"""Native curve export preserves sources and keeps descriptive scope explicit."""
from contextlib import redirect_stdout
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_analysis_input as fixtures
from pitch_analysis.analysis.native_motion_report import write_native_motion
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


class NativeMotionReportTests(unittest.TestCase):
    def test_export_keeps_complete_missing_rows_usable_null_and_source_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            helper = fixtures.NativeAnalysisInputTests()
            data = helper.fixture(Path(temp), missing_joint=True)
            helper.prepare(data)
            before = {path: path.read_bytes() for path in data['root'].rglob('*') if path.is_file()}
            output = data['root'] / 'analysis_results' / 'motion'
            with patch('cv2.VideoCapture', side_effect=AssertionError('no video capture')), \
                 patch('pitch_analysis.native_seeded_track.associate_saved_boxes', side_effect=AssertionError('no track replay')):
                result = write_native_motion(data['root'], data['output'], output)
            self.assertEqual(result['total_frames'], 3)
            self.assertEqual(result['scope'], 'descriptive_model_xy_projection')
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            with (output / 'motion_curves.csv').open(newline='', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row['frame_index'] for row in rows], ['0', '1', '2'])
            self.assertEqual(rows[1]['throwing_elbow_model_xy_deg'], '')
            self.assertTrue(all(row['throwing_elbow_usable_deg'] == row['lead_knee_usable_deg'] == '' for row in rows))
            summary = read_json(output / 'motion_summary.json')
            self.assertEqual(summary['curves']['throwing_elbow']['missing'], 1)
            self.assertIn('review_ref', summary['source_refs'])
            for ref in summary['artifacts'].values():
                self.assertEqual(reference(data['root'], data['root'] / ref['path']), ref)
            self.assertEqual((output / 'motion_curves.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(summary['new_inference_calls'], 0)
            self.assertIsNone(summary['usable_for_analysis'])

    def test_changed_source_existing_and_external_output_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            helper = fixtures.NativeAnalysisInputTests()
            data = helper.fixture(Path(temp))
            helper.prepare(data)
            output = data['root'] / 'analysis_results' / 'exists'
            output.mkdir()
            with self.assertRaises(FileExistsError):
                write_native_motion(data['root'], data['output'], output)
            outside = data['root'] / 'outside'
            with self.assertRaisesRegex(ValueError, 'inside'):
                write_native_motion(data['root'], data['output'], outside)
            self.assertFalse(outside.exists())
            data['video'].write_bytes(b'not the accepted source')
            target = data['root'] / 'analysis_results' / 'changed'
            with self.assertRaisesRegex(ValueError, 'Changed or external source'):
                write_native_motion(data['root'], data['output'], target)
            self.assertFalse(target.exists())

    def test_cli_dispatch_keeps_legacy_processing_separate(self):
        result = {'status': 'descriptive_motion_complete', 'pitch_id': 'fixture', 'total_frames': 3}
        with patch('sys.argv', ['pitch-analysis', 'describe-native-motion', 'bundle', '--output', 'analysis_results/new']), \
             patch('pitch_analysis.analysis.native_motion_report.write_native_motion', return_value=result) as writer, \
             patch('pitch_analysis.cli.extract_pose', side_effect=AssertionError('no inference')), \
             redirect_stdout(StringIO()) as output:
            main()
        writer.assert_called_once_with(Path.cwd(), 'bundle', 'analysis_results/new')
        self.assertEqual(json.loads(output.getvalue())['status'], 'descriptive_motion_complete')

    def test_cli_rejection_is_nonzero(self):
        with patch('sys.argv', ['pitch-analysis', 'describe-native-motion', 'bundle', '--output', 'analysis_results/new']), \
             patch('pitch_analysis.analysis.native_motion_report.write_native_motion', side_effect=ValueError('source mismatch')), \
             redirect_stdout(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
