@echo off
rem ============================================================
rem Songzuo (Song Dynasty Sim) - Universal Smart Launcher
rem Launches the Electron client; the client auto-spawns the
rem Python backend at 127.0.0.1:8080 (see frontend/src/main/index.ts).
rem This script:
rem   0) clears CodeBuddy shim env vars (they break the Python child)
rem   1) self-checks runtime deps (pip install -r requirements.txt if missing)
rem   2) detects Node (portable download fallback), then starts Electron
rem Flat goto architecture - no nested parenthesis.
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV_PY=%~dp0game\.venv\Scripts\python.exe"
set "NODE_DIR=%~dp0tools\nodejs"
set "NODE_ZIP=%~dp0tools\node-v20.19.5-win-x64.zip"
set "NODE_URL=https://registry.npmmirror.com/-/binary/node/v20.19.5/node-v20.19.5-win-x64.zip"

rem ---- Step 0: clear CodeBuddy shim env (PYTHONPATH shim breaks backend) ----
set "PYTHONPATH="
set "CODEBUDDY_TOOL_CALL_ID="
set "CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR="
set "PYTHONIOENCODING=utf-8"

rem Electron binary mirror (npmmirror) - used by @electron/get on (re)install.
rem Without it, npm install may skip the ~100MB binary and electron-vite
rem then fails with: Error: Electron uninstall
set "ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/"

rem ---- Step 0b: resolve python interpreter (venv preferred) ----
set "PY_CMD=python"
if exist "%VENV_PY%" set "PY_CMD=%VENV_PY%"

rem ---- Step 1: runtime deps self-check (fastapi/uvicorn/shapely needed) ----
%PY_CMD% -c "import fastapi, uvicorn, requests, rich, shapely" >nul 2>nul
if errorlevel 1 goto InstallDeps
goto RebuildMap

:InstallDeps
echo [Songzuo] Installing runtime deps from game\requirements.txt ...
%PY_CMD% -m pip install -r "%~dp0game\requirements.txt"
if errorlevel 1 goto DepsFail
echo [Songzuo] Runtime deps installed.
goto RebuildMap

rem ---- Step 1b: rebuild single-source map data ----
:RebuildMap
echo [Songzuo] Rebuilding map data (basemap + regime layers) ...
cd /d "%~dp0game"
%PY_CMD% build_map_basemap.py
if errorlevel 1 goto RebuildFail
%PY_CMD% -m content.build_map_geo
if errorlevel 1 goto RebuildFail
cd /d "%~dp0"
goto CheckNode

:RebuildFail
echo.
echo [Songzuo] ERROR: map data rebuild FAILED - the map may show stale data.
echo            Run rebuild_map.bat to see the full error output.
pause
cd /d "%~dp0"
goto CheckNode

:DepsFail
echo.
echo [Songzuo] Dependency install failed (network or proxy?). Install manually:
echo     %PY_CMD% -m pip install -r game\requirements.txt
pause
goto Finished

rem ---- Step 2: Detect Node ----
:CheckNode
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

rem ---- Step 3: Ask user about auto-download ----
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
goto DownloadNode

rem ---- Step 4: Auto-download Node ----
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

rem ---- Step 5: Launch Electron (backend auto-spawned by the client) ----
:LaunchElectron
cd /d "%~dp0game\frontend"
if exist "node_modules\.bin\electron-vite.cmd" goto RunDev

echo [Songzuo] Installing frontend deps (first run, about 3-5 min) ...
call npm install --no-audit --no-fund
if errorlevel 1 goto NpmFail

:RunDev
echo.
echo [Songzuo] Launching Electron client.
echo          Python backend will be spawned automatically at
echo          http://127.0.0.1:8080  (health check: /health)
echo          Keep this window open while playing.
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

rem ---- Step 6: Python backend only ----
:LaunchBackend
echo.
echo [Songzuo] Launching Python Backend Server on 127.0.0.1:8080 ...
echo          Health check: http://127.0.0.1:8080/health
cd /d "%~dp0game"
%PY_CMD% -m backend.server
if errorlevel 1 pause
goto Finished

:Finished
