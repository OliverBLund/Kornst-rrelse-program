@echo off
echo ==========================================
echo COMPLETE BUILD CLEANUP
echo ==========================================
echo.
echo Cleaning PyInstaller cache...
if exist "%LOCALAPPDATA%\pyinstaller" (
  rmdir /s /q "%LOCALAPPDATA%\pyinstaller"
)
echo Cleaning build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "releases" rmdir /s /q "releases"
if exist ".build_venv_temp" rmdir /s /q ".build_venv_temp"
echo Cleaning spec files...
del /f /q *.spec 2>nul
echo Cleaning Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
echo.
echo ==========================================
echo CLEANUP COMPLETE!
echo ==========================================
echo.
echo Now you can run BUILD_EXE.bat to create a fresh build.
echo.
pause
