@echo off
title Soy Lunita - Run Single Test
echo.
echo  #############################################
echo  #   Soy Lunita - Run Single Test/Class      #
echo  #############################################
echo.

cd /d "%~dp0"

if "%~1"=="" (
    echo  Usage: 6b run_single_test.bat [test_name]
    echo.
    echo  Examples:
    echo    6b run_single_test.bat TestTaskAPI
    echo    6b run_single_test.bat test_create_task
    echo.
    pause
    exit /b 1
)

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
set VERBOSE_TESTS=1

echo  [MODE] Running tests matching: %~1
echo.

python -m pytest tests/test_comprehensive.py -s --tb=short -q -k "%~1"

pause
exit /b %ERRORLEVEL%
