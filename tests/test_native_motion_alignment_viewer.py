"""Aligned review packages retain bound source values and human uncertainty."""
from contextlib import redirect_stdout
import csv
from fractions import Fraction
from importlib.resources import files
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import test_native_analysis_input as input_helpers
import test_native_motion_events as helpers
import test_native_motion_event_scope as scope_helpers

from pitch_analysis.analysis.native_motion_alignment_viewer import write_alignment_viewer
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


class AlignmentViewerTests(unittest.TestCase):
    @staticmethod
    def embedded(target):
        html = (target / 'review_alignment.html').read_text(encoding='utf-8')
        content = html.split('<script id="motion-data" type="application/json">', 1)[1].split('</script>', 1)[0]
        return html, json.loads(content)['clips']

    @staticmethod
    def run_viewer(data, target):
        with patch('subprocess.Popen', side_effect=AssertionError('saved data only; no inference or browser')), \
             patch('cv2.VideoCapture', side_effect=AssertionError('no decode')), \
             patch('pitch_analysis.analysis.native_motion_report.describe_native_motion',
                   side_effect=AssertionError('do not recalculate saved angles')):
            return write_alignment_viewer(data['root'], data['request_path'], target)

    def test_package_preserves_original_rows_sources_and_base_player_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            original_fixture = input_helpers.NativeAnalysisInputTests.fixture

            def missing_fixture(instance, fixture_root):
                return original_fixture(instance, fixture_root, missing_joint=True)

            with patch.object(input_helpers.NativeAnalysisInputTests, 'fixture', new=missing_fixture):
                data = helpers.NativeMotionEventExportTests().fixture(root)
            before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
            target = root / 'analysis_results' / 'alignment_viewer'
            result = self.run_viewer(data, target)
            html, clips = self.embedded(target)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertEqual(set(path.name for path in target.iterdir()), {
                'review_alignment.html', 'motion_viewer.js', 'motion_alignment.js', 'alignment_viewer_manifest.json'})
            self.assertEqual((result['clip_count'], result['source_frames']), (1, 3))
            self.assertEqual(read_json(target / 'alignment_viewer_manifest.json'), result)
            clip = clips[0]
            self.assertEqual((clip['fps_fraction'], clip['alignment_frame']), ('60000/1001', 1))
            self.assertNotIn('aligned_rows', clip)
            with (data['motion'] / 'motion_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
                source = list(csv.DictReader(stream))
            self.assertEqual(len(clip['rows']), len(source))
            for original, row in zip(source, clip['rows'], strict=True):
                self.assertEqual(row['frame_index'], int(original['frame_index']))
                self.assertEqual(row['timestamp_sec'], float(original['timestamp_sec']))
                for role in ('throwing_elbow', 'lead_knee'):
                    angle = original[f'{role}_model_xy_deg']
                    self.assertEqual(row[f'{role}_model_xy_deg'], float(angle) if angle else None)
                    self.assertEqual(row[f'{role}_coordinate_status'], original[f'{role}_coordinate_status'])
            self.assertIsNone(clip['rows'][1]['throwing_elbow_model_xy_deg'])
            self.assertEqual(clip['rows'][1]['throwing_elbow_coordinate_status'], 'missing_coordinates')
            self.assertEqual((target / unquote(clip['overlay_url'])).resolve(),
                             (root / clip['source_refs']['overlay_ref']['path']).resolve())
            for name in helpers.EVENT_NAMES:
                for key, value in data['truth']['labels']['events'][name].items():
                    self.assertEqual(clip['events'][name][key], value)
            self.assertEqual(clip['aligned_events']['foot_plant']['relative_seconds_bounds'], [0., 0.])
            for asset, source_name in [('motion_viewer.js', 'native_motion_viewer.js'),
                                       ('motion_alignment.js', 'native_motion_alignment.js')]:
                self.assertEqual((target / asset).read_bytes(),
                                 files('pitch_analysis').joinpath(f'review_assets/{source_name}').read_bytes())
            self.assertLess(html.index('src="motion_viewer.js"'), html.index('src="motion_alignment.js"'))
            for key in ('html_ref', 'script_ref', 'alignment_script_ref'):
                self.assertEqual(reference(root, root / result[key]['path']), result[key])
            for flag in ('base_player_modified', 'samples_resampled', 'angle_values_recomputed',
                         'event_midpoints_selected', 'browser_interaction_verified'):
                self.assertFalse(result[flag])
            self.assertEqual(result['new_inference_calls'], 0)
            self.assertEqual(result['new_ground_truth_labels'], 0)
            self.assertIsNone(result['usable_for_analysis'])

    def test_event_only_scope_keeps_null_uncertain_unobservable_and_release_range(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            helper = scope_helpers.NativeMotionEventScopeTests()
            data = helper.fixture(Path(temp))
            events = data['truth']['labels']['events']
            events['preparation_start'] = {'status': 'not_observable', 'frame_index': None,
                                            'confidence': None, 'note': 'Before source clip'}
            events['leg_lift'] = helpers.ranged(0, 0, status='uncertain')
            helper.refresh_truth_and_checkpoint(data)
            before = {path: path.read_bytes() for path in data['root'].rglob('*') if path.is_file()}
            target = data['root'] / 'analysis_results' / 'alignment_viewer'
            self.run_viewer(data, target)
            _, clips = self.embedded(target)
            clip = clips[0]
            self.assertEqual(clip['event_review_scope']['kind'], 'event_only')
            self.assertFalse(clip['event_review_scope']['full_pose_gt_complete'])
            self.assertEqual(clip['event_review_scope']['annotation_status'], 'in_progress')
            for name, original in events.items():
                for key, value in original.items():
                    self.assertEqual(clip['events'][name][key], value)
                    self.assertEqual(clip['aligned_events'][name][key], value)
            release = clip['aligned_events']['approximate_release']
            self.assertEqual(release['marker_kind'], 'range')
            self.assertIsNone(release['frame_index'])
            self.assertEqual(release['frame_bounds'], [1, 2])
            self.assertEqual(release['relative_frame_bounds'], [0, 1])
            self.assertEqual(release['relative_seconds_bounds_fraction'], ['0', '1001/60000'])
            self.assertEqual(release['relative_seconds_bounds'], [0., float(Fraction(1001, 60000))])
            self.assertEqual(clip['aligned_events']['leg_lift']['marker_kind'], 'uncertain')
            self.assertIsNone(clip['aligned_events']['preparation_start']['relative_frame_bounds'])
            self.assertIsNone(clip['aligned_events']['preparation_start']['relative_seconds_bounds'])
            self.assertEqual(clip['pointwise_reliability'], 'unknown')
            self.assertIsNone(clip['usable_for_analysis'])
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_human_notes_cannot_end_the_embedded_json_script(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = helpers.NativeMotionEventExportTests().fixture(Path(temp))
            note = '</script><script>alert("human note")</script>&\u2028\u2029'
            data['truth']['labels']['events']['foot_plant']['note'] = note
            helpers.NativeMotionEventExportTests.refresh(data)
            target = data['root'] / 'analysis_results' / 'alignment_viewer'
            self.run_viewer(data, target)
            html, clips = self.embedded(target)
            self.assertNotIn(note, html)
            self.assertNotIn('<script>alert', html)
            self.assertNotIn('\u2028', html)
            self.assertNotIn('\u2029', html)
            self.assertEqual(clips[0]['events']['foot_plant']['note'], note)
            self.assertEqual(clips[0]['aligned_events']['foot_plant']['note'], note)

    def test_changed_source_wrong_identity_and_nonexact_anchor_fail_before_output(self):
        for change in ('source', 'identity', 'range', 'uncertain', 'unobservable'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = helpers.NativeMotionEventExportTests().fixture(Path(temp))
                if change == 'source':
                    data['video'].write_bytes(data['video'].read_bytes() + b'changed')
                elif change == 'identity':
                    data['truth']['source_video']['pitch_id'] = 'another_pitch'
                    helpers.NativeMotionEventExportTests.refresh(data)
                else:
                    event = {'range': helpers.ranged(1, 1),
                             'uncertain': {**helpers.exact(1), 'status': 'uncertain'},
                             'unobservable': {'status': 'not_observable', 'frame_index': None,
                                              'confidence': None, 'note': 'Cannot see plant'}}[change]
                    data['truth']['labels']['events']['foot_plant'] = event
                    helpers.NativeMotionEventExportTests.refresh(data)
                target = data['root'] / 'analysis_results' / 'rejected'
                with self.assertRaises(ValueError):
                    self.run_viewer(data, target)
                self.assertFalse(target.exists())

    def test_event_only_checkpoint_is_required_and_must_bind_the_same_source(self):
        for change in ('missing_checkpoint', 'wrong_source'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                helper = scope_helpers.NativeMotionEventScopeTests()
                data = helper.fixture(Path(temp))
                if change == 'missing_checkpoint':
                    data['request']['clips'][0].pop('event_review_ref')
                    helper.overwrite(data['request_path'], data['request'])
                else:
                    data['checkpoint']['source_video_ref']['sha256'] = '0' * 64
                    helper.refresh_checkpoint(data)
                target = data['root'] / 'analysis_results' / 'rejected'
                with self.assertRaises(ValueError):
                    self.run_viewer(data, target)
                self.assertFalse(target.exists())

    def test_existing_output_is_preserved_and_output_stays_inside_analysis_results(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = helpers.NativeMotionEventExportTests().fixture(Path(temp))
            target = data['root'] / 'analysis_results' / 'alignment_viewer'
            self.run_viewer(data, target)
            before = {path: path.read_bytes() for path in target.iterdir()}
            with self.assertRaises(FileExistsError):
                self.run_viewer(data, target)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            outside = data['root'] / 'outside'
            with self.assertRaises(ValueError):
                self.run_viewer(data, outside)
            self.assertFalse(outside.exists())


class AlignmentViewerCliTests(unittest.TestCase):
    def test_cli_dispatches_config_and_output_without_inference(self):
        result = {'status': 'alignment_viewer_created', 'clip_count': 5, 'source_frames': 1684}
        with patch('sys.argv', ['pitch-analysis', 'review-native-motion-alignment', 'request.json', '--output', 'out']), \
             patch('pitch_analysis.analysis.native_motion_alignment_viewer.write_alignment_viewer',
                   return_value=result) as writer, \
             patch('pitch_analysis.cli.extract_pose', side_effect=AssertionError('no model')), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), 'request.json', 'out')
        emitted = json.loads(stream.getvalue())
        self.assertEqual((emitted['status'], emitted['source_frames']), ('alignment_viewer_created', 1684))
        self.assertEqual(emitted['new_inference_calls'], 0)

    def test_cli_source_failure_returns_nonzero_exit(self):
        with patch('sys.argv', ['pitch-analysis', 'review-native-motion-alignment', 'request.json', '--output', 'out']), \
             patch('pitch_analysis.analysis.native_motion_alignment_viewer.write_alignment_viewer',
                   side_effect=ValueError('source changed')), \
             redirect_stdout(StringIO()) as stream, self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {'status': 'failed', 'error': 'source changed'})


if __name__ == '__main__':
    unittest.main()
