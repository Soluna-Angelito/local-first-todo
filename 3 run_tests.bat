@echo off
title Soy Lunita - Run Tests (pytest)
echo.
echo  #############################################
echo  #       Soy Lunita - Run Tests (pytest)     #
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

echo  Running pytest tests...
echo.

REM Check for command line arguments
if "%~1"=="" (
    REM No arguments - run all tests with coverage
    pytest --cov=local_first_todo --cov-report=term-missing -v
) else if "%~1"=="fast" (
    REM Fast tests only (exclude slow, perf, fuzz, browser)
    echo  Running fast tests only...
    pytest -m "not slow and not perf and not fuzz and not browser" -v
) else if "%~1"=="api" (
    REM API tests only
    echo  Running API tests only...
    pytest tests/api/ -v
) else if "%~1"=="db" (
    REM Database tests only
    echo  Running database tests only...
    pytest tests/database/ -v
) else if "%~1"=="e2e" (
    REM E2E tests only
    echo  Running E2E tests only...
    pytest tests/e2e/ -v
) else if "%~1"=="services" (
    REM Service tests only
    echo  Running service tests only...
    pytest tests/services/ -v
) else (
    REM Pass arguments directly to pytest
    pytest %*
)

echo.
echo  #############################################
echo.
echo  Usage:
echo    run_tests.bat           - Run all tests with coverage
echo    run_tests.bat fast      - Run fast tests only
echo    run_tests.bat api       - Run API tests only
echo    run_tests.bat db        - Run database tests only
echo    run_tests.bat e2e       - Run E2E tests only
echo    run_tests.bat services  - Run service tests only
echo    run_tests.bat [args]    - Pass custom args to pytest
echo.
pause
