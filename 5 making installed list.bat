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


REM Get installed list
python -m pip freeze > ./installed0.txt
rem python -m pip list > ./installed.txt
rem for /f "tokens=1 delims==" %%A in ('python -m pip freeze') do (
rem 	echo %%A>> requirements.txt
rem ) > requirements.txt
@echo off
(
    for /f "tokens=1 delims==" %%A in ('python -m pip freeze') do (
        echo %%A
    )
) > requirements0.txt

	pause
