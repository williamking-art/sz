@echo off
rem ============================================================
rem Songzuo (Song Dynasty Sim) - Universal Smart Launcher
rem Auto-detects / auto-downloads Node, or falls back to Python.
rem Flat goto architecture - no nested parenthesis.
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV_PY=%~dp0game\.venv\Scripts\python.exe"
set "NODE_DIR=%~dp0tools\nodejs"
set "NODE_ZIP=%~dp0tools\node-v20.19.5-win-x64.zip"
set "NODE_URL=https://registry.npmmirror.com/-/binary/node/v20.19.5/node-v20.19.5-win-x64.zip"

rem ---- Step 1: Detect Node ----
if exist "%NODE_DIR%\node.exe" goto FoundNode

where node >nul 2>nul
if not errorlevel 1 goto FoundSystemNode

goto AskDownload

:FoundNode
set "PATH=%NODE_DIR%;%~dp0game\.venv\Scripts;%PATH%"
goto LaunchElectron

:FoundSystemNode
set "PATH=%~dp0game\.venv\Scripts;%PATH%"
goto LaunchElectron

rem ---- Step 2: Ask user about auto-download ----
:AskDownload
echo ============================================================
echo   Songzuo - Universal Smart Launcher
echo ============================================================
echo   Node.js was not detected on this system.
echo   The Electron map client requires Node 20+.
echo.
echo   Options:
echo     1 - Auto-download portable Node 20 and launch Electron
echo         Downloads from npmmirror China mirror, about 30 MB.
echo     2 - Launch Python Backend Server only (port 8080)
echo     3 - Exit
echo ============================================================
set CHOICE=1
set /p CHOICE="Enter choice [1, 2, 3] (default 1): "

if "%CHOICE%"=="2" goto LaunchBackend
if "%CHOICE%"=="3" goto Finished

rem ---- Step 3: Auto-download Node ----
:DownloadNode
echo.
echo [Songzuo] Creating tools directory...
if not exist "%~dp0tools" mkdir "%~dp0tools"

echo [Songzuo] Downloading portable Node 20.19.5 from npmmirror ...
if exist "%NODE_ZIP%" del "%NODE_ZIP%"
curl -L -o "%NODE_ZIP%" "%NODE_URL%"
if errorlevel 1 goto DownloadFail
if not exist "%NODE_ZIP%" goto DownloadFail

echo [Songzuo] Extracting Node ...
powershell -NoProfile -Command "Expand-Archive -Path '%NODE_ZIP%' -DestinationPath '%~dp0tools' -Force"
if errorlevel 1 goto DownloadFail

if exist "%~dp0tools\node-v20.19.5-win-x64" (
    if exist "%NODE_DIR%" rmdir /s /q "%NODE_DIR%"
    ren "%~dp0tools\node-v20.19.5-win-x64" nodejs
)
if not exist "%NODE_DIR%\node.exe" goto DownloadFail

del "%NODE_ZIP%" 2>nul
echo [Songzuo] Node.js installed successfully at tools\nodejs!
goto FoundNode

:DownloadFail
echo.
echo [Songzuo] Auto-download failed. Please install Node 20+ manually.
echo [Songzuo] Falling back to Python Backend Server...
goto LaunchBackend

rem ---- Step 4: Launch Electron with dependencies check ----
:LaunchElectron
cd /d "%~dp0game\frontend"
if exist "node_modules\.bin\electron-vite.cmd" goto RunDev

echo [Songzuo] Installing frontend dependencies, please wait...
call npm install --no-audit --no-fund
if errorlevel 1 goto NpmFail

:RunDev
echo [Songzuo] Launching Songzuo Electron Client...
call npm run dev
if errorlevel 1 goto ElectronFail
goto Finished

:NpmFail
echo.
echo [Songzuo] npm install failed. Check network or proxy settings.
pause
goto Finished

:ElectronFail
echo.
echo [Songzuo] Electron exited with error.
pause
goto Finished

rem ---- Step 5: Python backend only ----
:LaunchBackend
echo.
echo [Songzuo] Launching Python Backend Server on 127.0.0.1:8080...
cd /d "%~dp0game"
if exist "%VENV_PY%" (
    "%VENV_PY%" -m backend.server
) else (
    python -m backend.server
)
if errorlevel 1 pause
goto Finished

:Finished
