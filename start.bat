@echo off
rem Songzuo launcher: Electron frontend dev + auto-spawned Python backend.
rem Backend spawn is handled by the Electron main process (src/main/index.ts).
setlocal
cd /d "%~dp0game\frontend"

rem Prefer bundled Node (tools/nodejs), fallback to PATH
set "NODE_DIR=%~dp0tools\nodejs"
if exist "%NODE_DIR%\node.exe" (
  set "PATH=%NODE_DIR%;%PATH%"
) else (
  where node >nul 2>nul
  if errorlevel 1 (
    echo [start] Node.js not found. Install Node 20+ or place it at tools\nodejs.
    pause
    exit /b 1
  )
)

rem Expose project venv python so the Electron main process can spawn the backend
set "PATH=%~dp0game\.venv\Scripts;%PATH%"

if not exist "node_modules\.bin\electron-vite.cmd" (
  echo [start] Installing frontend dependencies ...
  call npm install --no-audit --no-fund
  if errorlevel 1 (
    echo [start] npm install failed.
    pause
    exit /b 1
  )
)

echo [start] Launching Songzuo (Electron dev) ...
call npm run dev
rem Pause after dev exits so errors stay visible (double-click scenario)
echo [start] Session ended.
pause
