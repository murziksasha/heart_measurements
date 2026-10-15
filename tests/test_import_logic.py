import unittest
import os
import shutil
import tempfile
import sqlite3
import struct
from import_local_er1 import (
    decompress_er1,
    count_samples,
    parse_header_timestamp,
    format_timestamp_display,
    format_duration,
    format_file_size,
    format_report_chip,
    guess_serial,
    scan_folder_records,
    is_er1_recording,
)

class TestImportLogic(unittest.TestCase):
    def test_decompress_empty(self):
        self.assertEqual(decompress_er1(b""), b"")
        self.assertEqual(decompress_er1(b"0123456789"), b"")

    def test_decompress_sample(self):
        # 10 byte header + simple delta
        # Header: 10 bytes
        header = b"\x01\xea\x07\n\x05\x17\x07\x07\x00\x00"
        # Delta: byte 5, byte -3
        deltas = bytes([5, 256 - 3])
        pcm = decompress_er1(header + deltas)
        self.assertEqual(len(pcm), 4) # 2 samples * 2 bytes
        s1, s2 = struct.unpack("<2h", pcm)
        self.assertEqual(s1, 5)
        self.assertEqual(s2, 2)

    def test_count_samples(self):
        header = b"\x01\xea\x07\n\x05\x17\x07\x07\x00\x00"
        deltas = bytes([1, 2, 3, 4, 5])
        cnt = count_samples(header + deltas)
        self.assertEqual(cnt, 5)

    def test_parse_header_timestamp(self):
        header = b"\x01\xea\x07\n\x05\x17\x07\x07\x00\x00"
        ts = parse_header_timestamp(header, "dummy.dat")
        self.assertEqual(ts, "20261005230707")

        # Filename override
        ts_file = parse_header_timestamp(header, "R20261005230712")
        self.assertEqual(ts_file, "20261005230712")

    def test_guess_serial_never_invents_one(self):
        self.assertIsNone(guess_serial(["R20261007120000", "readme.txt"]))
        self.assertEqual(guess_serial(["2306490032R20261007120000"]), "2306490032")
        self.assertEqual(guess_serial(["notes", "2306490032"]), "2306490032")

    def test_report_chip_and_file_size(self):
        self.assertEqual(format_file_size(1536), "1 KB")
        self.assertEqual(
            format_report_chip({"avg": 77, "min": 49, "max": 129, "diagnosis": "Normal sinus rhythm"}),
            "77 avg · 49–129 · Normal sinus rhythm",
        )
        self.assertEqual(format_report_chip(None), "")

    def test_format_helpers(self):
        self.assertEqual(format_timestamp_display("20261005230712"), "2026-10-05 23:07:12")
        self.assertEqual(format_duration(3665), "1 h 01 m")
        self.assertEqual(format_duration(125), "2 m 05 s")
        self.assertEqual(format_duration(45), "45 s")

    def test_is_er1_recording_accepts_valid(self):
        temp_dir = tempfile.mkdtemp()
        try:
            valid_header = b"\x01\xea\x07\n\x07\x0c\x00\x00\x00\x00" + b"\x00" * 6
            # Test without serial
            p1 = os.path.join(temp_dir, "R20261007120000")
            with open(p1, "wb") as f:
                f.write(valid_header)
            self.assertTrue(is_er1_recording(p1))

            # Test with serial
            p2 = os.path.join(temp_dir, "2306490032R20261007120000")
            with open(p2, "wb") as f:
                f.write(valid_header)
            self.assertTrue(is_er1_recording(p2))
        finally:
            shutil.rmtree(temp_dir)

    def test_is_er1_recording_rejects_invalid(self):
        temp_dir = tempfile.mkdtemp()
        try:
            valid_header = b"\x01\xea\x07\n\x07\x0c\x00\x00\x00\x00" + b"\x00" * 6

            # Rejects RSlogo.png
            p_png = os.path.join(temp_dir, "RSlogo.png")
            with open(p_png, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
            self.assertFalse(is_er1_recording(p_png))

            # Rejects .txt whose name starts with R
            p_txt = os.path.join(temp_dir, "Rnotes.txt")
            with open(p_txt, "wb") as f:
                f.write(valid_header)
            self.assertFalse(is_er1_recording(p_txt))

            # Rejects correctly named file whose first byte is not 0x01
            p_bad_byte = os.path.join(temp_dir, "R20261007120000")
            with open(p_bad_byte, "wb") as f:
                f.write(b"\x00\xea\x07\n\x07\x0c\x00\x00\x00\x00" + b"\x00" * 6)
            self.assertFalse(is_er1_recording(p_bad_byte))
        finally:
            shutil.rmtree(temp_dir)

    def test_scan_folder_records(self):
        temp_dir = tempfile.mkdtemp()
        try:
            # Create a mock R file
            fpath = os.path.join(temp_dir, "R20261007120000")
            header = b"\x01\xea\x07\n\x07\x0c\x00\x00\x00\x00"
            with open(fpath, "wb") as f:
                f.write(header + b"\x01" * 500)

            records = scan_folder_records(temp_dir)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["filename"], "R20261007120000")
            self.assertEqual(rec["timestamp"], "20261007120000")
            self.assertEqual(rec["datetime_display"], "2026-10-07 12:00:00")
            self.assertFalse(rec["is_duplicate"])
        finally:
            shutil.rmtree(temp_dir)

    def test_scan_folder_records_filters_non_ecg(self):
        temp_dir = tempfile.mkdtemp()
        try:
            # Valid recording
            rec_path = os.path.join(temp_dir, "R20261007120000")
            valid_header = b"\x01\xea\x07\n\x07\x0c\x00\x00\x00\x00"
            with open(rec_path, "wb") as f:
                f.write(valid_header + b"\x01" * 500)

            # RSlogo.png in the same folder
            logo_path = os.path.join(temp_dir, "RSlogo.png")
            with open(logo_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 500)

            records = scan_folder_records(temp_dir)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["filename"], "R20261007120000")
        finally:
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    unittest.main()
