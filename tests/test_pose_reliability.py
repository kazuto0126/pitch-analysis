import csv
import json
import tempfile
import unittest
from pathlib import Path

from pitch_analysis.pose_reliability import evaluate_pose_reliability, write_pose_reliability


FIELDS = ("frame", "source_frame_detected", "landmark", "x_raw", "y_raw", "z_raw",
          "visibility", "presence", "quality_valid", "interpolated", "usable", "x", "y")


def _make_analysis(folder: Path, *, elbow_states=None, shoulder_flip_frame=None):
    elbow_states = elbow_states or ["observed"] * 12
    folder.mkdir(parents=True)
    (folder / "input_manifest.json").write_text(json.dumps({
        "pitch_id": "pitch_test", "pitcher": {"id": "test_pitcher", "throws": "RIGHT"}
    }), encoding="utf-8")
    (folder / "keypoint_quality.json").write_text(json.dumps({
        "total_frames": 12, "valid_pose_ratio": 1.0, "longest_missing_pose_gap": 0
    }), encoding="utf-8")
    (folder / "pose_clean.clean.json").write_text(json.dumps({
        "timeline_start_frame": 0, "timeline_end_frame": 11, "coordinate_x_scale": 1.0
    }), encoding="utf-8")
    coordinates = {
        "LEFT_SHOULDER": (0.4, 0.3), "RIGHT_SHOULDER": (0.6, 0.3),
        "RIGHT_ELBOW": (0.62, 0.4), "RIGHT_WRIST": (0.64, 0.5),
        "LEFT_HIP": (0.42, 0.6), "RIGHT_HIP": (0.58, 0.6),
        "LEFT_KNEE": (0.42, 0.75), "LEFT_ANKLE": (0.42, 0.9),
    }
    with (folder / "pose_clean.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for frame in range(12):
            for name, (x, y) in coordinates.items():
                state = elbow_states[frame] if name == "RIGHT_ELBOW" else "observed"
                if shoulder_flip_frame == frame and name.endswith("SHOULDER"):
                    x = 1.0 - x
                observed = state == "observed"
                raw_predicted = state in {"observed", "rejected"}
                usable = state in {"observed", "interpolated"}
                writer.writerow({
                    "frame": frame, "source_frame_detected": raw_predicted, "landmark": name,
                    "x_raw": x if raw_predicted else "", "y_raw": y if raw_predicted else "",
                    "visibility": .2 if state == "rejected" else (.95 if observed else ""),
                    "presence": .95 if raw_predicted else "",
                    "quality_valid": observed, "interpolated": state == "interpolated",
                    "usable": usable, "x": x if usable else "", "y": y if usable else "",
                })


class PoseReliabilityTests(unittest.TestCase):
    def test_occlusion_keeps_observed_interpolated_and_missing_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            _make_analysis(source, elbow_states=["observed"] * 2 + ["interpolated"] * 2 +
                           ["missing"] * 5 + ["observed"] * 3)
            result = evaluate_pose_reliability(source)
            elbow = result["joints"]["RIGHT_ELBOW"]
            self.assertEqual(elbow["frame_states"], ["observed"] * 2 + ["interpolated"] * 2 +
                             ["missing"] * 5 + ["observed"] * 3)
            self.assertEqual(elbow["observed_frames"], 5)
            self.assertEqual(elbow["interpolated_frames"], 2)
            self.assertEqual(elbow["missing_frames"], 5)
            self.assertAlmostEqual(elbow["raw_coverage"], 5 / 12)
            self.assertEqual(elbow["longest_missing_span_frames"], 5)
            self.assertEqual(elbow["longest_not_observed_span_frames"], 7)
            self.assertEqual(elbow["frame_to_frame_jump"]["observed_adjacent_pairs"], 3)
            self.assertEqual(elbow["status"], "unreliable")
            self.assertEqual(result["joints"]["RIGHT_SHOULDER"]["status"], "reliable")
            self.assertFalse(result["ground_truth_evaluated"])

            destination = Path(temporary) / "phase2" / "pose_reliability.json"
            self.assertEqual(write_pose_reliability(source, destination), destination)
            self.assertTrue(destination.exists())
            self.assertFalse((source / "pose_reliability.json").exists())
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["pitch_id"], "pitch_test")

    def test_low_visibility_raw_prediction_is_missing_not_observed(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            _make_analysis(source, elbow_states=["observed"] * 5 + ["rejected"] + ["observed"] * 6)
            elbow = evaluate_pose_reliability(source)["joints"]["RIGHT_ELBOW"]
            self.assertEqual(elbow["frame_states"][5], "missing")
            self.assertEqual(elbow["raw_prediction_coverage"], 1.0)
            self.assertAlmostEqual(elbow["raw_coverage"], 11 / 12)
            self.assertEqual(elbow["visibility_statistics"]["raw_prediction"]["sample_count"], 12)
            self.assertEqual(elbow["visibility_statistics"]["quality_gated_observed"]["sample_count"], 11)

    def test_left_right_one_frame_reversal_is_review_candidate_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            _make_analysis(source, shoulder_flip_frame=5)
            result = evaluate_pose_reliability(source)
            shoulder = result["left_right_consistency"]["pairs"]["shoulder"]
            self.assertEqual(shoulder["image_order_sign_change_frames"], [5, 6])
            self.assertEqual(shoulder["single_frame_reversal_candidates"], [5])
            self.assertIn("not an anatomical swap", result["left_right_consistency"]["interpretation"])
            self.assertGreater(result["joints"]["LEFT_SHOULDER"]["frame_to_frame_jump"]["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
