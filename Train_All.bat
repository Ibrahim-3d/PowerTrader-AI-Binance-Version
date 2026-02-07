@echo off
title PowerTrader AI - Train All Coins
cd /d "%~dp0"

echo ============================================
echo   PowerTrader AI - Train All Coins
echo ============================================
echo.
echo This will train models for all configured
echo coins sequentially. This can take a while.
echo.
echo Press any key to start, or close this window to cancel.
pause >nul

:: Train BTC (main folder)
echo.
echo [1] Training BTC...
echo ----------------------------------------
python pt_trainer.py BTC
echo.

:: Train each subfolder coin if it exists
for /d %%D in (*) do (
    if exist "%%D\pt_trainer.py" (
        echo [+] Training %%D...
        echo ----------------------------------------
        python "%%D\pt_trainer.py" %%D
        echo.
    )
)

echo ============================================
echo   Training complete for all coins!
echo ============================================
echo.
pause
