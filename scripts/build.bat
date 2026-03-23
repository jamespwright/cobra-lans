@echo off
setlocal

rem Change to the root directory of the project
cd /d "%~dp0.."

echo [LAN Game Installer] Installing dependencies...
pip install -r app\requirements.txt

echo.
echo [LAN Game Installer] Building executable...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --uac-admin ^
    --name "LAN Game Installer" ^
    --add-data "app/core;core" ^
    --add-data "app/ui;ui" ^
    --collect-submodules app.core ^
    --collect-submodules app.ui ^
    --collect-all numpy ^
    app/lan_game_installer.py

echo.
if exist "dist\LAN Game Installer.exe" (
    echo [LAN Game Installer] Build successful: dist\LAN Game Installer.exe
) else (
    echo [LAN Game Installer] Build FAILED – check output above.
    exit /b 1
)

rem Cleanup build artifacts
rd /s /q build >nul
del /q "LAN Game Installer.spec"
endlocal
