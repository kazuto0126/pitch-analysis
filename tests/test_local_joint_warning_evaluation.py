"""Synthetic local-target masks, burden, unchanged contexts, and receipts."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import evaluate_local_joint_warnings as evaluation
finally:
    sys.path.pop(0)

MAPPING = dict(zip(evaluation.ROLES, ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST",
                                    "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE")))


def interval(start, end, status):
    return {"start_frame": start, "end_frame": end, "status": status}


def fixture():
    states = ("seed_excluded", "warning", "candidate_dependent", "within_reference_range", "insufficient_evidence", "warning")
    models = ("observed", "observed", "observed", "interpolated", "missing", "observed")
    target = {"pitch_id": "synthetic", "total_frames": 6, "width": 100, "height": 80}
    data = {"target": target, "important_joints": MAPPING.copy(), "frames": []}
    for index, (state, model) in enumerate(zip(states, models, strict=True)):
        data["frames"].append({"frame_index": index, "effectiveness_eligible": index != 0,
            "association_status": "ambiguous" if index == 2 else "none" if index == 4 else "unique_geometric_candidate",
            "candidate_slot_indices": [0, 3] if index == 2 else [] if index == 4 else [0],
            "joints": {role: {"landmark": landmark, "raw_model_state": model,
                "evidence_state": state, "warning": state == "warning"} for role, landmark in MAPPING.items()}})
    data["state_counts_non_seed"] = {role: {state: sum(s == state for s in states[1:])
                                         for state in evaluation.STATES[:-1]} for role in evaluation.ROLES}
    human = {"labels": {role + "_reliability": [interval(0, 0, "reliable"), interval(1, 1, "unreliable"),
        interval(2, 2, "reliable"), interval(3, 3, "not_observable"), interval(4, 4, "unreliable"),
        interval(5, 5, "uncertain")] for role in evaluation.ROLES}}
    pose = {"pitch_id": "synthetic", "total_frames": 6, "frame_indices": list(range(6)),
        "important_joints": MAPPING.copy(), "joints": {name: {"frame_states": list(models),
            "frame_to_frame_jump": {"candidate_frames": [2], "candidate_count": 1,
                                   "observed_adjacent_pairs": 2}} for name in MAPPING.values()}}
    return data, human, pose


def receipt_fixture():
    producer = {"policy": {"scope": "local_only"}, "code": {"producer_code": {"sha256": "producer"}}}
    run = {"status": "sealed_local_joint_warning_trial", "policy": producer["policy"],
        "plan_sha256": "plan", "producer_sha256": "producer", "human_annotation_inputs": [],
        "production_adoption": False, "major_warning_generated": False,
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "source_frames": 592, "non_seed_frames": 587}
    return producer, run


class LocalJointWarningEvaluationTests(unittest.TestCase):
    def test_joint_specific_unknown_masks_exclude_only_that_joint(self):
        data, human, pose = fixture()
        other = evaluation.ROLES[3]
        human["labels"][other + "_reliability"] = [interval(0, 5, "reliable")]
        rows = evaluation.make_rows(data, human, pose)
        first = evaluation.summarize_rows(rows[evaluation.ROLES[0]])
        second = evaluation.summarize_rows(rows[other])
        self.assertEqual(first["new_local_disagreement_screen"]["scorable_frames"], 3)
        self.assertEqual(first["new_local_disagreement_screen"]["human_excluded"], 2)
        self.assertEqual(second["new_local_disagreement_screen"]["scorable_frames"], 5)
        self.assertEqual(second["non_seed_joint_rows"], 5)

    def test_missing_positive_is_false_negative_not_removed_or_auto_warning(self):
        data, human, pose = fixture()
        rows = evaluation.make_rows(data, human, pose)[evaluation.ROLES[0]]
        new = evaluation.score_rows(rows, "new")
        self.assertEqual((new["tp"], new["fn"], new["fp"], new["tn"]), (1, 1, 0, 1))
        self.assertEqual(new["human_positive"], 2)
        self.assertEqual(new["insufficient_evidence_by_human_label"]["unreliable"], 1)
        self.assertEqual(new["evidence_coverage_on_scorable"], 2 / 3)
        missing = next(row for row in rows if row["model_state"] == "missing")
        self.assertFalse(missing["warning"])

    def test_excluded_warning_burden_reported_separately_from_precision(self):
        data, human, pose = fixture()
        rows = evaluation.make_rows(data, human, pose)[evaluation.ROLES[0]]
        rows[2].update(state="warning", warning=True)
        result = evaluation.score_rows(rows, "new")
        self.assertEqual(result["warning_on_excluded"], {"uncertain": 1, "not_observable": 1})
        self.assertEqual(result["warning_total"], 3)
        self.assertEqual(result["precision"], 1.)
        self.assertEqual((result["tp"], result["fp"]), (1, 0))

    def test_old_jump_new_and_local_union_have_independent_scores(self):
        data, human, pose = fixture()
        rows = evaluation.make_rows(data, human, pose)[evaluation.ROLES[0]]
        old, new, union = (evaluation.score_rows(rows, screen) for screen in ("jump", "new", "union"))
        self.assertEqual((old["tp"], old["fp"]), (0, 1))
        self.assertEqual((new["tp"], new["fp"]), (1, 0))
        self.assertEqual((union["tp"], union["fp"]), (1, 1))
        self.assertIsNone(old["evidence_coverage_on_scorable"])
        self.assertIsNone(old["insufficient_evidence_by_human_label"])

    def test_old_jump_warning_survives_new_missing_without_major_promotion(self):
        data, human, pose = fixture()
        rows = evaluation.make_rows(data, human, pose)[evaluation.ROLES[0]]
        rows[3]["jump"] = True
        union = evaluation.score_rows(rows, "union")
        self.assertEqual((union["tp"], union["fn"]), (2, 0))
        self.assertEqual(union["insufficient_evidence_by_human_label"]["unreliable"], 0)
        self.assertNotIn("major", union)

    def test_candidate_dependent_is_no_warning_and_remains_in_denominator(self):
        data, human, pose = fixture()
        role = evaluation.ROLES[0]
        human["labels"][role + "_reliability"][2]["status"] = "unreliable"
        result = evaluation.summarize_rows(evaluation.make_rows(data, human, pose)[role])
        new = result["new_local_disagreement_screen"]
        self.assertEqual((new["human_positive"], new["fn"]), (3, 2))
        self.assertEqual(result["query_state_by_association"]["ambiguous"]["candidate_dependent"], 1)
        self.assertEqual(result["query_state_by_candidate_count"]["2"]["candidate_dependent"], 1)
        self.assertEqual(result["query_state_by_candidate_count"]["6"], dict.fromkeys(evaluation.STATES[:-1], 0))

    def test_model_human_evidence_cross_table_keeps_unknown_and_missing(self):
        data, human, pose = fixture()
        result = evaluation.summarize_rows(evaluation.make_rows(data, human, pose)[evaluation.ROLES[0]])
        table = result["model_state_by_human_label_by_evidence"]
        self.assertEqual(table["missing"]["unreliable"]["insufficient_evidence"], 1)
        self.assertEqual(table["interpolated"]["not_observable"]["within_reference_range"], 1)
        self.assertEqual(table["observed"]["uncertain"]["warning"], 1)
        self.assertEqual(sum(sum(sum(states.values()) for states in humans.values()) for humans in table.values()), 5)

    def test_zero_positive_and_zero_predicted_classes_have_null_metrics(self):
        data, human, pose = fixture()
        role = evaluation.ROLES[0]
        human["labels"][role + "_reliability"] = [interval(0, 5, "reliable")]
        rows = evaluation.make_rows(data, human, pose)[role]
        self.assertIsNone(evaluation.score_rows(rows, "new")["recall"])
        for row in rows:
            row.update(warning=False, jump=False, state="within_reference_range")
        self.assertIsNone(evaluation.score_rows(rows, "new")["precision"])
        for row in rows:
            row["label"] = "uncertain"
        result = evaluation.score_rows(rows, "new")
        self.assertEqual(result["scorable_frames"], 0)
        self.assertIsNone(result["evidence_coverage_on_scorable"])

    def test_seed_is_excluded_for_all_six_joints(self):
        data, human, pose = fixture()
        rows = evaluation.make_rows(data, human, pose)
        self.assertEqual(sum(len(value) for value in rows.values()), 6 * 5)
        self.assertTrue(all(row["frame_index"] != 0 for value in rows.values() for row in value))
        evaluation.verify_frames(data, 6)

    def test_original_model_state_and_jump_timeline_cannot_be_changed(self):
        data, human, pose = fixture()
        role, landmark = evaluation.ROLES[0], MAPPING[evaluation.ROLES[0]]
        changed = copy.deepcopy(data)
        changed["frames"][4]["joints"][role]["raw_model_state"] = "observed"
        with self.assertRaises(ValueError):
            evaluation.make_rows(changed, human, pose)
        for jumps, count in (([2, 2], 2), ([6], 1), ([True], 1), ([2], 99)):
            changed_pose = copy.deepcopy(pose)
            changed_pose["joints"][landmark]["frame_to_frame_jump"].update(candidate_frames=jumps, candidate_count=count)
            with self.subTest(jumps=jumps), self.assertRaises(ValueError):
                evaluation.make_rows(data, human, changed_pose)

    def test_receipts_reject_gt_inference_adoption_and_local_major_promotion(self):
        producer, run = receipt_fixture()
        evaluation.verify_receipt(run, producer, "plan")
        for key, value in (("human_annotation_inputs", ["human.json"]), ("policy", {}),
            ("pose_inference_calls", 1), ("tracker_inference_calls", False), ("production_adoption", True),
            ("major_warning_generated", True), ("plan_sha256", "wrong"), ("producer_sha256", "wrong"),
            ("source_frames", 591), ("non_seed_frames", 592)):
            changed = copy.deepcopy(run)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluation.verify_receipt(changed, producer, "plan")
        sidecar = {**run, "status": "sealed_local_joint_warning_sidecar"}
        evaluation.verify_receipt(sidecar, producer, "plan", sidecar=True)
        sidecar["major_warning_generated"] = True
        with self.assertRaises(ValueError):
            evaluation.verify_receipt(sidecar, producer, "plan", sidecar=True)

    def test_duplicate_missing_landmark_seed_and_state_summary_rejected(self):
        data, _, _ = fixture()
        role = evaluation.ROLES[0]
        for edit in (
            lambda d: d["frames"].pop(), lambda d: d["frames"].reverse(),
            lambda d: d["frames"].append(copy.deepcopy(d["frames"][-1])),
            lambda d: d["frames"][0].update(effectiveness_eligible=True),
            lambda d: d["frames"][1]["joints"].pop(role),
            lambda d: d["frames"][1]["joints"][role].update(landmark="LEFT_WRIST"),
            lambda d: d["frames"][1]["joints"][role].update(warning=False),
            lambda d: d["state_counts_non_seed"][role].update(warning=99),
        ):
            changed = copy.deepcopy(data)
            edit(changed)
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                evaluation.verify_frames(changed, 6)

    def test_aggregate_preserves_duplicate_frame_numbers_across_clips(self):
        data, human, pose = fixture()
        rows = evaluation.make_rows(data, human, pose)[evaluation.ROLES[0]]
        result = evaluation.summarize_rows(rows + rows)
        self.assertEqual(result["non_seed_joint_rows"], 10)
        self.assertEqual(result["new_local_disagreement_screen"]["human_positive"], 4)
        self.assertEqual(result["new_local_disagreement_screen"]["warning_on_excluded"]["uncertain"], 2)

    def test_empty_inputs_and_helpers_never_modify_sources(self):
        data, human, pose = fixture()
        before = copy.deepcopy((data, human, pose))
        rows = evaluation.make_rows(data, human, pose)
        evaluation.summarize_rows(rows[evaluation.ROLES[0]])
        self.assertEqual((data, human, pose), before)
        empty = evaluation.summarize_rows([])
        self.assertEqual(empty["non_seed_joint_rows"], 0)
        self.assertIsNone(empty["new_local_disagreement_screen"]["precision"])
        with self.assertRaises(ValueError):
            evaluation.score_rows([], "major")


if __name__ == "__main__":
    unittest.main()
