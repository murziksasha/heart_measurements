#!/usr/bin/env python3
"""
Bind and unbind Lepu recorders in the portable database.

A serial is written only when you type it or when a filename contains it.
Scanning a USB stick never falls back to a built-in serial.
"""

import os
import sys
import argparse
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from import_local_er1 import get_target_locations, find_recording_sources
from ui_theme import (
    BG, CARD, BORDER, TEXT, MUTED, SUCCESS, ERROR, FONT, FONT_BOLD, FONT_SMALL, FONT_TITLE,
    apply_theme, button, center,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "Data", "config.ini")

DEVICE_PROFILES = {
    "ER1": {
        "name": "ER1 (Single-lead Holter)",
        "devicetype": 13873,
        "branchcode": "40040000",
        "hwversion": 67,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1,
    },
    "ER1-LW": {
        "name": "ER1-LW",
        "devicetype": 13873,
        "branchcode": "40012101",
        "hwversion": 67,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1,
    },
    "ER1-LB": {
        "name": "ER1-LB",
        "devicetype": 13873,
        "branchcode": "40012201",
        "hwversion": 67,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1,
    },
    "ER2": {
        "name": "ER2 / DuoEK",
        "devicetype": 13874,
        "branchcode": "40020000",
        "hwversion": 68,
        "fwversion": 16844800,
        "blversion": 258,
        "protocolversion": 1,
    },
}


def database_paths():
    """Every existing Lepu database this portable copy should keep in sync."""
    paths = []
    for loc in get_target_locations():
        db_path = os.path.join(loc, "db_lepu_care_world.db")
        if os.path.exists(db_path) and db_path not in paths:
            paths.append(db_path)
    return paths


def get_current_admin(conn=None):
    own_conn = conn is None
    if own_conn:
        paths = database_paths()
        if not paths:
            return _admin_from_config()
        conn = sqlite3.connect(paths[0])
    try:
        cur = conn.cursor()
        cur.execute("SELECT admin FROM tb_admin LIMIT 1")
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    finally:
        if own_conn:
            conn.close()
    return _admin_from_config()


def _admin_from_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith("LoginString="):
                    return line.strip().split("=", 1)[1]
    return ""


def model_name(devicetype, branchcode):
    for profile in DEVICE_PROFILES.values():
        if profile["branchcode"] == branchcode:
            return profile["name"]
    for profile in DEVICE_PROFILES.values():
        if profile["devicetype"] == devicetype:
            return profile["name"]
    return "Unknown"


def list_device_rows():
    paths = database_paths()
    if not paths:
        return []
    conn = sqlite3.connect(paths[0])
    cur = conn.cursor()
    cur.execute("SELECT sn, admin, devicetype, branchcode, hwversion, fwversion, blversion FROM tb_device")
    rows = cur.fetchall()
    conn.close()
    devices = []
    for sn, admin, dtype, branch, hw, fw, bl in rows:
        devices.append({
            "sn": sn,
            "admin": admin or "",
            "model": model_name(dtype, branch),
            "devicetype": dtype,
            "branchcode": branch,
            "hwversion": hw,
            "fwversion": fw,
            "blversion": bl,
        })
    return devices


def list_devices():
    rows = list_device_rows()
    print("\n" + "=" * 70)
    print("  BOUND RECORDERS")
    print("=" * 70)
    if not rows:
        print("  No recorders are bound.")
    for index, device in enumerate(rows, 1):
        print("  [%d] Serial : %s" % (index, device["sn"]))
        print("      Model  : %s (type %s, branch %s)" % (device["model"], device["devicetype"], device["branchcode"]))
        print("      Account: %s" % (device["admin"] or "(none)"))
        print("-" * 70)
    print()


