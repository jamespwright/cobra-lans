@echo off
setlocal

echo [Cobra LANs] Installing dependencies...
pip install -r requirements.txt

echo.
echo [Cobra LANs] Building executable...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --uac-admin ^
    --name "Cobra LANs" ^
    --add-data "core;core" ^
    --add-data "ui;ui" ^
    --collect-submodules core ^
    --collect-submodules ui ^
    --collect-all numpy ^
    cobra_lans.py

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
