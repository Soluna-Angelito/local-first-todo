@echo off
title Soy Lunita - Fast Tests Only
echo.
echo  #############################################
echo  #   Soy Lunita - Fast Tests (Skip Slow)     #
echo  #############################################
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
set PYTHONPATH=%CD%\src;%PYTHONPATH%
set VERBOSE_TESTS=0

echo  [MODE] Fast tests only (skipping slow)
echo.

python -m pytest tests/test_comprehensive.py -s --tb=no -q -m "not slow"

pause
exit /b %ERRORLEVEL%
