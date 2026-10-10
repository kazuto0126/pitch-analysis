"""Pairing, missingness and independent pixel/mapping replay regressions."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
try:
    import evaluate_tracked_roi_pose as audit
    import measure_tracked_roi_pose as measure
finally:
    sys.path.pop(0)
from pitch_analysis.subject import PitcherSelector


def point(x=.5,y=.5,visibility=.9,presence=.9):
    return {'x':x,'y':y,'z':0.,'visibility':visibility,'presence':presence}


class PairingTests(unittest.TestCase):
    def row(self, *, index=1, status='visible', arms=None, crop=None, bounds=None):
        joint={'name':'RIGHT_ELBOW','status':status,'x_px':255 if status=='visible' else None,
               'y_px':314 if status=='visible' else None}
        return audit.point_row(index,joint,[100,100,400,500] if bounds is None else bounds,
            arms if arms is not None else {arm:{'RIGHT_ELBOW':point()} for arm in ('crop','image','video')},
            crop if crop is not None else {'RIGHT_ELBOW':point()},
            {'min_visibility':.5,'min_presence':.5},False)

    def test_hidden_and_uncertain_have_no_error_and_never_enter_pairs(self):
        rows=[self.row(status=s) for s in ('not_observable','uncertain')]
        for r in rows:
            self.assertIsNone(r['reference_in_crop'])
            self.assertIsNone(r['arms']['crop']['xy_error_px'])
            self.assertFalse(r['paired']['image']['eligible'])
        self.assertEqual(audit.summarize_points(rows)['supported_paired']['image']['common_points'],0)

    def test_missing_new_prediction_retained_in_denominator(self):
        r=self.row(arms={'crop':{},'image':{'RIGHT_ELBOW':point()},'video':{'RIGHT_ELBOW':point()}})
        s=audit.summarize_points([r])
        self.assertEqual(s['manual_records'],1)
        self.assertEqual(s['per_arm_conditional_not_directly_comparable']['crop']['missing'],1)
        self.assertEqual(s['supported_paired']['image']['common_points'],0)

    def test_reference_outside_crop_kept_even_if_model_extrapolates(self):
        r=self.row(bounds=[0,0,200,200])
        s=audit.summarize_points([r])
        self.assertEqual(s['visible_reference_outside_crop'],1)
        self.assertIsNotNone(r['arms']['crop']['gated_error_px'])
        self.assertFalse(r['paired']['image']['eligible'])

    def test_half_open_prediction_support_rejects_edge_and_negative_without_clamp(self):
        for x in (-.01,1.,1.2):
            r=self.row(crop={'RIGHT_ELBOW':point(x=x)})
            self.assertFalse(r['arms']['crop']['prediction_in_crop'])
            self.assertTrue(r['arms']['crop']['gate_pass'])
            self.assertFalse(r['paired']['image']['eligible'])

    def test_existing_visibility_and_presence_gates_both_required(self):
        for p in (point(visibility=.499),point(presence=.499)):
            r=self.row(arms={'crop':{'RIGHT_ELBOW':p},'image':{'RIGHT_ELBOW':point()},'video':{'RIGHT_ELBOW':point()}})
            self.assertFalse(r['paired']['image']['eligible'])
        r=self.row(arms={a:{'RIGHT_ELBOW':point(visibility=.5,presence=.5)} for a in ('crop','image','video')})
        self.assertTrue(r['paired']['image']['eligible'])

    def test_primary_and_secondary_common_sets_are_independent(self):
        r=self.row(arms={'crop':{'RIGHT_ELBOW':point()},'image':{},'video':{'RIGHT_ELBOW':point()}})
        self.assertFalse(r['paired']['image']['eligible'])
        self.assertTrue(r['paired']['video']['eligible'])

    def test_paired_means_never_use_unmatched_low_error_points(self):
        first=self.row(arms={'crop':{'RIGHT_ELBOW':point(x=.6)},'image':{'RIGHT_ELBOW':point(x=.7)},'video':{}})
        second=self.row(index=2,arms={'crop':{'RIGHT_ELBOW':point()},'image':{},'video':{}})
        s=audit.summarize_points([first,second])
        p=s['supported_paired']['image']
        self.assertEqual(p['common_points'],1)
        self.assertAlmostEqual(p['crop_error']['mean_px'],51)
        self.assertAlmostEqual(p['baseline_error']['mean_px'],102)
        self.assertEqual((p['improved'],p['worsened'],p['exactly_tied']),(1,0,0))
        self.assertAlmostEqual(s['per_arm_conditional_not_directly_comparable']['crop']['gated_error_conditional']['mean_px'],25.5)

    def test_statistics_empty_single_and_linear_p90(self):
        self.assertIsNone(audit.stats([])['mean_px'])
        self.assertEqual(audit.stats([5])['p90_px'],5)
        self.assertEqual(audit.stats([0,10])['p90_px'],9)

    def test_exact_ties_and_worse_counts(self):
        r=self.row()
        worse=self.row(index=2,arms={'crop':{'RIGHT_ELBOW':point(x=.6)},'image':{'RIGHT_ELBOW':point()},'video':{}})
        p=audit.summarize_points([r,worse])['supported_paired']['image']
        self.assertEqual((p['improved'],p['worsened'],p['exactly_tied']),(0,1,1))


class ReplayTests(unittest.TestCase):
    def fixture(self, missing=False):
        pixels=np.arange(510*628*3,dtype=np.uint8).reshape(628,510,3)
        tracked={'frame_index':0,'native_timestamp_ms':0.,'decoded_bgr_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),
                 'usable_rectangle_xywh':None if missing else [85,165,217,435]}
        pose=[SimpleNamespace(**point(y=.5)) for _ in range(33)]
        for i in (11,12): pose[i].y=.1
        for i in (27,28): pose[i].y=.9
        capture=Mock()
        capture.read.side_effect=[(True,pixels),(False,None)]
        capture.get.return_value=0.
        detector=Mock()
        detector.detect.return_value=SimpleNamespace(pose_landmarks=[pose])
        result=measure.measure_frames(capture,detector,PitcherSelector(),{'frames':[tracked]},
            {'timestamps_ms':[0.]},{**measure.TARGET,'total_frames':1},image_factory=lambda rgb:rgb)
        return result['frames'][0],tracked,pixels

    def test_independent_pixels_mapping_and_selector_replay(self):
        f,t,p=self.fixture()
        audit.replay_frame(f,t,p,0.,0.,PitcherSelector())

    def test_source_crop_pixels_and_pts_tampering_rejected(self):
        f,t,p=self.fixture()
        variants=[('decoded_bgr_sha256','wrong'),('crop_rgb_sha256','wrong'),('crop_shape',[1,2,3]),
                  ('native_timestamp_ms',1),('crop_bounds_xyxy',[0,0,1,1])]
        for key,value in variants:
            changed=copy.deepcopy(f);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                audit.replay_frame(changed,t,p,0.,0.,PitcherSelector())

    def test_mapped_coordinate_confidence_and_selector_tampering_rejected(self):
        f,t,p=self.fixture()
        for key in ('x','z','visibility'):
            changed=copy.deepcopy(f);changed['full_image_candidates'][0][0][key]+=.1
            with self.subTest(key=key),self.assertRaises(ValueError):
                audit.replay_frame(changed,t,p,0.,0.,PitcherSelector())
        changed=copy.deepcopy(f);changed['selection']['index']=None
        with self.assertRaises(ValueError): audit.replay_frame(changed,t,p,0.,0.,PitcherSelector())

    def test_missing_roi_has_no_fallback_pose_or_fabricated_pixels(self):
        f,t,p=self.fixture(missing=True)
        audit.replay_frame(f,t,p,0.,0.,PitcherSelector())
        f['crop_bgr_sha256']='fabricated'
        with self.assertRaises(ValueError): audit.replay_frame(f,t,p,0.,0.,PitcherSelector())

    def test_cli_exposes_evaluation_entry_point(self):
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/evaluate_tracked_roi_pose.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('measurements',result.stdout)


if __name__=='__main__': unittest.main()
