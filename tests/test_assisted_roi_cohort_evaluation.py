"""Synthetic offline replay, denominator and raw-diagnostic regressions."""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import evaluate_assisted_roi_cohort as audit
finally:
    sys.path.pop(0)
from pitch_analysis.subject import PitcherSelector


CONFIG = {"min_visibility": .5, "min_presence": .5}
TARGET = {"pitch_id": "synthetic", "total_frames": 1, "width": 80, "height": 60}


def point(x=.5, y=.5, visibility=.9, presence=.9):
    return {"x": x, "y": y, "z": -.1, "visibility": visibility, "presence": presence}


def candidates():
    pose = [point() for _ in range(33)]
    for index in (11, 12):
        pose[index]["y"] = .1
    for index in (27, 28):
        pose[index]["y"] = .9
    return [pose]


def replay_fixture(*, missing=False):
    pixels = np.arange(TARGET["width"] * TARGET["height"] * 3, dtype=np.uint8).reshape(TARGET["height"], TARGET["width"], 3)
    digest = hashlib.sha256(pixels.tobytes()).hexdigest()
    rect = None if missing else [10, 5, 60, 50]
    tracker = {"frame_index": 0, "native_timestamp_ms": 0., "decoded_bgr_sha256": digest,
               "usable_rectangle_xywh": rect}
    bounds = audit.crop_bounds(rect, TARGET["width"], TARGET["height"])
    crop_candidates = [] if missing else candidates()
    mapped = [] if missing else audit.map_candidates(crop_candidates, bounds, TARGET["width"], TARGET["height"])
    choice = asdict(PitcherSelector().select(audit._poses(mapped)))
    bgr = None if missing else np.ascontiguousarray(pixels[5:55, 10:70].copy())
    rgb = None if missing else cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    frame = {"frame_index": 0, "native_timestamp_ms": 0., "timestamp_ms": 0,
        "decoded_bgr_sha256": digest, "tracker_rectangle_xywh": rect, "crop_bounds_xyxy": bounds,
        "crop_bgr_sha256": None if missing else hashlib.sha256(bgr.tobytes()).hexdigest(),
        "crop_rgb_sha256": None if missing else hashlib.sha256(rgb.tobytes()).hexdigest(),
        "crop_shape": None if missing else list(bgr.shape), "crop_candidates": crop_candidates,
        "full_image_candidates": mapped, "selection": choice,
        "inference_status": "roi_unavailable" if missing else "measured",
        "warning_prediction": None, "subject_alignment_verified": False}
    return frame, tracker, pixels


