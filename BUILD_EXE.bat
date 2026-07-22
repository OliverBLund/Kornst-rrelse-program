@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ==========================================
echo Grain Size Analysis - Build Script
echo ==========================================
echo.

REM Read the release identity from the same source used by the application UI.
python --version >NUL 2>&1
if ERRORLEVEL 1 (
    echo ERROR: Python 3 is not installed or not in PATH.
    pause
    exit /b 1
)
for /f "usebackq delims=" %%v in (`python -c "import sys; sys.path.insert(0, 'Program'); from version import VERSION; print(VERSION)"`) do set "APP_VERSION=%%v"
if "%~1"=="" (set "VERSION=!APP_VERSION!") else (set "VERSION=%~1")
if /i not "!VERSION!"=="!APP_VERSION!" (
    echo ERROR: Requested build version !VERSION! does not match Program/version.py ^(!APP_VERSION!^).
    echo Update Program/version.py and the release communication before building a different version.
    pause
    exit /b 1
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
echo   1. Single File (one .exe, but startup is silent while it extracts)
echo   2. Folder (recommended UX; fast startup and immediate progress splash)
echo.
set /p BUILD_MODE="Select mode (1 or 2) [default: 2]: "
if "!BUILD_MODE!"=="" set BUILD_MODE=2

REM Use a short release path to avoid MAX_PATH and OneDrive sync issues
set BASE_RELEASE_DIR=C:\gsa_build
if not exist "%BASE_RELEASE_DIR%" mkdir "%BASE_RELEASE_DIR%"
set RELEASE_DIR=%BASE_RELEASE_DIR%\%VERSION%
set APP_NAME=GrainSizeAnalysis
set CONTENTS_DIR=r
set ENTRY_SCRIPT=Program\main.py

echo Build Configuration:
echo   Version: %VERSION%
echo   Output:  %RELEASE_DIR%
echo   App:     %APP_NAME%
echo.

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
    python -m pip install "PyInstaller>=6.0.0"

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
        python -m pip install "PyInstaller>=6.0.0"
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

echo Verifying pinned Qt runtime...
"%PYTHON_CMD%" -c "from importlib import metadata; from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR; expected={'PyQt6':'6.9.1','PyQt6-Qt6':'6.9.1','PyQt6-sip':'13.10.2','PyQt6-WebEngine':'6.9.0','PyQt6-WebEngine-Qt6':'6.9.2'}; installed={name: metadata.version(name) for name in expected}; print('Qt runtime:', QT_VERSION_STR, 'PyQt:', PYQT_VERSION_STR); bad={k:(v, installed[k]) for k,v in expected.items() if not installed[k] == v}; assert QT_VERSION_STR == '6.9.0' and PYQT_VERSION_STR == '6.9.1' and not bad, f'Unexpected PyQt stack: {bad}'"
if ERRORLEVEL 1 (
    echo ERROR: The active Python environment does not match the pinned Qt versions.
    echo        Rebuild with option 2 ^(clean virtual environment^) or reinstall requirements.txt.
    pause
    exit /b 1
)
echo Qt runtime verified.
echo.

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

"%PYTHON_CMD%" "%PROJECT_DIR%\Program\build_version_info.py" --version "%VERSION%" --output "%TEMP_BUILD_DIR%\version_info.txt"
if ERRORLEVEL 1 (
    echo ERROR: Could not generate Windows executable version metadata.
    pause
    exit /b 1
)

REM Set build type based on mode
if "%BUILD_MODE%"=="1" (
    set BUILD_TYPE=--onefile
    set DIST_SUBDIR=
    set EXTRA_LAYOUT_FLAGS=
) else (
    set BUILD_TYPE=--onedir
    set DIST_SUBDIR=\%APP_NAME%
    set EXTRA_LAYOUT_FLAGS=--contents-directory %CONTENTS_DIR%
)

%PYTHON_CMD% -m PyInstaller ^
    "%PROJECT_DIR%\%ENTRY_SCRIPT%" ^
    --name "%APP_NAME%" ^
    --distpath "%TEMP_BUILD_DIR%" ^
    --workpath "%TEMP_BUILD_DIR%\build" ^
    --specpath "%TEMP_BUILD_DIR%" ^
    %BUILD_TYPE% ^
    %EXTRA_LAYOUT_FLAGS% ^
    --noconsole ^
    --noconfirm ^
    --version-file "%TEMP_BUILD_DIR%\version_info.txt" ^
    --icon "%PROJECT_DIR%\Program\resources\app_icon.ico" ^
    --paths "%PROJECT_DIR%\Program" ^
    --add-data "%PROJECT_DIR%\Program\CHANGELOG.md;Program" ^
    --add-data "%PROJECT_DIR%\Program\help_content;Program\help_content" ^
    --add-data "%PROJECT_DIR%\Program\resources;Program\resources" ^
    --add-data "%PROJECT_DIR%\docs;docs" ^
    --add-data "%PROJECT_DIR%\test_data;Program\test_data" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "xlrd" ^
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
        robocopy "!MPL_STYLE_SRC!" "%RELEASE_DIR%\%APP_NAME%\%CONTENTS_DIR%\matplotlib\mpl-data\stylelib" /E /R:2 /W:2 >nul
    )
    set PACKAGE_PATH=%RELEASE_DIR%\%APP_NAME%
)

