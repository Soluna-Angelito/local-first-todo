@echo off
title Soy Lunita - Task Manager Server
echo.
echo  #############################################
echo  #     Soy Lunita - Task Manager Server      #
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

echo  Starting server...
echo  Open http://127.0.0.1:8765 in your browser
echo.
echo  Press Ctrl+C to stop the server
echo.

python -m local_first_todo.main

if "%1"=="--foreground" pause
