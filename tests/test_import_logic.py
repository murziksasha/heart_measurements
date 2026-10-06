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
    scan_folder_records
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

    def test_format_helpers(self):
        self.assertEqual(format_timestamp_display("20261005230712"), "2026-10-05 23:07:12")
        self.assertEqual(format_duration(3665), "1 h 01 m")
        self.assertEqual(format_duration(125), "2 m 05 s")
        self.assertEqual(format_duration(45), "45 s")

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

if __name__ == "__main__":
    unittest.main()
