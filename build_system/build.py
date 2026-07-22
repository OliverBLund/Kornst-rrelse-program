#!/usr/bin/env python3
"""
Simplified build entry point for the Grain Size Analysis project.

The original DataMerger build system was feature-rich but far more complicated
than we need here. This script keeps the useful parts (installing dependencies,
optional console builds, one-file support) and removes the bespoke release
pipeline so that producing a fresh executable is a single command.
"""

from __future__ import annotations

import argparse
import ctypes
from importlib import metadata
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

PROGRAM_DIR = Path(__file__).resolve().parents[1] / "Program"
if str(PROGRAM_DIR) not in sys.path:
    sys.path.insert(0, str(PROGRAM_DIR))

from build_version_info import render_version_info


DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": "GrainSizeAnalysis",
    "entry_script": "../Program/main.py",
    "icon_path": None,
    "dist_dir": "dist",
    "build_dir": "build",
    "spec_dir": "build/spec",
    "contents_dir": "runtime",
    "extra_paths": [
        "../Program"
    ],
    "data": [
        {"source": "../Program/help_content", "target": "Program/help_content"},
        {"source": "../Program/resources", "target": "Program/resources"},
        {"source": "../Program/CHANGELOG.md", "target": "Program"},
        {"source": "../docs", "target": "docs"},
        {"source": "../test_data", "target": "Program/test_data"}
    ],
    "hidden_imports": [
        "xlrd",
        "matplotlib.backends.backend_qt5agg",
        "matplotlib.backends.backend_qtagg"
    ],
    "default_mode": "gui"
}

EXPECTED_QT_PACKAGES: Dict[str, str] = {
    "PyQt6": "6.9.1",
    "PyQt6-Qt6": "6.9.1",
    "PyQt6-sip": "13.10.2",
    "PyQt6-WebEngine": "6.9.0",
    "PyQt6-WebEngine-Qt6": "6.9.2",
}


@dataclass
class BuildResult:
    succeeded: bool
    message: str


