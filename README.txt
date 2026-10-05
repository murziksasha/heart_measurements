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
3. To download from the ER1 device:
   - Connect the ER1 to your computer via USB (appears as a removable drive).
   - In the top toolbar of the application, click the "Download" button
     (arrow pointing down into a tray).
   - Select patient "Grygoriev" and click "OK". The application scans the
     device drive for "R*" recording files, imports them, and prepares them
     for AI Analysis.
4. When you exit, all newly imported ECG recordings, patient records, PDF
   reports, and user configurations are automatically saved inside "Data/".

DEVICE MANAGEMENT (BIND / UNBIND):
- Double-click "Manage Devices.bat" to open the Portable Device Manager.
- You can view all currently bound devices, bind new devices (ER1, ER1-LW,
  ER1-LB, ER2/DuoEK, etc.), unbind unused devices, and re-bind them at any time.

DIRECT FILE IMPORT:
- Double-click "Import ECG.bat" to import any "R*" recording file or folder
  (such as records saved on your computer) directly into the patient database
  without requiring a physical USB connection.

DIRECTORY STRUCTURE:
- AI-ECG Portable.exe  : Portable launcher (run this file)
- Manage Devices.bat   : Device Manager tool (bind/unbind device serial numbers)
- Import ECG.bat       : Direct ECG file importer (imports R* files from any folder)
- App/                 : Application binaries, Qt libraries, and drivers
- Data/                : Portable patient database, reports, settings, and logs
  - config.ini         : User preferences and settings
  - DATA/              : SQLite database and patient ECG records/reports
========================================================================