class ReplayTests(unittest.TestCase):
    def test_general_dimensions_replay_without_any_inference(self):
        frame, tracker, pixels = replay_fixture()
        audit.replay_frame(frame, tracker, pixels, 0., 0., PitcherSelector(), TARGET)

    def test_source_pixel_pts_and_crop_color_tampering_rejected(self):
        frame, tracker, pixels = replay_fixture()
        for key, value in (("decoded_bgr_sha256", "wrong"), ("native_timestamp_ms", 1),
                           ("timestamp_ms", 1), ("crop_bounds_xyxy", [10, 5, 69, 55]),
                           ("crop_rgb_sha256", "wrong"), ("crop_bgr_sha256", "wrong"),
                           ("crop_shape", [1, 2, 3])):
            changed = copy.deepcopy(frame)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.replay_frame(changed, tracker, pixels, 0., 0., PitcherSelector(), TARGET)
        with self.assertRaises(ValueError):
            audit.replay_frame(frame, tracker, pixels[:, :-1], 0., 0., PitcherSelector(), TARGET)
        with self.assertRaises(ValueError):
            audit.replay_frame(frame, tracker, pixels, 0., .1, PitcherSelector(), TARGET)

    def test_all_landmark_xy_z_and_confidence_mapping_tampering_rejected(self):
        frame, tracker, pixels = replay_fixture()
        for key in ("x", "y", "z", "visibility", "presence"):
            changed = copy.deepcopy(frame)
            changed["full_image_candidates"][0][32][key] += .01
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.replay_frame(changed, tracker, pixels, 0., 0., PitcherSelector(), TARGET)
        changed = copy.deepcopy(frame)
        changed["crop_candidates"][0].pop()
        with self.assertRaises(ValueError):
            audit.replay_frame(changed, tracker, pixels, 0., 0., PitcherSelector(), TARGET)

    def test_selector_and_semantic_tampering_rejected(self):
        frame, tracker, pixels = replay_fixture()
        for key, value in (("selection", {**frame["selection"], "index": None}),
                           ("warning_prediction", True), ("subject_alignment_verified", True)):
            changed = copy.deepcopy(frame)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.replay_frame(changed, tracker, pixels, 0., 0., PitcherSelector(), TARGET)

    def test_missing_roi_has_no_fallback_or_fabricated_pixel_receipt(self):
        frame, tracker, pixels = replay_fixture(missing=True)
        audit.replay_frame(frame, tracker, pixels, 0., 0., PitcherSelector(), TARGET)
        for key, value in (("crop_bgr_sha256", "fabricated"), ("crop_candidates", candidates()),
                           ("inference_status", "measured")):
            changed = copy.deepcopy(frame)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.replay_frame(changed, tracker, pixels, 0., 0., PitcherSelector(), TARGET)

    def image_fixture(self):
        _, _, pixels = replay_fixture()
        poses = candidates()
        original = {"frame_index": 0, "timestamp_ms": 0, "status": "rejected", "selected_index": None}
        selection = asdict(PitcherSelector().select(audit._poses(poses)))
        image = audit.frame_measurement(0, 0, 0., hashlib.sha256(pixels.tobytes()).hexdigest(),
            poses, selection, {}, original, TARGET["width"], TARGET["height"], CONFIG)
        return image, pixels, original

    def test_full_frame_image_selector_and_video_comparison_replayed(self):
        image, pixels, original = self.image_fixture()
        audit.replay_image_frame(image, pixels, 0., 0., PitcherSelector(), {}, original, TARGET, CONFIG)
        for mutate in (lambda x: x["image_selection"].update(index=None),
                       lambda x: x["video_selection"].update(status="selected"),
                       lambda x: x["joint_disagreement"]["LEFT_ELBOW"].update(video_gate_pass=True)):
            changed = copy.deepcopy(image)
            mutate(changed)
            with self.assertRaises(ValueError):
                audit.replay_image_frame(changed, pixels, 0., 0., PitcherSelector(), {}, original, TARGET, CONFIG)

    def test_cli_import_does_not_require_new_producer_or_run_inference(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/evaluate_assisted_roi_cohort.py"), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("measurements", result.stdout)


class DiagnosticTests(unittest.TestCase):
    def row(self, index=1, *, crop=None, crop_source=None, image=None, video=None, bounds=(0, 0, 80, 60), label="known_negative"):
        arms = {"crop": {} if crop is None else {"RIGHT_ELBOW": crop},
                "image": {} if image is None else {"RIGHT_ELBOW": image},
                "video": {} if video is None else {"RIGHT_ELBOW": video}}
        cp = {} if crop_source is None else {"RIGHT_ELBOW": crop_source}
        return audit.joint_row(index, "RIGHT_ELBOW", arms, cp, bounds, TARGET, CONFIG, label)

    def test_missing_selection_stays_in_each_denominator_and_confidence_remains_null(self):
        row = self.row(image=point())
        state = row["arms"]["crop"]
        self.assertFalse(state["raw_finite"])
        self.assertTrue(state["missing"])
        self.assertIsNone(state["visibility"])
        summary = audit.summarize_joint_rows([row])
        self.assertEqual(summary["non_seed_frames"], 1)
        self.assertEqual(summary["arms"]["crop"]["missing"], 1)
        self.assertEqual(summary["arms"]["crop"]["visibility"]["count"], 0)

    def test_input_support_is_half_open_and_never_clamps_extrapolation(self):
        for x, supported in ((-.01, False), (0., True), (.999, True), (1., False), (1.01, False)):
            row = self.row(crop=point(), crop_source=point(x=x))
            with self.subTest(x=x):
                self.assertEqual(row["arms"]["crop"]["input_supported_raw"], supported)
                self.assertEqual(row["arms"]["crop"]["extrapolation"], not supported)
                self.assertTrue(row["arms"]["crop"]["gate_pass"])
        row = self.row(crop=point(), crop_source=point(), bounds=None)
        self.assertFalse(row["arms"]["crop"]["input_supported_raw"])

    def test_both_existing_gates_required_with_inclusive_boundary(self):
        for p, passes in ((point(visibility=.499), False), (point(presence=.499), False),
                          (point(visibility=.5, presence=.5), True)):
            row = self.row(crop=p, crop_source=p)
            with self.subTest(point=p):
                self.assertEqual(row["arms"]["crop"]["gate_pass"], passes)
                self.assertEqual(row["arms"]["crop"]["low_gate"], not passes)
        row = self.row(crop=point(x=float("nan")), crop_source=point())
        self.assertFalse(row["arms"]["crop"]["raw_finite"])
        self.assertFalse(row["arms"]["crop"]["missing"])
        summary = audit.summarize_joint_rows([row])["arms"]["crop"]
        self.assertEqual(summary["nonfinite_selected_raw"], 1)

    def test_seed_excluded_from_counts_confidence_spans_and_jumps(self):
        rows = [self.row(0, crop=point(x=.9), crop_source=point()),
                self.row(1, crop=point(x=.1), crop_source=point()),
                self.row(2, crop=point(x=.2), crop_source=point())]
        summary = audit.summarize_joint_rows(rows)
        self.assertEqual(summary["non_seed_frames"], 2)
        self.assertEqual(summary["arms"]["crop"]["selected_raw"], 2)
        jumps = summary["arms"]["crop"]["adjacent_supported_raw_jump_px"]
        self.assertEqual(jumps["count"], 1)
        self.assertAlmostEqual(jumps["max"], 8.)

    def test_jumps_do_not_bridge_missing_frame_or_group_gap(self):
        rows = [self.row(1, crop=point(x=.1), crop_source=point()), self.row(2),
                self.row(3, crop=point(x=.3), crop_source=point()),
                self.row(4, crop=point(x=.4), crop_source=point()),
                self.row(6, crop=point(x=.6), crop_source=point())]
        summary = audit.summarize_joint_rows(rows)["arms"]["crop"]
        self.assertEqual(summary["adjacent_supported_raw_jump_px"]["count"], 1)
        self.assertAlmostEqual(summary["adjacent_supported_raw_jump_px"]["max"], 8.)
        self.assertEqual(summary["longest_missing_span"], {"start_frame": 2, "end_frame": 2, "frames": 1})

    def test_low_gate_and_extrapolation_break_supported_gate_adjacency(self):
        rows = [self.row(1, crop=point(), crop_source=point()),
                self.row(2, crop=point(visibility=.4), crop_source=point()),
                self.row(3, crop=point(), crop_source=point(x=1.)),
                self.row(4, crop=point(), crop_source=point())]
        summary = audit.summarize_joint_rows(rows)["arms"]["crop"]
        self.assertEqual(summary["adjacent_supported_raw_jump_px"]["count"], 1)
        self.assertEqual(summary["adjacent_supported_gate_jump_px"]["count"], 0)
        self.assertEqual(summary["longest_supported_gate_unavailable_span"], {"start_frame": 2, "end_frame": 3, "frames": 2})

    def test_missing_spans_are_consecutive_and_do_not_bridge_group_gaps(self):
        rows = [self.row(i) for i in (1, 2, 4, 5, 6)]
        span = audit.summarize_joint_rows(rows)["arms"]["crop"]["longest_missing_span"]
        self.assertEqual(span, {"start_frame": 4, "end_frame": 6, "frames": 3})

    def test_original_major_labels_are_grouping_only(self):
        labels = audit.major_timeline({"labels": {"major_pose_failure_intervals": [
            {"start_frame": 1, "end_frame": 2, "status": "confirmed"}]}}, 4)
        self.assertEqual(labels, ["known_negative", "confirmed", "confirmed", "known_negative"])
        frames = [{"frame_index": i, "effectiveness_eligible": i != 0, "original_major_label": label,
                   "input_roi_valid": False, "selection": {a: {"status": "rejected"} for a in audit.ARMS},
                   "joints": {j: {**self.row(i, label=label), "joint": j} for j in audit.JOINT_NAMES}}
                  for i, label in enumerate(labels)]
        summary = audit.summarize_clip(frames)
        self.assertEqual(summary["non_seed_frames"], 3)
        self.assertEqual(summary["all_non_seed"]["input_roi_missing"], 3)
        self.assertEqual(summary["original_major_label_groups"]["confirmed"]["non_seed_frames"], 2)
        self.assertNotIn("warning_tp_fn_fp", summary)
        self.assertNotIn("accuracy", summary)


class SealTests(unittest.TestCase):
    def fixture(self, kind="new_measurement"):
        target = {**TARGET, "total_frames": 2}
        sources = {key: {"path": key, "sha256": key} for key in ("video", "metadata", "video_technical", "initialization")}
        refs = {key: {"path": key, "sha256": key} for key in ("tracking", "pose")}
        clip = {"target": target, "sources": sources, "kind": kind, "reused_tracking": refs["tracking"], "reused_pose": refs["pose"]}
        receipt = {"pitch_id": target["pitch_id"], "target": target, "kind": kind, **refs,
            "new_tracker_initialization_calls": 1 if kind == "new_measurement" else 0,
            "new_tracker_update_calls": 1 if kind == "new_measurement" else 0,
            "new_pose_inference_calls": 2 if kind == "new_measurement" else 0}
        common = {"status": "sealed_measurements_only", "target": target, "plan_sha256": "current" if kind == "new_measurement" else "old",
                  "warning_policy": None, "phase2_automatic_reliability": "NOT PASSED"}
        tracked = {**common, "producer_sources": sources, "initialization_frame_excluded_from_effectiveness": True,
            "post_initialization_frame_denominator": 1, "initialization_calls": 1, "native_update_calls": 1,
            "frames": [{"frame_index": i, "tracking_status": "initialized" if i == 0 else "native_success",
                "native_update_success": None if i == 0 else True, "native_rectangle_xywh": [1, 2, 20, 30],
                "usable_rectangle_xywh": [1, 2, 20, 30], "truncated": False,
                "native_rectangle_diagnostic": None, "warning_prediction": None, "subject_assignment": None} for i in range(2)]}
        pose = {**common, "producer_sources": {k: v for k, v in sources.items() if k != "initialization"} | {"tracked_roi": refs["tracking"]},
            "human_annotation_inputs": [], "inference_calls": 2,
            "frames": [{"frame_index": i, "inference_status": "measured"} for i in range(2)]}
        return clip, receipt, tracked, pose

    def test_new_clips_require_current_execution_hash_but_reused_seals_keep_old_hashes(self):
        for kind in ("new_measurement", "reuse_sealed"):
            parts = self.fixture(kind)
            audit.validate_sealed_clip(*parts, "current")
        clip, receipt, tracked, pose = self.fixture()
        pose["plan_sha256"] = "old"
        with self.assertRaises(ValueError):
            audit.validate_sealed_clip(clip, receipt, tracked, pose, "current")

    def test_reuse_calls_and_output_refs_cannot_be_relabelled(self):
        clip, receipt, tracked, pose = self.fixture("reuse_sealed")
        receipt["new_pose_inference_calls"] = 2
        with self.assertRaises(ValueError):
            audit.validate_sealed_clip(clip, receipt, tracked, pose, "current")
        receipt["new_pose_inference_calls"] = 0
        clip["reused_pose"] = {"path": "different", "sha256": "different"}
        with self.assertRaises(ValueError):
            audit.validate_sealed_clip(clip, receipt, tracked, pose, "current")

    def test_missing_tracker_roi_cannot_be_present_as_native_success(self):
        clip, receipt, tracked, pose = self.fixture()
        tracked["frames"][1]["usable_rectangle_xywh"] = None
        with self.assertRaises(ValueError):
            audit.validate_sealed_clip(clip, receipt, tracked, pose, "current")

    def test_four_new_clips_have_null_xy_accuracy_without_reading_manual_inputs(self):
        with patch.object(audit, "read", side_effect=AssertionError("No manual source may be opened")):
            for pitch_id in ("pitch_001", "pitch_002", "pitch_004", "pitch_005"):
                self.assertIsNone(audit.xy_accuracy(ROOT, {}, {}, ROOT / "unused", {**TARGET, "pitch_id": pitch_id}, {}))

    def test_reused_xy_summary_is_copied_exactly_without_rerunning_evaluation(self):
        source = {"pitch_id": "pitch_003"}
        manual = {"annotation_status": "reviewed", "source_video": source, "image_size": {"width": 80, "height": 60}}
        old = {"status": "complete_offline_xy_evaluation", "measurement_sha256": "sealedpose",
               "denominators": {"visible_xy": 1195}, "groups": {"saved": {"error": 1.234}},
               "per_joint": {"RIGHT_ELBOW": {"missing": 4}}, "frame_selection_counts": {"crop": {"selected": 90}}}
        sources = {"manual_xy": {"path": "manual.json"}, "reused_xy_evaluation": {"path": "old.json", "sha256": "bound"}}
        with patch.object(audit, "validate_manual_keypoints"), patch.object(audit, "read", side_effect=[manual, old]):
            result = audit.xy_accuracy(ROOT, sources, {"sha256": "sealedpose"}, ROOT / "video", {**TARGET, "pitch_id": "pitch_003"}, {"source_video": source})
        self.assertFalse(result["evaluation_rerun"])
        self.assertEqual(result["summary"], {k: old[k] for k in ("denominators", "groups", "per_joint", "frame_selection_counts")})

    def test_new_output_must_be_exclusive_and_inside_analysis_results(self):
        for target in (ROOT / "analysis_results", ROOT / "elsewhere"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                audit.evaluate(ROOT, "unused", "unused", target)


if __name__ == "__main__":
    unittest.main()
