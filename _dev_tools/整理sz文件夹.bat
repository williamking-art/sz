@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 整理 G:\sz 目录：将开发用文件移入 _dev_tools...
where python >nul 2>nul
if %errorlevel%==0 (
    python organize_sz.py
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py organize_sz.py
    ) else (
        echo [ERROR] 未找到 Python，请先安装 Python 并加入 PATH。
        pause
        exit /b 1
    )
)
pause
