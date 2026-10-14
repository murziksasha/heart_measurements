"""One-time, non-destructive, idempotent import of the old vendor data.

Reads <vendor>/DATA/db_lepu_care_world.db (read-only) and <vendor>/DATA/userfiles,
writes the new schema + layout:

    <data>/ecg_app.db
    <data>/recordings/<patient_id>/<serial>_<YYYYMMDDhhmmss>.er1   raw R file copy
    <data>/recordings/<patient_id>/<serial>_<YYYYMMDDhhmmss>.pcm   int16 LE, 250 Hz
    <data>/reports/<recording_id>/cloud_report.json|.pdf
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core import er1_format as er1
from ..core.models import AnalysisResult, CloudAccount, Device, Patient, Recording
from ..db.migrations import connect
from ..db.repository import Repository

R_RE = re.compile(r"^(\d{8,12})R(\d{14})$")
PCM_RE = re.compile(r"^(\d{10})(\d{14})$")
REPORT_RE = re.compile(r"^report_(\d+)_(\d+)_(\d{14})\.json$")
GENDER = {1: "female", 2: "male"}


@dataclass
class VendorRecording:
    subusr_id: int
    serial: str
    stamp: str
    r_file: Optional[Path] = None
    pcm_file: Optional[Path] = None
    report_json: Optional[Path] = None
    report_pdf: Optional[Path] = None
    db_row: Optional[dict] = None


@dataclass
class ImportReport:
    counts: Counter = field(default_factory=Counter)
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"{k}: {v}" for k, v in sorted(self.counts.items())]
        lines += [f"WARNING: {w}" for w in self.warnings]
        return "\n".join(lines)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _iso(stamp: str) -> str:
    return datetime.strptime(stamp, "%Y%m%d%H%M%S").isoformat(sep=" ")


def read_vendor_db(db_file: Path) -> dict:
    out = {"subusers": [], "devices": [], "admins": [], "records": []}
    if not db_file.exists():
        return out
    conn = sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for key, sql in (("subusers", "SELECT * FROM tb_subuser"), ("devices", "SELECT * FROM tb_device"),
                         ("admins", "SELECT admin, userid FROM tb_admin"), ("records", "SELECT * FROM tb_record")):
            try:
                out[key] = [dict(r) for r in conn.execute(sql)]
            except sqlite3.DatabaseError:
                pass
    finally:
        conn.close()
    return out


def scan_userfiles(userfiles: Path, records: list) -> dict:
    found: dict = {}

    def get(sub, sn, ts):
        return found.setdefault((sub, sn, ts), VendorRecording(sub, sn, ts))

    base = userfiles / "subusr"
    if base.exists():
        for d in sorted(p for p in base.iterdir() if p.is_dir() and p.name.isdigit()):
            sub = int(d.name)
            for f in sorted(d.iterdir()):
                if not f.is_file():
                    continue
                if m := R_RE.match(f.name):
                    get(sub, m[1], m[2]).r_file = f
                elif m := PCM_RE.match(f.name):
                    get(sub, m[1], m[2]).pcm_file = f
                elif m := REPORT_RE.match(f.name):
                    vr = get(int(m[1]), m[2], m[3])
                    vr.report_json = f
                    pdf = d / f"Record_{m[1]}_{m[2]}_{m[3]}Report.pdf"
                    if pdf.exists():
                        vr.report_pdf = pdf
    for row in records:
        key = (row.get("subusr_id"), row.get("sn"), row.get("checktime"))
        if key in found:
            found[key].db_row = row
    return found


CONFIG_KEYS = {"Language": ("language", int), "WaveType": ("wave_type", int), "MVHeightScale": ("mv_height_scale", float)}


def read_vendor_config(ini: Path) -> dict:
    """Language/WaveType/MVHeightScale from vendor config.ini [General]."""
    if not ini.exists():
        return {}
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    try:
        cp.read(ini, encoding="utf-8")
    except configparser.Error:
        return {}
    sec = cp["General"] if cp.has_section("General") else {}
    out = {}
    for k, (name, conv) in CONFIG_KEYS.items():
        if k in sec:
            try:
                out[name] = conv(sec[k])
            except ValueError:
                pass
    return out


def merge_subusers(recs: dict, merge: dict, rep: "ImportReport") -> dict:
    """Map subuser ids (merge {src: dst}) and dedupe by (serial, start stamp)."""
    out: dict = {}
    for key in sorted(recs, key=lambda k: (k[0] in merge, k)):
        vr = recs[key]
        sub = merge.get(vr.subusr_id, vr.subusr_id)
        k = (vr.serial, vr.stamp)
        if k not in out:
            vr.subusr_id = sub
            out[k] = vr
            continue
        cur = out[k]
        rep.counts["recordings_deduped"] += 1
        for f in ("r_file", "pcm_file", "report_json", "report_pdf", "db_row"):
            if getattr(cur, f) is None and getattr(vr, f) is not None:
                setattr(cur, f, getattr(vr, f))
        if vr.r_file and cur.r_file and sha256(vr.r_file) != sha256(cur.r_file):
            rep.warnings.append(f"{vr.r_file}: differs from duplicate {cur.r_file}; kept the latter")
    return out


def parse_merge(items) -> dict:
    out = {}
    for it in items or []:
        src, _, dst = it.partition("=")
        if not (src.isdigit() and dst.isdigit()) or src == dst:
            raise ValueError(f"bad --merge-subuser value: {it!r} (expected SRC=DST)")
        out[int(src)] = int(dst)
    return out


def run_import(vendor_root: Path, data_dir: Path, dry_run: bool = False, merge: Optional[dict] = None) -> ImportReport:
    """vendor_root is the old portable 'Data' folder (contains DATA/).
    merge maps vendor subuser ids into another one, e.g. {2: 1}."""
    merge = dict(merge or {})
    vendor_root = Path(vendor_root)
    data_dir = Path(data_dir)
    vdata = vendor_root / "DATA" if (vendor_root / "DATA").exists() else vendor_root
    rep = ImportReport()
    vdb = read_vendor_db(vdata / "db_lepu_care_world.db")
    raw_recs = scan_userfiles(vdata / "userfiles", vdb["records"])
    recs = merge_subusers(raw_recs, merge, rep)
    for row in vdb["records"]:
        if (row.get("subusr_id"), row.get("sn"), row.get("checktime")) not in raw_recs:
            rep.warnings.append(f"vendor record {row.get('recordid')} ({row.get('checktime')}) has no files; skipped")

    if dry_run:
        repo = None
        if (data_dir / "ecg_app.db").exists():
            conn = sqlite3.connect(f"file:{(data_dir / 'ecg_app.db').as_posix()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            repo = Repository(conn)
    else:
        data_dir.mkdir(parents=True, exist_ok=True)
        repo = Repository(connect(data_dir / "ecg_app.db"))

    def exists(table_repo, ref):
        return repo is not None and table_repo(repo).by("legacy_ref", ref) is not None

    # Account (no secrets: vendor vanish_id is NOT imported)
    for a in vdb["admins"]:
        if repo is not None and repo.accounts.by("email", a["admin"]):
            rep.counts["accounts_existing"] += 1
            continue
        rep.counts["accounts_new"] += 1
        if not dry_run:
            repo.accounts.add(CloudAccount(email=a["admin"], server_user_id=a["userid"]))

    # Devices
    serials = {d["sn"]: d for d in vdb["devices"]}
    for vr in recs.values():
        serials.setdefault(vr.serial, {"sn": vr.serial})
    device_ids: dict = {}
    for sn, d in serials.items():
        cur = repo.devices.by("serial", sn) if repo is not None else None
        if cur:
            rep.counts["devices_existing"] += 1
            device_ids[sn] = cur.id
            continue
        rep.counts["devices_new"] += 1
        if not dry_run:
            device_ids[sn] = repo.devices.add(Device(
                serial=sn, hw_version=d.get("hwversion"), fw_version=d.get("fwversion"),
                bl_version=d.get("blversion"), device_type=d.get("devicetype"),
                protocol_version=d.get("protocolversion"), branch_code=d.get("branchcode"))).id

    # Patients (DB rows + folders without a DB row)
    subs = {s["subusr_id"]: s for s in vdb["subusers"] if s["subusr_id"] not in merge}
    for vr in recs.values():
        if vr.subusr_id not in subs:
            subs[vr.subusr_id] = None
    patient_ids: dict = {}
    for sid, s in sorted(subs.items()):
        ref = f"vendor:subuser:{sid}"
        cur = repo.patients.by("legacy_ref", ref) if repo is not None else None
        if cur:
            rep.counts["patients_existing"] += 1
            patient_ids[sid] = cur.id
            continue
        rep.counts["patients_new"] += 1
        if s is None:
            rep.warnings.append(f"subusr folder {sid} has no tb_subuser row; placeholder patient created")
            p = Patient(name=f"Imported patient {sid}", legacy_ref=ref)
        else:
            p = Patient(name=s.get("name") or f"Patient {sid}", gender=GENDER.get(s.get("gender")),
                        birthday=s.get("birthday") or None, height_cm=s.get("height") or None,
                        weight_kg=s.get("weight") or None, contact=s.get("userkey") or None,
                        cloud_member_id=s.get("familyid"), legacy_ref=ref)
        if not dry_run:
            patient_ids[sid] = repo.patients.add(p).id

    # Recordings + reports
    for key in sorted(recs, key=lambda k: (k[1], k[0])):
        vr = recs[key]
        ref = f"vendor:rec:{vr.serial}:{vr.stamp}"
        if exists(lambda r: r.recordings, ref):
            rep.counts["recordings_existing"] += 1
            rec_id = repo.recordings.by("legacy_ref", ref).id
        elif vr.r_file is None and vr.pcm_file is None:
            rep.warnings.append(f"{ref}: only a report, no ECG data; skipped")
            continue
        else:
            rec_id = None
            try:
                raw = vr.r_file.read_bytes() if vr.r_file else None
                if raw is not None:
                    pcm = er1.decode_to_bytes(raw)
                    duration = er1.parse_trailer(raw).duration_seconds
                    if not er1.verify_checksum(raw):
                        rep.warnings.append(f"{vr.r_file.name}: CRC mismatch (imported anyway)")
                    if vr.pcm_file and vr.pcm_file.stat().st_size != len(pcm):
                        rep.warnings.append(f"{vr.pcm_file.name}: vendor PCM differs from re-decode; using re-decode")
                else:
                    pcm = vr.pcm_file.read_bytes()
                    if len(pcm) % 500 == 40:
                        pcm = pcm[:-40]
                        rep.counts["pcm_trimmed_40"] += 1
                    duration = len(pcm) / 2 / er1.SAMPLE_RATE
                    rep.counts["recordings_pcm_only"] += 1
            except er1.ER1FormatError as e:
                rep.warnings.append(f"{ref}: {e}; skipped")
                continue
            rep.counts["recordings_new"] += 1
            if not dry_run:
                pid = patient_ids[vr.subusr_id]
                rel = Path("recordings") / str(pid)
                (data_dir / rel).mkdir(parents=True, exist_ok=True)
                raw_rel = None
                if raw is not None:
                    raw_rel = rel / f"{vr.serial}_{vr.stamp}.er1"
                    shutil.copy2(vr.r_file, data_dir / raw_rel)
                pcm_rel = rel / f"{vr.serial}_{vr.stamp}.pcm"
                (data_dir / pcm_rel).write_bytes(pcm)
                row = vr.db_row or {}
                rec_id = repo.recordings.add(Recording(
                    patient_id=pid, device_id=device_ids.get(vr.serial), start_time=_iso(vr.stamp),
                    duration_s=duration, raw_path=raw_rel.as_posix() if raw_rel else None,
                    raw_sha256=_sha_bytes(raw) if raw is not None else None,
                    pcm_path=pcm_rel.as_posix(), pcm_sha256=_sha_bytes(pcm),
                    note=row.get("note") or "", cloud_file_id=row.get("fileid") or None,
                    legacy_ref=ref)).id

        if vr.report_json:
            aref = f"vendor:report:{vr.serial}:{vr.stamp}"
            if exists(lambda r: r.analysis, aref):
                rep.counts["reports_existing"] += 1
                continue
            try:
                payload = json.loads(vr.report_json.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                rep.warnings.append(f"{vr.report_json.name}: bad JSON ({e}); skipped")
                continue
            rep.counts["reports_new"] += 1
            if vr.report_pdf:
                rep.counts["report_pdfs"] += 1
            if not dry_run:
                rdir = Path("reports") / str(rec_id)
                (data_dir / rdir).mkdir(parents=True, exist_ok=True)
                shutil.copy2(vr.report_json, data_dir / rdir / "cloud_report.json")
                pdf_rel = None
                if vr.report_pdf:
                    pdf_rel = rdir / "cloud_report.pdf"
                    shutil.copy2(vr.report_pdf, data_dir / pdf_rel)
                repo.analysis.add(AnalysisResult(
                    recording_id=rec_id, source="cloud", payload=payload,
                    pdf_path=pdf_rel.as_posix() if pdf_rel else None, legacy_ref=aref))

    cfg = read_vendor_config(vendor_root / "config.ini")
    for name, val in cfg.items():
        if repo is not None and repo.settings.get(name) is not None:
            rep.counts["settings_existing"] += 1
            continue
        rep.counts["settings_new"] += 1
        if not dry_run:
            repo.settings.set(name, val)

    if repo is not None:
        if not dry_run:
            repo.settings.set("vendor_import", {"source": str(vendor_root), "at": datetime.now().isoformat(timespec="seconds")})
        repo.conn.close()
    return rep


def main(argv=None) -> int:
    from ..config import data_dir

    ap = argparse.ArgumentParser(description="Import old vendor Data/ into the new ecg_app layout.")
    ap.add_argument("vendor_data", type=Path, help="old portable Data folder (contains DATA/)")
    ap.add_argument("--target", type=Path, default=None, help="new data dir (default: config.data_dir())")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--merge-subuser", action="append", metavar="SRC=DST",
                    help="merge vendor subuser SRC into DST (repeatable), e.g. 2=1")
    a = ap.parse_args(argv)
    try:
        merge = parse_merge(a.merge_subuser)
    except ValueError as e:
        ap.error(str(e))
    target = a.target or data_dir()
    rep = run_import(a.vendor_data, target, dry_run=a.dry_run, merge=merge)
    print(("DRY RUN -> " if a.dry_run else "Imported -> ") + str(target))
    print(rep.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
