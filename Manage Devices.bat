@echo off
cd /d "%~dp0"
if exist "C:\Python312\pythonw.exe" (
    start "" "C:\Python312\pythonw.exe" manage_devices.py
    exit /b 0
)
if exist "C:\Python312\python.exe" (
    start "" "C:\Python312\python.exe" manage_devices.py
    exit /b 0
)
pythonw manage_devices.py
