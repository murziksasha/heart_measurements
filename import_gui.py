#!/usr/bin/env python3
"""
AI-ECG Analysis Portable - Import Modal GUI
Presents a dual-variant choice view (From Device vs From Folder)
and an interactive Folder Import table for selecting, verifying, and importing ER1 files.
Single top-level window architecture ensuring immediate foreground visibility.
"""

import os
import sys
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from import_local_er1 import (
    scan_folder_records,
    import_records,
    get_subusers,
    format_duration
)

APP_TITLE = "ECG Data Management - Import Data"
PRIMARY_COLOR = "#2ea2f8"
PRIMARY_HOVER = "#1a8de4"
TEXT_COLOR = "#2c3e50"
BG_COLOR = "#f8fafd"
CARD_BG = "#ffffff"
BORDER_COLOR = "#dce4ec"
SUCCESS_COLOR = "#27ae60"
MUTED_COLOR = "#7f8c8d"


def find_er1_usb_drive():
    """Scans for ER1 USB drive (removable drive containing R* recordings)."""
    try:
        kernel32 = ctypes.windll.kernel32
        bitmask = kernel32.GetLogicalDrives()
        removable_drives = []
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            if bitmask & (1 << (ord(letter) - ord("A"))):
                drive = f"{letter}:\\"
                dtype = kernel32.GetDriveTypeW(drive)
                if dtype == 2:  # DRIVE_REMOVABLE
                    try:
                        r_files = [
                            f for f in os.listdir(drive)
                            if f.startswith("R") and os.path.isfile(os.path.join(drive, f))
                        ]
                        if r_files:
                            return drive
                    except Exception:
                        pass
                    removable_drives.append(drive)
        return removable_drives[0] if removable_drives else None
    except Exception:
        return None


def refresh_main_window():
    """Signals ECG Data Management main window to refresh its records table."""
    try:
        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        target_hwnd = None

        def enum_cb(hwnd, lparam):
            nonlocal target_hwnd
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            if "Qt" in cls_buf.value:
                owner = user32.GetWindow(hwnd, 4)  # GW_OWNER
                if owner == 0:
                    r = RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(r))
                    if (r.right - r.left) >= 600:
                        target_hwnd = hwnd
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        if not target_hwnd:
            target_hwnd = user32.FindWindowW("Qt5152QWindowIcon", "ECG Data Management")

        if target_hwnd:
            # Click on Grygoriev patient item in left sidebar (x=90, y=165)
            lparam = (165 << 16) | 90
            user32.PostMessageW(target_hwnd, 0x0201, 1, lparam)  # WM_LBUTTONDOWN
            user32.PostMessageW(target_hwnd, 0x0202, 0, lparam)  # WM_LBUTTONUP
    except Exception:
        pass


