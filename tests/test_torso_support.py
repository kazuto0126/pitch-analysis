"""Torso conflict, ambiguity, abstention and immutable-source regressions."""
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
    import measure_torso_support as support
finally:
    sys.path.pop(0)


RAW = [(10., 10.), (20., 10.), (10., 20.), (20., 20.)]
FAR = [(40., 40.), (50., 40.), (40., 50.), (50., 50.)]


def frame(native=(FAR,), *, points=RAW, status="no_warning", candidates=None):
    candidates = list(range(len(native))) if candidates is None else candidates
    slots = []
    for index in range(6):
        xy = [[0., 0.] for _ in support.geometry.JOINTS]
        torso = native[index] if index < len(native) else FAR
        for name, point in zip(support.TORSO, torso, strict=True):
            xy[support.geometry.JOINTS.index(name)] = list(point)
        slots.append({"slot_index": index, "source_xy": xy})
    return {"status": status, "warning": {"warning": True, "no_warning": False,
        "insufficient_evidence": None}[status], "reason": "synthetic",
        "supporting_slot_indices": candidates, "candidate_slot_indices": candidates,
        "raw_torso_all_finite": points is not None,
        "raw_torso": {name: {"xy_px": list(point) if point else None}
            for name, point in zip(support.TORSO, points or [None] * 4, strict=True)},
        "slots": slots, "subject_alignment_verified": False, "confirmed_major_failure": None}


class TorsoSupportTests(unittest.TestCase):
    def test_disjoint_torso_warns_despite_bbox_support(self):
        result = support.refine_frame(frame())
        self.assertEqual((result["status"], result["warning"]), ("warning", True))
        self.assertEqual(result["reason"], "all_compatible_torso_hulls_disjoint")
        self.assertEqual(result["bbox_screen"]["status"], "no_warning")
        self.assertEqual(len(result["torso_support_tests"]), 6)
        self.assertFalse(result["subject_alignment_verified"])
        self.assertIsNone(result["confirmed_major_failure"])

    def test_touch_and_containment_are_overlap_not_identity_proof(self):
        for native in (RAW, [(20., 20.), (30., 20.), (20., 30.), (30., 30.)],
                [(0., 0.), (30., 0.), (0., 30.), (30., 30.)]):
            with self.subTest(native=native):
                result = support.refine_frame(frame((native,)))
                self.assertEqual(result["status"], "no_warning")
                self.assertEqual(result["overlapping_torso_slot_indices"], [0])

    def test_one_of_multiple_candidates_overlaps_no_winner(self):
        result = support.refine_frame(frame((FAR, RAW)))
        self.assertEqual(result["status"], "no_warning")
        self.assertEqual(result["candidate_slot_indices"], [0, 1])
        self.assertEqual(result["overlapping_torso_slot_indices"], [1])

    def test_incompatible_overlap_cannot_cancel_conflict(self):
        result = support.refine_frame(frame((FAR, RAW), candidates=[0]))
        self.assertEqual(result["status"], "warning")
        self.assertTrue(result["torso_support_tests"][1]["closed_hulls_overlap"])
        self.assertFalse(result["torso_support_tests"][1]["geometric_candidate"])

    def test_existing_bbox_warning_preserved_even_with_hull_overlap(self):
        result = support.refine_frame(frame((RAW,), status="warning"))
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["reason"], "preserved_existing_bbox_conflict")

    def test_degenerate_raw_and_candidate_abstain(self):
        line = [(10., 10.), (12., 12.), (14., 14.), (16., 16.)]
        for value in (frame(points=line), frame((FAR, line))):
            with self.subTest(value=value):
                result = support.refine_frame(value)
                self.assertEqual(result["status"], "insufficient_evidence")
                self.assertIsNone(result["warning"])

    def test_degenerate_competitor_cannot_remove_real_overlap(self):
        result = support.refine_frame(frame((RAW, [(40., 40.)] * 4)))
        self.assertEqual(result["status"], "no_warning")
        self.assertEqual(result["degenerate_candidate_slot_indices"], [1])

    def test_existing_missing_or_no_candidate_abstention_is_preserved(self):
        for value in (frame(points=None, status="insufficient_evidence"),
                frame(candidates=[], status="insufficient_evidence")):
            with self.subTest(value=value):
                result = support.refine_frame(value)
                self.assertEqual(result["status"], "insufficient_evidence")
                self.assertIsNone(result["warning"])
                json.dumps(result, allow_nan=False)

    def test_diagnostic_joint_residuals_have_no_gate(self):
        original = frame()
        saved = copy.deepcopy(original)
        result = support.refine_frame(original)
        self.assertEqual(original, saved)
        row = result["torso_support_tests"][0]
        self.assertAlmostEqual(row["same_named_joint_residual_px"]["LEFT_SHOULDER"], 1800. ** .5)
        self.assertAlmostEqual(row["center_residual_px"], 1800. ** .5)
        self.assertEqual(row["native_hip_minus_shoulder_y_px"], 10.)


class SourceTests(unittest.TestCase):
    def test_gt_data_role_changed_rule_and_duplicate_source_rejected(self):
        plan = {"status": "frozen_before_support_measurement", "warning_policy": copy.deepcopy(support.WARNING_POLICY),
            "human_annotation_inputs": [], "pose_inference_budget": 0, "tracker_inference_budget": 0,
            "production_adoption": False,
            "code": {key: {"path": value, "sha256": "synthetic"} for key, value in support.CODE_PATHS.items()},
            "source_frames": 2, "non_seed_frames": 1,
            "clips": [{"target": {"pitch_id": "fixture", "total_frames": 2, "width": 100, "height": 100},
                "sources": {role: {} for role in support.bbox.SOURCE_ROLES}}]}
        with patch.object(support.geometry, "verify_ref"), patch.object(support.geometry, "sha", return_value="synthetic"):
            for mutation in ("ground_truth", "duplicate", "policy", "annotation"):
                changed = copy.deepcopy(plan)
                if mutation == "ground_truth": changed["clips"][0]["sources"]["ground_truth"] = {}
                elif mutation == "duplicate": changed["clips"].append(copy.deepcopy(changed["clips"][0]))
                elif mutation == "policy": changed["warning_policy"]["padding"] = 10
                else: changed["human_annotation_inputs"] = ["forbidden"]
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    support.verify_plan(ROOT, changed)

    def test_source_mutation_during_computation_creates_no_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source.json"
            source.write_text("sealed", encoding="utf-8")
            ref = {"path": "source.json", "sha256": support.geometry.sha(source)}
            path = root / "plan.json"
            path.write_text(json.dumps({"output_directory": "analysis_results/new", "clips": [{}]}), encoding="utf-8")
            def mutate(*args):
                source.write_text("changed", encoding="utf-8")
                return {}
            with patch.object(support, "verify_plan", side_effect=lambda *a: support.geometry.verify_ref(root, ref)), \
                    patch.object(support, "measure_clip", side_effect=mutate):
                with self.assertRaisesRegex(ValueError, "Frozen source changed"):
                    support.measure(root, path)
            self.assertFalse((root / "analysis_results" / "new").exists())

    def test_existing_or_escaping_output_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "analysis_results" / "existing").mkdir(parents=True)
            for value in ("analysis_results/existing", "analysis_results", "elsewhere/new", "../escape"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    support.bbox.output_path(root, value)


if __name__ == "__main__":
    unittest.main()
