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
- **Header:** Title "Import recordings" with status subtitles and theme accent strip.
- **Patient Selector:**
  - Displays all subusers from `manage_users.get_all_subusers()`.
  - Format: `{name} · {age} · {gender} · {records} recordings (ID: {id})`.
  - "+ New patient" button opens `AddUserDialog` inline without leaving the import workflow.
- **Source Folder & Drive Detection:**
  - Text input with "Browse" folder dialog.
  - Detected drive chip: Checks for connected USB drives matching ER1 recording structure (`find_recording_sources()`).
  - Displays "No ER1 drive detected" or "Detected: {Drive} ({Count} files)".
- **Recording Table:**
  - Columns: Checkbox, When, Length, Size, State.
  - Duplicate detection: Compares prospective file against existing records in SQLite database for selected patient.
  - Report preview: Reads saved AI reports (`report_*.json`) to display average heart rate and diagnosis tags.
- **Filtering & Selection:**
  - "Select new" / "Clear" buttons.
  - "New only" checkbox filter to hide already imported recordings.

### 2.2 Background Import Engine
- Background Worker: Spawns worker thread communicating with GUI via thread-safe `queue.Queue`.
- Progress: Determinate `ttk.Progressbar` with live count: `"Importing {X} of {Total} — {Filename}"`.
- Output state: Sets internal `_imported_any = True` upon any successful record ingestion.

### 2.3 Exit Code Contracts
| Exit Code | Trigger | Action by Portable Launcher |
| :--- | :--- | :--- |
| **0** | Cancel clicked or window closed without imports | Closes intercepted vendor dialog (`WM_CLOSE`). Does not reload. |
| **1** | "Original device import" button clicked | Reveals native vendor dialog (`ShowWindow(SW_SHOW)`), brings to foreground. |
| **2** | Window closed after at least 1 record imported | Closes native dialog, copies host data to portable `Data/`, restarts vendor app. |

---

## 3. ECG File Ingestion Engine (`import_local_er1.py`)

### 3.1 Supported File Types & Detection
- File naming pattern: Starts with `R` followed by timestamp (e.g., `R20261015054228`).
- Raw waveforms and compressed binary formats produced by ER1, ER1-LW, ER1-LB, and ER2/DuoEK devices.
- Auto-decompression and waveform validation.

### 3.2 Database & Storage Integration
- Target SQLite Database: `db_lepu_care_world.db`.
- Record Table: `tb_record` (associates record with `userId`, `deviceSerial`, `startTime`, `duration`, `heartRate`).
- Destination Paths:
  - Raw / decompressed data: `DATA/userfiles/subusr/{userId}/{filename}`
  - Accompanying PDF reports: `DATA/userfiles/subusr/{userId}/Record_{userId}_{serial}_{timestamp}Report.pdf`
  - Accompanying JSON reports: `DATA/userfiles/subusr/{userId}/report_{userId}_{serial}_{timestamp}.json`

