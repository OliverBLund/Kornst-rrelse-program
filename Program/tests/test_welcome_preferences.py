import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "Program")

from gui.main_window import (
    WELCOME_SCREEN_PREF_REVISION,
    _effective_welcome_dont_show,
    _save_welcome_preference,
)


class _FakeSettings:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def value(self, key, default=None, type=None):
        result = self.values.get(key, default)
        if type is bool:
            return bool(result)
        if type is int:
            return int(result)
        return result

    def setValue(self, key, value):
        self.values[key] = value


class TestWelcomePreferences(unittest.TestCase):
    def test_old_dont_show_flag_does_not_hide_new_welcome_revision(self):
        settings = _FakeSettings(
            {
                "welcome_screen/dont_show": True,
                "welcome_screen/revision": WELCOME_SCREEN_PREF_REVISION - 1,
            }
        )

        self.assertFalse(_effective_welcome_dont_show(settings))

    def test_current_revision_dont_show_flag_is_respected(self):
        settings = _FakeSettings(
            {
                "welcome_screen/dont_show": True,
                "welcome_screen/revision": WELCOME_SCREEN_PREF_REVISION,
            }
        )

        self.assertTrue(_effective_welcome_dont_show(settings))

    def test_saving_welcome_preference_updates_revision(self):
        settings = _FakeSettings()

        _save_welcome_preference(settings, True)

        self.assertTrue(settings.values["welcome_screen/dont_show"])
        self.assertEqual(
            settings.values["welcome_screen/revision"],
            WELCOME_SCREEN_PREF_REVISION,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
