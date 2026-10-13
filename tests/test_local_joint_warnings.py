"""Synthetic local-scope, missingness and calibration-leakage regressions."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import measure_local_joint_warnings as trial
finally:
    sys.path.pop(0)

MAPPING = dict(zip(trial.ROLES, ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST", "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE")))


def source(name, values):
    data = {"status": "sealed_joint_disagreement_only", "target": {"pitch_id": name,
        "total_frames": len(values), "width": 100, "height": 200}, "human_annotation_inputs": [],
        "production_adoption": False, "coordinate_correctness_claimed": False,
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "new_binary_warnings": 0,
        "important_joints": MAPPING.copy(), "frames": []}
    for i, numbers in enumerate(values):
        numbers = list(numbers) if isinstance(numbers, tuple) else [] if numbers is None else [numbers]
        slots = list(range(len(numbers)))
        finite = [v for v in numbers if v is not None]
        bounds = {"min": min(finite) if finite else None, "max": max(finite) if finite else None}
        data["frames"].append({"frame_index": i, "effectiveness_eligible": i != 0,
            "native_timestamp_ms": i * 10., "capture_timestamp_ms": i * 10.,
            "candidate_slot_indices": slots, "association_status": "none" if not slots else
                "unique_geometric_candidate" if len(slots) == 1 else "ambiguous",
            "torso_rms": {"candidate_values": [{"slot_index": s, "rms_diagonal": v} for s, v in enumerate(numbers)],
                "range_diagonal": bounds.copy()},
            "joints": {landmark: {"raw": {"finite": bool(finite)}, "baseline_model_state": "observed",
                "slot_distances": [{"slot_index": s, "geometric_candidate": s in slots,
                    "distance_diagonal": numbers[s] if s in slots else 0. if finite else None} for s in range(6)],
                "candidate_distances": [{"slot_index": s, "geometric_candidate": True, "distance_diagonal": v} for s, v in enumerate(numbers)],
                "distance_range_diagonal": bounds.copy()} for landmark in MAPPING.values()}})
    return data


def set_joint(data, frame, role, numbers):
    joint = data["frames"][frame]["joints"][MAPPING[role]]
    finite = [v for v in numbers if v is not None]
    joint["raw"]["finite"] = bool(finite)
    slots = data["frames"][frame]["candidate_slot_indices"]
    joint["slot_distances"] = [{"slot_index": s, "geometric_candidate": s in slots,
        "distance_diagonal": numbers[s] if s in slots else 0. if finite else None} for s in range(6)]
    joint["candidate_distances"] = [{"slot_index": s, "geometric_candidate": True, "distance_diagonal": v} for s, v in enumerate(numbers)]
    joint["distance_range_diagonal"] = {"min": min(finite) if finite else None, "max": max(finite) if finite else None}


class LocalJointWarningTests(unittest.TestCase):
    def test_query_entire_clip_and_all_seeds_are_excluded(self):
        a, b = source("a", [99, .8, .9]), source("b", [99, .1, .2])
        result = trial.make_sidecars([a, b])[0]
        for role in trial.ROLES:
            self.assertEqual(result["calibration"][role]["maximum_min_disagreement_diagonal"], .2)
            self.assertEqual(result["calibration"][role]["reference_pitch_ids"], ["b"])
            self.assertEqual(result["frames"][0]["joints"][role]["evidence_state"], "seed_excluded")
            self.assertTrue(result["frames"][1]["joints"][role]["warning"])

    def test_each_joint_uses_its_own_anatomical_calibration_not_torso(self):
        a, b = source("a", [0, .2]), source("b", [0, .1])
        set_joint(b, 1, "throwing_elbow", [.3])
        result = trial.make_sidecars([a, b])[0]
        self.assertFalse(result["frames"][1]["joints"]["throwing_elbow"]["warning"])
        self.assertTrue(result["frames"][1]["joints"]["throwing_wrist"]["warning"])
        self.assertEqual(result["calibration"]["throwing_elbow"]["landmark"], "RIGHT_ELBOW")

    def test_local_warning_does_not_mark_frame_or_major_failure(self):
        result = trial.make_sidecars([source("a", [0, .2]), source("b", [0, .1])])[0]
        self.assertNotIn("warning", result["frames"][1])
        self.assertNotIn("major_pose_failure", result)
        self.assertIs(trial.POLICY["major_warning_generated"], False)

    def test_ambiguous_interval_retains_every_candidate_without_winner(self):
        result = trial.make_sidecars([source("a", [0, (.1, .9)]), source("b", [0, .2])])[0]
        joint = result["frames"][1]["joints"]["throwing_elbow"]
        self.assertEqual((joint["minimum_distance_diagonal"], joint["maximum_distance_diagonal"]), (.1, .9))
        self.assertEqual(joint["evidence_state"], "candidate_dependent")
        self.assertFalse(joint["warning"])

    def test_processed_missing_with_finite_raw_is_not_censored_or_automatic_warning(self):
        a, b = source("a", [0, .1]), source("b", [0, .2])
        a["frames"][1]["joints"]["RIGHT_ELBOW"]["baseline_model_state"] = "missing"
        joint = trial.make_sidecars([a, b])[0]["frames"][1]["joints"]["throwing_elbow"]
        self.assertEqual(joint["raw_model_state"], "missing")
        self.assertEqual(joint["minimum_distance_diagonal"], .1)
        self.assertFalse(joint["warning"])

    def test_raw_joint_missing_is_insufficient_without_erasing_other_joint(self):
        a, b = source("a", [0, .3]), source("b", [0, .2])
        set_joint(a, 1, "throwing_elbow", [None])
        result = trial.make_sidecars([a, b])[0]["frames"][1]["joints"]
        self.assertEqual(result["throwing_elbow"]["evidence_state"], "insufficient_evidence")
        self.assertTrue(result["throwing_wrist"]["warning"])

    def test_no_candidates_preserves_six_missing_rows_and_denominator(self):
        result = trial.make_sidecars([source("a", [0, None]), source("b", [0, .2])])[0]
        for role in trial.ROLES:
            self.assertEqual(result["state_counts_non_seed"][role]["insufficient_evidence"], 1)
            self.assertIsNone(result["frames"][1]["joints"][role]["minimum_distance_diagonal"])

    def test_no_joint_reference_keeps_other_reference_and_query_value(self):
        a, b = source("a", [0, .2]), source("b", [0, .1])
        set_joint(b, 1, "throwing_elbow", [None])
        result = trial.make_sidecars([a, b])[0]
        self.assertIsNone(result["calibration"]["throwing_elbow"]["maximum_min_disagreement_diagonal"])
        self.assertEqual(result["frames"][1]["joints"]["throwing_elbow"]["evidence_state"], "insufficient_evidence")
        self.assertTrue(result["frames"][1]["joints"]["throwing_wrist"]["warning"])

    def test_strict_equality_and_zero_reference(self):
        a, b = source("a", [0, 0]), source("b", [0, 0])
        result = trial.make_sidecars([a, b])[0]
        self.assertFalse(result["frames"][1]["joints"]["throwing_wrist"]["warning"])
        self.assertEqual(result["calibration"]["throwing_wrist"]["maximum_min_disagreement_diagonal"], 0)

    def test_tied_maximum_sources_and_missing_counts_are_retained(self):
        result = trial.make_sidecars([source("a", [0, .3]), source("b", [0, .2, None]), source("c", [0, .2])])[0]
        calibration = result["calibration"]["throwing_wrist"]
        self.assertEqual((calibration["reference_non_seed_frames"], calibration["finite_frames"], calibration["missing_frames"]), (3, 2, 1))
        self.assertEqual(len(calibration["maximum_sources"]), 2)

    def test_bad_calibration_values_are_not_removed_by_human_labels(self):
        a, b = source("a", [0, .8]), source("b", [0, .1, .9])
        result = trial.make_sidecars([a, b])[0]
        self.assertEqual(result["calibration"]["throwing_elbow"]["maximum_min_disagreement_diagonal"], .9)
        self.assertFalse(result["frames"][1]["joints"]["throwing_elbow"]["warning"])

    def test_different_hand_mapping_inconsistent_role_and_missing_role_rejected(self):
        for change in ("other_side", "wrong_elbow", "missing_role"):
            a, b = source("a", [0, .2]), source("b", [0, .1])
            if change == "other_side":
                b["important_joints"] = {r: n.replace("RIGHT", "TEMP").replace("LEFT", "RIGHT").replace("TEMP", "LEFT") for r, n in MAPPING.items()}
                for f in b["frames"]:
                    f["joints"] = {n.replace("RIGHT", "TEMP").replace("LEFT", "RIGHT").replace("TEMP", "LEFT"): j for n, j in f["joints"].items()}
            elif change == "wrong_elbow": b["important_joints"]["throwing_elbow"] = "LEFT_ELBOW"
            else: b["important_joints"].pop("lead_knee")
            with self.subTest(change=change), self.assertRaises(ValueError):
                trial.make_sidecars([a, b])

    def test_partial_slots_false_summary_bad_model_state_and_raw_flag_rejected(self):
        for change in ("partial", "summary", "state", "raw"):
            data = source("a", [0, (.1, .2)])
            joint = data["frames"][1]["joints"]["RIGHT_ELBOW"]
            if change == "partial": joint["candidate_distances"][0]["distance_diagonal"] = None
            elif change == "summary": joint["distance_range_diagonal"]["max"] = .3
            elif change == "state": joint["baseline_model_state"] = "visible"
            else: joint["raw"]["finite"] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                trial.verify_focus(data)

    def test_sources_not_mutated_and_duplicate_cohort_rejected(self):
        a, b = source("a", [0, .2]), source("b", [0, .1])
        before = copy.deepcopy([a, b])
        trial.make_sidecars([a, b])
        self.assertEqual([a, b], before)
        with self.assertRaises(ValueError): trial.make_sidecars([a, a])

    def test_saved_candidate_table_must_match_complete_native_slot_table(self):
        for change in ("different_distance", "omitted_slot", "false_membership", "native_raw_mismatch"):
            data = source("a", [0, (.1, .2)])
            joint = data["frames"][1]["joints"]["RIGHT_ELBOW"]
            if change == "different_distance": joint["candidate_distances"][0]["distance_diagonal"] = .15
            elif change == "omitted_slot": joint["slot_distances"].pop()
            elif change == "false_membership": joint["slot_distances"][0]["geometric_candidate"] = False
            else: joint["slot_distances"][5]["distance_diagonal"] = None
            with self.subTest(change=change), self.assertRaises(ValueError):
                trial.verify_focus(data)


if __name__ == "__main__":
    unittest.main()
