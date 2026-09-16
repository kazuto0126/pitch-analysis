import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pitch_analysis.workflow import rebuild_segment


class RebuildWorkflowTests(unittest.TestCase):
    def test_phase_quality_sidecar_moves_with_rebuilt_phase_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            segment = Path(directory)
            raw = segment / "pose_raw.csv"
            raw.write_text("placeholder", encoding="utf-8")
            raw.with_suffix(".capture.json").write_text(
                json.dumps({"fps": 30, "start_frame": 0, "end_frame": 20, "video": "sample.mp4"}),
                encoding="utf-8",
            )
            (segment / "events.json").write_text(
                json.dumps(
                    {
                        "throws": "RIGHT",
                        "review_status": "human_reviewed",
                        "events": {
                            "pitch_start": 1,
                            "peak_leg_lift": 5,
                            "foot_strike": 10,
                            "release": 15,
                            "follow_through_end": 20,
                        },
                    }
                ),
                encoding="utf-8",
            )

            def fake_build_phase(_features, _events, output, _columns):
                output = Path(output)
                output.write_text("phase data", encoding="utf-8")
                output.with_suffix(".quality.json").write_text("{}", encoding="utf-8")
                return {}

            feature_report = {
                "throwing_side": "RIGHT",
                "timeline_frames": 20,
            }
            gate = {"passed": True}
            with (
                patch("pitch_analysis.workflow.clean_pose", return_value={}),
                patch("pitch_analysis.workflow.build_features", return_value=feature_report),
                patch("pitch_analysis.workflow.quality_gate", return_value=gate),
                patch("pitch_analysis.workflow.build_phase_sequence", side_effect=fake_build_phase),
            ):
                result = rebuild_segment(segment)

            self.assertTrue((segment / "phase_sequence.csv").exists())
            self.assertTrue((segment / "phase_sequence.quality.json").exists())
            self.assertFalse((segment / "phase_sequence.rebuild.tmp.quality.json").exists())
            self.assertEqual(
                result["phase_sequence"]["quality_report"],
                str(segment / "phase_sequence.quality.json"),
            )


if __name__ == "__main__":
    unittest.main()
