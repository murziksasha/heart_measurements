# Import chooser in front of Import Data

> [!NOTE]
> **Superseded (2026-10-15)**: See [open-file-import-no-er1.md](open-file-import-no-er1.md).
> Clicking **Import Data** now directly launches the folder importer (`--folder`) without showing the chooser dialog. Device download remains available via **Original device import** within that window.

## Grill

Intent: Clicking **Import Data** in ECG Data Management should again offer two actions, **Import from folder** and **Import from device**. Folder import is the existing no-device script. Device import is the vendor download dialog.

Constraints:

- The chooser is the first window after **Import Data**. It is not a pair of buttons on the main toolbar.
- The chooser contains three controls: **Import from folder**, **Import from device**, and **Cancel**. No patient picker, folder path, drive chip, or help line. The window X does the same thing as Cancel.
- **Import from folder** opens the same recording window `Import ECG.bat` opens today, including **Original device import** and the drive chip.
- **Import from device** always unhides the vendor dialog, including when the status bar says the device is not connected.
- Cancel, or closing the recording window without an import, returns to the patient list. The vendor dialog stays closed.
- A successful folder import still closes and reopens ECG Data Management. `Import ECG.bat`, started by itself, still does not restart the app.
- Double-clicking `Import ECG.bat` skips the chooser.

Key decisions:

- Decision: chooser lives in `import_gui.py`, and the existing exit codes stay. Reason: `Program.cs` already hides the vendor dialog, runs `import_gui.py` with no arguments, and treats 0 as cancel, 1 as show the vendor dialog, and 2 as sync plus restart. Alternative considered: drawing the two buttons in the C# launcher, which would require a rebuild for a fork the Python process already owns.
- Decision: `--folder` is honored and skips the chooser. Reason: `Import ECG.bat` already passes `--folder`, and that flag is currently ignored. Alternative considered: a new bat argument, which would change a launcher the user said to leave alone.
- Decision: the recording window is not edited. Reason: the user wants that window exactly as the bat opens it. Alternative considered: removing **Original device import** from it because the chooser has a device button.

Surfaced assumptions:

- The root `import_gui.py` is the one that runs. `Program.cs` and `Import ECG.bat` both use it. `App/import_gui.py` is an unused copy and stays untouched.
- A Python launch failure still falls through to exit code 1 inside `Program.cs`, which shows the vendor dialog. That fallback stays.
- The vendor dialog is still hidden before the chooser appears. The chooser does not look for a drive.

Out of scope:

- Toolbar buttons on ECG Data Management.
- Patient list, **+ Add User**, device binding, analysis, and reports.
- Rebuilding `AI-ECG Portable.exe`.
- Auto-selecting a detected drive on the chooser.

