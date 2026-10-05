#!/usr/bin/env python3
"""
AI-ECG Analysis Portable - Device Binding Manager
Manage device bindings (ER1, ER2, etc.) in the portable SQLite database.
Supports listing, binding, unbinding, and auto-detecting devices.
"""

import os
import sys
import argparse
import sqlite3
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "Data", "DATA", "db_lepu_care_world.db")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "Data", "config.ini")

# Known Lepu / Viatom device profiles
DEVICE_PROFILES = {
    "ER1": {
        "name": "ER1 (Single-lead Holter)",
        "devicetype": 13873,
        "branchcode": "40040000",
        "hwversion": 67,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1
    },
    "ER1-LW": {
        "name": "ER1-LW",
        "devicetype": 13873,
        "branchcode": "40012101",
        "hwversion": 67,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1
    },
    "ER1-LB": {
        "name": "ER1-LB",
        "devicetype": 13873,
        "branchcode": "40012201",
        "hwversion": 67,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1
    },
    "ER2": {
        "name": "ER2 / DuoEK",
        "devicetype": 13874,
        "branchcode": "40020000",
        "hwversion": 68,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1
    }
}

def get_db_connection():
    if not os.path.exists(DB_PATH):
        print(f"[!] Database not found at: {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def get_current_admin(conn):
    cur = conn.cursor()
    cur.execute("SELECT admin FROM tb_admin LIMIT 1")
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    # Fallback to config.ini
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("LoginString="):
                    return line.strip().split("=", 1)[1]
    return "1versuses1@gmail.com"

def list_devices():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT sn, admin, devicetype, branchcode, hwversion, fwversion, blversion FROM tb_device")
    rows = cur.fetchall()
    conn.close()

    print("\n" + "="*70)
    print("  CURRENTLY BOUND DEVICES (AI-ECG Analysis System)")
    print("="*70)
    if not rows:
        print("  No devices currently bound in database.")
    else:
        for idx, r in enumerate(rows, 1):
            sn, admin, dtype, branch, hw, fw, bl = r
            dev_name = "Unknown"
            for k, v in DEVICE_PROFILES.items():
                if v["branchcode"] == branch or v["devicetype"] == dtype:
                    dev_name = v["name"]
                    break
            print(f"  [{idx}] Serial Number (SN) : {sn}")
            print(f"      Device Model       : {dev_name} (Type: {dtype}, Branch: {branch})")
            print(f"      Bound Account      : {admin if admin else '(Unassigned)'}")
            print(f"      Hardware/Firmware  : HW v{hw}, FW v{fw}, BL v{bl}")
            print("-" * 70)
    print()

def bind_device(sn, model_key="ER1", admin=None, branchcode=None, devicetype=None):
    sn = str(sn).strip()
    if not sn:
        print("[!] Serial number cannot be empty.")
        return False

    profile = DEVICE_PROFILES.get(model_key, DEVICE_PROFILES["ER1"])
    bcode = branchcode if branchcode else profile["branchcode"]
    dtype = devicetype if devicetype is not None else profile["devicetype"]
    hw = profile["hwversion"]
    fw = profile["fwversion"]
    bl = profile["blversion"]
    proto = profile["protocolversion"]

    conn = get_db_connection()
    if admin is None:
        admin = get_current_admin(conn)

    cur = conn.cursor()
    query = """
    INSERT INTO tb_device(sn, admin, hwversion, fwversion, blversion, devicetype, protocolversion, branchcode)
    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(sn) DO UPDATE SET
        admin = excluded.admin,
        hwversion = excluded.hwversion,
        fwversion = excluded.fwversion,
        blversion = excluded.blversion,
        devicetype = excluded.devicetype,
        protocolversion = excluded.protocolversion,
        branchcode = excluded.branchcode;
    """
    cur.execute(query, (sn, admin, hw, fw, bl, dtype, proto, bcode))
    conn.commit()
    conn.close()

    print(f"[+] Device {sn} ({profile['name']}) successfully bound to account '{admin}'.")
    return True

def unbind_device(sn):
    sn = str(sn).strip()
    if not sn:
        print("[!] Serial number cannot be empty.")
        return False

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT sn FROM tb_device WHERE sn = ?", (sn,))
    if not cur.fetchone():
        print(f"[!] Device {sn} is not registered in the database.")
        conn.close()
        return False

    cur.execute("DELETE FROM tb_device WHERE sn = ?", (sn,))
    conn.commit()
    conn.close()
    print(f"[+] Device {sn} has been unbound (removed from database).")
    return True

def scan_connected_devices():
    """Scan mounted drives and files to detect ER1 devices."""
    detected = []
    # Check drive letters
    import string
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            mkfs = os.path.join(drive, "MKFS")
            if os.path.exists(mkfs):
                # Found ER1 drive
                detected.append(drive)
    return detected

def interactive_menu():
    while True:
        print("\n" + "="*50)
        print("  AI-ECG PORTABLE - DEVICE MANAGER")
        print("="*50)
        print("  1. List bound devices")
        print("  2. Bind a new device (manual serial number)")
        print("  3. Scan USB & auto-bind connected device")
        print("  4. Unbind a device")
        print("  5. Re-bind default ER1 (2306490032)")
        print("  0. Exit")
        print("="*50)

        choice = input("Select an option [0-5]: ").strip()
        if choice == "1":
            list_devices()
        elif choice == "2":
            sn = input("Enter device Serial Number (e.g. 2306490032): ").strip()
            if sn:
                print("Available models:")
                keys = list(DEVICE_PROFILES.keys())
                for i, k in enumerate(keys, 1):
                    print(f"  {i}. {DEVICE_PROFILES[k]['name']}")
                m_choice = input("Select model [1]: ").strip()
                model = keys[int(m_choice) - 1] if m_choice.isdigit() and 1 <= int(m_choice) <= len(keys) else "ER1"
                bind_device(sn, model)
        elif choice == "3":
            print("[*] Scanning for connected ER1 devices...")
            drives = scan_connected_devices()
            if not drives:
                print("[-] No ER1 USB drives detected. Ensure the device is plugged in.")
            else:
                for d in drives:
                    print(f"[+] Detected ER1 on drive {d}")
                    # Look for R files to determine timestamp or prompt SN
                    bind_device("2306490032", "ER1")
        elif choice == "4":
            list_devices()
            sn = input("Enter Serial Number to unbind: ").strip()
            if sn:
                unbind_device(sn)
        elif choice == "5":
            bind_device("2306490032", "ER1")
        elif choice == "0":
            break
        else:
            print("[!] Invalid option.")

def main():
    parser = argparse.ArgumentParser(description="AI-ECG Portable Device Manager")
    parser.add_argument("--list", action="store_true", help="List all bound devices")
    parser.add_argument("--bind", metavar="SN", help="Bind a device by Serial Number")
    parser.add_argument("--unbind", metavar="SN", help="Unbind a device by Serial Number")
    parser.add_argument("--model", default="ER1", choices=list(DEVICE_PROFILES.keys()), help="Device model type")
    parser.add_argument("--admin", help="Account email to bind device to")
    parser.add_argument("--scan", action="store_true", help="Scan USB and auto-bind connected device")

    args = parser.parse_args()

    if args.list:
        list_devices()
    elif args.bind:
        bind_device(args.bind, model_key=args.model, admin=args.admin)
    elif args.unbind:
        unbind_device(args.unbind)
    elif args.scan:
        drives = scan_connected_devices()
        if drives:
            for d in drives:
                print(f"[+] Found device on {d}")
            bind_device("2306490032", "ER1")
        else:
            print("[-] No ER1 drive found.")
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
