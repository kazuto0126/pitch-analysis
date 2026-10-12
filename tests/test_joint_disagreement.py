"""Sealed joint-distance semantics and producer boundary regressions."""
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
    import measure_joint_disagreement as producer
finally:
    sys.path.pop(0)

TARGET = {"pitch_id": "fixture", "width": 100, "height": 100, "total_frames": 2}


def fixture(candidates=(0,), offsets=(0., 10., 20., 30., 40., 50.)):
    raw = {name: {"x": .2, "y": .2, "z": 0., "visibility": 0., "presence": 0.} for name in producer.JOINTS}
    slots = [{"slot_index": index,
        "source_xy": [[20. + offset, 20.] for _ in producer.geometry.JOINTS],
        "native_yx_score": [[0., 0., 0.] for _ in producer.geometry.JOINTS]}
        for index, offset in enumerate(offsets)]
    base = {"frame_index": 1, "effectiveness_eligible": True, "native_timestamp_ms": 16.,
        "capture_timestamp_ms": 16., "decoded_bgr_sha256": "synthetic",
        "association_status": "none" if not candidates else ("unique_geometric_candidate" if len(candidates) == 1 else "ambiguous"),
        "candidate_slot_indices": list(candidates), "slots": slots}
    states = dict.fromkeys(producer.JOINTS, "observed")
    return base, raw, states


class JointMeasurementTests(unittest.TestCase):
    def test_exact_same_name_and_diagonal_units(self):
        base, raw, states = fixture(offsets=(10., 0., 0., 0., 0., 0.))
        index = producer.geometry.JOINTS.index("RIGHT_ELBOW")
        base["slots"][0]["source_xy"][index] = [23., 24.]
        result = producer.frame_measurement(base, raw, states, TARGET)
        elbow = result["joints"]["RIGHT_ELBOW"]
        self.assertEqual(elbow["distance_range_px"], {"min": 5., "max": 5.})
        self.assertAlmostEqual(elbow["distance_range_diagonal"]["min"], 5. / (20000. ** .5))
        self.assertEqual(len(result["joints"]), 12)
        self.assertEqual(len(elbow["slot_distances"]), 6)

    def test_ambiguous_range_does_not_select_slot(self):
        base, raw, states = fixture(candidates=(1, 3))
        value = producer.frame_measurement(base, raw, states, TARGET)
        for joint in value["joints"].values():
            self.assertEqual(joint["distance_range_px"], {"min": 10., "max": 30.})
            self.assertEqual([row["slot_index"] for row in joint["candidate_distances"]], [1, 3])
        self.assertEqual(value["candidate_slot_indices"], [1, 3])
        self.assertNotIn("selected_slot_index", value)

    def test_same_slot_rms_cannot_assemble_best_joints_across_slots(self):
        base, raw, states = fixture(candidates=(0, 1), offsets=(0.,) * 6)
        for slot_index, names in ((0, producer.TORSO[:2]), (1, producer.TORSO[2:])):
            for name in names:
                base["slots"][slot_index]["source_xy"][producer.geometry.JOINTS.index(name)] = [30., 20.]
        value = producer.frame_measurement(base, raw, states, TARGET)
        self.assertTrue(all(value["joints"][name]["distance_range_px"]["min"] == 0 for name in producer.TORSO))
        self.assertAlmostEqual(value["torso_rms"]["range_px"]["min"], 50. ** .5)

    def test_no_candidates_missing_range_retains_all_slots(self):
        value = producer.frame_measurement(*fixture(candidates=()), TARGET)
        for joint in value["joints"].values():
            self.assertEqual(joint["distance_range_px"], {"min": None, "max": None})
            self.assertEqual(len(joint["slot_distances"]), 6)
            self.assertEqual(joint["candidate_distances"], [])

    def test_raw_missing_one_joint_does_not_erase_other_distances(self):
        base, raw, states = fixture()
        raw["LEFT_SHOULDER"] = None
        value = producer.frame_measurement(base, raw, states, TARGET)
        self.assertIsNone(value["joints"]["LEFT_SHOULDER"]["distance_range_px"]["min"])
        self.assertEqual(value["joints"]["RIGHT_ELBOW"]["distance_range_px"]["min"], 0.)
        self.assertIsNone(value["torso_rms"]["range_px"]["min"])
        json.dumps(value, allow_nan=False)

    def test_zero_confidence_and_saved_missing_state_are_not_new_coordinate_gates(self):
        base, raw, states = fixture()
        states["RIGHT_WRIST"] = "missing"
        value = producer.frame_measurement(base, raw, states, TARGET)["joints"]["RIGHT_WRIST"]
        self.assertEqual(value["baseline_model_state"], "missing")
        self.assertEqual(value["raw"]["visibility"], 0.)
        self.assertEqual(value["distance_range_px"]["min"], 0.)
        self.assertEqual(value["candidate_distances"][0]["native_joint_score"], 0.)

    def test_finite_out_of_image_coordinates_are_not_censored(self):
        base, raw, states = fixture(offsets=(90.,) * 6)
        raw["RIGHT_ELBOW"]["x"] = 1.2
        value = producer.frame_measurement(base, raw, states, TARGET)["joints"]["RIGHT_ELBOW"]
        self.assertFalse(value["raw"]["in_source"])
        self.assertFalse(value["candidate_distances"][0]["native_in_source"])
        self.assertEqual(value["distance_range_px"]["min"], 10.)

    def test_nonfinite_or_overflow_raw_is_explicitly_missing(self):
        for value in (float("nan"), float("inf"), 1e308):
            base, raw, states = fixture()
            raw["RIGHT_ELBOW"]["x"] = value
            result = producer.frame_measurement(base, raw, states, TARGET)
            self.assertFalse(result["joints"]["RIGHT_ELBOW"]["raw"]["finite"])
            self.assertIsNone(result["joints"]["RIGHT_ELBOW"]["distance_range_px"]["min"])
            json.dumps(result, allow_nan=False)

    def test_invalid_model_state_rejected_and_input_not_mutated(self):
        args = fixture()
        original = copy.deepcopy(args)
        producer.frame_measurement(*args, TARGET)
        self.assertEqual(args, original)
        args[2]["RIGHT_ELBOW"] = "trusted"
        with self.assertRaisesRegex(ValueError, "saved pose state"):
            producer.frame_measurement(*args, TARGET)


