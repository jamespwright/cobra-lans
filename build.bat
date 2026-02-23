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
    --collect-submodules app ^
    cobra_lans.py

echo.
if exist "dist\Cobra LANs.exe" (
    echo [Cobra LANs] Build successful: dist\Cobra LANs.exe
) else (
    echo [Cobra LANs] Build FAILED – check output above.
    exit /b 1
)
    
rem Copy external config/games.yaml into the distribution folder so it sits
rem alongside the executable in dist\config\games.yaml
if exist "dist\Cobra LANs.exe" (
    if exist "config\games.yaml" (
        if not exist "dist\config" mkdir "dist\config"
        copy /Y "config\games.yaml" "dist\config\games.yaml" >nul
        if %ERRORLEVEL% EQU 0 (
            echo [Cobra LANs] Copied config\games.yaml to dist\config\games.yaml
        ) else (
            echo [Cobra LANs] Warning: failed to copy config\games.yaml
        )
    ) else (
        echo [Cobra LANs] Note: config\games.yaml not found locally; skipping copy.
    )
)
endlocal
