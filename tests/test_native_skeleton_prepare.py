"""First-frame preparation never silently selects a subject or estimates pose."""
from pathlib import Path
import tempfile
import unittest

import test_native_pose_live as fixtures
import test_native_person_box_live as person_fixtures
from pitch_analysis.native_pose_io import read_json, reference, write_json
from pitch_analysis.native_skeleton_prepare import prepare_skeleton


class SkeletonPrepareTests(unittest.TestCase):
    def setUp(self):
        person_fixtures.FakeDetector.instances.clear();person_fixtures.FakeDetector.fail_at=None

    def fixture(self,root):
        _,base=fixtures.NativePoseLiveTests().fixture(root)
        for name in ('detector.bin','detector_worker.py'):(root/name).write_bytes(b'synthetic source')
        config={'schema_version':'seeded-skeleton-runtime-v1',
                **{key:base[key] for key in ('runtime_ref','model_ref','worker_ref','expected_runtime')},
                'detector_model_ref':reference(root,root/'detector.bin'),
                'detector_worker_ref':reference(root,root/'detector_worker.py')}
        config['source_refs']=[config[k] for k in ('runtime_ref','model_ref','worker_ref','detector_model_ref','detector_worker_ref')]
        path=root/'runtime.json';write_json(path,config)
        return path

    def run_fixture(self,root,runtime,name='prepared',fps='30'):
        return prepare_skeleton(root,root/'fixture.mp4',root/'fixture.json',runtime,root/'analysis_results'/name,
                                fps_fraction=fps,detector_factory=person_fixtures.FakeDetector)

    def test_one_firstframe_detector_no_pose_no_human_seed_and_full_source_canvas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);runtime=self.fixture(root);value=self.run_fixture(root,runtime)
            self.assertEqual((value['frame_count'],value['fps_fraction'],value['crop_xyxy_px']),(3,'30',[0,0,64,96]))
            self.assertEqual(value['status'],'awaiting_operator_seed');self.assertIsNone(value['operator_seed'])
            self.assertEqual(value['pose_calls_during_preparation'],0)
            self.assertEqual(person_fixtures.FakeDetector.instances[0].calls_completed,1)
            self.assertEqual(len(value['display_choices']),1)
            frame=read_json(root/value['frame0_ref']['path'])
            self.assertEqual(frame['frame_index'],0);self.assertEqual(frame['timestamp_ms'],0.)
            self.assertEqual(value['display_choices'][0]['output_index'],frame['candidates'][0]['output_index'])

    def test_new_output_path_cannot_duplicate_prepared_source_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);runtime=self.fixture(root);self.run_fixture(root,runtime)
            with self.assertRaisesRegex(ValueError,'preparation claim'):self.run_fixture(root,runtime,'another')
            self.assertEqual(len(person_fixtures.FakeDetector.instances),1)

    def test_changed_runtime_source_and_wrong_fractional_fps_rejected_without_detector(self):
        for mode in ('source','fps'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);runtime=self.fixture(root)
                if mode=='source':(root/'detector.bin').write_bytes(b'changed')
                with self.assertRaises(ValueError):self.run_fixture(root,runtime,fps='60' if mode=='fps' else '30')
                self.assertEqual(person_fixtures.FakeDetector.instances,[])

    def test_detector_failure_retains_attempt_and_claim_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);runtime=self.fixture(root);person_fixtures.FakeDetector.fail_at=1
            with self.assertRaisesRegex(RuntimeError,'not retried'):self.run_fixture(root,runtime)
            self.assertEqual(person_fixtures.FakeDetector.instances[0].calls_attempted,1)
            self.assertFalse((root/'analysis_results/prepared/preparation.json').exists())
            with self.assertRaisesRegex(ValueError,'preparation claim'):self.run_fixture(root,runtime,'retry')


if __name__=='__main__':unittest.main()
