"""Synthetic interrupted-run continuations: no real detector, replay or model."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import test_native_pose_live as fixtures
import test_native_seeded_live as seeded_fixtures
from pitch_analysis.native_person_box_live import _missing_landmarks
from pitch_analysis.native_pose import NativePoseFrame
from pitch_analysis.native_pose_estimator import decode_rtmpose_outputs, prepare_rtmpose_input
from pitch_analysis.native_pose_io import read_dataset, read_json, reference, write_dataset, write_json
from pitch_analysis.native_pose_live import preflight_live
from pitch_analysis.native_seeded_live import _seeded_manifest
from pitch_analysis.native_seeded_resume import run_resume
from pitch_analysis.native_seeded_track import associate_saved_boxes


class SeededResumeTests(unittest.TestCase):
    def setUp(self):
        fixtures.FakeTransport.instances.clear();fixtures.FakeTransport.fail_at=None

    def fixture(self,root):
        seeded_path,seeded=seeded_fixtures.SeededLiveTests().fixture(root)
        base,clips=preflight_live(root,root/seeded['source_config_ref']['path']);clip=clips[0]
        rows=[json.loads(line) for line in (root/seeded['detections_ref']['path']).read_text().splitlines()]
        tracks=associate_saved_boxes(rows,seed_output_index=0)
        _,original=read_dataset(root/seeded['cached_manifest_ref']['path'].rsplit('/',1)[0])
        capture=cv2.VideoCapture(str(clip['video_path']));okay,image=capture.read();capture.release();assert okay
        tensor,geometry=prepare_rtmpose_input(image,clip['crop_xyxy_px'],person_bbox_xyxy=tracks[0]['selected_bbox_xyxy_px'])
        x=np.zeros((1,17,384),np.float32);y=np.zeros((1,17,512),np.float32)
        x[:,:,192]=.7;y[:,:,256]=.8
        values=[frame.to_dict() for frame in original]
        values[0]['landmarks']=decode_rtmpose_outputs((x,y),geometry);values[0]['input_geometry']=geometry
        values[2]['landmarks']=_missing_landmarks('execution_interrupted_no_retry')
        for index,value in enumerate(values):
            value['model_selection']={**value['model_selection'],
                'pose_not_run':index==2,'pose_not_run_reason':'execution_interrupted_no_retry' if index==2 else None,
                'coordinate_origin':['new_inference','cached_exact_geometry','not_run'][index],
                'isolated_worker_attempt_index':1 if index==0 else None,
                'person_box_selection':{'status':tracks[index]['status'],
                    'selected_bbox_xyxy_px':tracks[index]['selected_bbox_xyxy_px']}}
        old=root/'analysis_results/interrupted';old.mkdir()
        saved=old/'rtmpose/fixture'
        manifest=_seeded_manifest(base,clip,seeded,reference(root,seeded_path))
        write_dataset(saved,manifest,[NativePoseFrame(value) for value in values])
        partial=old/'native.partial.jsonl';partial.write_text(''.join(json.dumps(v)+'\n' for v in values[:2]),encoding='utf-8')
        track=old/'subject_track.jsonl';track.write_text(''.join(json.dumps(v)+'\n' for v in tracks),encoding='utf-8')
        body=x.astype('<f4').tobytes()+y.astype('<f4').tobytes()
        binary=old/'outputs.bin';binary.write_bytes(body)
        digest=hashlib.sha256(tensor.astype('<f4',copy=False).tobytes()).hexdigest()
        journal=old/'calls.jsonl'
        records=[{'event':'started','attempt_index':1,'input_sha256':digest,'model_sha256':base['model_ref']['sha256']},
                 {'event':'completed','attempt_index':1,'input_sha256':digest,'output_offset_bytes':0,
                  'output_length_bytes':len(body),'output_sha256':hashlib.sha256(body).hexdigest()}]
        journal.write_text(''.join(json.dumps(v)+'\n' for v in records),encoding='utf-8')
        prior_claim=root/seeded['once_only_claim_path']
        write_json(prior_claim,{'config_ref':reference(root,seeded_path),'output':old.relative_to(root).as_posix()})
        interruption=old/'interrupted_run_receipt.json'
        write_json(interruption,{'state':'interrupted_preserved_no_retry','config_ref':reference(root,seeded_path),
                                'pose_calls_attempted':1,'pose_calls_completed':1,'source_pose_frames_saved':2})
        names={'original_config_ref':seeded_path,'interrupted_receipt_ref':interruption,'prior_claim_ref':prior_claim,
               'partial_ref':partial,'track_ref':track,'native_manifest_ref':saved/'native_pose_manifest.json',
               'native_keypoints_ref':saved/'native_keypoints.jsonl','journal_ref':journal,'binary_ref':binary}
        config={'schema_version':'native-seeded-resume-v1','status':'approved','approval':base['approval'],
                **{key:reference(root,value) for key,value in names.items()},'max_detector_calls':0,'max_tracking_replays':0,
                'prior_new_pose_calls':1,'prior_saved_pose_frames':2,'pending_frame_indices':[2],'max_new_pose_calls':1,
                'once_only_claim_path':'analysis_results/resume_claim.json'}
        config['source_refs']=[config[key] for key in names]
        path=root/'resume.json';write_json(path,config)
        return path,config,values

    def refresh(self,root,path,config,key=None):
        if key:
            before=config[key];config[key]=reference(root,root/before['path'])
            config['source_refs']=[config[key] if ref==before else ref for ref in config['source_refs']]
        path.write_text(json.dumps(config),encoding='utf-8')

    def run_fixture(self,root,path,name='continued'):
        return run_resume(root,path,root/'analysis_results'/name,pose_factory=fixtures.FakeTransport,render_overlay=False)

    def test_only_never_executed_tail_and_prefix_exactly_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,config,old=self.fixture(root)
            before={ref['path']:ref['sha256'] for ref in config['source_refs']}
            with patch('pitch_analysis.native_seeded_live.associate_saved_boxes',side_effect=AssertionError('replay forbidden')), \
                 patch('pitch_analysis.native_person_box_transport.IsolatedDetectorTransport',side_effect=AssertionError('detector forbidden')):
                receipt=self.run_fixture(root,path)
            self.assertEqual((receipt['state'],receipt['pose_calls_completed'],receipt['total_new_pose_calls_across_segments']),('completed',1,2))
            self.assertEqual(receipt['full_pose_frames_saved'],3)
            _,frames=read_dataset(root/'analysis_results/continued/rtmpose/fixture')
            self.assertEqual([f.to_dict() for f in frames[:2]],old[:2])
            self.assertEqual(frames[2].to_dict()['model_selection']['run_segment'],'continuation')
            self.assertEqual(fixtures.FakeTransport.instances[0].limit,1)
            self.assertEqual({name:reference(root,root/name)['sha256'] for name in before},before)
            self.assertEqual(len((root/'analysis_results/continued/continuation.partial.jsonl').read_text().splitlines()),1)

    def test_existing_continuation_claim_blocks_second_worker_or_different_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,_,_=self.fixture(root);self.run_fixture(root,path)
            with self.assertRaises(ValueError):self.run_fixture(root,path,'retry')
            self.assertEqual(len(fixtures.FakeTransport.instances),1)

    def test_indeterminate_prior_started_call_rejected_before_claim_or_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,config,_=self.fixture(root)
            journal=root/config['journal_ref']['path']
            with journal.open('a',encoding='utf-8') as stream:stream.write(json.dumps({'event':'started','attempt_index':2})+'\n')
            self.refresh(root,path,config,'journal_ref')
            with self.assertRaisesRegex(ValueError,'Indeterminate'):self.run_fixture(root,path)
            self.assertEqual(fixtures.FakeTransport.instances,[])
            self.assertFalse((root/'analysis_results/resume_claim.json').exists())

    def test_changed_payload_or_saved_prefix_rejected_without_inference(self):
        for key in ['binary_ref','partial_ref']:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);path,config,_=self.fixture(root)
                artifact=root/config[key]['path']
                if key=='binary_ref':artifact.write_bytes(b'bad payload')
                else:
                    rows=[json.loads(line) for line in artifact.read_text().splitlines()]
                    rows[0]['landmarks'][0]['x_px']+=1
                    artifact.write_text(''.join(json.dumps(v)+'\n' for v in rows),encoding='utf-8')
                self.refresh(root,path,config,key)
                with self.assertRaises(ValueError):self.run_fixture(root,path)
                self.assertEqual(fixtures.FakeTransport.instances,[])

    def test_resume_cannot_expand_budget_or_include_previously_inferred_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,base,_=self.fixture(root)
            for key,value in [('pending_frame_indices',[0,2]),('max_new_pose_calls',2),('prior_new_pose_calls',0)]:
                config=deepcopy(base);config[key]=value;self.refresh(root,path,config)
                with self.subTest(key=key),self.assertRaises(ValueError):self.run_fixture(root,path)
            self.assertEqual(fixtures.FakeTransport.instances,[])

    def test_model_error_and_failed_error_recording_preserve_original_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path,_,_=self.fixture(root);fixtures.FakeTransport.fail_at=1
            from pitch_analysis.native_progress_log import append_event
            def record(folder,event,payload):
                if event=='failed':raise PermissionError('fixture error-record failure')
                return append_event(folder,event,payload)
            with patch('pitch_analysis.native_seeded_resume.append_event',side_effect=record):
                with self.assertRaisesRegex(RuntimeError,'fixture model failure') as caught:self.run_fixture(root,path)
            self.assertIn('Could not save failure receipt',caught.exception.__notes__[0])
            self.assertEqual(fixtures.FakeTransport.instances[0].calls_attempted,1)
            self.assertTrue((root/'analysis_results/resume_claim.json').exists())
            with self.assertRaises(ValueError):self.run_fixture(root,path,'retry')


if __name__=='__main__':unittest.main()
