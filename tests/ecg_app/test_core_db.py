import hashlib
import shutil
import sqlite3
import struct
from pathlib import Path

import numpy as np
import pytest

from ecg_app.core import er1_format as er1
from ecg_app.core.models import AnalysisResult, CloudAccount, Device, Patient, Recording
from ecg_app.db.migrations import LATEST, connect, current_version, migrate
from ecg_app.db.repository import Repository
from ecg_app.importers.vendor_import import run_import

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "Data"
SUB1 = VENDOR / "DATA" / "userfiles" / "subusr" / "1"


def _make(body, duration=2):
    hdr = b"\x01\xea\x07\x0a\x04\x10\x12\x37\x00\x00"
    crc = er1.crc16_ccitt_false(hdr + body)
    return hdr + body + struct.pack("<II", duration, crc) + b"\x00" * 8 + er1.TRAILER_MAGIC


# --- format -------------------------------------------------------------

def test_decode_escapes_numpy():
    r = _make(bytes([5, 0xFD, 0x80, 0x10, 0x01, 0x7F, 3, 0x81, 1]), 330)
    s = er1.decode(r)
    assert s.dtype == np.int16
    assert s.tolist() == [5, 2, 0x110, 0x110 + 130, 0x110 + 2]
    assert er1.parse_trailer(r).duration_seconds == 165
    assert er1.verify_checksum(r)
    assert er1.parse_header(r).start.isoformat() == "2026-10-04T16:18:55"


def test_decode_bad_magic():
    with pytest.raises(er1.ER1FormatError):
        er1.decode(_make(b"\x01" * 4)[:-1] + b"\x00")


def test_decode_golden_vendor():
    r = (SUB1 / "2306490032R20261004161900").read_bytes()
    assert er1.decode_to_bytes(r) == (SUB1 / "230649003220261004161900").read_bytes()
    assert np.array_equal(er1.decode(r), er1.load_pcm(SUB1 / "230649003220261004161900"))


# --- schema / migrations ------------------------------------------------

def test_migrations(tmp_path):
    conn = connect(tmp_path / "a.db")
    assert current_version(conn) == LATEST
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"patients", "devices", "recordings", "analysis_results", "settings", "cloud_account"} <= tables
    assert migrate(conn) == LATEST  # idempotent
    conn.execute(f"PRAGMA user_version = {LATEST + 1}")
    with pytest.raises(RuntimeError):
        migrate(conn)


def test_no_secret_columns(tmp_path):
    conn = connect(tmp_path / "a.db")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cloud_account)")}
    assert not cols & {"password", "token", "vanish_id"}


# --- repository ---------------------------------------------------------

def test_repository_crud(tmp_path):
    repo = Repository(connect(tmp_path / "a.db"))
    p = repo.patients.add(Patient(name="Test", gender="male", birthday="1985-02-20"))
    assert p.id and p.created_at
    p.name = "Renamed"
    assert repo.patients.update(p).name == "Renamed"
    d = repo.devices.add(Device(serial="123"))
    r = repo.recordings.add(Recording(patient_id=p.id, device_id=d.id, start_time="2026-10-04 16:18:55", duration_s=165))
    assert repo.recordings.for_patient(p.id)[0].id == r.id
    a = repo.analysis.add(AnalysisResult(recording_id=r.id, source="local", payload={"hr": 70, "ім'я": "т"}))
    assert repo.analysis.get(a.id).payload == {"hr": 70, "ім'я": "т"}
    with pytest.raises(sqlite3.IntegrityError):
        repo.analysis.add(AnalysisResult(recording_id=r.id, source="other"))
    acc = repo.accounts.add(CloudAccount(email="a@b.c", remember=True))
    assert acc.remember is True
    repo.settings.set("lang", "uk")
    assert repo.settings.get("lang") == "uk" and repo.settings.get("x", 1) == 1
    repo.patients.delete(p.id)  # cascades
    assert repo.recordings.list() == [] and repo.analysis.list() == []


# --- vendor import ------------------------------------------------------

def _tree_hash(root: Path):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def vendor_copy(tmp_path_factory):
    dst = tmp_path_factory.mktemp("v") / "Data"
    shutil.copytree(VENDOR / "DATA", dst / "DATA", ignore=shutil.ignore_patterns("*.bak"))
    shutil.copy2(VENDOR / "config.ini", dst / "config.ini")
    return dst


def test_vendor_import(vendor_copy, tmp_path):
    before = _tree_hash(vendor_copy)
    target = tmp_path / "new"
    merge = {2: 1}
    dry = run_import(vendor_copy, target, dry_run=True, merge=merge)
    assert not target.exists()
    rep = run_import(vendor_copy, target, merge=merge)
    assert dict(rep.counts) == dict(dry.counts)
    assert rep.counts["recordings_new"] == 11 and rep.counts["recordings_deduped"] == 1
    assert rep.counts["reports_new"] == 4 and rep.counts["settings_new"] == 3
    assert rep.counts["patients_new"] == 1 and rep.counts["devices_new"] == 1
    assert not any("placeholder" in w for w in rep.warnings)
    again = run_import(vendor_copy, target, merge=merge)
    assert again.counts["recordings_new"] == 0 and again.counts["recordings_existing"] == 11
    assert again.counts["reports_existing"] == 4 and again.counts["settings_existing"] == 3
    assert _tree_hash(vendor_copy) == before  # non-destructive

    repo = Repository(connect(target / "ecg_app.db"))
    pats = repo.patients.list()
    assert [p.name for p in pats] == ["Grygoriev"]
    assert len(repo.recordings.for_patient(pats[0].id)) == 11
    assert repo.settings.get("language") == 0 and repo.settings.get("wave_type") == 1
    assert repo.settings.get("mv_height_scale") == 1.0
    assert repo.accounts.list()[0].server_user_id == 530338
    for r in repo.recordings.list():
        pcm = (target / r.pcm_path).read_bytes()
        assert hashlib.sha256(pcm).hexdigest() == r.pcm_sha256
        assert len(pcm) == int(r.duration_s * 500)
        assert er1.decode_to_bytes((target / r.raw_path).read_bytes()) == pcm
    cloud = repo.analysis.list()
    assert len(cloud) == 4 and all(a.source == "cloud" and a.payload["code"] == 200 for a in cloud)
    assert all((target / a.pdf_path).exists() for a in cloud)


def test_vendor_import_dedupes_without_merge(vendor_copy, tmp_path):
    # subusr/2 only holds a duplicate of a subusr/1 recording -> deduped, no placeholder
    rep = run_import(vendor_copy, tmp_path / "n", dry_run=True)
    assert rep.counts["patients_new"] == 1 and rep.counts["recordings_new"] == 11
    assert rep.counts["recordings_deduped"] == 1


def test_parse_merge():
    from ecg_app.importers.vendor_import import parse_merge
    assert parse_merge(["2=1", "3=1"]) == {2: 1, 3: 1}
    for bad in (["2"], ["a=1"], ["1=1"]):
        with pytest.raises(ValueError):
            parse_merge(bad)
