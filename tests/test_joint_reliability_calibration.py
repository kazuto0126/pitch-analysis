"""Synthetic supervised fitting, leakage, frozen bounds, and application I/O."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import calibrate_joint_reliability as calibration
finally:
    sys.path.pop(0)

MAPPING = dict(zip(calibration.ROLES, ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST",
                                     "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE")))


def source(name, values):
    data = {"status": "sealed_joint_disagreement_only", "target": {"pitch_id": name,
        "total_frames": len(values), "width": 100, "height": 200}, "human_annotation_inputs": [],
        "production_adoption": False, "coordinate_correctness_claimed": False,
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "new_binary_warnings": 0,
        "important_joints": MAPPING.copy(), "frames": []}
    for index, value in enumerate(values):
        numbers = list(value) if isinstance(value, tuple) else [] if value is None else [value]
        slots = list(range(len(numbers)))
        finite = all(number is not None for number in numbers)
        bounds = {"min": min(numbers) if numbers and finite else None, "max": max(numbers) if numbers and finite else None}
        joints = {}
        for landmark in MAPPING.values():
            native = [{"slot_index": s, "geometric_candidate": s in slots,
                "distance_diagonal": (numbers[s] if s in slots else 0.) if finite else None} for s in range(6)]
            joints[landmark] = {"raw": {"finite": finite, "xy_px": [10., 20.] if finite else None},
                "baseline_model_state": "observed" if finite else "missing", "slot_distances": native,
                "candidate_distances": [copy.deepcopy(row) for row in native if row["geometric_candidate"]],
                "distance_range_diagonal": bounds.copy()}
        data["frames"].append({"frame_index": index, "effectiveness_eligible": index != 0,
            "native_timestamp_ms": index * 10., "capture_timestamp_ms": index * 10.,
            "candidate_slot_indices": slots, "association_status": "none" if not slots else
                "unique_geometric_candidate" if len(slots) == 1 else "ambiguous",
            "torso_rms": {"candidate_values": [{"slot_index": s, "rms_diagonal": v} for s, v in enumerate(numbers)],
                          "range_diagonal": bounds.copy()}, "joints": joints})
    return data


def view_for(data):
    name = data["target"]["pitch_id"]
    view = {"schema_version": "reviewed-reliability-view-v1",
        "output_kind": "derived_reviewed_reliability_view_not_editable_ground_truth", "pitch_id": name,
        "summary": {"total_frames": data["target"]["total_frames"]},
        "source_artifacts": {"ground_truth": {"path": f"human/{name}/ground_truth.json", "sha256": "a" * 64}}, "frames": []}
    for measured in data["frames"]:
        human = {"pitcher_correctly_selected": True, "major_pose_failure": [], "track_break": [], "identity_switch": []}
        frame = {"frame_index": measured["frame_index"], "timestamp_ms": measured["native_timestamp_ms"],
                 "human_review": human, "focus_joints": {}}
        for role, landmark in MAPPING.items():
            original = measured["joints"][landmark]
            model = original["baseline_model_state"]
            frame["focus_joints"][role] = {"landmark": landmark, "model_state": model,
                "human_raw_overlay_review": {"status": "reliable"},
                "raw_landmark": {"x": .1, "y": .1} if original["raw"]["finite"] else None,
                "use_disposition": calibration.review.disposition("reliable", model, human)}
        view["frames"].append(frame)
    return view


def set_human(view, index, role, status):
    frame, joint = view["frames"][index], view["frames"][index]["focus_joints"][role]
    joint["human_raw_overlay_review"]["status"] = status
    joint["use_disposition"] = calibration.review.disposition(status, joint["model_state"], frame["human_review"])


class JointReliabilityCalibrationTests(unittest.TestCase):
    def test_other_clip_trusted_rows_only_and_seed_never_in_reference(self):
        a, b = source("a", [99, .8, .9]), source("b", [99, .1, .7])
        av, bv = view_for(a), view_for(b)
        for role in calibration.ROLES:
            set_human(bv, 2, role, "unreliable")
        artifact = calibration.fit_reference([a, b], [av, bv])
        record = artifact["folds"][0]["calibration"]["throwing_elbow"]
        self.assertEqual(record["reference_pitch_ids"], ["b"])
        self.assertEqual(record["maximum_min_disagreement_diagonal"], .1)
        self.assertEqual(record["excluded_use_disposition_counts"], {"hold_raw_unreliable": 1})
        self.assertEqual((record["reference_non_seed_frames"], record["eligible_reference_frames"], record["finite_frames"]), (2, 1, 1))
        self.assertEqual(record["retained_reference_rows"], [{"pitch_id": "b", "frame_index": 1, "value": .1}])

    def test_changing_query_human_labels_does_not_change_own_fold(self):
        data = [source("a", [99, .8, .9]), source("b", [99, .1, .2]), source("c", [99, .3, .4])]
        views = [view_for(d) for d in data]
        before = calibration.fit_reference(data, views)
        for role in calibration.ROLES:
            set_human(views[0], 2, role, "unreliable")
        after = calibration.fit_reference(data, views)
        self.assertEqual(before["folds"][0], after["folds"][0])
        self.assertEqual(calibration.apply_reference(data, before)[0], calibration.apply_reference(data, after)[0])
        self.assertNotEqual(before["folds"][1]["calibration"], after["folds"][1]["calibration"])

    def test_supervised_provenance_pool_and_each_fold_exclusion_are_explicit(self):
        data = [source("a", [0, .2]), source("b", [0, .1]), source("c", [0, .3])]
        artifact = calibration.fit_reference(data, [view_for(d) for d in data])
        self.assertTrue(artifact["supervised_calibration_used"])
        self.assertEqual([r["pitch_id"] for r in artifact["human_training_inputs"]], ["a", "b", "c"])
        self.assertEqual([r["pitch_id"] for r in artifact["folds"][0]["human_training_inputs"]], ["b", "c"])
        self.assertFalse(artifact["pose_model_training"])
        result = calibration.apply_reference(data, artifact)
        self.assertEqual(result[0]["human_training_inputs"], artifact["folds"][0]["human_training_inputs"])

    def test_reference_with_no_candidates_preserves_eligible_missing_denominator(self):
        data = [source("a", [0, .2]), source("b", [0, None])]
        artifact = calibration.fit_reference(data, [view_for(d) for d in data])
        record = artifact["folds"][0]["calibration"]["throwing_elbow"]
        self.assertEqual((record["eligible_reference_frames"], record["finite_frames"], record["missing_frames"]), (1, 0, 1))
        self.assertIsNone(record["maximum_min_disagreement_diagonal"])
        applied = calibration.apply_reference(data, artifact)[0]
        self.assertEqual(applied["frames"][1]["joints"]["throwing_elbow"]["evidence_state"], "insufficient_evidence")

    def test_existing_confirmed_frame_hold_excluded_but_uncertain_semantics_unchanged(self):
        data = [source("a", [0, .2]), source("b", [0, .1, .7])]
        views = [view_for(d) for d in data]
        frame = views[1]["frames"][2]
        frame["human_review"]["major_pose_failure"] = [{"status": "confirmed"}]
        for role, joint in frame["focus_joints"].items():
            joint["use_disposition"] = calibration.review.disposition("reliable", joint["model_state"], frame["human_review"])
        record = calibration.fit_reference(data, views)["folds"][0]["calibration"]["throwing_elbow"]
        self.assertEqual(record["maximum_min_disagreement_diagonal"], .1)
        self.assertEqual(record["excluded_use_disposition_counts"], {"hold_frame_review": 1})
        frame["human_review"]["major_pose_failure"] = [{"status": "uncertain"}]
        for role, joint in frame["focus_joints"].items():
            joint["use_disposition"] = calibration.review.disposition("reliable", joint["model_state"], frame["human_review"])
        record = calibration.fit_reference(data, views)["folds"][0]["calibration"]["throwing_elbow"]
        self.assertEqual(record["maximum_min_disagreement_diagonal"], .7)

    def test_each_joint_has_its_own_reference_without_role_pooling(self):
        data = [source("a", [0, .2]), source("b", [0, .1])]
        views = [view_for(d) for d in data]
        set_human(views[1], 1, "throwing_elbow", "not_observable")
        result = calibration.apply_reference(data, calibration.fit_reference(data, views))[0]["frames"][1]["joints"]
        self.assertEqual(result["throwing_elbow"]["evidence_state"], "insufficient_evidence")
        self.assertTrue(result["throwing_wrist"]["warning"])

    def test_fractional_native_and_rounded_capture_timestamps_are_same_source_frame(self):
        data = [source("a", [0, .2]), source("b", [0, .1])]
        data[1]["frames"][1].update(native_timestamp_ms=33.333333, capture_timestamp_ms=33.)
        views = [view_for(d) for d in data]
        calibration.fit_reference(data, views)
        views[1]["frames"][1]["timestamp_ms"] = 35.
        with self.assertRaisesRegex(ValueError, "timestamp"):
            calibration.fit_reference(data, views)

    def test_all_compatible_candidates_preserved_and_strict_boundary_not_reliable_claim(self):
        data = [source("a", [0, (.1, .9), .2]), source("b", [0, .2])]
        artifact = calibration.fit_reference(data, [view_for(d) for d in data])
        applied = calibration.apply_reference(data, artifact)[0]
        one, equal = (applied["frames"][i]["joints"]["throwing_elbow"] for i in (1, 2))
        self.assertEqual((one["minimum_distance_diagonal"], one["maximum_distance_diagonal"]), (.1, .9))
        self.assertEqual(one["evidence_state"], "candidate_dependent")
        self.assertFalse(one["warning"])
        self.assertEqual(equal["evidence_state"], "within_reference_range")
        self.assertNotIn("reliable", equal)
        self.assertEqual(applied["frames"][1]["candidate_slot_indices"], [0, 1])

    def test_interpolated_reference_is_not_trusted_raw_and_missing_query_not_auto_warning(self):
        data = [source("a", [0, .2]), source("b", [0, .1])]
        for joint in data[1]["frames"][1]["joints"].values():
            joint["baseline_model_state"] = "interpolated"
        views = [view_for(d) for d in data]
        artifact = calibration.fit_reference(data, views)
        record = artifact["folds"][0]["calibration"]["throwing_elbow"]
        self.assertEqual(record["excluded_use_disposition_counts"], {"unverified_processed_interpolation": 1})
        for joint in data[0]["frames"][1]["joints"].values():
            joint["baseline_model_state"] = "missing"
        result = calibration.apply_reference(data, artifact)[0]["frames"][1]["joints"]["throwing_elbow"]
        self.assertEqual(result["raw_model_state"], "missing")
        self.assertFalse(result["warning"])

    def test_reference_tamper_maximum_row_value_source_and_query_leakage_rejected(self):
        data = [source("a", [0, .2]), source("b", [0, .1])]
        artifact = calibration.fit_reference(data, [view_for(d) for d in data])
        role = "throwing_elbow"
        for mutate in (
            lambda a: a["folds"][0]["calibration"][role].update(maximum_min_disagreement_diagonal=0),
            lambda a: a["folds"][0]["calibration"][role]["retained_reference_rows"][0].update(value=.9),
            lambda a: a["folds"][0]["calibration"][role]["retained_reference_rows"][0].update(pitch_id="a"),
            lambda a: a["folds"][0]["calibration"][role]["retained_reference_rows"][0].update(frame_index=0),
            lambda a: a["folds"][0]["calibration"][role].update(maximum_sources=[]),
            lambda a: a["folds"][0].update(human_training_inputs=a["human_training_inputs"]),
            lambda a: a["folds"][0]["calibration"][role].update(missing_frames=1),
            lambda a: a["folds"][0]["calibration"][role].update(association_counts={}),
            lambda a: a.update(major_warning_generated=True),
        ):
            changed = copy.deepcopy(artifact)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                calibration.apply_reference(data, changed)

    def test_views_mapping_model_state_raw_coordinate_and_disposition_tampering_rejected(self):
        data = [source("a", [0, .2]), source("b", [0, .1])]
        views = [view_for(d) for d in data]
        for mutate in (
            lambda v: v[1]["frames"][1]["focus_joints"]["throwing_elbow"].update(landmark="LEFT_ELBOW"),
            lambda v: v[1]["frames"][1]["focus_joints"]["throwing_elbow"].update(model_state="missing"),
            lambda v: v[1]["frames"][1]["focus_joints"]["throwing_elbow"]["raw_landmark"].update(x=.9),
            lambda v: v[1]["frames"][1]["focus_joints"]["throwing_elbow"]["use_disposition"].update(status="hold_raw_unreliable"),
            lambda v: v[1]["frames"].pop(),
        ):
            changed = copy.deepcopy(views)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                calibration.fit_reference(data, changed)

    def test_apply_pure_function_never_reads_gt_views_or_calls_fit(self):
        data = [source("a", [0, .2]), source("b", [0, .1])]
        artifact = calibration.fit_reference(data, [view_for(d) for d in data])
        expected = calibration.apply_reference(data, artifact)
        with patch.object(calibration, "read", side_effect=AssertionError("no files")), \
                patch.object(calibration.review, "derive_clip", side_effect=AssertionError("no reviews")), \
                patch.object(calibration, "fit_reference", side_effect=AssertionError("no refit")):
            self.assertEqual(calibration.apply_reference(data, artifact), expected)

    def test_apply_plan_verification_does_not_dereference_nonexistent_human_or_view_files(self):
        data = [source(name, [0] + [.1] * (count - 1)) for name, count in zip("abcde", (87, 175, 115, 114, 101), strict=True)]
        artifact = calibration.fit_reference(data, [view_for(d) for d in data])
        code = {role: {"path": path, "sha256": "f" * 64} for role, path in calibration.CODE_PATHS.items()}
        budget = {"production_adoption": False, "major_warning_generated": False, "pose_inference_budget": 0, "tracker_inference_budget": 0}
        sources = [{"pitch_id": d["target"]["pitch_id"], "path": f"measurements/{d['target']['pitch_id']}.json", "sha256": "f" * 64} for d in data]
        fit_clips = [{"target": d["target"], "measurement": ref,
            "reviewed_reliability": {"path": f"views/{d['target']['pitch_id']}/reviewed_reliability.json", "sha256": "f" * 64}}
            for d, ref in zip(data, sources, strict=True)]
        fit_plan = {**budget, "status": "frozen_before_supervised_joint_reference_fit", "policy": calibration.FIT_POLICY,
            "code": code, "human_training_inputs": artifact["human_training_inputs"], "clips": fit_clips,
            "parent_evidence_plan": {"path": "parent.json", "sha256": "f" * 64}}
        artifact.update(plan_sha256="f" * 64, producer_sha256="f" * 64, measurement_sources=sources,
                        reviewed_source_references=[c["reviewed_reliability"] for c in fit_clips])
        clips = [{"target": d["target"], "source": ref} for d, ref in zip(data, sources, strict=True)]
        plan = {**budget, "status": "frozen_before_supervised_joint_reference_apply", "policy": calibration.APPLY_POLICY,
            "code": code, "supervised_calibration_used": True, "application_human_annotation_inputs": [], "clips": clips,
            "fit_plan": {"path": "fit.json", "sha256": "f" * 64}, "calibration_artifact": {"path": "numeric.json", "sha256": "f" * 64}}
        files = {"fit.json": fit_plan, "numeric.json": artifact, "parent.json": {"clips": clips},
                 **{ref["path"]: d for ref, d in zip(sources, data, strict=True)}}
        accessed = []
        def safe_bound(root, ref):
            path = ref["path"]
            if path.startswith(("human/", "views/")):
                raise AssertionError("Application dereferenced training human data")
            accessed.append(path)
            return Path(path)
        with patch.object(calibration, "bound", side_effect=safe_bound), \
                patch.object(calibration, "sha", return_value="f" * 64), \
                patch.object(calibration, "read", side_effect=lambda p: files[Path(p).as_posix()]), \
                patch.object(calibration.local, "verify_plan"), \
                patch.object(calibration, "verify_fit_plan", side_effect=AssertionError("no fit verifier")), \
                patch.object(calibration.review, "derive_clip", side_effect=AssertionError("no review rebuild")):
            measurements, reference = calibration.verify_apply_plan(Path("synthetic"), plan)
            self.assertEqual(calibration.apply_reference(measurements, reference), calibration.apply_reference(data, artifact))
        self.assertFalse(any(path.startswith(("human/", "views/")) for path in accessed))

    def test_duplicate_sources_and_incomplete_training_provenance_rejected(self):
        a = source("a", [0, .2])
        with self.assertRaises(ValueError):
            calibration.fit_reference([a, a], [view_for(a), view_for(a)])
        b = source("b", [0, .1])
        views = [view_for(a), view_for(b)]
        views[1]["source_artifacts"]["ground_truth"]["sha256"] = "invalid"
        with self.assertRaises(ValueError):
            calibration.fit_reference([a, b], views)

    def test_all_values_and_sources_are_preserved_without_input_mutation(self):
        data = [source("a", [0, .2]), source("b", [0, .1])]
        views = [view_for(d) for d in data]
        before = copy.deepcopy((data, views))
        artifact = calibration.fit_reference(data, views)
        artifact_before = copy.deepcopy(artifact)
        result = calibration.apply_reference(data, artifact)
        self.assertEqual((data, views), before)
        self.assertEqual(artifact, artifact_before)
        self.assertNotIn("major_pose_failure", result[0])
        self.assertNotIn("warning", result[0]["frames"][1])
        self.assertFalse(calibration.APPLY_POLICY["production_adoption"])


if __name__ == "__main__":
    unittest.main()
