@echo off
cd /d "%~dp0"
python manager.py
if errorlevel 1 (
  echo.
  echo Could not open DeckLink Desktop Manager. Check that Python with Tkinter is installed.
  pause
)
