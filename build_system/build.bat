@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ==========================================
echo Grain Size Analysis Build System
echo ==========================================
echo.

REM Check if Python is available
python --version >NUL 2>&1
if ERRORLEVEL 1 (
    echo ERROR: Python 3 is not installed or not accessible via PATH.
    echo Please install Python 3.8 or newer and ensure it is available from the command line.
    pause
    exit /b 1
)

:menu
echo Build Options:
echo   1. Build GUI version (fast start, no console)
echo   2. Build with console (debug-friendly)
echo   3. Build single-file GUI executable
echo   4. Build single-file executable with console
echo   5. Clean build artefacts
echo   6. Install / update Python dependencies
echo   7. Exit
echo.

set /p CHOICE=Select option (1-7):
echo.

if "%CHOICE%"=="1" (
    python build.py --mode gui
    goto :done
) else if "%CHOICE%"=="2" (
    python build.py --mode dev
    goto :done
) else if "%CHOICE%"=="3" (
    python build.py --mode gui --onefile
    goto :done
) else if "%CHOICE%"=="4" (
    python build.py --mode dev --onefile
    goto :done
) else if "%CHOICE%"=="5" (
    python build.py --clean-only
    goto :done
) else if "%CHOICE%"=="6" (
    python build.py --install-deps
    goto :done
) else if "%CHOICE%"=="7" (
    goto :eof
) else (
    echo Invalid option. Please choose a number between 1 and 7.
    echo.
    goto :menu
)

:done
if ERRORLEVEL 1 (
    echo.
    echo Build command reported an error. See messages above.
) else (
    echo.
    echo Command completed successfully.
)
echo.
pause
