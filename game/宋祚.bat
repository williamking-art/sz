@echo off
title Songzuo
cd /d "%~dp0"

set "PYTHONPATH="
set "CODEBUDDY_TOOL_CALL_ID="
set "CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR="

python gui_main.py
if errorlevel 1 (
    echo.
    echo [Failed] see songzuo_runtime.log
    pause
)
