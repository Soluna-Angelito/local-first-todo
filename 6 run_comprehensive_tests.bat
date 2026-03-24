@echo off
chcp 65001 >nul
title Soy Lunita - Comprehensive Test Suite
echo.
echo  #############################################
echo  #   Soy Lunita - Comprehensive Test Suite   #
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

REM Ensure src-layout package imports work
set PYTHONPATH=%CD%\src;%PYTHONPATH%

REM Set UTF-8 encoding for Python
set PYTHONIOENCODING=utf-8

REM Check for verbose flag
if "%1"=="--verbose" (
    set VERBOSE_TESTS=1
    echo  [MODE] Verbose output enabled
) else if "%1"=="-v" (
    set VERBOSE_TESTS=1
    echo  [MODE] Verbose output enabled
) else (
    set VERBOSE_TESTS=0
    echo  [MODE] Compact output (use --verbose for detailed)
)

echo.

REM Run pytest (conftest.py handles the output formatting)
python -m pytest tests/test_comprehensive.py -s --tb=no -q

set EXIT_CODE=%ERRORLEVEL%

pause
exit /b %EXIT_CODE%
