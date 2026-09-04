@echo off
rem ============================================================
rem Songzuo (Song Dynasty Sim) - Basemap & Route Preview
rem Usage: preview_map.bat [--demo]
rem ============================================================
setlocal
cd /d "%~dp0game"

set "PY=%~dp0game\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [Songzuo] Launching Map Preview Tool ...
"%PY%" preview_map.py %*

if errorlevel 1 (
    echo.
    echo [Songzuo] Map preview exited with error.
    pause
)
