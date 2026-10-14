"""Synthetic regressions for complete angle transitions and noncausal point deltas."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parents[1]/'src')]
import audit_saved_roi_transitions as audit


def sources(total=5, manual_arm=None, baseline_arm=None, crop_arm=None):
    roles = tuple(dict.fromkeys(r for rs in audit.parent.original.FEATURES.values() for r in rs))
    names = ['RIGHT_SHOULDER','RIGHT_ELBOW','RIGHT_WRIST','LEFT_HIP','LEFT_KNEE','LEFT_ANKLE']
    manual_arm = manual_arm or [(20.,20.),(20.,40.),(40.,40.)]
    baseline_arm = baseline_arm or manual_arm; crop_arm = crop_arm or manual_arm
    leg = [(60.,20.),(60.,50.),(80.,80.)]
    manual_xy,baseline_xy,crop_xy = ([list(p) for p in arm+leg] for arm in (manual_arm,baseline_arm,crop_arm))
    target = {'pitch_id':'synthetic','total_frames':total,'width':200,'height':100}
    manual = {'source_video':{'pitch_id':'synthetic','total_frames':total,'sha256':'a'*64},
        'image_size':{'width':200,'height':100},'frames':[]}
    view = {'pitch_id':'synthetic','source_artifacts':{'original_video':{'sha256':'a'*64}},'frames':[]}
    saved = {name:[] for name in audit.parent.original.FEATURES}
    for i in range(total):
        time = i*100/3; major = i==1
        joints = [{'name':n,'status':'visible','x_px':p[0],'y_px':p[1]} for n,p in zip(names,manual_xy)]
        manual['frames'].append({'frame_index':i,'timestamp_ms':time,'joints':joints})
        view['frames'].append({'frame_index':i,'timestamp_ms':time,'human_review':{'major_pose_failure':[{}] if major else []},
            'focus_joints':{r:{'landmark':n,'model_state':'observed',
                'processed_landmark':{'x':p[0]/200,'y':p[1]/100,'usable':True}} for r,n,p in zip(roles,names,baseline_xy)}})
        by_name = {j['name']:j for j in joints}
        for feature,required in audit.parent.original.FEATURES.items():
            indices = [roles.index(r) for r in required]; members = [names[j] for j in indices]
            reference = audit.parent.original.manual_reference(by_name,members)
            streams = {}
            for arm in audit.parent.STREAMS:
                points = crop_xy if arm=='crop' else baseline_xy
                angle = audit.parent.original.angle([points[j] for j in indices])
                streams[arm] = {'points':None if arm=='video_processed' else [
                    {'landmark':names[j],'xy_px':list(points[j])} for j in indices],
                    'numerical_support':True,'numerical_supported_angle_deg':angle,
                    'signed_error_deg':angle-reference['value_deg'],'unavailable_reasons':[]}
            saved[feature].append({'frame_index':i,'timestamp_ms':time,'effectiveness_eligible':i!=0,
                'required_roles':list(required),'required_landmarks':members,'streams':streams,'manual_reference':reference,
                'original_model_states':{r:'observed' for r in required},'existing_major_hold':major,'existing_eligible':not major,
                'existing_review_status':'hold_major' if major else 'eligible','original_feature_flags':['original'],
                'reference_all_points_in_crop':True,'crop_bounds_xyxy':[0,0,200,100]})
    return saved,manual,view,target


def unavailable(saved, feature, frame, arm, reasons=None):
    stream = saved[feature][frame]['streams'][arm]
    stream.update(numerical_support=False,numerical_supported_angle_deg=None,signed_error_deg=None,
        unavailable_reasons=reasons or ['below_original_gate:RIGHT_WRIST'])


def manual_status(source, frame, name, status):
    saved,manual,view,target = source
    for joint in manual['frames'][frame]['joints']:
        if joint['name']==name: joint['status']=status
    joints = {j['name']:j for j in manual['frames'][frame]['joints']}
    for rows in saved.values():
        row=rows[frame]
        row['manual_reference']=audit.parent.original.manual_reference(joints,row['required_landmarks'])
        row['reference_all_points_in_crop']=None
        ref=row['manual_reference']['value_deg']
        for stream in row['streams'].values():
            value=stream['numerical_supported_angle_deg']
            stream['signed_error_deg']=value-ref if value is not None and ref is not None else None


class SavedRoiTransitionTests(unittest.TestCase):
    def test_four_transitions_keep_full_and_nonseed_denominators(self):
        source=sources(); saved=source[0]; feature='throwing_elbow_angle'
        unavailable(saved,feature,2,'crop'); unavailable(saved,feature,3,'image')
        unavailable(saved,feature,4,'crop'); unavailable(saved,feature,4,'image')
        records=audit.audit_rows(*source); report=audit.summarize(records)
        self.assertEqual((report['source_frames'],report['non_seed_frames'],report['source_records'],report['non_seed_records']),(5,4,30,24))
        group=report['features'][feature]['image']
        self.assertEqual([group['main_non_seed']['transitions'][k]['frames'] for k in audit.TRANSITIONS],[1,1,1,1])
        self.assertEqual(group['full_source']['transitions']['both_available']['frame_indices'],[0,1])
        self.assertEqual([r['frame_index'] for r in records[:5]],list(range(5)))

    def test_reference_missing_does_not_hide_availability_or_create_zero_error(self):
        source=sources(); manual_status(source,2,'RIGHT_WRIST','not_observable')
        records=audit.audit_rows(*source)
        row=next(r for r in records if r['feature']=='throwing_elbow_angle' and r['baseline']=='image' and r['frame_index']==2)
        self.assertEqual(row['availability_transition'],'both_available'); self.assertFalse(row['reference_available'])
        self.assertIsNone(row['baseline_signed_error_deg']); self.assertIsNone(row['angle_error_change'])
        self.assertIsNone(row['points'][2]['manual_xy_px']); self.assertIsNone(row['points'][2]['crop_error_px'])
        group=audit.summarize(records)['features']['throwing_elbow_angle']['image']['main_non_seed']
        self.assertEqual((group['frame_denominator'],group['reference_available'],group['reference_unavailable']),(4,3,1))
        self.assertEqual(group['transitions']['both_available']['reference_unavailable'],1)

    def test_uncertain_guessed_xy_is_not_visible_reference_and_partial_distances_remain(self):
        source=sources(); manual_status(source,2,'RIGHT_ELBOW','uncertain')
        row=audit.audit_rows(*source)[2]
        self.assertIsNone(row['points'][1]['manual_xy_px']); self.assertIsNone(row['points'][1]['crop_minus_baseline_error_px'])
        self.assertEqual(row['points'][0]['crop_error_px'],0.)
        self.assertIsNone(row['point_error_pattern'])

    def test_nonexclusive_reasons_for_same_loss_are_all_counted_not_priority_partitioned(self):
        source=sources(); reasons=['below_original_gate:RIGHT_WRIST','prediction_outside_or_missing_crop:RIGHT_WRIST']
        unavailable(source[0],'throwing_elbow_angle',2,'crop',reasons)
        report=audit.summarize(audit.audit_rows(*source))
        loss=report['features']['throwing_elbow_angle']['image']['main_non_seed']['transitions']['baseline_only']
        self.assertEqual(loss['frames'],1); self.assertEqual(loss['crop_reason_counts_nonexclusive'],dict.fromkeys(reasons,1))

    def test_processed_point_error_uses_original_processed_xy_never_raw_substitute(self):
        source=sources(); saved,manual,view,target=source
        point=view['frames'][2]['focus_joints']['throwing_wrist']['processed_landmark']; point.update(x=.3,y=.7)
        stream=saved['throwing_elbow_angle'][2]['streams']['video_processed']
        value=audit.parent.original.angle([(20,20),(20,40),(60,70)])
        stream['numerical_supported_angle_deg']=value; stream['signed_error_deg']=value-90.
        records=audit.audit_rows(*source)
        processed=next(r for r in records if r['feature']=='throwing_elbow_angle' and r['baseline']=='video_processed' and r['frame_index']==2)
        raw=next(r for r in records if r['feature']=='throwing_elbow_angle' and r['baseline']=='video_raw' and r['frame_index']==2)
        self.assertEqual(processed['points'][2]['baseline_xy_px'],[60.,70.])
        self.assertGreater(processed['points'][2]['baseline_error_px'],0.)
        self.assertEqual(raw['points'][2]['baseline_error_px'],0.)
        point['usable']=False
        with self.assertRaisesRegex(ValueError,'original point geometry'): audit.audit_rows(*source)

    def test_angle_worse_can_coexist_with_all_three_smaller_pixel_errors_without_selecting_points(self):
        source=sources(manual_arm=[(40.,20.),(20.,20.),(20.,40.)],
            baseline_arm=[(40.,25.),(25.,25.),(25.,40.)],crop_arm=[(40.,22.),(20.5,20.5),(22.,40.)])
        records=audit.audit_rows(*source); row=records[1]
        self.assertEqual(row['angle_error_change'],'worsened'); self.assertEqual(row['point_error_pattern'],'all_three_smaller')
        self.assertTrue(all(p['crop_minus_baseline_error_px']<0 for p in row['points']))
        group=audit.summarize(records)['features']['throwing_elbow_angle']['image']['main_non_seed']
        self.assertEqual(group['angle_worsened_point_patterns']['all_three_smaller']['frame_indices'],[1,2,3,4])
        self.assertEqual(len(row['points']),3)

    def test_zero_degree_reference_and_zero_error_are_available_not_missing(self):
        source=sources(manual_arm=[(40.,20.),(20.,20.),(60.,20.)])
        row=audit.audit_rows(*source)[1]
        self.assertTrue(row['reference_available']); self.assertEqual(row['baseline_angle_deg'],0.)
        self.assertEqual(row['crop_minus_baseline_absolute_error_deg'],0.)
        self.assertEqual(row['angle_error_change'],'numerically_tied'); self.assertEqual(row['point_error_pattern'],'mixed_or_tied')

    def test_major_eligibility_and_crop_outside_are_context_not_support_filters(self):
        source=sources(); source[0]['throwing_elbow_angle'][1]['reference_all_points_in_crop']=False
        records=audit.audit_rows(*source); row=records[1]
        self.assertTrue(row['existing_major_hold']); self.assertFalse(row['existing_eligible'])
        self.assertEqual(row['availability_transition'],'both_available')
        self.assertIsNotNone(row['angle_error_change'])
        report=audit.summarize(records)['features']['throwing_elbow_angle']['image']
        self.assertEqual(report['by_reference_in_crop']['outside']['angle_common_frames'],1)
        self.assertEqual(report['by_original_major_hold']['True']['angle_common_frames'],1)

    def test_seed_only_clip_has_zero_main_denominator_and_complete_zero_state_counts(self):
        report=audit.summarize(audit.audit_rows(*sources(total=1)))
        self.assertEqual(report['non_seed_records'],0)
        main=report['features']['throwing_elbow_angle']['image']['main_non_seed']
        self.assertEqual(main['frame_denominator'],0)
        self.assertEqual([main['transitions'][k]['frames'] for k in audit.TRANSITIONS],[0,0,0,0])

    def test_truncated_wrong_source_or_inconsistent_saved_geometry_is_rejected(self):
        for kind in ('frames','video','geometry','modelstate','reference'):
            source=sources()
            if kind=='frames': source[0]['throwing_elbow_angle'].pop()
            if kind=='video': source[1]['source_video']['sha256']='b'*64
            if kind=='geometry': source[0]['throwing_elbow_angle'][2]['streams']['image']['points'][2]['xy_px']=[90.,90.]
            if kind=='modelstate': source[0]['throwing_elbow_angle'][2]['original_model_states']['throwing_elbow']='missing'
            if kind=='reference': source[0]['throwing_elbow_angle'][2]['manual_reference']['value_deg']=17.
            with self.assertRaises(ValueError): audit.audit_rows(*source)
        records=audit.audit_rows(*sources()); records.pop()
        with self.assertRaises(ValueError): audit.summarize(records)

    def test_inputs_and_outputs_keep_all_fixed_members_without_mutation(self):
        source=sources(); before=deepcopy(source)
        records=audit.audit_rows(*source); audit.summarize(records)
        self.assertEqual(source,before)
        self.assertEqual([p['role'] for p in records[0]['points']],['throwing_shoulder','throwing_elbow','throwing_wrist'])
        records[0]['original_feature_flags'].append('output_only')
        self.assertEqual(source,before)

    def _plan(self):
        return {'status':'frozen_before_saved_roi_transition_audit','policy':audit.POLICY,'target_pitch_id':'synthetic',
            'pose_inference_budget':0,'tracker_inference_budget':0,'production_adoption':False,
            'output_directory':'analysis_results/synthetic_saved_roi_transition_never_created',
            'code':{k:{'path':v,'sha256':'a'*64} for k,v in audit.CODE_PATHS.items()},
            **{k:{'path':'fake/'+k+'.json','sha256':'b'*64} for k in audit.INPUTS}}

    def test_wrapper_refuses_hash_mismatch_before_reconstruction_or_writing(self):
        root=Path(__file__).resolve().parents[1]; plan=self._plan()
        with patch.object(audit.parent.original,'read',return_value=plan),patch.object(audit,'sha',return_value='a'*64), \
                patch.object(audit,'bound',side_effect=ValueError('Changed bound source')),patch.object(audit.parent,'_angle_sources') as load:
            with self.assertRaisesRegex(ValueError,'Changed bound source'): audit.run(root,root/'fake_plan.json',root/plan['output_directory'])
            load.assert_not_called()

    def test_new_manifest_cannot_claim_different_target_from_sealed_parent(self):
        root=Path(__file__).resolve().parents[1]; plan=self._plan()
        with patch.object(audit.parent.original,'read',side_effect=[plan,{'target_pitch_id':'different_clip'}]), \
                patch.object(audit,'sha',return_value='a'*64),patch.object(audit,'bound',side_effect=lambda repo,ref:repo/ref['path']), \
                patch.object(audit.parent,'_angle_sources') as load:
            with self.assertRaisesRegex(ValueError,'target differs'): audit.run(root,root/'fake_plan.json',root/plan['output_directory'])
            load.assert_not_called()


if __name__=='__main__': unittest.main()
