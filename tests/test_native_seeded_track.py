"""Synthetic policy checks; never load real saved detections or pose outputs."""
from copy import deepcopy
import json
import unittest

from pitch_analysis.native_seeded_track import TRACK_POLICY, associate_saved_boxes


def candidate(index, box, *, eligible=True, score=.8):
    return {'output_index': index, 'bbox_original_xyxy_px': box, 'eligible': eligible, 'native_score': score}


def timeline(*frames):
    return [{'frame_index': i, 'timestamp_ms': i * (1001/60), 'decoded_bgr_sha256': 'a'*64,
             'candidates': boxes} for i, boxes in enumerate(frames)]


class NativeSeededTrackTests(unittest.TestCase):
    def test_seed_is_operator_index_and_ignores_higher_model_score(self):
        records=timeline([candidate(8,[0,0,10,10],score=.01),candidate(1,[20,0,30,10],score=.99)],
                         [candidate(9,[20,0,30,10],score=.999),candidate(4,[1,0,11,10],score=.01)])
        original=deepcopy(records)
        result=associate_saved_boxes(records,seed_output_index=8)
        self.assertEqual([r['status'] for r in result],['seeded','linked'])
        self.assertEqual([r['selected_output_index'] for r in result],[8,4])
        self.assertEqual(result[1]['previous_eligible_output_indices'],[8,1])
        self.assertEqual(result[1]['current_eligible_output_indices'],[9,4])
        self.assertAlmostEqual(result[1]['match_iou'],9/11)
        self.assertEqual(result[0]['iou_matrix'],[])
        self.assertEqual(result[0]['track_policy'],TRACK_POLICY)
        self.assertEqual(records,original)
        result[0]['selected_bbox_xyxy_px'][0]=500
        self.assertEqual(records,original)

    def test_ineligible_candidates_are_not_rescored_into_tracking(self):
        records=timeline([candidate(0,[0,0,10,10])],
                         [candidate(0,[0,0,10,10],eligible=False,score=1.),candidate(2,[1,0,11,10])])
        result=associate_saved_boxes(records,seed_output_index=0)
        self.assertEqual(result[1]['selected_output_index'],2)
        self.assertEqual(result[1]['current_eligible_output_indices'],[2])

    def test_two_positive_overlaps_can_have_one_mutual_unique_maximum(self):
        records=timeline([candidate(0,[0,0,10,10]),candidate(1,[9,0,19,10])],
                         [candidate(5,[.1,0,10.1,10]),candidate(6,[9.1,0,19.1,10])])
        result=associate_saved_boxes(records,seed_output_index=0)
        self.assertEqual(result[1]['status'],'linked')
        self.assertEqual(result[1]['selected_output_index'],5)
        self.assertGreater(result[1]['iou_matrix'][0][1],0)

    def test_row_maximum_tie_is_terminal_and_later_matrices_are_saved(self):
        records=timeline([candidate(0,[0,0,10,10])],
                         [candidate(1,[-1,0,9,10]),candidate(2,[1,0,11,10])],
                         [candidate(7,[0,0,10,10])])
        result=associate_saved_boxes(records,seed_output_index=0)
        self.assertEqual(result[1]['status'],'track_break_tie')
        self.assertEqual(result[1]['reason'],'tied_current_candidates')
        self.assertEqual(result[2]['status'],'after_track_break')
        self.assertEqual(result[2]['iou_matrix'],[[9/11],[9/11]])
        self.assertEqual(result[2]['break_frame_index'],1)
        self.assertIsNone(result[2]['selected_output_index'])

    def test_column_maximum_tie_does_not_assign_identity(self):
        records=timeline([candidate(0,[-1,0,9,10]),candidate(1,[1,0,11,10])],
                         [candidate(5,[0,0,10,10])])
        result=associate_saved_boxes(records,seed_output_index=0)
        self.assertEqual(result[1]['status'],'track_break_tie')
        self.assertEqual(result[1]['reason'],'tied_previous_candidates')
        self.assertIsNone(result[1]['match_iou'])

    def test_non_mutual_best_is_terminal(self):
        records=timeline([candidate(0,[0,0,10,10]),candidate(1,[2,0,12,10])],
                         [candidate(3,[2,0,12,10])],
                         [candidate(0,[0,0,10,10])])
        result=associate_saved_boxes(records,seed_output_index=0)
        self.assertEqual(result[1]['status'],'track_break_non_mutual')
        self.assertEqual(result[2]['status'],'after_track_break')
        self.assertIsNone(result[2]['selected_bbox_xyxy_px'])

    def test_touching_edges_and_empty_frame_break_without_reacquisition(self):
        for middle in ([candidate(1,[10,0,20,10])],[]):
            with self.subTest(middle=middle):
                result=associate_saved_boxes(timeline([candidate(0,[0,0,10,10])],middle,
                                                      [candidate(0,[0,0,10,10])]),seed_output_index=0)
                self.assertEqual([r['status'] for r in result],['seeded','track_break_no_overlap','after_track_break'])
                self.assertEqual(result[1]['break_frame_index'],1)
                self.assertIsNone(result[2]['previous_selected_output_index'])

    def test_invalid_seed_and_saved_timeline_are_rejected(self):
        valid=timeline([candidate(3,[0,0,10,10])],[candidate(2,[1,0,11,10])])
        for seed in (True,-1,0,3.0):
            with self.subTest(seed=seed),self.assertRaises(ValueError):associate_saved_boxes(valid,seed_output_index=seed)
        for mutation in ('index','time','sha','eligible','duplicate_index','duplicate_box','nan_box','zero_box'):
            changed=deepcopy(valid)
            if mutation=='index':changed[1]['frame_index']=2
            elif mutation=='time':changed[1]['timestamp_ms']=0
            elif mutation=='sha':changed[0]['decoded_bgr_sha256']='not-a-sha'
            elif mutation=='eligible':changed[0]['candidates'][0]['eligible']=1
            elif mutation=='duplicate_index':changed[0]['candidates'].append(candidate(3,[20,0,30,10]))
            elif mutation=='duplicate_box':changed[0]['candidates'].append(candidate(4,[0,0,10,10]))
            elif mutation=='nan_box':changed[0]['candidates'][0]['bbox_original_xyxy_px'][0]=float('nan')
            else:changed[0]['candidates'][0]['bbox_original_xyxy_px']=[0,0,0,10]
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):associate_saved_boxes(changed,seed_output_index=3)

    def test_complete_output_is_json_safe_and_keeps_source_timeline(self):
        records=timeline([candidate(0,[0,0,10,10])],[candidate(1,[1,0,11,10])])
        result=associate_saved_boxes(records,seed_output_index=0)
        json.dumps(result,allow_nan=False)
        self.assertEqual([r['frame_index'] for r in result],[0,1])
        self.assertEqual([r['timestamp_ms'] for r in result],[r['timestamp_ms'] for r in records])
        self.assertTrue(all(r['decoded_bgr_sha256']=='a'*64 for r in result))


if __name__=='__main__':unittest.main()
