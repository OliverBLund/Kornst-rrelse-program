"""Generate the Windows version resource consumed by PyInstaller."""

from __future__ import annotations

import argparse
from pathlib import Path

from version import VERSION


def version_tuple(value: str) -> tuple[int, int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"Expected a numeric X.Y.Z version, got {value!r}")
    return int(parts[0]), int(parts[1]), int(parts[2]), 0


def render_version_info(value: str = VERSION) -> str:
    numbers = version_tuple(value)
    tuple_text = ", ".join(str(number) for number in numbers)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tuple_text}),
    prodvers=({tuple_text}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'DTU Sustain'),
         StringStruct('FileDescription', 'Grain Size Analysis'),
         StringStruct('FileVersion', '{value}'),
         StringStruct('InternalName', 'GrainSizeAnalysis'),
         StringStruct('LegalCopyright', 'Copyright © 2025-2026 DTU Sustain'),
         StringStruct('OriginalFilename', 'GrainSizeAnalysis.exe'),
         StringStruct('ProductName', 'Grain Size Analysis'),
         StringStruct('ProductVersion', '{value}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)\n"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.version != VERSION:
        parser.error(
            f"requested version {args.version!r} does not match application version {VERSION!r}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_version_info(args.version), encoding="utf-8")


if __name__ == "__main__":
    main()
