@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
if exist "%USERPROFILE%\.pyenv\pyenv-win\versions\3.11.9\python.exe" (
    "%USERPROFILE%\.pyenv\pyenv-win\versions\3.11.9\python.exe" -m venv .venv
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
)
if not exist ".venv\Scripts\python.exe" goto failed
:install
".venv\Scripts\python.exe" -m pip --isolated install --index-url https://pypi.org/simple -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import tkinter, networkx, numpy"
if errorlevel 1 goto failed
echo Setup complete. Double-click launch.bat.
exit /b 0
:failed
echo Setup failed. Install Python 3.11 or newer with Tcl/Tk, then run setup.bat again.
pause
exit /b 1
