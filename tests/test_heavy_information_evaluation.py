"""Synthetic tests of Heavy evaluation, preserving labels and denominators."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("heavy_information_evaluation", SCRIPTS / "evaluate_heavy_information.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)
from heavy_information_policy import apply, calibrate


def _point(x=.1, y=.1, visibility=.9, presence=.9):
    return {"x": x, "y": y, "z": 0, "visibility": visibility, "presence": presence}


def _resupply_predictions(values):
    measurements, predictions, ground_truths, _, _ = values
    for pid in evaluation.PITCH_IDS:
        prediction = {"pitch_id": pid, "fold_status": {}, "frames": [
            {"frame_index": frame["frame_index"], "roles": {}} for frame in measurements[pid]["frames"]]}
        for role in evaluation.ROLES:
            training = []
            for other in evaluation.PITCH_IDS:
                if other == pid:
                    continue
                total = measurements[other]["total_frames"]
                labels = evaluation._timeline(ground_truths[other], role, total)
                training.append({"pitch_id": other, "rows": [{"frame_index": frame["frame_index"],
                    "canonical_label": labels[frame["frame_index"]],
                    "distance_diagonal": frame["roles"][role]["distance_diagonal"]}
                    for frame in measurements[other]["frames"]]})
            calibration = calibrate(training, pid, role)
            prediction["fold_status"][role] = calibration["status"]
            query = [{"frame_index": frame["frame_index"], "distance_diagonal": frame["roles"][role]["distance_diagonal"]}
                for frame in measurements[pid]["frames"]]
            for frame, result in zip(prediction["frames"], apply(query, calibration), strict=True):
                frame["roles"][role] = result
        predictions[pid] = prediction


def _refresh_role(values, pid, index, role):
    clip = values[0][pid]
    source = clip["frames"][index]["roles"][role]
    raw_finite, raw_xy, raw_gate = evaluation._point(source["original_point"], clip["width"], clip["height"])
    heavy_finite, heavy_xy, _ = evaluation._point(source["heavy_point"], clip["width"], clip["height"])
    source["raw_finite"], source["raw_gate_pass"] = raw_finite, raw_gate
    measurable = raw_finite and heavy_finite
    source["distance_px"] = math.hypot(raw_xy[0] - heavy_xy[0], raw_xy[1] - heavy_xy[1]) if measurable else None
    source["distance_diagonal"] = source["distance_px"] / math.hypot(clip["width"], clip["height"]) if measurable else None
    source["evidence_status"] = "measured" if measurable else "insufficient_evidence"
    baseline = next(row for row in values[3]["frame_joint_rows"] if
        row["pitch_id"] == pid and row["frame_index"] == index and row["role"] == role)
    baseline["raw_finite"], baseline["raw_gate_pass"], baseline["raw_xy_px"] = raw_finite, raw_gate, raw_xy
    warning = index != 0 and raw_finite and not raw_gate
    baseline["screens"]["score_only"] = {"state": "seed_excluded" if index == 0 else (
        "insufficient_evidence" if not raw_finite else "warning" if warning else "no_warning"), "warning": warning}


def fixture(total=7):
    measurements, predictions, truths, major = {}, {}, {}, {}
    baseline = {"frame_joint_rows": []}
    values = measurements, predictions, truths, baseline, major
    labels = ["reliable", "unreliable", "reliable", "not_observable", "uncertain", "unreliable", "reliable"]
    for number, pid in enumerate(evaluation.PITCH_IDS, 1):
        measurements[pid] = {"pitch_id": pid, "total_frames": total, "width": 100, "height": 200,
            "video_sha256": str(number) * 64, "frames": []}
        truths[pid] = {"annotation_status": "reviewed", "source_video": {"pitch_id": pid,
            "total_frames": total, "sha256": str(number) * 64},
            "labels": {role + "_reliability": [{"start_frame": i, "end_frame": i,
                "status": labels[i] if i < 7 else "reliable"} for i in range(total)] for role in evaluation.ROLES}}
        major[pid] = {"pitch_id": pid, "status": "evaluated_development_evidence", "frames": []}
        for index in range(total):
            candidates = [[_point() for _ in range(33)]] if index != 6 else []
            selection = {"index": 0 if candidates else None, "status": "selected" if candidates else "rejected",
                "reason": "synthetic", "candidate_count": len(candidates), "score": .7, "mean_confidence": .9}
            frame = {"frame_index": index, "timestamp_ms": index * 17, "heavy_candidates": candidates,
                "heavy_selection": selection, "roles": {}}
            measurements[pid]["frames"].append(frame)
            major[pid]["frames"].append({"frame_index": index, "timestamp_ms": index * 17, "review_required": index == 1})
            for role in evaluation.ROLES:
                landmark = "RIGHT_ELBOW" if role == "throwing_elbow" else "RIGHT_WRIST"
                point_index = evaluation.LANDMARK_INDEX[landmark]
                offset = .3 if index in (1, 3, 4) else .05
                if candidates:
                    candidates[0][point_index] = _point(x=.1 + offset)
                raw = None if index == 5 else _point(visibility=.4 if index == 2 else .9)
                frame["roles"][role] = {"original_point": raw,
                    "heavy_point": deepcopy(candidates[0][point_index]) if candidates else None}
                baseline["frame_joint_rows"].append({"pitch_id": pid, "role": role, "landmark": landmark,
                    "frame_index": index, "timestamp_ms": index * 17, "effectiveness_eligible": index != 0,
                    "canonical_label": labels[index] if index < 7 else "reliable",
                    "raw_finite": raw is not None, "raw_gate_pass": raw is not None and index != 2,
                    "raw_xy_px": [10, 20] if raw is not None else None,
                    "original_context": {"model_state": "observed" if index not in (2, 5) else "missing",
                        "use_disposition": {"status": "reviewed_raw_observation", "restrictions": []},
                        "major_hold": False, "major_pose_failure": [],
                        "processed_usable": raw is not None, "processed_landmark": {"usable": raw is not None}},
                    "screens": {screen: {"state": "seed_excluded" if index == 0 else "no_warning", "warning": False}
                        for screen in evaluation.HISTORICAL_SCREENS}})
                _refresh_role(values, pid, index, role)
    _resupply_predictions(values)
    return values


class HeavyInformationEvaluationTests(unittest.TestCase):
    def test_unknown_and_missing_keep_complete_denominators(self):
        result = evaluation.evaluate_clips(*fixture())
        self.assertEqual((result["source_frames"], result["source_joint_rows"], result["non_seed_joint_rows"]), (35, 70, 60))
        report = result["aggregate"]["throwing_elbow"]
        self.assertEqual(report["canonical_label_counts"], {"reliable": 10, "unreliable": 10, "not_observable": 5, "uncertain": 5})
        self.assertEqual(report["raw_missing_frames"], 5)
        heavy = report["screens"]["heavy_disagreement"]
        self.assertEqual({key: heavy[key] for key in ("tp", "fn", "fp", "tn")}, {"tp": 5, "fn": 5, "fp": 0, "tn": 10})
        self.assertEqual(heavy["unknown_label_warning_counts"], {"not_observable": 5, "uncertain": 5})
        self.assertEqual(heavy["abstain_frames"], 10)

    def test_raw_gate_support_and_major_increment_are_separate(self):
        result = evaluation.evaluate_clips(*fixture())
        report = result["aggregate"]["throwing_elbow"]
        gate = report["screens"]["heavy_disagreement"]["retention_on_original_raw_gate_pass"]
        self.assertEqual((gate["original_support"], gate["remaining_without_this_hint"], gate["reliable_remaining"]), (20, 5, 5))
        self.assertEqual(gate["newly_caught_gate_pass_wrong_points"], 5)
        overlap = report["existing_major_hint_overlap"]
        self.assertEqual((overlap["overlap_frames"], overlap["new_hint_union_increment"], overlap["union_frames"]), (5, 10, 15))
        self.assertEqual(overlap["new_gate_pass_bad_hint_beyond_major"], 0)

    def test_canonical_gt_is_expanded_and_old_label_mismatch_rejected(self):
        values = fixture()
        values[2]["pitch_003"]["labels"]["throwing_elbow_reliability"][1]["status"] = "reliable"
        with self.assertRaisesRegex(ValueError, "independently expanded canonical"):
            evaluation.evaluate_clips(*values)

    def test_gt_gap_and_overlap_are_rejected(self):
        for overlap in (False, True):
            values = fixture()
            intervals = values[2]["pitch_003"]["labels"]["throwing_elbow_reliability"]
            intervals.append(deepcopy(intervals[1])) if overlap else intervals.pop()
            with self.assertRaisesRegex(ValueError, "canonical"):
                evaluation.evaluate_clips(*values)

    def test_exact_training_maximum_does_not_warn(self):
        values = fixture()
        result = evaluation.evaluate_clips(*values)
        row = next(row for row in result["frame_joint_rows"] if row["pitch_id"] == "pitch_001" and
            row["frame_index"] == 2 and row["role"] == "throwing_elbow")
        hint = row["screens"]["heavy_disagreement"]
        self.assertEqual(hint["distance_diagonal"], hint["threshold_diagonal"])
        self.assertIs(hint["review_required"], False)
        values[1]["pitch_001"]["frames"][2]["roles"]["throwing_elbow"].update({
            "status": "warning", "review_required": True, "evaluated_warning": True})
        with self.assertRaisesRegex(ValueError, "strict-maximum"):
            evaluation.evaluate_clips(*values)

    def test_sealed_threshold_and_distances_cannot_be_changed(self):
        values = fixture()
        values[1]["pitch_001"]["frames"][1]["roles"]["throwing_elbow"]["threshold_diagonal"] = .02
        with self.assertRaisesRegex(ValueError, "training maximum"):
            evaluation.evaluate_clips(*values)
        values = fixture()
        values[0]["pitch_001"]["frames"][1]["roles"]["throwing_elbow"]["distance_px"] += 1
        with self.assertRaisesRegex(ValueError, "pixel distance"):
            evaluation.evaluate_clips(*values)

    def test_original_raw_gate_cannot_be_fabricated(self):
        values = fixture()
        values[0]["pitch_001"]["frames"][2]["roles"]["throwing_elbow"]["raw_gate_pass"] = True
        with self.assertRaisesRegex(ValueError, "0.5 raw gate"):
            evaluation.evaluate_clips(*values)

    def test_selected_native_point_not_cross_person_assembly(self):
        values = fixture()
        values[0]["pitch_001"]["frames"][1]["roles"]["throwing_elbow"]["heavy_point"]["x"] += .1
        with self.assertRaisesRegex(ValueError, "selected native same-name"):
            evaluation.evaluate_clips(*values)

    def test_heavy_low_score_is_kept_as_measurable_diagnostic(self):
        values = fixture()
        frame = values[0]["pitch_001"]["frames"][1]
        for point in (frame["heavy_candidates"][0][14], frame["roles"]["throwing_elbow"]["heavy_point"]):
            point["visibility"] = .01
            point["presence"] = .01
        result = evaluation.evaluate_clips(*values)
        row = next(row for row in result["frame_joint_rows"] if row["pitch_id"] == "pitch_001" and
            row["frame_index"] == 1 and row["role"] == "throwing_elbow")
        self.assertIs(row["heavy_selected_finite"], True)
        self.assertIs(row["heavy_gate_pass_diagnostic_only"], False)
        self.assertIs(row["screens"]["heavy_disagreement"]["evaluated_warning"], True)
        self.assertEqual(row["label_target"], "original_full_raw_overlay_only")

    def test_nonfinite_heavy_and_missing_raw_never_count_as_caught_errors(self):
        values = fixture()
        frame = values[0]["pitch_001"]["frames"][1]
        frame["heavy_candidates"][0][14]["x"] = None
        frame["roles"]["throwing_elbow"]["heavy_point"]["x"] = None
        _refresh_role(values, "pitch_001", 1, "throwing_elbow")
        _resupply_predictions(values)
        result = evaluation.evaluate_clips(*values)
        heavy = result["aggregate"]["throwing_elbow"]["screens"]["heavy_disagreement"]
        self.assertEqual((heavy["tp"], heavy["fn"], heavy["abstain_frames"]), (4, 6, 11))

    def test_original_context_hold_and_frame104_are_preserved(self):
        values = fixture(total=105)
        baseline = next(row for row in values[3]["frame_joint_rows"] if row["pitch_id"] == "pitch_003" and
            row["role"] == "throwing_elbow" and row["frame_index"] == 104)
        baseline["original_context"].update({"major_hold": True,
            "major_pose_failure": [{"status": "confirmed"}],
            "use_disposition": {"status": "hold_frame_review", "restrictions": ["human_confirmed_major_pose_failure"]}})
        result = evaluation.evaluate_clips(*values)
        held = result["held_out_pitch_003"]["known_major_miss_frame_104_context"]
        self.assertEqual(len(held), 2)
        self.assertEqual(held[0]["original_context"], baseline["original_context"])
        self.assertFalse(held[0]["existing_major_review_required"])
        self.assertFalse(held[0]["screens"]["heavy_disagreement"]["evaluated_warning"])

    def test_sources_are_immutable_and_other_four_precise_accuracy_null(self):
        values = fixture()
        before = deepcopy(values)
        result = evaluation.evaluate_clips(*values)
        self.assertEqual(values, before)
        result["frame_joint_rows"][0]["original_context"]["use_disposition"]["restrictions"].append("changed")
        self.assertEqual(values, before)
        self.assertTrue(all(clip["precise_accuracy"] is None for clip in result["clips"]))
        self.assertFalse(result["decision"]["automatically_passes_phase2"])

    def test_manual_xy_uses_same_finite_pairs_and_reports_missing_separately(self):
        values = fixture()
        manual = {"source_video": {"pitch_id": "pitch_003", "total_frames": 7, "sha256": "3" * 64},
            "coordinate_system": "original_image_pixels_xy", "image_size": {"width": 100, "height": 200},
            "frames": [{"frame_index": i, "joints": [{"name": name, "status": "visible", "x_px": 10, "y_px": 20}
                for name in ("RIGHT_ELBOW", "RIGHT_WRIST")]} for i in range(7)]}
        result = evaluation.evaluate_clips(*values, manual_xy=manual)
        precise = result["clips"][2]["precise_accuracy"]
        self.assertFalse(precise["heavy_quality_labelled"])
        role = precise["roles"]["throwing_elbow"]
        self.assertEqual((role["visible_reference_frames"], role["original_full_missing_visible_frames"],
            role["heavy_selected_missing_visible_frames"]), (6, 1, 1))
        pairs = role["same_frame_same_joint_paired_errors"]
        self.assertEqual(pairs["original_full"]["n"], 4)
        self.assertEqual(pairs["heavy"]["n"], 4)
        self.assertEqual(pairs["original_full"]["mean_px"], 0)
        self.assertEqual(role["paired_both_gates_pass_errors"]["heavy"]["n"], 3)
        self.assertEqual([row["frame_index"] for row in role["pairs"]], [1, 2, 3, 4])
        self.assertTrue(all(result["clips"][i]["precise_accuracy"] is None for i in (0, 1, 3, 4)))
        manual["frames"][3]["joints"][0]["status"] = "not_observable"
        with self.assertRaisesRegex(ValueError, "cannot become visible truth"):
            evaluation.evaluate_clips(*values, manual_xy=manual)

    def test_historical_screens_are_retained_verbatim(self):
        values = fixture()
        old = values[3]["frame_joint_rows"][2]
        old["screens"]["classifier"] = {"state": "warning", "warning": True, "probability": .9}
        result = evaluation.evaluate_clips(*values)
        row = next(row for row in result["frame_joint_rows"] if row["pitch_id"] == old["pitch_id"] and
            row["frame_index"] == old["frame_index"] and row["role"] == old["role"])
        self.assertEqual(row["screens"]["classifier"], old["screens"]["classifier"])


if __name__ == "__main__":
    unittest.main()
