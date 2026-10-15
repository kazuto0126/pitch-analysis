"""No-model regression tests for bounded expansion and crash-safe inference."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parents[1]/'src')]
import measure_expanded_roi_pose as m


class ExpandedProducerTests(unittest.TestCase):
    def test_float_geometry_not_rounded_crop_expansion(self):
        self.assertEqual(m.expand_bounds([10.6,20.8,11.2,13.4],100,100),[5,14,28,41])

    def test_clip_to_source(self):
        self.assertEqual(m.expand_bounds([1,1,10,10],12,12),[0,0,12,12])

    def test_missing_and_degenerate(self):
        for r in (None,[0,0,0,10],[0,0,10,-1],[200,200,2,2]):
            self.assertIsNone(m.expand_bounds(r,20,20))

    def test_nonfinite_and_boolean_rejected(self):
        for r in ([float('nan'),0,1,1],[0,0,True,2],[1,2,3]):
            with self.assertRaises(ValueError): m.expand_bounds(r,20,20)

    def test_journal_duplicate_and_budget(self):
        with tempfile.TemporaryDirectory() as d:
            j=m.AttemptJournal(Path(d)/'a.jsonl',1)
            j.append({'event':'started','attempt_id':'a'})
            with self.assertRaises(ValueError): j.append({'event':'started','attempt_id':'a'})
            with self.assertRaises(ValueError): j.append({'event':'started','attempt_id':'b'})

    def test_dangling_attempt_refuses_retry(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); j=m.AttemptJournal(p/'a.jsonl')
            j.append({'event':'started','attempt_id':'a','pixel':'x'})
            with self.assertRaisesRegex(ValueError,'retry refused'): j.existing('a',{'pixel':'x'},p/'result.json')

    def test_durable_result_reconciles_without_inference(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); j=m.AttemptJournal(p/'a.jsonl'); receipt={'pixel':'x'}
            j.append({'event':'started','attempt_id':'a',**receipt})
            value={'attempt_id':'a','input_receipt':receipt,'inference_status':'measured'}
            m.save(p/'result.json',value)
            self.assertEqual(j.existing('a',receipt,p/'result.json'),value)
            self.assertEqual(len(j.completed),1)
            j=m.AttemptJournal(p/'a.jsonl'); j.existing('a',receipt,p/'result.json')
            self.assertEqual(len((p/'a.jsonl').read_text().splitlines()),2)

    def test_tampered_completed_result_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); j=m.AttemptJournal(p/'a.jsonl')
            j.append({'event':'started','attempt_id':'a'})
            m.save(p/'r.json',{'attempt_id':'a','input_receipt':{},'inference_status':'measured'})
            j.existing('a',{},p/'r.json')
            (p/'r.json').write_text('{"attempt_id":"a","input_receipt":{},"inference_status":"measured","tampered":true}')
            with self.assertRaises(ValueError): j.existing('a',{},p/'r.json')

    def test_partial_journal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.jsonl'; p.write_text('{')
            with self.assertRaises(ValueError): m.AttemptJournal(p)

    def test_lock_prevents_second_invocation(self):
        with tempfile.TemporaryDirectory() as d:
            with m.exclusive_run(Path(d)/'lock'):
                with self.assertRaises(OSError):
                    with m.exclusive_run(Path(d)/'lock'): pass

    def test_clip_resume_replays_selector_without_detect(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); target={'pitch_id':'synthetic','total_frames':2,'width':6,'height':4}
            pixels=np.arange(72,dtype=np.uint8).reshape(4,6,3)
            def ref(name,value):
                m.save(p/name,value); return {'path':name,'sha256':m.sha(p/name)}
            sources={'video':ref('video.json',{}),'metadata':ref('meta.json',{'schema_version':'pitch-input-v1','pitch_id':'synthetic'})}
            sources['video_technical']=ref('technical.json',{'sha256':sources['video']['sha256'],
                'frame_count':2,'width':6,'height':4,'timestamps_ms':[0.,10.]})
            sources['tracked_roi']=ref('tracked.json',{'status':'sealed_measurements_only','target':target,
                'producer_sources':dict(sources),'initialization_frame_excluded_from_effectiveness':True,
                'frames':[{'frame_index':i,'decoded_bgr_sha256':m._pixel_hash(pixels),'native_timestamp_ms':i*10.,
                           'usable_rectangle_xywh':[1,1,2,2]} for i in range(2)]})
            class Capture:
                def __init__(self,*a): self.i=0
                def read(self):
                    self.i+=1; return (True,pixels.copy()) if self.i<=2 else (False,None)
                def get(self,*a): return (self.i-1)*10.
                def release(self): pass
            calls=[]
            class Estimator:
                def estimate(self,*a): calls.append(1); return SimpleNamespace(pose_landmarks=[])
                def __exit__(self,*a): pass
            with patch.object(m.cv2,'VideoCapture',Capture):
                j=m.AttemptJournal(p/'journal.jsonl')
                first=m.measure_clip(p,{'target':target,'producer_sources':sources},p/'out',j,Estimator)
                second=m.measure_clip(p,{'target':target,'producer_sources':sources},p/'out',j,
                    lambda: self.fail('Resume must not create a detector'))
            self.assertEqual(first,second); self.assertEqual(len(calls),2)
            self.assertEqual(len(j.started),2)


if __name__=='__main__': unittest.main()
