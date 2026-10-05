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
2. The application will launch with a clean patient database and default settings.
3. When you exit, all newly imported ECG recordings, patient records, PDF
   reports, and user configurations are automatically saved inside the "Data"
   folder.

ZERO-TRACE ISOLATION:
- All data stays inside this portable directory.
- No files or records are left behind in the host computer's AppData.
- If the host computer already had an installation of AI-ECG Analysis System,
  the launcher safely preserves and restores the host's existing data upon exit.

DIRECTORY STRUCTURE:
- AI-ECG Portable.exe  : Portable launcher (run this file)
- App/                 : Application binaries, Qt libraries, and drivers
- Data/                : Portable patient database, reports, settings, and logs
  - config.ini         : User preferences and settings
  - DATA/              : SQLite database and patient ECG records/reports
========================================================================