class BuildEnvironment:
    """Encapsulates paths, configuration, and helper utilities for the build."""

    def __init__(self, config_filename: str = "build_config.json") -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.project_root = self.base_dir.parent
        self.config_path = self.base_dir / config_filename
        self.config = self._load_config()

    # ------------------------------------------------------------------ #
    # Configuration helpers
    # ------------------------------------------------------------------ #
    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        config = DEFAULT_CONFIG.copy()
        self._write_config(config)
        return config

    def _write_config(self, config: Dict[str, Any]) -> None:
        with self.config_path.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=4)

    # ------------------------------------------------------------------ #
    # Derived paths
    # ------------------------------------------------------------------ #
    @property
    def dist_dir(self) -> Path:
        return self._resolve(self.config.get("dist_dir", "dist"))

    @property
    def build_dir(self) -> Path:
        return self._resolve(self.config.get("build_dir", "build"))

    @property
    def spec_dir(self) -> Path:
        return self._resolve(self.config.get("spec_dir", "."))

    def entry_script(self) -> Path:
        return self._resolve(self.config.get("entry_script", "../Program/main.py"))

    # ------------------------------------------------------------------ #
    # Utility helpers
    # ------------------------------------------------------------------ #
    def _resolve(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        return (self.base_dir / candidate).resolve()

    def _resolve_optional(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None
        return self._resolve(raw_path)

    def _to_cmd_path(self, path: Path) -> str:
        """Return a path representation safe for PyInstaller/Windows."""
        resolved = path.resolve()
        if os.name != "nt":
            return str(resolved)

        path_str = str(resolved)
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            required = kernel32.GetShortPathNameW(path_str, None, 0)
            if required == 0:
                return path_str
            buffer = ctypes.create_unicode_buffer(required)
            result = kernel32.GetShortPathNameW(path_str, buffer, required)
            if result == 0:
                return path_str
            return buffer.value or path_str
        except Exception:
            return path_str

    def _remove_path(self, path: Path) -> None:
        """Remove a file or directory, handling Windows long paths."""
        if not path.exists():
            return

        if path.is_file():
            path.unlink()
        else:
            # On Windows, use extended-length path syntax to handle paths > 260 chars
            if os.name == "nt":
                resolved_path = path.resolve()
                path_str = str(resolved_path)

                # Add \\?\ prefix if not already present and path is long
                if len(path_str) > 200 and not path_str.startswith("\\\\?\\"):
                    # Convert to extended-length path syntax
                    if path_str.startswith("\\\\"):
                        # UNC path: \\server\share -> \\?\UNC\server\share
                        path_str = "\\\\?\\UNC\\" + path_str[2:]
                    else:
                        # Regular path: C:\... -> \\?\C:\...
                        path_str = "\\\\?\\" + path_str

                # Use rmdir /s /q for robustness with long paths and locked files
                try:
                    # Use Windows rmdir command which handles locked files better
                    result = subprocess.run(
                        ["cmd", "/c", "rmdir", "/s", "/q", f'"{path_str}"'],
                        shell=True,
                        capture_output=True,
                        text=True
                    )

                    # If path no longer exists, we're done
                    if not path.exists():
                        return

                    # If path still exists, wait briefly and try shutil with ignore_errors
                    import time
                    time.sleep(0.5)

                    if path.exists():
                        print(f"[WARN] Using fallback removal for {path.name}")
                        shutil.rmtree(path, ignore_errors=True)

                except Exception as e:
                    # If all else fails, use ignore_errors to skip locked files
                    print(f"[WARN] Error removing {path}: {e}")
                    shutil.rmtree(path, ignore_errors=True)
            else:
                shutil.rmtree(path)

    # ------------------------------------------------------------------ #
    # High-level operations
    # ------------------------------------------------------------------ #
    def install_dependencies(self) -> None:
        """Install PyInstaller and runtime requirements listed in requirements.txt."""
        requirements_file = self.base_dir / "requirements.txt"

        if requirements_file.exists():
            print(f"[DEPS] Installing packages from {requirements_file.name} ...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                check=True,
            )
        else:
            print("[DEPS] No requirements.txt found, skipping dependency installation.")

        self._ensure_pyinstaller()
        self._verify_qt_runtime()

    def clean(self, *, remove_spec: bool = True) -> None:
        """Remove PyInstaller output directories and optional spec file."""
        for directory in (self.dist_dir, self.build_dir):
            if directory.exists():
                print(f"[CLEAN] Removing {directory}")
                self._remove_path(directory)

        if remove_spec:
            spec_file = self.spec_dir / f"{self.config['app_name']}.spec"
            if spec_file.exists():
                print(f"[CLEAN] Removing {spec_file.name}")
                spec_file.unlink()

    def build(
        self,
        *,
        console: bool,
        onefile: bool,
        clean_before: bool,
        extra_args: Iterable[str] | None = None,
    ) -> BuildResult:
        """Execute PyInstaller with the configured options."""
        try:
            entry_script = self.entry_script()
        except Exception as exc:  # pragma: no cover - defensive
            return BuildResult(False, f"Failed to resolve entry script: {exc}")

        if not entry_script.exists():
            return BuildResult(False, f"Entry script not found: {entry_script}")

        self._ensure_pyinstaller()
        self._verify_qt_runtime()

        if clean_before:
            self.clean(remove_spec=False)

        # Ensure output directories exist so Windows can resolve short paths.
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.spec_dir.mkdir(parents=True, exist_ok=True)

        version_file = self.build_dir / "version_info.txt"
        version_file.write_text(render_version_info(), encoding="utf-8")

        command: List[str] = [
            sys.executable,
            "-m",
            "PyInstaller",
            self._to_cmd_path(entry_script),
            "--name",
            self.config["app_name"],
            "--distpath",
            self._to_cmd_path(self.dist_dir),
            "--workpath",
            self._to_cmd_path(self.build_dir),
            "--specpath",
            self._to_cmd_path(self.spec_dir),
            "--noconfirm",
            "--version-file",
            self._to_cmd_path(version_file),
        ]

        if clean_before:
            command.append("--clean")

        command.append("--onefile" if onefile else "--onedir")
        command.append("--console" if console else "--noconsole")
        if not onefile:
            contents_dir = str(self.config.get("contents_dir", "")).strip()
            if contents_dir:
                command.extend(["--contents-directory", contents_dir])

        for extra_path in self.config.get("extra_paths", []):
            path = self._resolve(extra_path)
            if path.exists():
                command.extend(["--paths", self._to_cmd_path(path)])
            else:
                print(f"[WARN] Extra path not found, skipping: {path}")

        for mapping in self.config.get("data", []):
            source = self._resolve(mapping["source"])
            if not source.exists():
                print(f"[WARN] Data source missing, skipping: {source}")
                continue

            # Check if this mapping should exclude certain patterns
            exclude_patterns = mapping.get("exclude", [])

            # If there are exclusions and source is a directory, we need special handling
            if exclude_patterns and source.is_dir():
                # For test_data, we want to exclude the 'test' subdirectory with results
                # PyInstaller doesn't support exclude patterns in --add-data, so we skip
                # directories that need filtering and warn the user
                print(f"[INFO] Skipping {source} due to exclude patterns: {exclude_patterns}")
                print(f"       Users can load test data from the repository directly")
                continue

            target = mapping.get("target", ".")
            add_data_arg = f"{self._to_cmd_path(source)}{os.pathsep}{target}"
            command.extend(["--add-data", add_data_arg])

        for hidden in self.config.get("hidden_imports", []):
            command.extend(["--hidden-import", hidden])

        icon_path = self._resolve_optional(self.config.get("icon_path"))
        if icon_path and icon_path.exists():
            command.extend(["--icon", self._to_cmd_path(icon_path)])

        if extra_args:
            command.extend(extra_args)

        print("[BUILD] Running PyInstaller with command:")
        print("         " + " ".join(f'"{arg}"' if " " in arg else arg for arg in command))

        try:
            subprocess.run(command, check=True, cwd=self.base_dir)
        except subprocess.CalledProcessError as exc:
            return BuildResult(False, f"PyInstaller exited with status {exc.returncode}")

        return BuildResult(True, "Build completed successfully.")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_pyinstaller(self) -> None:
        try:
            import PyInstaller  # noqa: F401
        except ImportError:
            print("[DEPS] PyInstaller not found. Installing...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "PyInstaller>=6.0.0"],
                check=True,
            )

    def _verify_qt_runtime(self) -> None:
        """Fail fast if the build environment would bundle an untested Qt stack."""
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

        installed = {
            package: metadata.version(package)
            for package in EXPECTED_QT_PACKAGES
        }
        mismatches = {
            package: {"expected": expected, "installed": installed[package]}
            for package, expected in EXPECTED_QT_PACKAGES.items()
            if installed[package] != expected
        }

        if QT_VERSION_STR != "6.9.0" or PYQT_VERSION_STR != "6.9.1" or mismatches:
            package_details = ", ".join(
                f"{package} expected {values['expected']} but found {values['installed']}"
                for package, values in mismatches.items()
            )
            runtime_details = f"Qt runtime {QT_VERSION_STR}, PyQt {PYQT_VERSION_STR}"
            details = f"{runtime_details}; {package_details}" if package_details else runtime_details
            raise RuntimeError(
                "Unexpected PyQt/Qt build environment. "
                "Install build_system/requirements.txt before packaging. "
                f"{details}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Grain Size Analysis executables.")
    parser.add_argument(
        "--mode",
        choices=("gui", "dev"),
        help="Preset build mode. 'dev' enables the console window.",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Force the console window to remain visible.",
    )
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Force the console window to be hidden.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Bundle everything into a single executable.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip deleting previous dist/build folders before running PyInstaller.",
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Remove build artefacts and exit without running PyInstaller.",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install/upgrade dependencies then exit (unless --run-after-install is provided).",
    )
    parser.add_argument(
        "--run-after-install",
        action="store_true",
        help="When used with --install-deps, continue to the build step afterwards.",
    )
    parser.add_argument(
        "--pyinstaller-arg",
        action="append",
        default=[],
        help="Pass an additional raw argument to PyInstaller (can be used multiple times).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = BuildEnvironment()

    chosen_mode = args.mode or env.config.get("default_mode", "gui")
    console = chosen_mode == "dev"

    if args.console:
        console = True
    if args.no_console:
        console = False

    if args.install_deps:
        env.install_dependencies()
        if not args.run_after_install:
            return

    if args.clean_only:
        env.clean()
        return

    result = env.build(
        console=console,
        onefile=args.onefile,
        clean_before=not args.no_clean,
        extra_args=args.pyinstaller_arg,
    )

    status = "SUCCESS" if result.succeeded else "FAILED"
    print(f"[{status}] {result.message}")
    if not result.succeeded:
        sys.exit(1)


if __name__ == "__main__":
    main()
