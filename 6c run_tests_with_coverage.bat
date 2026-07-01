@echo off
title Soy Lunita - Tests with Coverage
echo.
echo  #############################################
echo  #   Soy Lunita - Tests with Coverage        #
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

REM Force UTF-8 output: conftest.py prints unicode symbols that crash
REM under legacy console codepages (e.g. cp949 on Korean Windows)
set PYTHONUTF8=1
set VERBOSE_TESTS=0

echo  [MODE] Running with coverage (this takes longer)
echo.

python -m pytest tests/test_comprehensive.py -s --tb=no -q --cov=src/local_first_todo --cov-report=term-missing --cov-report=html

echo.
echo  Coverage report: htmlcov\index.html
echo.

pause
exit /b %ERRORLEVEL%
