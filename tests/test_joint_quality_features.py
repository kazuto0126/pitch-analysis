"""Synthetic isolation and arithmetic tests; no real features or fitting."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import joint_quality_features as features


def fixture(total=4, times=None, candidates=(0, 1), overrides=None, throwing="RIGHT"):
    times = times or [index * 1000 for index in range(total)]
    target = {"pitch_id": "synthetic_clip", "total_frames": total, "width": 300, "height": 400}
    geom = {"source_height": 400, "source_width": 300, "target_height": 256, "target_width": 256,
            "resized_height": 256, "resized_width": 192, "pad_left": 32, "pad_right": 32,
            "pad_top": 0, "pad_bottom": 0, "scale_x": .64, "scale_y": .64,
            "coordinate_convention": features.COORDINATE_CONVENTION}
    lead = "LEFT" if throwing == "RIGHT" else "RIGHT"
    mapping = {role: (throwing if role.startswith("throwing_") else lead) + "_" + role.split("_")[1].upper()
               for role in ("throwing_shoulder", *features.ROLES, "lead_hip", "lead_knee", "lead_ankle")}
    refs = {"original_raw": {"path": "base/raw.csv", "sha256": "raw_hash"},
            "capture": {"path": "base/capture.json", "sha256": "capture_hash"}}
    capture = {"video": "D:/repository/input/synthetic_clip.mp4", "width": 300, "height": 400,
               "start_frame": 0, "end_frame": total - 1, "requested_frames": total, "processed_frames": total,
               "selection_frames": [{"frame_index": index, "timestamp_ms": times[index]} for index in range(total)]}
    config = {"source_pose_csv": "D:/repository/base/raw.csv", "source_context": "D:/repository/base/capture.json",
              "width": 300, "height": 400, "timeline_start_frame": 0, "timeline_end_frame": total - 1,
              "requested_frames": total, "min_visibility": .5, "min_presence": .5}
    native = {"status": "sealed_measurements_only", "human_annotation_inputs": [], "target": target,
              "total_frames": total, "completed_frames": total, "inference_calls": total,
              "source_references": {"video": {"path": "input/synthetic_clip.mp4", "sha256": "video_hash"}},
              "frames": []}
    disagreement = {"status": "sealed_joint_disagreement_only", "target": target,
                    "source_frames": total, "non_seed_frames": total - 1, "human_annotation_inputs": [],
                    "source_references": refs, "important_joints": mapping, "frames": []}
    raw = []
    for index in range(total):
        points = {name: {"x": .2 + index * .1, "y": .4, "z": 0., "visibility": .8, "presence": .9}
                  for name in features.JOINTS}
        for (frame_index, name), override in (overrides or {}).items():
            if frame_index == index:
                if override is None:
                    points.pop(name, None)
                else:
                    points[name].update(override)
        raw.append(points)
        output, slots = [], []
        for slot_index in range(6):
            triplets = [[.3, .3 + slot_index * .05, .1 * (slot_index + 1)] for _ in features.NATIVE_JOINTS]
            box = [.1, .1, .9, .9, .7]
            output.append([value for row in triplets for value in row] + box)
            slots.append({"slot_index": slot_index, "native_yx_score": triplets,
                "source_xy": [[(x * 256 - 32) / .64, (y * 256) / .64] for y, x, _ in triplets],
                "native_box_ymin_xmin_ymax_xmax_score": box, "joint_order": list(features.NATIVE_JOINTS),
                "subject_identity": None, "observability": None, "reliability_status": None})
        native["frames"].append({"frame_index": index, "native_timestamp_ms": float(times[index]),
            "timestamp_ms": round(times[index]), "decoded_bgr_sha256": "pixels_" + str(index),
            "input_geometry": copy.deepcopy(geom), "native_output": [output], "slots": slots})
        joints = {}
        for name in features.JOINTS:
            point = points.get(name)
            finite = point is not None and all(math.isfinite(point[key]) for key in ("x", "y", "visibility", "presence"))
            xy = [point["x"] * 300, point["y"] * 400] if finite else None
            saved_point = {"finite": finite, "xy_px": xy,
                "visibility": point["visibility"] if finite else None, "presence": point["presence"] if finite else None,
                "in_source": 0 <= xy[0] < 300 and 0 <= xy[1] < 400 if finite else None}
            rows = []
            for slot in slots:
                joint_index = features.NATIVE_JOINTS.index(name)
                position = slot["source_xy"][joint_index]
                distance = math.dist(xy, position) if finite else None
                rows.append({"slot_index": slot["slot_index"], "geometric_candidate": slot["slot_index"] in candidates,
                    "native_xy_px": position, "native_joint_score": slot["native_yx_score"][joint_index][2],
                    "native_in_source": 0 <= position[0] < 300 and 0 <= position[1] < 400,
                    "distance_px": distance, "distance_diagonal": distance / 500 if finite else None})
            compatible = [row for row in rows if row["geometric_candidate"]]
            joints[name] = {"raw": saved_point, "baseline_model_state": "observed" if finite else "missing",
                            "slot_distances": rows, "candidate_distances": compatible}
            for units, field in (("px", "distance_px"), ("diagonal", "distance_diagonal")):
                values = [row[field] for row in compatible if row[field] is not None]
                joints[name]["distance_range_" + units] = {"min": min(values) if values else None, "max": max(values) if values else None}
        disagreement["frames"].append({"frame_index": index, "effectiveness_eligible": index != 0,
            "native_timestamp_ms": float(times[index]), "capture_timestamp_ms": times[index],
            "decoded_bgr_sha256": "pixels_" + str(index), "candidate_slot_indices": list(candidates),
            "association_status": "none" if not candidates else "unique_geometric_candidate" if len(candidates) == 1 else "ambiguous",
            "joints": joints})
    return raw, capture, config, disagreement, native


class JointQualityFeaturesTest(unittest.TestCase):
    def test_feature_contract_denominators_and_no_labels(self):
        result = features.build_clip(*fixture())
        self.assertEqual(result["source_frames"], 4)
        self.assertEqual(result["non_seed_frames"], 3)
        self.assertEqual(len(result["feature_names"]), 13)
        self.assertEqual(result["continuous_indices"], [0, 1, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(result["human_annotation_inputs"], [])
        for index, frame in enumerate(result["frames"]):
            self.assertEqual(frame["effectiveness_eligible"], index != 0)
            for role in features.ROLES:
                self.assertEqual(len(frame["roles"][role]["features"]), 13)
        serialized = json.dumps(result, allow_nan=False)
        for forbidden in ("review_label", "manual_xy", "major_failure", "reliable", "unreliable", "ground_truth"):
            self.assertNotIn(forbidden, serialized)

    def test_velocity_acceleration_use_capture_seconds_and_midpoints(self):
        result = features.build_clip(*fixture(total=3, times=[0, 100, 300]))
        rows = [row["roles"]["throwing_elbow"] for row in result["frames"]]
        self.assertIsNone(rows[0]["features"][3])
        self.assertIsNone(rows[1]["features"][4])
        self.assertAlmostEqual(rows[1]["features"][3], .6)
        self.assertAlmostEqual(rows[2]["features"][3], .3)
        self.assertAlmostEqual(rows[2]["features"][4], 2.)

    def test_acceleration_is_vector_difference_not_difference_of_speed(self):
        data = fixture(total=3, overrides={(2, "RIGHT_ELBOW"): {"x": .2}})
        row = features.build_clip(*data)["frames"][2]["roles"]["throwing_elbow"]
        self.assertAlmostEqual(row["features"][3], .06)
        self.assertAlmostEqual(row["features"][4], .12)

    def test_missing_span_breaks_motion_without_interpolation(self):
        data = fixture(total=4, overrides={(1, "RIGHT_ELBOW"): None})
        rows = [frame["roles"]["throwing_elbow"] for frame in features.build_clip(*data)["frames"]]
        self.assertFalse(rows[1]["raw_finite"])
        self.assertEqual(rows[1]["evidence_status"], "insufficient_evidence")
        self.assertIsNone(rows[1]["raw_xy_px"])
        self.assertTrue(all(value is None for value in rows[1]["features"][:8]))
        self.assertIsNotNone(rows[1]["features"][8])
        self.assertIsNone(rows[2]["features"][3])
        self.assertIsNone(rows[3]["features"][4])
        self.assertAlmostEqual(rows[3]["features"][3], .06)

    def test_outside_finite_raw_is_retained_and_not_an_extra_gate(self):
        for x, y in ((1., .5), (-.1, .5), (.5, 1.), (.5, -.1)):
            with self.subTest(x=x, y=y):
                data = fixture(overrides={(1, "RIGHT_ELBOW"): {"x": x, "y": y}})
                row = features.build_clip(*data)["frames"][1]["roles"]["throwing_elbow"]
                self.assertTrue(row["raw_finite"])
                self.assertTrue(row["raw_gate_pass"])
                self.assertEqual(row["features"][2], 0.)
                self.assertIsNotNone(row["features"][3])
                self.assertIsNotNone(row["features"][5])

    def test_all_compatible_slots_and_scores_retained_without_winner(self):
        result = features.build_clip(*fixture(candidates=(0, 1, 4)))
        row = result["frames"][0]["roles"]["throwing_elbow"]
        self.assertEqual(row["features"][8:13], [.1, .5, 3., 0., 1.])
        self.assertEqual([slot["slot_index"] for slot in row["compatible_candidates"]], [0, 1, 4])
        distances = [slot["distance_diagonal"] for slot in row["compatible_candidates"]]
        self.assertEqual(row["features"][5:8], [min(distances), max(distances), max(distances) - min(distances)])

    def test_no_candidate_preserves_missing_features_and_zero_indicators(self):
        row = features.build_clip(*fixture(candidates=()))["frames"][0]["roles"]["throwing_wrist"]
        self.assertEqual(row["features"][5:10], [None] * 5)
        self.assertEqual(row["features"][10:13], [0., 1., 0.])
        self.assertEqual(row["compatible_candidates"], [])

    def test_no_future_frame_dependency(self):
        original = features.build_clip(*fixture())
        modified = features.build_clip(*fixture(overrides={(3, "RIGHT_ELBOW"): {"x": 9.}}))
        self.assertEqual(original["frames"][:3], modified["frames"][:3])

    def test_original_pose_state_is_context_not_feature(self):
        data = fixture()
        original = features.build_clip(*data)
        data[3]["frames"][1]["joints"]["RIGHT_ELBOW"]["baseline_model_state"] = "interpolated"
        modified = features.build_clip(*data)
        before = original["frames"][1]["roles"]["throwing_elbow"]
        after = modified["frames"][1]["roles"]["throwing_elbow"]
        self.assertNotEqual(before["model_state"], after["model_state"])
        self.assertEqual(before["features"], after["features"])

    def test_left_throwing_mapping_and_inconsistent_mapping_rejected(self):
        data = fixture(throwing="LEFT")
        result = features.build_clip(*data)
        self.assertEqual(result["frames"][0]["roles"]["throwing_wrist"]["landmark"], "LEFT_WRIST")
        data[3]["important_joints"]["throwing_elbow"] = "RIGHT_ELBOW"
        with self.assertRaisesRegex(ValueError, "mapping"):
            features.build_clip(*data)

    def test_original_gate_only_uses_existing_scores(self):
        data = fixture()
        before = features.build_clip(*data)["frames"][0]["roles"]["throwing_elbow"]
        data[2]["min_visibility"] = .85
        after = features.build_clip(*data)["frames"][0]["roles"]["throwing_elbow"]
        self.assertTrue(before["raw_gate_pass"])
        self.assertFalse(after["raw_gate_pass"])
        self.assertEqual(before["features"], after["features"])

    def test_nonfinite_original_raw_remains_insufficient_evidence(self):
        data = fixture(overrides={(1, "RIGHT_ELBOW"): {"visibility": float("nan")}})
        row = features.build_clip(*data)["frames"][1]["roles"]["throwing_elbow"]
        self.assertFalse(row["raw_finite"])
        self.assertFalse(row["raw_gate_pass"])
        self.assertIsNone(row["features"][0])
        json.dumps(features.build_clip(*data), allow_nan=False)

    def test_inputs_never_mutated(self):
        data = fixture()
        before = copy.deepcopy(data)
        features.build_clip(*data)
        self.assertEqual(data, before)

    def test_raw_tampering_in_any_of_twelve_landmarks_rejected(self):
        for landmark in ("RIGHT_ELBOW", "LEFT_ANKLE"):
            data = fixture()
            data[0][1][landmark]["presence"] = .7
            with self.assertRaisesRegex(ValueError, "raw point/score"):
                features.build_clip(*data)

    def test_native_score_coordinate_and_distance_tampering_rejected(self):
        for kind in ("raw_score", "saved_score", "saved_distance", "omitted_candidate"):
            with self.subTest(kind=kind):
                data = fixture()
                joint = data[3]["frames"][0]["joints"]["RIGHT_ELBOW"]
                if kind == "raw_score":
                    data[4]["frames"][0]["native_output"][0][0][26] = .9
                elif kind == "saved_score":
                    joint["slot_distances"][0]["native_joint_score"] = .9
                elif kind == "saved_distance":
                    joint["slot_distances"][0]["distance_diagonal"] += .1
                else:
                    joint["candidate_distances"] = joint["candidate_distances"][:1]
                with self.assertRaises(ValueError):
                    features.build_clip(*data)

    def test_timeline_and_source_mismatch_rejected(self):
        for kind in ("native_time", "capture_time", "duplicate_time", "frame_index", "video", "config_raw", "geometry"):
            with self.subTest(kind=kind):
                data = fixture()
                if kind == "native_time":
                    data[4]["frames"][1]["native_timestamp_ms"] += .01
                elif kind == "capture_time":
                    data[1]["selection_frames"][1]["timestamp_ms"] += 1
                elif kind == "duplicate_time":
                    for key in ("native_timestamp_ms", "timestamp_ms"):
                        data[4]["frames"][1][key] = 0
                    for key in ("native_timestamp_ms", "capture_timestamp_ms"):
                        data[3]["frames"][1][key] = 0
                    data[1]["selection_frames"][1]["timestamp_ms"] = 0
                elif kind == "frame_index":
                    data[3]["frames"][1]["frame_index"] = 0
                elif kind == "video":
                    data[1]["video"] = "D:/other/wrong.mp4"
                elif kind == "config_raw":
                    data[2]["source_pose_csv"] = "D:/other/pose.csv"
                else:
                    data[4]["frames"][1]["input_geometry"]["scale_x"] = .5
                with self.assertRaises(ValueError):
                    features.build_clip(*data)

    def test_missing_unknown_and_contaminated_sources_rejected(self):
        for kind in ("missing_frame", "target", "human_inputs", "bad_state", "native_nan"):
            with self.subTest(kind=kind):
                data = fixture()
                if kind == "missing_frame":
                    data[0].pop()
                elif kind == "target":
                    data[4]["target"] = dict(data[4]["target"], pitch_id="another_clip")
                elif kind == "human_inputs":
                    data[3]["human_annotation_inputs"] = ["unapproved_labels.json"]
                elif kind == "bad_state":
                    data[3]["frames"][0]["joints"]["LEFT_HIP"]["baseline_model_state"] = "reliable"
                else:
                    data[4]["frames"][0]["native_output"][0][0][0] = float("nan")
                with self.assertRaises(ValueError):
                    features.build_clip(*data)


if __name__ == "__main__":
    unittest.main()
