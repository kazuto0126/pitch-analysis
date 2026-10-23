"""Saved native diagnostics measure continuity without deciding correctness."""
from __future__ import annotations

from fractions import Fraction
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_analysis_input as fixtures
from pitch_analysis.analysis.native_input import load_native_analysis_input
from pitch_analysis.analysis.native_reliability import (
    describe_native_reliability, write_native_reliability,
)


class NativeReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.saved = fixtures.NativeAnalysisInputTests()

    @staticmethod
    def point(data, frame, name):
        return next(point for point in data["payloads"][frame]["landmarks"]
                    if point["name"] == name)

    def describe(self, data, *, track=False, raw=False):
        self.saved.refresh(data, track=track, raw=raw)
        self.saved.prepare(data)
        return describe_native_reliability(
            load_native_analysis_input(data["root"], data["output"]))

    def test_hand_computed_motion_fractional_time_and_first_pair_denominator(self):
        for frame_count in (3, 1):
            with self.subTest(frame_count=frame_count), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.saved.fixture(Path(temp))
                for index, xy in enumerate(((10., 10.), (13., 14.), (19., 22.))):
                    self.point(data, index, "RIGHT_WRIST").update(x_px=xy[0], y_px=xy[1])
                if frame_count == 1:
                    data["tracks"] = data["tracks"][:1]
                    data["payloads"] = data["payloads"][:1]
                    data["source"]["video"]["frame_count"] = 1
                    data["entry"]["frame_count"] = 1
                pose, _, rows = self.describe(data, track=True, raw=True)
                self.assertEqual(rows[0]["timestamp_sec"], 0)
                self.assertIsNone(rows[0]["joints"]["RIGHT_WRIST"]["step_px"])
                motion = pose["joints"]["RIGHT_WRIST"]["adjacent_motion"]["step_px"]
                self.assertEqual(motion["total_count"], frame_count - 1)
                self.assertEqual(motion["count"], frame_count - 1)
                self.assertEqual(motion["missing_count"], 0)
                if frame_count == 3:
                    self.assertEqual(rows[1]["joints"]["RIGHT_WRIST"]["step_px"], 5.)
                    self.assertEqual(rows[2]["joints"]["RIGHT_WRIST"]["step_px"], 10.)
                    self.assertEqual(rows[1]["timestamp_sec"], float(Fraction(1001, 60000)))
                    self.assertEqual(rows[2]["timestamp_sec"], float(Fraction(2002, 60000)))
                    self.assertAlmostEqual(rows[1]["joints"]["RIGHT_WRIST"]["speed_px_per_sec"],
                                           5 * 60000 / 1001)
                    self.assertEqual((motion["mean"], motion["min_frame"], motion["max_frame"]),
                                     (7.5, 1, 2))
                else:
                    self.assertIsNone(motion["mean"])
                    self.assertIsNone(motion["max_frame"])

    def test_missing_joint_does_not_bridge_a_gap_or_hide_pair_denominators(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.saved.fixture(Path(temp), missing_joint=True)
            self.point(data, 2, "RIGHT_WRIST")["x_px"] = 150.
            pose, _, rows = self.describe(data, raw=True)
            joint = pose["joints"]["RIGHT_WRIST"]
            self.assertEqual((joint["model_observed_coordinates"], joint["missing_coordinates"],
                              joint["longest_missing_span_frames"]), (2, 1, 1))
            motion = joint["adjacent_motion"]["step_px"]
            self.assertEqual((motion["total_count"], motion["count"], motion["missing_count"]), (2, 0, 2))
            self.assertIsNone(motion["max"])
            self.assertTrue(all(row["joints"]["RIGHT_WRIST"]["step_px"] is None for row in rows))
            self.assertEqual(joint["missing_spans"], [{
                "start_frame": 1, "end_frame": 1, "frame_count": 1,
                "start_sec": float(Fraction(1001, 60000)),
                "end_sec": float(Fraction(1001, 60000)),
                "duration_sec": float(Fraction(1001, 60000)),
            }])

    def test_left_right_order_does_not_jump_over_equal_or_missing_samples(self):
        for middle in ("equal", "missing", "opposite"):
            with self.subTest(middle=middle), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.saved.fixture(Path(temp))
                for index, left_x in enumerate((10., 20. if middle == "equal" else 30., 30.)):
                    self.point(data, index, "LEFT_SHOULDER")["x_px"] = left_x
                    self.point(data, index, "RIGHT_SHOULDER")["x_px"] = 20.
                if middle == "missing":
                    self.point(data, 1, "LEFT_SHOULDER").update(
                        x_px=None, y_px=None, coordinate_state="missing", missing_reason="saved_missing")
                pose, _, rows = self.describe(data, raw=True)
                report = pose["left_right_image_order"]["shoulder"]
                self.assertEqual(report["changed_at_frames"], [1] if middle == "opposite" else [])
                self.assertEqual(report["comparable_adjacent_pairs"], 2 if middle == "opposite" else 0)
                self.assertEqual(report["equal_x_frames"], [1] if middle == "equal" else [])
                self.assertEqual(report["missing_frames"], int(middle == "missing"))
                self.assertEqual(rows[0]["left_minus_right_x_sign"]["shoulder"], -1)
                self.assertEqual(rows[2]["left_minus_right_x_sign"]["shoulder"], 1)
                self.assertFalse(pose["semantics"]["image_order_flip_is_identity_switch"])

    def test_bbox_scale_is_separate_from_constant_torso_and_saved_iou(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.saved.fixture(Path(temp))
            for index, box in enumerate(([10, 10, 30, 50], [10, 10, 50, 90], [10, 10, 50, 90])):
                data["tracks"][index]["selected_bbox_xyxy_px"] = box
                data["tracks"][index]["match_iou"] = (None, .25, 1.)[index]
                data["payloads"][index]["model_selection"]["person_box_selection"]["selected_bbox_xyxy_px"] = box
                for name, xy in {"LEFT_SHOULDER": (20., 20.), "RIGHT_SHOULDER": (40., 20.),
                                 "LEFT_HIP": (20., 50.), "RIGHT_HIP": (40., 50.)}.items():
                    self.point(data, index, name).update(x_px=xy[0], y_px=xy[1])
            _, tracking, rows = self.describe(data, track=True, raw=True)
            self.assertEqual(rows[0]["bbox"]["area_px2"], 800)
            self.assertEqual(rows[1]["bbox"]["area_px2"], 3200)
            self.assertAlmostEqual(rows[1]["continuity"]["bbox_center_step_px"], math.sqrt(500))
            self.assertEqual(rows[1]["continuity"]["bbox_area_ratio"], 4)
            self.assertEqual(rows[1]["continuity"]["bbox_diagonal_ratio"], 2)
            self.assertEqual(rows[1]["hip_center_xy_px"], [30., 50.])
            self.assertAlmostEqual(rows[1]["torso_diagonal_px"], math.sqrt(1300))
            self.assertEqual(rows[1]["continuity"]["torso_diagonal_ratio"], 1)
            self.assertEqual(rows[1]["continuity"]["hip_center_step_px"], 0)
            self.assertEqual([row["saved_match_iou"] for row in rows], [None, .25, 1.])
            self.assertEqual(tracking["saved_match_iou"]["count"], 2)
            self.assertEqual(tracking["saved_match_iou"]["missing_count"], 0)

    def test_scores_outside_unit_interval_and_off_image_coordinates_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.saved.fixture(Path(temp))
            for index in range(3):
                self.point(data, index, "RIGHT_WRIST")["x_px"] = -3.
            pose, tracking, rows = self.describe(data, raw=True)
            for row in rows:
                self.assertEqual(row["joints"]["NOSE"]["native_score"], 12.)
                self.assertEqual(row["joints"]["RIGHT_WRIST"]["native_score"], -.25)
                self.assertEqual(row["joints"]["RIGHT_WRIST"]["xy_px"], [-3., 30.])
                self.assertEqual(row["joints"]["RIGHT_WRIST"]["coordinate_state"], "model_observed")
            joint = pose["joints"]["RIGHT_WRIST"]
            self.assertEqual((joint["model_observed_coordinates"], joint["coordinates_outside_image"]), (3, 3))
            self.assertEqual(joint["reliability"], "unknown")
            self.assertEqual(joint["human_visibility"], "unknown")
            self.assertIsNone(joint["usable_for_analysis"])
            self.assertEqual(pose["retained_landmark_slots"], 51)
            for report in (pose, tracking):
                self.assertEqual(report["quality_status"], "not_calibrated")
                self.assertIsNone(report["usable_for_analysis"])
                self.assertFalse(report["semantics"]["quality_gate_applied"])

    def test_terminal_break_and_detection_index_reordering_are_not_identity_labels(self):
        for broken in (True, False):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.saved.fixture(Path(temp), broken=broken)
                if not broken:
                    data["tracks"][1]["selected_output_index"] = 0
                    data["payloads"][1]["model_selection"]["person_box_selection"]["selected_output_index"] = 0
                pose, tracking, rows = self.describe(data, track=True, raw=True)
                self.assertEqual(tracking["automatic_identity_switch_assessment"], "unknown")
                self.assertFalse(tracking["semantics"]["candidate_index_is_person_identity"])
                self.assertEqual(tracking["multiple_candidate_frames"], 3)
                if broken:
                    self.assertEqual(tracking["break_frames"], [1])
                    span = tracking["unselected_spans"][0]
                    self.assertEqual((span["start_frame"], span["end_frame"], span["frame_count"]), (1, 2, 2))
                    self.assertEqual(rows[2]["track_status"], "after_track_break")
                    self.assertIsNone(rows[2]["bbox"]["center_xy_px"])
                    self.assertTrue(all(point["coordinate_state"] == "missing"
                                        for point in rows[2]["joints"].values()))
                    self.assertEqual(pose["joints"]["RIGHT_WRIST"]["adjacent_motion"]["step_px"]["count"], 0)
                else:
                    self.assertEqual([row["selected_output_index"] for row in rows], [1, 0, 1])
                    self.assertEqual(tracking["break_frames"], [])
                    self.assertEqual(tracking["unselected_spans"], [])

    def test_writer_preserves_source_bytes_without_models_decoder_or_tracking_replay(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.saved.fixture(Path(temp))
            self.saved.prepare(data)
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            output = data["root"] / "analysis_results" / "report"
            with patch("subprocess.Popen", side_effect=AssertionError("no model process")), \
                    patch("cv2.VideoCapture", side_effect=AssertionError("no video decoding")), \
                    patch("pitch_analysis.native_seeded_track.associate_saved_boxes",
                          side_effect=AssertionError("no association replay")):
                result = write_native_reliability(data["root"], data["output"], output)
            self.assertEqual(result["status"], "descriptive_report_complete")
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertEqual({path.name for path in output.iterdir()}, {
                "pose_reliability.json", "tracking_reliability.json", "frame_diagnostics.jsonl", "report.md"})
            for name in ("pose_reliability.json", "tracking_reliability.json"):
                report = json.loads((output / name).read_text(encoding="utf-8"))
                self.assertEqual(report["new_inference_calls"], 0)
                self.assertEqual(report["new_tracking_replays"], 0)
                self.assertEqual(report["new_ground_truth_labels"], 0)
                self.assertIn("review_ref", report["source_refs"])

    def test_writer_rejects_existing_output_external_output_and_changed_source(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.saved.fixture(Path(temp))
            self.saved.prepare(data)
            output = data["root"] / "analysis_results" / "report"
            write_native_reliability(data["root"], data["output"], output)
            before = {path: path.read_bytes() for path in output.iterdir()}
            with self.assertRaises(FileExistsError):
                write_native_reliability(data["root"], data["output"], output)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            outside = data["root"] / "outside_reports"
            with self.assertRaisesRegex(ValueError, "inside this project's analysis_results"):
                write_native_reliability(data["root"], data["output"], outside)
            self.assertFalse(outside.exists())
            data["video"].write_bytes(b"changed since human acceptance")
            fresh = data["root"] / "analysis_results" / "changed_source"
            with self.assertRaisesRegex(ValueError, "Changed or external source"):
                write_native_reliability(data["root"], data["output"], fresh)
            self.assertFalse(fresh.exists())


if __name__ == "__main__":
    unittest.main()
