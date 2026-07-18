@echo off
title Virtual Steering — Launcher
color 0B

echo.
echo  ██╗   ██╗██╗██████╗ ████████╗██╗   ██╗ █████╗ ██╗
echo  ██║   ██║██║██╔══██╗╚══██╔══╝██║   ██║██╔══██╗██║
echo  ██║   ██║██║██████╔╝   ██║   ██║   ██║███████║██║
echo  ╚██╗ ██╔╝██║██╔══██╗   ██║   ██║   ██║██╔══██║██║
echo   ╚████╔╝ ██║██║  ██║   ██║   ╚██████╔╝██║  ██║███████╗
echo    ╚═══╝  ╚═╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝
echo  ──────────────────────────────────────────────────────
echo  STEERING
echo  ──────────────────────────────────────────────────────
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [INFO] Checking dependencies...
pip install -r requirements.txt --quiet

echo.
echo [INFO] Starting Virtual Steering...
echo [INFO] Show BOTH hands to the camera to begin!
echo [INFO] Press Q in the camera window to quit.
echo.

:: Run with keyboard output enabled
python main.py %*

echo.
echo [INFO] Virtual Steering has exited.
pause
