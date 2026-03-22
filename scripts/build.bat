@echo off
setlocal

rem Change to the root directory of the project
cd /d "%~dp0.."

echo [Cobra LANs] Installing dependencies...
pip install -r app\requirements.txt

echo.
echo [Cobra LANs] Building executable...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --uac-admin ^
    --name "Cobra LANs" ^
    --add-data "app/core;core" ^
    --add-data "app/ui;ui" ^
    --collect-submodules app.core ^
    --collect-submodules app.ui ^
    --collect-all numpy ^
    app/cobra_lans.py

echo.
if exist "dist\Cobra LANs.exe" (
    echo [Cobra LANs] Build successful: dist\Cobra LANs.exe
) else (
    echo [Cobra LANs] Build FAILED – check output above.
    exit /b 1
)

rem Cleanup build artifacts
rd /s /q build >nul
del /q "cobra_lans.spec"
endlocal
