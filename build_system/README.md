# DataMerger Build System

This folder contains everything needed to build DataMerger as a Windows executable.

## 📁 Structure

```
build_system/
├── build.py           # Main build script
├── build.bat          # Windows batch launcher
├── DataMerger.spec    # PyInstaller specification
├── build_config.json  # Build configuration
├── requirements.txt   # Python dependencies
├── installer.nsi      # NSIS installer script (generated)
├── dist/             # Output executables (generated)
└── build/            # Temporary build files (generated)
```

## 🚀 Quick Start

### Option 1: Using Batch File (Easiest)
```cmd
cd build_system
build.bat
```
Select option 1 for directory build (recommended)

### Option 2: Using Python Script
```cmd
cd build_system
python build.py
```

## 📋 Prerequisites

1. **Python 3.8+** installed
2. **PyInstaller** (auto-installed by build script)
3. All dependencies from requirements.txt

## ⚙️ Build Options

### Command Line Arguments
```cmd
python build.py [options]

Options:
  --one-file       Build as single .exe file (larger, slower)
  --console        Show console window (for debugging)
  --version X.X.X  Set version number
  --no-clean       Don't clean previous builds
  --no-test        Skip testing the executable
  --no-archive     Don't create ZIP archive
```

### Examples
```cmd
# Standard build
python build.py

# Single file exe
python build.py --one-file

# Debug build with console
python build.py --console

# Quick rebuild without cleaning
python build.py --no-clean --no-test
```

## 📝 Configuration

Edit `build_config.json` to customize:
- App name and version
- Build directories
- One-file vs directory build
- Console visibility
- UPX compression

## 🔧 Troubleshooting

### Common Issues

1. **PyQt5/PyQt6 Conflict**
   - Solution: Uninstall PyQt5 with `pip uninstall PyQt5`

2. **Missing rasterio/GDAL**
   - Solution: Install with `pip install rasterio fiona`

3. **Import errors in exe**
   - Check hiddenimports in DataMerger.spec
   - Add missing modules to the list

4. **Large exe size (>60MB)**
   - Normal for scientific Python apps
   - Use UPX compression (enabled by default)

### Build Takes Too Long?
- First build: 10-15 minutes (normal)
- Subsequent builds: 5-10 minutes
- Use `--no-clean` for faster rebuilds

## 📊 Output

After successful build:
- **Executable**: `dist/DataMerger/DataMerger.exe`
- **Archive**: `DataMerger-1.0.0-[timestamp].zip`
- **Installer script**: `installer.nsi`

## 🔄 Updating Dependencies

1. Update `requirements.txt`
2. Run `pip install -r requirements.txt`
3. Update hiddenimports in `DataMerger.spec` if needed
4. Rebuild

## 📦 Creating Installer

After building, use NSIS to create installer:
1. Install NSIS from https://nsis.sourceforge.io/
2. Right-click `installer.nsi`
3. Select "Compile NSIS Script"

## 🐛 Debug Mode

To debug build issues:
1. Edit `build_config.json`: set `"console": true`
2. Run: `python build.py --console`
3. Check error messages in console window

## 📚 Files Description

- **build.py**: Main orchestrator, handles all build steps
- **build.bat**: Windows-friendly launcher with menu
- **DataMerger.spec**: Tells PyInstaller what to include
- **build_config.json**: User-editable settings
- **requirements.txt**: Python package dependencies

## ✨ Tips

1. Always test the exe after building
2. Keep build_system folder organized
3. Version control the spec and config files
4. Document any custom hiddenimports added
5. Use `--no-clean` during development for speed

## 📜 Build Process Steps

1. Clean previous builds (optional)
2. Install/verify dependencies
3. Update spec file with config
4. Run PyInstaller
5. Test executable (optional)
6. Create installer script
7. Create distribution archive (optional)

---
*Last updated: 2024*