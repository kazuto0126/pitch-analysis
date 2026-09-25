"""Continuity warnings are diagnostic and cannot become identity ground truth."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from pitch_analysis.tracking_reliability import (
    evaluate_tracking_reliability,
    write_tracking_reliability,
)


def make_analysis(folder: Path, centers: list[float | None],
                  *, heights: list[float] | None = None) -> None:
    count = len(centers)
    heights = heights or [0.5] * count
    (folder / "analysis.json").write_text(json.dumps({
        "pitch_id": "pitch_test", "pitcher_id": "known_pitcher",
    }), encoding="utf-8")
    (folder / "video_metadata.json").write_text(json.dumps({
        "frame_count": count, "width": 640, "height": 640,
    }), encoding="utf-8")
    (folder / "pose_raw.capture.json").write_text(json.dumps({
        "selection_frames": [{"frame_index": index,
                              "status": "selected" if center is not None else "rejected",
                              "candidate_count": 1, "selected_index": 0 if center is not None else None}
                             for index, center in enumerate(centers)],
    }), encoding="utf-8")
    with (folder / "pose_raw.csv").open("w", encoding="utf-8", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=(
            "frame", "landmark", "x", "y", "visibility", "presence"))
        writer.writeheader()
        for frame, center in enumerate(centers):
            if center is None:
                continue
            for name, x, y in (
                ("LEFT_HIP", center - .02, .50),
                ("RIGHT_HIP", center + .02, .50),
                ("LEFT_SHOULDER", center - .02, .25),
                ("RIGHT_SHOULDER", center + .02, .25),
                ("LEFT_ANKLE", center - .02, .25 + heights[frame]),
                ("RIGHT_ANKLE", center + .02, .25 + heights[frame]),
            ):
                writer.writerow({"frame": frame, "landmark": name, "x": x, "y": y,
                                 "visibility": .95, "presence": .95})


class TrackingReliabilityTests(unittest.TestCase):
    def test_continuous_skeleton_is_reliable(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_analysis(folder, [.50, .505, .51, .52, .525])
            report = write_tracking_reliability(folder)
            self.assertEqual(report["status"], "reliable")
            self.assertEqual(report["track_breaks"], [])
            self.assertFalse(report["identity_switch_warning"])
            self.assertIsNone(report["identity_switch_confirmed"])
            saved = json.loads((folder / "tracking_reliability.json").read_text())
            self.assertEqual(saved["selected_frames"], 5)
            self.assertEqual(saved["source"]["geometry_processing"],
                             "raw observed landmarks only; no interpolation or smoothing")

    def test_short_rejection_is_a_track_break_but_not_a_confirmed_switch(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_analysis(folder, [.50, .505, None, .515, .52])
            report = evaluate_tracking_reliability(folder)
            self.assertEqual(report["status"], "partially_reliable")
            self.assertEqual(report["track_breaks"], [
                {"start_frame": 2, "end_frame": 2, "length_frames": 1}])
            self.assertFalse(report["identity_switch_warning"])
            self.assertIsNone(report["identity_switch_confirmed"])
            self.assertEqual(report["frames"][2]["center_xy"], None)

    def test_large_body_center_jump_warns_without_claiming_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_analysis(folder, [.50, .505, .51, .81, .815])
            report = evaluate_tracking_reliability(folder)
            self.assertEqual(report["status"], "partially_reliable")
            self.assertTrue(report["identity_switch_warning"])
            self.assertIsNone(report["identity_switch_confirmed"])
            self.assertIn("body_center_jump", [event["type"] for event in report["warning_events"]])

    def test_scale_discontinuity_warns_even_when_center_is_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_analysis(folder, [.50] * 5, heights=[.50, .50, .25, .50, .50])
            report = evaluate_tracking_reliability(folder)
            self.assertTrue(report["identity_switch_warning"])
            self.assertIn("skeleton_scale_jump", [event["type"] for event in report["warning_events"]])

    def test_no_selected_skeleton_is_unreliable(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_analysis(folder, [None, None, None])
            report = evaluate_tracking_reliability(folder)
            self.assertEqual(report["status"], "unreliable")
            self.assertEqual(report["longest_track_break_frames"], 3)

    def test_selected_frame_without_raw_hip_geometry_is_not_silently_reliable(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_analysis(folder, [.50, .51, .52])
            raw = folder / "pose_raw.csv"
            lines = raw.read_text().splitlines()
            raw.write_text("\n".join(line for line in lines if not line.startswith("1,LEFT_HIP,")
                                        and not line.startswith("1,RIGHT_HIP,")) + "\n")
            report = evaluate_tracking_reliability(folder)
            self.assertEqual(report["status"], "partially_reliable")
            self.assertIn("raw_hip_center_unavailable_in_selected_frames", report["reasons"])
            self.assertIn("raw_hip_center_unavailable", report["frames"][1]["warnings"])

    def test_incomplete_selection_trace_cannot_silently_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_analysis(folder, [.50, .51, .52])
            capture = folder / "pose_raw.capture.json"
            payload = json.loads(capture.read_text())
            payload["selection_frames"].pop()
            capture.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "Complete per-frame"):
                evaluate_tracking_reliability(folder)


if __name__ == "__main__":
    unittest.main()
