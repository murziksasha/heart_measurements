#!/usr/bin/env python3
"""
AI-ECG Analysis Portable - Local ECG Record Importer
Imports .R* recording files from any folder or USB drive directly
into the portable AI-ECG patient database.
"""

import os
import sys
import glob
import shutil
import struct
import sqlite3
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "Data", "DATA", "db_lepu_care_world.db")
USERFILES_DIR = os.path.join(SCRIPT_DIR, "Data", "DATA", "userfiles", "subusr")

def decompress_er1(r_bytes):
    """
    Decompresses raw ER1 differential PCM recording into 16-bit signed PCM samples (250Hz).
    Byte-accurate reverse-engineered Lepu ER1 decompression algorithm.
    """
    if len(r_bytes) <= 10:
        return b""

    pos = 10  # Skip 10-byte recording header
    state = 0
    accumulator = 0
    low_byte = 0
    samples = []

    while pos < len(r_bytes):
        b = r_bytes[pos]
        pos += 1

        if state == 0:
            if b == 0x80:
                state = 1
            elif b == 0x7F:
                state = 3
            elif b == 0x81:
                state = 4
            else:
                delta = struct.unpack('<b', bytes([b]))[0]
                accumulator = (accumulator + delta) & 0xFFFF
                s16 = struct.unpack('<h', struct.pack('<H', accumulator))[0]
                accumulator = s16
                samples.append(s16)
        elif state == 1:
            low_byte = b
            state = 2
        elif state == 2:
            high_byte = struct.unpack('<b', bytes([b]))[0]
            val = (high_byte << 8) | low_byte
            s16 = struct.unpack('<h', struct.pack('<H', val & 0xFFFF))[0]
            accumulator = s16
            samples.append(s16)
            state = 0
        elif state == 3:
            accumulator = (accumulator + 127 + b) & 0xFFFF
            s16 = struct.unpack('<h', struct.pack('<H', accumulator))[0]
            accumulator = s16
            samples.append(s16)
            state = 0
        elif state == 4:
            accumulator = (accumulator - 127 - b) & 0xFFFF
            s16 = struct.unpack('<h', struct.pack('<H', accumulator))[0]
            accumulator = s16
            samples.append(s16)
            state = 0

    return struct.pack(f'<{len(samples)}h', *samples)

def parse_header_timestamp(r_bytes, fallback_filename):
    """Extract start timestamp from R header or filename."""
    if len(r_bytes) >= 8 and r_bytes[0] == 0x01:
        year, month, day, hour, minute, second = struct.unpack('<HBBBBB', r_bytes[1:8])
        try:
            dt = datetime(year, month, day, hour, minute, second)
            return dt.strftime('%Y%m%d%H%M%S')
        except Exception:
            pass

    # Fallback to filename timestamp
    base = os.path.basename(fallback_filename)
    digits = ''.join(c for c in base if c.isdigit())
    if len(digits) >= 14:
        return digits[:14]
    return datetime.now().strftime('%Y%m%d%H%M%S')

def get_default_device_and_subuser():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT sn FROM tb_device LIMIT 1")
    dev_row = cur.fetchone()
    sn = dev_row[0] if dev_row else "2306490032"

    cur.execute("SELECT subusr_id FROM tb_subuser LIMIT 1")
    sub_row = cur.fetchone()
    subusr_id = sub_row[0] if sub_row else 1

    conn.close()
    return sn, subusr_id

