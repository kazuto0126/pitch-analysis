"""Synthetic-only native-response evaluation and source-preservation tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import evaluate_rtmpose_response as evaluation
import rtmpose_response_features as features


def _point(visibility=.9):
    return {"x": .5, "y": .5, "z": 0., "visibility": visibility, "presence": .9}


def _refresh_frame(values, pid, index):
    clip, frame = values[0][pid], values[0][pid]["frames"][index]
    raw = {"RIGHT_ELBOW": frame["roles"]["throwing_elbow"]["original_point"],
           "RIGHT_WRIST": frame["roles"]["throwing_wrist"]["original_point"]}
    built = features.build_frame(raw, frame["native_simcc_x"], frame["native_simcc_y"], frame["geometry"],
        clip["width"], clip["height"], {"min_visibility": .5, "min_presence": .5})
    frame.update(built)
    for role in evaluation.ROLES:
        source = frame["roles"][role]
        baseline = next(row for row in values[3]["frame_joint_rows"] if
            row["pitch_id"] == pid and row["frame_index"] == index and row["role"] == role)
        baseline.update({"raw_finite": source["raw_finite"], "raw_gate_pass": source["raw_gate_pass"],
            "raw_xy_px": deepcopy(source["full_xy_px"])})
        warning = index != 0 and source["raw_finite"] and not source["raw_gate_pass"]
        baseline["screens"]["score_only"] = {"state": "seed_excluded" if index == 0 else (
            "insufficient_evidence" if not source["raw_finite"] else "warning" if warning else "no_warning"), "warning": warning}


def _resupply_predictions(values):
    measurements, predictions, truths = values[:3]
    for pid in evaluation.PITCH_IDS:
        prediction = {"pitch_id": pid, "fold_status": {}, "frames": [
            {"frame_index": frame["frame_index"], "roles": {}} for frame in measurements[pid]["frames"]]}
        for role in evaluation.ROLES:
            training = []
            for other in evaluation.PITCH_IDS:
                if other == pid:
                    continue
                labels = evaluation._timeline(truths[other], role, measurements[other]["total_frames"])
                training.extend(frame["roles"][role]["response_deficit"] for frame in measurements[other]["frames"] if
                    frame["frame_index"] != 0 and labels[frame["frame_index"]] == "reliable" and
                    frame["roles"][role]["response_deficit"] is not None)
            threshold = max(training) if training else None
            status = "calibrated" if training else "failed"
            prediction["fold_status"][role] = status
            for frame, source in zip(prediction["frames"], measurements[pid]["frames"], strict=True):
                index, deficit = source["frame_index"], source["roles"][role]["response_deficit"]
                warning = False
                if index == 0:
                    state, review = "seed_excluded", False
                elif status != "calibrated":
                    state, review = "calibration_failed", None
                elif deficit is None:
                    state, review = "insufficient_evidence", None
                else:
                    warning = deficit > threshold
                    state, review = ("warning" if warning else "no_warning"), warning
                frame["roles"][role] = {"frame_index": index, "response_deficit": deficit, "threshold": threshold,
                    "status": state, "review_required": review, "evaluated_warning": warning,
                    "effectiveness_eligible": index != 0}
        predictions[pid] = prediction


def fixture(total=7):
    measurements, predictions, truths, major = {}, {}, {}, {}
    baseline = {"frame_joint_rows": []}
    values = measurements, predictions, truths, baseline, major
    statuses = ["reliable", "unreliable", "reliable", "not_observable", "uncertain", "unreliable", "reliable"]
    geometry = features._geometry([19.2, 25.6, 153.6, 204.8], 192, 256)
    for number, pid in enumerate(evaluation.PITCH_IDS, 1):
        measurements[pid] = {"pitch_id": pid, "total_frames": total, "width": 192, "height": 256,
            "video_sha256": str(number) * 64, "frames": []}
        truths[pid] = {"annotation_status": "reviewed", "source_video": {"pitch_id": pid,
            "total_frames": total, "sha256": str(number) * 64},
            "labels": {role + "_reliability": [{"start_frame": i, "end_frame": i,
                "status": statuses[i] if i < 7 else "reliable"} for i in range(total)] for role in evaluation.ROLES}}
        major[pid] = {"pitch_id": pid, "status": "evaluated_development_evidence", "frames": []}
        for index in range(total):
            xs, ys = np.zeros((1, 17, 384), np.float32), np.zeros((1, 17, 512), np.float32)
            xs[0, :, 20], ys[0, :, 40] = 2., 3.
            deficit = 3 if index == 1 else 4 if index in (3, 4) else 1
            xs[0, :, 192], ys[0, :, 256] = 2 - deficit / 2, 3 - deficit / 2
            if index == 6:
                xs[0, (8, 10), 0] = np.nan
            frame = {"frame_index": index, "timestamp_ms": index * 17, "geometry": deepcopy(geometry),
                "native_simcc_x": xs, "native_simcc_y": ys, "roles": {
                    role: {"original_point": None if index == 5 else _point(.4 if index == 2 else .9)}
                    for role in evaluation.ROLES}}
            measurements[pid]["frames"].append(frame)
            major[pid]["frames"].append({"frame_index": index, "timestamp_ms": index * 17, "review_required": index == 1})
            for role in evaluation.ROLES:
                baseline["frame_joint_rows"].append({"pitch_id": pid, "role": role,
                    "landmark": "RIGHT_ELBOW" if role == "throwing_elbow" else "RIGHT_WRIST",
                    "frame_index": index, "timestamp_ms": index * 17, "effectiveness_eligible": index != 0,
                    "canonical_label": statuses[index] if index < 7 else "reliable",
                    "original_context": {"model_state": "observed", "use_disposition": {
                        "status": "reviewed_raw_observation", "restrictions": []}, "major_hold": False,
                        "major_pose_failure": [], "processed_usable": True, "processed_landmark": {"usable": True}},
                    "screens": {screen: {"state": "seed_excluded" if index == 0 else "no_warning", "warning": False}
                        for screen in evaluation.HISTORICAL_SCREENS}})
            _refresh_frame(values, pid, index)
    _resupply_predictions(values)
    return values


class RTMPoseResponseEvaluationTests(unittest.TestCase):
    def test_complete_unknown_and_insufficient_denominators(self):
        result = evaluation.evaluate_clips(*fixture())
        self.assertEqual((result["source_frames"], result["source_joint_rows"], result["non_seed_joint_rows"]), (35, 70, 60))
        role = result["aggregate"]["throwing_elbow"]
        self.assertEqual(role["canonical_label_counts"], {"reliable": 10, "unreliable": 10, "not_observable": 5, "uncertain": 5})
        screen = role["screens"]["rtmpose_response"]
        self.assertEqual({k: screen[k] for k in ("tp", "fn", "fp", "tn")}, {"tp": 5, "fn": 5, "fp": 0, "tn": 10})
        self.assertEqual(screen["unknown_label_warning_counts"], {"not_observable": 5, "uncertain": 5})
        self.assertEqual(screen["abstain_frames"], 10)

    def test_original_gate_support_and_major_union_increment(self):
        report = evaluation.evaluate_clips(*fixture())["aggregate"]["throwing_elbow"]
        kept = report["screens"]["rtmpose_response"]["retention_on_original_raw_gate_pass"]
        self.assertEqual((kept["original_support"], kept["remaining_without_this_hint"], kept["reliable_remaining"]), (20, 5, 5))
        self.assertEqual(kept["newly_caught_gate_pass_wrong_points"], 5)
        overlap = report["existing_major_hint_overlap"]
        self.assertEqual((overlap["overlap_frames"], overlap["new_hint_union_increment"], overlap["union_frames"]), (5, 10, 15))
        self.assertEqual(overlap["new_gate_pass_bad_hint_beyond_major"], 0)

    def test_canonical_gt_old_label_mismatch_and_gaps_rejected(self):
        values = fixture()
        values[2]["pitch_003"]["labels"]["throwing_elbow_reliability"][1]["status"] = "reliable"
        with self.assertRaisesRegex(ValueError, "independently expanded canonical"):
            evaluation.evaluate_clips(*values)
        values = fixture()
        values[2]["pitch_003"]["labels"]["throwing_elbow_reliability"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete canonical"):
            evaluation.evaluate_clips(*values)

    def test_sealed_four_training_maximum_and_strict_tie_checked(self):
        values = fixture()
        result = evaluation.evaluate_clips(*values)
        row = next(row for row in result["frame_joint_rows"] if row["pitch_id"] == "pitch_001" and
            row["frame_index"] == 2 and row["role"] == "throwing_elbow")
        hint = row["screens"]["rtmpose_response"]
        self.assertEqual(hint["response_deficit"], hint["threshold"])
        self.assertFalse(hint["review_required"])
        values[1]["pitch_001"]["frames"][1]["roles"]["throwing_elbow"]["threshold"] = .5
        with self.assertRaisesRegex(ValueError, "training maximum"):
            evaluation.evaluate_clips(*values)

    def test_deficit_is_recomputed_from_raw_native_vectors(self):
        values = fixture()
        values[0]["pitch_001"]["frames"][1]["roles"]["throwing_elbow"]["response_deficit"] += .5
        with self.assertRaisesRegex(ValueError, "raw SimCC response deficit"):
            evaluation.evaluate_clips(*values)

    def test_original_raw_gate_and_source_xy_cannot_be_changed(self):
        values = fixture()
        values[0]["pitch_001"]["frames"][2]["roles"]["throwing_elbow"]["raw_gate_pass"] = True
        with self.assertRaisesRegex(ValueError, "0.5 raw gate"):
            evaluation.evaluate_clips(*values)
        values = fixture()
        values[0]["pitch_001"]["frames"][1]["roles"]["throwing_elbow"]["full_xy_px"][0] += 1
        with self.assertRaisesRegex(ValueError, "Full source coordinate"):
            evaluation.evaluate_clips(*values)

    def test_native17_score_only_contract_and_axis_shapes(self):
        values = fixture()
        values[0]["pitch_001"]["frames"][1]["native_keypoints"][8]["visibility"] = .9
        with self.assertRaisesRegex(ValueError, "score-only contract"):
            evaluation.evaluate_clips(*values)
        values = fixture()
        values[0]["pitch_001"]["frames"][1]["native_simcc_x"] = np.zeros((1, 33, 384), np.float32)
        with self.assertRaisesRegex(ValueError, "COCO17 axis shape"):
            evaluation.evaluate_clips(*values)

    def test_nonpositive_native_score_keeps_primary_response(self):
        values = fixture()
        frame = values[0]["pitch_001"]["frames"][1]
        frame["native_simcc_x"][0, 8, :] = -3
        frame["native_simcc_y"][0, 8, :] = -4
        frame["native_simcc_x"][0, 8, 20] = -1
        frame["native_simcc_y"][0, 8, 40] = -2
        _refresh_frame(values, "pitch_001", 1)
        _resupply_predictions(values)
        result = evaluation.evaluate_clips(*values)
        row = next(row for row in result["frame_joint_rows"] if row["pitch_id"] == "pitch_001" and
            row["frame_index"] == 1 and row["role"] == "throwing_elbow")
        self.assertEqual(row["native_score"], -2)
        self.assertFalse(row["native_decoded_finite"])
        self.assertEqual(row["response_deficit"], 4)
        self.assertTrue(row["screens"]["rtmpose_response"]["evaluated_warning"])

    def test_outside_bins_not_clipped_or_removed_from_wrong_denominator(self):
        values = fixture()
        frame = values[0]["pitch_001"]["frames"][1]
        frame["roles"]["throwing_elbow"]["original_point"]["x"] = 2
        _refresh_frame(values, "pitch_001", 1)
        _resupply_predictions(values)
        result = evaluation.evaluate_clips(*values)
        report = result["aggregate"]["throwing_elbow"]
        self.assertEqual(report["full_point_outside_simcc_bins_frames"], 1)
        self.assertEqual(report["screens"]["rtmpose_response"]["fn"], 6)
        self.assertEqual(report["binary_label_frames"], 20)

    def test_nonfinite_vector_only_affects_own_joint(self):
        values = fixture()
        values[0]["pitch_001"]["frames"][1]["native_simcc_x"][0, 8, 0] = np.nan
        _refresh_frame(values, "pitch_001", 1)
        _resupply_predictions(values)
        result = evaluation.evaluate_clips(*values)
        self.assertEqual(result["aggregate"]["throwing_elbow"]["screens"]["rtmpose_response"]["tp"], 4)
        self.assertEqual(result["aggregate"]["throwing_wrist"]["screens"]["rtmpose_response"]["tp"], 5)

    def test_paired_manual_xy_only_same_frames_and_hidden_xy_stays_null(self):
        values = fixture()
        manual = {"source_video": {"pitch_id": "pitch_003", "total_frames": 7, "sha256": "3" * 64},
            "coordinate_system": "original_image_pixels_xy", "image_size": {"width": 192, "height": 256},
            "frames": [{"frame_index": i, "joints": [{"name": name, "status": "visible", "x_px": 96, "y_px": 128}
                for name in ("RIGHT_ELBOW", "RIGHT_WRIST")]} for i in range(7)]}
        result = evaluation.evaluate_clips(*values, manual_xy=manual)
        precise = result["clips"][2]["precise_accuracy"]
        self.assertFalse(precise["rtmpose_quality_labelled"])
        role = precise["roles"]["throwing_elbow"]
        self.assertEqual((role["visible_reference_frames"], role["original_full_missing_visible_frames"],
            role["rtmpose_decoded_missing_visible_frames"]), (6, 1, 1))
        self.assertEqual(role["same_frame_same_joint_paired_errors"]["original_full"]["n"], 4)
        self.assertEqual(role["same_frame_same_joint_paired_errors"]["rtmpose"]["n"], 4)
        self.assertEqual(role["same_frame_same_joint_paired_errors"]["original_full"]["mean_px"], 0)
        self.assertTrue(all(result["clips"][i]["precise_accuracy"] is None for i in (0, 1, 3, 4)))
        manual["frames"][3]["joints"][0]["status"] = "not_observable"
        with self.assertRaisesRegex(ValueError, "cannot become visible truth"):
            evaluation.evaluate_clips(*values, manual_xy=manual)

    def test_frame104_hold_and_existing_visibility_audit_are_retained(self):
        values = fixture(total=105)
        old = next(row for row in values[3]["frame_joint_rows"] if row["pitch_id"] == "pitch_003" and
            row["frame_index"] == 104 and row["role"] == "throwing_elbow")
        old["original_context"].update({"major_hold": True, "use_disposition": {
            "status": "hold_frame_review", "restrictions": ["human_confirmed_major_pose_failure"]}})
        visibility = {"conflicts": [97, 98, 99, 100, 101, 102, 103, 104], "labels_unchanged": True}
        result = evaluation.evaluate_clips(*values, visibility_audit=visibility)
        self.assertEqual(result["visibility_audit_existing_sources_only"], visibility)
        held = result["held_out_pitch_003"]["known_major_miss_frame_104_context"]
        self.assertEqual(held[0]["original_context"], old["original_context"])
        self.assertEqual(len(held), 2)
        self.assertFalse(held[0]["screens"]["rtmpose_response"]["evaluated_warning"])
        self.assertEqual(result["source_joint_rows"], 1050)

    def test_original_history_and_inputs_immutable_json_output_no_arrays(self):
        values = fixture()
        old = values[3]["frame_joint_rows"][2]
        old["screens"]["classifier"] = {"state": "warning", "warning": True, "probability": .9}
        arrays = [(frame["native_simcc_x"].copy(), frame["native_simcc_y"].copy()) for clip in values[0].values() for frame in clip["frames"]]
        result = evaluation.evaluate_clips(*values)
        row = next(row for row in result["frame_joint_rows"] if row["pitch_id"] == old["pitch_id"] and
            row["frame_index"] == old["frame_index"] and row["role"] == old["role"])
        self.assertEqual(row["screens"]["classifier"], old["screens"]["classifier"])
        row["original_context"]["use_disposition"]["restrictions"].append("changed")
        self.assertEqual(old["original_context"]["use_disposition"]["restrictions"], [])
        for (xs, ys), frame in zip(arrays, (frame for clip in values[0].values() for frame in clip["frames"]), strict=True):
            np.testing.assert_array_equal(xs, frame["native_simcc_x"])
            np.testing.assert_array_equal(ys, frame["native_simcc_y"])
        json.dumps(result, allow_nan=False)
        self.assertFalse(result["decision"]["automatically_passes_phase2"])

    def test_failed_folds_keep_all_binary_rows_without_warnings(self):
        values = fixture()
        for pid in evaluation.PITCH_IDS:
            for index in (2, 6):
                frame = values[0][pid]["frames"][index]
                frame["native_simcc_x"][0, (8, 10), 0] = np.nan
                _refresh_frame(values, pid, index)
        _resupply_predictions(values)
        result = evaluation.evaluate_clips(*values)
        for role in evaluation.ROLES:
            report = result["aggregate"][role]
            self.assertEqual(report["binary_label_frames"], 20)
            screen = report["screens"]["rtmpose_response"]
            self.assertEqual((screen["tp"], screen["fn"], screen["fp"], screen["tn"]), (0, 10, 0, 10))
            self.assertEqual(screen["abstain_frames"], 30)


if __name__ == "__main__":
    unittest.main()
