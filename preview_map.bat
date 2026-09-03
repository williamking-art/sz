@echo off
chcp 65001 >nul
title 宋祚 · 舆图预览
cd /d "%~dp0game"

set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.14.3\python.exe"
if not exist "%PY%" set "PY=python"
set "PYTHONUTF8=1"

echo ============================================
echo   宋祚 · 舆图预览
echo   直接回车 = 普通预览；输入 demo 回车 = 燕云归宋演示
echo ============================================
set "ARGS="
set /p "IN=> " || set "IN="
if /i "%IN%"=="demo" set "ARGS=--demo"

"%PY%" preview_map.py %ARGS%

echo.
echo [宋祚] 预览已退出。
pause
