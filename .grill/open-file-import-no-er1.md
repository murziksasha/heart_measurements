# Open file import when no ER1 is connected

Date: 2026-10-15

## Intent

Clicking **Import Data** in ECG Data Management opens the folder importer directly, even when no ER1 recorder is plugged in. The vendor dialog ("Download data" / "Please connect your device first!") is hidden immediately and never left on screen.

## Constraints

- Folder importer opens directly: launches `import_gui.py --folder`, showing patient selection and file browsing without requiring an intermediate chooser.
- Device import is still accessible: clicking **Original device import** inside the folder importer window exits with code 1 and is the only path that reveals the vendor download dialog.
- Launcher intercepts vendor dialog robustly:
  - Measures popups under per-monitor DPI awareness (`DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE`).
  - Matches by title (`Download` or `Import`), ±48 px of 387×273, or ±40 px of no-device popups (265×142 and 265×157).
  - Performs a follow-up re-check after ~150 ms to catch late title or size updates from Qt.
  - One match at a time (`s_importLock` and `s_isImportModalRunning`); ignores main window and `s_allowedDeviceHwnd`.
- Launcher failure safety: if Python fails to start, the launcher logs the error and closes the hidden vendor dialog via `WM_CLOSE`. It never falls through to un-hiding the vendor dialog.
- Preserves existing patient management, database sync, and analysis functionality without regressions.

## Key decisions

- Decision: Launch `import_gui.py --folder` on toolbar Import click. Reason: Folder import does not require a device, and the window already contains the **Original device import** button to switch to vendor device download when needed.
- Decision: Per-monitor DPI awareness during interceptor window measurement (`GetWindowRectDpiAware`). Reason: Qt windows are per-monitor DPI aware; measuring in an unaware thread shifts coordinates and distorts window sizes across different display scales.
- Decision: Re-check after 150 ms off the WinEvent callback. Reason: Qt frequently shows the native window before painting the text or finishing layout, so the title and size can arrive slightly after `EVENT_OBJECT_SHOW`.
- Decision: Launcher failure sets exit code -1 and closes vendor dialog. Reason: Exit code 1 must be strictly reserved for an intentional click on **Original device import**, preventing a broken Python environment from revealing the vendor error dialog.
- Decision: Rebuild `AI-ECG Portable.exe` using .NET Framework `csc.exe`. Reason: The launcher binary must match `Program.cs` changes in the portable distribution.

## Surfaced assumptions

- `import_gui.py` at repository root is the executed script (`App/import_gui.py` is stale and untouched).
- Qt dialog classes contain `"Qt"`.
- Closing the folder importer on cancel (exit code 0) leaves ECG Data Management active with no patient table changes.
- Successful import (exit code 2) syncs host storage to portable `Data/` and restarts ECG Data Management to reload the patient list.

## Out of scope

- Changes to patient database schema or import decompression logic in `import_local_er1.py`.
- Modifications to `App/` directory binaries or scripts.
- Modifying `+ Add User` button placement logic.

