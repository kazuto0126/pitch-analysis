"""Event alignment shifts time without changing model samples or human labels."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from fractions import Fraction
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_motion_events as helpers
import test_native_motion_event_scope as scope_helpers
from pitch_analysis.analysis.native_motion_alignment import align_clip, write_native_alignment
from pitch_analysis.analysis.native_motion_events import describe_events
from pitch_analysis.cli import main


class AlignmentMathTests(unittest.TestCase):
    def fixture(self):
        events = {name: helpers.exact(frame) for name, frame in
                  zip(helpers.EVENT_NAMES, [0, 2, 3, 5, 7], strict=True)}
        events['approximate_release'] = helpers.ranged(4, 5)
        rows = helpers.rows()
        info = describe_events(events, Fraction(60000, 1001), rows)
        return {'pitch_id': 'fixture', 'frame_count': 8, 'fps_fraction': '60000/1001',
                'rows': rows, **info}

    def test_fractional_negative_and_zero_time_preserve_every_sample_and_original_fields(self):
        clip = self.fixture()
        original = deepcopy(clip)
        result = align_clip(clip)
        self.assertEqual(result['alignment_frame'], 3)
        self.assertEqual(len(result['aligned_rows']), 8)
        for row, aligned in zip(clip['rows'], result['aligned_rows'], strict=True):
            for key, value in row.items():
                self.assertEqual(aligned[key], value)
            expected = Fraction(row['frame_index'] - 3) / Fraction(60000, 1001)
            self.assertEqual(aligned['relative_timestamp_sec'], float(expected))
            self.assertEqual(Fraction(aligned['relative_timestamp_fraction']), expected)
        self.assertEqual(result['aligned_rows'][3]['relative_timestamp_sec'], 0)
        self.assertEqual(result['aligned_rows'][0]['relative_frame_index'], -3)
        result['aligned_rows'][0]['throwing_elbow_model_xy_deg'] = 999
        self.assertEqual(clip, original)

    def test_release_range_and_missing_values_are_not_replaced_or_interpolated(self):
        clip = self.fixture()
        clip['rows'][2].update(throwing_elbow_model_xy_deg=None,
                              throwing_elbow_coordinate_status='missing_coordinates')
        result = align_clip(clip)
        self.assertIsNone(result['aligned_rows'][2]['throwing_elbow_model_xy_deg'])
        event = result['aligned_events']['approximate_release']
        self.assertEqual(event['frame_bounds'], [4, 5])
        self.assertEqual(event['relative_frame_bounds'], [1, 2])
        self.assertIsNone(event['frame_index'])
        self.assertEqual(event['relative_seconds_bounds_fraction'], ['1001/60000', '1001/30000'])

    def test_uncertain_and_unobservable_events_retain_status_and_empty_bounds(self):
        clip = self.fixture()
        clip['events']['approximate_release']['status'] = 'uncertain'
        clip['events']['preparation_start'].update(status='not_observable', frame_index=None,
                                                  frame_bounds=None, time_bounds_sec=None)
        result = align_clip(clip)
        self.assertEqual(result['aligned_events']['approximate_release']['status'], 'uncertain')
        self.assertIsNone(result['aligned_events']['preparation_start']['relative_frame_bounds'])
        self.assertIsNone(result['aligned_events']['preparation_start']['relative_seconds_bounds'])

    def test_nonexact_or_invalid_anchor_cannot_be_assigned_a_zero(self):
        changes = [{'status': 'uncertain'}, {'frame_index': None}, {'frame_index': True},
                   {'frame_index': -1}, {'frame_index': 8},
                   {'frame_range': {'start_frame': 3, 'end_frame': 3}}]
        for change in changes:
            with self.subTest(change=change):
                clip = self.fixture()
                clip['events']['foot_plant'].update(change)
                with self.assertRaises(ValueError):
                    align_clip(clip)

    def test_incomplete_or_shifted_source_timeline_is_rejected(self):
        for change in ('row_count', 'duplicate_frame', 'source_time'):
            with self.subTest(change=change):
                clip = self.fixture()
                if change == 'row_count':
                    clip['rows'].pop()
                elif change == 'duplicate_frame':
                    clip['rows'][1]['frame_index'] = 0
                else:
                    clip['rows'][0]['timestamp_sec'] = 1
                with self.assertRaises(ValueError):
                    align_clip(clip)


class AlignmentExportTests(unittest.TestCase):
    def run_export(self, data):
        with patch('pitch_analysis.analysis.native_motion_alignment._plot',
                   side_effect=lambda _clips, _role, path: path.write_bytes(b'plot fixture')), \
             patch('subprocess.Popen', side_effect=AssertionError('no model or browser')), \
             patch('cv2.VideoCapture', side_effect=AssertionError('saved input only')):
            return write_native_alignment(data['root'], data['request_path'], data['comparison'])

    def test_export_preserves_all_source_csv_fields_and_does_not_write_sources(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = helpers.NativeMotionEventExportTests().fixture(Path(temp))
            before = {p: p.read_bytes() for p in data['root'].rglob('*') if p.is_file()}
            result = self.run_export(data)
            self.assertEqual((result['clip_count'], result['source_frames']), (1, 3))
            with (data['motion']/'motion_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
                source = list(csv.DictReader(stream))
            with (data['comparison']/'aligned_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
                aligned = list(csv.DictReader(stream))
            self.assertEqual(len(source), len(aligned))
            for original, current in zip(source, aligned, strict=True):
                for key, value in original.items():
                    self.assertEqual(current[key], value, key)
            self.assertEqual(aligned[1]['relative_timestamp_sec'], '0.0')
            for flag in ('angle_values_recomputed', 'samples_resampled', 'time_warped',
                         'smoothed', 'interpolated', 'event_midpoints_selected'):
                self.assertFalse(result[flag])
            self.assertEqual(result['new_inference_calls'], 0)
            self.assertIsNone(result['usable_for_analysis'])
            self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_event_only_checkpoint_supplies_exact_anchor_without_promoting_gt(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = scope_helpers.NativeMotionEventScopeTests().fixture(Path(temp))
            before = data['truth_path'].read_bytes()
            result = self.run_export(data)
            self.assertEqual(result['clips'][0]['event_review_scope']['kind'], 'event_only')
            self.assertFalse(result['clips'][0]['event_review_scope']['full_pose_gt_complete'])
            self.assertEqual(data['truth_path'].read_bytes(), before)

    def test_anchor_range_and_changed_source_fail_before_creating_output(self):
        for change in ('range', 'changed_source'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = helpers.NativeMotionEventExportTests().fixture(Path(temp))
                if change == 'range':
                    data['truth']['labels']['events']['foot_plant'] = helpers.ranged(1, 1)
                    helpers.NativeMotionEventExportTests.refresh(data)
                else:
                    with data['truth_path'].open('a', encoding='utf-8') as stream:
                        stream.write('\n')
                with self.assertRaises(ValueError):
                    self.run_export(data)
                self.assertFalse(data['comparison'].exists())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = helpers.NativeMotionEventExportTests().fixture(Path(temp))
            data['comparison'].mkdir()
            keep = data['comparison']/'keep.txt'
            keep.write_text('existing result', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                self.run_export(data)
            self.assertEqual(keep.read_text(encoding='utf-8'), 'existing result')


class AlignmentCliTests(unittest.TestCase):
    def test_cli_dispatches_saved_alignment_only(self):
        value = {'status': 'alignment_created', 'clip_count': 5, 'source_frames': 1684}
        with patch('sys.argv', ['pitch-analysis', 'align-native-motion', 'request.json', '--output', 'out']), \
             patch('pitch_analysis.analysis.native_motion_alignment.write_native_alignment', return_value=value) as writer, \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), 'request.json', 'out')
        self.assertIn('alignment_created', stream.getvalue())

    def test_cli_source_failure_has_nonzero_exit(self):
        with patch('sys.argv', ['pitch-analysis', 'align-native-motion', 'request.json', '--output', 'out']), \
             patch('pitch_analysis.analysis.native_motion_alignment.write_native_alignment', side_effect=ValueError('source changed')), \
             redirect_stdout(StringIO()) as stream, self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 1)
        self.assertIn('source changed', stream.getvalue())
