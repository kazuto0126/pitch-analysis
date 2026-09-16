import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pitch_analysis.camera import compare_camera_contexts


class CameraCompatibilityTests(unittest.TestCase):
    def test_strict_requires_explicit_mirror_and_full_body(self):
        result = compare_camera_contexts(
            {"view": "rear_centerfield_broadcast"},
            {"view": "rear_centerfield_broadcast"},
            mode="strict",
        )

        self.assertFalse(result["compatible"])
        self.assertIn("horizontal_mirror_unknown", result["reasons"])
        self.assertIn("subject_framing_not_confirmed_full_body", result["reasons"])

    def test_exploratory_allows_unknowns_with_warnings(self):
        result = compare_camera_contexts(
            {"view": "rear_centerfield_broadcast"},
            {"view": "rear_centerfield_broadcast"},
            mode="exploratory",
        )

        self.assertTrue(result["compatible"])
        self.assertIn("horizontal_mirror_unknown", result["warnings"])

    def test_view_mismatch_is_never_compatible(self):
        result = compare_camera_contexts(
            {"view": "rear_centerfield_broadcast", "horizontal_mirror": False, "subject_framing": "full_body"},
            {"view": "side_broadcast", "horizontal_mirror": False, "subject_framing": "full_body"},
            mode="exploratory",
        )

        self.assertFalse(result["compatible"])
        self.assertIn("camera_view_mismatch", result["reasons"])


if __name__ == "__main__":
    unittest.main()
