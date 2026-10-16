"""The additive hint artifact must not alter established analysis decisions."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from pitch_analysis.analysis.pitch import analyze_pitch
from test_phase0_input import fake_prepare, make_video, metadata


class MajorHintIntegrationTests(unittest.TestCase):
    def test_analysis_emits_hint_artifact_without_changing_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); video=root/'pitch_001.mp4'; make_video(video)
            meta=root/'pitch_001.json'; meta.write_text(json.dumps(metadata('fixture','pitch_001',video.name)))
            model=root/'model.task'; model.write_bytes(b'fixture')
            with patch('pitch_analysis.analysis.pitch.prepare_segment',side_effect=fake_prepare):
                result=analyze_pitch(video,meta,output_root=root/'outputs',model_path=model)
            output=Path(result['output_dir'])
            manifest=json.loads((output/'analysis.json').read_text())
            hint=json.loads((output/'major_review_hints.json').read_text())
            self.assertEqual(manifest['artifacts']['major_review_hints.json'],'major_review_hints.json')
            self.assertEqual(result['status'],'quality_gate_failed')
            self.assertFalse(result['quality_gate_passed'])
            self.assertEqual(hint['status'],'not_evaluated')
            self.assertEqual(len(hint['frames']),12)
            self.assertTrue(all(f['review_required'] is None for f in hint['frames']))
            self.assertTrue((output/'overlay.mp4').is_file())
            self.assertTrue((output/'pose_raw.csv').is_file())

    def test_packaged_evidence_is_declared(self):
        import tomllib
        root=Path(__file__).resolve().parents[1]
        config=tomllib.loads((root/'pyproject.toml').read_text())
        self.assertIn('review_evidence/*.json',config['tool']['setuptools']['package-data']['pitch_analysis'])


if __name__=='__main__': unittest.main()
