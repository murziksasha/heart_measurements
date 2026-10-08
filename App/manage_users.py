#!/usr/bin/env python3
"""
AI-ECG Analysis Portable - Patient / Subuser Management
Supports creating, listing, and managing patient profiles in the SQLite database.
Includes a Tkinter modal dialog matching the original application design system.
"""

import os
import sys
import argparse
import sqlite3
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from ui_theme import apply_theme, button, center

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Design system colors matching ECG Data Management
PRIMARY_COLOR = "#2ea2f8"
PRIMARY_HOVER = "#1a8de4"
TEXT_COLOR = "#2c3e50"
BG_COLOR = "#f8fafd"
CARD_BG = "#ffffff"
BORDER_COLOR = "#dce4ec"
SUCCESS_COLOR = "#27ae60"
MUTED_COLOR = "#7f8c8d"
ERROR_COLOR = "#e74c3c"


def get_target_locations():
    """
    Returns all existing DATA directory locations (portable and/or AppData).
    Ensures that operations are written to both if both exist.
    """
    locations = []
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        appdata_data = os.path.join(local_app_data, "ECG Browser", "DATA")
        if os.path.exists(appdata_data):
            locations.append(appdata_data)

    candidate_portable_dirs = [
        os.path.join(SCRIPT_DIR, "Data", "DATA"),
        os.path.join(os.path.dirname(SCRIPT_DIR), "Data", "DATA"),
    ]
    for pdir in candidate_portable_dirs:
        if os.path.exists(pdir) and pdir not in locations:
            locations.append(pdir)
            break

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


def get_current_admin():
    """Returns active admin account email."""
    db_path = get_primary_db_path()
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT admin FROM tb_admin LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            pass

    config_path = os.path.join(SCRIPT_DIR, "Data", "config.ini")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("LoginString="):
                        return line.strip().split("=", 1)[1]
        except Exception:
            pass

    return "1versuses1@gmail.com"


def calculate_age(birthday_str):
    """Calculates age in years from YYYY-MM-DD string."""
    if not birthday_str:
        return 0
    try:
        b_date = datetime.strptime(birthday_str[:10], "%Y-%m-%d")
        today = datetime.now()
        age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
        return max(0, age)
    except Exception:
        try:
            b_year = int(birthday_str.split("-")[0])
            return max(0, datetime.now().year - b_year)
        except Exception:
            return 0


