@echo off
setlocal

rem Change to the root directory of the project
cd /d "app"

set VENV_DIR=.venv

rem Create venv if it doesn't exist
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [Cobra LANs] Creating virtual environment...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [Cobra LANs] Failed to create virtual environment.
        exit /b 1
    )
)

rem Activate venv
call "%VENV_DIR%\Scripts\activate.bat"

rem Install/sync dependencies
echo [Cobra LANs] Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [Cobra LANs] Failed to install dependencies.
    exit /b 1
)

rem Launch the app
echo [Cobra LANs] Starting app...
python cobra_lans.py %*

endlocal
