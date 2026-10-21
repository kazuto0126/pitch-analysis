"""Single-clip orchestration uses generated video and synthetic transports only."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import test_native_pose_live as fixtures
from pitch_analysis.native_person_boxes import POLICY
from pitch_analysis.native_person_box_live import run_person_box
from pitch_analysis.native_pose_io import read_dataset, read_json, reference, write_dataset, write_json


class FakeDetector(fixtures.FakeTransport):
    instances = []
    fail_at = None
    def run(self, tensor):
        self.calls_attempted += 1
        if self.calls_attempted == self.fail_at:
            raise RuntimeError('fixture detector failure; not retried')
        assert tensor.shape == (1,3,640,640) and tensor.dtype == np.float32
        assert self.calls_attempted <= self.limit
        pattern = ([[100,100,400,600,.8]], [], [[100,100,400,600,.8],[110,110,410,610,.9]])
        rows = pattern[self.calls_attempted-1]
        self.calls_completed += 1
        return np.array(rows,np.float32).reshape(1,-1,5), np.zeros((1,len(rows)),np.int64)


class PersonBoxLiveTests(unittest.TestCase):
    def setUp(self):
        fixtures.FakeTransport.instances.clear(); fixtures.FakeTransport.fail_at = None
        FakeDetector.instances.clear(); FakeDetector.fail_at = None

    def fixture(self, root):
        path, config = fixtures.NativePoseLiveTests().fixture(root)
        region_path = root/config['region_config_ref']['path']
        region = read_json(region_path)
        region['clips'][0]['subject_roi'] = [0.,0.,1.,1.]
        region_path.write_text(json.dumps(region),encoding='utf-8')
        config['region_config_ref'] = reference(root,region_path)
        for name in ('detector.bin','detector_worker.py'):
            (root/name).write_bytes(b'fixture detector source')
        baked = {'nms_applied_in_graph':True,'second_nms':False,'iou_threshold':.65,'score_threshold':.01}
        metadata = root/'detector_metadata.json'
        write_json(metadata, {'status':'metadata_compatible_no_inference','model_sha256':reference(root,root/'detector.bin')['sha256'],
                             'real_detector_calls':0,'real_pose_calls':0,'actual_baked_postprocessing':baked})
        (root/'analysis_results').mkdir()
        ext = {'schema_version':'native-person-box-conditioning-v1', 'policy':POLICY,
               'final_score_threshold':.7,'max_detector_calls':3, 'operator_roi':[0.,0.,1.,1.],
               'model_ref':reference(root,root/'detector.bin'), 'worker_ref':reference(root,root/'detector_worker.py'),
               'metadata_ref':reference(root,metadata),'baked_postprocessing':baked,
               'once_only_claim_path':'analysis_results/once.json'}
        ext['source_refs'] = [ext[k] for k in ('model_ref','worker_ref','metadata_ref')]
        config['person_box_conditioning'] = ext
        path.write_text(json.dumps(config),encoding='utf-8')
        return path, config

    def run_fixture(self, root, path, name='run'):
        return run_person_box(root,path,root/'analysis_results'/name,
                              detector_factory=FakeDetector,pose_factory=fixtures.FakeTransport,render_overlay=False)

    def test_complete_timeline_keeps_no_box_and_ambiguity_without_pose_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,_=self.fixture(root)
            receipt=self.run_fixture(root,path)
            self.assertEqual(receipt['state'],'completed')
            self.assertEqual((receipt['detector_calls_attempted'],receipt['pose_calls_attempted']),(3,1))
            self.assertEqual(receipt['frames_completed'],3)
            manifest,frames=read_dataset(root/'analysis_results/run/rtmpose/fixture')
            self.assertIn('detector-derived',manifest['roi_provenance']['roi_source'])
            self.assertFalse(manifest['roi_provenance']['per_frame_boxes_human_reviewed'])
            self.assertEqual([f.to_dict()['frame_index'] for f in frames],[0,1,2])
            self.assertEqual([f.to_dict()['timestamp_ms'] for f in frames],[0.,1000/30,2000/30])
            self.assertEqual([f.to_dict()['input_geometry']['input_mode'] for f in frames],['roi_affine','not_run','not_run'])
            self.assertTrue(all(p['native_score'] is None and p['coordinate_state']=='missing' for p in frames[2].to_dict()['landmarks']))
            self.assertEqual(receipt['source_sha256_changes'],[])
            self.assertTrue(FakeDetector.instances[0].closed and fixtures.FakeTransport.instances[0].closed)

    def test_once_only_claim_prevents_rerun_even_to_another_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,_=self.fixture(root);self.run_fixture(root,path)
            for name in ('run','different_new_output'):
                with self.subTest(name=name), self.assertRaises(ValueError): self.run_fixture(root,path,name)
            self.assertEqual(len(FakeDetector.instances),1)

    def test_no_run_cannot_be_repackaged_as_cached_native_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,_=self.fixture(root);self.run_fixture(root,path)
            manifest,frames=read_dataset(root/'analysis_results/run/rtmpose/fixture')
            manifest['inference_mode']='cached_read_only'
            with self.assertRaisesRegex(ValueError,'requires a live'):
                write_dataset(root/'analysis_results/cached',manifest,frames)
            self.assertFalse((root/'analysis_results/cached').exists())

    def test_policy_and_source_fail_before_output_claim_or_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,base=self.fixture(root)
            for key,value in [('final_score_threshold',.5),('operator_roi',[0.,0.,.8,.8]),('max_detector_calls',4)]:
                config=deepcopy(base);config['person_box_conditioning'][key]=value
                path.write_text(json.dumps(config),encoding='utf-8')
                with self.subTest(key=key), self.assertRaises(ValueError):self.run_fixture(root,path)
            self.assertFalse((root/'analysis_results/run').exists())
            self.assertFalse((root/'analysis_results/once.json').exists())
            self.assertEqual(FakeDetector.instances,[])

    def test_detector_failure_keeps_counts_and_never_calls_pose_for_failed_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,_=self.fixture(root);FakeDetector.fail_at=2
            with self.assertRaisesRegex(RuntimeError,'not retried'):self.run_fixture(root,path)
            receipt=read_json(root/'analysis_results/run/run_receipt.json')
            self.assertEqual(receipt['state'],'failed')
            self.assertEqual((receipt['detector_calls_attempted'],receipt['detector_calls_completed'],receipt['pose_calls_completed']),(2,1,1))
            self.assertEqual(receipt['failed_frame'],1)
            self.assertEqual(len((root/'analysis_results/run/native.partial.jsonl').read_text().splitlines()),1)
            with self.assertRaises(ValueError):self.run_fixture(root,path,'no_retry')


if __name__ == '__main__':unittest.main()
