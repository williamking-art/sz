@echo off
rem ============================================================
rem Songzuo (Song Dynasty Sim) - Rebuild Map Data Only
rem Regenerates every GeoJSON under game\assets\map\web from the
rem single source of truth (content\geo_admin.py / content\data.py):
rem   1) build_map_basemap.py  Song circuits + prefectures (117+ blocks)
rem   2) content.build_map_geo regimes + regime prefectures + cities
rem Order matters: the regime layer is clipped against Song land,
rem so the basemap must be rebuilt FIRST.
rem Use this whenever geography/economy tables change and you want
rem to refresh the map without launching the whole client.
rem ============================================================
setlocal
cd /d "%~dp0game"

set "PY=%~dp0game\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [Songzuo] 1/2 Rebuilding basemap (Song circuits + prefectures) ...
"%PY%" build_map_basemap.py
if errorlevel 1 goto Fail

echo [Songzuo] 2/2 Rebuilding regime layers (regimes + regime prefectures) ...
"%PY%" -m content.build_map_geo
if errorlevel 1 goto Fail

echo.
echo [Songzuo] Map data is up to date: game\assets\map\web
echo           Restart the preview (or hard-refresh the browser) to see it.
pause
goto :eof

:Fail
echo.
echo [Songzuo] Rebuild FAILED - see the error above. Map data left unchanged.
pause
