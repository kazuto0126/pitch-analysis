"""Synthetic warning receipt, denominator, and additive screen regressions."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import evaluate_disagreement_warning as evaluation
finally:
    sys.path.pop(0)


def interval(start, end, status="confirmed"):
    return {"start_frame": start, "end_frame": end, "status": status}


def receipt_fixture():
    producer = {"policy": {"experimental_threshold": "sample_max"},
                "code": {"producer_code": {"sha256": "producer-sha"}}}
    run = {"status": "sealed_disagreement_warning_trial", "plan_sha256": "plan-sha",
        "producer_sha256": "producer-sha", "policy": producer["policy"], "human_annotation_inputs": [],
        "source_frames": 592, "non_seed_frames": 587, "pose_inference_calls": 0,
        "tracker_inference_calls": 0, "production_adoption": False}
    target = {"pitch_id": "synthetic", "total_frames": 5, "width": 100, "height": 80}
    source = {"path": "synthetic.json", "sha256": "source-sha", "pitch_id": "synthetic"}
    states = ("seed_excluded", "warning", "candidate_dependent", "within_reference_range", "insufficient_evidence")
    data = {**run, "status": "sealed_disagreement_warning_sidecar", "target": target,
        "source_reference": source, "frames": [{"frame_index": i, "effectiveness_eligible": i != 0,
            "evidence_state": state, "warning": state == "warning",
            "association_status": "unique_geometric_candidate", "candidate_slot_indices": [0]}
            for i, state in enumerate(states)],
        "state_counts_non_seed": {state: 1 for state in states if state != "seed_excluded"}}
    return producer, run, target, source, data


class DisagreementWarningEvaluationTests(unittest.TestCase):
    def test_query_strata_retain_ambiguous_missing_and_zero_count_states(self):
        *_, data = receipt_fixture()
        data["frames"][1].update(association_status="ambiguous", candidate_slot_indices=[0, 1])
        data["frames"][2].update(association_status="ambiguous", candidate_slot_indices=[0, 1])
        data["frames"][4].update(association_status="none", candidate_slot_indices=[])
        result = evaluation.query_state_strata(data["frames"])
        associations = result["query_state_by_association"]
        counts = result["query_state_by_candidate_count"]
        self.assertEqual(sum(sum(values.values()) for values in associations.values()), 4)
        self.assertEqual(sum(sum(values.values()) for values in counts.values()), 4)
        self.assertEqual(associations["ambiguous"]["warning"], 1)
        self.assertEqual(associations["ambiguous"]["candidate_dependent"], 1)
        self.assertEqual(associations["none"]["insufficient_evidence"], 1)
        self.assertEqual(counts["0"]["insufficient_evidence"], 1)
        self.assertEqual(counts["2"]["candidate_dependent"], 1)
        self.assertEqual(counts["6"], dict.fromkeys(evaluation.STATES[:-1], 0))
        combined = evaluation.query_state_strata(data["frames"] + data["frames"])
        self.assertEqual(sum(sum(values.values()) for values in combined["query_state_by_candidate_count"].values()), 8)

    def test_missing_positive_stays_false_negative_and_in_primary_denominator(self):
        result = evaluation.score_screens([interval(2, 3)], set(), set(), {2}, set(), {3}, 5)
        new = result["new_disagreement_screen"]
        self.assertEqual((new["tp"], new["fn"], new["human_positive"], new["scorable_frames"]), (1, 1, 2, 4))
        self.assertEqual(new["abstention_positive"], 1)
        self.assertEqual(new["decision_coverage"], .75)
        self.assertEqual(result["change_from_previous"]["remaining_false_negative_ranges"], [{"start_frame": 3, "end_frame": 3}])

    def test_candidate_dependent_is_explicit_no_warning_not_abstention(self):
        # Frame 2 is candidate-dependent; only frame 3 lacks a measurement.
        result = evaluation.score_screens([interval(2, 2)], set(), set(), set(), set(), {3}, 5)
        new = result["new_disagreement_screen"]
        self.assertEqual((new["tp"], new["fn"], new["tn"]), (0, 1, 3))
        self.assertEqual((new["abstention_positive"], new["abstention_negative"]), (0, 1))
        self.assertEqual(new["scorable_frames"], 4)

    def test_additive_trial_preserves_old_and_bbox_warnings_and_adds_new_only(self):
        result = evaluation.score_screens([interval(1, 3)], {1}, {2}, {3, 4}, set(), set(), 6)
        self.assertEqual(result["original_tracking_screen"]["tp"], 1)
        self.assertEqual(result["previous_additive_screen"]["tp"], 2)
        self.assertEqual(result["additive_trial_screen"]["tp"], 3)
        change = result["change_from_previous"]
        self.assertTrue(change["previous_warnings_preserved"])
        self.assertEqual((change["added_warning_count"], change["newly_caught_major_count"],
                          change["added_false_positive_count"], change["remaining_false_negative_count"]), (2, 1, 1, 0))
        self.assertEqual(change["added_warning_ranges"], [{"start_frame": 3, "end_frame": 4}])
        self.assertEqual(change["newly_caught_major_ranges"], [{"start_frame": 3, "end_frame": 3}])

    def test_prior_warning_is_not_withdrawn_when_new_evidence_missing(self):
        result = evaluation.score_screens([interval(1, 2)], {1}, {2}, set(), set(), {1, 2}, 4)
        trial = result["additive_trial_screen"]
        self.assertEqual((trial["tp"], trial["fn"], trial["abstention_positive"]), (2, 0, 0))
        self.assertEqual(trial["decision_coverage"], 1.)

    def test_combined_abstention_requires_both_sources_missing_and_no_old_warning(self):
        result = evaluation.score_screens([interval(1, 3)], {1}, set(), {4}, {1, 2, 3, 5}, {1, 2, 5}, 6)
        # Frame 3 is candidate-dependent, not insufficient evidence.
        trial = result["additive_trial_screen"]
        self.assertEqual((trial["abstention_positive"], trial["abstention_negative"]), (1, 1))
        self.assertEqual(trial["decision_coverage"], 3 / 5)
        self.assertEqual(result["previous_additive_screen"]["abstention_positive"], 2)

    def test_unknown_human_frames_excluded_but_added_warnings_are_reported(self):
        result = evaluation.score_screens([interval(1, 1), interval(2, 2, "uncertain"),
            interval(3, 3, "not_observable")], set(), set(), {1, 2, 3, 4}, set(), set(), 6)
        self.assertEqual(result["new_disagreement_screen"]["human_excluded"], 2)
        self.assertEqual(result["new_disagreement_screen"]["scorable_frames"], 3)
        change = result["change_from_previous"]
        self.assertEqual((change["added_warning_count"], change["added_human_excluded_count"],
                          change["added_false_positive_count"]), (4, 2, 1))

    def test_seed_zero_never_contributes_tp_fp_or_added_counts(self):
        result = evaluation.score_screens([interval(0, 0)], {0}, set(), {0, 1}, set(), set(), 3)
        self.assertEqual(result["new_disagreement_screen"]["human_positive"], 0)
        self.assertEqual(result["change_from_previous"]["added_warning_count"], 1)
        self.assertEqual(result["new_disagreement_screen"]["non_seed_frames"], 2)

    def test_receipt_contamination_policy_budget_and_denominator_rejected(self):
        producer, run, _, _, _ = receipt_fixture()
        evaluation.verify_trial_receipt(run, producer, "plan-sha")
        for key, value in (
            ("human_annotation_inputs", ["human.json"]), ("policy", {}), ("pose_inference_calls", 1),
            ("tracker_inference_calls", 1), ("pose_inference_calls", False), ("production_adoption", True),
            ("source_frames", 591), ("non_seed_frames", 592), ("plan_sha256", "wrong"),
            ("producer_sha256", "wrong"), ("status", "unsealed"),
        ):
            changed = copy.deepcopy(run)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluation.verify_trial_receipt(changed, producer, "plan-sha")

    def test_sidecar_flag_binding_and_inference_contamination_rejected(self):
        _, run, target, source, data = receipt_fixture()
        evaluation.verify_sidecar(data, target, source, run, "plan-sha")
        for key, value in (
            ("human_annotation_inputs", ["human.json"]), ("policy", {}), ("pose_inference_calls", 1),
            ("tracker_inference_calls", False), ("production_adoption", True),
            ("source_reference", {}), ("plan_sha256", "wrong"), ("producer_sha256", "wrong"),
        ):
            changed = copy.deepcopy(data)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluation.verify_sidecar(changed, target, source, run, "plan-sha")

    def test_duplicate_missing_reordered_seed_and_warning_flags_rejected(self):
        _, run, target, source, data = receipt_fixture()
        for edit in (
            lambda d: d["frames"].pop(), lambda d: d["frames"].reverse(),
            lambda d: d["frames"].append(copy.deepcopy(d["frames"][-1])),
            lambda d: d["frames"][0].update(warning=True),
            lambda d: d["frames"][1].update(warning=False),
            lambda d: d["frames"][0].update(effectiveness_eligible=True),
            lambda d: d["frames"][1].update(evidence_state="seed_excluded", warning=False),
            lambda d: d["state_counts_non_seed"].update(warning=9),
        ):
            changed = copy.deepcopy(data)
            edit(changed)
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                evaluation.verify_sidecar(changed, target, source, run, "plan-sha")

    def test_zero_state_counts_are_retained_in_sealed_summary(self):
        _, run, target, source, data = receipt_fixture()
        data["frames"][1].update(evidence_state="within_reference_range", warning=False)
        data["state_counts_non_seed"].update(warning=0, within_reference_range=2)
        evaluation.verify_sidecar(data, target, source, run, "plan-sha")

    def test_no_human_positives_has_null_recall_and_helpers_do_not_mutate_inputs(self):
        intervals, old, bbox, new = [], {1}, {2}, {3}
        before = copy.deepcopy((intervals, old, bbox, new))
        result = evaluation.score_screens(intervals, old, bbox, new, set(), set(), 5)
        self.assertIsNone(result["additive_trial_screen"]["recall"])
        self.assertEqual((intervals, old, bbox, new), before)
        self.assertEqual(result["change_from_previous"]["remaining_false_negative_count"], 0)


if __name__ == "__main__":
    unittest.main()
