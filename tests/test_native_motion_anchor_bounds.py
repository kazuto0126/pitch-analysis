"""Human foot-plant ranges bound display time without selecting a new event."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import csv
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_motion_events as helpers
from pitch_analysis.analysis.native_motion_alignment import align_clip, write_native_alignment
from pitch_analysis.analysis.native_motion_anchor_bounds import describe_anchor_bounds, write_bounded_alignment
from pitch_analysis.analysis.native_motion_events import describe_events, load_event_clips
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json


class AnchorBoundsMathTests(unittest.TestCase):
    def fixture(self, anchor):
        events = {name: helpers.exact(frame) for name, frame in
                  zip(helpers.EVENT_NAMES, [0, 1, 3, 5, 7], strict=True)}
        events['foot_plant'] = anchor
        values = helpers.rows()
        return {'pitch_id': 'fixture', 'frame_count': len(values), 'fps_fraction': '60000/1001',
                'rows': values, **describe_events(events, Fraction(60000, 1001), values)}

    def test_exact_anchor_has_identical_lower_and_upper_coordinates(self):
        clip = self.fixture(helpers.exact(3))
        result, exact = describe_anchor_bounds(clip), align_clip(clip)
        self.assertEqual(result['origin_status'], 'exact')
        self.assertEqual(result['origin_frame_bounds'], [3, 3])
        self.assertEqual(result['origin_candidates'], [3])
        for bounded, shifted in zip(result['bounded_rows'], exact['aligned_rows'], strict=True):
            self.assertEqual(bounded['relative_frame_bounds'], [shifted['relative_frame_index']] * 2)
            self.assertEqual(bounded['relative_seconds_bounds'], [shifted['relative_timestamp_sec']] * 2)
            self.assertEqual(bounded['relative_seconds_bounds_fraction'],
                             [shifted['relative_timestamp_fraction']] * 2)

    def test_single_frame_range_remains_bounded_without_an_exact_event(self):
        clip = self.fixture(helpers.ranged(3, 3))
        result = describe_anchor_bounds(clip)
        self.assertEqual(result['origin_status'], 'bounded')
        self.assertEqual(result['origin_frame_bounds'], [3, 3])
        self.assertEqual(result['origin_candidates'], [3])
        self.assertEqual(result['events'], clip['events'])
        self.assertEqual(result['events']['foot_plant']['marker_kind'], 'range')
        self.assertIsNone(result['events']['foot_plant']['frame_index'])
        self.assertEqual(result['bounded_rows'][3]['relative_frame_bounds'], [0, 0])

    def test_every_integer_origin_contributes_to_fractional_negative_time_bounds(self):
        clip = self.fixture(helpers.ranged(2, 4))
        result = describe_anchor_bounds(clip)
        fps = Fraction(60000, 1001)
        self.assertEqual(result['origin_status'], 'bounded')
        self.assertEqual(result['origin_frame_bounds'], [2, 4])
        self.assertEqual(result['origin_candidates'], [2, 3, 4])
        for row in result['bounded_rows']:
            frame = row['frame_index']
            possibilities = [Fraction(frame - origin) / fps for origin in (2, 3, 4)]
            expected = [min(possibilities), max(possibilities)]
            self.assertEqual(row['relative_frame_bounds'], [frame - 4, frame - 2])
            self.assertEqual(row['relative_seconds_bounds'], [float(value) for value in expected])
            self.assertEqual(row['relative_seconds_bounds_fraction'], [str(value) for value in expected])
        self.assertEqual(result['bounded_rows'][0]['relative_seconds_bounds_fraction'],
                         ['-1001/15000', '-1001/30000'])
        self.assertEqual(result['bounded_rows'][3]['relative_frame_bounds'], [-1, 1])

    def test_uncertain_candidates_and_unobservable_anchors_never_supply_origins(self):
        anchors = [helpers.ranged(2, 4, status='uncertain'),
                   {'status': 'uncertain', 'frame_index': None, 'confidence': None,
                    'note': 'No confirmed location'},
                   *[{'status': status, 'frame_index': None, 'confidence': None,
                      'note': 'Foot plant cannot be observed'}
                     for status in ('not_observable', 'not_visible')]]
        for anchor in anchors:
            with self.subTest(anchor=anchor):
                clip = self.fixture(anchor)
                result = describe_anchor_bounds(clip)
                self.assertEqual(result['origin_status'], 'unavailable')
                self.assertIsNone(result['origin_frame_bounds'])
                self.assertEqual(result['origin_candidates'], [])
                self.assertEqual(result['events'], clip['events'])
                self.assertEqual(result['timing'], clip['timing'])
                self.assertEqual(len(result['bounded_rows']), clip['frame_count'])
                for row in result['bounded_rows']:
                    for field in ('relative_frame_bounds', 'relative_seconds_bounds',
                                  'relative_seconds_bounds_fraction'):
                        self.assertIsNone(row[field], field)

    def test_source_fields_missing_values_and_nested_human_labels_are_deep_copied(self):
        clip = self.fixture(helpers.ranged(2, 4))
        clip['rows'][2].update(throwing_elbow_model_xy_deg=None,
                              throwing_elbow_coordinate_status='missing_coordinates')
        original = deepcopy(clip)
        result = describe_anchor_bounds(clip)
        self.assertEqual(result['rows'], original['rows'])
        self.assertEqual(result['events'], original['events'])
        self.assertEqual(result['timing'], original['timing'])
        for source, bounded in zip(clip['rows'], result['bounded_rows'], strict=True):
            for field, value in source.items():
                self.assertEqual(bounded[field], value, field)
        self.assertIsNone(result['bounded_rows'][2]['throwing_elbow_model_xy_deg'])
        self.assertTrue(all(row['throwing_elbow_usable_deg'] is None for row in result['bounded_rows']))
        result['bounded_rows'][2]['throwing_elbow_model_xy_deg'] = 90
        result['rows'][0]['timestamp_sec'] = 999
        result['events']['foot_plant']['frame_range']['start_frame'] = 999
        result['timing']['foot_plant_to_release']['frame_bounds'][0] = 999
        self.assertEqual(clip, original)


class AnchorBoundsExportTests(unittest.TestCase):
    def fixture(self, root, anchor, *, missing_joint=False):
        fixture_class = helpers.fixtures.NativeAnalysisInputTests
        original_fixture = fixture_class.fixture
        with patch.object(fixture_class, 'fixture', autospec=True,
                          side_effect=lambda helper, path: original_fixture(helper, path, missing_joint=missing_joint)):
            data = helpers.NativeMotionEventExportTests().fixture(root)
        data['truth']['labels']['events']['foot_plant'] = anchor
        helpers.NativeMotionEventExportTests.refresh(data)
        return data

    def run_export(self, data):
        with patch('pitch_analysis.analysis.native_motion_anchor_bounds._plot',
                   side_effect=lambda _clips, _role, path: path.write_bytes(b'bounded plot fixture')), \
             patch('subprocess.Popen', side_effect=AssertionError('no model or browser')), \
             patch('cv2.VideoCapture', side_effect=AssertionError('saved input only')):
            return write_bounded_alignment(data['root'], data['request_path'], data['comparison'])

    def test_export_retains_all_source_columns_nulls_frames_labels_and_source_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp), helpers.ranged(0, 2), missing_joint=True)
            loaded = load_event_clips(data['root'], data['request_path'], data['comparison'])['clips'][0]
            before = {path: path.read_bytes() for path in data['root'].rglob('*') if path.is_file()}
            result = self.run_export(data)
            self.assertEqual((result['clip_count'], result['source_frames']), (1, 3))
            self.assertEqual(read_json(data['comparison'] / 'anchor_bounds_summary.json'), result)
            for name in ('bounded_curves.csv', 'throwing_elbow_bounds.png', 'lead_knee_bounds.png', 'report.md'):
                self.assertTrue((data['comparison'] / name).is_file(), name)
            with (data['motion'] / 'motion_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
                source = list(csv.DictReader(stream))
            with (data['comparison'] / 'bounded_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
                exported = list(csv.DictReader(stream))
            self.assertEqual(len(exported), len(source))
            for original, bounded in zip(source, exported, strict=True):
                for field, value in original.items():
                    self.assertEqual(bounded[field], value, field)
                self.assertEqual(bounded['pitch_id'], 'pitch_fixture')
                self.assertEqual(bounded['origin_status'], 'bounded')
                self.assertEqual([bounded['origin_frame_min'], bounded['origin_frame_max']], ['0', '2'])
                frame = int(original['frame_index'])
                self.assertEqual([int(bounded['relative_frame_min']), int(bounded['relative_frame_max'])],
                                 [frame - 2, frame])
                expected = [Fraction(value) / Fraction(60000, 1001) for value in (frame - 2, frame)]
                for edge, value in zip(('min', 'max'), expected, strict=True):
                    self.assertEqual(float(bounded[f'relative_seconds_{edge}']), float(value))
                    self.assertEqual(bounded[f'relative_fraction_{edge}'], str(value))
                self.assertEqual(bounded['throwing_elbow_usable_deg'], '')
                self.assertEqual(bounded['lead_knee_usable_deg'], '')
            self.assertTrue(any(row['throwing_elbow_model_xy_deg'] == '' for row in exported))
            clip = result['clips'][0]
            self.assertEqual(clip['origin_status'], 'bounded')
            self.assertEqual(clip['origin_frame_bounds'], [0, 2])
            self.assertEqual(clip['origin_candidates'], [0, 1, 2])
            for key in ('source_refs', 'events', 'timing'):
                self.assertEqual(clip[key], loaded[key], key)
            self.assertNotIn('rows', clip)
            self.assertNotIn('bounded_rows', clip)
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_unavailable_origin_exports_every_source_row_with_null_relative_coordinates(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp), helpers.ranged(1, 2, status='uncertain'))
            result = self.run_export(data)
            self.assertEqual(result['source_frames'], 3)
            clip = result['clips'][0]
            self.assertEqual(clip['origin_status'], 'unavailable')
            self.assertEqual(clip['origin_candidates'], [])
            self.assertIsNone(clip['origin_frame_bounds'])
            self.assertEqual(clip['events']['foot_plant']['status'], 'uncertain')
            self.assertEqual(clip['events']['foot_plant']['frame_bounds'], [1, 2])
            with (data['comparison'] / 'bounded_curves.csv').open(encoding='utf-8-sig', newline='') as stream:
                exported = list(csv.DictReader(stream))
            self.assertEqual(len(exported), 3)
            self.assertEqual([row['frame_index'] for row in exported], ['0', '1', '2'])
            for row in exported:
                self.assertEqual(row['origin_status'], 'unavailable')
                for field in ('origin_frame_min', 'origin_frame_max', 'relative_frame_min', 'relative_frame_max',
                              'relative_seconds_min', 'relative_seconds_max', 'relative_fraction_min',
                              'relative_fraction_max'):
                    self.assertEqual(row[field], '', field)

    def test_changed_bound_sources_are_rejected_before_any_output_is_created(self):
        for changed in ('ground_truth', 'saved_curves'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp), helpers.ranged(0, 2))
                source = data['truth_path'] if changed == 'ground_truth' else data['motion'] / 'motion_curves.csv'
                with source.open('a', encoding='utf-8') as stream:
                    stream.write('\n')
                with self.assertRaises(ValueError):
                    self.run_export(data)
                self.assertFalse(data['comparison'].exists())

    def test_original_exact_export_still_rejects_single_or_multiple_frame_ranges(self):
        for first, last in ((1, 1), (0, 2)):
            with self.subTest(bounds=(first, last)), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp), helpers.ranged(first, last))
                with self.assertRaises(ValueError):
                    write_native_alignment(data['root'], data['request_path'], data['comparison'])
                self.assertFalse(data['comparison'].exists())


class AnchorBoundsCliTests(unittest.TestCase):
    def test_retain_anchor_ranges_flag_selects_bounded_writer_and_default_remains_exact(self):
        for retain in (True, False):
            with self.subTest(retain=retain):
                argv = ['pitch-analysis', 'align-native-motion', 'request.json', '--output', 'out']
                if retain:
                    argv.append('--retain-anchor-ranges')
                value = {'status': 'fixture_created', 'clip_count': 5, 'source_frames': 1684}
                with patch('sys.argv', argv), \
                     patch('pitch_analysis.analysis.native_motion_anchor_bounds.write_bounded_alignment',
                           return_value=value) as bounded, \
                     patch('pitch_analysis.analysis.native_motion_alignment.write_native_alignment',
                           return_value=value) as exact, \
                     patch('pitch_analysis.cli.extract_pose', side_effect=AssertionError('no inference')), \
                     redirect_stdout(StringIO()) as stream:
                    main()
                selected, other = (bounded, exact) if retain else (exact, bounded)
                selected.assert_called_once_with(Path.cwd(), 'request.json', 'out')
                other.assert_not_called()
                self.assertEqual(json.loads(stream.getvalue())['status'], 'fixture_created')


if __name__ == '__main__':
    unittest.main()
