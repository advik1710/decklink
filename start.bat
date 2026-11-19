@echo off
cd /d "%~dp0"
python host.py
if errorlevel 1 (
  echo.
  echo DeckLink stopped with an error. Check that Python 3 is installed.
  pause
)
