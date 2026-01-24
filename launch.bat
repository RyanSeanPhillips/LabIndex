@echo off
REM LabIndex Launcher
REM Activates the plethapp conda environment and runs the application

echo Starting LabIndex...
echo.

REM Activate conda environment
call conda activate plethapp

REM Change to the script directory
cd /d "%~dp0"

REM Run the application
python run.py

REM Always pause so we can see any error messages
echo.
echo Application exited.
pause
