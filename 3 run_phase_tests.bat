@echo off
title Soy Lunita - Run Phase Tests
echo.
echo  #############################################
echo  #     Soy Lunita - Run Phase Tests          #
echo  #############################################
echo.

cd /d "%~dp0"

REM Check if venv exists
if not exist ".venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found.
    echo  Please run setup_venv.bat first.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Ensure src-layout package imports work (local_first_todo is under .\src)
set PYTHONPATH=%CD%\src;%PYTHONPATH%

echo  Select test suite:
echo.
echo    [1] Run All Phase Tests (Phases 1-9)
echo    [2] Run API Tests
echo    [3] Run Both
echo.

set /p choice="  Enter choice (1/2/3): "

echo.

if "%choice%"=="1" (
    echo  Running Phase Tests (scripts/run_all_tests.py)...
    echo  ================================================
    echo.
    python scripts/run_all_tests.py
) else if "%choice%"=="2" (
    echo  Running API Tests (scripts/run_api_tests.py)...
    echo  ================================================
    echo.
    python scripts/run_api_tests.py
) else if "%choice%"=="3" (
    echo  Running All Phase Tests...
    echo  ================================================
    echo.
    python scripts/run_all_tests.py
    echo.
    echo  Running API Tests...
    echo  ================================================
    echo.
    python scripts/run_api_tests.py
) else (
    echo  Invalid choice. Please run again and select 1, 2, or 3.
)

echo.
echo  #############################################
echo.
pause
