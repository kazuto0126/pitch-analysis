"""Checks for the frozen HOG candidate pilot and its reviewer boundary."""
from __future__ import annotations

import importlib.util
import copy
import subprocess
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


measure = load_script("measure_person_support")
evaluate = load_script("evaluate_person_support")


class PersonEvaluatorCommandTests(unittest.TestCase):
    def test_command_dispatches_named_plan_to_evaluator_before_reading_it(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT_DIR / "evaluate_person_support.py"),
                                 "__absent_person_plan__.json", "__absent_person_measurements__.json",
                                 str(SCRIPT_DIR.parent / "analysis_results" / "__absent_person_cli_output__")],
                                cwd=SCRIPT_DIR.parent, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FileNotFoundError", result.stderr)
        self.assertIn("__absent_person_plan__.json", result.stderr)
        self.assertNotIn("unexpected keyword argument", result.stderr)

    def test_replay_preserves_each_receipt_but_compares_exact_values_without_api_order(self):
        original = measure.serialize_candidates([[1, 2, 10, 20], [4, 5, 10, 20]], [.5, .7], 100, 100)
        replay = measure.serialize_candidates([[4, 5, 10, 20], [1, 2, 10, 20]], [.7, .5], 100, 100)
        before = copy.deepcopy((original, replay))
        self.assertEqual(evaluate.compare_replay(original, replay),
                         {"api_order_equal": False, "candidate_values_equal_ignoring_order": True})
        self.assertEqual((original, replay), before)

    def test_replay_does_not_ignore_score_coordinate_or_duplicate_count_changes(self):
        original = measure.serialize_candidates([[1, 2, 10, 20]], [.5], 100, 100)
        variants = [measure.serialize_candidates([[1, 2, 10, 20]], [.50000000001], 100, 100),
                    measure.serialize_candidates([[2, 2, 10, 20]], [.5], 100, 100),
                    original + [{**original[0], "candidate_index": 1}]]
        for replay in variants:
            with self.subTest(replay=replay):
                self.assertFalse(evaluate.compare_replay(original, replay)["candidate_values_equal_ignoring_order"])


class PersonCandidateSerializationTests(unittest.TestCase):
    def test_api_order_scores_and_outside_coordinates_are_preserved(self):
        rectangles = np.array([[90, 20, 25, 40], [-5, -2, 20, 30], [1, 2, 30, 40]], dtype=np.int32)
        scores = np.array([-.7, 4.5, .25], dtype=np.float64)
        values = measure.serialize_candidates(rectangles, scores, 100, 80)
        self.assertEqual([v["candidate_index"] for v in values], [0, 1, 2])
        self.assertEqual([v["rectangle_xywh"] for v in values], rectangles.tolist())
        self.assertEqual([v["raw_svm_score"] for v in values], scores.tolist())
        self.assertEqual([v["entirely_inside_image"] for v in values], [False, False, True])
        self.assertTrue(all(v["subject_assignment"] is None for v in values))

    def test_empty_api_result_is_retained_as_empty_candidates(self):
        self.assertEqual(measure.serialize_candidates([], [], 64, 128), [])

    def test_cardinality_mismatch_is_rejected_in_both_directions(self):
        for rectangles, scores in [([[0, 0, 10, 20]], []), ([], [.5])]:
            with self.subTest(rectangles=rectangles, scores=scores), self.assertRaisesRegex(ValueError, "cardinality"):
                measure.serialize_candidates(rectangles, scores, 64, 128)

    def test_nonfinite_rectangle_and_score_values_are_rejected(self):
        for bad in [float("nan"), float("inf"), -float("inf")]:
            with self.subTest(kind="coordinate", value=bad), self.assertRaises(ValueError):
                measure.serialize_candidates([[bad, 0, 10, 20]], [.5], 64, 128)
            with self.subTest(kind="score", value=bad), self.assertRaises(ValueError):
                measure.serialize_candidates([[0, 0, 10, 20]], [bad], 64, 128)

    def test_noninteger_boolean_and_malformed_rectangles_are_rejected(self):
        for rectangle in [[.5, 0, 10, 20], [0, 0, 10.25, 20], [True, 0, 10, 20],
                          [np.bool_(False), 0, 10, 20], [0, 0, 10], [0, 0, 10, 20, 30]]:
            with self.subTest(rectangle=rectangle), self.assertRaises(ValueError):
                measure.serialize_candidates([rectangle], [.5], 64, 128)

    def test_zero_and_negative_sizes_are_rejected(self):
        for width, height in [(0, 20), (10, 0), (-10, 20), (10, -20)]:
            with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                measure.serialize_candidates([[0, 0, width, height]], [.5], 64, 128)


