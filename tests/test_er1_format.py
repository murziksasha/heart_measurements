import glob
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from import_local_er1 import (  # noqa: E402
    ER1_TRAILER_MAGIC,
    ER1FormatError,
    count_samples,
    crc16_ccitt_false,
    decompress_er1,
    parse_er1_header,
    parse_er1_trailer,
    verify_er1_checksum,
)
import repair_er1_decoded as repair  # noqa: E402

DATA = os.path.join(ROOT, "Data", "DATA", "userfiles", "subusr")
R_FILES = sorted(glob.glob(os.path.join(DATA, "*", "*R2*")))
# Decoded files written by the vendor app (before the Python importer existed).
VENDOR_STAMPS = ("20240930124937", "20240930173705", "20240930212036", "20241001092916",
                 "20260513131523", "20261004161900", "20261004205450")
VENDOR_GOLDEN = [p for p in R_FILES if p.endswith(VENDOR_STAMPS)]


def _read(p):
    with open(p, "rb") as f:
        return f.read()


def _decoded_path(r_path):
    return os.path.join(os.path.dirname(r_path), os.path.basename(r_path).replace("R", "", 1))


def _make(body, duration=2):
    hdr = b"\x01\xea\x07\x0a\x04\x10\x12\x37\x00\x00"
    crc = crc16_ccitt_false(hdr + body)
    return hdr + body + struct.pack("<II", duration, crc) + b"\x00" * 8 + ER1_TRAILER_MAGIC


@pytest.mark.parametrize("r_path", VENDOR_GOLDEN, ids=os.path.basename)
def test_golden_vendor_decode(r_path):
    assert decompress_er1(_read(r_path)) == _read(_decoded_path(r_path))


@pytest.mark.parametrize("r_path", R_FILES, ids=os.path.basename)
def test_all_r_files(r_path):
    r = _read(r_path)
    pcm = decompress_er1(r)
    t = parse_er1_trailer(r)
    assert len(pcm) == t["duration"] * 250
    assert count_samples(r) * 2 == len(pcm)
    assert verify_er1_checksum(r)
    assert os.path.getsize(_decoded_path(r_path)) == len(pcm)  # repaired in repo


def test_header():
    h = parse_er1_header(b"\x01\xea\x07\x0a\x04\x10\x12\x37\x00\x00")
    assert h["version"] == 1
    assert h["start"].isoformat() == "2026-10-04T16:18:55"


def test_trailer_and_escapes():
    body = bytes([5, 0xFD, 0x80, 0x10, 0x01, 0x7F, 3, 0x81, 1])
    r = _make(body, duration=330)
    assert parse_er1_trailer(r)["duration"] == 330
    assert parse_er1_trailer(r)["duration_seconds"] == 330
    assert struct.unpack("<5h", decompress_er1(r)) == (5, 2, 0x110, 0x110 + 130, 0x110 + 2)
    assert verify_er1_checksum(r)
    assert not verify_er1_checksum(r[:10] + b"\x06" + r[11:])


def test_bad_magic():
    r = _make(b"\x01" * 20)
    bad = r[:-1] + b"\x00"
    with pytest.raises(ER1FormatError):
        decompress_er1(bad)
    with pytest.raises(ER1FormatError):
        parse_er1_trailer(bad)


def test_crc_known_vector():
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_repair(tmp_path):
    d = tmp_path / "Data"
    d.mkdir()
    r = _make(bytes([1, 2, 3, 4]), duration=0)
    (d / "1234567890R20260101000000").write_bytes(r)
    good = decompress_er1(r)
    (d / "123456789020260101000000").write_bytes(good + b"\xAA" * 40)
    (d / "123456789020260101000001").write_bytes(b"\x00" * 540)  # no R file
    assert repair.main([str(d), "--dry-run"]) == 0
    assert (d / "123456789020260101000000").stat().st_size == len(good) + 40
    assert repair.main([str(d)]) == 0
    assert (d / "123456789020260101000000").read_bytes() == good
    assert (d / "123456789020260101000001").stat().st_size == 500  # 540 % 250 == 40 -> trimmed
    backups = list(tmp_path.glob("er1_repair_backup_*"))
    assert len(backups) == 1
    assert (backups[0] / "123456789020260101000000").stat().st_size == len(good) + 40
    assert repair.find_candidates(str(d)) == []
