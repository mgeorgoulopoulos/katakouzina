@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    call setup.bat
    if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -c "import tkinter, networkx, numpy" >nul 2>&1
if errorlevel 1 (
    echo Dependencies are missing. Run setup.bat to repair the environment.
    pause
    exit /b 1
)
if not exist logs mkdir logs
set "PYTHONPATH=%~dp0src"
".venv\Scripts\python.exe" -m katakouzina 1>>"logs\startup.log" 2>&1
if errorlevel 1 (
    echo Katakouzina failed to start or stopped unexpectedly.
    type "logs\startup.log"
    echo Full startup output is saved in logs\startup.log.
    pause
    exit /b 1
)
exit /b 0
