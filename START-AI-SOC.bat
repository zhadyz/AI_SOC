@echo off
REM ===================================================================
REM AI-SOC One-Click Launcher
REM ===================================================================
REM Double-click this file to start the AI-SOC Control Center
REM ===================================================================

title AI-SOC Launcher

echo.
echo ========================================================
echo    AI-SOC Control Center - Starting...
echo ========================================================
echo.
echo Checking Python installation...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not installed!
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo Python found!
echo.
echo Installing required packages...
python -m pip install --quiet flask

echo.
echo Launching AI-SOC Control Center...
echo.
python AI-SOC-Launcher.py

pause
