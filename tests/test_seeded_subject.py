"""Synthetic regression checks for declared-seed CSRT continuation boundaries."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("measure_seeded_subject", ROOT / "scripts/measure_seeded_subject.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class SeededContinuationTests(unittest.TestCase):
    def fixture(self, count=4):
        pixels = [np.full((32, 40, 3), value, np.uint8) for value in range(count)]
        times = [index * 1000 / 30 for index in range(count)]
        capture = Mock()
        capture.read.side_effect = [(True, item) for item in pixels] + [(False, None)]
        capture.get.side_effect = times
        tracker = Mock()
        tracker.init.return_value = None
        tracker.update.return_value = (True, (3, 4, 12, 20))
        tracker.getTrackingScore.return_value = .7
        seed = {"rectangle_xywh": [3, 4, 12, 20], "native_timestamp_ms": 0.,
                "decoded_bgr_sha256": hashlib.sha256(pixels[0].tobytes()).hexdigest()}
        technical = {"timestamps_ms": times}
        target = {"total_frames": count, "width": 40, "height": 32}
        return capture, tracker, seed, technical, target, pixels

    def run_fixture(self, values):
        return measure.measure_frames(*values[:5])

    def test_none_initialization_is_normal_and_only_one_init_occurs(self):
        values = self.fixture()
        report = self.run_fixture(values)
        tracker = values[1]
        self.assertEqual([f["tracking_status"] for f in report["frames"]],
                         ["initialized", "native_success", "native_success", "native_success"])
        self.assertEqual(report["initialization_calls"], 1)
        self.assertEqual(report["native_update_calls"], 3)
        tracker.init.assert_called_once()
        self.assertIs(tracker.init.call_args.args[0], values[5][0])
        self.assertEqual(tracker.init.call_args.args[1], (3, 4, 12, 20))
        self.assertIsNone(report["frames"][0]["native_update_success"])
        self.assertIsNone(report["frames"][0]["native_rectangle_xywh"])
        self.assertEqual(report["frames"][0]["usable_rectangle_xywh"], [3, 4, 12, 20])
        self.assertEqual(tracker.getTrackingScore.call_count, 3)
        self.assertTrue(all(f["subject_assignment"] is None and f["warning_prediction"] is None
                            for f in report["frames"]))
        self.assertIsNone(report["terminal_break"])

    def test_first_false_is_terminal_with_no_reinit_or_recovery(self):
        values = self.fixture()
        tracker = values[1]
        tracker.update.side_effect = [(False, (1, 2, 3, 4)), (True, (3, 4, 12, 20))]
        report = self.run_fixture(values)
        self.assertEqual([f["tracking_status"] for f in report["frames"]],
                         ["initialized", "terminal_break", "not_attempted_after_terminal_break",
                          "not_attempted_after_terminal_break"])
        self.assertEqual(report["terminal_break"], {"frame_index": 1, "reason": "native_update_false"})
        self.assertEqual(report["native_update_calls"], 1)
        tracker.update.assert_called_once()
        tracker.init.assert_called_once()
        self.assertEqual(values[0].read.call_count, 5)
        self.assertEqual(report["frames"][1]["native_rectangle_xywh"], [1, 2, 3, 4])
        self.assertIsNone(report["frames"][1]["usable_rectangle_xywh"])
        self.assertTrue(all(f["usable_rectangle_xywh"] is None for f in report["frames"][1:]))

    def test_initialization_exception_keeps_all_receipts_and_never_updates(self):
        values = self.fixture()
        values[1].init.side_effect = RuntimeError("synthetic init failure")
        report = self.run_fixture(values)
        self.assertEqual([f["tracking_status"] for f in report["frames"]],
                         ["init_failed"] + ["not_attempted_after_initialization_failure"] * 3)
        self.assertEqual(report["terminal_break"]["frame_index"], 0)
        self.assertEqual(report["initialization_calls"], 1)
        self.assertEqual(report["native_update_calls"], 0)
        values[1].update.assert_not_called()
        values[1].getTrackingScore.assert_not_called()
        self.assertEqual(len(report["frames"]), 4)

    def test_update_exception_is_terminal_without_recovering(self):
        values = self.fixture()
        values[1].update.side_effect = RuntimeError("synthetic update failure")
        report = self.run_fixture(values)
        self.assertEqual(report["frames"][1]["tracking_status"], "terminal_break")
        self.assertIn("RuntimeError: synthetic update failure", report["frames"][1]["failure_reason"])
        self.assertEqual(report["frames"][2]["tracking_status"], "not_attempted_after_terminal_break")
        values[1].update.assert_called_once()

    def test_partial_outside_is_preserved_without_clamping_or_failure(self):
        values = self.fixture()
        values[1].update.return_value = (True, (-3, 27, 12, 20))
        report = self.run_fixture(values)
        for frame in report["frames"][1:]:
            self.assertEqual(frame["native_rectangle_xywh"], [-3, 27, 12, 20])
            self.assertEqual(frame["usable_rectangle_xywh"], [-3, 27, 12, 20])
            self.assertTrue(frame["truncated"])
            self.assertEqual(frame["tracking_status"], "native_success")
        self.assertIsNone(report["terminal_break"])

    def test_fully_outside_is_terminal_and_retains_native_rectangle(self):
        for rectangle in [(40, 0, 12, 20), (-12, 0, 12, 20), (0, 32, 12, 20), (0, -20, 12, 20)]:
            with self.subTest(rectangle=rectangle):
                values = self.fixture()
                values[1].update.return_value = (True, rectangle)
                report = self.run_fixture(values)
                frame = report["frames"][1]
                self.assertEqual(frame["native_rectangle_xywh"], list(rectangle))
                self.assertIsNone(frame["usable_rectangle_xywh"])
                self.assertEqual(frame["failure_reason"], "native_rectangle_fully_outside_image")
                values[1].update.assert_called_once()

    def test_invalid_and_nonfinite_geometry_are_json_safe_terminal_receipts(self):
        rectangles = [(0, 0, 0, 20), (0, 0, 10, -1), (True, 0, 10, 20),
                      (float("nan"), 0, 10, 20), (0, float("inf"), 10, 20),
                      (0, 0, 10), None, "malformed", np.array(3), np.zeros((4, 2))]
        for rectangle in rectangles:
            with self.subTest(rectangle=rectangle):
                values = self.fixture()
                values[1].update.return_value = (True, rectangle)
                report = self.run_fixture(values)
                frame = report["frames"][1]
                self.assertEqual(frame["tracking_status"], "terminal_break")
                self.assertEqual(frame["failure_reason"], "invalid_native_rectangle")
                self.assertIsNone(frame["usable_rectangle_xywh"])
                self.assertIsNone(frame["native_rectangle_xywh"])
                json.dumps(report, allow_nan=False)
                values[1].update.assert_called_once()

    def test_score_exception_or_nonfinite_never_breaks_tracking(self):
        for score in [RuntimeError("synthetic unavailable score"), float("nan"), float("inf"), True]:
            with self.subTest(score=score):
                values = self.fixture()
                if isinstance(score, Exception):
                    values[1].getTrackingScore.side_effect = score
                else:
                    values[1].getTrackingScore.return_value = score
                report = self.run_fixture(values)
                self.assertIsNone(report["terminal_break"])
                for frame in report["frames"][1:]:
                    self.assertEqual(frame["tracking_status"], "native_success")
                    self.assertIsNone(frame["raw_tracking_score"])
                    self.assertIsNotNone(frame["score_error"])
                json.dumps(report, allow_nan=False)

    def test_seed_pixel_receipt_mismatch_prevents_initialization(self):
        values = self.fixture()
        values[2]["decoded_bgr_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Initialization frame"):
            self.run_fixture(values)
        values[1].init.assert_not_called()

    def test_decode_pts_and_extra_frames_are_integrity_failures_even_after_break(self):
        for kind in ["decode", "pts", "extra"]:
            with self.subTest(kind=kind):
                values = self.fixture()
                values[1].update.return_value = (False, (1, 2, 3, 4))
                if kind == "decode":
                    values[0].read.side_effect = [(True, values[5][0]), (True, values[5][1]), (False, None)]
                elif kind == "pts":
                    values[0].get.side_effect = [0., 1000 / 30, 999.]
                else:
                    values[0].read.side_effect = [(True, p) for p in values[5]] + [(True, values[5][0])]
                with self.assertRaises(ValueError):
                    self.run_fixture(values)

    def test_native_pixel_mutation_is_integrity_failure_for_init_and_update(self):
        for stage in ["init", "update"]:
            with self.subTest(stage=stage):
                values = self.fixture()
                def mutate(pixels, *args):
                    pixels[0, 0, 0] = 255
                    return None if stage == "init" else (True, (3, 4, 12, 20))
                getattr(values[1], stage).side_effect = mutate
                with self.assertRaisesRegex(ValueError, "mutated source pixels"):
                    self.run_fixture(values)


class SeededFreezeTests(unittest.TestCase):
    def fixture(self):
        parameters = {key: 0 for key in measure.PARAMETER_NAMES}
        sources = {role: {"path": role + ".json", "sha256": "receipt"} for role in measure.PRODUCER_ROLES}
        proposal = {"target": copy.deepcopy(measure.TARGET), "proposed_parameters": parameters,
                    "proposed_producer_sources": sources, "failure_policy": measure.FAILURE_POLICY,
                    "review_sampling": copy.deepcopy(measure.REVIEW_SAMPLING),
                    "raw_score_policy": measure.RAW_SCORE_POLICY,
                    "initialization_failure_policy": measure.INITIALIZATION_FAILURE_POLICY,
                    "integrity_failure_policy": measure.INTEGRITY_FAILURE_POLICY,
                    "runtime": {}, "native_binding_hashes": {"binding.pyd": "receipt"}}
        plan = {"status": "frozen_before_measurement", "target": copy.deepcopy(measure.TARGET),
                "parameters": parameters, "runtime": {}, "producer_sources": sources,
                "failure_policy": measure.FAILURE_POLICY, "review_sampling": proposal["review_sampling"],
                "raw_score_policy": measure.RAW_SCORE_POLICY,
                "initialization_failure_policy": measure.INITIALIZATION_FAILURE_POLICY,
                "integrity_failure_policy": measure.INTEGRITY_FAILURE_POLICY,
                "proposal_manifest": "proposal.json", "proposal_manifest_sha256": "receipt",
                "producer_sha256": "receipt", "evaluator_sha256": "receipt", "test_sha256": "receipt",
                "native_binding_hashes": {"binding.pyd": "receipt"}}
        return plan, proposal, parameters

    def verify(self, plan, proposal, parameters, **kwargs):
        with patch.object(measure, "default_parameters", return_value=parameters), \
                patch.object(measure, "runtime", return_value={}), \
                patch.object(measure, "read", return_value=proposal), \
                patch.object(measure, "sha", return_value="receipt"), \
                patch.object(measure, "verify_sources") as sources:
            measure.verify_execution(ROOT, plan, **kwargs)
        return sources

    def test_frozen_producer_uses_exactly_four_roles(self):
        plan, proposal, parameters = self.fixture()
        source_check = self.verify(plan, proposal, parameters)
        source_check.assert_called_once_with(ROOT.resolve(), plan["producer_sources"])
        for role in ["ground_truth", "manual_xy", "full_nine_ownership_answers"]:
            wrong = copy.deepcopy(plan)
            wrong["producer_sources"][role] = {"path": "forbidden.json", "sha256": "receipt"}
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "source role"):
                self.verify(wrong, proposal, parameters)

    def test_changed_target_parameters_status_or_failure_policy_are_rejected(self):
        plan, proposal, parameters = self.fixture()
        variants = [("target", {**measure.TARGET, "total_frames": 114}), ("status", "proposal_only"),
                    ("parameters", {**parameters, "padding": 99}), ("failure_policy", "reset_on_loss"),
                    ("raw_score_policy", "confidence_gate"), ("initialization_failure_policy", "retry"),
                    ("integrity_failure_policy", "skip_bad_frame"), ("review_sampling", {})]
        for name, value in variants:
            wrong = copy.deepcopy(plan)
            wrong[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(wrong, proposal, parameters)

    def test_changed_proposal_sampling_or_inputs_are_rejected(self):
        plan, proposal, parameters = self.fixture()
        for key in ["review_sampling", "proposed_producer_sources"]:
            wrong = copy.deepcopy(proposal)
            wrong[key] = {}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "differs"):
                self.verify(plan, wrong, parameters)

    def test_evaluator_true_binds_evaluator_and_tests_without_opening_evaluator_sources(self):
        plan, proposal, parameters = self.fixture()
        opened = []
        def file_hash(path):
            opened.append(Path(path).as_posix())
            return "receipt"
        with patch.object(measure, "default_parameters", return_value=parameters), \
                patch.object(measure, "runtime", return_value={}), \
                patch.object(measure, "read", return_value=proposal), \
                patch.object(measure, "sha", side_effect=file_hash), \
                patch.object(measure, "verify_sources"):
            measure.verify_execution(ROOT, plan, evaluator=True)
        self.assertTrue(any(name.endswith("scripts/evaluate_seeded_subject.py") for name in opened))
        self.assertTrue(any(name.endswith("tests/test_seeded_subject.py") for name in opened))
        self.assertEqual(len(opened), 5)

    def test_source_paths_outside_workspace_are_rejected_before_hashing(self):
        with patch.object(measure, "sha") as digest:
            with self.assertRaisesRegex(ValueError, "outside workspace"):
                measure.verify_sources(ROOT, {"video": {"path": "../elsewhere.mp4", "sha256": "receipt"}})
        digest.assert_not_called()

    def test_installed_csrt_parameter_constructor_has_exactly_27_frozen_fields(self):
        parameters = measure.default_parameters()
        self.assertEqual(len(parameters), 27)
        self.assertEqual(set(parameters), set(measure.PARAMETER_NAMES))
        json.dumps(parameters, allow_nan=False)

    def test_writer_is_exclusive_strict_json_with_lf(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as directory:
            path = Path(directory) / "receipt.json"
            measure.write(path, {"declared_input": "投手"})
            self.assertNotIn(b"\r", path.read_bytes())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"declared_input": "投手"})
            with self.assertRaises(FileExistsError):
                measure.write(path, {})


class SeededRunBoundaryTests(unittest.TestCase):
    def fixture(self):
        pixels = np.zeros((628, 510, 3), np.uint8)
        times = [index * 1000 / 30 for index in range(115)]
        parameters = measure.default_parameters()
        sources = {role: {"path": role + ".json", "sha256": "source-hash"}
                   for role in measure.PRODUCER_ROLES}
        plan = {"target": copy.deepcopy(measure.TARGET), "producer_sources": sources,
                "parameters": parameters, "proposal_manifest": "proposal.json",
                "proposal_manifest_sha256": "proposal-hash"}
        seed = {"status": "proposed_not_used", "pitch_id": "pitch_003", "frame_index": 0,
                "native_timestamp_ms": 0., "rectangle_xywh": list(measure.SEED_RECTANGLE),
                "decoded_bgr_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
                "human_conclusion": "pitcher", "source_kind": "model_proposed_human_confirmed",
                "extent_observation": None, "query_id": "pitch_003_f0000_box0",
                "source_video": sources["video"], "producer_must_not_open_lineage_sources": True,
                "excluded_from_effectiveness_evaluation": True,
                "lineage_for_parent_preflight_only": {"source_review": {"path": "must-not-open-nine-answers.json"}}}
        technical = {"sha256": "source-hash", "frame_count": 115, "width": 510, "height": 628,
                     "timestamps_ms": times}
        files = {"plan.json": plan, "metadata.json": {"schema_version": "pitch-input-v1", "pitch_id": "pitch_003"},
                 "video_technical.json": technical, "initialization.json": seed}
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.side_effect = [(True, pixels)] * 115 + [(False, None)]
        capture.get.side_effect = times
        tracker = Mock()
        tracker.init.return_value = None
        tracker.update.return_value = (True, tuple(measure.SEED_RECTANGLE))
        tracker.getTrackingScore.return_value = -.125
        api = Mock()
        api.Params.return_value = Mock(**parameters)
        api.create.return_value = tracker
        return files, capture, tracker, api

    def invoke(self, fixture, writer=None):
        files, capture, tracker, api = fixture
        opened = []
        writer = Mock() if writer is None else writer
        def read_allowed(path):
            opened.append(Path(path).name)
            return files[Path(path).name]
        with patch.object(measure, "read", side_effect=read_allowed), \
                patch.object(measure, "verify_execution"), \
                patch.object(measure, "runtime", return_value={}), \
                patch.object(measure, "sha", return_value="receipt"), \
                patch.object(measure.cv2, "TrackerCSRT", api), \
                patch.object(measure.cv2, "VideoCapture", return_value=capture), \
                patch.object(Path, "mkdir"), \
                patch.object(measure, "write", writer):
            result = measure.run(ROOT, ROOT / "plan.json", ROOT / "analysis_results/synthetic-seeded-test-never-written")
        return result, opened, writer

    def test_run_reads_only_declared_sources_and_seals_all_115_synthetic_receipts(self):
        fixture = self.fixture()
        report, opened, writer = self.invoke(fixture)
        self.assertEqual(opened, ["plan.json", "metadata.json", "video_technical.json", "initialization.json"])
        self.assertEqual(len(report["frames"]), 115)
        self.assertEqual(report["native_update_calls"], 114)
        self.assertEqual(report["initialization_calls"], 1)
        self.assertEqual(report["post_initialization_frame_denominator"], 114)
        self.assertEqual(report["human_annotation_inputs"], [fixture[0]["plan.json"]["producer_sources"]["initialization"]])
        self.assertEqual(report["pose_inputs"], [])
        self.assertEqual(report["status"], "sealed_measurements_only")
        self.assertIsNone(report["subject_assignment"])
        self.assertIsNone(report["warning_policy"])
        self.assertIsNone(report["calibrated_confidence"])
        self.assertEqual(report["frames"][1]["raw_tracking_score"], -.125)
        writer.assert_called_once()
        fixture[1].release.assert_called_once()

    def test_run_rejects_integrity_failure_without_writing_a_seal(self):
        fixture = self.fixture()
        fixture[0]["initialization.json"]["decoded_bgr_sha256"] = "0" * 64
        writer = Mock()
        with self.assertRaisesRegex(ValueError, "Initialization frame"):
            self.invoke(fixture, writer=writer)
        writer.assert_not_called()
        fixture[2].init.assert_not_called()
        fixture[1].release.assert_called_once()

    def test_initialization_semantics_cannot_be_replaced_by_full_body_or_other_subject(self):
        fixture = self.fixture()
        seed = fixture[0]["initialization.json"]
        plan = fixture[0]["plan.json"]
        for key, value in [("human_conclusion", "other"), ("extent_observation", "full_body"),
                           ("frame_index", 38), ("rectangle_xywh", [85, 165, 218, 435])]:
            wrong = copy.deepcopy(seed)
            wrong[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                measure.validate_initialization(wrong, plan)


if __name__ == "__main__":
    unittest.main()
