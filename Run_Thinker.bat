@echo off
title PowerTrader AI - Signal Generator
cd /d "%~dp0"

echo ============================================
echo   PowerTrader AI - Signal Generator
echo ============================================
echo   (Press Ctrl+C to stop)
echo.

python pt_thinker.py

echo.
echo Signal generator stopped.
pause
