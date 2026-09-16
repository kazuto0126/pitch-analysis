import unittest
import csv
import json
import tempfile
from pathlib import Path

from pitch_analysis.segmentation import (
    detect_activity_windows,
    detect_motion_window,
    detect_motion_windows,
    write_motion_candidates,
)


class MotionSegmentationTests(unittest.TestCase):
    def test_detects_multiple_motion_candidates(self) -> None:
        frames = list(range(100))
        separation = [1.0] * 100
        for frame in range(20, 31):
            separation[frame] = 3.0
        for frame in range(60, 73):
            separation[frame] = 2.5

        windows = detect_motion_windows(
            frames,
            separation,
            baseline_frames=10,
            merge_gap_frames=2,
            min_window_frames=8,
            pre_roll_frames=2,
            post_roll_frames=3,
        )

        self.assertEqual(len(windows), 2)
        self.assertEqual((windows[0].start_frame, windows[0].end_frame), (18, 33))
        self.assertEqual((windows[1].start_frame, windows[1].end_frame), (58, 75))
        self.assertEqual(windows[0].peak_separation_frame, 20)

    def test_ignores_short_threshold_spike(self) -> None:
        frames = list(range(60))
        separation = [1.0] * 60
        separation[30] = 4.0

        windows = detect_motion_windows(
            frames,
            separation,
            baseline_frames=10,
            min_window_frames=5,
        )

        self.assertEqual(windows, [])

    def test_existing_single_window_api_is_preserved(self) -> None:
        frames = list(range(40))
        separation = [1.0] * 10 + [3.0] * 20 + [1.0] * 10

        window = detect_motion_window(frames, separation, baseline_frames=10)

        self.assertIsNotNone(window)
        assert window is not None
        self.assertEqual((window.start_frame, window.end_frame), (10, 29))

    def test_rejects_mismatched_input_lengths(self) -> None:
        with self.assertRaises(ValueError):
            detect_motion_windows([0, 1], [1.0])

    def test_writes_reviewable_candidate_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            features_path = Path(directory) / "features.csv"
            output_path = Path(directory) / "candidates.json"
            with features_path.open("w", encoding="utf-8", newline="") as sink:
                writer = csv.DictWriter(sink, fieldnames=["frame", "lateral_foot_separation_smoothed"])
                writer.writeheader()
                for frame in range(40):
                    writer.writerow(
                        {
                            "frame": frame,
                            "lateral_foot_separation_smoothed": 3.0 if 15 <= frame <= 25 else 1.0,
                        }
                    )

            payload = write_motion_candidates(
                features_path,
                output_path,
                method="foot-separation",
                baseline_frames=10,
                min_window_frames=5,
                pre_roll_frames=0,
                post_roll_frames=0,
            )

            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(payload["status"], "review_required")
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["candidates"][0]["start_frame"], 15)

    def test_multi_feature_activity_finds_motion_burst(self) -> None:
        frames = list(range(80))
        features = {}
        for name in (
            "throwing_knee_angle_smoothed",
            "lead_knee_angle_smoothed",
            "shoulder_line_angle_smoothed",
            "hip_line_angle_smoothed",
        ):
            values = [100.0] * 80
            for frame in range(30, 41):
                values[frame] = 100.0 + (frame - 29) * 5.0
            for frame in range(41, 51):
                values[frame] = 155.0 - (frame - 40) * 5.0
            features[name] = values

        windows = detect_activity_windows(
            frames,
            features,
            activity_quantile=0.7,
            merge_gap_frames=4,
            min_window_frames=4,
            pre_roll_frames=5,
            post_roll_frames=5,
        )

        self.assertEqual(len(windows), 1)
        self.assertLessEqual(windows[0].start_frame, 30)
        self.assertGreaterEqual(windows[0].end_frame, 50)
        self.assertEqual(windows[0].method, "multi-feature-velocity-proxy")


if __name__ == "__main__":
    unittest.main()