echo Files copied to release directory.
echo.

REM Copy release licensing and source-availability documents into the package.
if "%BUILD_MODE%"=="1" (
    set "NOTICE_DIR=%RELEASE_DIR%"
) else (
    set "NOTICE_DIR=%RELEASE_DIR%\%APP_NAME%"
)
for %%f in (README.md COPYING LICENSE THIRD_PARTY_NOTICES.md) do (
    if exist "%PROJECT_DIR%\%%f" copy "%PROJECT_DIR%\%%f" "!NOTICE_DIR!\%%f" >nul
)
(
    echo Grain Size Analysis source code notice
    echo.
    echo This binary release is distributed under the GNU General Public License
    echo version 3 or later ^(GPL-3.0-or-later^).
    echo.
    echo Corresponding source code for this exact installer version must be
    echo published with the release.
    echo.
    echo Repository:
    echo   https://github.com/OliverBLund/Kornst-rrelse-program
    echo.
    echo Expected release/tag for this build:
    echo   https://github.com/OliverBLund/Kornst-rrelse-program/releases/tag/v%VERSION%
    echo.
    echo The full license text is included in COPYING and LICENSE.
) > "!NOTICE_DIR!\SOURCE_CODE_NOTICE.txt"
echo Added release license and source notice files to: !NOTICE_DIR!
echo.

REM Write a short user-facing install note into the release output. Folder-based
REM PyInstaller builds contain deep Qt/WebEngine runtime paths, so extracting
REM them under long OneDrive/SharePoint/project folders can exceed Windows path
REM limits before the app starts.
if "%BUILD_MODE%"=="1" (
    set "README_TARGET=%RELEASE_DIR%\README_FIRST.txt"
) else (
    set "README_TARGET=%RELEASE_DIR%\%APP_NAME%\README_FIRST.txt"
)
(
    echo Grain Size Analysis - install note
    echo.
    echo Recommended location:
    echo   C:\GSA
    echo   C:\Tools\GSA
    echo.
    echo Avoid extracting or running the app from deeply nested OneDrive,
    echo SharePoint, Desktop, or project folders. Windows and ZIP tools may
    echo fail when the full path becomes too long, especially for folder-based
    echo builds that include Qt runtime files.
    echo.
    echo If the app does not start after extraction, move the entire app folder
    echo or executable to a short local path and run it again.
) > "!README_TARGET!"
echo Added install note: !README_TARGET!
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
    echo Use this only when a single portable file is required.
    echo NOTE: The app progress splash cannot appear until extraction finishes.
) else (
    echo Folder-based build created - FAST startup ~2s!
    echo Recommended release mode for the immediate progress splash.
    echo Distribute the entire %APP_NAME% folder.
    echo Optional installer experiment: BUILD_INSTALLER.bat %VERSION%
    echo IMPORTANT: Ask users to extract it to a short local path such as C:\GSA.
)
echo.
pause
