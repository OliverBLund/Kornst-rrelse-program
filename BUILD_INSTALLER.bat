@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ==========================================
echo Grain Size Analysis - Windows Installer
echo ==========================================
echo.

python --version >NUL 2>&1
if ERRORLEVEL 1 (
    echo ERROR: Python 3 is not installed or not in PATH.
    pause
    exit /b 1
)
for /f "usebackq delims=" %%v in (`python -c "import sys; sys.path.insert(0, 'Program'); from version import VERSION; print(VERSION)"`) do set "APP_VERSION=%%v"
if "%~1"=="" (set "VERSION=!APP_VERSION!") else (set "VERSION=%~1")
if /i not "!VERSION!"=="!APP_VERSION!" (
    echo ERROR: Requested installer version !VERSION! does not match Program/version.py ^(!APP_VERSION!^).
    echo Build and package the canonical application version only.
    pause
    exit /b 1
)

set RELEASE_DIR=C:\gsa_build\%VERSION%
set APP_DIR=%RELEASE_DIR%\GrainSizeAnalysis
set APP_EXE=%APP_DIR%\GrainSizeAnalysis.exe
set SCRIPT=%CD%\installer\GrainSizeAnalysis.iss

if not exist "%APP_EXE%" (
    echo ERROR: Folder build not found:
    echo   %APP_EXE%
    echo.
    echo First run:
    echo   BUILD_EXE.bat %VERSION%
    echo and choose build mode 2 ^(Folder^).
    echo.
    pause
    exit /b 1
)

set ISCC=
for /f "delims=" %%p in ('where ISCC.exe 2^>nul') do (
    set "ISCC=%%p"
    goto :found_iscc
)

if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

:found_iscc
if "%ISCC%"=="" (
    echo ERROR: Inno Setup compiler ^(ISCC.exe^) was not found.
    echo.
    echo Install Inno Setup 6, then rerun this script.
    echo Download: https://jrsoftware.org/isinfo.php
    echo.
    pause
    exit /b 1
)

echo Using Inno Setup:
echo   %ISCC%
echo.
echo Packaging folder build:
echo   %APP_DIR%
echo.

"%ISCC%" ^
    /DAppVersion="%VERSION%" ^
    /DSourceDir="%APP_DIR%" ^
    /DOutputDir="%RELEASE_DIR%" ^
    "%SCRIPT%"

if ERRORLEVEL 1 (
    echo.
    echo ERROR: Installer build failed.
    pause
    exit /b 1
)

echo.
echo Installer created:
echo   %RELEASE_DIR%\GrainSizeAnalysis-%VERSION%-Setup.exe
if exist "%CD%\README.csv" (
    copy /Y "%CD%\README.csv" "%RELEASE_DIR%\README.csv" >nul
    echo Companion metadata CSV:
    echo   %RELEASE_DIR%\README.csv
) else (
    echo WARNING: README.csv companion file was not found in the project root.
)
echo.
pause
