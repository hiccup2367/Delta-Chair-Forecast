@echo off
REM Chair Forecast launcher for Windows. Double-click to start.
REM First run sets up a private Python environment in the .venv folder (needs internet once).
REM After that it starts in a few seconds and works offline.
cd /d "%~dp0"
title Chair Forecast

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY (
  where python >nul 2>nul && set PY=python
)
if not defined PY (
  echo.
  echo Python 3.10 or newer is needed and was not found.
  echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  echo Then double-click this file again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Setting up for the first time. This takes a few minutes and only happens once.
  %PY% -m venv .venv || goto :fail
)

if not exist ".venv\.installed" (
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
  echo done> ".venv\.installed"
)

".venv\Scripts\python.exe" run.py
goto :eof

:fail
echo.
echo Setup did not finish. Check the internet connection and try again.
echo If it keeps failing, see docs\SETUP.md.
pause
exit /b 1
