@echo off
title PowerTrader AI - Install Dependencies
cd /d "%~dp0"

echo ============================================
echo   PowerTrader AI - Dependency Installer
echo ============================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python was not found on your system!
    echo Please install Python 3.10+ from:
    echo https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo Found Python:
python --version
echo.

echo Upgrading pip...
python -m pip install --upgrade pip
echo.

echo Installing required packages...
python -m pip install -r requirements.txt
echo.

if %errorlevel% equ 0 (
    echo ============================================
    echo   All dependencies installed successfully!
    echo   You can now run PowerTrader.bat
    echo ============================================
) else (
    echo ============================================
    echo   Some packages failed to install.
    echo   Try running this file as Administrator.
    echo ============================================
)
echo.
pause
