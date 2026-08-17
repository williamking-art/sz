@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 准备合并 songzuo 与 game...
where python >nul 2>nul
if %errorlevel%==0 (
    python merge_songzuo_game.py
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py merge_songzuo_game.py
    ) else (
        echo [ERROR] 未找到 Python，请先安装 Python 并加入 PATH。
        pause
        exit /b 1
    )
)
pause
