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

REM Ask for clean build option
echo.
echo Build Environment:
echo   1. Use current Python environment (faster build)
echo   2. Create clean virtual environment (smaller .exe, recommended)
echo.
set /p USE_CLEAN_ENV="Select option (1 or 2) [default: 1]: "
if "!USE_CLEAN_ENV!"=="" set USE_CLEAN_ENV=1

REM Ask for build mode
echo.
echo Build Mode:
echo   1. Single File (slower startup ~10s, one .exe file)
echo   2. Folder (fast startup ~2s, multiple files in folder)
echo.
set /p BUILD_MODE="Select mode (1 or 2) [default: 2]: "
if "!BUILD_MODE!"=="" set BUILD_MODE=2

REM Use a short release path to avoid MAX_PATH and OneDrive sync issues
set BASE_RELEASE_DIR=C:\gsa_build
if not exist "%BASE_RELEASE_DIR%" mkdir "%BASE_RELEASE_DIR%"
set RELEASE_DIR=%BASE_RELEASE_DIR%\%VERSION%
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

REM Check if version already exists and try to clean up
if exist "%RELEASE_DIR%\%APP_NAME%" (
    echo.
    echo WARNING: Build folder already exists: %RELEASE_DIR%\%APP_NAME%
    echo This may be from a previous build.
    echo.
    echo Please ensure:
    echo   1. The .exe is NOT running
    echo   2. No File Explorer windows are open in that folder
    echo   3. Close any programs that might be using those files
    echo.
    set /p CONTINUE="Continue and try to overwrite? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        echo Build cancelled.
        pause
        exit /b 0
    )

    echo Attempting to clean up old build folder...
    rmdir /s /q "%RELEASE_DIR%\%APP_NAME%" 2>nul

    REM Check if cleanup succeeded
    if exist "%RELEASE_DIR%\%APP_NAME%" (
        echo.
        echo ERROR: Could not delete old build folder - files may be locked!
        echo Please manually delete: %RELEASE_DIR%\%APP_NAME%
        echo Or use a different version number.
        pause
        exit /b 1
    )
    echo Old build folder cleaned up successfully.
    echo.
)

if exist "%RELEASE_DIR%\%APP_NAME%.exe" (
    echo.
    echo WARNING: Single-file .exe already exists: %RELEASE_DIR%\%APP_NAME%.exe
    echo Attempting to delete...
    del /f "%RELEASE_DIR%\%APP_NAME%.exe" 2>nul
    if exist "%RELEASE_DIR%\%APP_NAME%.exe" (
        echo ERROR: Could not delete old .exe - it may be running!
        echo Please close the program or use a different version number.
        pause
        exit /b 1
    )
    echo.
)

REM Setup build environment
if "%USE_CLEAN_ENV%"=="2" (
    echo [1/5] Creating clean virtual environment...

    REM Create venv OUTSIDE the OneDrive project path to avoid Windows MAX_PATH (260 char)
    REM limits. Nested package paths (e.g. PyQt6\Qt6\qml\QtWebEngine\...) easily exceed
    REM 260 chars when combined with the long OneDrive base path, which causes pip install
    REM to fail with OSError [Errno 2] on files like WebEngineQuickDelegatesQml.qmltypes.
    set VENV_DIR=C:\gsa_venv_%RANDOM%
    echo Venv path: !VENV_DIR!

    REM Remove old venv if exists (also clean up any leftover legacy in-project venv)
    if exist ".build_venv_temp" (
        echo Cleaning up legacy in-project venv...
        rmdir /s /q ".build_venv_temp" 2>nul
    )
    if exist "!VENV_DIR!" (
        echo Cleaning up old venv...
        rmdir /s /q "!VENV_DIR!" 2>nul
    )

    REM Create venv at short absolute path
    python -m venv "!VENV_DIR!"
    if ERRORLEVEL 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )

    echo Installing dependencies from requirements.txt...
    call "!VENV_DIR!\Scripts\activate.bat"
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install PyInstaller>=6.0.0

    if exist "requirements.txt" (
        python -m pip install -r requirements.txt
    ) else (
        echo WARNING: requirements.txt not found!
        pause
    )

    echo Clean environment ready.
    echo.
    set "PYTHON_CMD=!VENV_DIR!\Scripts\python.exe"
) else (
    echo [1/5] Using current Python environment...

    REM Ensure PyInstaller is installed
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
    echo Environment ready.
    echo.
    set PYTHON_CMD=python
)

REM Create release directory
echo [2/5] Creating release directory...
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
echo.

REM Build with PyInstaller
echo [3/5] Building executable...
echo This may take a few minutes...
echo.