class FolderImportApp(tk.Tk):
    """Unified Import Dialog supporting Choice screen and Folder Import screen."""
    def __init__(self, mode="choice", initial_dir=None):
        super().__init__()
        self.configure(bg=BG_COLOR)

        self.initial_dir = initial_dir or r"C:\Users\user\Downloads\ER1"
        if not os.path.exists(self.initial_dir):
            self.initial_dir = os.path.expanduser(r"~\Downloads")

        self.current_folder = tk.StringVar(value=self.initial_dir)
        self.patient_var = tk.StringVar()
        self.records_data = []
        self.item_checkboxes = {}
        self.exit_code = 0

        self._init_styles()

        # Container frames for smooth in-window switching
        self.choice_frame = tk.Frame(self, bg=BG_COLOR)
        self.folder_frame = tk.Frame(self, bg=BG_COLOR)

        self._build_choice_ui()
        self._build_folder_ui()

        self.protocol("WM_DELETE_WINDOW", self._cancel)

        if mode == "choice":
            self.title("Import ECG - Select Source")
            self.geometry("540x360")
            self.resizable(False, False)
            self._center_window(540, 360)
            self.choice_frame.pack(fill="both", expand=True)
        else:
            self.title(APP_TITLE)
            self.geometry("880x560")
            self.minsize(760, 460)
            self.resizable(True, True)
            self._center_window(880, 560)
            self.folder_frame.pack(fill="both", expand=True)
            self._load_folder(self.current_folder.get())

        # Ensure window is always brought to top and focused
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.lift()
        self.focus_force()

    def _center_window(self, width, height):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _init_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background="#ffffff",
            foreground=TEXT_COLOR,
            fieldbackground="#ffffff",
            font=("Segoe UI", 10),
            rowheight=32,
            borderwidth=1
        )
        style.configure(
            "Treeview.Heading",
            background="#f1f5f9",
            foreground="#34495e",
            font=("Segoe UI", 10, "bold"),
            borderwidth=1,
            relief="flat"
        )
        style.map("Treeview", background=[("selected", "#e3f2fd")], foreground=[("selected", TEXT_COLOR)])

    # -------------------------------------------------------------
    # Choice Screen UI
    # -------------------------------------------------------------
    def _build_choice_ui(self):
        header = tk.Frame(self.choice_frame, bg=PRIMARY_COLOR, height=75)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_lbl = tk.Label(
            header,
            text="📥  Import ECG Recording",
            font=("Segoe UI", 16, "bold"),
            fg="white",
            bg=PRIMARY_COLOR
        )
        title_lbl.pack(pady=(12, 2))

        sub_lbl = tk.Label(
            header,
            text="Choose your recording source to begin analysis",
            font=("Segoe UI", 9),
            fg="#e3f2fd",
            bg=PRIMARY_COLOR
        )
        sub_lbl.pack()

        content = tk.Frame(self.choice_frame, bg=BG_COLOR, padx=30, pady=25)
        content.pack(fill="both", expand=True)

        dev_btn = tk.Button(
            content,
            text="📱  From Device\nDirectly download recordings from connected ER1 via USB",
            font=("Segoe UI", 11, "bold"),
            bg="#ffffff",
            fg=TEXT_COLOR,
            activebackground="#eef7fe",
            activeforeground=PRIMARY_COLOR,
            relief="solid",
            bd=1,
            cursor="hand2",
            justify="center",
            pady=12,
            command=self._on_device_choice_clicked
        )
        dev_btn.pack(fill="x", pady=(0, 15))

        folder_btn = tk.Button(
            content,
            text="📁  From Folder\nSelect folder with files from ER1 (e.g. Downloads\\ER1)",
            font=("Segoe UI", 11, "bold"),
            bg="#ffffff",
            fg=PRIMARY_COLOR,
            activebackground="#eef7fe",
            activeforeground=PRIMARY_HOVER,
            relief="solid",
            bd=1,
            cursor="hand2",
            justify="center",
            pady=12,
            command=self._on_folder_choice_clicked
        )
        folder_btn.pack(fill="x", pady=(0, 10))

    def _on_device_choice_clicked(self):
        er1_drive = find_er1_usb_drive()
        if er1_drive:
            self._switch_to_folder(er1_drive)
        else:
            ans = messagebox.askquestion(
                "Device Not Connected",
                "No ER1 device was detected via USB.\n\n"
                "Would you like to import from folder (e.g. copied files) instead?",
                icon="warning",
                parent=self
            )
            if ans == "yes":
                self._switch_to_folder()
            else:
                self.exit_code = 1
                self.destroy()

    def _on_folder_choice_clicked(self):
        self._switch_to_folder()

    def _switch_to_folder(self, target_folder=None):
        self.choice_frame.pack_forget()
        self.title(APP_TITLE)
        self.geometry("880x560")
        self.minsize(760, 460)
        self.resizable(True, True)
        self._center_window(880, 560)
        self.folder_frame.pack(fill="both", expand=True)

        folder = target_folder or self.current_folder.get()
        if target_folder:
            self.current_folder.set(target_folder)
        self._load_folder(folder)

        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.lift()
        self.focus_force()

    # -------------------------------------------------------------
    # Folder Import Screen UI
    # -------------------------------------------------------------
    def _build_folder_ui(self):
        top_bar = tk.Frame(self.folder_frame, bg=PRIMARY_COLOR, height=50)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        top_title = tk.Label(
            top_bar,
            text="📁  Import ER1 Recordings",
            font=("Segoe UI", 13, "bold"),
            fg="white",
            bg=PRIMARY_COLOR
        )
        top_title.pack(side="left", padx=20, pady=10)

        control_card = tk.Frame(self.folder_frame, bg=CARD_BG, padx=15, pady=10, relief="solid", bd=1)
        control_card.pack(fill="x", padx=20, pady=(10, 8))

        folder_row = tk.Frame(control_card, bg=CARD_BG)
        folder_row.pack(fill="x", pady=(0, 6))

        folder_lbl = tk.Label(folder_row, text="Source Folder:", font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_COLOR)
        folder_lbl.pack(side="left", padx=(0, 10))

        folder_entry = tk.Entry(folder_row, textvariable=self.current_folder, font=("Segoe UI", 10), relief="solid", bd=1)
        folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=2)

        browse_btn = tk.Button(
            folder_row,
            text="Browse...",
            font=("Segoe UI", 9, "bold"),
            bg="#f0f4f8",
            fg=TEXT_COLOR,
            activebackground="#e2e8f0",
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=12,
            pady=2,
            command=self._browse_folder
        )
        browse_btn.pack(side="right")

        patient_row = tk.Frame(control_card, bg=CARD_BG)
        patient_row.pack(fill="x")

        patient_lbl = tk.Label(patient_row, text="Assign to Patient:", font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_COLOR)
        patient_lbl.pack(side="left", padx=(0, 10))

        self.subusers = get_subusers()
        patient_options = [f"{u['name']} (ID: {u['id']})" for u in self.subusers]
        self.patient_var.set(patient_options[0] if patient_options else "Grygoriev (ID: 1)")

        patient_dropdown = ttk.Combobox(
            patient_row,
            textvariable=self.patient_var,
            values=patient_options,
            state="readonly",
            font=("Segoe UI", 10),
            width=30
        )
        patient_dropdown.pack(side="left")

        # 3. Bottom Action & Selection Bar (Packed side="bottom" first to guarantee 100% visibility)
        action_bar = tk.Frame(self.folder_frame, bg="#edf2f7", padx=15, pady=8, relief="solid", bd=1)
        action_bar.pack(side="bottom", fill="x")

        sel_all_btn = tk.Button(
            action_bar,
            text="Select All New",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg=TEXT_COLOR,
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._select_all_new
        )
        sel_all_btn.pack(side="left", padx=(0, 8))

        desel_btn = tk.Button(
            action_bar,
            text="Deselect All",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg=TEXT_COLOR,
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._deselect_all
        )
        desel_btn.pack(side="left", padx=(0, 15))

        self.summary_lbl = tk.Label(
            action_bar,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg="#edf2f7",
            fg=MUTED_COLOR
        )
        self.summary_lbl.pack(side="left")

        cancel_btn = tk.Button(
            action_bar,
            text="Cancel",
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg=TEXT_COLOR,
            activebackground="#e2e8f0",
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=18,
            pady=4,
            command=self._cancel
        )
        cancel_btn.pack(side="right", padx=(10, 0))

        self.import_btn = tk.Button(
            action_bar,
            text="Import Selected Recordings (0)",
            font=("Segoe UI", 9, "bold"),
            bg=PRIMARY_COLOR,
            fg="white",
            activebackground=PRIMARY_HOVER,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=5,
            command=self._do_import
        )
        self.import_btn.pack(side="right")

        # 4. Table Panel (Fills all remaining vertical space in center)
        table_frame = tk.Frame(self.folder_frame, bg=BG_COLOR, padx=20)
        table_frame.pack(side="top", fill="both", expand=True, pady=(0, 10))

        columns = ("select", "filename", "time", "duration", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("select", text="[✓]", anchor="center")
        self.tree.heading("filename", text="Recording File", anchor="w")
        self.tree.heading("time", text="Recording Start Time", anchor="center")
        self.tree.heading("duration", text="Duration", anchor="center")
        self.tree.heading("status", text="Uniqueness / Status", anchor="center")

        self.tree.column("select", width=55, minwidth=50, anchor="center")
        self.tree.column("filename", width=190, minwidth=140, anchor="w")
        self.tree.column("time", width=190, minwidth=160, anchor="center")
        self.tree.column("duration", width=130, minwidth=110, anchor="center")
        self.tree.column("status", width=200, minwidth=160, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<space>", self._on_tree_space)

    def _browse_folder(self):
        initial = self.current_folder.get()
        if not os.path.exists(initial):
            initial = r"C:\Users\user\Downloads"
        chosen = filedialog.askdirectory(
            parent=self,
            title="Select Folder with ER1 Recordings",
            initialdir=initial
        )
        if chosen:
            self.current_folder.set(chosen)
            self._load_folder(chosen)

    def _load_folder(self, folder_path):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.records_data.clear()
        self.item_checkboxes.clear()

        if not os.path.exists(folder_path):
            self.summary_lbl.config(text="Folder not found.", fg="#e74c3c")
            self._update_import_button()
            return

        subusr_id = self._get_selected_subuser_id()
        records = scan_folder_records(folder_path, subusr_id=subusr_id)
        self.records_data = records

        if not records:
            self.summary_lbl.config(text="No ER1 files (R*) found in folder.", fg=MUTED_COLOR)
            self._update_import_button()
            return

        new_count = 0
        dup_count = 0

        for idx, rec in enumerate(records):
            item_id = str(idx)
            is_dup = rec["is_duplicate"]
            checked = not is_dup  # Pre-select new files
            if checked:
                new_count += 1
            else:
                dup_count += 1
            self.item_checkboxes[item_id] = checked

            check_mark = "  ☑  " if checked else "  ☐  "
            status_text = f"Already Exists (ID {rec['existing_id']})" if is_dup else "Ready (New)"

            tag = "dup" if is_dup else "new"
            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(check_mark, rec["filename"], rec["datetime_display"], rec["duration_display"], status_text),
                tags=(tag,)
            )

        self.tree.tag_configure("new", foreground="#2c3e50")
        self.tree.tag_configure("dup", foreground="#95a5a6")

        self.summary_lbl.config(
            text=f"Total: {len(records)} files  |  New: {new_count}  |  Existing: {dup_count}",
            fg=TEXT_COLOR
        )
        self._update_import_button()

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item_id:
            return
        if region in ("cell", "tree") and (col == "#1" or event.x < 70):
            self._toggle_item(item_id)

    def _on_tree_space(self, event):
        sel = self.tree.selection()
        if sel:
            self._toggle_item(sel[0])

    def _toggle_item(self, item_id):
        current = self.item_checkboxes.get(item_id, False)
        new_state = not current
        self.item_checkboxes[item_id] = new_state

        mark = "  ☑  " if new_state else "  ☐  "
        vals = list(self.tree.item(item_id, "values"))
        vals[0] = mark
        self.tree.item(item_id, values=vals)
        self._update_import_button()

    def _select_all_new(self):
        for idx, rec in enumerate(self.records_data):
            item_id = str(idx)
            if not rec["is_duplicate"]:
                self.item_checkboxes[item_id] = True
                vals = list(self.tree.item(item_id, "values"))
                vals[0] = "  ☑  "
                self.tree.item(item_id, values=vals)
        self._update_import_button()

    def _deselect_all(self):
        for idx in range(len(self.records_data)):
            item_id = str(idx)
            self.item_checkboxes[item_id] = False
            vals = list(self.tree.item(item_id, "values"))
            vals[0] = "  ☐  "
            self.tree.item(item_id, values=vals)
        self._update_import_button()

    def _update_import_button(self):
        selected_count = sum(1 for v in self.item_checkboxes.values() if v)
        if selected_count > 0:
            self.import_btn.config(
                text=f"Import Selected Recordings ({selected_count})",
                state="normal",
                bg=PRIMARY_COLOR
            )
        else:
            self.import_btn.config(
                text="Import Selected Recordings (0)",
                state="disabled",
                bg="#b0bec5"
            )

    def _get_selected_subuser_id(self):
        val = self.patient_var.get()
        if "ID: " in val:
            try:
                return int(val.split("ID: ")[1].rstrip(")"))
            except Exception:
                pass
        return 1

    def _do_import(self):
        selected_files = []
        for idx, rec in enumerate(self.records_data):
            if self.item_checkboxes.get(str(idx), False):
                selected_files.append(rec["filepath"])

        if not selected_files:
            messagebox.showwarning("No Files Selected", "Please select at least one recording to import.", parent=self)
            return

        subusr_id = self._get_selected_subuser_id()

        self.import_btn.config(state="disabled", text="Importing, please wait...")
        self.update_idletasks()

        res = import_records(selected_files, subusr_id=subusr_id, force=True)

        imported_count = len(res["imported"])
        skipped_count = len(res["duplicates_skipped"])
        errors_count = len(res["errors"])

        summary_lines = [
            f"Import complete for patient: {self.patient_var.get()}\n",
            f"✔ Successfully imported: {imported_count} record(s)",
        ]
        if res["imported"]:
            summary_lines.append("\nImported Files:")
            for item in res["imported"]:
                summary_lines.append(f"  • {item['file']}: {item['message']}")

        if skipped_count > 0:
            summary_lines.append(f"\nDuplicate files skipped: {skipped_count}")

        if errors_count > 0:
            summary_lines.append(f"\nErrors encountered: {errors_count}")
            for err in res["errors"]:
                summary_lines.append(f"  • {err['file']}: {err['message']}")

        summary_lines.append("\nThe ECG Data Management table has been updated with the new records.")

        messagebox.showinfo(
            "ECG Import Summary",
            "\n".join(summary_lines),
            parent=self
        )

        refresh_main_window()

        self.exit_code = 2
        self.destroy()

    def _cancel(self):
        self.exit_code = 0
        self.destroy()


def main():
    mode = "choice"
    initial_dir = None

    if "--folder" in sys.argv:
        mode = "folder"
    if len(sys.argv) > 1 and not sys.argv[-1].startswith("--"):
        initial_dir = sys.argv[-1]

    app = FolderImportApp(mode=mode, initial_dir=initial_dir)
    app.mainloop()
    sys.exit(app.exit_code)


if __name__ == "__main__":
    main()
