"""Input integrity and one-pass measurement safeguards; never invoke a real model."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import export_movenet_inputs as exporter
import measure_movenet_cohort as producer
import check_movenet_compatibility as compat


def reference(root,path):
    return {'path':path.relative_to(root).as_posix(),'sha256':compat.sha(path)}


class MovenetCohortSafeguards(unittest.TestCase):
    def test_full_frame_rgb_conversion_keeps_corners_and_native_time(self):
        bgr=np.zeros((4,6,3),np.uint8)
        bgr[0,0]=[11,22,33];bgr[-1,-1]=[44,55,66]
        tech={'fps':30.0,'timestamps_ms':[0,1000/30]}
        rgb,receipt=exporter.pixel_receipt(bgr,1,1000/30,tech,{'height':4,'width':6})
        self.assertEqual(rgb.shape,bgr.shape)
        self.assertEqual(rgb[0,0].tolist(),[33,22,11])
        self.assertEqual(rgb[-1,-1].tolist(),[66,55,44])
        self.assertEqual(receipt['timestamp_ms'],33)
        self.assertEqual(receipt['native_timestamp_ms'],1000/30)
        self.assertEqual(receipt['frame_time_sec'],1/30)

    def test_decoded_pts_and_dimensions_must_match_frozen_source(self):
        pixels=np.zeros((4,6,3),np.uint8)
        for frame,pts in ((pixels,1.0),(pixels[:,:5],0.0),(pixels.astype(np.float32),0.0)):
            with self.assertRaises(ValueError):
                exporter.pixel_receipt(frame,0,pts,{'fps':30,'timestamps_ms':[0]},{'height':4,'width':6})

    def test_producer_rejects_extra_annotation_role_before_model_load(self):
        clips=[{'target':{'total_frames':n,'pitch_id':f'pitch_{i:03d}'},'sources':{'ground_truth':{}}}
               for i,n in enumerate((87,175,115,114,101),1)]
        plan={'status':'frozen_before_measurement','synthetic_inference_budget':0,
              'formal_video_inference_budget':592,'sources':{},'clips':clips}
        with self.assertRaisesRegex(ValueError,'only declared'):
            producer.validate_plan(ROOT,plan)

    def test_changed_budget_or_duplicate_clip_is_rejected(self):
        clip={'target':{'total_frames':1,'pitch_id':'any'},'sources':{}}
        for budget,clips in ((2,[clip]),(2,[clip,clip])):
            plan={'status':'frozen_before_measurement','synthetic_inference_budget':0,
                  'formal_video_inference_budget':budget,'sources':{},'clips':clips}
            with self.assertRaisesRegex(ValueError,'Unfrozen plan'):
                producer.validate_plan(ROOT,plan)

    def make_export(self,root):
        target={'pitch_id':'sample','total_frames':1,'width':6,'height':4}
        sources={}
        for role in ('video','metadata','video_technical'):
            path=root/role;path.write_text(role)
            sources[role]=reference(root,path)
        technical={'sha256':sources['video']['sha256'],'frame_count':1,'width':6,'height':4,
                   'fps':30.0,'timestamps_ms':[0.0]}
        path=root/'video_technical';path.write_text(json.dumps(technical))
        sources['video_technical']=reference(root,path)
        pixels=np.zeros((1,4,6,3),np.uint8)
        archive=root/'frames.npz';np.savez(archive,rgb=pixels)
        sources['frame_archive']=reference(root,archive)
        receipt={'status':'sealed_full_frame_rgb_inputs','target':target,
                 'archive':sources['frame_archive'],'frame_key':'rgb','source_video':sources['video'],
                 'pose_inference_calls':0,'human_annotation_inputs':[],'fps_float':30.0,
                 'sources':{k:sources[k] for k in ('video','metadata','video_technical')},
                 'frames':[{'frame_index':0,'native_timestamp_ms':0.0,'timestamp_ms':0,'frame_time_sec':0.0,
                            'decoded_rgb_sha256':producer.hashlib.sha256(pixels[0].tobytes()).hexdigest()}]}
        path=root/'receipt.json';path.write_text(json.dumps(receipt))
        sources['export_receipt']=reference(root,path)
        return {'target':target,'sources':sources},receipt,pixels

    def test_sealed_export_is_loaded_without_pickle_or_color_conversion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            clip,expected,pixels=self.make_export(root)
            receipt,actual=producer.load_export(root,clip)
            self.assertEqual(receipt,expected)
            np.testing.assert_array_equal(actual,pixels)

    def test_rebound_archive_cannot_hide_changed_rgb_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            clip,receipt,pixels=self.make_export(root)
            pixels[:]=255
            path=root/'frames.npz';np.savez(path,rgb=pixels)
            clip['sources']['frame_archive']=reference(root,path)
            receipt['archive']=clip['sources']['frame_archive']
            path=root/'receipt.json';path.write_text(json.dumps(receipt))
            clip['sources']['export_receipt']=reference(root,path)
            with self.assertRaisesRegex(ValueError,'RGB bytes'):
                producer.load_export(root,clip)

    def test_incomplete_export_cannot_silently_shorten_denominator(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            clip,receipt,pixels=self.make_export(root)
            receipt['frames']=[]
            path=root/'receipt.json';path.write_text(json.dumps(receipt))
            clip['sources']['export_receipt']=reference(root,path)
            with self.assertRaisesRegex(ValueError,'incomplete'):
                producer.load_export(root,clip)

    def test_changed_frame_timeline_is_rejected_before_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            clip,receipt,_=self.make_export(root)
            receipt['frames'][0]['native_timestamp_ms']=1.0
            path=root/'receipt.json';path.write_text(json.dumps(receipt))
            clip['sources']['export_receipt']=reference(root,path)
            with self.assertRaisesRegex(ValueError,'timeline mismatch'):
                producer.load_export(root,clip)

    def test_native_all_six_slots_and_low_scores_remain_unclassified(self):
        mask=np.ones((256,256),np.float32)
        geometry=compat.geometry_from_mask(mask,4,6)
        raw=np.zeros((1,6,56),np.float32)
        frame=producer.record_frame({'frame_index':0},geometry,raw,.1)
        self.assertEqual(len(frame['slots']),6)
        self.assertEqual(np.asarray(frame['native_output']).shape,(1,6,56))
        self.assertTrue(all(s['subject_identity'] is None for s in frame['slots']))
        self.assertTrue(all(s['observability'] is None for s in frame['slots']))

    def test_nonfinite_native_output_fails_without_coordinate_fabrication(self):
        geometry=compat.geometry_from_mask(np.ones((256,256),np.float32),4,6)
        raw=np.zeros((1,6,56),np.float32);raw[0,0,0]=np.nan
        with self.assertRaises(ValueError):producer.record_frame({},geometry,raw,.1)

    def test_attempt_is_durably_flushed_before_inference_can_start(self):
        class Journal(io.StringIO):
            def flush(self):self.was_flushed=True
        journal=Journal();journal.was_flushed=False
        producer.mark_attempt(journal,7,'sample',6,'digest')
        self.assertTrue(journal.was_flushed)
        self.assertEqual(json.loads(journal.getvalue())['ordinal'],7)


if __name__=='__main__':unittest.main()
