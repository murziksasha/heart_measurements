# AI-ECG Analysis System - Portable Edition Specifications

System architecture, component specifications, and operational rules for the portable AI-ECG Analysis distribution.

## Documentation Index

- [Launcher & Interceptor Specification](interceptor-and-launcher.md) — Win32 interceptor lifecycle, DPI awareness, popup matching, scaled size bands, message pump timer scanning, sidebar button injection.
- [Import Workflow Specification](import-workflow.md) — Chooser modal, folder import UI, ER1 decompression, SQLite database ingestion, exit codes, sync & restart lifecycle.
- [Patient Management Specification](patient-management.md) — Patient profile schema, SQLite tables, CRUD operations, UI dialogs, validation rules.
- [Device Management Specification](device-management.md) — Recorder binding/unbinding, serial number validation, USB scan matching rules.
- [Development & Engineering Rules](development-rules.md) — Build rules (`csc.exe`), Python coding conventions, testing requirements, encoding standards.

## System Architecture Overview

```
+---------------------------------------------------------------------------------+
|                              AI-ECG Portable.exe                                |
|  - Manages single-instance mutex                                                |
|  - Isolates localAppData/ECG Browser profile (backup & restore host profile)    |
|  - Launches App/ECG Data Management.exe (vendor Qt application)                 |
|  - Runs Unified Interceptor thread:                                             |
|      * WinEvent hook (EVENT_OBJECT_SHOW)                                        |
|      * 200 ms message pump timer window scanner                                 |
|      * Injects native Segoe UI "+ Add User" button into Qt sidebar              |
|      * Intercepts "Download data" dialogs across all DPI scales                 |
|      * Spawns Python modal dialogs (import chooser, folder import, user add)    |
+---------------------------------------------------------------------------------+
       |
       +---> vendor Qt window ("ECG Data Management")
       |
       +---> import_gui.py (Chooser & Folder Importer)
       |        * Exit code 0 -> Cancel (closes vendor dialog)
       |        * Exit code 1 -> Device import (reveals native vendor dialog)
       |        * Exit code 2 -> Folder import complete (syncs DB, restarts app)
       |
       +---> manage_users.py (Patient Manager & Add User Dialog)
       |        * Direct SQLite database modification on db_lepu_care_world.db
       |        * Exit code 2 -> Patient added, triggers app reload
       |
       +---> manage_devices.py (Device Bind / Unbind Manager)
```

## Storage & Directory Layout

- `AI-ECG Portable.exe`: C# portable launcher and Win32 interceptor.
- `Program.cs`: Source code for the portable launcher.
- `import_gui.py`: Tkinter import chooser (`ImportChooserApp`) and folder import window (`FolderImportApp`).
- `import_local_er1.py`: ER1 recording decompression, waveform parsing, and database insertion engine.
- `manage_users.py`: Patient management GUI and SQLite database helper.
- `manage_devices.py`: Device binding GUI for ER1/ER2 serial numbers.
- `ui_theme.py`: Shared UI palette, styling, font constants, and button widget builders.
- `App/`: Vendor application binaries (`ECG Data Management.exe`), Qt5 libraries, drivers.
- `Data/`: Persistent portable data directory:
  - `config.ini`: User settings and data directory path.
  - `DATA/db_lepu_care_world.db`: SQLite database for patients, recordings, and bind tables.
  - `DATA/userfiles/subusr/{userId}/`: ECG recording files and AI analysis JSON/PDF reports.
  - `log/interceptor.log`: Launcher and interceptor event log.

