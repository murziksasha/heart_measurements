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
   - In the top toolbar of the application, click the "Import Data" button.
   - A modal will appear giving you 2 options:
     * "From Device": Use when ER1 is connected via USB. The application
       scans the device drive for "R*" recording files.
     * "From Folder": Use to import files copied from the ER1 onto your computer
       (e.g. from "C:\Users\user\Downloads\ER1"). Choose folder, select one or
       multiple recordings with automatic uniqueness checking, and import.
   - Newly imported recordings appear immediately as new rows in the table
     with full functionality (View report, View ECG, Batch analysis).
4. When you exit, all newly imported ECG recordings, patient records, PDF
   reports, and user configurations are automatically saved inside "Data/".

DEVICE MANAGEMENT (BIND / UNBIND):
- Double-click "Manage Devices.bat" to open the Portable Device Manager.
- You can view all currently bound devices, bind new devices (ER1, ER1-LW,
  ER1-LB, ER2/DuoEK, etc.), unbind unused devices, and re-bind them at any time.

DIRECT FILE IMPORT (STANDALONE GUI):
- Double-click "Import ECG.bat" to launch the Folder Import tool directly
  without requiring a physical USB connection.

PATIENT / USER MANAGEMENT:
- Click the "+ ADD" button in the Left Sidebar header next to "User" to create
  a new patient profile.
- Or right-click "All Users" in the sidebar and choose "+ Add User...".
- Or double-click "Manage Users.bat" to view, add, or delete patient profiles.
- When importing ECG files, you can also click "+ Add User" directly inside the
  "Import Data" window.
- Fields match original application: Patient Name (required), Gender, Birthday
  (with live Age computation), E-mail, and Note/Remark.

DIRECTORY STRUCTURE:
- AI-ECG Portable.exe  : Portable launcher (run this file)
- Manage Users.bat     : Patient Manager tool (add/list/manage patient profiles)
- Manage Devices.bat   : Device Manager tool (bind/unbind device serial numbers)
- Import ECG.bat       : Direct ECG file importer (graphical folder importer)
- manage_users.py      : Patient profile management engine & Add User modal
- import_gui.py        : Import GUI dialog (Choice modal & Folder import)
- import_local_er1.py  : Core ECG file import & decompression engine
- App/                 : Application binaries, Qt libraries, and drivers
- Data/                : Portable patient database, reports, settings, and logs
  - config.ini         : User preferences and settings
  - DATA/              : SQLite database and patient ECG records/reports
========================================================================
