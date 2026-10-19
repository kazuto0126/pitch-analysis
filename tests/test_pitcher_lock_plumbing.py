"""Operator subject constraints reach capture without changing legacy calls."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_phase0_input as fixtures
from pitch_analysis.analysis.pitch import analyze_pitch
from pitch_analysis.workflow import prepare_segment


class PitcherLockPlumbingTests(unittest.TestCase):
    def test_analysis_records_constraint_and_preserves_candidate_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video, metadata, model = root / "pitch_001.mp4", root / "pitch_001.json", root / "model.task"
            fixtures.make_video(video)
            model.write_bytes(b"fixture model")
            metadata.write_text(json.dumps(fixtures.metadata("pitcher_a", "pitch_001", video.name)), encoding="utf-8")
            original_metadata = metadata.read_bytes()
            roi = (.1, .3, .7, .9)

            def prepare(*args, subject_roi, record_candidates, **kwargs):
                self.assertEqual(subject_roi, roi)
                self.assertTrue(record_candidates)
                result = fixtures.fake_prepare(*args, **kwargs)
                core = Path(args[1])
                trace = core / "pose_raw.candidates.jsonl"
                trace.write_text('{"frame_index":0,"candidates":[]}\n', encoding="utf-8")
                capture = core / "pose_raw.capture.json"
                payload = json.loads(capture.read_text(encoding="utf-8"))
                payload["subject_roi"] = list(subject_roi)
                payload["candidate_trace"] = {"path": str(trace), "record_count": 1}
                capture.write_text(json.dumps(payload), encoding="utf-8")
                return result

            with patch("pitch_analysis.analysis.pitch.prepare_segment", side_effect=prepare):
                result = analyze_pitch(video, metadata, output_root=root / "results", model_path=model,
                                       subject_roi=roi, record_candidates=True)
            output = Path(result["output_dir"])
            manifest = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["provenance"]["subject_selection"], "rear_centerfield_subject_roi_v1")
            self.assertEqual(manifest["provenance"]["subject_constraint"]["subject_roi"], list(roi))
            self.assertIn("pose_raw.candidates.jsonl", manifest["artifacts"])
            capture = json.loads((output / "pose_raw.capture.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(capture["candidate_trace"]["path"]), output / "pose_raw.candidates.jsonl")
            self.assertFalse((output / "core").exists())
            self.assertEqual(metadata.read_bytes(), original_metadata)

    def test_workflow_forwards_only_requested_opt_in_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number, roi in enumerate((None, (.1, .3, .7, .9))):
                with self.subTest(roi=roi), patch("pitch_analysis.workflow.extract_pose", return_value={"detected_frames": 0}) as capture:
                    prepare_segment("fixture.mp4", root / str(number), video_id="fixture", throwing_side="RIGHT",
                                    model_path="fixture.task", start_second=0, end_second=None,
                                    subject_selection="rear_centerfield_broadcast", subject_roi=roi,
                                    record_candidates=roi is not None)
                if roi is None:
                    self.assertNotIn("subject_roi", capture.call_args.kwargs)
                    self.assertNotIn("record_candidates", capture.call_args.kwargs)
                else:
                    self.assertEqual(capture.call_args.kwargs["subject_roi"], roi)
                    self.assertTrue(capture.call_args.kwargs["record_candidates"])


if __name__ == "__main__":
    unittest.main()