class PersonDetectorTests(unittest.TestCase):
    def test_native_bgr_array_and_exact_frozen_arguments_reach_hog(self):
        frame = np.arange(48 * 80 * 3, dtype=np.uint8).reshape(48, 80, 3)
        before = frame.copy()
        hog = Mock()
        hog.detectMultiScale.return_value = (np.array([[-4, 3, 12, 25]]), np.array([-.125]))
        values = measure.detect(hog, frame)
        hog.detectMultiScale.assert_called_once()
        args, kwargs = hog.detectMultiScale.call_args
        self.assertEqual(len(args), 1)
        self.assertIs(args[0], frame)
        self.assertEqual(kwargs, {"hitThreshold": 0., "winStride": (0, 0), "padding": (0, 0),
                                  "scale": 1.05, "groupThreshold": 2., "useMeanshiftGrouping": False})
        np.testing.assert_array_equal(frame, before)
        self.assertEqual(values[0]["rectangle_xywh"], [-4, 3, 12, 25])
        self.assertEqual(values[0]["raw_svm_score"], -.125)

    def test_invalid_native_frame_shape_or_type_is_rejected_before_hog(self):
        for frame in [np.zeros((128, 64), np.uint8), np.zeros((128, 64, 4), np.uint8),
                      np.zeros((128, 64, 3), np.float32)]:
            hog = Mock()
            with self.subTest(shape=frame.shape, dtype=frame.dtype), self.assertRaises(ValueError):
                measure.detect(hog, frame)
            hog.detectMultiScale.assert_not_called()

    def test_real_default_hog_accepts_fixed_parameters_on_blank_native_window(self):
        hog, signature = measure.create_detector()
        frame = np.zeros((128, 64, 3), np.uint8)
        self.assertEqual(signature["win_size"], [64, 128])
        self.assertTrue(signature["detector_size_valid"])
        self.assertEqual(measure.detect(hog, frame), [])
        self.assertFalse(frame.any())

    def test_run_keeps_every_decoded_frame_when_hog_returns_no_rectangles(self):
        pixels = [np.zeros((128, 64, 3), np.uint8), np.full((128, 64, 3), 7, np.uint8)]
        timestamps = [0., 33.3667]
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.side_effect = [(True, pixels[0]), (True, pixels[1]), (False, None)]
        capture.get.side_effect = timestamps
        hog = Mock()
        hog.detectMultiScale.return_value = ((), ())
        target = {"pitch_id": "synthetic-pilot-test", "total_frames": 2, "width": 64, "height": 128}
        plan = {"target": target, "detector_signature": {}, "producer_sources": {
            "video": {"path": "synthetic.mp4", "sha256": "video-hash"},
            "metadata": {"path": "synthetic-meta.json"},
            "video_technical": {"path": "synthetic-technical.json"}}}
        metadata = {"schema_version": "pitch-input-v1", "pitch_id": target["pitch_id"]}
        technical = {"sha256": "video-hash", "frame_count": 2, "width": 64, "height": 128,
                     "timestamps_ms": timestamps}
        root = SCRIPT_DIR.parent
        source_values = {"plan.json": plan, "synthetic-meta.json": metadata,
                         "synthetic-technical.json": technical}
        with patch.object(measure, "read", side_effect=lambda p: source_values[p.name]), \
                patch.object(measure, "verify_execution"), \
                patch.object(measure, "create_detector", return_value=(hog, {})), \
                patch.object(measure.cv2, "VideoCapture", return_value=capture), \
                patch.object(measure, "runtime", return_value={}), \
                patch.object(measure, "sha", return_value="test-hash"), \
                patch.object(Path, "mkdir"), \
                patch.object(measure, "write") as write:
            report = measure.run(root, root / "plan.json", root / "analysis_results" / "synthetic-test-never-written")
        self.assertEqual([f["frame_index"] for f in report["frames"]], [0, 1])
        self.assertEqual([f["native_timestamp_ms"] for f in report["frames"]], timestamps)
        self.assertEqual([f["candidates"] for f in report["frames"]], [[], []])
        self.assertTrue(all(f["warning_prediction"] is None for f in report["frames"]))
        self.assertEqual(report["human_annotation_inputs"], [])
        self.assertEqual(report["pose_inputs"], [])
        self.assertEqual(report["phase2_automatic_reliability"], "NOT PASSED")
        write.assert_called_once()
        self.assertIs(write.call_args.args[1], report)
        capture.release.assert_called_once()