def bind_device(sn, model_key="ER1", admin=None, branchcode=None, devicetype=None):
    sn = str(sn).strip()
    if not sn:
        print("[!] Serial number cannot be empty.")
        return False
    paths = database_paths()
    if not paths:
        print("[!] Database not found.")
        return False

    profile = DEVICE_PROFILES.get(model_key, DEVICE_PROFILES["ER1"])
    branch = branchcode if branchcode else profile["branchcode"]
    dtype = devicetype if devicetype is not None else profile["devicetype"]
    if admin is None:
        admin = get_current_admin()

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
        branchcode = excluded.branchcode
    """
    for db_path in paths:
        conn = sqlite3.connect(db_path)
        conn.execute(
            query,
            (sn, admin, profile["hwversion"], profile["fwversion"], profile["blversion"], dtype, profile["protocolversion"], branch),
        )
        conn.commit()
        conn.close()
    print("[+] Recorder %s (%s) bound to '%s'." % (sn, profile["name"], admin))
    return True


def unbind_device(sn):
    sn = str(sn).strip()
    if not sn:
        print("[!] Serial number cannot be empty.")
        return False
    paths = database_paths()
    if not paths:
        print("[!] Database not found.")
        return False

    found = False
    for db_path in paths:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT sn FROM tb_device WHERE sn = ?", (sn,))
        if cur.fetchone():
            found = True
            cur.execute("DELETE FROM tb_device WHERE sn = ?", (sn,))
            conn.commit()
        conn.close()
    if not found:
        print("[!] Recorder %s is not bound." % sn)
        return False
    print("[+] Recorder %s unbound." % sn)
    return True


def scan_connected_devices():
    """Drives that look like an ER1 stick. Does not bind anything."""
    return find_recording_sources()


class DeviceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Recorders")
        self.configure(bg=BG)
        apply_theme(self)
        self.minsize(640, 480)
        center(self, 720, 560)
        self.sn_var = tk.StringVar()
        self.model_var = tk.StringVar(value="ER1")
        self.status_var = tk.StringVar(value="")
        self._build()
        self._reload()

    def _build(self):
        tk.Frame(self, bg="#2ea2f8", height=4).pack(fill="x")
        header = tk.Frame(self, bg=CARD, padx=20, pady=14, highlightthickness=1, highlightbackground=BORDER)
        header.pack(fill="x")
        tk.Label(header, text="Recorders", font=FONT_TITLE, fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(
            header,
            text="Bind the serial printed on the device. A USB scan never guesses a serial.",
            font=FONT_SMALL, fg=MUTED, bg=CARD,
        ).pack(anchor="w", pady=(2, 0))

        self.list_frame = tk.Frame(self, bg=BG, padx=16, pady=12)
        self.list_frame.pack(fill="both", expand=True)

        form = tk.Frame(self, bg=CARD, padx=16, pady=12, highlightthickness=1, highlightbackground=BORDER)
        form.pack(fill="x", side="bottom")
        tk.Label(form, text="Serial", font=FONT_BOLD, fg=TEXT, bg=CARD).grid(row=0, column=0, sticky="w")
        tk.Label(form, text="Model", font=FONT_BOLD, fg=TEXT, bg=CARD).grid(row=0, column=1, sticky="w", padx=(12, 0))
        tk.Entry(
            form, textvariable=self.sn_var, font=FONT, width=24, relief="flat",
            highlightthickness=1, highlightbackground=BORDER,
        ).grid(row=1, column=0, sticky="we", pady=(4, 0), ipady=3)
        ttk.Combobox(
            form, textvariable=self.model_var, values=list(DEVICE_PROFILES.keys()),
            state="readonly", width=18, font=FONT,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(4, 0))
        actions = tk.Frame(form, bg=CARD)
        actions.grid(row=1, column=2, sticky="e", padx=(12, 0))
        button(actions, "Bind", self._bind, kind="primary").pack(side="left")
        button(actions, "Scan USB", self._scan).pack(side="left", padx=(8, 0))
        form.grid_columnconfigure(0, weight=1)
        self.status = tk.Label(form, textvariable=self.status_var, font=FONT_SMALL, fg=MUTED, bg=CARD, anchor="w")
        self.status.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _reload(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        if not database_paths():
            tk.Label(self.list_frame, text="Database not found.", font=FONT, fg=ERROR, bg=BG).pack(anchor="w")
            return
        devices = list_device_rows()
        if not devices:
            tk.Label(self.list_frame, text="No recorders bound yet.", font=FONT, fg=MUTED, bg=BG).pack(anchor="w", pady=12)
            return
        for device in devices:
            self._card(device)

    def _card(self, device):
        card = tk.Frame(self.list_frame, bg=CARD, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text=device["model"], font=FONT_BOLD, fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(card, text="Serial %s" % device["sn"], font=FONT, fg=TEXT, bg=CARD).pack(anchor="w", pady=(2, 0))
        account = device["admin"] or "No account"
        tk.Label(card, text=account, font=FONT_SMALL, fg=MUTED, bg=CARD).pack(anchor="w")
        button(card, "Unbind", lambda sn=device["sn"]: self._unbind(sn), kind="danger").pack(anchor="e")

    def _bind(self):
        sn = self.sn_var.get().strip()
        if not sn:
            self._set_status("Enter the serial from the recorder.", ERROR)
            return
        try:
            ok = bind_device(sn, self.model_var.get() or "ER1")
        except Exception as exc:
            self._set_status(str(exc), ERROR)
            return
        if ok:
            self.sn_var.set("")
            self._set_status("Bound %s." % sn, SUCCESS)
            self._reload()

    def _unbind(self, sn):
        if not messagebox.askyesno("Unbind recorder", "Unbind serial %s?" % sn, parent=self):
            return
        try:
            unbind_device(sn)
        except Exception as exc:
            self._set_status(str(exc), ERROR)
            return
        self._set_status("Unbound %s." % sn, SUCCESS)
        self._reload()

    def _scan(self):
        sources = find_recording_sources()
        if not sources:
            self._set_status("No ER1 drive detected. Plug it in, or type the serial.", ERROR)
            return
        notes = []
        bound = 0
        for source in sources:
            if source["serial"]:
                bind_device(source["serial"], self.model_var.get() or "ER1")
                bound += 1
                notes.append("Bound %s from %s." % (source["serial"], source["path"]))
            else:
                notes.append(
                    "%s has %d recording file(s) and no serial in the names. Type the serial printed on the device."
                    % (source["path"], source["count"])
                )
        self._set_status(" ".join(notes), SUCCESS if bound else ERROR)
        self._reload()

    def _set_status(self, text, color):
        self.status_var.set(text)
        self.status.config(fg=color)


def interactive_menu():
    while True:
        print("\n" + "=" * 50)
        print("  RECORDERS")
        print("=" * 50)
        print("  1. List bound recorders")
        print("  2. Bind a serial")
        print("  3. Scan USB")
        print("  4. Unbind a serial")
        print("  0. Exit")
        choice = input("Select an option [0-4]: ").strip()
        if choice == "1":
            list_devices()
        elif choice == "2":
            sn = input("Serial number: ").strip()
            if not sn:
                continue
            keys = list(DEVICE_PROFILES.keys())
            for index, key in enumerate(keys, 1):
                print("  %d. %s" % (index, DEVICE_PROFILES[key]["name"]))
            picked = input("Model [1]: ").strip()
            model = keys[int(picked) - 1] if picked.isdigit() and 1 <= int(picked) <= len(keys) else "ER1"
            bind_device(sn, model)
        elif choice == "3":
            sources = scan_connected_devices()
            if not sources:
                print("[-] No ER1 drive detected.")
                continue
            for source in sources:
                if source["serial"]:
                    print("[+] %s serial %s" % (source["path"], source["serial"]))
                    bind_device(source["serial"], "ER1")
                else:
                    print("[-] %s has recordings but no serial in the file names. Use option 2." % source["path"])
        elif choice == "4":
            list_devices()
            sn = input("Serial to unbind: ").strip()
            if sn:
                unbind_device(sn)
        elif choice == "0":
            break
        else:
            print("[!] Invalid option.")


def main():
    parser = argparse.ArgumentParser(description="AI-ECG Portable recorder binding")
    parser.add_argument("--list", action="store_true", help="List bound recorders")
    parser.add_argument("--bind", metavar="SN", help="Bind a recorder by serial")
    parser.add_argument("--unbind", metavar="SN", help="Unbind a recorder by serial")
    parser.add_argument("--model", default="ER1", choices=list(DEVICE_PROFILES.keys()), help="Recorder model")
    parser.add_argument("--admin", help="Account email to bind to")
    parser.add_argument("--scan", action="store_true", help="Scan USB and bind only a serial found in file names")
    parser.add_argument("--menu", action="store_true", help="Open the text menu")
    parser.add_argument("--gui", action="store_true", help="Open the recorder window")
    args = parser.parse_args()

    if args.list:
        list_devices()
    elif args.bind:
        if not bind_device(args.bind, model_key=args.model, admin=args.admin):
            sys.exit(1)
    elif args.unbind:
        if not unbind_device(args.unbind):
            sys.exit(1)
    elif args.scan:
        sources = scan_connected_devices()
        if not sources:
            print("[-] No ER1 drive found.")
            sys.exit(1)
        bound = False
        for source in sources:
            print("[+] %s (%d files)" % (source["path"], source["count"]))
            if source["serial"]:
                bind_device(source["serial"], args.model, admin=args.admin)
                bound = True
            else:
                print("[-] No serial in file names on %s. Pass --bind SERIAL." % source["path"])
        if not bound:
            sys.exit(1)
    elif args.menu:
        interactive_menu()
    else:
        app = DeviceApp()
        app.mainloop()


if __name__ == "__main__":
    main()
