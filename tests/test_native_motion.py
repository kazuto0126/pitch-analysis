"""Native motion descriptions preserve source geometry and unknown usability."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import tempfile
import unittest

import test_native_analysis_input as fixtures

from pitch_analysis.analysis.native_input import NativeAnalysisInput, load_native_analysis_input
from pitch_analysis.analysis.native_motion import describe_native_motion
from pitch_analysis.native_pose_io import reference


class NativeMotionTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixtures.NativeAnalysisInputTests()

    @staticmethod
    def set_points(frame, names, coords):
        points = {point["name"]: point for point in frame["landmarks"]}
        for name, (x, y) in zip(names, coords, strict=True):
            points[name].update(x_px=x, y_px=y, coordinate_state="model_observed", missing_reason=None)

    def load(self, data):
        self.helper.refresh(data, raw=True)
        self.helper.prepare(data)
        return load_native_analysis_input(data["root"], data["output"])

    def test_known_zero_ninety_and_straight_angles_are_descriptive_only(self):
        names = ["RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST"]
        examples = [([(10, 20), (20, 20), (20, 30)], 90.),
                    ([(10, 20), (20, 20), (30, 20)], 180.),
                    ([(10, 20), (20, 20), (15, 20)], 0.)]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp))
            for frame, (coords, _) in zip(data["payloads"], examples, strict=True):
                self.set_points(frame, names, coords)
            summary, rows = describe_native_motion(self.load(data))
            self.assertEqual([row["throwing_elbow_model_xy_deg"] for row in rows], [90., 180., 0.])
            self.assertEqual(summary["curves"]["throwing_elbow"],
                             {"total_frames": 3, "calculated": 3, "missing": 0, "degenerate": 0})
            self.assertTrue(all(row["throwing_elbow_usable_deg"] is None for row in rows))
            self.assertEqual(summary["scope"], "descriptive_model_xy_projection")
            self.assertIsNone(summary["usable_for_analysis"])

    def test_degenerate_limb_is_not_a_zero_angle_or_missing_coordinate(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp))
            self.set_points(data["payloads"][1], ["RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST"],
                            [(20, 20), (20, 20), (25, 20)])
            summary, rows = describe_native_motion(self.load(data))
            self.assertIsNone(rows[1]["throwing_elbow_model_xy_deg"])
            self.assertEqual(rows[1]["throwing_elbow_coordinate_status"], "degenerate_geometry")
            self.assertEqual(summary["curves"]["throwing_elbow"],
                             {"total_frames": 3, "calculated": 2, "missing": 0, "degenerate": 1})

    def test_left_and_right_metadata_choose_throwing_arm_and_opposite_lead_leg(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp))
            pitch = self.load(data)
            right_summary, _ = describe_native_motion(pitch)
            self.assertEqual(right_summary["role_joints"]["throwing_elbow"],
                             ["RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST"])
            self.assertEqual(right_summary["role_joints"]["lead_knee"],
                             ["LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"])
            metadata = pitch.metadata
            metadata["pitcher"]["throws"] = "LEFT"
            left_pitch = NativeAnalysisInput(pitch.manifest, metadata, pitch.usage_summary,
                                             [frame.native for frame in pitch.iter_frames()],
                                             [frame.tracking for frame in pitch.iter_frames()])
            left_summary, _ = describe_native_motion(left_pitch)
            self.assertEqual(left_summary["role_joints"]["throwing_elbow"],
                             ["LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST"])
            self.assertEqual(left_summary["role_joints"]["lead_knee"],
                             ["RIGHT_HIP", "RIGHT_KNEE", "RIGHT_ANKLE"])

    def test_non_square_source_uses_original_pixels_not_axis_normalized_coordinates(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp))
            # In the 160x120 image the vectors are perpendicular in pixels;
            # independently dividing X/Y by width/height would distort the angle.
            self.set_points(data["payloads"][0], ["RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST"],
                            [(40, 20), (60, 40), (40, 60)])
            _, rows = describe_native_motion(self.load(data))
            self.assertAlmostEqual(rows[0]["throwing_elbow_model_xy_deg"], 90.)

    def test_missing_joint_preserves_null_without_interpolation(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp), missing_joint=True)
            summary, rows = describe_native_motion(self.load(data))
            self.assertIsNotNone(rows[0]["throwing_elbow_model_xy_deg"])
            self.assertIsNone(rows[1]["throwing_elbow_model_xy_deg"])
            self.assertIsNotNone(rows[2]["throwing_elbow_model_xy_deg"])
            self.assertEqual(rows[1]["throwing_elbow_coordinate_status"], "missing_coordinates")
            self.assertEqual(summary["curves"]["throwing_elbow"]["missing"], 1)
            self.assertEqual(summary["interpolated_angles"], 0)
            self.assertEqual(summary["smoothed_angles"], 0)

    def test_low_negative_native_scores_do_not_reject_existing_coordinates(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp))
            for point in data["payloads"][0]["landmarks"]:
                point["native_score"] = -1000.
            summary, rows = describe_native_motion(self.load(data))
            self.assertEqual(rows[0]["throwing_elbow_coordinate_status"], "calculated_from_model_xy")
            self.assertEqual(rows[0]["lead_knee_coordinate_status"], "calculated_from_model_xy")
            self.assertEqual(rows[0]["pointwise_reliability"], "unknown")
            self.assertEqual(summary["quality_status"], "not_calibrated")

    def test_fractional_timestamps_preserve_zero_origin_and_source_duration(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp))
            summary, rows = describe_native_motion(self.load(data))
            self.assertEqual([row["frame_index"] for row in rows], [0, 1, 2])
            self.assertEqual([row["timestamp_sec"] for row in rows],
                             [float(Fraction(index) / Fraction(60000, 1001)) for index in range(3)])
            self.assertEqual(summary["timebase"]["fps_fraction"], "60000/1001")
            self.assertEqual(summary["timebase"]["timestamp_unit"], "seconds")
            self.assertNotEqual(rows[-1]["timestamp_sec"], 1.)

    def test_calculation_does_not_modify_raw_sources_or_consumer_snapshots(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp))
            pitch = self.load(data)
            before_refs = [reference(data["root"], path) for path in data["root"].rglob("*") if path.is_file()]
            before_frames = [frame.native.to_dict() for frame in pitch.iter_frames()]
            before_metadata, before_review = pitch.metadata, pitch.review
            summary, rows = describe_native_motion(pitch)
            summary["human_overlay_review"]["reviewer"] = "mutation"
            rows[0]["throwing_elbow_model_xy_deg"] = -1234
            self.assertEqual([frame.native.to_dict() for frame in pitch.iter_frames()], before_frames)
            self.assertEqual(pitch.metadata, before_metadata)
            self.assertEqual(pitch.review, before_review)
            self.assertEqual([reference(data["root"], data["root"] / ref["path"]) for ref in before_refs], before_refs)

    def test_terminal_break_keeps_complete_denominator_and_both_null_curves(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.helper.fixture(Path(temp), broken=True)
            summary, rows = describe_native_motion(self.load(data))
            self.assertEqual(summary["total_frames"], 3)
            self.assertEqual(len(rows), 3)
            for role in ("throwing_elbow", "lead_knee"):
                self.assertEqual(summary["curves"][role],
                                 {"total_frames": 3, "calculated": 1, "missing": 2, "degenerate": 0})
                for row in rows[1:]:
                    self.assertIsNone(row[f"{role}_model_xy_deg"])
                    self.assertIsNone(row[f"{role}_usable_deg"])
                    self.assertEqual(row[f"{role}_coordinate_status"], "missing_coordinates")


if __name__ == "__main__":
    unittest.main()
