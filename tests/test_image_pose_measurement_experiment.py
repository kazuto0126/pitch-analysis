"""Verify measurement meaning with synthetic images, never formal pose inference."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

_script=Path(__file__).resolve().parents[1]/'scripts/measure_image_pose_evidence.py'
_spec=importlib.util.spec_from_file_location('image_measurement_experiment',_script)
measure=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure)

_evaluate_script=_script.with_name('evaluate_image_pose_evidence.py')
_evaluate_spec=importlib.util.spec_from_file_location('image_measurement_evaluator',_evaluate_script)
evaluate=importlib.util.module_from_spec(_evaluate_spec)
_evaluate_spec.loader.exec_module(evaluate)


class ImagePoseMeasurementExperimentTests(unittest.TestCase):
    def setUp(self):
        self.image=np.random.default_rng(42).integers(0,256,(180,180),dtype=np.uint8)
        self.corners=cv2.goodFeaturesToTrack(self.image,40,.02,8)[:,0,:].astype(float).tolist()

    def test_flow_recovers_known_image_translation(self):
        current=cv2.warpAffine(self.image,np.array([[1,0,4],[0,1,-2]],dtype=np.float32),(180,180))
        records=measure.flow_pairs(self.image,current,self.corners)
        valid=[r for r in records if r['numerically_usable']]
        self.assertGreater(len(valid),20)
        motion=measure.cohort_displacement([r['previous_xy_px'] for r in valid],[r['forward_xy_px'] for r in valid])
        np.testing.assert_allclose(motion['median_displacement_px'],[4,-2],atol=.15)
        self.assertTrue(all(r['fb_error_px'] is not None for r in valid))

    def test_stationary_pixels_do_not_follow_raw_skeleton_jump(self):
        records=measure.flow_pairs(self.image,self.image,self.corners)
        valid=[r for r in records if r['numerically_usable']]
        motion=measure.cohort_displacement([r['previous_xy_px'] for r in valid],[r['forward_xy_px'] for r in valid])
        self.assertAlmostEqual(measure.discrepancy([0,-60],motion['median_displacement_px']),60,places=3)
        self.assertAlmostEqual(measure.discrepancy([0,0],motion['median_displacement_px']),0,places=3)

    def test_survivor_cohort_uses_its_own_seed_positions(self):
        # Removed feature ID at the far left must not shift the origin median.
        seed=[[20,0],[40,0],[30,20]]
        current=[[30,3],[50,3],[40,23]]
        result=measure.cohort_displacement(seed,current)
        self.assertEqual(result['median_displacement_px'],[10,3])
        self.assertIsNone(result['reason'])

    def test_insufficient_spatial_support_is_null_not_stationary(self):
        for a,b in [([],[]),([[1,2]],[[3,4]]),([[0,0],[1,0],[2,0]],[[1,0],[2,0],[3,0]])]:
            result=measure.cohort_displacement(a,b)
            self.assertIsNone(result['median_displacement_px'])
            self.assertIsNotNone(result['reason'])
        self.assertIsNone(measure.discrepancy([3,4],None))
        self.assertIsNone(measure.discrepancy(None,[3,4]))

    def test_angle_boundary_does_not_create_a_358_degree_jump(self):
        self.assertEqual(measure.angular_delta(179,-179),2)
        self.assertEqual(measure.angular_delta(-179,179),-2)
        self.assertIsNone(measure.angular_delta(None,20))

    def test_missing_landmark_does_not_become_zero_length_or_recovered_xy(self):
        pose={'RIGHT_SHOULDER':{'x':.4,'y':.4,'visibility':.99,'presence':.99},
              'RIGHT_ELBOW':{'x':.5,'y':.5,'visibility':.2,'presence':.99}}
        result=measure.raw_geometry(pose,100,100,{'min_visibility':.5,'min_presence':.5})
        self.assertAlmostEqual(result['arms']['RIGHT_upper_arm']['length_px'],2**.5*10)
        self.assertFalse(result['arms']['RIGHT_upper_arm']['existing_endpoint_gate_pass'])
        self.assertIsNone(result['arms']['RIGHT_forearm']['length_px'])
        self.assertIsNone(result['joints']['RIGHT_WRIST']['xy_px'])

    def test_existing_output_is_rejected_without_touching_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary);marker=out/'preserve.txt';marker.write_text('original')
            with self.assertRaises(FileExistsError):measure.run_measurements(out/'input',out/'predictions',out)
            self.assertEqual(marker.read_text(),'original')

    def test_saved_video_experiment_never_reads_human_annotation_and_keeps_raw(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);inputs=root/'input';inputs.mkdir();pred=root/'predictions/pitcher/pitch_test';pred.mkdir(parents=True)
            gt=root/'predictions/ground_truth';gt.mkdir();(gt/'ground_truth.json').write_text('THIS IS INTENTIONALLY INVALID')
            video=inputs/'pitch_test.mp4'
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),30,(180,180))
            self.assertTrue(writer.isOpened())
            for _ in range(4):writer.write(cv2.cvtColor(self.image,cv2.COLOR_GRAY2BGR))
            writer.release()
            xy={'LEFT_SHOULDER':(.3,.3),'RIGHT_SHOULDER':(.7,.3),'LEFT_HIP':(.3,.7),'RIGHT_HIP':(.7,.7)}
            frames=[{'frame_index':i,'timestamp_ms':i*1000/30,'landmarks':[
                {'name':n,'x':x,'y':y,'visibility':.9,'presence':.9} for n,(x,y) in xy.items()]} for i in range(4)]
            payloads={
                'input_manifest.json':{'pitch_id':'pitch_test','pitcher':{'id':'pitcher','throws':'RIGHT'},'video':{'file':video.name}},
                'video_metadata.json':{'sha256':measure.sha256(video),'frame_count':4,'width':180,'height':180,'timestamps_ms':[i*1000/30 for i in range(4)]},
                'keypoints.json':{'pitch_id':'pitch_test','frames':frames},
                'pose_raw.capture.json':{'selection_frames':[{'frame_index':i,'status':'selected'} for i in range(4)]},
                'pose_clean.clean.json':{'min_visibility':.5,'min_presence':.5}}
            for name,payload in payloads.items():(pred/name).write_text(json.dumps(payload))
            raw_before=(pred/'keypoints.json').read_bytes()
            run=measure.run_measurements(inputs,root/'predictions',root/'output')
            result=json.loads((root/'output/pitch_test/image_pose_measurements.json').read_text())
            self.assertEqual(result['total_frames'],4)
            self.assertEqual(result['seed_frame'],0)
            self.assertEqual(result['reset_frames'],[])
            self.assertFalse(result['foreground_validated'])
            self.assertIsNone(result['warning_predictions'])
            self.assertEqual((pred/'keypoints.json').read_bytes(),raw_before)
            self.assertEqual(json.loads(run.read_text())['human_annotation_inputs'],[])

    def test_conditional_comparison_preserves_missing_positive_denominator(self):
        result=evaluate.conditional([None,3,1,None,99],
            ['confirmed','confirmed','known_negative','known_negative','not_observable'])
        self.assertEqual(result['human_positive_total'],2)
        self.assertEqual(result['positive_with_measurement']['n'],1)
        self.assertEqual(result['positive_without_measurement'],1)
        self.assertEqual(result['human_negative_total'],2)
        self.assertEqual(result['negative_without_measurement'],1)
        self.assertEqual(result['excluded_human_counts'],{'not_observable':1})
        self.assertEqual(result['conditional_rank_auc_higher_is_positive'],1)

    def test_rank_comparison_handles_ties_and_unmeasured_positives(self):
        self.assertEqual(evaluate.auc([2],[1,2,3]),.5)
        result=evaluate.conditional([None,1],['confirmed','known_negative'])
        self.assertIsNone(result['conditional_rank_auc_higher_is_positive'])
        self.assertEqual(result['positive_without_measurement'],1)
        self.assertIsNone(evaluate.auc([], [1]))

    def test_image_support_does_not_hide_missing_raw_comparison(self):
        frames=[{'raw_geometry':{'torso_center_px':[5,5],'torso_existing_gate_pass':True}},
            {'raw_geometry':{'torso_center_px':None,'torso_existing_gate_pass':False},
             'selection_status':'pose_missing','torso_step':{'median_displacement_px':[1,1]}}]
        self.assertEqual(evaluate.comparison_reason(frames,1),
            ['current_raw_torso_missing','current_selector_not_selected'])
        self.assertEqual(evaluate.comparison_reason(frames,0),['no_previous_frame'])


if __name__=='__main__':unittest.main()
