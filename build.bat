@echo off
setlocal

echo [Cobra LANs] Installing dependencies...
pip install pyyaml pillow pyinstaller

echo.
echo [Cobra LANs] Building executable...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "Cobra LANs" ^
    --add-data "app;app" ^
    --add-data "config;config" ^
    --collect-submodules app ^
    --collect-submodules config ^
    cobra_lans.py

echo.
if exist "dist\Cobra LANs.exe" (
    echo [Cobra LANs] Build successful: dist\Cobra LANs.exe
) else (
    echo [Cobra LANs] Build FAILED – check output above.
    exit /b 1
)

endlocal
