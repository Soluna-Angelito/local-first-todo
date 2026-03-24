@echo off
title Soy Lunita - Stop Server
echo.
echo  #############################################
echo  #       Soy Lunita - Stopping Server        #
echo  #############################################
echo.

REM Find and kill Python process running on port 8765
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8765" ^| findstr "LISTENING"') do (
    echo  Found server process: PID %%a
    taskkill /PID %%a /F >nul 2>&1
    if %errorlevel% equ 0 (
        echo  Server stopped successfully.
    ) else (
        echo  Could not stop process %%a
    )
)

REM Check if any process was found
netstat -aon | findstr ":8765" | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo  No server process found running on port 8765.
)

echo.
echo  #############################################
echo.
pause