REM Use absolute paths to avoid path resolution issues
set PROJECT_DIR=%CD%

REM Use a temporary short build path to avoid Windows MAX_PATH (260 char) issues
REM This is especially important with long OneDrive paths
set TEMP_BUILD_DIR=C:\temp_build_%RANDOM%
echo Building in temporary location to avoid path length issues...
echo Temp path: %TEMP_BUILD_DIR%
echo.

REM Set build type based on mode
if "%BUILD_MODE%"=="1" (
    set BUILD_TYPE=--onefile
    set DIST_SUBDIR=
) else (
    set BUILD_TYPE=--onedir
    set DIST_SUBDIR=\%APP_NAME%
)

%PYTHON_CMD% -m PyInstaller ^
    "%PROJECT_DIR%\%ENTRY_SCRIPT%" ^
    --name "%APP_NAME%" ^
    --distpath "%TEMP_BUILD_DIR%" ^
    --workpath "%TEMP_BUILD_DIR%\build" ^
    --specpath "%TEMP_BUILD_DIR%" ^
    %BUILD_TYPE% ^
    --noconsole ^
    --noconfirm ^
    --paths "%PROJECT_DIR%\Program" ^
    --add-data "%PROJECT_DIR%\Program\help_content;Program\help_content" ^
    --add-data "%PROJECT_DIR%\Program\resources;Program\resources" ^
    --add-data "%PROJECT_DIR%\docs;docs" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --collect-data matplotlib ^
    --hidden-import "matplotlib.backends.backend_qt5agg" ^
    --hidden-import "matplotlib.backends.backend_qtagg" ^
    --collect-all "qtawesome"

if ERRORLEVEL 1 (
    echo.
    echo ERROR: Build failed! See messages above.

    REM Clean up temp directory on failure
    if exist "%TEMP_BUILD_DIR%" (
        rmdir /s /q "%TEMP_BUILD_DIR%" 2>nul
    )

    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo.

REM Copy build output to final location
echo Copying build output to: %RELEASE_DIR%
if "%BUILD_MODE%"=="1" (
    REM Single file mode - copy the .exe
    copy "%TEMP_BUILD_DIR%\%APP_NAME%.exe" "%RELEASE_DIR%\%APP_NAME%.exe" >nul
    set PACKAGE_PATH=%RELEASE_DIR%\%APP_NAME%.exe
) else (
    REM Folder mode - copy the entire folder
    xcopy "%TEMP_BUILD_DIR%\%APP_NAME%" "%RELEASE_DIR%\%APP_NAME%\" /E /I /Y >nul

    REM Ensure matplotlib stylelib (seaborn styles) is present
    for /f "usebackq delims=" %%p in (`%PYTHON_CMD% -c "import matplotlib, pathlib; print(pathlib.Path(matplotlib.get_data_path())/'stylelib')"`) do set "MPL_STYLE_SRC=%%p"
    if defined MPL_STYLE_SRC if exist "!MPL_STYLE_SRC!" (
        robocopy "!MPL_STYLE_SRC!" "%RELEASE_DIR%\%APP_NAME%\_internal\matplotlib\mpl-data\stylelib" /E /R:2 /W:2 >nul
    )
    set PACKAGE_PATH=%RELEASE_DIR%\%APP_NAME%
)

REM Copy spec file for reference
copy "%TEMP_BUILD_DIR%\%APP_NAME%.spec" "%RELEASE_DIR%\%APP_NAME%.spec" >nul 2>&1

echo Files copied to release directory.
echo.

REM Clean up temporary build directory
echo Cleaning up temporary build files...
rmdir /s /q "%TEMP_BUILD_DIR%" 2>nul
echo.

REM Cleanup temporary venv if created
if "%USE_CLEAN_ENV%"=="2" (
    echo [4/5] Cleaning up temporary virtual environment...
    if defined VENV_DIR if exist "!VENV_DIR!" (
        rmdir /s /q "!VENV_DIR!" 2>nul
    )
    REM Also clean up any legacy in-project venv that might be left behind
    if exist ".build_venv_temp" (
        rmdir /s /q ".build_venv_temp" 2>nul
    )
    echo.
)

echo.
echo ==========================================
echo BUILD COMPLETE!
echo ==========================================
echo.
echo Version:     %VERSION%
echo Location:    %PACKAGE_PATH%
echo.
if "%BUILD_MODE%"=="1" (
    echo Single-file executable created.
    echo NOTE: First startup may be slower ~10s as files are extracted.
) else (
    echo Folder-based build created - FAST startup ~2s!
    echo Distribute the entire %APP_NAME% folder.
)
echo.
pause
