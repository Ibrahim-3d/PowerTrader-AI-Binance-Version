@echo off
title PowerTrader AI - Trade Executor
cd /d "%~dp0"

echo ============================================
echo   PowerTrader AI - Trade Executor
echo ============================================
echo.
echo   WARNING: This will execute REAL trades
echo   on your Binance account!
echo.
echo   Make sure b_key.txt and b_secret.txt
echo   contain your Binance API credentials.
echo.
echo Press any key to start, or close this window to cancel.
pause >nul
echo.

python pt_trader.py

echo.
echo Trade executor stopped.
pause
