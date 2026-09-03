@echo off
rem Songzuo map preview: game/preview_map.py (pass --demo for the YanYun demo).
rem Prefers the project venv interpreter, falls back to PATH python.
setlocal
cd /d "%~dp0game"

set "PY=%~dp0game\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" preview_map.py %*
