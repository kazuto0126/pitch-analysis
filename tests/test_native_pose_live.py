"""Live orchestration checks use synthetic inputs and no pose model."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from pitch_analysis.native_pose_io import read_dataset, read_json, reference, write_json
from pitch_analysis.native_pose_live import preflight_live, run_live


class FakeTransport:
    instances = []
    fail_at = None

    def __init__(self, python, worker, model, *, expected_model_sha256, max_calls, output_dir):
        self.calls_attempted = self.calls_completed = 0
        self.metadata = {'runtime': {'numpy': 'fixture'}}
        self.output_dir = output_dir
        self.closed = False
        self.limit = max_calls
        self.__class__.instances.append(self)

    def __enter__(self):
        (self.output_dir / 'worker_calls.jsonl').write_text('', encoding='utf-8')
        return self

    def __exit__(self, *args):
        self.closed = True

    def run(self, tensor):
        self.calls_attempted += 1
        if self.calls_attempted == self.fail_at:
            raise RuntimeError('fixture model failure; not retried')
        assert self.calls_attempted <= self.limit
        assert tensor.shape == (1, 3, 256, 192) and tensor.dtype == np.float32
        x, y = np.zeros((1,17,384), np.float32), np.zeros((1,17,512), np.float32)
        x[:,:,192], y[:,:,256] = .7, .8
        self.calls_completed += 1
        return x, y


class NativePoseLiveTests(unittest.TestCase):
    def setUp(self):
        FakeTransport.instances.clear()
        FakeTransport.fail_at = None

    def fixture(self, root):
        video = root / 'fixture.mp4'
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 30., (64,96))
        self.assertTrue(writer.isOpened())
        for _ in range(3):
            writer.write(np.full((96,64,3), 100, np.uint8))
        writer.release()
        metadata = root / 'fixture.json'
        write_json(metadata, {'schema_version':'pitch-input-v1','pitch_id':'fixture',
                             'pitcher':{'id':'fixture_pitcher','display_name':'Fixture','throws':'RIGHT'},
                             'video':{'file':'fixture.mp4','camera_view':'rear_centerfield_broadcast',
                                      'horizontal_mirror':False,'playback_speed':1.,'contains_single_pitch':True,
                                      'continuous_shot':True,'subject_framing':'full_body'},
                             'context':{'season':None,'team':None,'pitch_type':None,'session_id':None}})
        for name in ('model.bin','python.exe','worker.py'):
            (root/name).write_bytes(b'fixture source')
        from pitch_analysis.native_pose_live import REVIEW_ITEMS
        review = root/'review.json'
        write_json(review, {'overall_status':'review_complete','source_video_sha256':reference(root,video)['sha256'],
                            'items':{key:{'latest':{'conclusion':'pass','reviewer':'fixture'}} for key in REVIEW_ITEMS}})
        timeline = root/'timeline.json'
        write_json(timeline, {'frame_count':3,'fractional_fps':'30','source_video_sha256':reference(root,video)['sha256']})
        regions = root/'regions.json'
        write_json(regions, {'status':'operator_confirmed','operator_confirmation':{'reviewer':'fixture','reviewed_at_utc':'2026-10-20T08:33:11Z'},
                             'clips':[{'pitch_id':'fixture','video_sha256':reference(root,video)['sha256'],
                                       'expected_pixel_bounds_xyxy_exclusive':[0,0,64,96]}]})
        config = {'schema_version':'native-live-run-v1','status':'approved',
                  'approval':{'reviewer':'fixture','reviewed_at_utc':'2026-10-20T13:06:00Z','user_reply':'approved fixture'},
                  'pitcher_id':'fixture_pitcher','max_real_calls':3,
                  'model_ref':reference(root,root/'model.bin'),'runtime_ref':reference(root,root/'python.exe'),
                  'worker_ref':reference(root,root/'worker.py'),'region_config_ref':reference(root,regions),
                  'expected_runtime':{'numpy':'fixture'},'clips':[{'pitch_id':'fixture','video_ref':reference(root,video),
                   'metadata_ref':reference(root,metadata),'review_ref':reference(root,review),
                   'timeline_ref':reference(root,timeline),'fps_fraction':'30','frame_count':3,'crop_xyxy_px':[0,0,64,96]}]}
        path = root/'run.json'
        write_json(path, config)
        return path, config

    def test_complete_source_bound_frames_and_native_dataset_without_true_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, _ = self.fixture(root)
            result = run_live(root, config, root/'analysis_results/run', transport_factory=FakeTransport, render_overlays=False)
            self.assertEqual((result['state'],result['calls_attempted'],result['calls_completed']), ('completed',3,3))
            manifest, frames = read_dataset(root/'analysis_results/run/rtmpose/fixture')
            self.assertEqual(manifest['inference_mode'],'live_stateless_roi')
            self.assertEqual(manifest['roi_provenance']['reviewed_at_utc'],'2026-10-20T08:33:11Z')
            self.assertEqual([f.to_dict()['frame_index'] for f in frames],[0,1,2])
            self.assertEqual([f.to_dict()['timestamp_ms'] for f in frames],[0.,1000/30,2000/30])
            self.assertIsNone(frames[0].to_dict()['usable_for_analysis'])
            self.assertEqual(len(frames[0].to_dict()['landmarks']),17)
            self.assertEqual(result['source_sha256_changes'],[])
            self.assertTrue(FakeTransport.instances[0].closed)

    def test_rejects_existing_or_external_output_without_starting_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,_=self.fixture(root)
            existing=root/'analysis_results/existing';existing.mkdir(parents=True)
            for output in (existing, root/'wrong_place'):
                with self.assertRaises(ValueError):run_live(root,path,output,transport_factory=FakeTransport)
            self.assertEqual(FakeTransport.instances,[])

    def test_all_reviews_and_hashes_preflight_before_output_or_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,config=self.fixture(root)
            for mutation in ('changed_source','pending_review','unconfirmed_regions','wrong_crop','shifted_timeline'):
                changed=deepcopy(config)
                if mutation=='changed_source':changed['clips'][0]['video_ref']['sha256']='a'*64
                elif mutation=='pending_review':
                    p=root/'pending.json';write_json(p,{'overall_status':'pending'})
                    changed['clips'][0]['review_ref']=reference(root,p)
                elif mutation=='unconfirmed_regions':
                    p=root/'unconfirmed.json';write_json(p,{'status':'proposed'})
                    changed['region_config_ref']=reference(root,p)
                elif mutation=='wrong_crop':changed['clips'][0]['crop_xyxy_px']=[1,0,64,96]
                else:changed['clips'][0]['frame_count']=4;changed['max_real_calls']=4
                case=root/(mutation+'.json');write_json(case,changed)
                output=root/'analysis_results'/mutation
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    run_live(root,case,output,transport_factory=FakeTransport)
                self.assertFalse(output.exists())
            self.assertEqual(FakeTransport.instances,[])

    def test_failure_keeps_partial_frames_reason_and_no_second_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,_=self.fixture(root);FakeTransport.fail_at=2
            output=root/'analysis_results/failed'
            with self.assertRaisesRegex(RuntimeError,'not retried'):
                run_live(root,path,output,transport_factory=FakeTransport,render_overlays=False)
            result=read_json(output/'run_receipt.json')
            self.assertEqual((result['state'],result['calls_attempted'],result['calls_completed']),('failed',2,1))
            self.assertEqual(result['clips'][0]['failed_frame'],1)
            self.assertEqual(len((output/'fixture.partial.jsonl').read_text().splitlines()),1)
            self.assertTrue(FakeTransport.instances[0].closed)
            with self.assertRaises(ValueError):run_live(root,path,output,transport_factory=FakeTransport)
            self.assertEqual(len(FakeTransport.instances),1)

    def test_runtime_mismatch_fails_before_first_model_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,config=self.fixture(root)
            config['expected_runtime']['numpy']='unexpected'
            path.write_text(__import__('json').dumps(config),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'runtime changed'):
                run_live(root,path,root/'analysis_results/run',transport_factory=FakeTransport,render_overlays=False)
            self.assertEqual(FakeTransport.instances[0].calls_attempted,0)

    def test_actual_source_timing_checked_before_output_and_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,_=self.fixture(root)
            original=cv2.VideoCapture
            class BadTimeCapture:
                def __init__(self,*args):self.capture=original(*args)
                def isOpened(self):return self.capture.isOpened()
                def read(self):return self.capture.read()
                def release(self):return self.capture.release()
                def get(self,key):
                    return self.capture.get(key)+(5 if key==cv2.CAP_PROP_POS_MSEC else 0)
            output=root/'analysis_results/run'
            with patch('pitch_analysis.native_pose_live.cv2.VideoCapture',BadTimeCapture):
                with self.assertRaisesRegex(ValueError,'timing differs'):
                    run_live(root,path,output,transport_factory=FakeTransport)
            self.assertFalse(output.exists())
            self.assertEqual(FakeTransport.instances,[])


if __name__=='__main__':unittest.main()
