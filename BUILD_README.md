# Build Instructions

## Quick Start

To build a new release of Grain Size Analysis:

```batch
BUILD_EXE.bat 1.0.0
```

Replace `1.0.0` with your desired version number.

## What It Does

The build script:

1. **Checks Requirements**: Verifies Python and PyInstaller are installed
2. **Creates Versioned Folder**: Makes a new folder `releases/v1.0.0/`
3. **Builds Executable**: Uses PyInstaller to create the application
4. **Creates ZIP Archive**: Automatically packages everything for distribution

## Output Structure

After building version `1.0.0`, you'll have:

```
releases/
└── v1.0.0/
    ├── dist/
    │   └── GrainSizeAnalysis/          ← The runnable application
    │       ├── GrainSizeAnalysis.exe   ← Main executable
    │       └── (all dependencies)
    ├── build/                          ← Build artifacts (can be ignored)
    ├── GrainSizeAnalysis.spec          ← PyInstaller spec file
    └── GrainSizeAnalysis_v1.0.0.zip    ← Ready for distribution
```

## Distribution

The ZIP file `GrainSizeAnalysis_v1.0.0.zip` contains everything needed to run the application. Simply extract and run `GrainSizeAnalysis.exe`.

## Version Management

- **Each build is isolated**: No conflicts between versions
- **Old versions are preserved**: Previous builds are never deleted
- **No permission issues**: Fresh folders avoid locked files

## Rebuilding a Version

If you need to rebuild an existing version:

```batch
BUILD_EXE.bat 1.0.0
```

You'll be prompted to confirm overwriting the existing build.

## Requirements

- Python 3.8 or newer
- PyInstaller (auto-installed if missing)
- Windows 10 or newer (for ZIP creation via PowerShell)

## Troubleshooting

### "Python 3 is not installed or not in PATH"
Install Python from [python.org](https://www.python.org/) and ensure "Add to PATH" is checked during installation.

### "Entry script not found"
Make sure you're running the script from the project root directory where `Program/main.py` exists.

### ZIP creation fails
The executable is still built successfully in `releases/vX.X.X/dist/GrainSizeAnalysis/`. You can manually zip this folder.

## Previous Build System

The old `build_system/` folder contained a more complex Python-based build system with multiple layers. The new simplified script replaces this with:

- ✅ Single, easy-to-read batch file
- ✅ Version management built-in
- ✅ Automatic archiving
- ✅ No permission conflicts
- ✅ All old versions preserved
