@echo off
REM LabIndex Launcher
REM Activates the plethapp conda environment and runs the application

echo Starting LabIndex...

REM Activate conda environment
call conda activate plethapp

REM Change to the script directory
cd /d "%~dp0"

REM Run the application
python run.py

REM Keep window open if there's an error
if errorlevel 1 pause
