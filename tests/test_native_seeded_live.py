"""Seeded orchestration uses generated video/synthetic caches and no real model."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import test_native_pose_live as fixtures
from pitch_analysis.native_person_box_live import _missing_landmarks
from pitch_analysis.native_pose import NativePoseFrame
from pitch_analysis.native_pose_estimator import decode_rtmpose_outputs, prepare_rtmpose_input
from pitch_analysis.native_pose_io import read_dataset, read_json, reference, write_dataset, write_json
from pitch_analysis.native_pose_live import _manifest
from pitch_analysis.native_seeded_live import run_seeded
from pitch_analysis.native_seeded_track import TRACK_POLICY, associate_saved_boxes


class SeededLiveTests(unittest.TestCase):
    def setUp(self):
        fixtures.FakeTransport.instances.clear();fixtures.FakeTransport.fail_at=None

    def fixture(self,root):
        source_path,base=fixtures.NativePoseLiveTests().fixture(root)
        (root/'analysis_results').mkdir()
        video=root/'fixture.mp4';capture=cv2.VideoCapture(str(video))
        images=[]
        try:
            while True:
                okay,image=capture.read()
                if not okay:break
                images.append(image)
        finally:capture.release()
        import hashlib
        records=[];detections=[]
        for i,image in enumerate(images):
            bbox=[10.+i*.5,15.,30.+i*.5,80.]
            candidates=[{'output_index':i,'eligible':True,'bbox_original_xyxy_px':bbox}]
            if i!=1:candidates.append({'output_index':7,'eligible':True,'bbox_original_xyxy_px':[42.,10.,60.,70.]})
            pixel=hashlib.sha256(image.tobytes()).hexdigest()
            detections.append({'frame_index':i,'timestamp_ms':float(i*1000/30),'decoded_bgr_sha256':pixel,
                'policy':'unique_person_box_center_in_operator_roi_v1','final_score_threshold':.7,'candidates':candidates})
            if i==1:
                _,geometry=prepare_rtmpose_input(image,[0,0,64,96],person_bbox_xyxy=bbox)
                x=np.zeros((1,17,384),np.float32);y=np.zeros((1,17,512),np.float32)
                x[:,:,192]=.7;y[:,:,256]=.8
                landmarks=decode_rtmpose_outputs((x,y),geometry)
            else:
                geometry={'input_mode':'not_run','roi_xywh':None,'affine_src_to_input':None,'affine_input_to_src':None,'sdk_geometry':None}
                landmarks=_missing_landmarks('ambiguous_subject_boxes')
            records.append(NativePoseFrame({'schema_version':'native-keypoints-v1','pitch_id':'fixture',
                'backend':'rtmpose_live_onnx','topology':'coco_17','frame_index':i,'timestamp_ms':float(i*1000/30),
                'source_video_sha256':reference(root,video)['sha256'],'decoded_bgr_sha256':pixel,
                'image_size':{'width':64,'height':96},'coordinate_space':'original_image_pixels_xy',
                'quality_status':'not_calibrated','usable_for_analysis':None,'input_geometry':geometry,
                'model_selection':{'inference_mode':'live_stateless_roi','pose_not_run':i!=1,
                    'pose_not_run_reason':'ambiguous_subject_boxes' if i!=1 else None,
                    'isolated_worker_attempt_index':1 if i==1 else None,
                    'person_box_selection':{'status':'selected' if i==1 else 'ambiguous_subject_boxes',
                        'selected_bbox_xyxy_px':bbox if i==1 else None}},'landmarks':landmarks}))
        clip={**base['clips'][0],'width':64,'height':96,'fps':__import__('fractions').Fraction(30),
              'region_confirmation':read_json(root/base['region_config_ref']['path'])['operator_confirmation']}
        manifest=_manifest(base,clip,reference(root,source_path))
        cache=root/'analysis_results/old';write_dataset(cache,manifest,records)
        old_receipt=root/'analysis_results/old_receipt.json'
        write_json(old_receipt,{'state':'completed','pitch_id':'fixture','frame_count':3,'pose_calls_completed':1})
        boxes_path=root/'analysis_results/boxes.jsonl'
        boxes_path.write_text(''.join(json.dumps(row)+'\n' for row in detections),encoding='utf-8')
        seed_path=root/'seed.json'
        write_json(seed_path,{'schema_version':'native-subject-seed-v1','status':'operator_confirmed','ground_truth':False,
            'pitch_id':'fixture','frame_index':0,'selected_output_index':0,'selected_bbox_xyxy_px':detections[0]['candidates'][0]['bbox_original_xyxy_px'],
            'source_video_ref':reference(root,video),'saved_detection_ref':reference(root,boxes_path),
            'decoded_bgr_sha256':detections[0]['decoded_bgr_sha256'],'reviewer':'Fixture','reviewed_at_utc':'2026-10-21T00:00:00Z','user_reply':'approved'})
        config={'schema_version':'native-seeded-track-run-v1','status':'approved','approval':base['approval'],
            'source_config_ref':reference(root,source_path),'seed_ref':reference(root,seed_path),'detections_ref':reference(root,boxes_path),
            'cached_manifest_ref':reference(root,cache/'native_pose_manifest.json'),
            'cached_keypoints_ref':reference(root,cache/'native_keypoints.jsonl'),'cached_receipt_ref':reference(root,old_receipt),
            'prior_inferred_frame_indices':[1],'max_new_pose_calls':2,'max_detector_calls':0,'track_policy':TRACK_POLICY,
            'once_only_claim_path':'analysis_results/seeded_claim.json'}
        config['source_refs']=[config[key] for key in ('source_config_ref','seed_ref','detections_ref','cached_manifest_ref','cached_keypoints_ref','cached_receipt_ref')]
        path=root/'seeded.json';write_json(path,config)
        return path,config

    def run_fixture(self,root,path,name='new'):
        return run_seeded(root,path,root/'analysis_results'/name,pose_factory=fixtures.FakeTransport,render_overlay=False)

    def refresh(self,root,path,config):
        for key in ('source_config_ref','seed_ref','detections_ref','cached_manifest_ref','cached_keypoints_ref','cached_receipt_ref'):
            config[key]=reference(root,root/config[key]['path'])
        config['source_refs']=[config[key] for key in ('source_config_ref','seed_ref','detections_ref','cached_manifest_ref','cached_keypoints_ref','cached_receipt_ref')]
        path.write_text(json.dumps(config),encoding='utf-8')

    def test_two_new_calls_one_exact_reuse_and_only_one_association(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,_=self.fixture(root)
            with patch('pitch_analysis.native_seeded_live.associate_saved_boxes',wraps=associate_saved_boxes) as replay, \
                 patch('pitch_analysis.native_person_box_transport.IsolatedDetectorTransport',side_effect=AssertionError('detector forbidden')):
                receipt=self.run_fixture(root,path)
            self.assertEqual(replay.call_count,1)
            self.assertEqual((receipt['tracking_replays_completed'],receipt['pose_calls_completed'],receipt['cached_pose_frames_reused'],receipt['detector_calls']),(1,2,1,0))
            manifest,frames=read_dataset(root/'analysis_results/new/rtmpose/fixture')
            old_manifest,old=read_dataset(root/'analysis_results/old')
            self.assertEqual([f.to_dict()['model_selection']['coordinate_origin'] for f in frames],['new_inference','cached_exact_geometry','new_inference'])
            self.assertEqual(frames[1].to_dict()['landmarks'],old[1].to_dict()['landmarks'])
            self.assertEqual(frames[1].to_dict()['input_geometry'],old[1].to_dict()['input_geometry'])
            self.assertFalse(manifest['roi_provenance']['per_frame_boxes_human_reviewed'])
            self.assertEqual(receipt['source_sha256_changes'],[])

    def test_claim_blocks_rerun_to_other_output_before_second_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,_=self.fixture(root);self.run_fixture(root,path)
            with patch('pitch_analysis.native_seeded_live.associate_saved_boxes',side_effect=AssertionError('second replay')):
                with self.assertRaises(ValueError):self.run_fixture(root,path,'different')
            self.assertEqual(len(fixtures.FakeTransport.instances),1)

    def test_cache_geometry_mismatch_missing_without_rerun_or_track_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,config=self.fixture(root)
            cache=root/config['cached_keypoints_ref']['path']
            rows=[json.loads(line) for line in cache.read_text().splitlines()]
            rows[1]['input_geometry']['sdk_geometry']['changed_for_fixture']=True
            cache.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8');self.refresh(root,path,config)
            receipt=self.run_fixture(root,path)
            _,frames=read_dataset(root/'analysis_results/new/rtmpose/fixture')
            self.assertEqual(receipt['pose_calls_completed'],2)
            self.assertEqual(receipt['cached_pose_frames_reused'],0)
            self.assertEqual(frames[1].to_dict()['input_geometry']['input_mode'],'not_run')
            self.assertEqual(frames[1].to_dict()['model_selection']['pose_not_run_reason'],'cache_geometry_mismatch_no_rerun')
            self.assertEqual(read_json(root/'analysis_results/new/seeded_track_summary.json')['track_status_counts'],{'seeded':1,'linked':2})

    def test_terminal_break_prevents_later_reacquire_and_cached_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,config=self.fixture(root)
            boxes=root/config['detections_ref']['path'];rows=[json.loads(line) for line in boxes.read_text().splitlines()]
            rows[1]['candidates'][0]['bbox_original_xyxy_px']=[45.,80.,63.,95.]
            boxes.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
            seed=root/config['seed_ref']['path'];payload=read_json(seed);payload['saved_detection_ref']=reference(root,boxes)
            seed.write_text(json.dumps(payload),encoding='utf-8');self.refresh(root,path,config)
            receipt=self.run_fixture(root,path)
            self.assertEqual((receipt['pose_calls_completed'],receipt['cached_pose_frames_reused']),(1,0))
            summary=read_json(root/'analysis_results/new/seeded_track_summary.json')
            self.assertEqual(summary['first_break_frame'],1)
            self.assertEqual(summary['missing_frame_indices'],[1,2])

    def test_invalid_policy_budget_or_prior_frames_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,base=self.fixture(root)
            for key,value in [('track_policy','changed'),('max_new_pose_calls',3),('prior_inferred_frame_indices',[])]:
                config=deepcopy(base);config[key]=value;path.write_text(json.dumps(config),encoding='utf-8')
                with self.subTest(key=key),self.assertRaises(ValueError):self.run_fixture(root,path)
            self.assertEqual(fixtures.FakeTransport.instances,[])
            self.assertFalse((root/'analysis_results/seeded_claim.json').exists())
            self.assertFalse((root/'analysis_results/new').exists())

    def test_failure_preserves_new_attempts_reuse_and_partial_timeline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,_=self.fixture(root);fixtures.FakeTransport.fail_at=2
            with self.assertRaisesRegex(RuntimeError,'not retried'):self.run_fixture(root,path)
            receipt=read_json(root/'analysis_results/new/run_receipt.json')
            self.assertEqual((receipt['state'],receipt['frames_completed'],receipt['pose_calls_attempted'],receipt['pose_calls_completed'],receipt['cached_pose_frames_reused']),('failed',2,2,1,1))
            self.assertEqual(receipt['failed_frame'],2)
            self.assertEqual(len((root/'analysis_results/new/native.partial.jsonl').read_text().splitlines()),2)
            with self.assertRaises(ValueError):self.run_fixture(root,path,'retry')


if __name__=='__main__':unittest.main()