class SourceBoundaryTests(unittest.TestCase):
    def test_human_source_role_or_threshold_or_changed_denominator_rejected(self):
        plan = {"status": "frozen_before_disagreement_measurement", "policy": copy.deepcopy(producer.POLICY),
            "human_annotation_inputs": [], "pose_inference_budget": 0, "tracker_inference_budget": 0,
            "production_adoption": False, "source_frames": 2, "non_seed_frames": 1,
            "code": {key: {"path": path, "sha256": "fixture"} for key, path in producer.CODE_PATHS.items()},
            "clips": [{"target": TARGET, "sources": {role: {} for role in producer.SOURCE_ROLES}}]}
        with patch.object(producer.geometry, "verify_ref"), patch.object(producer.geometry, "sha", return_value="fixture"):
            for kind in ("source", "cutoff", "frames"):
                changed = copy.deepcopy(plan)
                if kind == "source": changed["clips"][0]["sources"]["ground_truth"] = {}
                elif kind == "cutoff": changed["policy"]["score_cutoff"] = .5
                else: changed["non_seed_frames"] = 2
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    producer.verify_plan(ROOT, changed)

    def test_changed_source_after_computation_aborts_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source.json"
            source.write_text("sealed", encoding="utf-8")
            ref = {"path": "source.json", "sha256": producer.geometry.sha(source)}
            plan = root / "plan.json"
            plan.write_text(json.dumps({"output_directory": "analysis_results/new", "clips": [{}]}), encoding="utf-8")
            def mutate(*args):
                source.write_text("changed", encoding="utf-8")
                return {}
            with patch.object(producer, "verify_plan", side_effect=lambda *a: producer.geometry.verify_ref(root, ref)), \
                    patch.object(producer, "measure_clip", side_effect=mutate):
                with self.assertRaisesRegex(ValueError, "Frozen source changed"):
                    producer.measure(root, plan)
            self.assertFalse((root / "analysis_results/new").exists())


if __name__ == "__main__":
    unittest.main()
