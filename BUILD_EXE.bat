@echo off
setlocal
REM Quick launcher for the Grain Size Analysis build system

echo ==========================================
echo Grain Size Analysis - Build Launcher
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

if not exist "build_system" (
    echo ERROR: build_system folder not found!
    echo Make sure you are running this from the project root.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "build_system\venv" (
    echo Creating virtual environment...
    python -m venv build_system\venv
    if ERRORLEVEL 1 (
        echo ERROR: Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call build_system\venv\Scripts\activate.bat
if ERRORLEVEL 1 (
    echo ERROR: Failed to activate virtual environment!
    pause
    exit /b 1
)

REM Install/update dependencies
echo Installing/updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r build_system\requirements.txt
if ERRORLEVEL 1 (
    echo ERROR: Failed to install dependencies!
    call build_system\venv\Scripts\deactivate.bat
    pause
    exit /b 1
)
echo.

echo Opening build menu...
echo.

pushd build_system
call build.bat
set BUILD_ERROR=%ERRORLEVEL%
popd

REM Deactivate virtual environment
call build_system\venv\Scripts\deactivate.bat

if NOT "%BUILD_ERROR%"=="0" (
    echo.
    echo Build encountered an error! (code %BUILD_ERROR%)
    pause
    exit /b %BUILD_ERROR%
)

echo.
echo Build workflow completed.
pause
