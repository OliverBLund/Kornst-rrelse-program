@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ==========================================
echo Grain Size Analysis - Build Script
echo ==========================================
echo.

REM Get version number (from parameter or prompt)
if "%~1"=="" (
    echo No version specified. Please enter a version number.
    echo Examples: 1.0.0, 1.2.3, 2.0.0-beta
    echo.
    set /p VERSION="Enter version number: "
    if "!VERSION!"=="" (
        echo ERROR: Version number cannot be empty!
        pause
        exit /b 1
    )
) else (
    set VERSION=%~1
)

REM Ask for build mode
echo.
echo Build Mode:
echo   1. Single File (slower startup ~10s, one .exe file)
echo   2. Folder (fast startup ~2s, multiple files in folder)
echo.
set /p BUILD_MODE="Select mode (1 or 2) [default: 2]: "
if "!BUILD_MODE!"=="" set BUILD_MODE=2

set RELEASE_DIR=releases\%VERSION%
set APP_NAME=GrainSizeAnalysis
set ENTRY_SCRIPT=Program\main.py

echo Build Configuration:
echo   Version: %VERSION%
echo   Output:  %RELEASE_DIR%
echo   App:     %APP_NAME%
echo.

REM Check if Python is available
python --version >NUL 2>&1
if ERRORLEVEL 1 (
    echo ERROR: Python 3 is not installed or not in PATH.
    echo Please install Python 3.8 or newer.
    pause
    exit /b 1
)

REM Check if entry script exists
if not exist "%ENTRY_SCRIPT%" (
    echo ERROR: Entry script not found: %ENTRY_SCRIPT%
    pause
    exit /b 1
)

REM Check if version already exists
if exist "%RELEASE_DIR%\%APP_NAME%.exe" (
    echo.
    echo WARNING: Version %VERSION% already exists!
    echo This will overwrite: %RELEASE_DIR%\%APP_NAME%.exe
    set /p CONTINUE="Continue? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        echo Build cancelled.
        pause
        exit /b 0
    )
    echo.
)

REM Ensure PyInstaller is installed
echo [1/4] Checking PyInstaller...
python -c "import PyInstaller" 2>NUL
if ERRORLEVEL 1 (
    echo PyInstaller not found. Installing...
    python -m pip install PyInstaller>=6.0.0
    if ERRORLEVEL 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)
echo PyInstaller ready.
echo.

REM Create release directory
echo [2/4] Creating release directory...
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
echo.

REM Build with PyInstaller
echo [3/4] Building executable...
echo This may take a few minutes...
echo.

REM Use absolute paths to avoid path resolution issues
set PROJECT_DIR=%CD%

REM Set build type based on mode
if "%BUILD_MODE%"=="1" (
    set BUILD_TYPE=--onefile
    set DIST_SUBDIR=
) else (
    set BUILD_TYPE=--onedir
    set DIST_SUBDIR=\%APP_NAME%
)

python -m PyInstaller ^
    "%PROJECT_DIR%\%ENTRY_SCRIPT%" ^
    --name "%APP_NAME%" ^
    --distpath "%PROJECT_DIR%\%RELEASE_DIR%" ^
    --workpath "%PROJECT_DIR%\%RELEASE_DIR%\build" ^
    --specpath "%PROJECT_DIR%\%RELEASE_DIR%" ^
    %BUILD_TYPE% ^
    --noconsole ^
    --noconfirm ^
    --paths "%PROJECT_DIR%\Program" ^
    --add-data "%PROJECT_DIR%\Program\help_content;Program\help_content" ^
    --add-data "%PROJECT_DIR%\Program\resources;Program\resources" ^
    --add-data "%PROJECT_DIR%\docs;docs" ^
    --hidden-import "matplotlib.backends.backend_qt5agg" ^
    --hidden-import "matplotlib.backends.backend_qtagg"

if ERRORLEVEL 1 (
    echo.
    echo ERROR: Build failed! See messages above.
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo.

REM Create ZIP archive
echo [4/4] Creating ZIP archive...

set ZIP_NAME=%APP_NAME%_%VERSION%.zip
set ZIP_PATH=%RELEASE_DIR%\%ZIP_NAME%

if "%BUILD_MODE%"=="1" (
    set PACKAGE_PATH=%RELEASE_DIR%\%APP_NAME%.exe
) else (
    set PACKAGE_PATH=%RELEASE_DIR%\%APP_NAME%
)

REM Use PowerShell to create ZIP (built into Windows 10+)
powershell -command "Compress-Archive -Path '%PACKAGE_PATH%' -DestinationPath '%ZIP_PATH%' -Force"

if ERRORLEVEL 1 (
    echo WARNING: Failed to create ZIP archive.
    echo You can manually zip: %PACKAGE_PATH%
) else (
    echo ZIP archive created: %ZIP_PATH%
)

echo.
echo ==========================================
echo BUILD COMPLETE!
echo ==========================================
echo.
echo Version:     %VERSION%
echo Location:    %PACKAGE_PATH%
echo Archive:     %ZIP_PATH%
echo.
if "%BUILD_MODE%"=="1" (
    echo Single-file executable created.
    echo NOTE: First startup may be slower ~10s as files are extracted.
) else (
    echo Folder-based build created - FAST startup ~2s!
    echo Distribute the entire %APP_NAME% folder.
)
echo.
echo The ZIP archive is ready for distribution:
echo   %ZIP_PATH%
echo.
pause
