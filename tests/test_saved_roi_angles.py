"""Synthetic tests for angle support, complete denominators and fixed pairing."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parents[1]/'src')]
import assess_saved_roi_angles as assessment


def fixtures(total=3, throws='RIGHT'):
    roles = tuple(dict.fromkeys(r for rs in assessment.original.FEATURES.values() for r in rs))
    lead = 'LEFT' if throws == 'RIGHT' else 'RIGHT'
    names = [throws+'_'+n for n in ('SHOULDER','ELBOW','WRIST')]+[lead+'_'+n for n in ('HIP','KNEE','ANKLE')]
    mapping = dict(zip(roles,names)); xy = [(20.,20.),(20.,40.),(40.,40.),(60.,20.),(60.,50.),(80.,80.)]
    target = {'pitch_id':'synthetic','total_frames':total,'width':200,'height':100}
    data = {'target':target,'important_joints':mapping,'frames':[]}
    view = {'source_artifacts':{'original_video':{'sha256':'a'*64}},'frames':[]}
    manual = {'source_video':{'pitch_id':'synthetic','total_frames':total,'sha256':'a'*64},
        'image_size':{'width':200,'height':100},'frames':[]}
    feature_view = {'pitch_id':'synthetic','frames':[]}
    roi = {'target':target,'frames':[]}
    config = {'min_visibility':.5,'min_presence':.5}
    image = {**target,'video_sha256':'a'*64,'gate':config,'frames':[]}
    video_raw, capture = [],{'selection_frames':[]}
    for i in range(total):
        points = {n:{'x':.5,'y':.5,'z':0.,'visibility':.9,'presence':.9} for n in assessment.mode.LANDMARK_NAMES}
        for name,p in zip(names,xy): points[name].update(x=p[0]/200,y=p[1]/100)
        candidates = [[deepcopy(points[n]) for n in assessment.mode.LANDMARK_NAMES]]
        selection = {'status':'selected','index':0}; ms = i*100/3
        data['frames'].append({'frame_index':i,'joints':{name:{'raw':{'finite':True,'xy_px':[p[0],p[1]],
            'visibility':.9,'presence':.9}} for name,p in zip(names,xy)}})
        view['frames'].append({'frame_index':i,'timestamp_ms':ms,'focus_joints':{
            r:{'model_state':'observed','processed_landmark':{'x':p[0]/200,'y':p[1]/100,'usable':True}} for r,p in zip(roles,xy)},
            'human_review':{'major_pose_failure':[{'status':'confirmed'}] if i==1 else []}})
        manual['frames'].append({'frame_index':i,'timestamp_ms':ms,'joints':[
            {'name':n,'status':'visible','x_px':p[0],'y_px':p[1]} for n,p in zip(names,xy)]})
        feature_view['frames'].append({'frame_index':i,'features':{name:{'saved_values':{
            key:assessment.original.angle([xy[roles.index(r)] for r in members]) for key in ('base','feature_interpolated','smoothed')},
            'status':'hold_major' if i==1 else 'eligible','eligible':i!=1,'saved_flags':['original_flag']}
            for name,members in assessment.original.FEATURES.items()}})
        roi['frames'].append({'frame_index':i,'native_timestamp_ms':ms,'decoded_bgr_sha256':str(i),
            'full_image_candidates':deepcopy(candidates),'crop_candidates':deepcopy(candidates),
            'selection':deepcopy(selection),'crop_bounds_xyxy':[0,0,200,100]})
        image['frames'].append({'frame_index':i,'native_timestamp_ms':ms,'decoded_bgr_sha256':str(i),
            'image_candidates':deepcopy(candidates),'image_selection':deepcopy(selection)})
        video_raw.append(points)
        capture['selection_frames'].append({'frame_index':i,'timestamp_ms':round(ms),**selection})
    return data,view,manual,feature_view,roi,image,video_raw,capture,config


def compare(source):
    data,view,manual,features,roi,image,raw,capture,config = source
    old = assessment.original.compare_rows(data,view,features,manual)
    return assessment.compare(data,view,manual,old,roi,image,raw,capture,config)


def candidate(source, frame, arm, landmark):
    data,view,manual,features,roi,image,raw,capture,config = source
    name = data['important_joints'][landmark]; index = assessment.mode.LANDMARK_NAMES.index(name)
    return (roi['frames'][frame]['full_image_candidates'] if arm=='crop' else image['frames'][frame]['image_candidates'])[0][index]


class SavedRoiAngleTests(unittest.TestCase):
    def test_source_pixel_geometry_and_bound_role_mapping_not_pitch_or_right_hand_hardcoded(self):
        rows = compare(fixtures(throws='LEFT'))['throwing_elbow_angle']
        self.assertEqual(rows[1]['required_landmarks'],['LEFT_SHOULDER','LEFT_ELBOW','LEFT_WRIST'])
        self.assertEqual(rows[1]['manual_reference']['value_deg'],90.)
        self.assertEqual(rows[1]['streams']['crop']['numerical_supported_angle_deg'],90.)
        self.assertEqual(rows[1]['streams']['crop']['points'][0]['xy_px'],[20.,20.])

    def test_seed_saved_but_excluded_from_main_denominators_and_original_holds_retained(self):
        rows = compare(fixtures())['throwing_elbow_angle']; summary = assessment.summarize(rows)
        self.assertEqual((len(rows),summary['source_frame_denominator'],summary['evaluation_frame_denominator']),(3,3,2))
        self.assertEqual(summary['paired_crop_comparisons']['image']['frame_indices'],[1,2])
        self.assertEqual(assessment.summarize(rows,include_seed=True)['evaluation_frame_denominator'],3)
        self.assertTrue(rows[1]['existing_major_hold']); self.assertFalse(rows[1]['existing_eligible'])
        self.assertEqual(summary['by_original_major_hold']['True']['evaluation_frame_denominator'],1)
        self.assertEqual(rows[1]['original_feature_flags'],['original_flag'])

    def test_hidden_uncertain_guessed_xy_stay_null_not_zero_error_or_negative_reference(self):
        source = fixtures()
        source[2]['frames'][1]['joints'][2]['status']='not_observable'
        source[2]['frames'][2]['joints'][2]['status']='uncertain'
        rows = compare(source)['throwing_elbow_angle']; summary = assessment.summarize(rows)
        self.assertEqual(summary['evaluation_frame_denominator'],2)
        self.assertEqual(summary['manual_reference_frames'],0)
        self.assertEqual(summary['paired_crop_comparisons']['image']['common_frames'],0)
        for row in rows[1:]:
            self.assertIsNone(row['streams']['crop']['signed_error_deg'])
            self.assertIsNone(row['reference_all_points_in_crop'])
        self.assertEqual(summary['streams']['crop']['prediction_present_without_manual_reference'],2)

    def test_manual_reference_outside_crop_remains_in_primary_pairs_and_outside_stratum(self):
        source = fixtures()
        source[2]['frames'][1]['joints'][2]['x_px']=150.
        source[4]['frames'][1]['crop_bounds_xyxy']=[0,0,100,100]
        for p in source[4]['frames'][1]['crop_candidates'][0]: p['x']*=2
        rows = compare(source)['throwing_elbow_angle']; row = rows[1]
        self.assertIs(row['reference_all_points_in_crop'],False)
        self.assertTrue(row['streams']['crop']['numerical_support'])
        summary = assessment.summarize(rows)
        self.assertIn(1,summary['paired_crop_comparisons']['image']['frame_indices'])
        self.assertEqual(summary['by_reference_in_crop']['outside']['paired_crop_comparisons']['image']['common_frames'],1)

    def test_prediction_outside_crop_even_at_half_open_edge_is_ungated_diagnostic_only(self):
        source = fixtures(); source[4]['frames'][1]['crop_bounds_xyxy']=[0,0,100,100]
        for p in source[4]['frames'][1]['crop_candidates'][0]: p['x']*=2
        name=source[0]['important_joints']['throwing_wrist']; index=assessment.mode.LANDMARK_NAMES.index(name)
        source[4]['frames'][1]['crop_candidates'][0][index]['x']=1.
        candidate(source,1,'crop','throwing_wrist')['x']=.5
        stream = compare(source)['throwing_elbow_angle'][1]['streams']['crop']
        self.assertIsNotNone(stream['ungated_angle_deg'])
        self.assertFalse(stream['numerical_support']); self.assertIsNone(stream['numerical_supported_angle_deg'])
        self.assertIn('prediction_outside_or_missing_crop:'+name,stream['unavailable_reasons'])

    def test_original_visibility_and_presence_both_required_without_new_cutoff(self):
        for field in ('visibility','presence'):
            source = fixtures(); candidate(source,1,'crop','throwing_elbow')[field]=.499
            stream = compare(source)['throwing_elbow_angle'][1]['streams']['crop']
            self.assertIsNotNone(stream['ungated_angle_deg']); self.assertFalse(stream['numerical_support'])
            source = fixtures(); candidate(source,1,'crop','throwing_elbow')[field]=.5
            self.assertTrue(compare(source)['throwing_elbow_angle'][1]['streams']['crop']['numerical_support'])

    def test_raw_source_outside_image_has_angle_but_no_primary_support(self):
        source = fixtures(); candidate(source,1,'image','throwing_wrist')['x']=1.1
        rows = compare(source)['throwing_elbow_angle']; stream=rows[1]['streams']['image']
        self.assertIsNotNone(stream['ungated_angle_deg']); self.assertFalse(stream['numerical_support'])
        self.assertEqual(assessment.summarize(rows)['paired_crop_comparisons']['image']['frame_indices'],[2])

    def test_missing_selection_remains_in_each_full_denominator_with_explicit_reason(self):
        source = fixtures(); frame=source[5]['frames'][1]
        frame['image_candidates']=[]; frame['image_selection']={'status':'rejected','index':None}
        rows=compare(source)['throwing_elbow_angle']; summary=assessment.summarize(rows)
        self.assertEqual(summary['streams']['image']['frame_denominator'],2)
        self.assertEqual(summary['streams']['image']['reference_present_prediction_missing'],1)
        self.assertIn('selection_not_selected',rows[1]['streams']['image']['unavailable_reasons'])
        self.assertEqual(summary['paired_crop_comparisons']['video_raw']['common_frames'],2)
        self.assertEqual(summary['paired_crop_comparisons']['image']['common_frames'],1)

    def test_same_frame_pairing_not_different_conditional_means_and_processed_is_secondary(self):
        source=fixtures()
        candidate(source,1,'image','throwing_wrist')['y']=.6
        source[5]['frames'][2]['image_candidates']=[]
        source[5]['frames'][2]['image_selection']={'status':'rejected','index':None}
        # An unmatched crop error must not enter the paired statistic.
        candidate(source,2,'crop','throwing_wrist')['y']=.9
        rows=compare(source)['throwing_elbow_angle']; summary=assessment.summarize(rows)
        paired=summary['paired_crop_comparisons']['image']
        self.assertEqual(paired['frame_indices'],[1]); self.assertEqual(paired['improved'],1)
        self.assertEqual(paired['crop_error']['mae_deg'],0.)
        self.assertGreater(summary['streams']['crop']['error_conditional_not_directly_comparable']['mae_deg'],0.)
        self.assertEqual(summary['paired_crop_comparisons']['video_processed']['comparison_scope'],'secondary_original_processed_base')

    def test_missing_original_processed_value_does_not_remove_supported_raw_comparisons(self):
        source=fixtures(); source[1]['frames'][1]['focus_joints']['throwing_wrist']['processed_landmark']['usable']=False
        source[1]['frames'][1]['focus_joints']['throwing_wrist']['model_state']='missing'
        for key in source[3]['frames'][1]['features']['throwing_elbow_angle']['saved_values']:
            source[3]['frames'][1]['features']['throwing_elbow_angle']['saved_values'][key]=None
        rows=compare(source)['throwing_elbow_angle']; summary=assessment.summarize(rows)
        self.assertEqual(summary['paired_crop_comparisons']['video_raw']['common_frames'],2)
        self.assertEqual(summary['paired_crop_comparisons']['video_processed']['common_frames'],1)
        self.assertEqual(rows[1]['original_model_states']['throwing_wrist'],'missing')

    def test_exact_ties_empty_conditional_stats_and_linear_p95(self):
        rows=compare(fixtures())['throwing_elbow_angle']; summary=assessment.summarize(rows)
        self.assertEqual(summary['paired_crop_comparisons']['image']['numerically_tied'],2)
        empty=assessment.summarize([])
        self.assertEqual(empty['evaluation_frame_denominator'],0)
        self.assertIsNone(empty['paired_crop_comparisons']['image']['crop_error']['mae_deg'])
        self.assertEqual(assessment.original.error_stats([0.,10.,20.])['p95_absolute_deg'],19.)

    def test_inputs_and_original_saved_arrays_not_mutated(self):
        source=fixtures(); before=deepcopy(source)
        rows=compare(source); assessment.summarize(rows['throwing_elbow_angle'])
        self.assertEqual(source,before)

    def test_frame_hash_time_gate_or_original_raw_mismatch_is_rejected(self):
        for kind in ('hash','time','gate','raw','frames'):
            source=fixtures()
            if kind=='hash': source[5]['frames'][1]['decoded_bgr_sha256']='other_pixels'
            if kind=='time': source[5]['frames'][1]['native_timestamp_ms']+=1
            if kind=='gate': source[5]['gate']={'min_visibility':.4,'min_presence':.5}
            if kind=='raw': source[6][1]['RIGHT_WRIST']['x']+=.01
            if kind=='frames': source[4]['frames'].pop()
            with self.assertRaises(ValueError): compare(source)

    def test_wrapper_refuses_source_hash_mismatch_before_loading_predictions(self):
        root=Path(__file__).resolve().parents[1]
        plan={'status':'frozen_before_saved_roi_angle_assessment','policy':assessment.POLICY,
            'pose_inference_budget':0,'tracker_inference_budget':0,'production_adoption':False,
            'output_directory':'analysis_results/synthetic_saved_roi_angles_never_created',
            'code':{k:{'path':v,'sha256':'a'*64} for k,v in assessment.CODE_PATHS.items()},
            **{k:{'path':'bad/'+k,'sha256':'b'*64} for k in assessment.INPUTS}}
        with patch.object(assessment.original,'read',return_value=plan),patch.object(assessment,'sha',return_value='a'*64), \
                patch.object(assessment,'bound',side_effect=ValueError('Changed bound source')),patch.object(assessment,'_angle_sources') as load:
            with self.assertRaisesRegex(ValueError,'Changed bound source'):
                assessment.run(root,root/'synthetic_plan.json',root/plan['output_directory'])
            load.assert_not_called()

    def test_gate_sidecar_binds_original_raw_capture_dimensions_and_full_timeline(self):
        root=Path(__file__).resolve().parents[1]; target=fixtures()[0]['target']
        raw={'path':'analysis_results/synthetic_raw.csv','sha256':'a'*64}
        capture={'path':'analysis_results/synthetic_capture.json','sha256':'b'*64}
        config={'schema_version':'pose-clean-v0.2','source_pose_csv':str(root/raw['path']),
            'source_context':str(root/capture['path']),'width':200,'height':100,
            'requested_frames':3,'timeline_start_frame':0,'timeline_end_frame':2,
            'min_visibility':.5,'min_presence':.5}
        with patch.object(assessment,'bound',side_effect=lambda repo,ref:(repo/ref['path']).resolve()):
            self.assertEqual(assessment._verify_clean_config(root,config,target,raw,capture),{'min_visibility':.5,'min_presence':.5})
            for key,value in (('source_pose_csv','other.csv'),('source_context','other.capture.json'),
                    ('width',201),('height',101),('requested_frames',2),('timeline_start_frame',1),('timeline_end_frame',3)):
                with self.assertRaisesRegex(ValueError,'gate configuration source or frame identity'):
                    assessment._verify_clean_config(root,{**config,key:value},target,raw,capture)


if __name__=='__main__': unittest.main()
