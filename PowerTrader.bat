@echo off
title PowerTrader AI
cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ============================================
    echo   Python was not found on your system!
    echo   Please install Python 3.10+ from:
    echo   https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH"
    echo ============================================
    pause
    exit /b 1
)

:: Check if dependencies are installed by trying a quick import
python -c "import requests, psutil, matplotlib, colorama, binance, kucoin" >nul 2>&1
if %errorlevel% neq 0 (
    echo Dependencies not found. Installing now...
    echo.
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo ============================================
        echo   Failed to install dependencies!
        echo   Try running Install_Dependencies.bat
        echo   as Administrator.
        echo ============================================
        pause
        exit /b 1
    )
    echo.
    echo Dependencies installed successfully!
    echo.
)

echo ============================================
echo   Starting PowerTrader AI Hub...
echo ============================================
echo.
python pt_hub.py
if %errorlevel% neq 0 (
    echo.
    echo PowerTrader AI exited with an error.
    pause
)
