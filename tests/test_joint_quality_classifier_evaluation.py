"""Synthetic checks for fixed denominators, screening cost and decision scope."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("joint_quality_evaluation", Path(__file__).resolve().parents[1] /
    "scripts/evaluate_joint_quality_classifier.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def fixture():
    features, predictions, ground_truths, baselines, views = [], [], {}, {}, {}
    for number in range(1, 6):
        pid = f"pitch_{number:03d}"
        target = {"pitch_id": pid, "total_frames": 7, "width": 100, "height": 200}
        features.append({"target": target, "frames": []})
        predictions.append({"target": deepcopy(target), "fold_status": {r: "converged" for r in evaluation.ROLES}, "frames": []})
        statuses = ["reliable", "unreliable", "reliable", "not_observable", "uncertain", "unreliable", "reliable"]
        ground_truths[pid] = {"annotation_status": "reviewed", "source_video": {"pitch_id": pid, "total_frames": 7},
            "labels": {r + "_reliability": [{"start_frame": i, "end_frame": i, "status": s} for i, s in enumerate(statuses)]
                for r in evaluation.ROLES}}
        baselines[pid] = {"target": deepcopy(target), "frames": []}
        views[pid] = {"pitch_id": pid, "frames": []}
        for i in range(7):
            ff, pf, bf, vf = ({"frame_index": i, "timestamp_ms": i * 17, "roles": {}},
                {"frame_index": i, "timestamp_ms": i * 17, "roles": {}},
                {"frame_index": i, "capture_timestamp_ms": i * 17, "joints": {}},
                {"frame_index": i, "timestamp_ms": i * 17, "human_review": {"major_pose_failure": []}, "focus_joints": {}})
            for r in evaluation.ROLES:
                landmark = "RIGHT_ELBOW" if r == "throwing_elbow" else "RIGHT_WRIST"
                finite, gate = i != 5, i not in (2, 5)
                model_state = "observed" if gate else "missing"
                ff["roles"][r] = {"landmark": landmark, "raw_finite": finite, "raw_gate_pass": gate,
                    "raw_xy_px": [10, 20] if finite else None, "model_state": model_state,
                    "features": [0.7] * 13, "missing_reasons": {}}
                warning = i in (1, 3, 4)
                pf["roles"][r] = {"state": "seed_excluded" if i == 0 else (
                    "insufficient_evidence" if not finite else "warning" if warning else "no_warning"),
                    "warning": warning, "probability": None if i in (0, 5) else 0.8 if warning else 0.2}
                bf["joints"][r] = {"warning": i == 1, "evidence_state": "seed_excluded" if i == 0 else "warning" if i == 1 else "no_warning"}
                vf["focus_joints"][r] = {"landmark": landmark, "model_state": model_state,
                    "processed_landmark": {"usable": gate},
                    "use_disposition": {"status": "reviewed_raw_observation" if gate else "unavailable_missing", "restrictions": []}}
            features[-1]["frames"].append(ff)
            predictions[-1]["frames"].append(pf)
            baselines[pid]["frames"].append(bf)
            views[pid]["frames"].append(vf)
    return features, predictions, ground_truths, baselines, views


def counts(tp=0, fp=1):
    return {"tp": tp, "fp": fp}


def decision_input():
    reports = [{"pitch_id": f"pitch_{i:03d}", "roles": {r: {"screens": {
        "classifier": counts(6 if r == "throwing_wrist" else 4),
        "score_only": counts(1), "sample_maximum": counts(1)}} for r in evaluation.ROLES}} for i in range(1, 6)]
    aggregate = {r: {"screens": {"classifier": counts(30 if r == "throwing_wrist" else 20),
        "score_only": counts(19 if r == "throwing_wrist" else 9, 100), "sample_maximum": counts(8)}} for r in evaluation.ROLES}
    folds = {f"pitch_{i:03d}": {r: "converged" for r in evaluation.ROLES} for i in range(1, 6)}
    return reports, aggregate, folds


class JointQualityEvaluationTests(unittest.TestCase):
    def test_complete_unknown_and_missing_denominators(self):
        result = evaluation.evaluate_clips(*fixture())
        self.assertEqual((result["source_frames"], result["source_joint_rows"], result["non_seed_joint_rows"]), (35, 70, 60))
        report = result["aggregate"]["throwing_elbow"]
        self.assertEqual(report["canonical_label_counts"], {"reliable": 10, "unreliable": 10, "not_observable": 5, "uncertain": 5})
        self.assertEqual(report["raw_missing_frames"], 5)
        self.assertEqual({k: report["screens"]["classifier"][k] for k in ("tp", "fn", "fp", "tn")},
            {"tp": 5, "fn": 5, "fp": 0, "tn": 10})
        self.assertEqual(report["screens"]["classifier"]["unknown_label_warning_counts"], {"not_observable": 5, "uncertain": 5})

    def test_raw_missing_still_counts_fn_and_abstention(self):
        result = evaluation.evaluate_clips(*fixture())
        for role in evaluation.ROLES:
            for screen in evaluation.SCREENS:
                self.assertEqual(result["aggregate"][role]["screens"][screen]["fn"],
                    10 if screen == "score_only" else 5)
            self.assertEqual(result["aggregate"][role]["screens"]["classifier"]["abstain_frames"], 5)

    def test_finite_query_cannot_abstain_to_improve_false_positive_count(self):
        values = fixture()
        values[1][0]["frames"][2]["roles"]["throwing_elbow"] = {
            "state": "insufficient_evidence", "warning": False, "probability": None}
        with self.assertRaisesRegex(ValueError, "without abstention"):
            evaluation.evaluate_clips(*values)

    def test_fixed_half_probability_threshold(self):
        values = fixture()
        values[1][0]["frames"][2]["roles"]["throwing_elbow"] = {
            "state": "warning", "warning": True, "probability": 0.5}
        result = evaluation.evaluate_clips(*values)
        self.assertEqual(result["aggregate"]["throwing_elbow"]["screens"]["classifier"]["fp"], 1)
        values[1][0]["frames"][2]["roles"]["throwing_elbow"]["probability"] = 0.499
        with self.assertRaises(ValueError):
            evaluation.evaluate_clips(*values)

    def test_sample_maximum_uses_its_own_saved_warning_not_label(self):
        values = fixture()
        values[3]["pitch_001"]["frames"][3]["joints"]["throwing_elbow"]["warning"] = True
        result = evaluation.evaluate_clips(*values)
        self.assertEqual(result["aggregate"]["throwing_elbow"]["screens"]["sample_maximum"]["unknown_label_warning_counts"]["not_observable"], 1)
        self.assertEqual(result["aggregate"]["throwing_elbow"]["screens"]["sample_maximum"]["tp"], 5)

    def test_gate_increment_and_existing_good_point_loss_are_separate(self):
        result = evaluation.evaluate_clips(*fixture())
        classifier = result["aggregate"]["throwing_elbow"]["screens"]["classifier"]["retention_on_original_raw_gate_pass"]
        self.assertEqual(classifier["original_support"], 20)
        self.assertEqual(classifier["remaining_without_this_hint"], 5)
        self.assertEqual(classifier["newly_caught_gate_pass_wrong_points"], 5)
        self.assertEqual(classifier["newly_flagged_gate_pass_good_points"], 0)
        self.assertEqual(classifier["reliable_remaining"], 5)
        self.assertEqual(classifier["duplicate_hint_on_gate_blocked_finite_raw"], 0)
        score = result["aggregate"]["throwing_elbow"]["screens"]["score_only"]["retention_on_original_raw_gate_pass"]
        self.assertEqual(score["duplicate_hint_on_gate_blocked_finite_raw"], 5)
        self.assertEqual(score["newly_caught_gate_pass_wrong_points"], 0)

    def test_major_and_use_restrictions_survive_no_hint(self):
        values = fixture()
        frame = values[4]["pitch_003"]["frames"][6]
        frame["human_review"]["major_pose_failure"] = [{"status": "confirmed", "reason": "saved major hold"}]
        frame["focus_joints"]["throwing_elbow"]["use_disposition"] = {
            "status": "hold_frame_review", "restrictions": ["human_confirmed_major_pose_failure"]}
        result = evaluation.evaluate_clips(*values)
        role = result["clips"][2]["roles"]["throwing_elbow"]
        self.assertEqual(role["existing_major_hold_frames"], 1)
        self.assertEqual(role["screens"]["classifier"]["original_gate_plus_hint_union_estimate"]["original_reviewed_support_without_hint"], 0)
        row = next(r for r in result["frame_joint_rows"] if r["pitch_id"] == "pitch_003" and r["role"] == "throwing_elbow" and r["frame_index"] == 6)
        self.assertEqual(row["original_context"]["use_disposition"], frame["focus_joints"]["throwing_elbow"]["use_disposition"])

    def test_immutable_inputs(self):
        values = fixture()
        before = deepcopy(values)
        result = evaluation.evaluate_clips(*values)
        self.assertEqual(values, before)
        result["frame_joint_rows"][0]["original_context"]["use_disposition"]["restrictions"].append("new")
        self.assertEqual(values, before)

    def test_missing_features_are_reported_without_dropping_rows(self):
        values = fixture()
        values[0][0]["frames"][1]["roles"]["throwing_elbow"]["features"][4] = None
        result = evaluation.evaluate_clips(*values)
        role = result["aggregate"]["throwing_elbow"]
        self.assertEqual((role["feature_missing_frames"], role["feature_missing_value_count"]), (1, 1))
        self.assertEqual(role["non_seed_frames"], 30)

    def test_canonical_overlap_rejected(self):
        values = fixture()
        values[2]["pitch_001"]["labels"]["throwing_elbow_reliability"].append({"start_frame": 2, "end_frame": 2, "status": "unreliable"})
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            evaluation.evaluate_clips(*values)

    def test_canonical_gap_rejected(self):
        values = fixture()
        values[2]["pitch_001"]["labels"]["throwing_elbow_reliability"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete canonical"):
            evaluation.evaluate_clips(*values)

    def test_misaligned_prediction_timeline_rejected(self):
        values = fixture()
        values[1][0]["frames"][3]["timestamp_ms"] += 1
        with self.assertRaisesRegex(ValueError, "timeline"):
            evaluation.evaluate_clips(*values)

    def test_seed_has_context_but_no_effectiveness_count(self):
        result = evaluation.evaluate_clips(*fixture())
        seeds = [r for r in result["frame_joint_rows"] if r["frame_index"] == 0]
        self.assertEqual(len(seeds), 10)
        self.assertTrue(all(not r["effectiveness_eligible"] for r in seeds))
        self.assertEqual(result["clips"][0]["roles"]["throwing_elbow"]["non_seed_frames"], 6)

    def test_joint_decisions_are_independent_and_never_auto_adopt(self):
        reports, aggregate, folds = decision_input()
        aggregate["throwing_wrist"]["screens"]["classifier"]["fp"] = 2
        decision = evaluation._decision(reports, aggregate, folds)
        self.assertEqual(decision["proposed_roles"], ["throwing_elbow"])
        self.assertFalse(decision["automatic_adoption"])

    def test_false_positive_cap_applies_even_with_large_tp_gain(self):
        reports, aggregate, folds = decision_input()
        for role in evaluation.ROLES:
            aggregate[role]["screens"]["classifier"] = counts(100, 2)
        self.assertEqual(evaluation._decision(reports, aggregate, folds)["proposed_roles"], [])

    def test_improvement_only_from_003_cannot_pass(self):
        reports, aggregate, folds = decision_input()
        for report in reports:
            if report["pitch_id"] != "pitch_003":
                for role in evaluation.ROLES:
                    report["roles"][role]["screens"]["classifier"]["tp"] = 0
        result = evaluation._decision(reports, aggregate, folds)
        self.assertEqual(result["proposed_roles"], [])

    def test_one_non003_clip_large_gain_cannot_replace_two_clip_improvement(self):
        reports, aggregate, folds = decision_input()
        for report in reports:
            if report["pitch_id"] != "pitch_003":
                for role in evaluation.ROLES:
                    report["roles"][role]["screens"]["classifier"]["tp"] = 30 if report["pitch_id"] == "pitch_001" else 1
        decision = evaluation._decision(reports, aggregate, folds)
        self.assertEqual(decision["proposed_roles"], [])

    def test_failed_fold_prevents_only_that_joint_proposal(self):
        reports, aggregate, folds = decision_input()
        folds["pitch_004"]["throwing_elbow"] = "failed"
        self.assertEqual(evaluation._decision(reports, aggregate, folds)["proposed_roles"], ["throwing_wrist"])

    def test_failed_fold_records_finite_query_fn_and_never_reclassifies_missing(self):
        values = fixture()
        values[1][0]["fold_status"]["throwing_elbow"] = {"status": "failed"}
        for frame in values[1][0]["frames"][1:]:
            if frame["frame_index"] != 5:
                frame["roles"]["throwing_elbow"] = {"state": "fold_failed", "warning": False, "probability": None}
        result = evaluation.evaluate_clips(*values)
        report = result["clips"][0]["roles"]["throwing_elbow"]["screens"]["classifier"]
        self.assertEqual((report["fn"], report["fold_failed_frames"], report["abstain_frames"]), (2, 5, 6))
        self.assertFalse(result["decision"]["roles"]["throwing_elbow"]["meets_proposal_rule"])

    def test_visible_xy_remains_auxiliary_and_outside_raw_is_not_filtered(self):
        values = fixture()
        values[0][2]["frames"][1]["roles"]["throwing_elbow"]["raw_xy_px"] = [110, 20]
        manual = {"source_video": {"pitch_id": "pitch_003", "total_frames": 7}, "coordinate_system": "original_image_pixels_xy", "frames": []}
        for i in range(7):
            manual["frames"].append({"frame_index": i, "joints": [
                {"name": "RIGHT_ELBOW", "status": "visible", "x_px": 10, "y_px": 20},
                {"name": "RIGHT_WRIST", "status": "not_observable", "x_px": None, "y_px": None}]})
        without = evaluation.evaluate_clips(*values)
        result = evaluation.evaluate_clips(*values, manual)
        self.assertEqual(result["decision"], without["decision"])
        self.assertEqual(result["aggregate"], without["aggregate"])
        precise = result["clips"][2]["precise_accuracy"]["roles"]
        self.assertEqual(precise["throwing_elbow"]["all_finite_raw_visible_pairs"]["n"], 5)
        self.assertEqual(precise["throwing_elbow"]["all_finite_raw_visible_pairs"]["maximum_px"], 100)
        self.assertEqual(precise["throwing_elbow"]["visible_reference_raw_missing"], 1)
        self.assertEqual(precise["throwing_wrist"]["all_finite_raw_visible_pairs"]["n"], 0)
        self.assertTrue(all(c["precise_accuracy"] is None for c in result["clips"] if c["pitch_id"] != "pitch_003"))


if __name__ == "__main__":
    unittest.main()