def get_all_subusers():
    """Retrieves all registered patients from the database with age and recording count."""
    db_path = get_primary_db_path()
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.subusr_id, s.familyid, s.userkey, s.admin, s.name, s.gender, s.birthday, s.height, s.weight,
               COUNT(r.recordid) as record_count
        FROM tb_subuser s
        LEFT JOIN tb_record r ON s.subusr_id = r.subusr_id
        GROUP BY s.subusr_id
        ORDER BY s.subusr_id ASC
    """)
    rows = cur.fetchall()
    conn.close()

    admin_email = get_current_admin()
    users = []
    for r in rows:
        subusr_id, familyid, userkey, admin_val, name, gender_code, birthday, height, weight, rec_count = r
        gender_str = "Male" if gender_code == 2 else "Female" if gender_code == 1 else "Unknown"
        b_str = str(birthday) if birthday else ""
        users.append({
            "id": subusr_id,
            "familyid": familyid,
            "userkey": userkey or admin_email,
            "name": name or f"User {subusr_id}",
            "gender": gender_str,
            "gender_code": gender_code,
            "birthday": b_str,
            "age": calculate_age(b_str),
            "height": height or 0,
            "weight": weight or 0,
            "records": rec_count
        })
    return users


def _validate_body(height, weight):
    """Height and weight are optional. 0 means not recorded."""
    try:
        height = int(height or 0)
        weight = int(weight or 0)
    except (TypeError, ValueError):
        raise ValueError("Height and weight must be whole numbers.")
    if height < 0 or height > 250:
        raise ValueError("Height must be between 0 and 250 cm.")
    if weight < 0 or weight > 400:
        raise ValueError("Weight must be between 0 and 400 kg.")
    return height, weight


def _validate_name(name):
    name = str(name).strip()
    if not name:
        raise ValueError("Patient name cannot be empty.")
    if len(name) > 20:
        raise ValueError("Patient name must not exceed 20 characters.")
    return name


def add_subuser(name, gender="Male", birthday="1990-01-01", email=None, height=0, weight=0, note=""):
    """
    Creates a new patient profile across all database copies.
    Generates a unique familyid, creates patient folder, and updates tb_subusr_selected_time.
    Returns the created user dict.
    note is accepted for older callers and is not stored: tb_subuser has no note column.
    """
    name = _validate_name(name)
    height, weight = _validate_body(height, weight)

    gender_code = 2 if str(gender).strip().lower() in ["male", "m", "2"] else 1
    if not email:
        email = get_current_admin()
    email = str(email).strip()

    locations = get_target_locations()
    new_subusr_id = None
    created_user = None

    for loc in locations:
        db_path = os.path.join(loc, "db_lepu_care_world.db")
        if not os.path.exists(db_path):
            continue

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Generate unique familyid
        cur.execute("SELECT MAX(familyid) FROM tb_subuser")
        max_fam = cur.fetchone()[0]
        familyid = (max_fam + 1) if max_fam and max_fam >= 800000 else 843795

        # Check existing max subusr_id if needed
        cur.execute("SELECT MAX(subusr_id) FROM tb_subuser")
        max_id = cur.fetchone()[0]
        target_id = (max_id + 1) if max_id else 1
        if new_subusr_id is not None:
            target_id = new_subusr_id

        # Insert new user
        cur.execute("""
            INSERT INTO tb_subuser(subusr_id, familyid, userkey, admin, name, gender, birthday, height, weight)
            VALUES(?, ?, ?, '', ?, ?, ?, ?, ?)
        """, (target_id, familyid, email, name, gender_code, birthday, int(height), int(weight)))

        new_subusr_id = cur.lastrowid or target_id

        # Insert selected time
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")
        cur.execute("""
            INSERT INTO tb_subusr_selected_time(subusr_id, selected_time)
            VALUES(?, ?)
            ON CONFLICT(subusr_id) DO UPDATE SET selected_time = excluded.selected_time
        """, (new_subusr_id, now_str))

        conn.commit()
        conn.close()

        # Create user storage directory
        user_folder = os.path.join(loc, "userfiles", "subusr", str(new_subusr_id))
        os.makedirs(user_folder, exist_ok=True)

    created_user = {
        "id": new_subusr_id,
        "name": name,
        "gender": "Male" if gender_code == 2 else "Female",
        "birthday": birthday,
        "age": calculate_age(birthday),
        "email": email,
        "height": height,
        "weight": weight,
    }
    return created_user


def update_subuser(subusr_id, name, gender="Male", birthday="1990-01-01", email=None, height=0, weight=0):
    """Updates an existing patient on every database copy. Does not change the id."""
    name = _validate_name(name)
    height, weight = _validate_body(height, weight)
    gender_code = 2 if str(gender).strip().lower() in ["male", "m", "2"] else 1
    if not email:
        email = get_current_admin()
    email = str(email).strip()
    subusr_id = int(subusr_id)

    updated = False
    for loc in get_target_locations():
        db_path = os.path.join(loc, "db_lepu_care_world.db")
        if not os.path.exists(db_path):
            continue
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT subusr_id FROM tb_subuser WHERE subusr_id = ?", (subusr_id,))
        if not cur.fetchone():
            conn.close()
            continue
        cur.execute(
            """
            UPDATE tb_subuser
            SET userkey = ?, name = ?, gender = ?, birthday = ?, height = ?, weight = ?
            WHERE subusr_id = ?
            """,
            (email, name, gender_code, birthday, height, weight, subusr_id),
        )
        conn.commit()
        conn.close()
        updated = True

    if not updated:
        raise ValueError("Patient %s was not found." % subusr_id)

    return {
        "id": subusr_id,
        "name": name,
        "gender": "Male" if gender_code == 2 else "Female",
        "birthday": birthday,
        "age": calculate_age(birthday),
        "email": email,
        "height": height,
        "weight": weight,
    }


def delete_subuser(subusr_id):
    """Deletes a subuser from the database by ID."""
    subusr_id = int(subusr_id)
    if subusr_id == 1:
        raise ValueError("Cannot delete the default primary patient profile (ID 1).")

    locations = get_target_locations()
    for loc in locations:
        db_path = os.path.join(loc, "db_lepu_care_world.db")
        if not os.path.exists(db_path):
            continue

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM tb_record WHERE subusr_id = ?", (subusr_id,))
        cur.execute("DELETE FROM tb_subusr_selected_time WHERE subusr_id = ?", (subusr_id,))
        cur.execute("DELETE FROM tb_subuser WHERE subusr_id = ?", (subusr_id,))
        conn.commit()
        conn.close()

        user_folder = os.path.join(loc, "userfiles", "subusr", str(subusr_id))
        if os.path.exists(user_folder):
            try:
                shutil.rmtree(user_folder)
            except Exception:
                pass


# =========================================================================
# Tkinter GUI Modals & Dialogs
# =========================================================================

class AddUserBase:
    """
    Base form logic and UI components for creating a new patient / subuser.
    Matches the ECG Data Management aesthetic (#2ea2f8, cards, Segoe UI).
    """
    def _setup_dialog(self, on_success=None, existing=None):
        self.on_success = on_success
        self.existing = existing
        self.result = None
        self.editing = existing is not None

        self.title("Edit patient" if self.editing else "Add patient")
        self.configure(bg=BG_COLOR)
        apply_theme(self)

        width, height = 460, 520
        self.geometry("%dx%d" % (width, height))
        self.minsize(420, 480)
        self.resizable(True, True)
        center(self, width, height)

        self._init_variables()
        self._build_ui()

        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.after(60, lambda: self.name_entry.focus())

    def _init_variables(self):
        current = self.existing or {}
        self.name_var = tk.StringVar(value=current.get("name") or "")
        self.gender_var = tk.StringVar(value=current.get("gender") if current.get("gender") in ("Male", "Female") else "Male")
        self.email_var = tk.StringVar(value=current.get("email") or get_current_admin())
        self.height_var = tk.StringVar(value=str(current.get("height") or 0))
        self.weight_var = tk.StringVar(value=str(current.get("weight") or 0))
        self.count_var = tk.StringVar(value="0/20")
        self.age_var = tk.StringVar(value="Age: —")
        self.error_var = tk.StringVar()

        birthday = str(current.get("birthday") or "")[:10]
        parts = birthday.split("-") if birthday else []
        if len(parts) == 3 and len(parts[0]) == 4:
            self.year_var = tk.StringVar(value=parts[0])
            self.month_var = tk.StringVar(value=parts[1])
            self.day_var = tk.StringVar(value=parts[2])
        else:
            self.year_var = tk.StringVar(value="")
            self.month_var = tk.StringVar(value="01")
            self.day_var = tk.StringVar(value="01")

        users = get_all_subusers()
        if self.editing:
            self.next_id_str = "Patient #%s" % current.get("id")
        else:
            next_id = (max(u["id"] for u in users) + 1) if users else 1
            self.next_id_str = "Patient #%s" % next_id

    def _build_ui(self):
        # 1. Header banner (Top)
        header_frame = tk.Frame(self, bg=CARD_BG, padx=24, pady=14, highlightthickness=1, highlightbackground=BORDER_COLOR)
        header_frame.pack(fill="x", side="top")

        heading = "Edit patient" if self.editing else "Add patient"
        title_lbl = tk.Label(header_frame, text=heading, font=("Segoe UI", 15, "bold"), fg=TEXT_COLOR, bg=CARD_BG)
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(header_frame, text=self.next_id_str, font=("Segoe UI", 9), fg=MUTED_COLOR, bg=CARD_BG)
        sub_lbl.pack(anchor="w", pady=(2, 0))

        btn_frame = tk.Frame(self, bg=CARD_BG, padx=24, pady=12, highlightthickness=1, highlightbackground=BORDER_COLOR)
        btn_frame.pack(fill="x", side="bottom")

        btn_cancel = button(btn_frame, "Cancel", self._on_cancel)
        btn_cancel.pack(side="right", padx=(10, 0))

        save_text = "Save changes" if self.editing else "Save patient"
        self.btn_submit = button(btn_frame, save_text, self._submit, kind="primary")
        self.btn_submit.pack(side="right")

        # 3. Main form container (Fills remaining middle area)
        form_frame = tk.Frame(self, bg=BG_COLOR, padx=24, pady=12)
        form_frame.pack(fill="both", expand=True)

        name_hdr = tk.Frame(form_frame, bg=BG_COLOR)
        name_hdr.pack(fill="x", pady=(0, 3))
        tk.Label(name_hdr, text="Name *", font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(side="left")
        tk.Label(name_hdr, textvariable=self.count_var, font=("Segoe UI", 9), fg=MUTED_COLOR, bg=BG_COLOR).pack(side="right")

        self.name_entry = tk.Entry(form_frame, textvariable=self.name_var, font=("Segoe UI", 10),
                                   bg=CARD_BG, fg=TEXT_COLOR, relief="solid", bd=1, highlightthickness=0)
        self.name_entry.pack(fill="x", ipady=4, pady=(0, 8))
        self.name_var.trace_add("write", self._on_name_change)
        self._on_name_change()

        # Gender
        lbl_gender = tk.Label(form_frame, text="Gender", font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR, bg=BG_COLOR)
        lbl_gender.pack(anchor="w", pady=(0, 3))

        gender_frame = tk.Frame(form_frame, bg=BG_COLOR)
        gender_frame.pack(fill="x", pady=(0, 8))

        rb_m = tk.Radiobutton(gender_frame, text="Male", variable=self.gender_var, value="Male",
                              font=("Segoe UI", 10), bg=BG_COLOR, fg=TEXT_COLOR, activebackground=BG_COLOR,
                              selectcolor=CARD_BG, cursor="hand2")
        rb_m.pack(side="left", padx=(0, 20))

        rb_f = tk.Radiobutton(gender_frame, text="Female", variable=self.gender_var, value="Female",
                              font=("Segoe UI", 10), bg=BG_COLOR, fg=TEXT_COLOR, activebackground=BG_COLOR,
                              selectcolor=CARD_BG, cursor="hand2")
        rb_f.pack(side="left")

        # Birthday & Live Age badge
        birth_hdr = tk.Frame(form_frame, bg=BG_COLOR)
        birth_hdr.pack(fill="x", pady=(0, 3))

        lbl_birth = tk.Label(birth_hdr, text="Birthday", font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR, bg=BG_COLOR)
        lbl_birth.pack(side="left")

        self.lbl_age_badge = tk.Label(birth_hdr, textvariable=self.age_var, font=("Segoe UI", 9, "bold"),
                                      fg=PRIMARY_COLOR, bg="#e8f4fd", padx=8, pady=1)
        self.lbl_age_badge.pack(side="right")

        date_frame = tk.Frame(form_frame, bg=BG_COLOR)
        date_frame.pack(fill="x", pady=(0, 8))

        years = [""] + [str(y) for y in range(datetime.now().year, 1920, -1)]
        cb_year = ttk.Combobox(date_frame, textvariable=self.year_var, values=years, width=8, state="readonly")
        cb_year.pack(side="left", padx=(0, 6))

        months = [f"{m:02d}" for m in range(1, 13)]
        cb_month = ttk.Combobox(date_frame, textvariable=self.month_var, values=months, width=5, state="readonly")
        cb_month.pack(side="left", padx=(0, 6))

        days = [f"{d:02d}" for d in range(1, 32)]
        cb_day = ttk.Combobox(date_frame, textvariable=self.day_var, values=days, width=5, state="readonly")
        cb_day.pack(side="left")

        self.year_var.trace_add("write", self._update_age)
        self.month_var.trace_add("write", self._update_age)
        self.day_var.trace_add("write", self._update_age)
        self._update_age()

        measure = tk.Frame(form_frame, bg=BG_COLOR)
        measure.pack(fill="x", pady=(0, 8))

        tk.Label(measure, text="Height (cm)", font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).grid(row=0, column=0, sticky="w")
        tk.Label(measure, text="Weight (kg)", font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).grid(row=0, column=1, sticky="w", padx=(16, 0))
        tk.Spinbox(
            measure, from_=0, to=250, textvariable=self.height_var, width=8,
            font=("Segoe UI", 10), justify="left", buttoncursor="hand2",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        tk.Spinbox(
            measure, from_=0, to=400, textvariable=self.weight_var, width=8,
            font=("Segoe UI", 10), justify="left", buttoncursor="hand2",
        ).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(3, 0))
        tk.Label(
            form_frame,
            text="Leave height and weight at 0 if you do not know them. 0 is stored as not recorded.",
            font=("Segoe UI", 8),
            fg=MUTED_COLOR,
            bg=BG_COLOR,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(form_frame, text="Account", font=("Segoe UI", 10, "bold"), fg=TEXT_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(0, 3))
        tk.Label(form_frame, textvariable=self.email_var, font=("Segoe UI", 10), fg=MUTED_COLOR, bg=BG_COLOR).pack(anchor="w", pady=(0, 8))


        self.lbl_error = tk.Label(form_frame, textvariable=self.error_var, font=("Segoe UI", 9),
                                  fg=ERROR_COLOR, bg=BG_COLOR)
        self.lbl_error.pack(anchor="w", pady=(0, 2))

    def _on_cancel(self):
        self.destroy()

    def _on_name_change(self, *args):
        val = self.name_var.get()
        if len(val) > 20:
            self.name_var.set(val[:20])
            return
        self.count_var.set("%d/20" % len(val))
        self.error_var.set("")

    def _update_age(self, *args):
        year = self.year_var.get().strip()
        if not year:
            self.age_var.set("Age: —")
            return
        birthday = "%s-%s-%s" % (year, self.month_var.get(), self.day_var.get())
        try:
            datetime.strptime(birthday, "%Y-%m-%d")
            self.age_var.set("Age: %d" % calculate_age(birthday))
        except Exception:
            self.age_var.set("Age: —")

    def _birthday(self):
        year = self.year_var.get().strip()
        if not year:
            return None
        birthday = "%s-%s-%s" % (year, self.month_var.get(), self.day_var.get())
        try:
            datetime.strptime(birthday, "%Y-%m-%d")
        except ValueError:
            return None
        return birthday

    def _submit(self):
        name = self.name_var.get().strip()
        if not name:
            self.error_var.set("Enter a patient name.")
            self.name_entry.focus()
            return

        birthday = self._birthday()
        if not birthday:
            self.error_var.set("Enter a real birth date. The year is required.")
            return

        self_id = self.existing["id"] if self.existing else None
        for user in get_all_subusers():
            if user["id"] == self_id:
                continue
            if user["name"].lower() == name.lower():
                if not messagebox.askyesno(
                    "Duplicate name",
                    "A patient named '%s' already exists.\nSave this one anyway?" % name,
                    parent=self,
                ):
                    return
                break

        gender = self.gender_var.get()
        email = self.email_var.get().strip() or get_current_admin()
        try:
            height = int(self.height_var.get() or 0)
            weight = int(self.weight_var.get() or 0)
        except ValueError:
            self.error_var.set("Height and weight must be whole numbers.")
            return

        try:
            if self.editing:
                created = update_subuser(
                    self.existing["id"], name=name, gender=gender, birthday=birthday,
                    email=email, height=height, weight=weight,
                )
            else:
                created = add_subuser(
                    name=name, gender=gender, birthday=birthday, email=email,
                    height=height, weight=weight,
                )
            self.result = created
            if self.on_success:
                self.on_success(created)
            self.destroy()
        except Exception as e:
            self.error_var.set("Error: %s" % e)


class AddUserDialog(tk.Toplevel, AddUserBase):
    """
    Modal dialog for creating a new patient / subuser within an existing Tk root.
    """
    def __init__(self, parent=None, on_success=None, existing=None):
        super().__init__(parent)
        if parent:
            self.transient(parent)
        self.grab_set()
        self._setup_dialog(on_success, existing=existing)


class StandaloneAddUserApp(tk.Tk, AddUserBase):
    """
    Standalone root window for Add User dialog (used by --add-gui from C# wrapper).
    Owns its own taskbar presence and process lifecycle.
    """
    def __init__(self):
        super().__init__()
        self.result_status = {"added": False, "refresh": True}
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_dialog(on_success=self._on_user_created)

    def _on_user_created(self, created):
        self.result_status["added"] = True
        ans = messagebox.askyesno(
            "Patient Added",
            f"Patient '{created['name']}' was successfully created!\n\nWould you like to refresh the application now to display the new patient in the sidebar?",
            icon="question",
            parent=self
        )
        self.result_status["refresh"] = ans
        self.destroy()

    def _on_close(self):
        self.destroy()


def _measure(value, unit):
    if not value:
        return "—"
    return "%s %s" % (value, unit)


class ManageUsersApp(tk.Tk):
    """Standalone patient list."""
    def __init__(self):
        super().__init__()
        self.title("Patients")
        self.configure(bg=BG_COLOR)
        apply_theme(self)
        width, height = 820, 480
        self.minsize(700, 380)
        center(self, width, height)
        self._users = []
        self._build_ui()
        self._load_users()

    def _build_ui(self):
        header = tk.Frame(self, bg=CARD_BG, padx=20, pady=14, highlightthickness=1, highlightbackground=BORDER_COLOR)
        header.pack(fill="x", side="top")
        tk.Label(header, text="Patients", font=("Segoe UI", 15, "bold"), fg=TEXT_COLOR, bg=CARD_BG).pack(side="left")
        button(header, "Add patient", self._open_add_dialog, kind="primary").pack(side="right")

        table_frame = tk.Frame(self, bg=BG_COLOR, padx=20, pady=14)
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "gender", "age", "birthday", "height", "weight", "records")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = (
            ("name", "Patient", 160, "w"),
            ("gender", "Gender", 80, "center"),
            ("age", "Age", 50, "center"),
            ("birthday", "Birthday", 110, "center"),
            ("height", "Height", 80, "center"),
            ("weight", "Weight", 80, "center"),
            ("records", "Recordings", 90, "center"),
        )
        for key, label, width, anchor in headings:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=anchor)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _event: self._open_edit_dialog())

        footer = tk.Frame(self, bg=CARD_BG, padx=20, pady=12, highlightthickness=1, highlightbackground=BORDER_COLOR)
        footer.pack(fill="x", side="bottom")
        self.lbl_status = tk.Label(footer, text="", font=("Segoe UI", 9), fg=MUTED_COLOR, bg=CARD_BG)
        self.lbl_status.pack(side="left")
        button(footer, "Close", self.destroy).pack(side="right")
        button(footer, "Delete", self._delete_selected, kind="danger").pack(side="right", padx=(0, 8))
        button(footer, "Edit", self._open_edit_dialog).pack(side="right", padx=(0, 8))

    def _load_users(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._users = get_all_subusers()
        for user in self._users:
            self.tree.insert("", "end", iid=str(user["id"]), values=(
                user["name"],
                user["gender"],
                user["age"],
                (user["birthday"] or "")[:10],
                _measure(user["height"], "cm"),
                _measure(user["weight"], "kg"),
                user["records"],
            ))
        self.lbl_status.config(text="%d patients" % len(self._users))

    def _selected_user(self):
        selected = self.tree.selection()
        if not selected:
            return None
        uid = int(selected[0])
        for user in self._users:
            if user["id"] == uid:
                return user
        return None

    def _open_add_dialog(self):
        AddUserDialog(self, on_success=lambda _user: self._load_users())

    def _open_edit_dialog(self):
        user = self._selected_user()
        if not user:
            messagebox.showinfo("Select a patient", "Select a patient to edit.", parent=self)
            return
        AddUserDialog(self, existing=user, on_success=lambda _user: self._load_users())

    def _delete_selected(self):
        user = self._selected_user()
        if not user:
            messagebox.showinfo("Select a patient", "Select a patient to delete.", parent=self)
            return
        if user["id"] == 1:
            messagebox.showwarning("Protected patient", "The original patient (ID 1) cannot be deleted.", parent=self)
            return
        if user["records"] > 0:
            if not _confirm_typed_name(self, user["name"], user["records"]):
                return
        elif not messagebox.askyesno("Delete patient", "Delete patient '%s'?" % user["name"], parent=self):
            return
        try:
            delete_subuser(user["id"])
            self._load_users()
        except Exception as exc:
            messagebox.showerror("Error", "Failed to delete patient: %s" % exc, parent=self)


def _confirm_typed_name(parent, name, recordings):
    """Ask the operator to type the patient name before deleting recordings."""
    dialog = tk.Toplevel(parent)
    dialog.title("Delete patient")
    dialog.configure(bg=BG_COLOR)
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()
    center(dialog, 420, 220)
    confirmed = {"ok": False}
    typed = tk.StringVar()
    error = tk.StringVar()

    body = tk.Frame(dialog, bg=BG_COLOR, padx=20, pady=16)
    body.pack(fill="both", expand=True)
    tk.Label(
        body,
        text="Delete %s and %d recording(s)? This cannot be undone.\nType the patient name to confirm." % (name, recordings),
        font=("Segoe UI", 10),
        fg=TEXT_COLOR,
        bg=BG_COLOR,
        justify="left",
    ).pack(anchor="w")
    tk.Entry(body, textvariable=typed, font=("Segoe UI", 10), relief="solid", bd=1).pack(fill="x", ipady=3, pady=(10, 4))
    tk.Label(body, textvariable=error, font=("Segoe UI", 9), fg=ERROR_COLOR, bg=BG_COLOR).pack(anchor="w")

    actions = tk.Frame(dialog, bg=CARD_BG, padx=16, pady=10)
    actions.pack(fill="x", side="bottom")

    def accept():
        if typed.get().strip() != name:
            error.set("Type the name exactly.")
            return
        confirmed["ok"] = True
        dialog.destroy()

    button(actions, "Cancel", dialog.destroy).pack(side="right", padx=(8, 0))
    button(actions, "Delete", accept, kind="danger").pack(side="right")
    dialog.bind("<Return>", lambda _event: accept())
    dialog.wait_window()
    return confirmed["ok"]


def run_add_gui_modal():
    """Runs the standalone Add User modal dialog and exits with code 2 (refresh) or 3 (no-refresh) on success."""
    try:
        app = StandaloneAddUserApp()
        app.mainloop()

        if app.result_status["added"]:
            sys.exit(2 if app.result_status["refresh"] else 3)
        else:
            sys.exit(0)
    except Exception as e:
        import traceback
        log_dir = os.path.join(SCRIPT_DIR, "Data", "log")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "add_user_error.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {traceback.format_exc()}\n")
        sys.exit(1)


def print_cli_table(users):
    print("\n" + "="*80)
    print("  AI-ECG ANALYSIS SYSTEM - REGISTERED PATIENTS")
    print("="*80)
    print(f"  {'ID':<6} {'Name':<20} {'Gender':<8} {'Age':<6} {'Birthday':<12} {'Recordings':<10}")
    print("-" * 80)
    for u in users:
        print(f"  #{u['id']:<5} {u['name']:<20} {u['gender']:<8} {u['age']:<6} {u['birthday']:<12} {u['records']:<10}")
    print("="*80)
    print(f"  Total Registered Patients: {len(users)}\n")


def main():
    parser = argparse.ArgumentParser(description="AI-ECG Portable Patient / User Manager")
    parser.add_argument("--add-gui", action="store_true", help="Launch interactive Add User GUI modal")
    parser.add_argument("--gui", action="store_true", help="Launch User Management Manager window")
    parser.add_argument("--list", action="store_true", help="List all registered patients")
    parser.add_argument("--add", metavar="NAME", help="Add patient by name (CLI)")
    parser.add_argument("--gender", default="Male", choices=["Male", "Female"], help="Gender for --add")
    parser.add_argument("--birthday", default="1990-01-01", help="Birthday (YYYY-MM-DD) for --add")
    parser.add_argument("--email", help="Account email for --add")
    parser.add_argument("--note", default="", help="Note / remark for --add")
    parser.add_argument("--delete", type=int, metavar="ID", help="Delete patient by ID")

    args = parser.parse_args()

    if args.add_gui:
        run_add_gui_modal()
    elif args.gui:
        app = ManageUsersApp()
        app.mainloop()
    elif args.list:
        users = get_all_subusers()
        print_cli_table(users)
    elif args.add:
        try:
            created = add_subuser(
                name=args.add,
                gender=args.gender,
                birthday=args.birthday,
                email=args.email,
                note=args.note
            )
            print(f"[+] Patient created successfully: #{created['id']} {created['name']} ({created['gender']}, Age: {created['age']})")
        except Exception as e:
            print(f"[!] Error: {e}")
            sys.exit(1)
    elif args.delete:
        try:
            delete_subuser(args.delete)
            print(f"[+] Patient ID {args.delete} deleted successfully.")
        except Exception as e:
            print(f"[!] Error: {e}")
            sys.exit(1)
    else:
        # Default behavior when launched without flags: Open GUI manager
        app = ManageUsersApp()
        app.mainloop()


if __name__ == "__main__":
    main()
