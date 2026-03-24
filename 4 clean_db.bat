@echo off
setlocal EnableDelayedExpansion

title Soy Lunita - Database Cleanup
echo.
echo  #############################################
echo  #       Soy Lunita - Database Cleanup       #
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

echo  Database Cleanup Options:
echo.
echo    [1] Show Statistics
echo    [2] Remove Soft-Deleted Tasks
echo    [3] Clean Orphaned Attachments
echo    [4] Vacuum Database (reclaim space)
echo    [5] Clean Undo Log (keep 500 entries)
echo    [6] Fix Sort Order (fix gaps/inconsistencies)
echo    [7] Full Maintenance (2+3+4+5+6)
echo    [8] Reset Database (WARNING: Deletes all data!)
echo.

set /p choice="  Enter choice (1-8): "

echo.

if "%choice%"=="1" (
    python scripts/clean_db.py --stats --verbose
) else if "%choice%"=="2" (
    python scripts/clean_db.py --soft-deleted --verbose
) else if "%choice%"=="3" (
    python scripts/clean_db.py --orphaned --verbose
) else if "%choice%"=="4" (
    python scripts/clean_db.py --vacuum --verbose
) else if "%choice%"=="5" (
    python scripts/clean_db.py --undo-log 500 --verbose
) else if "%choice%"=="6" (
    python scripts/clean_db.py --fix-sort-order --verbose
) else if "%choice%"=="7" (
    echo  Running full maintenance...
    python scripts/clean_db.py --soft-deleted --orphaned --undo-log 500 --fix-sort-order --vacuum --verbose
) else if "%choice%"=="8" (
    echo  Resetting Database...
    python scripts/clean_db.py --reset
) else (
    echo  Invalid choice.
)

echo.
echo  #############################################
echo.
pause
