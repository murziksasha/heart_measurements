# Import Workflow Specification

Components: `import_gui.py`, `import_local_er1.py`  
UI Toolkit: Python 3 Tkinter / `ui_theme.py`

## 1. Import Launcher & Chooser Architecture

### 1.1 CLI Entry Point (`main()` in `import_gui.py`)
- **Invocation Without Arguments:**
  - Used by `RunImportModal` in `Program.cs` when user clicks **Import Data** in the vendor GUI.
  - Displays `ImportChooserApp` first.
  - If user selects "Import from folder", transitions to `FolderImportApp`.
- **Invocation With `--folder` or `[path]`:**
  - Used by `Import ECG.bat` for standalone direct folder import.
  - Skips `ImportChooserApp` and directly launches `FolderImportApp`.

### 1.2 `ImportChooserApp` Dialog
- **Window Specs:**
  - Size: `340 × 200` (minimum `300 × 160`), non-resizable, centered on screen.
  - Topmost behavior: Briefly sets `-topmost True` for 400 ms to guarantee foreground focus over vendor Qt windows, then drops topmost.
- **Controls (3 Buttons):**
  1. **"Import from folder" (Primary):** Closes chooser and proceeds to `FolderImportApp`.
  2. **"Import from device" (Secondary):** Closes chooser and terminates process with **exit code 1**.
  3. **"Cancel" (Secondary) / ESC / Window Close:** Terminates process with **exit code 0**.

---

## 2. Folder Import Interface (`FolderImportApp`)

### 2.1 Window Layout & Controls
- **Header:** Title "Import recordings" with accent strip and subtitle:
  `New recordings are selected. A recording already stored for this patient cannot be imported again.`
- **Patient Selector:**
  - Displays all subusers from `manage_users.get_all_subusers()`.
  - Format: `{name} · {age} · {gender} · {records} recordings (ID: {id})`.
  - Switching patient reloads folder records and recomputes duplicate status against that patient's records.
  - "+ New patient" button opens `AddUserDialog` inline without leaving the import workflow.
- **Source Folder & Drive Detection:**
  - Text input with "Browse" folder dialog.
  - Detected drive chip: Checks for connected USB drives containing ER1 recordings (`find_recording_sources()`).
  - Displays "No ER1 drive detected" or "{Drive} · {Count} files · SN {Serial}".
- **Recording Table:**
  - Columns: Checkbox, When, Length, Size, State.
  - State indicators:
    - **Already exist**: Color `MUTED` (`#7f8c8d`), same font as New. Checkbox is disabled and unchecked. Row click does not toggle it.
    - **New**: Color `SUCCESS` (`#27ae60`), checkbox checked by default.
    - **Not selected**: Color `MUTED` (`#7f8c8d`), when a new recording is manually unchecked.
    - Accompanying AI report summary displayed when present (e.g. `77 avg · 49–129 · Normal sinus rhythm`).
    - No "Replace existing" state. A recording already stored for the selected patient cannot be imported again.
  - Selection Controls:
    - **"Select new"**: Checks all new recordings; already-exist rows remain unchecked.
    - **"Clear"**: Unchecks all recordings; already-exist rows remain unchecked.
    - **"New only"**: Checkbox filter that hides already-exist rows.
    - Empty messages: `"No ER1 recordings in this folder."` if no valid ER1 files found, or `"No new recordings. Turn off New only to see imported ones."` when all files already exist.
  - Summary label:
    `%d recordings · %d new · %d already exist · %d selected`
  - Import button:
    - Counts only non-duplicate recordings.
    - Disabled (`#b0bec5`, text `"Import recordings"`) if 0 recordings selected or only already-exist rows.
    - Enabled (`PRIMARY`, text `"Import N"`) when $N \ge 1$ new recordings are selected.

### 2.2 Background Import Engine
- Background Worker: Spawns worker thread communicating with GUI via thread-safe `queue.Queue`.
- Progress: Determinate `ttk.Progressbar` with live count: `"Importing {X} of {Total} — {Filename}"`.
- Output state: Sets internal `_imported_any = True` upon any successful record ingestion.
- Safety: Background jobs never pass `force=True`. Duplicate records are not re-imported.

### 2.3 Exit Code Contracts
| Exit Code | Trigger | Action by Portable Launcher |
| :--- | :--- | :--- |
| **0** | Cancel clicked or window closed without imports | Closes intercepted vendor dialog (`WM_CLOSE`). Does not reload. |
| **1** | "Original device import" button clicked | Reveals native vendor dialog (`ShowWindow(SW_SHOW)`), brings to foreground. |
| **2** | Window closed after at least 1 record imported | Closes native dialog, copies host data to portable `Data/`, restarts vendor app. |

---

## 3. ECG File Ingestion Engine (`import_local_er1.py`)

### 3.1 Supported File Types & Detection (`is_er1_recording`)
- Strict validation via `is_er1_recording(path)`:
  - File exists as a regular file with size $\ge 16$ bytes.
  - Basename matches `^(?:\d{8,12})?R\d{14}$` (optional 8–12 digit serial, `R`, followed by 14-digit timestamp `YYYYMMDDHHMMSS` with no extension).
  - Header check: First byte must be `0x01`, and bytes 1–7 unpack (`<HBBBBB`) to a valid, real `datetime`.
- Non-ECG files (e.g. `RSlogo.png`, `logo.png`, `*.txt`, or files with invalid headers) are rejected and excluded from `scan_folder_records`, `inspect_recording_folder`, and `scan_and_import`.
- `parse_header_timestamp`: Extracts 14-digit timestamp directly following `R` (`R(\d{14})`), falling back to binary header unpacking.
- `import_single_file`: Rejects any path failing `is_er1_recording` before file copy or database insertion.

### 3.2 Uniqueness & Duplicate Scoping
- Unique key: `tb_record.checktime` + `tb_record.subusr_id`.
- Duplicate check: A file is considered a duplicate only if the selected patient already has a record with the same `checktime`. The same file remains importable for another patient.
- `force=True` parameter remains supported in programmatic API for callers, but is never used by the GUI.

### 3.3 Database & Storage Integration
- Target SQLite Database: `db_lepu_care_world.db`.
- Record Table: `tb_record` (associates record with `subusr_id`, `sn`, `checktime`, `duration`, `syncdatetime`).
- Device Table: `tb_device` (ensures recorder serial is registered).
- Destination Paths:
  - Raw recording: `DATA/userfiles/subusr/{subusr_id}/{sn}R{timestamp}`
  - Decompressed PCM dat: `DATA/userfiles/subusr/{subusr_id}/{sn}{timestamp}`
  - Accompanying PDF reports: `DATA/userfiles/subusr/{subusr_id}/Record_{subusr_id}_{sn}_{timestamp}Report.pdf`
  - Accompanying JSON reports: `DATA/userfiles/subusr/{subusr_id}/report_{subusr_id}_{sn}_{timestamp}.json`
