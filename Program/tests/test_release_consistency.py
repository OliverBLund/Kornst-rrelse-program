"""Release identity and communication must move together."""

from pathlib import Path
import sys


PROGRAM_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PROGRAM_DIR.parent
if str(PROGRAM_DIR) not in sys.path:
    sys.path.insert(0, str(PROGRAM_DIR))

from build_version_info import render_version_info
from version import RELEASE_DATE_ISO, RELEASE_HIGHLIGHTS, VERSION, VERSION_LABEL


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_release_identity_is_final_and_complete():
    assert VERSION == "0.9.7"
    assert VERSION_LABEL == "v0.9.7"
    assert RELEASE_DATE_ISO == "2026-07-22"
    assert len(RELEASE_HIGHLIGHTS) == 5
    assert not any("NDA" in item or "unfinished" in item.lower() for item in RELEASE_HIGHLIGHTS)


def test_repository_and_bundled_changelogs_are_identical():
    root = _read("CHANGELOG.md")
    bundled = _read("Program/CHANGELOG.md")
    assert root == bundled
    assert f"## [{VERSION}] - {RELEASE_DATE_ISO}" in root
    assert "## [0.9.7] - Unreleased" not in root


def test_changelog_covers_completed_feedback_workstreams():
    changelog = _read("CHANGELOG.md")
    required_topics = (
        "cumulative percent passing",
        "ErrorTab",
        "Multiple Samples in One File (Experimental)",
        "Delimited TXT",
        "51 samples",
        "Guides",
        "Home navigation",
        "Samples batch selection in the left Samples panel",
        "legend-column control",
        "Tick size",
        "native multi-file",
        "redesigned Export",
    )
    missing = [topic for topic in required_topics if topic not in changelog]
    assert missing == []


def test_home_whats_new_uses_the_canonical_release_notes():
    source = _read("Program/gui/welcome_widget.py")
    assert 'VERSION_LABEL' in source
    assert 'RELEASE_DATE_ISO' in source
    assert 'list(RELEASE_HIGHLIGHTS)' in source
    assert "enumerate(self._welcome_release_notes())" in source
    assert "v0.9.6" not in source


def test_build_and_installer_versions_match_the_application():
    main_source = _read("Program/main.py")
    installer = _read("installer/GrainSizeAnalysis.iss")
    legacy_installer = _read("build_system/installer.nsi")
    developer_build = _read("build_system/build.py")
    build_script = _read("BUILD_EXE.bat")
    installer_script = _read("BUILD_INSTALLER.bat")
    metadata = render_version_info()

    assert f'#define AppVersion "{VERSION}"' in installer
    assert f'!define APP_VERSION "{VERSION}"' in legacy_installer
    assert "render_version_info" in developer_build
    assert "app.setApplicationVersion(VERSION)" in main_source
    assert "from version import VERSION" in build_script
    assert "from version import VERSION" in installer_script
    assert "--version-file" in build_script
    assert f"FileVersion', '{VERSION}'" in metadata
    assert f"ProductVersion', '{VERSION}'" in metadata


def test_guides_describe_the_shipped_analysis_and_summary_scope():
    analysis = _read("Program/help_content/analysis_parameters.html")
    samples = _read("Program/help_content/individual_samples_tab.html")
    assert "Analysis Settings" in analysis
    assert "Dataset Inputs" in analysis
    assert "positive <strong>OK</strong> results from all active methods" in samples
