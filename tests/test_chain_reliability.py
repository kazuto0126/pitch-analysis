"""Synthetic chain geometry, supervised fold isolation, and application boundary."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import measure_chain_reliability as chain
finally:
    sys.path.pop(0)

MAPPING = dict(zip(chain.parent.ROLES, ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST", "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE")))
POINTS = dict(zip(chain.parent.ROLES, ([0., 0.], [10., 0.], [20., 0.], [0., 10.], [0., 20.], [0., 30.])))


def source(name, total=3):
    return {"target": {"pitch_id": name, "total_frames": total, "width": 200, "height": 100},
        "important_joints": MAPPING.copy(), "frames": [{"frame_index": i, "effectiveness_eligible": i != 0,
            "native_timestamp_ms": i * 10., "capture_timestamp_ms": i * 10.,
            "joints": {MAPPING[role]: {"raw": {"finite": True, "xy_px": point[:]}, "baseline_model_state": "observed"}
                       for role, point in POINTS.items()}} for i in range(total)]}


def view_for(data):
    view = {"schema_version": "reviewed-reliability-view-v1",
        "output_kind": "derived_reviewed_reliability_view_not_editable_ground_truth", "pitch_id": data["target"]["pitch_id"],
        "summary": {"total_frames": data["target"]["total_frames"]},
        "source_artifacts": {"ground_truth": {"path": f"human/{data['target']['pitch_id']}.json", "sha256": "a" * 64}}, "frames": []}
    for frame in data["frames"]:
        human = {"pitcher_correctly_selected": True, "major_pose_failure": [], "track_break": [], "identity_switch": []}
        joints = {}
        for role, landmark in data["important_joints"].items():
            original = frame["joints"][landmark]
            xy = original["raw"]["xy_px"]
            state = original["baseline_model_state"]
            joints[role] = {"landmark": landmark, "model_state": state, "human_raw_overlay_review": {"status": "reliable"},
                "raw_landmark": {"x": xy[0] / 200, "y": xy[1] / 100} if xy is not None else None,
                "use_disposition": chain.parent.review.disposition("reliable", state, human)}
        view["frames"].append({"frame_index": frame["frame_index"], "timestamp_ms": frame["native_timestamp_ms"],
                               "human_review": human, "focus_joints": joints})
    return view


def set_human(view, frame, role, status):
    row = view["frames"][frame]
    point = row["focus_joints"][role]
    point["human_raw_overlay_review"]["status"] = status
    point["use_disposition"] = chain.parent.review.disposition(status, point["model_state"], row["human_review"])


def put(data, frame, role, xy, state="observed"):
    data["frames"][frame]["joints"][MAPPING[role]] = {"raw": {"finite": xy is not None, "xy_px": xy}, "baseline_model_state": state}


class ChainReliabilityTests(unittest.TestCase):
    def test_pixel_aspect_geometry_not_normalized_image_distance(self):
        data = source("a")
        put(data, 1, "throwing_elbow", [20., 0.])
        put(data, 1, "throwing_wrist", [40., 0.])
        result = chain.chain_feature(data["frames"][1], MAPPING, "arm_chain")
        self.assertEqual(result["segment_lengths_px"], [20., 20.])
        self.assertEqual((result["numerator_px"], result["denominator_px"], result["ratio"]), (40., 10., 4.))

    def test_rigid_translation_and_uniform_scale_leave_ratio_unchanged(self):
        data = source("a")
        first = chain.chain_feature(data["frames"][1], MAPPING, "arm_chain")["ratio"]
        for joint in data["frames"][1]["joints"].values():
            joint["raw"]["xy_px"] = [value * 5 + 1000 for value in joint["raw"]["xy_px"]]
        self.assertEqual(chain.chain_feature(data["frames"][1], MAPPING, "arm_chain")["ratio"], first)

    def test_natural_shortening_has_no_lower_bound_warning(self):
        data = [source("a"), source("b")]
        put(data[0], 1, "throwing_elbow", [0., 0.])
        put(data[0], 1, "throwing_wrist", [0., 0.])
        artifact = chain.fit_reference(data, [view_for(d) for d in data])
        result = chain.apply_reference(data, artifact)[0]["frames"][1]["chains"]["arm_chain"]
        self.assertEqual(result["ratio"], 0.)
        self.assertEqual(result["evidence_state"], "within_reference_range")
        self.assertFalse(result["warning"])

    def test_strict_upper_bound_and_whole_chain_scope(self):
        data = [source("a"), source("b")]
        put(data[0], 1, "throwing_wrist", [40., 0.])
        result = chain.apply_reference(data, chain.fit_reference(data, [view_for(d) for d in data]))[0]
        self.assertTrue(result["frames"][1]["chains"]["arm_chain"]["warning"])
        self.assertEqual(result["frames"][1]["chains"]["arm_chain"]["reasons"], ["chain_relative_stretch_warning"])
        self.assertFalse(result["frames"][2]["chains"]["arm_chain"]["warning"])
        self.assertNotIn("joints", result["frames"][1])
        self.assertNotIn("major_pose_failure", result)

    def test_zero_missing_and_nonfinite_denominator_are_explicit_null(self):
        for xy in ([0., 0.], None, [float("nan"), 0.], [float("inf"), 0.]):
            data = source("a")
            put(data, 1, "lead_hip", xy, "missing" if xy is None else "observed")
            with self.subTest(xy=xy):
                feature = chain.chain_feature(data["frames"][1], MAPPING, "arm_chain")
                self.assertIsNone(feature["ratio"])
                self.assertTrue(feature["measurement_reasons"])

    def test_tiny_positive_denominator_not_clamped_and_overflow_not_fake_value(self):
        data = source("a")
        put(data, 1, "lead_hip", [0., 1e-100])
        result = chain.chain_feature(data["frames"][1], MAPPING, "arm_chain")
        self.assertEqual(result["denominator_px"], 1e-100)
        self.assertEqual(result["ratio"], 2e101)
        put(data, 1, "lead_hip", [0., 5e-324])
        result = chain.chain_feature(data["frames"][1], MAPPING, "arm_chain")
        self.assertEqual(result["denominator_px"], 5e-324)
        self.assertIsNone(result["ratio"])
        self.assertIn("nonfinite_ratio_from_unclamped_positive_denominator", result["measurement_reasons"])

    def test_missing_member_keeps_other_chain_and_original_model_states(self):
        data = [source("a"), source("b")]
        put(data[0], 1, "throwing_elbow", None, "missing")
        artifact = chain.fit_reference(data, [view_for(d) for d in data])
        result = chain.apply_reference(data, artifact)[0]["frames"][1]["chains"]
        self.assertEqual(result["arm_chain"]["evidence_state"], "insufficient_evidence")
        self.assertEqual(result["arm_chain"]["dependency_raw_states"]["throwing_elbow"], "missing")
        self.assertEqual(result["lead_leg_chain"]["ratio"], 2.)

    def test_finite_raw_geometry_retained_when_processed_interpolated_or_missing(self):
        for state in ("interpolated", "missing"):
            data = [source("a"), source("b")]
            put(data[0], 1, "throwing_wrist", [20., 0.], state)
            result = chain.apply_reference(data, chain.fit_reference(data, [view_for(d) for d in data]))[0]["frames"][1]["chains"]["arm_chain"]
            self.assertEqual(result["ratio"], 2.)
            self.assertEqual(result["dependency_raw_states"]["throwing_wrist"], state)
            self.assertFalse(result["warning"])

    def test_all_unique_dependencies_including_other_chain_anchor_must_be_trusted(self):
        data = [source("a"), source("b")]
        views = [view_for(d) for d in data]
        set_human(views[1], 1, "lead_hip", "unreliable")
        set_human(views[1], 2, "throwing_shoulder", "not_observable")
        artifact = chain.fit_reference(data, views)
        for name in chain.CHAINS:
            record = artifact["folds"][0]["calibration"][name]
            self.assertEqual((record["eligible_reference_frames"], record["excluded_reference_frames"]), (0, 2))
            self.assertEqual(len(record["dependency_roles"]), 4)
            self.assertIsNone(record["maximum_ratio"])

    def test_multiple_failed_dependencies_count_each_reference_frame_once(self):
        data = [source("a"), source("b")]
        views = [view_for(d) for d in data]
        set_human(views[1], 1, "throwing_elbow", "unreliable")
        set_human(views[1], 1, "throwing_wrist", "not_observable")
        record = chain.fit_reference(data, views)["folds"][0]["calibration"]["arm_chain"]
        self.assertEqual(record["excluded_reference_frames"], 1)
        self.assertEqual(sum(record["excluded_use_disposition_counts"].values()), 1)
        self.assertEqual(record["reference_non_seed_frames"], 2)

    def test_query_gt_changes_do_not_change_own_fold_or_own_sidecar(self):
        data = [source("a"), source("b")]
        views = [view_for(d) for d in data]
        before = chain.fit_reference(data, views)
        set_human(views[0], 1, "throwing_elbow", "unreliable")
        after = chain.fit_reference(data, views)
        self.assertEqual(before["folds"][0], after["folds"][0])
        self.assertEqual(chain.apply_reference(data, before)[0], chain.apply_reference(data, after)[0])
        self.assertNotEqual(before["folds"][1]["calibration"], after["folds"][1]["calibration"])

    def test_seed_extreme_excluded_and_tied_maximum_sources_all_retained(self):
        data = [source("a"), source("b")]
        put(data[1], 0, "throwing_wrist", [999., 0.])
        artifact = chain.fit_reference(data, [view_for(d) for d in data])
        record = artifact["folds"][0]["calibration"]["arm_chain"]
        self.assertEqual(record["maximum_ratio"], 2.)
        self.assertEqual([r["frame_index"] for r in record["maximum_sources"]], [1, 2])
        self.assertEqual(chain.apply_reference(data, artifact)[0]["frames"][0]["chains"]["arm_chain"]["evidence_state"], "seed_excluded")

    def test_trusted_but_zero_anchor_preserves_eligible_missing_denominator(self):
        data = [source("a"), source("b")]
        for index in (1, 2):
            put(data[1], index, "lead_hip", [0., 0.])
        artifact = chain.fit_reference(data, [view_for(d) for d in data])
        record = artifact["folds"][0]["calibration"]["arm_chain"]
        self.assertEqual((record["eligible_reference_frames"], record["finite_frames"], record["missing_frames"]), (2, 0, 2))
        self.assertIsNone(record["maximum_ratio"])
        self.assertEqual(chain.apply_reference(data, artifact)[0]["state_counts_non_seed"]["arm_chain"]["insufficient_evidence"], 2)

    def test_no_native_coordinates_or_scores_required_for_pure_fit_or_apply(self):
        data = [source("a"), source("b")]
        put(data[0], 1, "throwing_wrist", [40., 0.])
        views = [view_for(d) for d in data]
        artifact = chain.fit_reference(data, views)
        expected = chain.apply_reference(data, artifact)
        for clip in data:
            for frame in clip["frames"]:
                frame["native_output"] = "unreadable native data"
                frame["candidate_slot_indices"] = []
                frame["association_status"] = "none"
                for joint in frame["joints"].values():
                    joint["candidate_distances"] = []
                    joint["distance_range_diagonal"] = {"min": None, "max": None}
                    joint["native_joint_score"] = "not read by geometry"
        self.assertEqual(chain.fit_reference(data, views), artifact)
        self.assertEqual(chain.apply_reference(data, artifact), expected)
        self.assertTrue(expected[0]["frames"][1]["chains"]["arm_chain"]["warning"])

    def test_fractional_native_and_rounded_capture_are_same_frame(self):
        data = [source("a"), source("b")]
        data[1]["frames"][1].update(native_timestamp_ms=33.333333, capture_timestamp_ms=33.)
        chain.fit_reference(data, [view_for(d) for d in data])
        data[1]["frames"][1]["capture_timestamp_ms"] = 35.
        with self.assertRaises(ValueError):
            chain.fit_reference(data, [view_for(d) for d in data])

    def test_calibration_tamper_leakage_and_scope_promotion_rejected(self):
        data = [source("a"), source("b")]
        artifact = chain.fit_reference(data, [view_for(d) for d in data])
        for edit in (
            lambda a: a["folds"][0]["calibration"]["arm_chain"].update(maximum_ratio=0),
            lambda a: a["folds"][0]["calibration"]["arm_chain"]["retained_reference_rows"][0].update(pitch_id="a"),
            lambda a: a["folds"][0]["calibration"]["arm_chain"]["retained_reference_rows"][0].update(frame_index=0),
            lambda a: a["folds"][0]["calibration"]["arm_chain"].update(missing_frames=1),
            lambda a: a["folds"][0]["calibration"]["arm_chain"].update(maximum_sources=[]),
            lambda a: a.update(joint_warning_generated=True), lambda a: a.update(major_warning_generated=True),
        ):
            changed = copy.deepcopy(artifact)
            edit(changed)
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                chain.apply_reference(data, changed)

    def test_apply_pure_function_does_not_read_gt_or_fit_and_inputs_unchanged(self):
        data = [source("a"), source("b")]
        views = [view_for(d) for d in data]
        artifact = chain.fit_reference(data, views)
        expected, before = chain.apply_reference(data, artifact), copy.deepcopy((data, views, artifact))
        with patch.object(chain, "read", side_effect=AssertionError("no I/O")), \
                patch.object(chain, "fit_reference", side_effect=AssertionError("no FIT")), \
                patch.object(chain.parent, "_view_measurement", side_effect=AssertionError("no views")):
            self.assertEqual(chain.apply_reference(data, artifact), expected)
        self.assertEqual((data, views, artifact), before)

    def test_apply_wrapper_uses_numeric_parent_only_and_checks_declared_training_pool(self):
        data = [source(name, count) for name, count in zip("abcde", (87, 175, 115, 114, 101), strict=True)]
        artifact = chain.fit_reference(data, [view_for(d) for d in data])
        refs = [{"pitch_id": d["target"]["pitch_id"], "path": f"measurement/{d['target']['pitch_id']}.json", "sha256": "f" * 64} for d in data]
        views = [{"path": f"views/{d['target']['pitch_id']}.json", "sha256": "f" * 64} for d in data]
        artifact.update(plan_sha256="f" * 64, producer_sha256="f" * 64, measurement_sources=refs, reviewed_source_references=views)
        code = {role: {"path": path, "sha256": "f" * 64} for role, path in chain.CODE_PATHS.items()}
        common = {"policy": chain.POLICY, "code": code, "source_frames": 592, "non_seed_frames": 587,
            "supervised_calibration_used": True, "human_training_inputs": artifact["human_training_inputs"],
            "production_adoption": False, "joint_warning_generated": False, "major_warning_generated": False,
            "pose_inference_budget": 0, "tracker_inference_budget": 0,
            "parent_apply_plan": {"path": "parent_apply.json", "sha256": "f" * 64}}
        fit_plan = common | {"status": "frozen_before_chain_reference_fit", "parent_fit_plan": {"path": "never_read_fit_parent.json", "sha256": "f" * 64}}
        plan = common | {"status": "frozen_before_chain_reference_apply", "application_human_annotation_inputs": [],
            "fit_plan": {"path": "fit.json", "sha256": "f" * 64}, "calibration_artifact": {"path": "numeric.json", "sha256": "f" * 64}}
        previous = {"human_training_inputs": artifact["human_training_inputs"], "reviewed_source_references": views}
        files = {"fit.json": fit_plan, "numeric.json": artifact, "parent_apply.json": {"clips": [{"source": ref} for ref in refs]}}
        def safe_bound(root, ref):
            if ref["path"].startswith(("views/", "human/")):
                raise AssertionError("Application must not dereference human/view input")
            return Path(ref["path"])
        with patch.object(chain, "bound", side_effect=safe_bound), patch.object(chain, "sha", return_value="f" * 64), \
                patch.object(chain, "read", side_effect=lambda p: files[Path(p).as_posix()]), \
                patch.object(chain.parent, "verify_apply_plan", return_value=(data, previous)), \
                patch.object(chain.parent, "verify_fit_plan", side_effect=AssertionError("No parent FIT")), \
                patch.object(chain, "verify_plan", side_effect=AssertionError("No chain FIT verifier")), \
                patch.object(chain.parent, "_view_measurement", side_effect=AssertionError("No review reads")):
            measured, reference = chain.verify_apply_plan(Path("synthetic"), plan)
            self.assertEqual(chain.apply_reference(measured, reference), chain.apply_reference(data, artifact))
            changed = plan | {"human_training_inputs": []}
            with self.assertRaisesRegex(ValueError, "Declared chain cohort"):
                chain.verify_apply_plan(Path("synthetic"), changed)
            changed = plan | {"source_frames": 591}
            with self.assertRaisesRegex(ValueError, "Changed chain plan"):
                chain.verify_apply_plan(Path("synthetic"), changed)

    def test_source_code_hash_changed_rejected_before_parent_or_gt_reads(self):
        plan = {"status": "frozen_before_chain_reference_fit", "policy": chain.POLICY,
            "production_adoption": False, "joint_warning_generated": False, "major_warning_generated": False,
            "pose_inference_budget": 0, "tracker_inference_budget": 0,
            "source_frames": 592, "non_seed_frames": 587, "supervised_calibration_used": True,
            "code": {role: {"path": path, "sha256": "0" * 64} for role, path in chain.CODE_PATHS.items()}}
        with patch.object(chain.parent, "verify_fit_plan") as parent_fit:
            with self.assertRaisesRegex(ValueError, "Changed or outside bound source"):
                chain.verify_plan(ROOT, plan)
            parent_fit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
