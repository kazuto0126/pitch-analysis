import csv
import json
import tempfile
import unittest
from pathlib import Path

from pitch_analysis.phases import build_phase_sequence, resample_phase


class PhaseQualityTests(unittest.TestCase):
    def test_line_orientation_resampling_uses_short_wrap_path(self) -> None:
        rows = [
            {"frame": "0", "shoulder_line_angle_smoothed": "89"},
            {"frame": "1", "shoulder_line_angle_smoothed": "-89"},
        ]

        result = resample_phase(
            rows,
            ["shoulder_line_angle_smoothed"],
            start=0,
            end=1,
            points=3,
        )

        middle = result[1]["shoulder_line_angle_smoothed"]
        self.assertAlmostEqual(abs(middle), 90.0)
        self.assertNotAlmostEqual(middle, 0.0)

    def test_event_window_quality_uses_only_compared_frames(self) -> None:
        feature = "throwing_elbow_angle_smoothed"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            features_path = root / "features.csv"
            output_path = root / "phases.csv"
            with features_path.open("w", encoding="utf-8", newline="") as sink:
                writer = csv.DictWriter(
                    sink,
                    fieldnames=["frame", feature, "throwing_elbow_angle_raw_observed"],
                )
                writer.writeheader()
                for frame in range(20):
                    in_event = 5 <= frame <= 15
                    writer.writerow(
                        {
                            "frame": frame,
                            feature: 90 + frame if in_event else "",
                            "throwing_elbow_angle_raw_observed": in_event,
                        }
                    )
            annotation = {
                "video_id": "sample",
                "review_status": "human_reviewed",
                "events": {
                    "pitch_start": 5,
                    "peak_leg_lift": 7,
                    "foot_strike": 10,
                    "release": 12,
                    "follow_through_end": 15,
                },
            }

            report = build_phase_sequence(features_path, annotation, output_path, [feature], 3)

            self.assertEqual(report["event_frame_range"], [5, 15])
            self.assertEqual(report["event_window"]["raw_feature_coverage"][feature], 1.0)
            saved = json.loads(output_path.with_suffix(".quality.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["event_window"]["source_frames"], 11)


if __name__ == "__main__":
    unittest.main()
