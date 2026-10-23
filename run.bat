@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Install Python 3.9+ from https://www.python.org/downloads/
    echo Remember to enable "tcl/tk and IDLE" during installation.
    pause
    exit /b 1
)
start "" pythonw "%~dp0translator.pyw"
