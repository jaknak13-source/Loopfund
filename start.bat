@echo off
REM loopfund: one command to set everything up and launch the dashboard.
REM Double-click this file, or run it from a terminal.
REM   start.bat            install on first run, then start the dashboard
REM   start.bat cycle      run a single research/decision cycle
REM   start.bat status     print the current portfolio snapshot
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- pick a Python (3.11+) ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo Python 3.11+ is required. Get it from https://www.python.org/downloads/
  echo During install, tick "Add Python to PATH". Then run this again.
  pause
  exit /b 1
)

REM --- install on first run (or if dependencies are missing) ---
if not exist ".venv\Scripts\python.exe" (
  echo [setup] creating virtual environment...
  %PY% -m venv .venv
)
".venv\Scripts\python.exe" -c "import fastapi, yfinance, pydantic, uvicorn" 1>nul 2>nul
if errorlevel 1 (
  echo [setup] installing dependencies...
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r scripts\requirements.txt
  if errorlevel 1 ( echo ERROR: failed to install dependencies. & pause & exit /b 1 )
)

REM --- build the dashboard if missing and Node is available ---
if not exist "dashboard\web\dist\index.html" (
  where npm >nul 2>nul
  if not errorlevel 1 (
    pushd dashboard\web
    call npm install
    call npm run build
    popd
  )
)

REM --- first-run config ---
if not exist ".env" copy ".env.example" ".env" >nul

set "PYTHONPATH=%cd%"

REM --- default to starting the dashboard; pass through any CLI subcommand ---
if "%~1"=="" (
  ".venv\Scripts\python.exe" scripts\run.py serve
) else (
  ".venv\Scripts\python.exe" scripts\run.py %*
)
endlocal
