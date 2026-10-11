from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evaluate_movenet_support import aggregate,score,verify_tracking_timeline


class SupportEvaluationTests(unittest.TestCase):
    def test_tracking_without_timestamp_uses_its_bound_capture(self):
        tracking={'frames':[{'frame_index':0,'selection_status':'selected'}]}
        capture={'selection_frames':[{'frame_index':0,'status':'selected','timestamp_ms':0}]}
        verify_tracking_timeline(tracking,[{'frame_index':0,'native_timestamp_ms':0.0}],capture,1)

    def test_source_timestamp_shift_is_rejected(self):
        tracking={'frames':[{'frame_index':0,'selection_status':'selected'}]}
        capture={'selection_frames':[{'frame_index':0,'status':'selected','timestamp_ms':0}]}
        with self.assertRaises(ValueError):
            verify_tracking_timeline(tracking,[{'frame_index':0,'native_timestamp_ms':33.3}],capture,1)

    def test_tracking_and_capture_selection_must_match(self):
        tracking={'frames':[{'frame_index':0,'selection_status':'rejected'}]}
        capture={'selection_frames':[{'frame_index':0,'status':'selected','timestamp_ms':0}]}
        with self.assertRaises(ValueError):
            verify_tracking_timeline(tracking,[{'frame_index':0,'native_timestamp_ms':0}],capture,1)

    def test_abstained_positive_is_still_false_negative(self):
        r=score([{'start_frame':2,'end_frame':3,'status':'confirmed'}],{3},{2},5)
        self.assertEqual((r['tp'],r['fn'],r['human_positive'],r['abstention_positive']),(1,1,2,1))
        self.assertEqual(r['decision_coverage'],.75)

    def test_seed_excluded_even_if_human_positive_or_predicted(self):
        r=score([{'start_frame':0,'end_frame':0}],{0},set(),3)
        self.assertEqual((r['non_seed_frames'],r['human_positive'],r['fp']),(2,0,0))
        self.assertIsNone(r['recall'])

    def test_human_unknown_is_not_a_negative(self):
        r=score([{'start_frame':1,'end_frame':1,'status':'uncertain'}],{1,2},set(),4)
        self.assertEqual((r['human_excluded'],r['human_negative'],r['fp']),(1,2,1))

    def test_union_retains_existing_false_positive(self):
        labels=[{'start_frame':2,'end_frame':2}]
        original,new={1},{2}
        r=score(labels,original|new,set(),4)
        self.assertEqual((r['tp'],r['fp'],r['fn']),(1,1,0))

    def test_abstention_cannot_also_be_warning(self):
        with self.assertRaises(ValueError):score([],{1},{1},4)

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):score([{'start_frame':1,'end_frame':2},{'start_frame':2,'end_frame':3}],set(),set(),4)

    def test_aggregate_uses_counts_not_mean_recall(self):
        a=score([{'start_frame':1,'end_frame':1}],{1},set(),3)
        b=score([{'start_frame':1,'end_frame':3}],set(),{1},5)
        r=aggregate([a,b])
        self.assertEqual((r['tp'],r['fn'],r['recall'],r['scorable_frames']),(1,3,.25,6))

    def test_exact_ranges_not_extended_to_intervals(self):
        r=score([{'start_frame':1,'end_frame':3}],{2},set(),5)
        self.assertEqual(r['ranges']['tp'],[{'start_frame':2,'end_frame':2}])
        self.assertEqual(r['fn'],2)
