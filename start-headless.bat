@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-headless.ps1"
if errorlevel 1 echo Could not start DeckLink. Check that Python is installed and see decklink-error.log.
