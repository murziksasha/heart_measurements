@echo off
title AI-ECG Portable - Import ECG Files
cd /d "%~dp0"
if exist "C:\Python312\pythonw.exe" (
    start "" "C:\Python312\pythonw.exe" import_gui.py --folder
    exit /b 0
)
if exist "C:\Python312\python.exe" (
    start "" "C:\Python312\python.exe" import_gui.py --folder
    exit /b 0
)
python import_gui.py --folder
