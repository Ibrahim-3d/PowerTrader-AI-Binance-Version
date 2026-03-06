@echo off
REM PowerTrader AI+ Launcher Script
REM This ensures the virtual environment is used

echo Starting PowerTraderAI+...
echo Using virtual environment...

REM Change to the PowerTrader directory
cd /d "%~dp0"

REM Activate virtual environment and run PowerTrader
.venv\Scripts\python.exe app\pt_hub.py

pause