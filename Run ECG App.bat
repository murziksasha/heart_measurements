@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (start "" ".venv\Scripts\pythonw.exe" -m ecg_app) else (start "" pythonw -m ecg_app)
