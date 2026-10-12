"""Synthetic leakage, abstention and ambiguity regressions; no real inference."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import measure_disagreement_warning as trial
finally:
    sys.path.pop(0)


def measurement(name, values):
    data = {"status": "sealed_joint_disagreement_only", "target": {"pitch_id": name,
        "total_frames": len(values), "width": 100, "height": 200}, "human_annotation_inputs": [],
        "production_adoption": False, "coordinate_correctness_claimed": False,
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "new_binary_warnings": 0, "frames": []}
    for i, numbers in enumerate(values):
        numbers = list(numbers) if isinstance(numbers, tuple) else [] if numbers is None else [numbers]
        slots = list(range(len(numbers)))
        finite = [v for v in numbers if v is not None]
        data["frames"].append({"frame_index": i, "effectiveness_eligible": i != 0,
            "native_timestamp_ms": i * 10., "capture_timestamp_ms": i * 10.,
            "candidate_slot_indices": slots, "association_status": "none" if not slots else
                "unique_geometric_candidate" if len(slots) == 1 else "ambiguous",
            "torso_rms": {"candidate_values": [{"slot_index": s, "rms_diagonal": n} for s, n in enumerate(numbers)],
                "range_diagonal": {"min": min(finite) if finite else None, "max": max(finite) if finite else None}}})
    return data


class DisagreementWarningTests(unittest.TestCase):
    def test_entire_query_clip_is_excluded_from_its_own_reference(self):
        a, b = measurement("a", [999, .7, .8]), measurement("b", [999, .1, .2])
        result = trial.make_sidecars([a, b])
        self.assertEqual(result[0]["calibration"]["maximum_min_disagreement_diagonal"], .2)
        self.assertEqual(result[1]["calibration"]["maximum_min_disagreement_diagonal"], .8)
        self.assertEqual(result[0]["calibration"]["reference_pitch_ids"], ["b"])
        self.assertEqual([f["warning"] for f in result[0]["frames"]], [False, True, True])

    def test_reference_seed_never_sets_bound(self):
        result = trial.make_sidecars([measurement("a", [.1, .3]), measurement("b", [100, .2])])[0]
        self.assertEqual(result["calibration"]["finite_frames"], 1)
        self.assertEqual(result["frames"][0]["evidence_state"], "seed_excluded")
        self.assertEqual(result["calibration"]["maximum_sources"], [{"pitch_id": "b", "frame_index": 1, "value": .2}])

    def test_ambiguous_candidates_keep_entire_interval_and_do_not_pick_winner(self):
        result = trial.make_sidecars([measurement("a", [0, (.1, .9)]), measurement("b", [0, .2])])[0]
        frame = result["frames"][1]
        self.assertEqual(frame["candidate_slot_indices"], [0, 1])
        self.assertEqual(frame["evidence_state"], "candidate_dependent")
        self.assertFalse(frame["warning"])

    def test_all_candidate_discrepancies_must_exceed_bound_for_warning(self):
        self.assertEqual(trial.classify(.3, .9, .2)[:2], ("warning", True))
        self.assertEqual(trial.classify(.1, .9, .2)[:2], ("candidate_dependent", False))

    def test_strict_boundary_equality_never_warns(self):
        self.assertEqual(trial.classify(.2, .2, .2)[:2], ("within_reference_range", False))
        self.assertEqual(trial.classify(.2, .3, .2)[:2], ("candidate_dependent", False))

    def test_zero_is_real_reference_not_missing(self):
        self.assertEqual(trial.classify(.01, .01, 0)[:2], ("warning", True))
        self.assertEqual(trial.classify(0, 0, 0)[:2], ("within_reference_range", False))

    def test_no_reference_abstains_whole_query_and_retains_its_values(self):
        result = trial.make_sidecars([measurement("only", [0, .9, None])])[0]
        self.assertIsNone(result["calibration"]["maximum_min_disagreement_diagonal"])
        self.assertEqual(result["state_counts_non_seed"]["insufficient_evidence"], 2)
        self.assertEqual(result["frames"][1]["min_disagreement_diagonal"], .9)

    def test_missing_and_no_candidate_are_not_zero_or_reliable(self):
        a = measurement("a", [0, None, (None, None)])
        result = trial.make_sidecars([a, measurement("b", [0, .2])])[0]
        self.assertTrue(all(f["evidence_state"] == "insufficient_evidence" for f in result["frames"][1:]))
        self.assertTrue(all(f["min_disagreement_diagonal"] is None for f in result["frames"][1:]))

    def test_no_gt_filtering_bad_reference_can_raise_bound(self):
        result = trial.make_sidecars([measurement("a", [0, .8]), measurement("b", [0, .1, .9])])[0]
        self.assertEqual(result["calibration"]["maximum_min_disagreement_diagonal"], .9)
        self.assertEqual(result["frames"][1]["evidence_state"], "within_reference_range")

    def test_all_tied_maximum_sources_preserved(self):
        result = trial.make_sidecars([measurement("a", [0, .4]), measurement("b", [0, .2, .2]),
            measurement("c", [0, .2, None])])[0]
        calibration = result["calibration"]
        self.assertEqual(calibration["reference_non_seed_frames"], 4)
        self.assertEqual(calibration["finite_frames"], 3)
        self.assertEqual(calibration["missing_frames"], 1)
        self.assertEqual(len(calibration["maximum_sources"]), 3)
        self.assertEqual(calibration["candidate_count_counts"], {"1": 3, "0": 1})

    def test_invalid_range_types_nonfinite_or_partial_rejected(self):
        for low, high in ((None, 1), (1, None), (True, 1), (-1, 0), (2, 1), (float("nan"), 1), (1, float("inf"))):
            with self.subTest(low=low, high=high), self.assertRaises(ValueError):
                trial.classify(low, high, .2)

    def test_duplicate_or_empty_cohort_rejected(self):
        a = measurement("a", [0, .1])
        for cohort in ([], [a, a]):
            with self.assertRaises(ValueError):
                trial.make_sidecars(cohort)

    def test_source_is_not_mutated(self):
        data = [measurement("a", [0, (.1, .8)]), measurement("b", [0, .2])]
        before = copy.deepcopy(data)
        trial.make_sidecars(data)
        self.assertEqual(data, before)

    def test_partial_torso_per_slot_or_false_summary_rejected(self):
        for numbers in ((None, .2), (.1, .2)):
            data = measurement("a", [0, numbers])
            if numbers[0] is not None:
                data["frames"][1]["torso_rms"]["range_diagonal"]["max"] = .3
            with self.assertRaises(ValueError):
                trial.verify_measurement(data)

    def test_changed_seed_timeline_association_or_candidate_rejected(self):
        for key, value in (("frame_index", True), ("effectiveness_eligible", False),
                ("association_status", "none"), ("candidate_slot_indices", [0, 0]),
                ("native_timestamp_ms", float("nan")), ("capture_timestamp_ms", 99)):
            data = measurement("a", [0, .2])
            data["frames"][1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.verify_measurement(data)

    def test_inference_human_or_adoption_contamination_rejected(self):
        for key, value in (("human_annotation_inputs", ["gt.json"]), ("production_adoption", True),
                ("coordinate_correctness_claimed", True), ("pose_inference_calls", 1),
                ("tracker_inference_calls", False), ("new_binary_warnings", 1)):
            data = measurement("a", [0, .2])
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                trial.verify_measurement(data)


if __name__ == "__main__":
    unittest.main()
