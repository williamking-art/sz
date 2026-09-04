@echo off
rem ============================================================
rem Songzuo (Song Dynasty Sim) - Universal Game Launcher
rem Uses flat goto architecture (no nested parenthesis).
rem ============================================================
setlocal
cd /d "%~dp0"

set PY=%~dp0game\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

rem Check bundled node
if exist "%~dp0tools\nodejs\node.exe" goto FoundBundledNode

rem Check system node
where node >nul 2>nul
if not errorlevel 1 goto FoundSystemNode

goto NoNodeFound

:FoundBundledNode
set PATH=%~dp0tools\nodejs;%~dp0game\.venv\Scripts;%PATH%
goto LaunchElectron

:FoundSystemNode
set PATH=%~dp0game\.venv\Scripts;%PATH%
goto LaunchElectron

:LaunchElectron
cd /d "%~dp0game\frontend"
if exist "node_modules\.bin\electron-vite.cmd" goto DoRunDev

echo [Songzuo] Frontend dependencies not found.
echo [Songzuo] Installing npm packages, please wait...
call npm install --no-audit --no-fund
if errorlevel 1 goto NpmInstallFailed

:DoRunDev
echo [Songzuo] Launching Songzuo Electron Client...
call npm run dev
if errorlevel 1 goto ElectronExitError
goto Finished

:NpmInstallFailed
echo.
echo [Songzuo] npm install failed.
echo [Songzuo] Switching to Python GUI...
goto LaunchPython

:ElectronExitError
echo.
echo [Songzuo] Electron exited with code %errorlevel%.
pause
goto Finished

:NoNodeFound
echo ============================================================
echo   Songzuo - Universal Launcher
echo ============================================================
echo   Node.js was not found on this system.
echo   Electron client requires Node 20 or higher.
echo.
echo   Options:
echo     1 - Launch Pure Python GUI (No Node needed, instant play)
echo     2 - Launch Python Backend Server (FastAPI on port 8080)
echo     3 - Exit
echo ============================================================
set CHOICE=1
set /p CHOICE="Enter choice [1, 2, 3] (default 1): "

if "%CHOICE%"=="2" goto LaunchBackend
if "%CHOICE%"=="3" goto Finished

:LaunchPython
echo.
echo [Songzuo] Launching Pure Python Desktop GUI...
cd /d "%~dp0game"
"%PY%" gui_main.py
if errorlevel 1 (
    echo.
    echo [Songzuo] Python GUI stopped with error.
    pause
)
goto Finished

:LaunchBackend
echo.
echo [Songzuo] Launching Backend Server on 127.0.0.1:8080...
cd /d "%~dp0game"
"%PY%" -m backend.server
if errorlevel 1 (
    echo.
    echo [Songzuo] Backend server stopped with error.
    pause
)
goto Finished

:Finished
