import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pitch_analysis.alignment import constrained_dtw
from pitch_analysis.clean_pose import clean_pose
from pitch_analysis.events import validate_events
from pitch_analysis.features import extract_frame_features
from pitch_analysis.temporal import (
    circular_smooth_line_angles,
    interpolate_short_line_angle_gaps,
    line_angle_delta,
)
from pitch_analysis.workflow import quality_gate
from pitch_analysis.comparison import FEATURE_SCALES, compare_phase_sequences


class QualityContractTests(unittest.TestCase):
    def test_comparison_uses_raw_phase_coverage_instead_of_smoothed_completeness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "query.csv", root / "reference.csv"]
            fields = ["phase", "phase_index", "source_frame_float", *FEATURE_SCALES]
            for path in paths:
                with path.open("w", encoding="utf-8", newline="") as sink:
                    writer = csv.DictWriter(sink, fieldnames=fields)
                    writer.writeheader()
                    for phase in ("windup", "stride", "arm_acceleration", "follow_through"):
                        for index in range(3):
                            writer.writerow(
                                {
                                    "phase": phase,
                                    "phase_index": index,
                                    "source_frame_float": index,
                                    **{feature: 90 + index for feature in FEATURE_SCALES},
                                }
                            )
                raw = {feature: 1.0 for feature in FEATURE_SCALES}
                if path.name == "query.csv":
                    raw["throwing_elbow_angle_smoothed"] = 0.0
                path.with_suffix(".quality.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "phase-quality-v0.1",
                            "phases": {
                                phase: {"raw_feature_coverage": raw}
                                for phase in (
                                    "windup",
                                    "stride",
                                    "arm_acceleration",
                                    "follow_through",
                                )
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            result = compare_phase_sequences(paths[0], paths[1])

            windup = result["phases"]["windup"]
            self.assertEqual(windup["query_coverage"]["throwing_elbow_angle_smoothed"], 0.0)
            self.assertIn(
                "throwing_elbow_angle_smoothed",
                windup["excluded_low_coverage_features"],
            )
            self.assertEqual(
                windup["query_coverage_source"]["throwing_elbow_angle_smoothed"],
                "phase_quality_raw_feature_coverage",
            )

    def test_comparison_rejects_an_overall_score_from_too_few_phases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "query.csv", root / "reference.csv"]
            fields = ["phase", "phase_index", "source_frame_float", *FEATURE_SCALES]
            phases = ("windup", "stride", "arm_acceleration", "follow_through")
            for path in paths:
                with path.open("w", encoding="utf-8", newline="") as sink:
                    writer = csv.DictWriter(sink, fieldnames=fields)
                    writer.writeheader()
                    for phase in phases:
                        for index in range(3):
                            writer.writerow(
                                {
                                    "phase": phase,
                                    "phase_index": index,
                                    "source_frame_float": index,
                                    **{feature: 90 + index for feature in FEATURE_SCALES},
                                }
                            )
                path.with_suffix(".quality.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "phase-quality-v0.1",
                            "phases": {
                                phase: {
                                    "raw_feature_coverage": {
                                        feature: (
                                            1.0
                                            if phase in {"windup", "stride"}
                                            else 0.0
                                        )
                                        for feature in FEATURE_SCALES
                                    }
                                }
                                for phase in phases
                            },
                        }
                    ),
                    encoding="utf-8",
                )

            result = compare_phase_sequences(paths[0], paths[1])

            self.assertEqual(result["scored_phase_count"], 2)
            self.assertIsNone(result["overall_mean_phase_distance"])
            self.assertTrue(result["overall_eligibility_failures"])

    @staticmethod
    def _point(x, y):
        return {"x": x, "y": y, "visibility": 0.95, "presence": 0.95}

    def test_aspect_corrected_line_angle_matches_same_pixel_geometry(self):
        # Same physical/pixel shoulder line in 100x100 and 200x100 frames.
        square = {
            "LEFT_SHOULDER": self._point(0.20, 0.20),
            "RIGHT_SHOULDER": self._point(0.80, 0.60),
        }
        wide = {
            "LEFT_SHOULDER": self._point(0.10, 0.20),
            "RIGHT_SHOULDER": self._point(0.40, 0.60),
        }
        square_angle = extract_frame_features(square, "RIGHT", 0.5, coordinate_x_scale=1.0)["shoulder_line_angle"]
        wide_angle = extract_frame_features(wide, "RIGHT", 0.5, coordinate_x_scale=2.0)["shoulder_line_angle"]
        self.assertAlmostEqual(square_angle, wide_angle)

    def test_clean_pose_keeps_requested_capture_timeline_when_pose_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "pose_raw.csv"
            with raw.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=("frame", "landmark", "x", "y", "z", "visibility", "presence"))
                writer.writeheader()
                for frame in (1, 3):
                    writer.writerow({"frame": frame, "landmark": "LEFT_SHOULDER", "x": 0.2, "y": 0.3, "z": 0, "visibility": 0.95, "presence": 0.95})
            raw.with_suffix(".capture.json").write_text(json.dumps({
                "start_frame": 0, "end_frame": 4, "requested_frames": 5,
                "width": 100, "height": 100, "fps": 30,
            }), encoding="utf-8")
            clean = root / "pose_clean.csv"
            report = clean_pose(raw, clean)
            with clean.open(encoding="utf-8-sig", newline="") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(report["frame_range"], [0, 4])
            self.assertEqual([int(row["frame"]) for row in rows], [0, 1, 2, 3, 4])
            self.assertEqual([row["source_frame_detected"] for row in rows], ["False", "True", "False", "True", "False"])

    def test_quality_gate_uses_raw_not_only_interpolated_coverage(self):
        report = {
            "timeline_frames": 100,
            "input_frames_detected": 100,
            "invalid_feature_frames": {
                "throwing_knee_angle": 0, "lead_knee_angle": 0,
                "shoulder_line_angle": 0, "throwing_elbow_angle": 0,
                "hip_line_angle": 0, "lateral_foot_separation": 0,
            },
            "raw_invalid_feature_frames": {
                "throwing_knee_angle": 21, "lead_knee_angle": 0,
                "shoulder_line_angle": 0, "throwing_elbow_angle": 0,
                "hip_line_angle": 0, "lateral_foot_separation": 0,
            },
            "coordinate_imputed_feature_fraction": {},
            "max_consecutive_missing_source_frames": 0,
        }
        result = quality_gate(report)
        self.assertFalse(result["passed"])
        self.assertIn("throwing_knee_angle raw coverage below 80%", result["failures"])

    def test_line_orientation_wrap_is_circular(self):
        self.assertAlmostEqual(line_angle_delta(89.0, -89.0), 2.0)
        values, mask = interpolate_short_line_angle_gaps([89.0, None, -89.0])
        self.assertTrue(mask[1])
        self.assertAlmostEqual(abs(line_angle_delta(89.0, values[1])), 1.0)
        smoothed = circular_smooth_line_angles([89.0, -89.0], radius=1)
        self.assertLess(abs(line_angle_delta(smoothed[0], smoothed[1])), 1e-6)

    def test_dtw_rejects_frames_with_too_few_shared_features(self):
        result = constrained_dtw(
            [{"a": 0.0, "b": None}], [{"a": 0.0, "b": 2.0}],
            {"a": 1.0, "b": 1.0}, min_shared_features=2,
        )
        self.assertIsNone(result)

    def test_events_must_be_strict_and_in_range(self):
        duplicate = {"events": {"pitch_start": 1, "peak_leg_lift": 1, "foot_strike": 3, "release": 4, "follow_through_end": 5}}
        with self.assertRaises(ValueError):
            validate_events(duplicate)
        outside = {"events": {"pitch_start": 1, "peak_leg_lift": 2, "foot_strike": 3, "release": 4, "follow_through_end": 8}}
        with self.assertRaises(ValueError):
            validate_events(outside, frame_range=(1, 7))


if __name__ == "__main__":
    unittest.main()