def import_r_file(filepath, sn=None, subusr_id=None):
    if not os.path.exists(filepath):
        print(f"[!] File not found: {filepath}")
        return False

    with open(filepath, "rb") as f:
        r_bytes = f.read()

    if len(r_bytes) < 16:
        print(f"[!] File too small: {filepath}")
        return False

    default_sn, default_subusr = get_default_device_and_subuser()
    if sn is None:
        sn = default_sn
    if subusr_id is None:
        subusr_id = default_subusr

    timestamp = parse_header_timestamp(r_bytes, filepath)
    print(f"[*] Processing recording timestamp: {timestamp}")

    # Ensure device is registered
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT sn FROM tb_device WHERE sn = ?", (sn,))
    if not cur.fetchone():
        print(f"[*] Auto-registering device {sn} in database...")
        cur.execute("""
            INSERT INTO tb_device(sn, admin, hwversion, fwversion, blversion, devicetype, protocolversion, branchcode)
            VALUES(?, '', 67, 16844800, 258, 13873, 1, '40040000')
        """, (sn,))
        conn.commit()

    # Destination directory
    dest_dir = os.path.join(USERFILES_DIR, str(subusr_id))
    os.makedirs(dest_dir, exist_ok=True)

    # 1. Raw R file: {sn}R{timestamp}
    raw_filename = f"{sn}R{timestamp}"
    raw_dest = os.path.join(dest_dir, raw_filename)
    shutil.copy2(filepath, raw_dest)
    print(f"[+] Saved raw recording: {raw_filename}")

    # 2. Decompress to converted dat: {sn}{timestamp}
    dat_filename = f"{sn}{timestamp}"
    dat_dest = os.path.join(dest_dir, dat_filename)
    dat_bytes = decompress_er1(r_bytes)
    with open(dat_dest, "wb") as f:
        f.write(dat_bytes)
    print(f"[+] Decompressed ECG data: {dat_filename} ({len(dat_bytes)} bytes)")

    # Calculate duration (at 250Hz sample rate, duration parameter is 2 * seconds)
    total_samples = len(dat_bytes) // 2
    seconds = total_samples // 250
    duration_val = seconds * 2

    # 3. Insert or update tb_record
    cur.execute("SELECT recordid FROM tb_record WHERE checktime = ? AND subusr_id = ?", (timestamp, subusr_id))
    existing = cur.fetchone()
    now_ts = datetime.now().strftime('%Y%m%d%H%M%S')

    if existing:
        print(f"[!] Record for {timestamp} already exists (ID: {existing[0]}). Updating...")
        cur.execute("""
            UPDATE tb_record SET sn = ?, duration = ?, syncdatetime = ?
            WHERE recordid = ?
        """, (sn, duration_val, now_ts, existing[0]))
    else:
        cur.execute("""
            INSERT INTO tb_record(sn, subusr_id, admin, checktime, duration, syncdatetime, fileversion, note, aistate, fileid)
            VALUES(?, ?, NULL, ?, ?, ?, '1', '', 0, '')
        """, (sn, subusr_id, timestamp, duration_val, now_ts))
        print(f"[+] Inserted new record into database (Duration: {seconds}s / {seconds//60} min)")

    conn.commit()
    conn.close()
    return True

def scan_and_import(target_path):
    if os.path.isfile(target_path):
        return import_r_file(target_path)
    elif os.path.isdir(target_path):
        r_files = [f for f in glob.glob(os.path.join(target_path, "*")) if os.path.isfile(f) and os.path.basename(f).startswith("R")]
        if not r_files:
            print(f"[-] No 'R*' recording files found in: {target_path}")
            return False
        print(f"[*] Found {len(r_files)} recording file(s):")
        success = 0
        for rf in r_files:
            print(f"\n--- Importing {os.path.basename(rf)} ---")
            if import_r_file(rf):
                success += 1
        print(f"\n[+] Successfully imported {success}/{len(r_files)} file(s).")
        return success > 0
    else:
        print(f"[!] Path does not exist: {target_path}")
        return False

def main():
    print("="*60)
    print("  AI-ECG PORTABLE - DIRECT ECG FILE IMPORTER")
    print("="*60)

    target = None
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        default_folder = r"C:\Users\user\Desktop\source ER1\sys  files from ER1"
        if os.path.exists(default_folder):
            prompt = f"Import from default ER1 folder ({default_folder})? [Y/n]: "
            ans = input(prompt).strip().lower()
            if ans in ("", "y", "yes"):
                target = default_folder

        if not target:
            target = input("Enter path to file or folder containing 'R*' recordings: ").strip().strip('"')

    if target:
        scan_and_import(target)
    else:
        print("[!] No file or folder selected.")

if __name__ == "__main__":
    main()
