@echo off
REM Birthright Campaign Manager Launcher
REM Launch the GUI application for Birthright D&D campaigns

cd /d "%~dp0"

REM Check if dependencies are installed
python -c "import dearpygui" 2>nul
if errorlevel 1 (
    echo Installing GUI dependencies...
    pip install dearpygui>=1.9
)

REM Launch the application
python -m oracle.gui.launcher
