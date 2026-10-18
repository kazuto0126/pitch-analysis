"""Native data semantics cannot silently become production gate decisions."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import unittest

from pitch_analysis.native_pose import (
    CAPABILITIES, COMMON_JOINTS, NativePoseFrame, TOPOLOGIES, validate_frame, validate_manifest,
)


def make_manifest(topology="coco_17", count=2):
    return {
        "schema_version": "native-pose-manifest-v1", "pitch_id": "fixture",
        "backend": {"name": "rtmpose" if topology == "coco_17" else "mediapipe",
                    "model_sha256": "a" * 64, "model_version": "fixture",
                    "score_semantics": "native model value; not calibrated accuracy"},
        "topology": topology, "image_size": {"width": 100, "height": 200},
        "video": {"path": "source.mp4", "sha256": "b" * 64, "frame_count": count, "fps": 30.0},
        "timebase": {"frame_index_base": 0, "timestamp_semantics": "saved zero-based clip time"},
        "capabilities": deepcopy(CAPABILITIES[topology]), "quality_status": "not_calibrated",
        "usable_for_analysis": None, "inference_mode": "cached_read_only",
        "source_refs": [{"path": "source.mp4", "sha256": "b" * 64}],
        "roi_provenance": {"human_initialization": topology == "coco_17"},
        "original_overlay": None,
    }


def make_frame(topology="coco_17", index=0):
    is_mp = topology == "mediapipe_33"
    points = [{
        "name": name, "index": number, "x_px": -2.5 + number, "y_px": 250.0,
        "z": .12 if is_mp else None, "visibility": .01 if is_mp else None,
        "presence": .02 if is_mp else None, "native_score": None if is_mp else 2.3,
        "coordinate_state": "model_observed", "missing_reason": None,
        "source_record": {"raw_index": number},
    } for number, name in enumerate(TOPOLOGIES[topology]["names"])]
    geometry = {
        "input_mode": "full_frame" if is_mp else "roi_affine",
        "roi_xywh": None if is_mp else [-4, 2, 90, 180],
        "affine_src_to_input": None if is_mp else [[2, 0, 0], [0, 2, 0]],
        "affine_input_to_src": None if is_mp else [[.5, 0, 0], [0, .5, 0]],
        "sdk_geometry": None if is_mp else {"input_size": [192, 256]},
    }
    return {
        "schema_version": "native-keypoints-v1", "pitch_id": "fixture",
        "backend": "mediapipe" if is_mp else "rtmpose", "topology": topology,
        "frame_index": index, "timestamp_ms": index * 1000 / 30,
        "source_video_sha256": "b" * 64, "decoded_bgr_sha256": "c" * 64,
        "image_size": {"width": 100, "height": 200},
        "coordinate_space": "original_image_pixels_xy", "quality_status": "not_calibrated",
        "usable_for_analysis": None, "input_geometry": geometry,
        "model_selection": {"source": "cached"}, "landmarks": points,
    }


class NativePoseContractTests(unittest.TestCase):
    def test_native_topologies_have_exact_names_indices_and_supported_connections(self):
        from pitch_analysis.pose_capture import LANDMARK_NAMES
        self.assertEqual(TOPOLOGIES["mediapipe_33"]["names"], LANDMARK_NAMES)
        self.assertEqual(len(TOPOLOGIES["coco_17"]["names"]), 17)
        self.assertEqual(len(COMMON_JOINTS), 12)
        for topology, data in TOPOLOGIES.items():
            validate_manifest(make_manifest(topology))
            validate_frame(make_frame(topology))
            self.assertEqual(len(set(data["names"])), len(data["names"]))
            for start, end in data["connections"]:
                self.assertTrue(0 <= start < len(data["names"]))
                self.assertTrue(0 <= end < len(data["names"]))
            self.assertTrue(set(COMMON_JOINTS) <= set(data["names"]))

    def test_model_observation_is_not_a_visibility_gate_and_native_score_is_not_clipped(self):
        mp = NativePoseFrame(make_frame("mediapipe_33")).to_dict()
        self.assertEqual(mp["landmarks"][0]["coordinate_state"], "model_observed")
        self.assertLess(mp["landmarks"][0]["visibility"], .5)
        rtm = make_frame()
        rtm["landmarks"][0]["native_score"] = -4.2
        wrapped = NativePoseFrame(rtm).to_dict()
        self.assertEqual(wrapped["landmarks"][0]["native_score"], -4.2)
        self.assertEqual(wrapped["landmarks"][1]["native_score"], 2.3)
        self.assertEqual(wrapped["landmarks"][0]["x_px"], -2.5)
        self.assertEqual(wrapped["landmarks"][0]["y_px"], 250.0)

    def test_fake_visibility_presence_depth_and_native_score_are_rejected(self):
        for topology, fields in (("coco_17", ("visibility", "presence", "z")),
                                 ("mediapipe_33", ("native_score",))):
            for field in fields:
                with self.subTest(topology=topology, field=field):
                    frame = make_frame(topology)
                    frame["landmarks"][0][field] = 1.0
                    with self.assertRaisesRegex(ValueError, "Unsupported"):
                        validate_frame(frame)

    def test_wrong_count_order_and_anatomical_name_are_rejected(self):
        for mutate in (lambda f: f["landmarks"].pop(),
                       lambda f: f["landmarks"].reverse(),
                       lambda f: f["landmarks"][0].update(name="LEFT_HEEL")):
            frame = make_frame()
            mutate(frame)
            with self.assertRaises(ValueError):
                validate_frame(frame)

    def test_no_interpolated_or_unsupported_padded_landmarks(self):
        frame = make_frame()
        frame["landmarks"][0]["coordinate_state"] = "interpolated"
        with self.assertRaises(ValueError):
            validate_frame(frame)
        frame = make_frame()
        frame["landmarks"].extend(deepcopy(frame["landmarks"][:16]))
        with self.assertRaises(ValueError):
            validate_frame(frame)

    def test_missing_retains_joint_and_reason_without_invented_xy(self):
        frame = make_frame()
        point = frame["landmarks"][7]
        point.update(x_px=None, y_px=None, coordinate_state="missing", missing_reason="native_decode_failed")
        validate_frame(frame)
        for mutate in (lambda p: p.update(x_px=1), lambda p: p.update(missing_reason=None)):
            bad = deepcopy(frame)
            mutate(bad["landmarks"][7])
            with self.assertRaises(ValueError):
                validate_frame(bad)

    def test_nonfinite_nested_metadata_and_numeric_bools_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            frame = make_frame()
            frame["landmarks"][0]["source_record"]["old"] = {"score": value}
            with self.assertRaisesRegex(ValueError, "Nonfinite"):
                validate_frame(frame)
        frame = make_frame()
        frame["landmarks"][0]["x_px"] = True
        with self.assertRaises(ValueError):
            validate_frame(frame)

    def test_false_quality_or_usability_claims_cannot_enter_native_data(self):
        for key, value in (("quality_status", "reliable"), ("usable_for_analysis", True),
                           ("usable_for_analysis", False), ("quality_valid", True)):
            frame = make_frame()
            frame[key] = value
            with self.assertRaises(ValueError):
                validate_frame(frame)
        manifest = make_manifest()
        manifest["quality_status"] = "passed"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_geometry_does_not_claim_roi_for_full_frame_mediapipe(self):
        mp = make_frame("mediapipe_33")
        mp["input_geometry"] = make_frame()["input_geometry"]
        with self.assertRaisesRegex(ValueError, "full-frame"):
            validate_frame(mp)
        rtm = make_frame()
        rtm["input_geometry"] = make_frame("mediapipe_33")["input_geometry"]
        with self.assertRaisesRegex(ValueError, "saved ROI"):
            validate_frame(rtm)
        rtm = make_frame()
        rtm["input_geometry"]["roi_xywh"][2] = 0
        with self.assertRaisesRegex(ValueError, "positive"):
            validate_frame(rtm)

    def test_frame_snapshot_and_exports_are_isolated_and_wrapper_is_frozen(self):
        source = make_frame()
        frame = NativePoseFrame(source)
        source["landmarks"][0]["x_px"] = 999
        exported = frame.to_dict()
        exported["landmarks"][0]["x_px"] = 888
        frame.payload["landmarks"][0]["x_px"] = 777
        self.assertEqual(frame.to_dict()["landmarks"][0]["x_px"], -2.5)
        with self.assertRaises(FrozenInstanceError):
            frame._payload = {}

    def test_manifest_rejects_fake_capability_non_cached_mode_and_traversal(self):
        manifest = make_manifest()
        manifest["capabilities"]["visibility"] = True
        with self.assertRaisesRegex(ValueError, "capabilities"):
            validate_manifest(manifest)
        manifest = make_manifest()
        manifest["inference_mode"] = "live"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest = make_manifest()
        manifest["timebase"]["frame_index_base"] = False
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        for path in ("../video.mp4", "C:/video.mp4", "a/./b", "a\\b", "a//b"):
            manifest = make_manifest()
            manifest["source_refs"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
