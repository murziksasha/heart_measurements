========================================================================
AI-ECG Analysis System - Portable Edition (v1.2.0)
========================================================================

ABOUT:
This is a fully self-contained portable edition of the AI-ECG Analysis System.
It runs on any compatible Windows PC (Windows 7/8/10/11) directly from a
folder or USB flash drive without requiring an installation or administrator
rights.

HOW TO USE:
1. Double-click "AI-ECG Portable.exe" to start the application.
2. The application automatically logs into your account (1versuses1@gmail.com)
   with patient profile "Grygoriev" and your registered ER1 device ready.
3. To import ECG recordings:
   - In the top toolbar, click "Import Data".
   - One window opens. It uses a connected ER1 drive when it sees one,
     or browse to a folder of copied files (names starting with R).
   - Pick the patient. New recordings are checked. Already imported ones
     stay unchecked; check one only if you mean to replace it.
   - A saved AI report, when present, is shown on that row (heart rate and
     the first diagnosis).
   - Close the window after a successful import. ECG Data Management
     restarts so the new rows appear. "Original device import" opens the
     vendor dialog instead.
4. View report, View ECG, and batch analysis stay in the main window.
5. When you exit, all newly imported ECG recordings, patient records, PDF
   reports, and user configurations are automatically saved inside "Data/".

DEVICE MANAGEMENT (BIND / UNBIND):
- Double-click "Manage Devices.bat" to open the recorder window.
- Bind a serial you type, or scan USB. A scan binds a device only when the
  serial is present in a file name. It never writes a built-in serial.
- Models: ER1, ER1-LW, ER1-LB, ER2/DuoEK.

DIRECT FILE IMPORT (STANDALONE GUI):
- Double-click "Import ECG.bat" to launch the Folder Import tool directly
  without requiring a physical USB connection.

PATIENT MANAGEMENT:
- Click "+ Add User" in the left sidebar, or right-click and choose
  "+ Add User...".
- Or double-click "Manage Users.bat" to list, add, edit, or delete patients.
- Import also has "New patient".
- Fields: name (20 characters), gender, birthday with a live age, optional
  height and weight. The account email is shown and is not the patient's
  address. There is no note field; the patient table has nowhere to store one.
- Deleting a patient who has recordings asks you to type the name.

DIRECTORY STRUCTURE:
- AI-ECG Portable.exe  : Portable launcher (run this file)
- Manage Users.bat     : Patient Manager tool (add/list/manage patient profiles)
- Manage Devices.bat   : Device Manager tool (bind/unbind device serial numbers)
- Import ECG.bat       : Direct ECG file importer (graphical folder importer)
- manage_users.py      : Patient list, add, and edit
- manage_devices.py    : Recorder bind / unbind window
- import_gui.py        : Import window
- import_local_er1.py  : ECG file import and decompression
- ui_theme.py          : Shared window colors and buttons
- App/                 : Application binaries, Qt libraries, and drivers
- Data/                : Portable patient database, reports, settings, and logs
  - config.ini         : User preferences and settings
  - DATA/              : SQLite database and patient ECG records/reports
========================================================================
