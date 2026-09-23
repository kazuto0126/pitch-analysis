"""Input-quality triage tests use local generated video, never network media."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pitch_analysis.analysis.pitch import analyze_pitch
from pitch_analysis.contracts import validate_contract
from pitch_analysis.video.input_quality import refine_input_quality, scan_input_quality
from pitch_analysis.video.validation import validate_mp4


def _video(path: Path, *, cut: bool) -> None:
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (96, 96))
    assert writer.isOpened()
    for frame in range(30):
        image = np.zeros((96, 96, 3), dtype=np.uint8)
        image[:] = (25, 40, 170) if not cut or frame < 15 else (170, 40, 25)
        image[10:25, frame % 40:frame % 40 + 15] = (90, 100, 100)
        writer.write(image)
    writer.release()


class InputQualityTests(unittest.TestCase):
    def test_continuous_video_has_no_hard_cut(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "continuous.mp4"
            _video(path, cut=False)
            report = scan_input_quality(validate_mp4(path))
            validate_contract(report, "input-quality-v1")
            self.assertEqual(report["status"], "accepted")
            self.assertEqual(report["detected_shot_boundaries"], [])
            self.assertEqual(report["camera_view_consistency"], "declared_unverified")

    def test_hard_cut_is_rejected_before_pose_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "pitch_001.mp4"
            _video(path, cut=True)
            report = scan_input_quality(validate_mp4(path))
            validate_contract(report, "input-quality-v1")
            self.assertEqual(report["status"], "rejected")
            self.assertIn(15, [item["frame_index"] for item in report["detected_shot_boundaries"]])
            metadata = root / "pitch_001.json"
            metadata.write_text(json.dumps({"schema_version": "pitch-input-v1", "pitch_id": "pitch_001",
                                            "pitcher": {"id": "test_pitcher", "throws": "RIGHT"},
                                            "video": {"file": path.name, "camera_view": "rear_centerfield_broadcast",
                                                      "horizontal_mirror": False, "playback_speed": 1.0,
                                                      "contains_single_pitch": True, "continuous_shot": True,
                                                      "subject_framing": "full_body"}}), encoding="utf-8")
            model = root / "model.task"
            model.write_bytes(b"test model fixture")
            with patch("pitch_analysis.analysis.pitch.prepare_segment") as prepare:
                result = analyze_pitch(path, metadata, output_root=root / "results", model_path=model)
            prepare.assert_not_called()
            self.assertEqual(result["status"], "input_rejected")
            output = Path(result["output_dir"])
            self.assertFalse((output / "keypoints.json").exists())
            self.assertEqual(json.loads((output / "input_quality.json").read_text(encoding="utf-8"))["status"], "rejected")

    def test_long_static_run_is_only_suspected_replay(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "static.mp4"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (96, 96))
            self.assertTrue(writer.isOpened())
            frame = np.full((96, 96, 3), (20, 30, 80), dtype=np.uint8)
            for _ in range(40):
                writer.write(frame)
            writer.release()
            report = scan_input_quality(validate_mp4(path))
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["slow_motion_replay"], "freeze_or_replay_suspected")
            self.assertEqual(report["detected_shot_boundaries"], [])

    def test_post_pose_marks_missing_start_and_long_pose_gap(self):
        base = {"schema_version": "input-quality-v1", "stage": "video_preflight", "status": "accepted",
                "video_sha256": "a" * 64, "frame_count": 90, "fps": 30.0,
                "detected_shot_boundaries": [], "camera_continuity": "no_cut_detected",
                "camera_view_consistency": "declared_unverified", "longest_invalid_span_frames": None,
                "pose_selection_ratio": None, "possible_identity_switch": None, "identity_transitions": [],
                "start_completeness": "unknown", "followthrough_completeness": "unknown",
                "slow_motion_replay": "not_detected_not_excluded", "longest_near_duplicate_run_frames": 0,
                "reasons": [], "confidence": {"level": "low", "calibrated": False, "basis": "test"},
                "uncertainties": []}
        pose = {frame: {name: {"x": .5, "y": y, "visibility": .9, "presence": .9}
                        for name, y in (("LEFT_KNEE", .4), ("RIGHT_KNEE", .6),
                                        ("LEFT_SHOULDER", .2), ("RIGHT_SHOULDER", .2),
                                        ("LEFT_ANKLE", .8), ("RIGHT_ANKLE", .8))}
                for frame in range(35, 90)}
        capture = {"selection_frames": [{"frame_index": frame, "status": "selected" if frame in pose else "rejected"}
                                        for frame in range(90)]}
        result = refine_input_quality(base, capture, pose, throwing_side="RIGHT", quality_gate_passed=True)
        validate_contract(result, "input-quality-v1")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["longest_invalid_span_frames"], 35)
        self.assertEqual(result["start_completeness"], "incomplete")
        self.assertIn("missing_preparation_phase", result["reasons"])

    def test_confident_hip_jump_after_pose_gap_flags_possible_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "continuous.mp4"
            _video(path, cut=False)
            preflight = scan_input_quality(validate_mp4(path))
        pose = {frame: {name: {"x": .35 if frame < 12 else .75, "y": .5,
                              "visibility": .95, "presence": .95}
                        for name in ("LEFT_HIP", "RIGHT_HIP")}
                for frame in range(30) if frame != 11}
        capture = {"selection_frames": [{"frame_index": frame, "status": "selected" if frame != 11 else "rejected"}
                                        for frame in range(30)]}
        result = refine_input_quality(preflight, capture, pose, throwing_side="RIGHT", quality_gate_passed=True)
        self.assertEqual(result["status"], "rejected")
        self.assertTrue(result["possible_identity_switch"])
        self.assertEqual(result["identity_transitions"][0]["first_frame_after_gap"], 12)


if __name__ == "__main__":
    unittest.main()