class PersonContextTests(unittest.TestCase):
    def test_point_membership_uses_native_half_open_edges(self):
        rectangle = [-5, 10, 20, 30]
        for point, expected in [((-5, 10), True), ((14.999, 39.999), True),
                                ((15, 20), False), ((0, 40), False),
                                ((-5.001, 20), False), ((0, 9.999), False)]:
            with self.subTest(point=point):
                self.assertEqual(evaluate.contains(rectangle, point), expected)

    @staticmethod
    def visible_torso():
        return {"joints": [
            {"name": "LEFT_SHOULDER", "status": "visible", "x_px": 10., "y_px": 20.},
            {"name": "RIGHT_SHOULDER", "status": "visible", "x_px": 29.9, "y_px": 20.},
            {"name": "LEFT_HIP", "status": "visible", "x_px": 15., "y_px": 39.9},
            {"name": "RIGHT_HIP", "status": "visible", "x_px": 29., "y_px": 39.}]}

    def test_four_visible_torso_points_give_descriptive_box_context(self):
        context = evaluate.torso_context(self.visible_torso(), [
            {"candidate_index": 8, "rectangle_xywh": [10, 20, 20, 20]},
            {"candidate_index": 2, "rectangle_xywh": [10, 20, 19, 20]}])
        self.assertTrue(context["available"])
        self.assertEqual(context["missing_joint_names"], [])
        self.assertEqual([c["candidate_index"] for c in context["candidates"]], [8, 2])
        self.assertTrue(context["candidates"][0]["all_four_inside"])
        self.assertFalse(context["candidates"][1]["all_four_inside"])
        self.assertEqual(context["candidates"][1]["visible_torso_points_inside"], ["LEFT_SHOULDER", "LEFT_HIP"])
        self.assertEqual(context["candidates"][1]["visible_torso_points_outside"], ["RIGHT_SHOULDER", "RIGHT_HIP"])

    def test_unobservable_or_uncertain_torso_xy_is_excluded_and_answer_stays_null(self):
        for status, coordinates in [("not_observable", (None, None)), ("uncertain", (15., 25.))]:
            frame = self.visible_torso()
            frame["joints"][2].update(status=status, x_px=coordinates[0], y_px=coordinates[1])
            with self.subTest(status=status):
                context = evaluate.torso_context(frame, [{"candidate_index": 0, "rectangle_xywh": [0, 0, 50, 50]}])
                self.assertFalse(context["available"])
                self.assertEqual(context["missing_joint_names"], ["LEFT_HIP"])
                candidate = context["candidates"][0]
                self.assertIsNone(candidate["all_four_inside"])
                self.assertNotIn("LEFT_HIP", candidate["visible_torso_points_inside"])
                self.assertNotIn("LEFT_HIP", candidate["visible_torso_points_outside"])
                self.assertEqual(len(candidate["visible_torso_points_inside"]), 3)

    def test_no_boxes_preserves_empty_context_without_an_ownership_answer(self):
        context = evaluate.torso_context(self.visible_torso(), [])
        self.assertTrue(context["available"])
        self.assertEqual(context["candidates"], [])


