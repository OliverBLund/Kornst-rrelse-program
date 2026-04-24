import os
import sys
import unittest

sys.path.insert(0, "Program")

from data_loader import get_test_data_files, resolve_test_data_dir


class TestDemoData(unittest.TestCase):
    def test_demo_data_resolves_root_test_data_csv_files(self):
        test_dir = resolve_test_data_dir()
        self.assertIsNotNone(test_dir)

        basenames = [os.path.basename(path) for path in get_test_data_files()]
        self.assertEqual(
            basenames,
            [
                "Example_1_Case_1_Vukovic.csv",
                "Example_1_Case_2_Vukovic_15C.csv",
                "Example_2_Case_1_Vukovic_15C.csv",
                "Sample_1_Odong.csv",
                "Thomson_SERDP_Borden_Sand.csv",
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
