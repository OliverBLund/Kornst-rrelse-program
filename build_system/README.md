# Developer Build Helper

This folder contains a simplified PyInstaller helper for local Grain Size Analysis development builds.

Run `build.bat` or `python build.py --mode gui` from this folder. The helper reads the application identity from `Program/version.py` and embeds matching Windows executable metadata.

This is not the release packaging route. For a versioned folder build and the supported Inno Setup installer, use these commands from the repository root:

```batch
BUILD_EXE.bat 0.9.7
BUILD_INSTALLER.bat 0.9.7
```

Both release scripts reject a version that differs from `Program/version.py`. The `installer.nsi` file remains only for legacy local testing and must not be used for a published release.
