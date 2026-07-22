# Build Instructions

## Quick Start

Build a new release from the project root:

```batch
BUILD_EXE.bat 0.9.7
```

The version may be omitted; the script reads `Program/version.py`. If supplied,
it must match that canonical application version.

## Recommended Publish Mode

For the best user experience, choose build mode `2` / `Folder`.
This keeps startup fast, so the program's own PyQt progress splash appears as
soon as possible and can show the real loading stages.

Do not add PyInstaller's static `--splash` for the normal release. It would only
cover the one-file extraction phase, then hand off to the real PyQt splash, which
feels like two separate startup screens.

Use build mode `1` / `Single File` only when a single portable `.exe` is more
important than immediate startup feedback. In one-file mode, the app cannot show
its progress dialog until PyInstaller has finished extracting the runtime.

## Long-Path Rule For Folder Builds

Folder mode is still the right startup choice, but users must extract it to a
short local path.

Recommended locations:

```text
C:\GSA
C:\Tools\GSA
```

Avoid deeply nested OneDrive, SharePoint, Desktop, Downloads subfolders, or
project folders. Folder-based PyInstaller builds include long internal paths such
as Qt QML resources, and Windows ZIP tools can fail once the full extracted path
approaches the classic 260-character limit.

The build script reduces this risk by:

1. Building from a short temporary path.
2. Writing release output to `C:\gsa_build\<version>`.
3. Using a short internal runtime folder named `r`.
4. Adding a `README_FIRST.txt` install note to the release output.

## Output

Folder mode:

```text
C:\gsa_build\0.9.7\
    GrainSizeAnalysis\
        GrainSizeAnalysis.exe
        README_FIRST.txt
        r\                       runtime dependencies
```

Single-file mode:

```text
C:\gsa_build\0.9.7\
    GrainSizeAnalysis.exe
    README_FIRST.txt
```

For folder mode, distribute the entire `GrainSizeAnalysis` folder. Do not move
only the `.exe` out of the folder.


## Windows Installer

A proper Windows installer can package the folder build without losing the fast
startup behavior. The installer copies the app to a controlled short path under
`%LOCALAPPDATA%\Programs\GrainSizeAnalysis`, creates Start Menu shortcuts, and
keeps users away from deep OneDrive extraction paths.
The installer and generated shortcuts use the bundled `r/Program/resources/app_icon.ico` icon from the folder build.

Prerequisite: install Inno Setup 6 from https://jrsoftware.org/isinfo.php.

Build flow:

```batch
BUILD_EXE.bat 0.9.7
BUILD_INSTALLER.bat 0.9.7
```

When `BUILD_EXE.bat` asks for build mode, choose `2` / `Folder`. The installer
helper expects this folder build:

```text
C:\gsa_build\0.9.7\GrainSizeAnalysis\GrainSizeAnalysis.exe
```

The installer output will be:

```text
C:\gsa_build\0.9.7\GrainSizeAnalysis-0.9.7-Setup.exe
```

This is the supported release distribution path. It preserves the immediate
PyQt progress splash and avoids the extraction-path problems of a folder ZIP.

## Licensing Release Checklist

This project currently packages PyQt6 and PyQt6-WebEngine, so public binary releases should use the GPL route unless the project switches toolkit or obtains a commercial PyQt license.

Before publishing an installer:

1. Confirm the copyright holder line in `README.md` with DTU.
2. Commit the exact source code used for the release.
3. Tag the commit, for example `v0.9.7`.
4. Build the folder package with `BUILD_EXE.bat 0.9.7`.
5. Build the installer with `BUILD_INSTALLER.bat 0.9.7`.
6. Publish the installer together with the matching source archive or GitHub release/tag.

The folder package and installer include:

```text
README.md
COPYING
LICENSE
SOURCE_CODE_NOTICE.txt
THIRD_PARTY_NOTICES.md
```

Inno Setup displays `SOURCE_CODE_NOTICE.txt` before installation and `COPYING` as the GPL license text.

## Troubleshooting

### The app does not start after extracting the folder

Move the entire app folder to a short local path such as `C:\GSA` and try again.
This is especially important if the user extracted it inside OneDrive or a long
organization/project directory.

### The progress splash appears late or not at all in single-file mode

That is expected for one-file builds. PyInstaller must extract the runtime before
`Program/main.py` starts, so the PyQt splash cannot exist during that phase. Use
folder mode for the final release if startup feedback matters.

### Python is not installed or not in PATH

Install Python from https://www.python.org/ and enable `Add Python to PATH`.

### The active Qt runtime is rejected

Use build option `2` when prompted for the build environment so the script creates
a clean temporary virtual environment with the pinned dependency versions.
