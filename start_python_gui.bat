@echo off
rem ============================================================
rem Songzuo (Song Dynasty Sim) - Pure Python GUI Launcher
rem Zero Node.js dependencies. Runs instantly via project venv.
rem ============================================================
setlocal
cd /d "%~dp0game"

set "PY=%~dp0game\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [Songzuo] Launching Pure Python Desktop GUI (gui_main.py) ...
"%PY%" gui_main.py %*

if errorlevel 1 (
    echo.
    echo [Songzuo] Python GUI exited with error code %errorlevel%.
    pause
)
