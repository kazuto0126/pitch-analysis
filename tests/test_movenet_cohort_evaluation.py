"""Synthetic native-contract, association and honest-denominator regressions."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import evaluate_movenet_cohort as audit
    from check_movenet_compatibility import geometry_from_mask, native_slots, to_target_yx
finally:
    sys.path.pop(0)


TARGET = {"pitch_id": "synthetic", "total_frames": 3, "width": 80, "height": 60}
CONFIG = {"min_visibility": .5, "min_presence": .5}


def point(x=.25, y=1 / 3, visibility=.9, presence=.9):
    return {"x": x, "y": y, "z": 0., "visibility": visibility, "presence": presence}


def native_frame(index=1):
    mask = np.zeros((256, 256), np.float32)
    mask[32:224] = 1
    geometry = geometry_from_mask(mask, TARGET["height"], TARGET["width"])
    raw = np.zeros((1, 6, 56), np.float32)
    for slot in range(6):
        xy = (20., 20.) if slot == 0 else (70., 55.)
        raw[0, slot, :51] = np.tile([*to_target_yx(*xy, geometry), 0.], 17)
        box = (10., 10., 60., 50.) if slot == 0 else (65., 50., 79., 59.)
        raw[0, slot, 51:55] = [*to_target_yx(box[0], box[1], geometry),
                                      *to_target_yx(box[2], box[3], geometry)]
        raw[0, slot, 55] = slot / 10
    pixels = np.arange(60 * 80 * 3, dtype=np.uint8).reshape(60, 80, 3)
    rgb = cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)
    ms = index * 40.
    frame = {"frame_index": index, "native_timestamp_ms": ms, "timestamp_ms": round(ms),
        "frame_time_sec": index / 25., "decoded_bgr_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
        "decoded_rgb_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(), "input_geometry": geometry,
        "native_output": raw.tolist(), "slots": native_slots(raw, geometry), "inference_seconds": .01}
    return frame, pixels


def set_xy(frame, slot, joint, xy):
    raw = np.asarray(frame["native_output"], dtype=np.float32)
    raw[0, slot, joint * 3:joint * 3 + 2] = to_target_yx(*xy, frame["input_geometry"])
    frame["native_output"] = raw.tolist()
    frame["slots"] = native_slots(raw, frame["input_geometry"])


def set_box(frame, slot, box):
    raw = np.asarray(frame["native_output"], dtype=np.float32)
    raw[0, slot, 51:55] = [*to_target_yx(box[0], box[1], frame["input_geometry"]),
                                   *to_target_yx(box[2], box[3], frame["input_geometry"])]
    frame["native_output"] = raw.tolist()
    frame["slots"] = native_slots(raw, frame["input_geometry"])


def result_frame(index=1, *, rectangle=(10., 10., 50., 40.), video=None, image=None):
    frame, _ = native_frame(index)
    slots = audit.derive_slots(frame, TARGET)
    association = audit.geometric_association(slots, rectangle, TARGET["width"], TARGET["height"])
    arms = {"video": {name: point() for name in audit.JOINTS} if video is None else video,
            "image": {name: point() for name in audit.JOINTS} if image is None else image}
    return {"frame_index": index, "native_timestamp_ms": index * 40., "effectiveness_eligible": index != 0,
        "original_major_label": "confirmed" if index == 1 else "known_negative", "slots": slots,
        "association": association, "joints": audit.joint_diagnostics(slots, association, arms, TARGET, CONFIG)}


class NativeReplayTests(unittest.TestCase):
    def test_all_six_zero_joint_score_slots_are_preserved_without_a_gate(self):
        frame, _ = native_frame()
        slots = audit.derive_slots(frame, TARGET)
        self.assertEqual([slot["slot_index"] for slot in slots], list(range(6)))
        self.assertTrue(all(len(slot["native_yx_score"]) == 17 for slot in slots))
        self.assertTrue(all(point[2] == 0 for slot in slots for point in slot["native_yx_score"]))
        self.assertEqual(frame["slots"][0]["subject_identity"], None)
        self.assertNotIn("visibility", slots[0])

    def test_mapping_is_unclipped_and_source_xy_tampering_is_rejected(self):
        frame, _ = native_frame()
        set_xy(frame, 5, 16, (-10., 70.))
        slots = audit.derive_slots(frame, TARGET)
        self.assertLess(slots[5]["source_xy"][16][0], 0)
        self.assertGreater(slots[5]["source_xy"][16][1], TARGET["height"])
        frame["slots"][5]["source_xy"][16][0] = 0.
        with self.assertRaisesRegex(ValueError, "do not reproduce"):
            audit.derive_slots(frame, TARGET)

    def test_native_score_box_and_semantic_tampering_is_rejected(self):
        frame, _ = native_frame()
        for mutate in (lambda value: value["slots"][0]["native_yx_score"][0].__setitem__(2, .8),
                       lambda value: value["slots"][0]["native_box_ymin_xmin_ymax_xmax_score"].__setitem__(4, .9),
                       lambda value: value["slots"][0].update(subject_identity="pitcher"),
                       lambda value: value["slots"].pop()):
            changed = copy.deepcopy(frame)
            mutate(changed)
            with self.assertRaises(ValueError):
                audit.derive_slots(changed, TARGET)

    def test_wrong_shape_nonfinite_and_out_of_range_scores_fail_closed(self):
        frame, _ = native_frame()
        for value in (-.1, 1.1, float("nan")):
            changed = copy.deepcopy(frame)
            changed["native_output"][0][0][2] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.derive_slots(changed, TARGET)
        frame["native_output"][0].pop()
        with self.assertRaises(ValueError):
            audit.derive_slots(frame, TARGET)

    def test_recorded_scale_and_padding_cannot_change(self):
        frame, _ = native_frame()
        for key, value in (("scale_x", 2.), ("pad_top", 31), ("source_width", 81), ("target_height", 128)):
            changed = copy.deepcopy(frame)
            changed["input_geometry"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.derive_slots(changed, TARGET)

    def test_independent_bgr_rgb_pts_and_timeline_bindings_are_checked(self):
        frame, pixels = native_frame()
        reference = {key: frame[key] for key in ("frame_index", "native_timestamp_ms", "decoded_bgr_sha256")}
        audit.verify_frame(frame, reference, reference, pixels, 40., 40., TARGET)
        for key, value in (("decoded_bgr_sha256", "wrong"), ("decoded_rgb_sha256", "wrong"),
                           ("native_timestamp_ms", 41.), ("timestamp_ms", 41), ("frame_index", 2)):
            changed = copy.deepcopy(frame)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.verify_frame(changed, reference, reference, pixels, 40., 40., TARGET)
        with self.assertRaises(ValueError):
            audit.verify_frame(frame, reference, reference, pixels, 40., 40.01, TARGET)


class AssociationTests(unittest.TestCase):
    def associate(self, frame, rectangle=(10., 10., 50., 40.)):
        return audit.geometric_association(audit.derive_slots(frame, TARGET), rectangle, 80, 60)

    def test_unique_geometry_with_zero_scores_is_descriptive_and_unverified(self):
        frame, _ = native_frame()
        result = self.associate(frame)
        self.assertEqual(result["status"], "unique_geometric_candidate")
        self.assertEqual(result["candidate_slot_indices"], [0])
        self.assertEqual(result["descriptive_slot_index"], 0)
        self.assertEqual(len(result["competitors"]), 6)
        self.assertFalse(result["subject_alignment_verified"])
        self.assertFalse(result["ground_truth_used"])
        self.assertIsNone(result["score_cutoff"])

    def test_different_iou_and_instance_scores_never_resolve_two_candidates(self):
        frame, _ = native_frame()
        for name in audit.TORSO:
            set_xy(frame, 1, audit.JOINTS.index(name), (30., 30.))
        set_box(frame, 1, (10., 10., 60., 50.))
        set_box(frame, 0, (15., 15., 55., 45.))
        result = self.associate(frame)
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["candidate_slot_indices"], [0, 1])
        self.assertIsNone(result["descriptive_slot_index"])
        self.assertGreater(result["top_minus_runner_up_box_iou"], 0)

    def test_highest_iou_is_not_a_candidate_when_one_torso_point_is_outside(self):
        frame, _ = native_frame()
        set_box(frame, 1, (10., 10., 60., 50.))
        set_box(frame, 0, (15., 15., 55., 45.))
        result = self.associate(frame)
        self.assertEqual(result["box_iou_ranking_slot_indices"][0], 1)
        self.assertEqual(result["descriptive_slot_index"], 0)
        self.assertFalse(result["competitors"][1]["all_four_torso_inside_csrt"])

    def test_all_four_torso_points_and_positive_box_are_required(self):
        frame, _ = native_frame()
        for name in audit.TORSO:
            changed = copy.deepcopy(frame)
            set_xy(changed, 0, audit.JOINTS.index(name), (70., 55.))
            with self.subTest(joint=name):
                self.assertEqual(self.associate(changed)["status"], "none")
        for box in ((20., 20., 20., 40.), (30., 20., 20., 40.), (70., 50., 79., 59.)):
            changed = copy.deepcopy(frame)
            set_box(changed, 0, box)
            with self.subTest(box=box):
                self.assertEqual(self.associate(changed)["status"], "none")

    def test_half_open_source_and_csrt_boundaries_are_not_clamped(self):
        frame, _ = native_frame()
        for xy, rectangle in (((60., 20.), (10., 10., 50., 40.)),
                              ((80., 20.), (0., 0., 100., 100.)),
                              ((20., 60.), (0., 0., 100., 100.))):
            changed = copy.deepcopy(frame)
            set_xy(changed, 0, audit.JOINTS.index("LEFT_HIP"), xy)
            result = self.associate(changed, rectangle)
            self.assertNotIn(0, result["candidate_slot_indices"])
            self.assertFalse(result["competitors"][0]["geometric_candidate"])

    def test_missing_csrt_preserves_six_competitors_without_fallback(self):
        frame, _ = native_frame()
        result = self.associate(frame, None)
        self.assertEqual(result["status"], "none")
        self.assertEqual(result["reason"], "missing_sealed_csrt")
        self.assertEqual(len(result["competitors"]), 6)
        self.assertEqual(result["box_iou_ranking_slot_indices"], [])
        self.assertIsNone(result["descriptive_slot_index"])


class HonestDenominatorTests(unittest.TestCase):
    def test_native_zero_score_is_finite_and_not_converted_to_mediapipe_gate(self):
        frame = result_frame()
        joint = frame["joints"]["RIGHT_ELBOW"]
        self.assertEqual(len(joint["native_slots"]), 6)
        self.assertTrue(joint["descriptive_association"]["finite"])
        self.assertEqual(joint["descriptive_association"]["native_score"], 0.)
        self.assertIsNone(joint["movenet_gate"])
        self.assertNotIn("visibility", joint["descriptive_association"])

    def test_existing_mediapipe_gate_only_filters_its_own_difference_subset(self):
        frame = result_frame(video={"RIGHT_ELBOW": point(visibility=.49)}, image={})
        joint = frame["joints"]["RIGHT_ELBOW"]
        self.assertIsNotNone(joint["descriptive_association"]["prediction_differences"]["video"]["both_finite_distance_px"])
        self.assertIsNone(joint["descriptive_association"]["prediction_differences"]["video"]["mediapipe_existing_gate_distance_px"])
        self.assertTrue(joint["mediapipe"]["image"]["missing"])
        self.assertIsNone(joint["mediapipe"]["image"]["visibility"])

    def test_seed_and_no_association_remain_explicit_in_effectiveness_denominator(self):
        frames = [result_frame(0), result_frame(1), result_frame(2, rectangle=None)]
        summary = audit.summarize_frames(frames)
        self.assertEqual(summary["non_seed_frames"], 2)
        self.assertEqual(summary["association_status_counts"], {"unique_geometric_candidate": 1, "none": 1})
        joint = summary["per_joint"]["RIGHT_ELBOW"]
        self.assertEqual(joint["all_native_slot_point_denominator"], 12)
        self.assertEqual(joint["descriptive_association_points"], 1)
        self.assertEqual(joint["no_descriptive_association"], 1)
        self.assertEqual(joint["all_native_scores"]["count"], 12)

    def test_jumps_do_not_include_seed_group_gaps_or_changed_descriptor_slot(self):
        frames = [result_frame(index) for index in (0, 1, 2, 4)]
        frames[2]["association"]["descriptive_slot_index"] = 1
        summary = audit.summarize_frames(frames)["per_joint"]["RIGHT_ELBOW"]
        self.assertEqual(summary["native_array_slot_jump_px"]["0"]["count"], 1)
        self.assertEqual(summary["adjacent_same_array_slot_descriptive_jump_px"]["count"], 0)

    def manual(self, frames):
        return {"frames": [{"frame_index": frame["frame_index"], "timestamp_ms": frame["native_timestamp_ms"],
            "joints": [{"name": name, "status": "visible", "x_px": 20., "y_px": 20.} for name in audit.JOINT_NAMES]}
            for frame in frames]}

    def test_hidden_uncertain_points_are_never_xy_truth_and_seed_is_excluded(self):
        frames = [result_frame(index) for index in range(3)]
        manual = self.manual(frames)
        for index, status in ((0, "not_observable"), (1, "uncertain")):
            manual["frames"][1]["joints"][index].update(status=status, x_px=None, y_px=None)
        rows = audit.coordinate_rows(manual, frames)
        summary = audit.coordinate_summary(rows)
        self.assertEqual(summary["source_visible_reference_denominator"], 34)
        self.assertEqual(summary["visible_reference_denominator"], 22)
        self.assertEqual(summary["hidden_coordinates_evaluated"], 0)
        hidden = [row for row in rows if row["human_status"] != "visible"]
        self.assertTrue(all(row["movenet_descriptive_error_px"] is None and row["video_error_px"] is None for row in hidden))

    def test_common_visible_pair_sets_report_coverage_and_mediapipe_gate_separately(self):
        frames = [result_frame(0), result_frame(1, video={}), result_frame(2, rectangle=None)]
        rows = audit.coordinate_rows(self.manual(frames), frames)
        summary = audit.coordinate_summary(rows)
        self.assertEqual(summary["visible_reference_denominator"], 24)
        self.assertEqual(summary["visible_without_descriptive_association"], 12)
        self.assertEqual(summary["mediapipe"]["video"]["visible_missing_or_nonfinite"], 12)
        self.assertEqual(summary["common_finite_pairs"]["video"]["all_finite"]["count"], 0)
        self.assertEqual(summary["common_finite_pairs"]["image"]["all_finite"]["count"], 12)
        self.assertEqual(summary["common_finite_pairs"]["image"]["mediapipe_existing_gate_only"]["count"], 12)

    def test_gt_does_not_reselect_a_closer_competing_slot(self):
        frames = [result_frame(1)]
        manual = self.manual(frames)
        for joint in manual["frames"][0]["joints"]:
            joint.update(x_px=70., y_px=55.)
        rows = audit.coordinate_rows(manual, frames)
        self.assertTrue(all(row["descriptive_slot_index"] == 0 for row in rows))
        self.assertTrue(all(row["movenet_descriptive_error_px"] > 50 for row in rows))
        self.assertNotIn("best_slot", audit.coordinate_summary(rows))

    def test_original_major_labels_only_group_original_predictions(self):
        labels = audit.major_timeline({"labels": {"major_pose_failure_intervals": [
            {"start_frame": 1, "end_frame": 1, "status": "confirmed"}]}}, 3)
        self.assertEqual(labels, ["known_negative", "confirmed", "known_negative"])
        summary = audit.summarize_frames([result_frame(1)])
        self.assertNotIn("accuracy", summary)
        self.assertNotIn("warning_tp_fn_fp", summary)


class ExportBindingTests(unittest.TestCase):
    def fixture(self, root):
        frames, pixels = zip(*(native_frame(index) for index in range(3)))
        archive = root / "frames.npz"
        np.savez_compressed(archive, rgb=np.asarray([cv2.cvtColor(value, cv2.COLOR_BGR2RGB) for value in pixels]))
        sources = {key: {"path": key, "sha256": key} for key in ("video", "metadata", "video_technical")}
        sources["frame_archive"] = {"path": "frames.npz", "sha256": audit.sha(archive)}
        fields = ("frame_index", "native_timestamp_ms", "timestamp_ms", "frame_time_sec", "decoded_bgr_sha256", "decoded_rgb_sha256")
        receipt = {"status": "sealed_full_frame_rgb_inputs", "target": TARGET,
            "sources": {key: sources[key] for key in ("video", "metadata", "video_technical")},
            "source_video": sources["video"], "archive": sources["frame_archive"], "frame_key": "rgb",
            "human_annotation_inputs": [], "pose_inference_calls": 0, "fps_float": 25.,
            "frames": [{key: frame[key] for key in fields} for frame in frames]}
        path = root / "export.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        sources["export_receipt"] = {"path": "export.json", "sha256": audit.sha(path)}
        return {"target": TARGET, "sources": sources}, {"frames": list(frames)}, receipt

    def test_full_ordered_rgb_archive_is_bound_without_loading_tensorflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            clip, data, receipt = self.fixture(root)
            checked, rgb = audit.load_export(root, clip, data, {"fps": 25.})
            self.assertEqual(checked, receipt)
            self.assertEqual(rgb.shape, (3, 60, 80, 3))
            self.assertEqual(rgb.dtype, np.uint8)

    def test_retiming_frame_omission_gt_inputs_and_archive_hash_tampering_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            clip, data, receipt = self.fixture(root)
            for mutate in (lambda value: value["frames"][1].update(frame_time_sec=.041),
                           lambda value: value["frames"].pop(),
                           lambda value: value.update(human_annotation_inputs=["manual.json"]),
                           lambda value: value.update(pose_inference_calls=1)):
                changed = copy.deepcopy(receipt)
                mutate(changed)
                path = root / "export.json"
                path.write_text(json.dumps(changed), encoding="utf-8")
                clip["sources"]["export_receipt"]["sha256"] = audit.sha(path)
                with self.assertRaises(ValueError):
                    audit.load_export(root, clip, data, {"fps": 25.})
            (root / "export.json").write_text(json.dumps(receipt), encoding="utf-8")
            clip["sources"]["export_receipt"]["sha256"] = audit.sha(root / "export.json")
            clip["sources"]["frame_archive"]["sha256"] = "wrong"
            with self.assertRaises(ValueError):
                audit.load_export(root, clip, data, {"fps": 25.})

    def test_new_output_is_exclusive_and_inside_analysis_results(self):
        for output in (ROOT / "analysis_results", ROOT / "elsewhere"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                audit.evaluate(ROOT, ROOT / "unused", ROOT / "unused", output)


if __name__ == "__main__":
    unittest.main()
