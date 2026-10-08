#!/usr/bin/env python3
"""
Import recordings from a folder or an ER1 USB drive.

One window: pick the patient, see each recording, import on a background thread.
Exit codes used by the portable launcher:
  0 cancel, 1 open the original device dialog, 2 recordings were imported.
"""

import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from import_local_er1 import (
    scan_folder_records,
    import_single_file,
    find_recording_sources,
    load_report_summaries,
    format_report_chip,
    format_file_size,
)
from manage_users import AddUserDialog, get_all_subusers
from ui_theme import (
    BG, CARD, BORDER, TEXT, MUTED, PRIMARY, SUCCESS, WARNING, ERROR, ROW_ALT, STRIPE,
    FONT, FONT_BOLD, FONT_SMALL, FONT_TITLE,
    apply_theme, button, center,
)

APP_TITLE = "Import recordings"


def patient_label(user):
    return "%s · %s · %s · %s recordings (ID: %s)" % (
        user["name"], user["age"], user["gender"], user["records"], user["id"],
    )


def patient_id_from_label(label):
    if "(ID:" not in label:
        return 1
    try:
        return int(label.split("(ID:")[1].split(")")[0].strip())
    except (IndexError, ValueError):
        return 1


class FolderImportApp(tk.Tk):
    """Single import window. `mode` is accepted so older launchers keep working."""

    def __init__(self, mode="choice", initial_dir=None):
        super().__init__()
        del mode
        self.title(APP_TITLE)
        self.configure(bg=BG)
        apply_theme(self)
        self.minsize(860, 560)
        center(self, 980, 660)

        self._queue = queue.Queue()
        self._busy = False
        self._imported_any = False
        self._suppress_patient = False
        self._sources = []
        self.records = []
        self.exit_code = 0

        self.initial_dir = self._starting_folder(initial_dir)
        self.current_folder = tk.StringVar(value=self.initial_dir)
        self.patient_var = tk.StringVar()
        self.new_only = tk.BooleanVar(value=False)
        self.summary_var = tk.StringVar(value="")
        self.banner_var = tk.StringVar(value="")

        self._build()
        self._reload_patients()
        self._refresh_sources()
        self._load_folder(self.current_folder.get())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())
        self._poll_after = self.after(80, self._poll)
        self._top_after = None

        self.attributes("-topmost", True)
        self._top_after = self.after(400, self._drop_topmost)
        self.lift()
        self.focus_force()

    def _drop_topmost(self):
        self._top_after = None
        if self.winfo_exists():
            self.attributes("-topmost", False)

    def destroy(self):
        for job in (getattr(self, "_poll_after", None), getattr(self, "_top_after", None)):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._poll_after = None
        self._top_after = None
        try:
            self.unbind_all("<MouseWheel>")
        except Exception:
            pass
        super().destroy()

    def _starting_folder(self, initial_dir):
        if initial_dir and os.path.isdir(initial_dir):
            return initial_dir
        sources = find_recording_sources()
        if sources:
            return sources[0]["path"]
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        er1 = os.path.join(downloads, "ER1")
        if os.path.isdir(er1):
            return er1
        if os.path.isdir(downloads):
            return downloads
        return os.path.expanduser("~")

    def _build(self):
        tk.Frame(self, bg=PRIMARY, height=4).pack(fill="x")

        header = tk.Frame(self, bg=CARD, padx=20, pady=12, highlightthickness=1, highlightbackground=BORDER)
        header.pack(fill="x")
        tk.Label(header, text=APP_TITLE, font=FONT_TITLE, fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(
            header,
            text="New recordings are selected. Imported ones stay unchecked unless you choose to replace them.",
            font=FONT_SMALL,
            fg=MUTED,
            bg=CARD,
        ).pack(anchor="w", pady=(2, 0))

        controls = tk.Frame(self, bg=CARD, padx=16, pady=12, highlightthickness=1, highlightbackground=BORDER)
        controls.pack(fill="x", padx=16, pady=(12, 8))

        patient_row = tk.Frame(controls, bg=CARD)
        patient_row.pack(fill="x", pady=(0, 8))
        tk.Label(patient_row, text="Patient", font=FONT_BOLD, fg=TEXT, bg=CARD).pack(side="left")
        self.patient_combo = ttk.Combobox(
            patient_row, textvariable=self.patient_var, state="readonly", font=FONT, width=52,
        )
        self.patient_combo.pack(side="left", padx=(10, 8))
        self.patient_var.trace_add("write", self._on_patient_changed)
        button(patient_row, "New patient", self._add_patient, kind="quiet").pack(side="left")

        folder_row = tk.Frame(controls, bg=CARD)
        folder_row.pack(fill="x")
        tk.Label(folder_row, text="Source", font=FONT_BOLD, fg=TEXT, bg=CARD).pack(side="left")
        entry = tk.Entry(
            folder_row, textvariable=self.current_folder, font=FONT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=PRIMARY,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(10, 8), ipady=3)
        entry.bind("<Return>", lambda _event: self._load_folder(self.current_folder.get()))
        button(folder_row, "Browse", self._browse).pack(side="left")
        self.chip = button(folder_row, "No ER1 drive detected", self._use_detected_drive, kind="quiet")
        self.chip.pack(side="left", padx=(8, 0))

        list_head = tk.Frame(self, bg=STRIPE, padx=16, pady=6)
        list_head.pack(fill="x", padx=16)
        for text, width in ((" ", 4), ("When", 28), ("Length", 12), ("Size", 10)):
            tk.Label(list_head, text=text, font=FONT_BOLD, fg=TEXT, bg=STRIPE, width=width, anchor="w").pack(side="left")
        tk.Label(list_head, text="State", font=FONT_BOLD, fg=TEXT, bg=STRIPE, anchor="w").pack(side="left", fill="x", expand=True)

        table = tk.Frame(self, bg=BG, padx=16)
        table.pack(fill="both", expand=True, pady=(0, 8))
        self.canvas = tk.Canvas(table, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.canvas.yview)
        self.rows = tk.Frame(self.canvas, bg=BG)
        self._rows_window = self.canvas.create_window((0, 0), window=self.rows, anchor="nw")
        self.rows.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._stretch_rows)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda _event: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda _event: self.canvas.unbind_all("<MouseWheel>"))

        self.banner = tk.Label(self, textvariable=self.banner_var, font=FONT, fg=SUCCESS, bg=BG, anchor="w", justify="left")
        self.banner.pack(fill="x", padx=18)

        self.progress = ttk.Progressbar(self, mode="determinate")

        footer = tk.Frame(self, bg=STRIPE, padx=12, pady=10, highlightthickness=1, highlightbackground=BORDER)
        footer.pack(fill="x", side="bottom")
        button(footer, "Select new", self._select_new).pack(side="left")
        button(footer, "Clear", self._clear_selection).pack(side="left", padx=(8, 0))
        tk.Checkbutton(
            footer, text="New only", variable=self.new_only, command=self._render_rows,
            font=FONT, bg=STRIPE, fg=TEXT, activebackground=STRIPE, selectcolor=CARD, cursor="hand2",
        ).pack(side="left", padx=(12, 0))
        tk.Label(footer, textvariable=self.summary_var, font=FONT_SMALL, fg=MUTED, bg=STRIPE).pack(side="left", padx=(12, 0))

        button(footer, "Original device import", self._open_vendor, kind="quiet").pack(side="right", padx=(8, 0))
        button(footer, "Close", self._cancel).pack(side="right", padx=(8, 0))
        self.import_btn = button(footer, "Import recordings", self._do_import, kind="primary")
        self.import_btn.pack(side="right")

    def _stretch_rows(self, event):
        self.canvas.itemconfigure(self._rows_window, width=event.width)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _reload_patients(self, select_id=None):
        self._patients = get_all_subusers()
        labels = [patient_label(user) for user in self._patients]
        self.patient_combo["values"] = labels
        chosen = labels[0] if labels else ""
        if select_id is not None:
            for user, label in zip(self._patients, labels):
                if user["id"] == select_id:
                    chosen = label
                    break
        self._suppress_patient = True
        self.patient_var.set(chosen)
        self._suppress_patient = False

    def _selected_patient_id(self):
        return patient_id_from_label(self.patient_var.get())

    def _on_patient_changed(self, *_args):
        if self._suppress_patient or self._busy:
            return
        folder = self.current_folder.get()
        if folder:
            self._load_folder(folder)

    def _add_patient(self):
        if self._busy:
            return

        def added(user):
            self._reload_patients(select_id=user["id"])
            self._load_folder(self.current_folder.get())

        AddUserDialog(self, on_success=added)

    def _refresh_sources(self):
        self._sources = find_recording_sources()
        if not self._sources:
            self.chip.config(text="No ER1 drive detected", state="disabled")
            return
        source = self._sources[0]
        serial = (" · SN " + source["serial"]) if source["serial"] else " · serial not on the files"
        self.chip.config(
            text="%s · %d files%s" % (source["path"], source["count"], serial),
            state="normal",
        )

    def _use_detected_drive(self):
        if self._busy or not self._sources:
            return
        self.current_folder.set(self._sources[0]["path"])
        self._load_folder(self._sources[0]["path"])

    def _browse(self):
        if self._busy:
            return
        initial = self.current_folder.get()
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        chosen = filedialog.askdirectory(parent=self, title="Folder with ER1 recordings", initialdir=initial)
        if chosen:
            self.current_folder.set(chosen)
            self._load_folder(chosen)

    def _load_folder(self, folder_path):
        self.records = []
        if not folder_path or not os.path.isdir(folder_path):
            self.summary_var.set("Folder not found.")
            self._render_rows()
            self._update_import_button()
            return

        patient_id = self._selected_patient_id()
        reports = load_report_summaries(patient_id)
        records = scan_folder_records(folder_path, subusr_id=patient_id)
        records.sort(key=lambda item: item["timestamp"], reverse=True)
        for record in records:
            record["checked"] = not record["is_duplicate"]
            record["report"] = format_report_chip(reports.get(record["timestamp"]))
            record["_var"] = None
        self.records = records
        self._render_rows()
        self._update_summary()
        self._update_import_button()

    def _render_rows(self):
        for child in self.rows.winfo_children():
            child.destroy()
        for record in self.records:
            record["_var"] = None

        visible = [
            record for record in self.records
            if not (self.new_only.get() and record["is_duplicate"])
        ]
        if not visible:
            text = "No ER1 recordings in this folder." if not self.records else "No new recordings. Turn off New only to see imported ones."
            tk.Label(self.rows, text=text, font=FONT, fg=MUTED, bg=BG, pady=24).pack(anchor="w")
            return

        for index, record in enumerate(visible):
            self._build_row(record, index % 2 == 1)

    def _build_row(self, record, alt):
        bg = ROW_ALT if alt else CARD
        style = "Alt.TCheckbutton" if alt else "TCheckbutton"
        row = tk.Frame(self.rows, bg=bg, padx=8, pady=6)
        row.pack(fill="x")

        var = tk.BooleanVar(value=record["checked"])
        record["_var"] = var

        def toggle(*_args):
            record["checked"] = bool(var.get())
            self._paint_state(state, record)
            self._update_summary()
            self._update_import_button()

        var.trace_add("write", toggle)
        ttk.Checkbutton(row, variable=var, style=style).pack(side="left", padx=(4, 8))

        when = tk.Frame(row, bg=bg)
        when.pack(side="left", padx=(0, 12))
        when_title = tk.Label(when, text=record["datetime_display"], font=FONT_BOLD, fg=TEXT, bg=bg)
        when_title.pack(anchor="w")
        when_file = tk.Label(when, text=record["filename"], font=FONT_SMALL, fg=MUTED, bg=bg)
        when_file.pack(anchor="w")

        length = tk.Label(row, text=record["duration_display"], font=FONT, fg=TEXT, bg=bg, width=12, anchor="w")
        length.pack(side="left")
        size = tk.Label(row, text=format_file_size(record["file_size"]), font=FONT, fg=TEXT, bg=bg, width=10, anchor="w")
        size.pack(side="left")
        state = tk.Label(row, text="", font=FONT, bg=bg, anchor="w", justify="left")
        state.pack(side="left", fill="x", expand=True)
        self._paint_state(state, record)

        def flip(_event, target=var):
            if not self._busy:
                target.set(not target.get())

        for widget in (row, when, when_title, when_file, length, size, state):
            widget.bind("<Button-1>", flip)

    def _paint_state(self, label, record):
        if record["is_duplicate"] and record["checked"]:
            text, color = "Replace existing", WARNING
        elif record["is_duplicate"]:
            text, color = "Imported", MUTED
        elif record["checked"]:
            text, color = "New", SUCCESS
        else:
            text, color = "Not selected", MUTED
        if record.get("report"):
            text = "%s · %s" % (text, record["report"])
        label.config(text=text, fg=color)

    def _set_checked(self, record, value):
        record["checked"] = value
        var = record.get("_var")
        if var is not None and bool(var.get()) != value:
            var.set(value)

    def _select_new(self):
        if self._busy:
            return
        for record in self.records:
            self._set_checked(record, not record["is_duplicate"])
        self._update_summary()
        self._update_import_button()

    def _clear_selection(self):
        if self._busy:
            return
        for record in self.records:
            self._set_checked(record, False)
        self._update_summary()
        self._update_import_button()

    def _selected_records(self):
        return [record for record in self.records if record["checked"]]

    def _update_summary(self):
        total = len(self.records)
        new_count = sum(1 for record in self.records if not record["is_duplicate"])
        imported = total - new_count
        selected = len(self._selected_records())
        self.summary_var.set("%d recordings · %d new · %d imported · %d selected" % (total, new_count, imported, selected))

    def _update_import_button(self):
        selected = self._selected_records()
        replace = sum(1 for record in selected if record["is_duplicate"])
        fresh = len(selected) - replace
        if self._busy:
            self.import_btn.config(state="disabled", bg="#b0bec5", text="Importing…")
            return
        if not selected:
            self.import_btn.config(state="disabled", bg="#b0bec5", text="Import recordings")
            return
        parts = []
        if fresh:
            parts.append("Import %d" % fresh)
        if replace:
            parts.append("replace %d" % replace)
        self.import_btn.config(state="normal", bg=PRIMARY, text=", ".join(parts))

    def _do_import(self):
        selected = self._selected_records()
        if not selected or self._busy:
            return
        jobs = [(record["filepath"], bool(record["is_duplicate"])) for record in selected]
        patient_id = self._selected_patient_id()
        self._busy = True
        self.import_btn.config(state="disabled", bg="#b0bec5", text="Importing…")
        self.progress.pack(fill="x", padx=18, pady=(0, 6), before=self.banner)
        self.progress.configure(maximum=len(jobs), value=0)
        self.banner_var.set("")
        threading.Thread(
            target=self._import_worker, args=(jobs, patient_id), daemon=True,
        ).start()

    def _import_worker(self, jobs, patient_id):
        results = []
        total = len(jobs)
        for index, (path, force) in enumerate(jobs, 1):
            name = os.path.basename(path)
            self._queue.put(("progress", index, total, name))
            try:
                ok, message, _timestamp = import_single_file(path, subusr_id=patient_id, force=force)
            except Exception as exc:
                ok, message = False, str(exc)
            duplicate = "already exists" in message.lower()
            results.append((name, ok, message, duplicate))
        self._queue.put(("done", results))

    def _poll(self):
        self._poll_after = None
        if not self.winfo_exists():
            return
        try:
            while True:
                item = self._queue.get_nowait()
                if item[0] == "progress":
                    _kind, index, total, name = item
                    self.progress.configure(value=max(0, index - 1))
                    self.summary_var.set("Importing %d of %d — %s" % (index, total, name))
                else:
                    self._finish_import(item[1])
        except queue.Empty:
            if self.winfo_exists():
                self._poll_after = self.after(80, self._poll)
        except tk.TclError:
            return

    def _finish_import(self, results):
        imported = [item for item in results if item[1]]
        failed = [item for item in results if not item[1] and not item[3]]
        if imported:
            self._imported_any = True
        self.progress.configure(value=self.progress["maximum"])
        lines = []
        if imported:
            lines.append("Imported %d recording%s." % (len(imported), "" if len(imported) == 1 else "s"))
        if failed:
            detail = "; ".join("%s (%s)" % (name, message) for name, _ok, message, _dup in failed[:3])
            lines.append("Failed: %s" % detail)
        if self._imported_any:
            lines.append("Close this window to reload ECG Data Management.")
        self.banner_var.set(" ".join(lines))
        self.banner.config(fg=ERROR if failed and not imported else SUCCESS)
        self._busy = False
        self._load_folder(self.current_folder.get())

    def _open_vendor(self):
        if self._busy:
            return
        self.exit_code = 2 if self._imported_any else 1
        self.destroy()

    def _cancel(self):
        if self._busy:
            self.banner_var.set("Import still running.")
            self.banner.config(fg=WARNING)
            return
        self.exit_code = 2 if self._imported_any else 0
        self.destroy()


def main():
    initial_dir = None
    if len(sys.argv) > 1 and not sys.argv[-1].startswith("--"):
        initial_dir = sys.argv[-1]
    app = FolderImportApp(initial_dir=initial_dir)
    app.mainloop()
    sys.exit(app.exit_code)


if __name__ == "__main__":
    main()
