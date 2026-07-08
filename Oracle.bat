@echo off
REM Oracle — one front door. Picks Solo RPG / Wargame / Birthright.
REM Keep this console open while playing: it is currently the only error log.
cd /d "%~dp0"
python -m oracle.gui.mode_picker
pause
