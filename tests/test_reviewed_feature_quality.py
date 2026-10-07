"""Existing numeric values need all constituent reviewed observation evidence."""
from copy import deepcopy
import csv
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("reviewed_feature_export", Path(__file__).resolve().parents[1] / "scripts/export_reviewed_feature_quality.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def fixture():
    frame = {"frame_index": 0, "timestamp_ms": 0., "focus_joints": {},
             "human_review": {"pitcher_correctly_selected": True, "major_pose_failure": [], "track_break": [], "identity_switch": []}}
    for roles in guard.DEPENDENCIES.values():
        for role, xy in zip(roles, ((0., 0.), (.5, 0.), (.5, .5))):
            frame["focus_joints"][role] = {
                "processed_landmark": {"x": xy[0], "y": xy[1], "usable": True},
                "model_state": "observed", "use_disposition": {"status": "reviewed_raw_observation"},
                "human_raw_overlay_review": {"status": "reliable", "reason": "human reviewed"},
            }
    row = {"frame": "0", "source_frame_detected": "True"}
    for feature in guard.DEPENDENCIES:
        row.update({feature: "90", feature + "_raw_observed": "True", feature + "_coordinate_imputed": "False",
                    feature + "_imputed": "False", feature + "_interpolated": "90", feature + "_smoothed": "92"})
    return row, frame


class ReviewedFeatureQualityTests(unittest.TestCase):
    def test_saved_base_only_is_eligible_and_smoothed_neighbors_stay_unverified(self):
        row, frame = fixture()
        before = deepcopy((row, frame))
        item = guard.apply_review(row, frame, "throwing_elbow_angle", .8)
        self.assertTrue(item["eligible"])
        self.assertEqual(item["eligible_value"], 90.)
        self.assertEqual(item["saved_values"]["smoothed"], 92.)
        self.assertIn("not verified", item["alternate_values_review"])
        self.assertEqual((row, frame), before)

    def test_one_hidden_constituent_withholds_angle_without_claiming_error(self):
        row, frame = fixture()
        frame["focus_joints"]["throwing_wrist"]["human_raw_overlay_review"]["status"] = "not_observable"
        frame["focus_joints"]["throwing_wrist"]["use_disposition"]["status"] = "hold_raw_not_observable"
        item = guard.apply_review(row, frame, "throwing_elbow_angle", 1.)
        self.assertFalse(item["eligible"])
        self.assertIsNone(item["eligible_value"])
        self.assertEqual(item["saved_values"]["base"], 90.)
        self.assertEqual(item["status"], "unverifiable_joint")
        self.assertIn("human_raw_not_observable:throwing_wrist", item["reason_codes"])

    def test_joint_error_is_local_and_does_not_alter_other_feature(self):
        row, frame = fixture()
        frame["focus_joints"]["throwing_elbow"]["human_raw_overlay_review"]["status"] = "unreliable"
        elbow = guard.apply_review(row, frame, "throwing_elbow_angle", 1.)
        knee = guard.apply_review(row, frame, "lead_knee_angle", 1.)
        self.assertEqual(elbow["status"], "hold_joint_review")
        self.assertFalse(elbow["eligible"])
        self.assertTrue(knee["eligible"])

    def test_whole_frame_failure_holds_even_individually_reliable_joints(self):
        row, frame = fixture()
        frame["human_review"]["major_pose_failure"] = [{"status": "confirmed", "reason": "whole skeleton shift"}]
        for feature in guard.DEPENDENCIES:
            item = guard.apply_review(row, frame, feature, 1.)
            self.assertEqual(item["status"], "hold_frame_review")
            self.assertIsNone(item["eligible_value"])
            self.assertIn("human_confirmed_major_pose_failure", item["reason_codes"])
        self.assertEqual(frame["human_review"]["identity_switch"], [])

    def test_reliable_raw_label_does_not_certify_coordinate_imputation(self):
        row, frame = fixture()
        frame["focus_joints"]["throwing_elbow"]["model_state"] = "interpolated"
        frame["focus_joints"]["throwing_elbow"]["use_disposition"]["status"] = "unverified_processed_interpolation"
        row["throwing_elbow_angle_raw_observed"] = "False"
        row["throwing_elbow_angle_coordinate_imputed"] = "True"
        item = guard.apply_review(row, frame, "throwing_elbow_angle", 1.)
        self.assertEqual(item["status"], "unverified_imputation")
        self.assertIsNone(item["eligible_value"])
        self.assertEqual(item["saved_values"]["base"], 90.)

    def test_missing_coordinate_retains_none_and_other_original_variants(self):
        row, frame = fixture()
        frame["focus_joints"]["throwing_elbow"]["model_state"] = "missing"
        frame["focus_joints"]["throwing_elbow"]["processed_landmark"]["usable"] = False
        frame["focus_joints"]["throwing_elbow"]["use_disposition"]["status"] = "unavailable_missing"
        row["throwing_elbow_angle"] = ""
        row["throwing_elbow_angle_raw_observed"] = "False"
        row["throwing_elbow_angle_imputed"] = "True"
        item = guard.apply_review(row, frame, "throwing_elbow_angle", 1.)
        self.assertIsNone(item["eligible_value"])
        self.assertIsNone(item["saved_values"]["base"])
        self.assertEqual(item["saved_values"]["smoothed"], 92.)

    def test_mixed_value_or_provenance_is_rejected_not_silently_certified(self):
        for key, value in (("throwing_elbow_angle", "80"), ("throwing_elbow_angle_raw_observed", "False"),
                           ("throwing_elbow_angle_coordinate_imputed", "True"), ("source_frame_detected", "False"),
                           ("throwing_elbow_angle_imputed", "True"), ("throwing_elbow_angle_interpolated", "100")):
            row, frame = fixture()
            row[key] = value
            with self.assertRaises(ValueError):
                guard.apply_review(row, frame, "throwing_elbow_angle", 1.)
        for value in ("nan", "inf", "-inf"):
            with self.assertRaises(ValueError):
                guard.number(value)
        with self.assertRaises(ValueError):
            guard.boolean("")

    def test_width_height_projection_is_used_without_clamping(self):
        points = [{"x": 0., "y": 0., "usable": True}, {"x": 1., "y": 1., "usable": True},
                  {"x": 2., "y": 1., "usable": True}]
        angle = guard.projected_angle(points, .5)
        self.assertAlmostEqual(angle, 116.565051177078, places=10)
        self.assertNotAlmostEqual(angle, guard.projected_angle(points, 1.))
        for aspect in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                guard.projected_angle(points, aspect)

    def test_degenerate_angle_is_missing_and_zero_angle_is_a_value(self):
        points = [{"x": 0., "y": 0., "usable": True}] * 3
        self.assertIsNone(guard.projected_angle(points, 1.))
        self.assertEqual(guard.number("0"), 0.)
        self.assertFalse(guard.same_number(None, 0.))

    def test_unknown_subject_or_uncertain_major_interval_is_held(self):
        row, frame = fixture()
        frame["human_review"]["major_pose_failure"] = [{"status": "uncertain", "reason": "cannot decide"}]
        item = guard.apply_review(row, frame, "lead_knee_angle", 1.)
        self.assertEqual(item["status"], "hold_frame_review")
        self.assertIn("human_uncertain_major_pose_failure", item["reason_codes"])
        frame["human_review"]["major_pose_failure"][0]["status"] = "not_observable"
        item = guard.apply_review(row, frame, "lead_knee_angle", 1.)
        self.assertEqual(item["status"], "hold_frame_review")
        self.assertIn("human_not_observable_major_pose_failure", item["reason_codes"])
        self.assertNotIn("human_uncertain_major_pose_failure", item["reason_codes"])
        frame["human_review"]["major_pose_failure"] = []
        frame["human_review"]["pitcher_correctly_selected"] = None
        self.assertFalse(guard.apply_review(row, frame, "lead_knee_angle", 1.)["eligible"])

    def test_csv_held_value_stays_blank_with_original_numeric_value_retained(self):
        row, frame = fixture()
        frame["focus_joints"]["throwing_elbow"]["human_raw_overlay_review"]["status"] = "unreliable"
        features = {name: guard.apply_review(row, frame, name, 1.) for name in guard.DEPENDENCIES}
        report = {"frames": [{"frame_index": 0, "timestamp_ms": 0., "features": features}]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reviewed.csv"
            guard.write_csv(path, report)
            with path.open(encoding="utf-8", newline="") as stream:
                saved = list(csv.DictReader(stream))
            self.assertEqual(saved[0]["throwing_elbow_angle_original_base"], "90.0")
            self.assertEqual(saved[0]["throwing_elbow_angle_eligible_value"], "")
            self.assertEqual(saved[0]["lead_knee_angle_eligible_value"], "90.0")
            with self.assertRaises(FileExistsError):
                guard.write_csv(path, report)
            with self.assertRaises(FileExistsError):
                guard.run(Path(temp) / "missing.json", Path(temp))

    def test_all_frame_denominator_and_summary_reject_gaps_and_mixed_metadata(self):
        row, frame = fixture()
        view = {"pitch_id": "pitch_test", "pitcher": {"id": "p", "throws": "RIGHT"},
                "summary": {"total_frames": 1}, "frames": [frame], "ground_truth_provenance": {"reviewer": "HSU"},
                "source_artifacts": {"original_video": {"sha256": "abc"}}}
        quality = {"timeline_frames": 1, "throwing_side": "RIGHT", "coordinate_x_scale": 1.,
                   "raw_feature_coverage": {name: 1. for name in guard.DEPENDENCIES}}
        meta = {"frame_count": 1, "width": 600, "height": 600, "sha256": "abc", "timestamps_ms": [0.]}
        metrics = {"pitch_id": "pitch_test", "pitcher_id": "p", "quality_gate_passed": True, "status": "source",
                   "metrics": {name: {"observed_frames": 1, "raw_coverage": 1.} for name in guard.DEPENDENCIES}}
        result = guard.derive(view, [row], metrics, quality, meta)
        self.assertEqual(result["frames"][0]["human_frame_evidence"], frame["human_review"])
        self.assertEqual(result["summary"]["throwing_elbow_angle"]["total_frame_denominator"], 1)
        self.assertTrue(result["original_metrics_quality_gate_passed"])
        for mutated_meta in ({**meta, "timestamps_ms": []}, {**meta, "sha256": "wrong"}):
            with self.assertRaises(ValueError):
                guard.derive(view, [row], metrics, quality, mutated_meta)
        with self.assertRaises(ValueError):
            guard.derive(view, [], metrics, quality, meta)
        quality["throwing_side"] = "LEFT"
        with self.assertRaises(ValueError):
            guard.derive(view, [row], metrics, quality, meta)


if __name__ == "__main__":
    unittest.main()
