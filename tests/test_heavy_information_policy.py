"""Synthetic tests only: no real calibration, GT reads, or inference."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import heavy_information_policy as policy


def training(query="pitch_003"):
    return [{"pitch_id": pitch, "rows": [
        {"frame_index": 0, "distance_diagonal": 99., "canonical_label": "reliable"},
        {"frame_index": 1, "distance_diagonal": .1, "canonical_label": "reliable"},
        {"frame_index": 2, "distance_diagonal": .2, "canonical_label": "reliable"},
        {"frame_index": 3, "distance_diagonal": 9., "canonical_label": "unreliable"},
        {"frame_index": 4, "distance_diagonal": 8., "canonical_label": "not_observable"},
        {"frame_index": 5, "distance_diagonal": 7., "canonical_label": "uncertain"},
    ]} for pitch in policy.PITCH_IDS if pitch != query]


def calibrated():
    return policy.calibrate(training(), "pitch_003", "throwing_elbow")


def passing_stats():
    tps = {"throwing_elbow": [7, 2, 4, 2, 2], "throwing_wrist": [9, 3, 4, 9, 2]}
    return {role: [{"pitch_id": pitch, "calibration_status": "calibrated",
                   "tp": tp, "fn": 5, "fp": int(i == 0), "tn": 20,
                   "gate_passed_bad_hinted": tp}
                  for i, (pitch, tp) in enumerate(zip(policy.PITCH_IDS, tps[role]))]
            for role in policy.ROLES}


class CalibrationTests(unittest.TestCase):
    def test_maximum_only_reliable_nonseed_and_immutable(self):
        clips = training(); saved = deepcopy(clips)
        result = policy.calibrate(clips, "pitch_003", "throwing_elbow")
        self.assertEqual(result["status"], "calibrated")
        self.assertEqual(result["threshold_diagonal"], .2)
        self.assertEqual(result["used_reliable_rows"], 8)
        self.assertEqual(result["excluded_rows"], {
            "seed": 4, "other_label": 12, "unmeasurable_reliable": 0})
        self.assertEqual(clips, saved)

    def test_training_ids_must_be_exact_four_other_clips(self):
        clips = training()
        for bad in (clips[:3], clips + [clips[0]], [clips[0]] * 4):
            with self.assertRaises(ValueError):
                policy.calibrate(bad, "pitch_003", "throwing_elbow")
        clips[0]["pitch_id"] = "pitch_003"
        with self.assertRaises(ValueError): policy.calibrate(clips, "pitch_003", "throwing_elbow")

    def test_invalid_role_or_query_rejected(self):
        for query, role in (("candidate_009", "throwing_elbow"), ("pitch_003", "lead_knee")):
            with self.assertRaises(ValueError): policy.calibrate(training(), query, role)

    def test_all_missing_reliable_returns_explicit_failure(self):
        clips = training()
        for clip in clips:
            for row in clip["rows"]:
                if row["frame_index"] != 0 and row["canonical_label"] == "reliable":
                    row["distance_diagonal"] = None
        result = policy.calibrate(clips, "pitch_003", "throwing_wrist")
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["threshold_diagonal"])
        self.assertEqual(result["reason"], "no_measurable_reliable_training_rows")

    def test_nonfinite_negative_bool_not_used_and_zero_is_valid(self):
        clips = training()
        invalid = (float("nan"), float("inf"), -1., True)
        for clip, value in zip(clips, invalid):
            clip["rows"][1]["distance_diagonal"] = value
            clip["rows"][2]["distance_diagonal"] = 0.
        result = policy.calibrate(clips, "pitch_003", "throwing_elbow")
        self.assertEqual(result["threshold_diagonal"], 0.)
        self.assertEqual(result["excluded_rows"]["unmeasurable_reliable"], 4)

    def test_invalid_frame_identity_and_label_rejected(self):
        for key, value in (("frame_index", 0), ("frame_index", True),
                           ("canonical_label", "inferred_correct")):
            clips = training(); clips[0]["rows"][1][key] = value
            with self.assertRaises(ValueError):
                policy.calibrate(clips, "pitch_003", "throwing_elbow")


class ApplicationTests(unittest.TestCase):
    def test_strict_greater_than_maximum_equality_not_warning(self):
        result = policy.apply([
            {"frame_index": 1, "distance_diagonal": .19},
            {"frame_index": 2, "distance_diagonal": .2},
            {"frame_index": 3, "distance_diagonal": .200001},
        ], calibrated())
        self.assertEqual([row["review_required"] for row in result], [False, False, True])
        self.assertEqual([row["status"] for row in result], ["no_warning", "no_warning", "warning"])

    def test_missing_keeps_effectiveness_without_warning(self):
        row = policy.apply([{"frame_index": 1, "distance_diagonal": None}], calibrated())[0]
        self.assertEqual(row["status"], "insufficient_evidence")
        self.assertIsNone(row["review_required"])
        self.assertFalse(row["evaluated_warning"])
        self.assertTrue(row["effectiveness_eligible"])

    def test_frame_zero_kept_but_excluded_even_large_distance(self):
        row = policy.apply([{"frame_index": 0, "distance_diagonal": 90.}], calibrated())[0]
        self.assertEqual(row["distance_diagonal"], 90.)
        self.assertEqual(row["status"], "seed_excluded")
        self.assertFalse(row["review_required"])
        self.assertFalse(row["evaluated_warning"])
        self.assertFalse(row["effectiveness_eligible"])

    def test_failed_calibration_never_falls_back(self):
        clips = training()
        for clip in clips: clip["rows"] = []
        calibration = policy.calibrate(clips, "pitch_003", "throwing_elbow")
        row = policy.apply([{"frame_index": 1, "distance_diagonal": 9.}], calibration)[0]
        self.assertEqual(row["status"], "calibration_failed")
        self.assertIsNone(row["review_required"])
        self.assertFalse(row["evaluated_warning"])

    def test_query_labels_and_context_not_read_and_inputs_immutable(self):
        class QueryRow(dict):
            def __getitem__(self, key):
                if key not in ("frame_index", "distance_diagonal"):
                    raise AssertionError("query annotation/context was accessed")
                return super().__getitem__(key)
        rows = [QueryRow(frame_index=1, distance_diagonal=.3,
                         canonical_label="reliable", context={"forbidden": True})]
        calibration = calibrated(); saved = deepcopy(calibration)
        output = policy.apply(rows, calibration)
        self.assertTrue(output[0]["review_required"])
        self.assertEqual(calibration, saved)
        self.assertEqual(dict(rows[0])["canonical_label"], "reliable")

    def test_invalid_query_or_calibration_cannot_silently_change_policy(self):
        for value in (-1., float("inf"), float("nan"), True, "0.3"):
            with self.assertRaises(ValueError):
                policy.apply([{"frame_index": 1, "distance_diagonal": value}], calibrated())
        for key, value in (("threshold_diagonal", None), ("comparison", ">="),
                           ("training_pitch_ids", ["pitch_003"] * 4)):
            bad = calibrated(); bad[key] = value
            with self.assertRaises(ValueError): policy.apply([], bad)


class DecisionTests(unittest.TestCase):
    def test_exact_tp_fp_non003_boundary_and_immutable(self):
        stats = passing_stats(); saved = deepcopy(stats)
        result = policy.decision(stats)
        self.assertEqual(result["proposed_roles"], list(policy.ROLES))
        self.assertEqual(result["roles"]["throwing_elbow"]["totals"]["tp"], 17)
        self.assertEqual(result["roles"]["throwing_wrist"]["totals"]["tp"], 27)
        self.assertFalse(result["automatically_passes_phase2"])
        self.assertFalse(result["changes_formal_pose_tracking_or_gates"])
        self.assertEqual(stats, saved)

    def test_each_frozen_check_can_block_adoption(self):
        for role, changes, check in (
            ("throwing_elbow", [(0, "tp", 6), (0, "gate_passed_bad_hinted", 6)], "minimum_tp"),
            ("throwing_wrist", [(0, "fp", 2)], "maximum_fp"),
            ("throwing_elbow", [(0, "tp", 0), (0, "gate_passed_bad_hinted", 0),
                                (2, "tp", 20)], "minimum_non003_tp"),
            ("throwing_wrist", [(0, "gate_passed_bad_hinted", 0),
                                (1, "gate_passed_bad_hinted", 0),
                                (2, "gate_passed_bad_hinted", 0),
                                (3, "gate_passed_bad_hinted", 6)],
             "gate_passed_bad_hints_strictly_improve"),
        ):
            stats = passing_stats()
            for i, key, value in changes: stats[role][i][key] = value
            result = policy.decision(stats)
            self.assertFalse(result["roles"][role]["checks"][check])
            self.assertNotIn(role, result["proposed_roles"])

    def test_two_non003_clips_must_improve_strictly_over_both_baselines(self):
        stats = passing_stats()
        for i, tp in enumerate((6, 0, 20, 0, 11)):
            stats["throwing_elbow"][i]["tp"] = tp
            stats["throwing_elbow"][i]["gate_passed_bad_hinted"] = tp
        result = policy.decision(stats)["roles"]["throwing_elbow"]
        self.assertEqual(result["improved_non003_clips"], ["pitch_005"])
        self.assertFalse(result["passed"])

    def test_failed_fold_or_incomplete_cohort_not_accepted(self):
        stats = passing_stats(); stats["throwing_elbow"][2]["calibration_status"] = "failed"
        result = policy.decision(stats)
        self.assertFalse(result["roles"]["throwing_elbow"]["checks"]["five_folds_calibrated"])
        self.assertEqual(result["proposed_roles"], ["throwing_wrist"])
        for values in (passing_stats()["throwing_elbow"][:4],
                       [passing_stats()["throwing_elbow"][0]] * 5):
            stats = passing_stats(); stats["throwing_elbow"] = values
            with self.assertRaises(ValueError): policy.decision(stats)

    def test_rejection_stops_trial_no_phase2_pass_and_invalid_counts_rejected(self):
        stats = passing_stats()
        for role in policy.ROLES:
            for row in stats[role]: row["fp"] = 2
        result = policy.decision(stats)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["proposed_roles"], [])
        self.assertEqual(result["next_action"], "stop_this_trial_need_better_images_or_model_information")
        for key, value in (("tp", -1), ("fp", True), ("tn", 2.5),
                           ("gate_passed_bad_hinted", 100), ("calibration_status", "guessed")):
            stats = passing_stats(); stats["throwing_elbow"][0][key] = value
            with self.assertRaises(ValueError): policy.decision(stats)
        with self.assertRaises(ValueError): policy.decision({"throwing_elbow": []})


if __name__ == "__main__":
    unittest.main()
