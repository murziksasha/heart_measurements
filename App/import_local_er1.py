#!/usr/bin/env python3
"""
AI-ECG Analysis Portable - Local ECG Record Importer
Imports .R* recording files from any folder or USB drive directly
into the AI-ECG patient database. Supports active AppData and portable storage.
"""

import os
import sys
import re
import glob
import json
import shutil
import struct
import sqlite3
import array
import ctypes
from datetime import datetime

_SERIAL_BEFORE_R = re.compile(r"(?<!\d)(\d{8,12})R")
_SERIAL_EXACT = re.compile(r"^\d{8,12}$")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_target_locations():
    """
    Returns all existing DATA directory locations (portable and/or AppData).
    Ensures that imports are written to both if both exist.
    """
    locations = []
    
    # 1. Check local AppData
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        appdata_data = os.path.join(local_app_data, "ECG Browser", "DATA")
        if os.path.exists(appdata_data):
            locations.append(appdata_data)
            
    # 2. Check portable Data folder (script dir or parent dir if inside App)
    candidate_portable_dirs = [
        os.path.join(SCRIPT_DIR, "Data", "DATA"),
        os.path.join(os.path.dirname(SCRIPT_DIR), "Data", "DATA"),
    ]
    for pdir in candidate_portable_dirs:
        if os.path.exists(pdir) and pdir not in locations:
            locations.append(pdir)
            break
        
    # Fallback to portable if none exists yet
    if not locations:
        pdir = candidate_portable_dirs[0]
        os.makedirs(pdir, exist_ok=True)
        locations.append(pdir)
        
    return locations

def get_primary_db_path():
    """Returns the primary active database path."""
    locs = get_target_locations()
    for loc in locs:
        db = os.path.join(loc, "db_lepu_care_world.db")
        if os.path.exists(db):
            return db
    return os.path.join(locs[0], "db_lepu_care_world.db")

def decompress_er1(r_bytes):
    """
    Decompresses raw ER1 differential PCM recording into 16-bit signed PCM samples (250Hz).
    Byte-accurate reverse-engineered Lepu ER1 decompression algorithm.
    Optimized for high-speed batch processing.
    """
    if len(r_bytes) <= 10:
        return b""

    pos = 10  # Skip 10-byte recording header
    state = 0
    accumulator = 0
    low_byte = 0
    samples = array.array('h')
    n = len(r_bytes)

    while pos < n:
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
                delta = b if b < 128 else b - 256
                accumulator = (accumulator + delta) & 0xFFFF
                if accumulator >= 32768:
                    accumulator -= 65536
                samples.append(accumulator)
        elif state == 1:
            low_byte = b
            state = 2
        elif state == 2:
            high_byte = b if b < 128 else b - 256
            val = (high_byte << 8) | low_byte
            accumulator = val if val < 32768 else val - 65536
            samples.append(accumulator)
            state = 0
        elif state == 3:
            accumulator = (accumulator + 127 + b) & 0xFFFF
            if accumulator >= 32768:
                accumulator -= 65536
            samples.append(accumulator)
            state = 0
        elif state == 4:
            accumulator = (accumulator - 127 - b) & 0xFFFF
            if accumulator >= 32768:
                accumulator -= 65536
            samples.append(accumulator)
            state = 0

    return samples.tobytes()

def count_samples(r_bytes):
    """Quickly counts decompressed samples without allocating memory."""
    if len(r_bytes) <= 10:
        return 0
    pos = 10
    state = 0
    cnt = 0
    n = len(r_bytes)
    while pos < n:
        b = r_bytes[pos]
        pos += 1
        if state == 0:
            if b == 0x80: state = 1
            elif b == 0x7F: state = 3
            elif b == 0x81: state = 4
            else: cnt += 1
        elif state == 1:
            state = 2
        elif state == 2:
            cnt += 1
            state = 0
        elif state == 3:
            cnt += 1
            state = 0
        elif state == 4:
            cnt += 1
            state = 0
    return cnt

def parse_header_timestamp(r_bytes, fallback_filename):
    """
    Extract start timestamp from filename digits first (matching standard vendor naming),
    falling back to binary header if needed.
    """
    base = os.path.basename(fallback_filename)
    digits = ''.join(c for c in base if c.isdigit())
    if len(digits) >= 14:
        return digits[:14]

    if len(r_bytes) >= 8 and r_bytes[0] == 0x01:
        year, month, day, hour, minute, second = struct.unpack('<HBBBBB', r_bytes[1:8])
        try:
            dt = datetime(year, month, day, hour, minute, second)
            return dt.strftime('%Y%m%d%H%M%S')
        except Exception:
            pass

    return datetime.now().strftime('%Y%m%d%H%M%S')

