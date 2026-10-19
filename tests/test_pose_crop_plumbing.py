"""Explicit model crops reach capture with original-image provenance intact."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_phase0_input as fixtures
from pitch_analysis.analysis.pitch import analyze_pitch
from pitch_analysis.config import QualityConfig
from pitch_analysis.contracts import validate_contract
from pitch_analysis.pose_crop import build_input_transform
from pitch_analysis.workflow import prepare_segment


class PoseCropPlumbingTests(unittest.TestCase):
    def test_workflow_forwards_explicit_crop_and_keeps_original_roi_independent(self):
        crop, roi = (.1, .15, .8, .95), (.25, .25, .6, .7)
        with tempfile.TemporaryDirectory() as directory:
            for number, setting in enumerate((None, crop)):
                with self.subTest(crop=setting), patch(
                    "pitch_analysis.workflow.extract_pose", return_value={"detected_frames": 0}
                ) as capture:
                    prepare_segment("fixture.mp4", Path(directory) / str(number),
                                    video_id="fixture", throwing_side="RIGHT",
                                    model_path="fixture.task", start_second=0, end_second=None,
                                    subject_selection="rear_centerfield_broadcast",
                                    subject_roi=roi, record_candidates=True, input_crop=setting)
                    self.assertEqual(capture.call_args.kwargs["subject_roi"], roi)
                    self.assertTrue(capture.call_args.kwargs["record_candidates"])
                    if setting is None:
                        self.assertNotIn("input_crop", capture.call_args.kwargs)
                    else:
                        self.assertEqual(capture.call_args.kwargs["input_crop"], crop)

    def test_invalid_crop_rejected_before_workflow_creates_output_or_calls_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "invalid"
            with patch("pitch_analysis.workflow.extract_pose") as capture:
                with self.assertRaises(ValueError):
                    prepare_segment("fixture.mp4", output, video_id="fixture", throwing_side="RIGHT",
                                    model_path="fixture.task", start_second=0, end_second=None,
                                    input_crop=(.8, .1, .2, .9))
                capture.assert_not_called()
                self.assertFalse(output.exists())

    def test_invalid_crop_rejected_before_analysis_reads_input_or_creates_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "invalid"
            with patch("pitch_analysis.analysis.pitch.load_input") as load:
                with self.assertRaises(ValueError):
                    analyze_pitch("missing.mp4", "missing.json", output_root=output,
                                  input_crop=(0, False, 1, 1))
                load.assert_not_called()
                self.assertFalse(output.exists())

    def _analyze(self, root, *, crop=None, roi=None):
        video, metadata, model = root / "pitch_001.mp4", root / "pitch_001.json", root / "model.task"
        fixtures.make_video(video)
        model.write_bytes(b"fixture model")
        metadata.write_text(json.dumps(fixtures.metadata("pitcher_a", "pitch_001", video.name)), encoding="utf-8")
        original_metadata = metadata.read_bytes()

        def prepare(*args, **kwargs):
            if crop is None:
                self.assertNotIn("input_crop", kwargs)
            else:
                self.assertEqual(kwargs.pop("input_crop"), crop)
            if roi is None:
                self.assertNotIn("subject_roi", kwargs)
            else:
                self.assertEqual(kwargs.pop("subject_roi"), roi)
            return fixtures.fake_prepare(*args, **kwargs)

        with patch("pitch_analysis.analysis.pitch.prepare_segment", side_effect=prepare):
            result = analyze_pitch(video, metadata, output_root=root / "results", model_path=model,
                                   input_crop=crop, subject_roi=roi)
        self.assertEqual(metadata.read_bytes(), original_metadata)
        return json.loads((Path(result["output_dir"]) / "analysis.json").read_text(encoding="utf-8"))

    def test_analysis_crop_provenance_records_exact_transform_and_original_roi(self):
        crop, roi = (.1, .15, .8, .95), (.25, .25, .6, .7)
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._analyze(Path(directory), crop=crop, roi=roi)
        provenance = manifest["provenance"]
        self.assertEqual(provenance["subject_constraint"]["subject_roi"], list(roi))
        self.assertEqual(provenance["subject_constraint"]["model_input"],
                         "explicit operator crop; predictions mapped to original image")
        model_crop = provenance["model_input_crop"]
        self.assertEqual(model_crop["input_crop"], list(crop))
        self.assertEqual(model_crop["coordinate_system"], "original_image_normalized_xy")
        self.assertIn("caller-supplied operator crop", model_crop["source"])
        self.assertEqual(model_crop["input_transform"], build_input_transform(crop, 96, 128))
        self.assertEqual(model_crop["input_transform"]["pixel_bounds_xyxy"], [9, 19, 77, 122])
        self.assertAlmostEqual(model_crop["input_transform"]["z_scale"], 68 / 96)
        self.assertIn("native_x", model_crop["x_mapping"])
        self.assertIn("native_y", model_crop["y_mapping"])
        self.assertIn("native_z * actual_crop_width / original_width", model_crop["z_mapping"])
        self.assertIn("not calibrated 3D", model_crop["z_mapping"])
        self.assertEqual(provenance["quality_config"], vars(QualityConfig()))
        validate_contract(manifest, "pitch-analysis-v1")

    def test_crop_can_be_requested_without_subject_roi(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._analyze(Path(directory), crop=(0, 0, .8, 1))
        provenance = manifest["provenance"]
        self.assertEqual(provenance["subject_selection"], "rear_centerfield_v1")
        self.assertNotIn("subject_constraint", provenance)
        self.assertIn("model_input_crop", provenance)
        self.assertEqual(provenance["candidate_recording"], "all model candidates before subject selection")

    def test_default_analysis_omits_crop_and_retains_original_model_input_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._analyze(Path(directory), roi=(.1, .2, .8, .9))
        provenance = manifest["provenance"]
        self.assertNotIn("model_input_crop", provenance)
        self.assertEqual(provenance["subject_constraint"]["model_input"],
                         "unchanged full original image; no crop or coordinate transform")

    def test_schema_only_accepts_declared_model_input_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._analyze(Path(directory), crop=(0, 0, .8, 1), roi=(.1, .2, .7, .9))
        changed = deepcopy(manifest)
        changed["provenance"]["subject_constraint"]["model_input"] = "unknown remapping"
        with self.assertRaises(ValueError):
            validate_contract(changed, "pitch-analysis-v1")
        changed = deepcopy(manifest)
        changed["provenance"]["model_input_crop"]["source"] = "automatically inferred identity"
        with self.assertRaises(ValueError):
            validate_contract(changed, "pitch-analysis-v1")


if __name__ == "__main__":
    unittest.main()
