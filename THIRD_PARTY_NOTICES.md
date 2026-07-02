# Third-Party Notices

Grain Size Analysis is distributed under GPL-3.0-or-later. This notice summarizes direct runtime and packaging dependencies declared in requirements.txt and build scripts. It is not a substitute for the full license texts shipped by each upstream project.

## Primary GPL Reason

- PyQt6 6.9.1: GNU GPL v3 or Riverbank Commercial License. This release uses the GPL route.
- PyQt6-WebEngine 6.9.0: GNU GPL v3 or Riverbank Commercial License. This release uses the GPL route.

Because the application links to and bundles PyQt6/PyQt6-WebEngine under the GPL route, the distributed application is licensed as GPL-3.0-or-later and corresponding source code must be published for each binary release.

## Qt Runtime Bundled Through PyQt Wheels

- PyQt6-Qt6 6.9.1: LGPL v3 according to package metadata.
- PyQt6-WebEngine-Qt6 6.9.2: LGPL v3 according to package metadata.

## Direct Python Dependencies

- PyQt6-sip 13.10.2: BSD-2-Clause according to package metadata.
- qtawesome >=1.2.0: MIT according to package metadata. qtawesome provides Font Awesome icon integration; Font Awesome assets have their own upstream notices.
- numpy >=1.24.0: BSD-3-Clause style license; binary wheels may include additional bundled numeric libraries such as OpenBLAS with their own notices.
- pandas >=2.0.0: BSD-3-Clause.
- xlrd >=2.0.1: BSD-style license.
- matplotlib >=3.7.0: Matplotlib license.
- openpyxl >=3.1.0: MIT.
- dataclasses-json >=0.6.0: MIT.
- python-docx >=1.0.0: MIT.

## Packaging Tools

- PyInstaller >=6.0.0: GPL-2.0-or-later with the PyInstaller bootloader exception allowing bundled applications to use different licenses, subject to dependency licenses.
- Inno Setup 6: installer compiler used to create the Windows setup executable. The installer and installed program are separate works; Inno Setup's license permits use for this packaging workflow.

## Python

The application is built with CPython 3.11. Python is distributed under the Python Software Foundation License.

## Project Assets

- DTU_logo.png: DTU visual identity asset. Do not reuse in derivative projects in a way that implies DTU endorsement unless you have permission.
- app_icon.ico and soil layer images: project assets distributed with Grain Size Analysis.

## Source Availability

The source code corresponding to each released installer must be available from the matching release/tag:
https://github.com/OliverBLund/Kornst-rrelse-program
