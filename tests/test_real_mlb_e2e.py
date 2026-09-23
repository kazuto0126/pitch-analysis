"""Opt-in positive E2E: requires 3–5 genuine prepared MLB single-pitch MP4s.

Set PITCH_ANALYSIS_REAL_BASELINE_DIR to a directory containing one pitcher's
MP4/JSON pairs. Missing material is a SKIP, never a synthetic positive pass.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pitch_analysis.contracts import load_input


BASELINE_DIR = os.environ.get("PITCH_ANALYSIS_REAL_BASELINE_DIR")


@unittest.skipUnless(BASELINE_DIR, "Set PITCH_ANALYSIS_REAL_BASELINE_DIR to 3–5 prepared real MLB single-pitch MP4/JSON pairs")
class RealMlbBaselineTests(unittest.TestCase):
    def test_three_to_five_real_pitch_positive_handoff(self):
        root = Path(BASELINE_DIR).resolve(strict=True)
        pairs = [(root / (path.stem + ".mp4"), path) for path in sorted(root.glob("*.json"))]
        self.assertGreaterEqual(len(pairs), 3, "Provide at least three real single-pitch MP4/JSON pairs")
        self.assertLessEqual(len(pairs), 5, "Phase 1 baseline is one pitcher with 3–5 clips")
        pitchers = {load_input(video, metadata)["pitcher"]["id"] for video, metadata in pairs}
        self.assertEqual(len(pitchers), 1)
        with tempfile.TemporaryDirectory() as temporary:
            for video, metadata in pairs:
                with self.subTest(video=video.name):
                    process = subprocess.run([sys.executable, "-B", "-m", "pitch_analysis.cli", "analyze-pitch",
                                              str(video), str(metadata), "--output-root", temporary],
                                             cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                             text=True, timeout=600)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    result = json.loads(process.stdout.strip().splitlines()[-1])
                    output = Path(result["output_dir"])
                    report = json.loads((output / "keypoint_quality.json").read_text(encoding="utf-8"))
                    self.assertGreater(report["frames_with_valid_pitcher_pose"], 0,
                                       "Real positive fixture must yield a selected pitcher pose")
                    self.assertIn(report["status"], ("success", "degraded"))
                    self.assertTrue((output / "overlay.mp4").is_file())
                    self.assertTrue((output / "metrics.json").is_file())
                    self.assertEqual(len((output / "keypoints.jsonl").read_text(encoding="utf-8").splitlines()),
                                     report["total_frames"])
                    self.assertEqual(len((output / "processed_keypoints.jsonl").read_text(encoding="utf-8").splitlines()),
                                     report["total_frames"])


if __name__ == "__main__":
    unittest.main()
