"""
Regression tests for bundled resource lookup in frozen builds.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, 'Program')

from gui import theme


class TestThemeResourceLookup(unittest.TestCase):
    def test_font_base_dir_prefers_program_resources_in_frozen_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            program_fonts = base / "Program" / "resources" / "fonts"
            direct_fonts = base / "resources" / "fonts"
            program_fonts.mkdir(parents=True)
            direct_fonts.mkdir(parents=True)

            with patch.object(theme.sys, "frozen", True, create=True), patch.object(
                theme.sys, "_MEIPASS", str(base), create=True
            ):
                self.assertEqual(theme._font_base_dir(), program_fonts)


if __name__ == '__main__':
    unittest.main(verbosity=2)
