"""Synthetic source and transports for the shared seeded skeleton entry."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from pitch_analysis.native_person_boxes import prepare_detector_input, select_person_box
from pitch_analysis.native_pose_io import read_dataset, read_json, reference, write_json
from pitch_analysis.seeded_skeleton import run_seeded_skeleton


class FakeDetector:
    instances = []
    pattern = None
    fail_at = None

    def __init__(self, python, worker, model, *, expected_model_sha256, max_calls, output_dir):
        self.calls_attempted = self.calls_completed = 0
        self.limit = max_calls
        self.metadata = {'runtime': {'numpy': 'fixture'}}
        self.output_dir = output_dir
        self.closed = False
        self.__class__.instances.append(self)

    def __enter__(self):
        (self.output_dir / 'detector_calls.jsonl').write_text('', encoding='utf-8')
        return self

    def __exit__(self, *args):
        self.closed = True

    def run(self, tensor):
        self.calls_attempted += 1
        if self.calls_attempted == self.fail_at:
            raise RuntimeError('synthetic detector failed without retry')
        assert tensor.shape == (1, 3, 640, 640)
        assert self.calls_attempted <= self.limit
        boxes = self.pattern[self.calls_attempted - 1]
        ratio = Fraction(640, 96)
        rows = [[*[float(value * ratio) for value in box], .9] for box in boxes]
        self.calls_completed += 1
        return np.array(rows, np.float32).reshape(1, -1, 5), np.zeros((1, len(rows)), np.int64)


class FakePose:
    instances = []
    fail_at = None

    def __init__(self, python, worker, model, *, expected_model_sha256, max_calls, output_dir):
        self.calls_attempted = self.calls_completed = 0
        self.limit = max_calls
        self.metadata = {'runtime': {'numpy': 'fixture'}}
        self.output_dir = output_dir
        self.closed = False
        self.__class__.instances.append(self)

    def __enter__(self):
        (self.output_dir / 'pose_calls.jsonl').write_text('', encoding='utf-8')
        return self

    def __exit__(self, *args):
        self.closed = True

    def run(self, tensor):
        self.calls_attempted += 1
        if self.calls_attempted == self.fail_at:
            raise RuntimeError('synthetic pose failed without retry')
        assert tensor.shape == (1, 3, 256, 192)
        assert self.calls_attempted <= self.limit
        x, y = np.zeros((1, 17, 384), np.float32), np.zeros((1, 17, 512), np.float32)
        x[:, :, 192], y[:, :, 256] = .7, .8
        self.calls_completed += 1
        return x, y


class SeededSkeletonTests(unittest.TestCase):
    def setUp(self):
        FakeDetector.instances.clear()
        FakePose.instances.clear()
        FakeDetector.fail_at = FakePose.fail_at = None
        FakeDetector.pattern = [
            [[9, 10, 31, 80], [35, 10, 58, 80]],
            [[10, 10, 32, 80], [35, 10, 58, 80]],
        ]

    def fixture(self, root: Path, *, seed_index=0, frame_count=3):
        video = root / 'fixture.mp4'
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 30., (64, 96))
        self.assertTrue(writer.isOpened())
        for number in range(frame_count):
            writer.write(np.full((96, 64, 3), 90 + number%100, np.uint8))
        writer.release()
        metadata = root / 'fixture.json'
        write_json(metadata, {
            'schema_version': 'pitch-input-v1', 'pitch_id': 'fixture',
            'pitcher': {'id': 'fixture_pitcher', 'throws': 'RIGHT'},
            'video': {'file': 'fixture.mp4', 'camera_view': 'rear_centerfield_broadcast',
                      'horizontal_mirror': False, 'playback_speed': 1.0,
                      'contains_single_pitch': True, 'continuous_shot': True,
                      'subject_framing': 'full_body'},
        })
        for name in ('runtime.exe', 'pose.onnx', 'pose_worker.py', 'detector.onnx', 'detector_worker.py'):
            (root / name).write_bytes(b'synthetic source ' + name.encode())
        refs = {
            key: reference(root, root / name) for key, name in {
                'runtime_ref': 'runtime.exe', 'model_ref': 'pose.onnx',
                'worker_ref': 'pose_worker.py', 'detector_model_ref': 'detector.onnx',
                'detector_worker_ref': 'detector_worker.py',
            }.items()
        }
        prep_dir = root / 'analysis_results' / 'prepared'
        prep_dir.mkdir(parents=True)
        capture = cv2.VideoCapture(str(video))
        okay, image = capture.read()
        capture.release()
        self.assertTrue(okay)
        _, geometry = prepare_detector_input(image, [0, 0, 64, 96])
        ratio = Fraction(640, 96)
        boxes = [[8, 10, 30, 80], [35, 10, 58, 80]]
        rows = [[*[float(value * ratio) for value in box], .9] for box in boxes]
        selection = select_person_box((np.array(rows, np.float32).reshape(1, -1, 5),
                                       np.zeros((1, 2), np.int64)), geometry, [0., 0., 1., 1.])
        frame0 = {**selection, 'frame_index': 0, 'timestamp_ms': 0.,
                  'decoded_bgr_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
                  'detector_geometry': geometry}
        first = prep_dir / 'first_frame_candidates.json'
        write_json(first, frame0)
        prep = {
            'schema_version': 'seeded-skeleton-preparation-v1', 'status': 'awaiting_operator_seed',
            'pitch_id': 'fixture', 'pitcher_id': 'fixture_pitcher',
            'video_ref': reference(root, video), 'metadata_ref': reference(root, metadata),
            'frame_count': frame_count, 'width': 64, 'height': 96, 'fps_fraction': '30',
            'crop_xyxy_px': [0, 0, 64, 96], 'operator_roi': [0., 0., 1., 1.],
            'frame0_ref': reference(root, first), 'expected_runtime': {'numpy': 'fixture'},
            'display_choices': [
                {'display_number': number, 'output_index': item['output_index'],
                 'bbox_original_xyxy_px': item['bbox_original_xyxy_px']}
                for number, item in enumerate(frame0['candidates'], 1)
            ],
            **refs,
        }
        prep['source_refs'] = [prep[key] for key in ('video_ref', 'metadata_ref', 'frame0_ref', *refs)]
        preparation_path = prep_dir / 'preparation.json'
        write_json(preparation_path, prep)
        seed = {
            'schema_version': 'native-subject-seed-v1', 'status': 'operator_confirmed',
            'ground_truth': False, 'pitch_id': 'fixture', 'frame_index': 0,
            'selected_output_index': seed_index,
            'selected_bbox_xyxy_px': frame0['candidates'][seed_index]['bbox_original_xyxy_px'],
            'source_video_ref': prep['video_ref'], 'saved_detection_ref': prep['frame0_ref'],
            'decoded_bgr_sha256': frame0['decoded_bgr_sha256'],
            'reviewer': 'Fixture operator', 'reviewed_at_utc': '2026-10-23T00:00:00Z',
            'user_reply': 'Choose this first-frame box',
        }
        seed_path = root / 'seed.json'
        write_json(seed_path, seed)
        return preparation_path, seed_path, prep, seed

    def run_fixture(self, root, preparation_path, seed_path, name='run'):
        return run_seeded_skeleton(root, preparation_path, seed_path,
                                   root / 'analysis_results' / name,
                                   detector_factory=FakeDetector, pose_factory=FakePose,
                                   render_overlay=False)

    def test_frame_zero_cached_and_native_seventeen_unsupported_fields_null(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            prep, seed, _, _ = self.fixture(root)
            result = self.run_fixture(root, prep, seed)
            self.assertEqual(result['state'], 'completed')
            self.assertEqual((result['new_detector_calls_completed'], result['pose_calls_completed']), (2, 3))
            detections = [json.loads(line) for line in (root / 'analysis_results/run/person_boxes.jsonl').read_text().splitlines()]
            self.assertEqual(detections[0], read_json(root / 'analysis_results/prepared/first_frame_candidates.json'))
            self.assertEqual(len(detections), 3)
            manifest, frames = read_dataset(root / 'analysis_results/run/rtmpose/fixture')
            self.assertEqual(manifest['topology'], 'coco_17')
            self.assertEqual(manifest['timebase']['fps_fraction'], '30/1')
            self.assertEqual([row.to_dict()['frame_index'] for row in frames], [0, 1, 2])
            for row in frames:
                self.assertEqual(len(row.to_dict()['landmarks']), 17)
                for point in row.to_dict()['landmarks']:
                    self.assertIsNone(point['z'])
                    self.assertIsNone(point['visibility'])
                    self.assertIsNone(point['presence'])
            self.assertTrue(FakeDetector.instances[0].closed and FakePose.instances[0].closed)

    def test_seed_choice_controls_initial_subject_and_track(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            prep, seed, _, _ = self.fixture(root, seed_index=1)
            self.run_fixture(root, prep, seed)
            tracks = [json.loads(line) for line in (root / 'analysis_results/run/subject_track.jsonl').read_text().splitlines()]
            self.assertEqual([row['selected_output_index'] for row in tracks], [1, 1, 1])
            self.assertEqual([row['status'] for row in tracks], ['seeded', 'linked', 'linked'])

    def test_longer_sources_keep_total_budget_across_detector_sessions(self):
        FakeDetector.pattern=[[[9,10,31,80],[35,10,58,80]]]*321
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root=Path(temp);prep,seed,_,_=self.fixture(root,frame_count=323)
            result=self.run_fixture(root,prep,seed)
            self.assertEqual([worker.limit for worker in FakeDetector.instances],[321,1])
            self.assertEqual(result['new_detector_calls_completed'],322)
            self.assertEqual(result['pose_calls_completed'],323)
            self.assertEqual(result['frames_completed'],323)
            self.assertTrue(all(worker.closed for worker in FakeDetector.instances))

    def test_terminal_break_keeps_complete_explicit_missing_timeline(self):
        FakeDetector.pattern = [
            [[35, 10, 58, 80]],
            [[9, 10, 31, 80]],
        ]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            prep, seed, _, _ = self.fixture(root)
            result = self.run_fixture(root, prep, seed)
            self.assertEqual(result['pose_calls_completed'], 1)
            tracks = [json.loads(line) for line in (root / 'analysis_results/run/subject_track.jsonl').read_text().splitlines()]
            self.assertEqual([row['status'] for row in tracks], ['seeded', 'track_break_no_overlap', 'after_track_break'])
            _, frames = read_dataset(root / 'analysis_results/run/rtmpose/fixture')
            self.assertEqual([frame.to_dict()['input_geometry']['input_mode'] for frame in frames],
                             ['roi_affine', 'not_run', 'not_run'])
            for frame in frames[1:]:
                value = frame.to_dict()
                self.assertTrue(value['model_selection']['pose_not_run'])
                self.assertTrue(all(point['coordinate_state'] == 'missing' and point['native_score'] is None
                                    for point in value['landmarks']))

    def test_bad_seed_and_changed_source_reject_before_claim_or_model(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            prep, seed_path, _, seed = self.fixture(root)
            bad = deepcopy(seed)
            bad['selected_output_index'] = 42
            seed_path.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'eligible'):
                self.run_fixture(root, prep, seed_path)
            self.assertFalse((prep.parent / 'execution_claim.json').exists())
            self.assertFalse((root / 'analysis_results/run').exists())
            seed_path.write_text(json.dumps(seed), encoding='utf-8')
            with (root / 'fixture.mp4').open('ab') as stream:
                stream.write(b'mutation')
            with self.assertRaisesRegex(ValueError, 'Changed or external source'):
                self.run_fixture(root, prep, seed_path)
            self.assertFalse((prep.parent / 'execution_claim.json').exists())
            self.assertEqual(FakeDetector.instances, [])
            self.assertEqual(FakePose.instances, [])

    def test_claim_blocks_another_output_even_with_changed_seed(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            prep, seed_path, _, seed = self.fixture(root)
            self.run_fixture(root, prep, seed_path)
            seed['user_reply'] = 'Changed reply'
            seed_path.write_text(json.dumps(seed), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'already been claimed'):
                self.run_fixture(root, prep, seed_path, name='other')
            self.assertFalse((root / 'analysis_results/other').exists())
            self.assertEqual(len(FakeDetector.instances), 1)

    def test_detector_failure_preserves_reason_claim_and_no_pose(self):
        FakeDetector.fail_at = 2
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            prep, seed, _, _ = self.fixture(root)
            with self.assertRaisesRegex(RuntimeError, 'without retry'):
                self.run_fixture(root, prep, seed)
            receipt = read_json(root / 'analysis_results/run/run_receipt.json')
            self.assertEqual((receipt['state'], receipt['failed_stage'], receipt['failed_frame']),
                             ('failed', 'detector', 2))
            self.assertEqual((receipt['new_detector_calls_attempted'], receipt['new_detector_calls_completed']), (2, 1))
            self.assertEqual(FakePose.instances, [])
            self.assertTrue((prep.parent / 'execution_claim.json').exists())
            self.assertEqual(len((root / 'analysis_results/run/person_boxes.jsonl').read_text().splitlines()), 2)
            with self.assertRaises(ValueError):
                self.run_fixture(root, prep, seed, name='retry')


if __name__ == '__main__':
    unittest.main()
