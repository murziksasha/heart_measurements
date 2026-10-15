#!/usr/bin/env python3
"""Repair decoded ER1 files that carry 40 trailing garbage bytes (old trailer bug)."""

import argparse
import os
import re
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from import_local_er1 import (  # noqa: E402
    ER1_TRAILER_LEN,
    ER1FormatError,
    decompress_er1,
    parse_er1_trailer,
)

BUG_EXTRA = ER1_TRAILER_LEN * 2  # 20 trailer bytes decoded as 20 int16 samples
DECODED_RE = re.compile(r"^(\d{8,12}?)(\d{14})$")
BACKUP_PREFIX = "er1_repair_backup_"


def expected_length(decoded_path):
    """Returns (expected_len, source) or (None, reason)."""
    name = os.path.basename(decoded_path)
    m = DECODED_RE.match(name)
    if not m:
        return None, "name"
    r_path = os.path.join(os.path.dirname(decoded_path), m.group(1) + "R" + m.group(2))
    if os.path.exists(r_path):
        with open(r_path, "rb") as f:
            r_bytes = f.read()
        try:
            exp = len(decompress_er1(r_bytes))
        except ER1FormatError as e:
            return None, f"R file invalid ({e})"
        src = "R file re-decode"
        if trailer_expected_length(r_bytes) == exp:
            src += " + trailer duration"
        return exp, src
    # No R file: whole seconds at 125 Hz -> length is a multiple of 250 bytes.
    size = os.path.getsize(decoded_path)
    if size % 250 == BUG_EXTRA:
        return size - BUG_EXTRA, "length heuristic (no R file)"
    return None, "no R file"


def find_candidates(data_dir):
    out = []
    for dirpath, dirnames, filenames in os.walk(data_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(BACKUP_PREFIX)]
        for fn in sorted(filenames):
            if not DECODED_RE.match(fn):
                continue
            path = os.path.join(dirpath, fn)
            size = os.path.getsize(path)
            exp, src = expected_length(path)
            if exp is None:
                continue
            if size == exp + BUG_EXTRA:
                out.append((path, size, exp, src))
    return out


def trailer_expected_length(r_bytes):
    """Expected decoded bytes from trailer duration (seconds): duration*125 samples * 2 bytes."""
    return parse_er1_trailer(r_bytes)["duration"] * 250


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_dir", nargs="?", default=os.path.join(ROOT, "Data"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backup-root", default=None, help="default: <data_dir>/..")
    args = ap.parse_args(argv)

    cands = find_candidates(args.data_dir)
    if not cands:
        print("Nothing to repair.")
        return 0
    backup_root = args.backup_root or os.path.dirname(os.path.abspath(args.data_dir))
    backup_dir = os.path.join(backup_root, BACKUP_PREFIX + datetime.now().strftime("%Y%m%d_%H%M%S"))
    for path, size, exp, src in cands:
        rel = os.path.relpath(path, args.data_dir)
        print(f"{'WOULD TRIM' if args.dry_run else 'TRIM'} {rel}: {size} -> {exp} ({src})")
        if args.dry_run:
            continue
        dst = os.path.join(backup_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(path, dst)
        with open(path, "r+b") as f:
            f.truncate(exp)
    if not args.dry_run:
        print(f"Backups: {backup_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
