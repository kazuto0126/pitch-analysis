"""Saved exports become a viewer without changing numeric or source evidence."""
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
from pitch_analysis.analysis.native_motion_viewer import write_motion_viewer
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


class NativeMotionViewerTests(unittest.TestCase):
    def fixture(self, root):
        helper = fixtures.NativeAnalysisInputTests()
        data = helper.fixture(root, missing_joint=True)
        helper.prepare(data)
        motion = root / 'analysis_results' / 'motion'
        write_native_motion(root, data['output'], motion)
        return data, motion

    def test_embedded_data_retains_null_and_complete_rational_timeline_without_recalculation(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            data, motion = self.fixture(root)
            before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
            target = root / 'analysis_results' / 'viewer'
            with patch('pitch_analysis.analysis.native_motion_report.describe_native_motion', side_effect=AssertionError('no recompute')), \
                 patch('cv2.VideoCapture', side_effect=AssertionError('no decode')):
                result = write_motion_viewer(root, [motion], target)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            text = (target / 'review_motion.html').read_text(encoding='utf-8')
            content = text.split('<script id="motion-data" type="application/json">', 1)[1].split('</script>', 1)[0]
            clip = json.loads(content)['clips'][0]
            self.assertEqual(clip['frame_count'], 3)
            self.assertEqual(clip['fps_fraction'], '60000/1001')
            self.assertEqual([row['frame_index'] for row in clip['rows']], [0, 1, 2])
            self.assertEqual(clip['rows'][0]['timestamp_sec'], 0)
            self.assertIsNone(clip['rows'][1]['throwing_elbow_model_xy_deg'])
            self.assertEqual(clip['rows'][1]['throwing_elbow_coordinate_status'], 'missing_coordinates')
            self.assertEqual(result['clip_count'], 1)
            self.assertEqual(result['new_inference_calls'], 0)
            self.assertFalse(result['angle_values_recomputed'])
            self.assertFalse(result['browser_interaction_verified'])
            self.assertIsNone(result['usable_for_analysis'])
            for key in ('html_ref', 'script_ref'):
                self.assertEqual(reference(root, root / result[key]['path']), result[key])

    def test_changed_export_and_changed_accepted_source_are_rejected(self):
        for changed in ('csv', 'source'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                root = Path(temp)
                data, motion = self.fixture(root)
                path = motion / 'motion_curves.csv' if changed == 'csv' else data['video']
                path.write_bytes(path.read_bytes() + b'changed')
                target = root / 'analysis_results' / 'rejected'
                with self.assertRaisesRegex(ValueError, 'Changed or external source'):
                    write_motion_viewer(root, [motion], target)
                self.assertFalse(target.exists())

    def test_even_rehashed_csv_must_preserve_frame_time_state_and_counts(self):
        for changed in ('frame', 'time', 'null', 'count'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                root = Path(temp)
                _, motion = self.fixture(root)
                path = motion / 'motion_curves.csv'
                with path.open(newline='', encoding='utf-8') as stream:
                    reader = csv.DictReader(stream)
                    fields, rows = reader.fieldnames, list(reader)
                if changed == 'frame':
                    rows[1]['frame_index'] = '3'
                elif changed == 'time':
                    rows[1]['timestamp_sec'] = '0.02'
                elif changed == 'null':
                    rows[1]['throwing_elbow_model_xy_deg'] = '80'
                else:
                    rows.pop()
                with path.open('w', newline='', encoding='utf-8') as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader(); writer.writerows(rows)
                summary_path = motion / 'motion_summary.json'
                summary = read_json(summary_path)
                summary['artifacts']['curves_ref'] = reference(root, path)
                summary_path.write_text(json.dumps(summary), encoding='utf-8')
                target = root / 'analysis_results' / 'rejected'
                with self.assertRaises(ValueError):
                    write_motion_viewer(root, [motion], target)
                self.assertFalse(target.exists())

    def test_fresh_output_single_identity_and_project_boundary(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            _, motion = self.fixture(root)
            target = root / 'analysis_results' / 'viewer'
            write_motion_viewer(root, [motion], target)
            before = {path: path.read_bytes() for path in target.iterdir()}
            with self.assertRaises(FileExistsError):
                write_motion_viewer(root, [motion], target)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            with self.assertRaisesRegex(ValueError, 'inside'):
                write_motion_viewer(root, [motion], root / 'outside')
            with self.assertRaisesRegex(ValueError, 'Duplicate pitch'):
                write_motion_viewer(root, [motion, motion], root / 'analysis_results' / 'duplicate')

    def test_cli_only_dispatches_saved_motion_exports(self):
        with patch('sys.argv', ['pitch-analysis', 'review-native-motion', 'p1', 'p2', '--output', 'analysis_results/v']), \
             patch('pitch_analysis.analysis.native_motion_viewer.write_motion_viewer',
                   return_value={'status': 'viewer_created', 'clip_count': 2, 'source_frames': 9}) as writer, \
             patch('pitch_analysis.cli.extract_pose', side_effect=AssertionError('no model')), \
             redirect_stdout(StringIO()) as output:
            main()
        writer.assert_called_once_with(Path.cwd(), ['p1', 'p2'], 'analysis_results/v')
        self.assertEqual(json.loads(output.getvalue())['source_frames'], 9)

    def test_cli_rejects_inconsistent_source(self):
        with patch('sys.argv', ['pitch-analysis', 'review-native-motion', 'bad', '--output', 'analysis_results/v']), \
             patch('pitch_analysis.analysis.native_motion_viewer.write_motion_viewer', side_effect=ValueError('source mismatch')), \
             redirect_stdout(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
