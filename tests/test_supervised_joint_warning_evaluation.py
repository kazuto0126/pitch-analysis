"""Supervised provenance and unchanged local-target comparison regressions."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import evaluate_supervised_joint_warnings as evaluation
finally:
    sys.path.pop(0)


def receipt():
    training = [{"pitch_id": "other", "ground_truth": {"path": "human.json", "sha256": "gt"}}]
    plan = {"code": {"producer_code": {"sha256": "code"}}, "policy": {"supervised": True}}
    artifact = {"path": "calibration.json", "sha256": "numeric"}
    run = {"status": "sealed_supervised_local_joint_warning_trial", "plan_sha256": "plan", "producer_sha256": "code",
        "policy": plan["policy"], "calibration_artifact": artifact, "supervised_calibration_used": True,
        "application_human_annotation_inputs": [], "human_training_inputs": training,
        "production_adoption": False, "major_warning_generated": False, "pose_inference_calls": 0,
        "tracker_inference_calls": 0, "source_frames": 592, "non_seed_frames": 587}
    return plan, artifact, training, run


class SupervisedJointWarningEvaluationTests(unittest.TestCase):
    def test_nonempty_training_provenance_and_no_query_reads_required(self):
        plan, artifact, training, run = receipt()
        evaluation.verify_receipt(run, plan, "plan", artifact, training)
        with self.assertRaises(ValueError): evaluation.verify_receipt(run, plan, "plan", artifact, [])

    def test_cannot_claim_gt_blind_or_use_query_gt_during_application(self):
        plan, artifact, training, run = receipt()
        for key, value in (("supervised_calibration_used", False), ("human_training_inputs", []),
                ("application_human_annotation_inputs", ["query_gt.json"]), ("calibration_artifact", {})):
            changed = copy.deepcopy(run); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluation.verify_receipt(changed, plan, "plan", artifact, training)

    def test_inference_adoption_major_promotion_and_policy_change_rejected(self):
        plan, artifact, training, run = receipt()
        for key, value in (("pose_inference_calls", 1), ("tracker_inference_calls", False),
                ("production_adoption", True), ("major_warning_generated", True), ("policy", {}),
                ("plan_sha256", "other"), ("producer_sha256", "other"), ("source_frames", 591), ("non_seed_frames", 592)):
            changed = copy.deepcopy(run); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluation.verify_receipt(changed, plan, "plan", artifact, training)

    def test_sidecar_requires_its_fold_training_inputs_not_global_pool(self):
        plan, artifact, training, run = receipt()
        run["status"] = "sealed_supervised_local_joint_warning_sidecar"
        evaluation.verify_receipt(run, plan, "plan", artifact, training, sidecar=True)
        with self.assertRaises(ValueError):
            evaluation.verify_receipt(run, plan, "plan", artifact, training + [{"pitch_id": "query"}], sidecar=True)

    def test_comparison_cannot_change_human_target_exclusions_or_missing_denominator(self):
        old = {"non_seed_joint_rows": 587, "human_label_counts": {"reliable": 4, "unreliable": 2, "not_observable": 1},
            "human_positive": 2, "human_negative": 4, "human_excluded": 1, "scorable_frames": 6,
            "tp": 1, "fn": 1, "fp": 0, "tn": 4, "warning_total": 1}
        for key, value in (("non_seed_joint_rows", 586), ("human_label_counts", {}), ("human_positive", 1),
                ("human_negative", 3), ("human_excluded", 0), ("scorable_frames", 5)):
            new = copy.deepcopy(old); new[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): evaluation.compare_screens(old, new)

    def test_comparison_keeps_increased_false_positives_and_original_scores(self):
        old = {"non_seed_joint_rows": 6, "human_label_counts": {"reliable": 4, "unreliable": 2},
            "human_positive": 2, "human_negative": 4, "human_excluded": 0, "scorable_frames": 6,
            "tp": 1, "fn": 1, "fp": 0, "tn": 4, "warning_total": 1}
        new = old | {"tp": 2, "fn": 0, "fp": 2, "tn": 2, "warning_total": 4}
        saved = copy.deepcopy((old, new))
        result = evaluation.compare_screens(old, new)
        self.assertEqual(result["change"], {"tp": 1, "fn": -1, "fp": 2, "tn": -2, "warning_total": 3})
        self.assertEqual((old, new), saved)
        self.assertIn("no major promotion", result["interpretation"])


if __name__ == "__main__": unittest.main()