def format_timestamp_display(ts_str):
    """Converts YYYYMMDDHHMMSS to YYYY-MM-DD HH:MM:SS."""
    if len(ts_str) >= 14:
        try:
            dt = datetime.strptime(ts_str[:14], '%Y%m%d%H%M%S')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    return ts_str

def guess_serial(names):
    """Serial printed into Lepu filenames as '{sn}R{timestamp}'. Never invents one."""
    for name in names:
        base = os.path.basename(str(name))
        match = _SERIAL_BEFORE_R.search(base)
        if match:
            return match.group(1)
    for name in names:
        base = os.path.basename(str(name))
        if _SERIAL_EXACT.match(base):
            return base
    return None


def format_file_size(num_bytes):
    """Short file size for the import list."""
    size = int(num_bytes or 0)
    if size < 1024:
        return "%d B" % size
    if size < 1024 * 1024:
        return "%d KB" % (size // 1024)
    return "%.1f MB" % (size / (1024 * 1024))


def format_report_chip(summary):
    """One line from a saved AI report: rate range and the first diagnosis."""
    if not summary:
        return ""
    parts = []
    if summary.get("avg") is not None:
        parts.append("%s avg" % summary["avg"])
    if summary.get("min") is not None and summary.get("max") is not None:
        parts.append("%s–%s" % (summary["min"], summary["max"]))
    if summary.get("diagnosis"):
        parts.append(summary["diagnosis"])
    return " · ".join(parts)


def load_report_summaries(subusr_id):
    """
    Map recording timestamp -> heart-rate summary from report JSON already on disk.
    Filename shape: report_{patient}_{serial}_{timestamp}.json
    """
    found = {}
    if subusr_id is None:
        return found
    for loc in get_target_locations():
        folder = os.path.join(loc, "userfiles", "subusr", str(subusr_id))
        if not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except Exception:
            continue
        for name in names:
            if not name.startswith("report_") or not name.endswith(".json"):
                continue
            parts = name[:-5].split("_")
            if len(parts) < 4:
                continue
            timestamp = parts[-1]
            path = os.path.join(folder, name)
            summary = _read_report_summary(path)
            if summary:
                pdf_name = "Record_%s_%s_%sReport.pdf" % (subusr_id, parts[-2], timestamp)
                summary["has_pdf"] = os.path.exists(os.path.join(folder, pdf_name))
                found[timestamp] = summary
    return found


def _read_report_summary(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    diagnosis = ""
    for item in data.get("diagnoseList") or []:
        if isinstance(item, dict) and item.get("diagnoseInfo"):
            diagnosis = str(item["diagnoseInfo"])
            break
    return {
        "avg": data.get("averageHeartRate"),
        "min": data.get("minHeartRate"),
        "max": data.get("maxHeartRate"),
        "diagnosis": diagnosis,
        "has_pdf": False,
    }


def find_recording_sources():
    """
    Removable drives that look like an ER1 stick (R* files or an MKFS folder).
    Serial is returned only when a filename actually contains one.
    """
    sources = []
    try:
        kernel32 = ctypes.windll.kernel32
        bitmask = kernel32.GetLogicalDrives()
    except Exception:
        return sources

    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        if not (bitmask & (1 << (ord(letter) - ord("A")))):
            continue
        drive = "%s:\\" % letter
        try:
            if kernel32.GetDriveTypeW(drive) != 2:
                continue
        except Exception:
            continue
        info = inspect_recording_folder(drive)
        mkfs = os.path.join(drive, "MKFS")
        if info["count"] <= 0 and not os.path.exists(mkfs):
            continue
        if info["serial"] is None and os.path.isdir(mkfs):
            try:
                info["serial"] = guess_serial(os.listdir(mkfs))
            except Exception:
                pass
        sources.append({
            "path": drive,
            "count": info["count"],
            "serial": info["serial"],
        })
    return sources


def inspect_recording_folder(folder_path):
    """Count top-level R* recordings and guess a serial from file names."""
    names = []
    count = 0
    if os.path.isdir(folder_path):
        try:
            names = os.listdir(folder_path)
        except Exception:
            names = []
        for name in names:
            full = os.path.join(folder_path, name)
            if os.path.isfile(full) and name.startswith("R"):
                count += 1
    return {"count": count, "serial": guess_serial(names)}


def format_duration(seconds):
    """Formats duration seconds into human-readable string (e.g. 11 h 27 m or 45 m 10 s)."""
    hrs = seconds // 3600
    rem = seconds % 3600
    mins = rem // 60
    secs = rem % 60
    if hrs > 0:
        return f"{hrs} h {mins:02d} m"
    elif mins > 0:
        return f"{mins} m {secs:02d} s"
    else:
        return f"{secs} s"

def get_subusers():
    """Retrieves all registered patients/subusers from the database."""
    db_path = get_primary_db_path()
    if not os.path.exists(db_path):
        return [{"id": 1, "name": "Grygoriev", "age": 41, "gender": "Male", "email": "1versuses1@gmail.com"}]
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    default_email = "1versuses1@gmail.com"
    try:
        cur.execute("SELECT admin FROM tb_admin LIMIT 1")
        row = cur.fetchone()
        if row and row[0]:
            default_email = row[0]
    except Exception:
        pass

    try:
        cur.execute("SELECT subusr_id, name, gender, birthday FROM tb_subuser ORDER BY subusr_id")
        rows = cur.fetchall()
    except Exception:
        rows = []
    conn.close()
    
    subusers = []
    current_year = datetime.now().year
    for r in rows:
        subusr_id = r[0]
        name = r[1] or f"User {subusr_id}"
        gender_code = r[2]
        gender_str = "Male" if gender_code == 2 else "Female" if gender_code == 1 else "Unknown"
        birthday_str = str(r[3]) if r[3] else ""
        age = 0
        if birthday_str:
            try:
                b_year = int(birthday_str.split('-')[0])
                age = max(0, current_year - b_year)
            except Exception:
                age = 0

        subusers.append({
            "id": subusr_id,
            "name": name,
            "age": age,
            "gender": gender_str,
            "email": default_email
        })
    if not subusers:
        subusers.append({"id": 1, "name": "Grygoriev", "age": 41, "gender": "Male", "email": default_email})
    return subusers

def get_default_device_and_subuser():
    db_path = get_primary_db_path()
    if not os.path.exists(db_path):
        return "2306490032", 1
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT sn FROM tb_device LIMIT 1")
    dev_row = cur.fetchone()
    sn = dev_row[0] if dev_row else "2306490032"

    cur.execute("SELECT subusr_id FROM tb_subuser LIMIT 1")
    sub_row = cur.fetchone()
    subusr_id = sub_row[0] if sub_row else 1

    conn.close()
    return sn, subusr_id

def get_existing_records(subusr_id=None):
    """Returns a dictionary of existing checktime -> record info."""
    db_path = get_primary_db_path()
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if subusr_id is not None:
        cur.execute("SELECT recordid, checktime, duration, sn FROM tb_record WHERE subusr_id = ?", (subusr_id,))
    else:
        cur.execute("SELECT recordid, checktime, duration, sn FROM tb_record")
    rows = cur.fetchall()
    conn.close()
    
    existing = {}
    for r in rows:
        existing[r[1]] = {"recordid": r[0], "duration": r[2], "sn": r[3]}
    return existing

def scan_folder_records(folder_path, subusr_id=None):
    """
    Scans a folder for ER1 recordings (starting with 'R'), analyzes each file,
    and checks uniqueness against the database.
    """
    if not os.path.exists(folder_path):
        return []

    r_files = [
        f for f in glob.glob(os.path.join(folder_path, "*"))
        if os.path.isfile(f) and os.path.basename(f).startswith("R")
    ]
    r_files.sort(key=lambda x: os.path.basename(x))

    existing = get_existing_records(subusr_id)
    records = []

    for filepath in r_files:
        filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        if size < 16:
            continue

        with open(filepath, "rb") as f:
            header_sample = f.read(16)
        
        timestamp = parse_header_timestamp(header_sample, filepath)
        datetime_display = format_timestamp_display(timestamp)

        # Count samples for duration
        with open(filepath, "rb") as f:
            full_data = f.read()
        sample_count = count_samples(full_data)
        seconds = sample_count // 250
        duration_display = format_duration(seconds)

        is_dup = timestamp in existing

        records.append({
            "filename": filename,
            "filepath": filepath,
            "timestamp": timestamp,
            "datetime_display": datetime_display,
            "duration_seconds": seconds,
            "duration_display": duration_display,
            "file_size": size,
            "is_duplicate": is_dup,
            "existing_id": existing.get(timestamp, {}).get("recordid") if is_dup else None
        })

    return records

def import_single_file(filepath, sn=None, subusr_id=None, force=False):
    """
    Imports one R* file into all active DATA locations (portable and AppData).
    Returns (success: bool, status_msg: str, timestamp: str)
    """
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}", ""

    with open(filepath, "rb") as f:
        r_bytes = f.read()

    if len(r_bytes) < 16:
        return False, "File too small (< 16 bytes)", ""

    default_sn, default_subusr = get_default_device_and_subuser()
    file_sn = guess_serial([os.path.basename(filepath)])
    if sn is None:
        sn = file_sn or default_sn
    if subusr_id is None:
        subusr_id = default_subusr

    timestamp = parse_header_timestamp(r_bytes, filepath)
    
    # Check duplicate on primary DB
    primary_db = get_primary_db_path()
    if os.path.exists(primary_db) and not force:
        conn = sqlite3.connect(primary_db)
        cur = conn.cursor()
        cur.execute("SELECT recordid FROM tb_record WHERE checktime = ? AND subusr_id = ?", (timestamp, subusr_id))
        row = cur.fetchone()
        conn.close()
        if row:
            return False, f"Record {timestamp} already exists (ID: {row[0]})", timestamp

    # Decompress PCM
    dat_bytes = decompress_er1(r_bytes)
    total_samples = len(dat_bytes) // 2
    seconds = total_samples // 250
    duration_val = seconds * 2  # At 250Hz sample rate, duration parameter is 2 * seconds
    now_ts = datetime.now().strftime('%Y%m%d%H%M%S')

    raw_filename = f"{sn}R{timestamp}"
    dat_filename = f"{sn}{timestamp}"

    # Write to all target locations
    target_locs = get_target_locations()
    for loc in target_locs:
        db_path = os.path.join(loc, "db_lepu_care_world.db")
        userfiles_dir = os.path.join(loc, "userfiles", "subusr", str(subusr_id))
        os.makedirs(userfiles_dir, exist_ok=True)

        # 1. Save raw recording file
        shutil.copy2(filepath, os.path.join(userfiles_dir, raw_filename))

        # 2. Save decompressed dat file
        with open(os.path.join(userfiles_dir, dat_filename), "wb") as f:
            f.write(dat_bytes)

        # 3. Update SQLite database
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            # Ensure device is bound
            cur.execute("SELECT sn FROM tb_device WHERE sn = ?", (sn,))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO tb_device(sn, admin, hwversion, fwversion, blversion, devicetype, protocolversion, branchcode)
                    VALUES(?, '', 67, 16844800, 258, 13873, 1, '40040000')
                """, (sn,))
                conn.commit()

            cur.execute("SELECT recordid FROM tb_record WHERE checktime = ? AND subusr_id = ?", (timestamp, subusr_id))
            existing = cur.fetchone()
            if existing:
                cur.execute("""
                    UPDATE tb_record SET sn = ?, duration = ?, syncdatetime = ?
                    WHERE recordid = ?
                """, (sn, duration_val, now_ts, existing[0]))
            else:
                cur.execute("""
                    INSERT INTO tb_record(sn, subusr_id, admin, checktime, duration, syncdatetime, fileversion, note, aistate, fileid)
                    VALUES(?, ?, NULL, ?, ?, ?, '1', '', 0, '')
                """, (sn, subusr_id, timestamp, duration_val, now_ts))
            conn.commit()
            conn.close()

    return True, f"Successfully imported (Duration: {format_duration(seconds)})", timestamp

def import_records(file_paths, sn=None, subusr_id=None, force=False):
    """
    Batch imports multiple recording files.
    Returns: { "imported": [...], "duplicates_skipped": [...], "errors": [...] }
    """
    results = {
        "imported": [],
        "duplicates_skipped": [],
        "errors": []
    }
    
    for fp in file_paths:
        ok, msg, ts = import_single_file(fp, sn=sn, subusr_id=subusr_id, force=force)
        base = os.path.basename(fp)
        if ok:
            results["imported"].append({"file": base, "timestamp": ts, "message": msg})
        elif "already exists" in msg.lower():
            results["duplicates_skipped"].append({"file": base, "timestamp": ts, "message": msg})
        else:
            results["errors"].append({"file": base, "message": msg})
            
    return results

def import_r_file(filepath, sn=None, subusr_id=None):
    """Legacy compatibility function."""
    ok, msg, ts = import_single_file(filepath, sn=sn, subusr_id=subusr_id, force=True)
    print(f"[{'+' if ok else '!'}] {os.path.basename(filepath)}: {msg}")
    return ok

def scan_and_import(target_path):
    """Legacy compatibility function."""
    if os.path.isfile(target_path):
        return import_r_file(target_path)
    elif os.path.isdir(target_path):
        r_files = [f for f in glob.glob(os.path.join(target_path, "*")) if os.path.isfile(f) and os.path.basename(f).startswith("R")]
        if not r_files:
            print(f"[-] No 'R*' recording files found in: {target_path}")
            return False
        print(f"[*] Found {len(r_files)} recording file(s):")
        res = import_records(r_files)
        print(f"\n[+] Successfully imported {len(res['imported'])}/{len(r_files)} file(s).")
        return len(res["imported"]) > 0
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
        default_folder = r"C:\Users\user\Downloads\ER1"
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
