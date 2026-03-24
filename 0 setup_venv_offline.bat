@echo off
title Soy Lunita - Virtual Environment Setup (Offline)
echo.
echo  #############################################
echo  #    Soy Lunita - Virtual Environment Setup #
echo  #              (Offline Mode)               #
echo  #############################################
echo.

cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Please install Python 3.10+ and try again.
    goto :end
)

echo  [1/4] Creating virtual environment...
if exist ".venv" (
    echo        Virtual environment already exists.
    echo        To recreate, delete .venv folder first.
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to create virtual environment.
        goto :end
    )
    echo        Done.
)

echo.
echo  [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to activate virtual environment.
    goto :end
)
echo        Done.

echo.
echo  [3/4] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo        Done.

echo.
echo  [4/4] Installing dependencies from offline wheels...
pip install --no-index --find-links ./offline_wheels -r requirements-dev.txt --quiet
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install dev dependencies.
    echo  Trying with main dependencies only...
    pip install --no-index --find-links ./offline_wheels -r requirements.txt --quiet
)
echo        Done.

echo.
echo  #############################################
echo  #         Setup Complete!                   #
echo  #############################################
echo.
echo  Virtual environment created at: .venv
echo.
echo  Available commands:
echo    - run_server.bat      : Start the server
echo    - stop_server.bat     : Stop the server
echo    - run_tests.bat       : Run pytest tests
echo    - run_phase_tests.bat : Run phase integration tests
echo.
echo  To activate venv manually in cmd:
echo    .venv\Scripts\activate.bat
echo.
echo  To activate venv manually in PowerShell:
echo    .venv\Scripts\Activate.ps1
echo.

:end
pause
