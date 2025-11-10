@echo off
setlocal
REM Quick launcher for the Grain Size Analysis build system

echo ==========================================
echo Grain Size Analysis - Build Launcher
echo ==========================================
echo.

if not exist "build_system" (
    echo ERROR: build_system folder not found!
    echo Make sure you are running this from the project root.
    pause
    exit /b 1
)

echo Opening build menu...
echo.

pushd build_system
call build.bat
set BUILD_ERROR=%ERRORLEVEL%
popd

if NOT "%BUILD_ERROR%"=="0" (
    echo.
    echo Build encountered an error! (code %BUILD_ERROR%)
    pause
    exit /b %BUILD_ERROR%
)

echo.
echo Build workflow completed.
pause
