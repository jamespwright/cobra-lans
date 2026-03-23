@echo off
setlocal

rem Change to the root directory of the project
cd /d "app"

set VENV_DIR=.venv

rem Create venv if it doesn't exist
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [LAN Game Installer] Creating virtual environment...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [LAN Game Installer] Failed to create virtual environment.
        exit /b 1
    )
)

rem Activate venv
call "%VENV_DIR%\Scripts\activate.bat"

rem Install/sync dependencies
echo [LAN Game Installer] Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [LAN Game Installer] Failed to install dependencies.
    exit /b 1
)

rem Launch the app
echo [LAN Game Installer] Starting app...
python lan_game_installer.py %*

endlocal
