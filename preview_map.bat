@echo off
rem ============================================================
rem Songzuo (Song Dynasty Sim) - Basemap & Route Preview
rem Usage: preview_map.bat [--demo]
rem Rebuilds the single-source map data first, then serves it.
rem ============================================================
setlocal
cd /d "%~dp0game"

set "PY=%~dp0game\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

rem ---- Step 1: rebuild map data (basemap + regime layers) ----
echo [Songzuo] Rebuilding map data (basemap + regime layers) ...
"%PY%" build_map_basemap.py
if errorlevel 1 goto RebuildFail
"%PY%" -m content.build_map_geo
if errorlevel 1 goto RebuildFail
goto Launch

:RebuildFail
echo.
echo [Songzuo] ERROR: map data rebuild FAILED - the preview may show stale data.
echo            Run rebuild_map.bat to see the full error output.
pause

:Launch
echo [Songzuo] Launching Map Preview Tool ...
"%PY%" preview_map.py %*

if errorlevel 1 (
    echo.
    echo [Songzuo] Map preview exited with error.
    pause
)