class PersonMembershipTests(unittest.TestCase):
    @staticmethod
    def reviews():
        original = {"queries": [
            {"query_id": "old8", "frame_index": 8, "queried_image_xy_px": [12., 15.], "human_code": "O"},
            {"query_id": "old3", "frame_index": 3, "queried_image_xy_px": [8., 4.], "human_code": "T"},
            {"query_id": "old2", "frame_index": 3, "queried_image_xy_px": [2., 4.], "human_code": "P"}]}
        supplement = {"queries": [
            {"query_id": "recheck1", "frame_index": 3, "image_xy_px": [8., 4.],
             "previous_query_id": "old3", "region_status": "human_confirmed", "actual_reply_code": "?", "resolved_code": "O"},
            {"query_id": "new-position", "frame_index": 3, "image_xy_px": [2., 5.],
             "previous_query_id": None, "region_status": "human_confirmed", "actual_reply_code": "T", "resolved_code": "T"},
            {"query_id": "recheck2", "frame_index": 3, "image_xy_px": [8., 4.],
             "previous_query_id": "old3", "region_status": "human_confirmed", "actual_reply_code": "P", "resolved_code": "P"}]}
        return original, supplement

    def test_latest_resolved_code_preserves_history_and_sorted_distinct_positions(self):
        original, supplement = self.reviews()
        before = copy.deepcopy((original, supplement))
        joined = evaluate.join_memberships(original, supplement)
        self.assertEqual([(q["frame_index"], q["image_xy_px"]) for q in joined],
                         [(3, [2., 4.]), (3, [2., 5.]), (3, [8., 4.]), (8, [12., 15.])])
        rechecked = joined[2]
        self.assertEqual(rechecked["latest_human_code"], "P")
        self.assertEqual(rechecked["human_history"], [
            {"query_id": "old3", "code": "T"},
            {"query_id": "recheck1", "actual_reply_code": "?", "code": "O"},
            {"query_id": "recheck2", "actual_reply_code": "P", "code": "P"}])
        self.assertEqual(joined[1]["human_history"], [{"query_id": "new-position", "actual_reply_code": "T", "code": "T"}])
        self.assertEqual((original, supplement), before)

    def test_recheck_requires_matching_original_id_and_exact_position(self):
        for changes in [{"previous_query_id": "absent"}, {"image_xy_px": [8., 4.01]}, {"frame_index": 4}]:
            original, supplement = self.reviews()
            supplement["queries"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "original position"):
                evaluate.join_memberships(original, supplement)

    def test_repeated_position_requires_explicit_prior_link(self):
        original, supplement = self.reviews()
        supplement["queries"][0]["previous_query_id"] = None
        with self.assertRaisesRegex(ValueError, "explicit prior query link"):
            evaluate.join_memberships(original, supplement)

    def test_unresolved_supplementary_answer_is_rejected(self):
        for changes in [{"region_status": "pending"}, {"resolved_code": None}, {"resolved_code": "pitcher"}]:
            original, supplement = self.reviews()
            supplement["queries"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluate.join_memberships(original, supplement)

    def test_duplicate_original_positions_or_question_ids_are_rejected(self):
        for field, value in [("queried_image_xy_px", [8., 4.]), ("query_id", "old3")]:
            original, supplement = self.reviews()
            original["queries"][2][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                evaluate.join_memberships(original, supplement)

    def test_nonfinite_membership_position_is_rejected(self):
        for bad in [float("nan"), float("inf")]:
            original, supplement = self.reviews()
            supplement["queries"][1]["image_xy_px"] = [bad, 5.]
            with self.subTest(value=bad), self.assertRaisesRegex(ValueError, "membership position"):
                evaluate.join_memberships(original, supplement)


class PersonOwnershipQuestionTests(unittest.TestCase):
    @staticmethod
    def candidate(index, rectangle, score=1.):
        return {"candidate_index": index, "rectangle_xywh": rectangle, "raw_svm_score": score,
                "entirely_inside_image": True, "subject_assignment": None}

    @staticmethod
    def frame(index, candidates):
        return {"frame_index": index, "native_timestamp_ms": index * 33.3667,
                "decoded_bgr_sha256": "synthetic-pixel-hash-" + str(index), "candidates": candidates}

    def test_six_fixed_frames_select_top_two_by_raw_score_then_native_geometry(self):
        c = self.candidate
        fixed = [0, 8, 17, 26, 35, 44]
        candidates = [
            [c(0, [1, 0, 1, 1], .7), c(1, [9, 9, 1, 1], .8), c(2, [5, 5, 1, 1], .9)],
            [c(0, [20, 0, 10, 20]), c(1, [2, 99, 100, 200]), c(2, [10, 0, 10, 20])],
            [c(0, [2, 9, 10, 20]), c(1, [2, 1, 10, 20]), c(2, [2, 5, 10, 20])],
            [c(0, [2, 1, 20, 20]), c(1, [2, 1, 5, 20]), c(2, [2, 1, 10, 20])],
            [c(0, [2, 1, 5, 20]), c(1, [2, 1, 5, 5]), c(2, [2, 1, 5, 10])],
            [c(8, [2, 1, 5, 10]), c(7, [2, 1, 5, 10]), c(3, [2, 1, 5, 10])]]
        frames = [self.frame(index, boxes) for index, boxes in zip(fixed, candidates)]
        frames.insert(1, self.frame(3, [c(99, [0, 0, 64, 128], 100.)]))
        before = copy.deepcopy(frames)
        sampling = {"frames": fixed, "max_boxes_per_frame": 2, "maximum_questions": 12}
        questions = evaluate.make_questions(frames, sampling)
        self.assertEqual(len(questions), 12)
        self.assertEqual([(q["frame_index"], q["candidate_index"]) for q in questions],
                         [(0, 2), (0, 1), (8, 1), (8, 2), (17, 1), (17, 2),
                          (26, 1), (26, 2), (35, 1), (35, 2), (44, 3), (44, 7)])
        self.assertEqual(len({q["query_id"] for q in questions}), 12)
        for question in questions:
            for field in ("reviewer", "reviewed_at_utc", "conclusion", "note", "subject_assignment"):
                self.assertIsNone(question[field])
            frame = next(f for f in frames if f["frame_index"] == question["frame_index"])
            candidate = next(c for c in frame["candidates"] if c["candidate_index"] == question["candidate_index"])
            self.assertEqual(question["rectangle_xywh"], candidate["rectangle_xywh"])
            self.assertEqual(question["raw_svm_score"], candidate["raw_svm_score"])
            self.assertEqual(question["decoded_bgr_sha256"], frame["decoded_bgr_sha256"])
            self.assertEqual(question["native_timestamp_ms"], frame["native_timestamp_ms"])
        self.assertEqual(frames, before)

    def test_empty_frames_make_no_ownership_questions_or_forced_answers(self):
        frames = [self.frame(index, []) for index in [0, 8, 17, 26, 35, 44]]
        self.assertEqual(evaluate.make_questions(frames,
            {"frames": [0, 8, 17, 26, 35, 44], "max_boxes_per_frame": 2, "maximum_questions": 12}), [])

    def test_exceeding_the_fixed_question_budget_fails_closed(self):
        frames = [self.frame(0, [self.candidate(i, [i, 0, 10, 20]) for i in range(3)])]
        with self.assertRaisesRegex(ValueError, "review budget"):
            evaluate.make_questions(frames, {"frames": [0], "max_boxes_per_frame": 2, "maximum_questions": 1})


if __name__ == "__main__":
    unittest.main()
