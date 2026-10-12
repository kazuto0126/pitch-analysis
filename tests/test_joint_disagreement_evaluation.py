"""Synthetic denominator and semantics tests; no real video, GT, or inference."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import evaluate_joint_disagreement as evaluation
finally:
    sys.path.pop(0)


MAPPING = dict(zip(evaluation.ROLES, (
    "RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST", "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE")))


def interval(start, end, status="reliable"):
    return {"start_frame": start, "end_frame": end, "status": status}


def fixture(total=4):
    data = {"target": {"pitch_id": "synthetic", "total_frames": total, "width": 100, "height": 100},
        "important_joints": MAPPING.copy(), "frames": []}
    canonical = {"labels": {role + "_reliability": [interval(0, total - 1)] for role in evaluation.ROLES}}
    canonical["labels"]["major_pose_failure_intervals"] = []
    for index in range(total):
        data["frames"].append({"frame_index": index, "effectiveness_eligible": index != 0,
            "native_timestamp_ms": index * 10., "capture_timestamp_ms": index * 10.,
            "association_status": "unique_geometric_candidate", "candidate_slot_indices": [0],
            "joints": {name: {"raw": {"finite": True, "xy_px": [0., 0.]},
                "baseline_model_state": "observed", "distance_range_diagonal": {"min": .1, "max": .1},
                "distance_range_px": {"min": 10., "max": 10.},
                "candidate_distances": [{"slot_index": 0, "distance_px": 10.}]}
                for name in evaluation.JOINT_NAMES},
            "torso_rms": {"range_diagonal": {"min": .2, "max": .2}, "range_px": {"min": 20., "max": 20.}}})
    return data, canonical


class JointDisagreementEvaluationTests(unittest.TestCase):
    def test_receipt_policy_inference_and_gt_boundaries_fail_closed(self):
        policy = {"new_warning_threshold": None, "new_binary_warning": False}
        producer = {"policy": policy, "human_annotation_inputs": [], "production_adoption": False,
                    "pose_inference_budget": 0, "tracker_inference_budget": 0}
        run = {"policy": copy.deepcopy(policy), "human_annotation_inputs": [], "production_adoption": False,
               "pose_inference_calls": 0, "tracker_inference_calls": 0, "new_binary_warnings": 0}
        data = copy.deepcopy(run)
        evaluation.verify_receipt_boundaries(producer, run, data)
        for which, key, value in (
            (0, "human_annotation_inputs", ["human.json"]), (0, "pose_inference_budget", 1),
            (0, "tracker_inference_budget", 1), (0, "production_adoption", True),
            (1, "policy", {}), (1, "new_binary_warnings", 1), (1, "pose_inference_calls", 1),
            (1, "tracker_inference_calls", 1), (1, "production_adoption", True),
            (1, "human_annotation_inputs", ["human.json"]), (2, "policy", {}),
            (2, "pose_inference_calls", 1), (2, "tracker_inference_calls", 1),
            (2, "production_adoption", True), (2, "new_binary_warnings", 1),
            (2, "human_annotation_inputs", ["human.json"]), (1, "new_binary_warnings", False),
        ):
            documents = copy.deepcopy((producer, run, data))
            documents[which][key] = value
            with self.subTest(document=which, key=key), self.assertRaises(ValueError):
                evaluation.verify_receipt_boundaries(*documents)

    def test_complete_inclusive_joint_intervals_preserve_unknown_human_states(self):
        self.assertEqual(evaluation.expand_labels([
            interval(0, 1), interval(2, 2, "unreliable"), interval(3, 3, "uncertain"),
            interval(4, 4, "not_observable")], 5),
            ["reliable", "reliable", "unreliable", "uncertain", "not_observable"])

    def test_overlapping_gap_unknown_and_out_of_bounds_intervals_rejected(self):
        cases = ([interval(0, 1), interval(1, 2)], [interval(0, 0), interval(2, 2)],
                 [interval(0, 2, "bad")], [interval(0, 3)], [], [interval(True, 2)])
        for intervals in cases:
            with self.subTest(intervals=intervals), self.assertRaises(ValueError):
                evaluation.expand_labels(intervals, 3)

    def test_major_sparse_intervals_default_to_reliable_without_filling_exclusions(self):
        self.assertEqual(evaluation.expand_labels([
            {"start_frame": 1, "end_frame": 2}, interval(4, 4, "uncertain"),
            interval(5, 5, "not_observable")], 7, major=True),
            ["reliable", "unreliable", "unreliable", "reliable", "uncertain", "not_observable", "reliable"])

    def test_seed_excluded_but_missing_human_positive_remains_in_joint_denominator(self):
        data, human = fixture()
        role, name = evaluation.ROLES[1], MAPPING[evaluation.ROLES[1]]
        human["labels"][role + "_reliability"] = [interval(0, 1), interval(2, 3, "unreliable")]
        data["frames"][0]["joints"][name]["distance_range_diagonal"] = {"min": 999, "max": 999}
        data["frames"][2]["joints"][name]["distance_range_diagonal"] = {"min": None, "max": None}
        data["frames"][2]["joints"][name]["baseline_model_state"] = "missing"
        result = evaluation.summarize_rows(evaluation.joint_rows(data, human)[role])
        self.assertEqual(result["min"]["scorable_counts"], {"reliable": 1, "unreliable": 2, "total": 3})
        self.assertEqual(result["min"]["unavailable_counts"]["unreliable"], 1)
        self.assertEqual(result["min"]["descriptive"]["reliable"]["max"], .1)
        self.assertEqual(result["model_state_by_human_label"]["unreliable"]["missing"], 1)

    def test_association_candidate_counts_and_all_human_state_cross_table(self):
        data, human = fixture()
        role, name = evaluation.ROLES[0], MAPPING[evaluation.ROLES[0]]
        data["frames"][2].update(association_status="ambiguous", candidate_slot_indices=[0, 4])
        data["frames"][3].update(association_status="none", candidate_slot_indices=[])
        human["labels"][role + "_reliability"] = [interval(0, 1), interval(2, 2, "uncertain"), interval(3, 3, "not_observable")]
        data["frames"][2]["joints"][name]["baseline_model_state"] = "interpolated"
        result = evaluation.summarize_rows(evaluation.joint_rows(data, human)[role])
        self.assertEqual(result["min"]["human_excluded_count"], 2)
        self.assertEqual(result["by_association"]["ambiguous"]["min"]["label_counts"]["uncertain"], 1)
        self.assertEqual(result["by_candidate_count"]["0"]["max"]["label_counts"]["not_observable"], 1)
        self.assertEqual(result["model_state_by_human_label"]["uncertain"]["interpolated"], 1)

    def test_major_ranking_uses_same_slot_torso_range_and_keeps_missing_failure(self):
        data, human = fixture()
        human["labels"]["major_pose_failure_intervals"] = [interval(2, 3, "confirmed")]
        data["frames"][2]["torso_rms"]["range_diagonal"] = {"min": .9, "max": 1.2}
        data["frames"][3]["torso_rms"]["range_diagonal"] = {"min": None, "max": None}
        result = evaluation.summarize_rows(evaluation.major_rows(data, human))
        self.assertEqual(result["min"]["conditional_auroc"], 1.)
        self.assertEqual(result["max"]["descriptive"]["unreliable"]["max"], 1.2)
        self.assertEqual(result["min"]["unavailable_counts"]["unreliable"], 1)
        self.assertNotIn("model_state_by_human_label", result)

    def test_duplicate_missing_reordered_seed_and_joint_denominators_rejected(self):
        original, _ = fixture()
        mutators = (
            lambda d: d["frames"].append(copy.deepcopy(d["frames"][-1])),
            lambda d: d["frames"].pop(),
            lambda d: d["frames"].reverse(),
            lambda d: d["frames"][0].update(effectiveness_eligible=True),
            lambda d: d["frames"][0]["joints"].pop("LEFT_ELBOW"),
            lambda d: d["important_joints"].pop("lead_hip"),
        )
        for mutate in mutators:
            data = copy.deepcopy(original)
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                evaluation.verify_frames(data, 4)
        evaluation.verify_frames(original, 4)

    def test_invalid_range_association_and_candidate_reordering_rejected(self):
        original, _ = fixture()
        for edit in (
            lambda f: f.update(association_status="ambiguous"),
            lambda f: f.update(candidate_slot_indices=[0, 0]),
            lambda f: f["joints"]["LEFT_WRIST"]["distance_range_diagonal"].update(min=-1),
            lambda f: f["joints"]["LEFT_WRIST"]["distance_range_diagonal"].update(max=None),
            lambda f: f["torso_rms"]["range_diagonal"].update(min=float("nan")),
            lambda f: f["joints"]["LEFT_WRIST"]["candidate_distances"][0].update(slot_index=2),
            lambda f: f["joints"]["LEFT_WRIST"].update(baseline_model_state="unknown"),
        ):
            data = copy.deepcopy(original)
            edit(data["frames"][1])
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                evaluation.verify_frames(data, 4)

    def test_visible_xy_only_and_missing_raw_is_not_scored_as_zero(self):
        data, _ = fixture()
        manual = {"frames": [{"frame_index": index, "timestamp_ms": index * 10., "joints": [
            {"name": "LEFT_ELBOW", "status": "visible", "x_px": 3., "y_px": 4.},
            {"name": "LEFT_WRIST", "status": "not_observable", "x_px": None, "y_px": None},
            {"name": "RIGHT_ELBOW", "status": "uncertain", "x_px": None, "y_px": None}]}
            for index in range(4)]}
        data["frames"][2]["joints"]["LEFT_ELBOW"]["raw"] = {"finite": False, "xy_px": None}
        data["frames"][3]["joints"]["LEFT_ELBOW"]["distance_range_px"] = {"min": None, "max": None}
        rows = evaluation.manual_rows(data, manual)
        result = evaluation.summarize_manual(rows)
        self.assertEqual(len(rows), 9)
        self.assertEqual(result["visible_denominator"], 3)
        self.assertEqual(result["raw_available"], 2)
        self.assertEqual(result["raw_unavailable"], 1)
        self.assertEqual(result["min"]["paired_count"], 1)
        self.assertEqual(result["min"]["measurement_unavailable"], 1)
        self.assertIsNone(result["min"]["conditional_spearman"])
        self.assertEqual(rows[0]["raw_error_px"], 5.)

    def test_manual_xy_correlation_and_full_visible_denominator(self):
        rows = [{"joint": "RIGHT_WRIST", "human_status": "visible", "raw_error_px": x,
                 "min": x, "max": 10 - x} for x in (0, 1, 2)]
        result = evaluation.summarize_manual(rows)
        self.assertEqual(result["min"]["conditional_spearman"], 1.)
        self.assertEqual(result["max"]["conditional_spearman"], -1.)
        self.assertEqual(result["max"]["unpaired_visible_count"], 0)
        self.assertEqual(result["visible_denominator"], 3)

    def test_manual_timeline_mismatch_and_timestamp_offset_rejected(self):
        data, _ = fixture()
        manual = {"frames": [{"frame_index": index, "timestamp_ms": index * 10., "joints": []}
                             for index in range(4)]}
        manual["frames"][1]["timestamp_ms"] = 20.
        with self.assertRaises(ValueError):
            evaluation.manual_rows(data, manual)
        manual["frames"][1]["timestamp_ms"] = 10.
        manual["frames"][2]["frame_index"] = 1
        with self.assertRaises(ValueError):
            evaluation.manual_rows(data, manual)

    def test_empty_statistics_and_helpers_do_not_modify_predictions_or_human_labels(self):
        data, human = fixture()
        before = copy.deepcopy((data, human))
        evaluation.summarize_rows(evaluation.joint_rows(data, human)[evaluation.ROLES[0]])
        evaluation.summarize_rows(evaluation.major_rows(data, human))
        self.assertEqual((data, human), before)
        self.assertIsNone(evaluation.summarize_manual([])["min"]["conditional_spearman"])
        self.assertIsNone(evaluation.summarize_rows([])["min"]["conditional_auroc"])

    def test_changed_producer_plan_hash_rejected_before_any_human_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "analysis_results").mkdir()
            producer = root / "producer.json"
            producer.write_text("{}", encoding="utf-8")
            plan, run = root / "plan.json", root / "run.json"
            plan.write_text(json.dumps({"producer_plan": {"path": "producer.json", "sha256": "0" * 64}}), encoding="utf-8")
            run.write_text("{}", encoding="utf-8")
            with patch.object(evaluation, "validate_ground_truth") as validate:
                with self.assertRaisesRegex(ValueError, "Changed or outside bound source"):
                    evaluation.evaluate(root, plan, run, root / "analysis_results" / "new")
                validate.assert_not_called()
            self.assertFalse((root / "analysis_results" / "new").exists())

    def test_existing_evaluation_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "analysis_results" / "existing"
            output.mkdir(parents=True)
            sentinel = output / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Exclusive"):
                evaluation.evaluate(root, root / "absent_plan", root / "absent_run", output)
            self.assertEqual(sentinel.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
