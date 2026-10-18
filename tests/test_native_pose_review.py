"""Native review tests focus on topology, gate isolation, and source binding."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from pitch_analysis.native_pose import CAPABILITIES, NativePoseFrame, TOPOLOGIES
from pitch_analysis.native_pose_review import draw_native_frame, summarize_native, write_native_overlay


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(topology="coco_17", count=3):
    return {
        "schema_version": "native-pose-manifest-v1", "pitch_id": "pitch_fixture",
        "backend": {"name": "rtmpose" if topology == "coco_17" else "mediapipe",
                    "model_sha256": "a" * 64, "model_version": "saved_fixture",
                    "score_semantics": "native score; not calibrated"},
        "topology": topology, "image_size": {"width": 160, "height": 120},
        "video": {"path": "fixture.mp4", "sha256": "b" * 64, "frame_count": count, "fps": 30.0},
        "timebase": {"frame_index_base": 0, "timestamp_semantics": "saved round(OpenCV POS_MSEC)"},
        "capabilities": deepcopy(CAPABILITIES[topology]),
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "inference_mode": "cached_read_only", "source_refs": [{"path": "fixtures/saved.json", "sha256": "c" * 64}],
        "roi_provenance": {"human_initialized": True}, "original_overlay": None,
    }


def frame_payload(source, index=0):
    topology = source["topology"]
    coco = topology == "coco_17"
    points = []
    for point_index, name in enumerate(TOPOLOGIES[topology]["names"]):
        points.append({
            "name": name, "index": point_index,
            "x_px": 10.0 + point_index * (6 if coco else 3), "y_px": 70.0 + point_index % 4 * 10,
            "z": None if coco else -.1, "visibility": None if coco else .1,
            "presence": None if coco else .1, "native_score": .01 if coco else None,
            "coordinate_state": "model_observed", "missing_reason": None,
            "source_record": {"fixture": True},
        })
    return {
        "schema_version": "native-keypoints-v1", "pitch_id": source["pitch_id"],
        "backend": source["backend"]["name"], "topology": topology,
        "frame_index": index, "timestamp_ms": round(index * 1000 / source["video"]["fps"]),
        "source_video_sha256": source["video"]["sha256"], "decoded_bgr_sha256": "d" * 64,
        "image_size": deepcopy(source["image_size"]), "coordinate_space": "original_image_pixels_xy",
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "input_geometry": {
            "input_mode": "roi_affine" if coco else "full_frame",
            "roi_xywh": [0, 0, 160, 120] if coco else None,
            "affine_src_to_input": [[1, 0, 0], [0, 1, 0]] if coco else None,
            "affine_input_to_src": [[1, 0, 0], [0, 1, 0]] if coco else None,
            "sdk_geometry": {"fixture": True} if coco else None,
        }, "model_selection": {}, "landmarks": points,
    }


def missing(point):
    point.update(x_px=None, y_px=None, coordinate_state="missing", missing_reason="saved_native_missing")


class NativeSummaryTests(unittest.TestCase):
    def test_counts_native_missing_outside_and_unsupported_separately(self):
        source = manifest()
        payloads = [frame_payload(source, index) for index in range(3)]
        payloads[0]["landmarks"][8]["x_px"] = -2.0
        payloads[0]["landmarks"][8]["native_score"] = 12.0
        missing(payloads[1]["landmarks"][8])
        missing(payloads[2]["landmarks"][8])
        result = summarize_native(source, [NativePoseFrame(payload) for payload in payloads])
        elbow = result["joints"]["RIGHT_ELBOW"]
        self.assertEqual((elbow["model_observed_coordinates"], elbow["missing_coordinates"]), (1, 2))
        self.assertEqual(elbow["coordinates_outside_image"], 1)
        self.assertEqual(elbow["longest_missing_span_frames"], 2)
        self.assertEqual(elbow["field_statistics"]["native_score"]["max"], 12.0)
        self.assertEqual(elbow["field_statistics"]["native_score"]["count"], 3)
        self.assertIsNone(elbow["field_statistics"]["visibility"]["missing_count"])
        self.assertIn("LEFT_FOOT_INDEX", result["unsupported_landmarks"])
        self.assertIn("LEFT_INDEX", result["unsupported_landmarks"])
        self.assertNotIn("RIGHT_ELBOW", result["unsupported_landmarks"])
        self.assertEqual(result["unsupported_fields"], ["presence", "visibility", "z"])
        self.assertEqual(result["interpolated_coordinates"], 0)
        self.assertIsNone(result["usable_for_analysis"])
        self.assertEqual(result["quality_status"], "not_calibrated")

    def test_mediapipe_low_visibility_is_descriptive_not_a_gate(self):
        source = manifest("mediapipe_33", 1)
        result = summarize_native(source, [NativePoseFrame(frame_payload(source))])
        elbow = result["joints"]["RIGHT_ELBOW"]
        self.assertEqual(result["native_landmark_count"], 33)
        self.assertEqual(elbow["model_observed_coordinates"], 1)
        self.assertEqual(elbow["field_statistics"]["visibility"]["mean"], .1)
        self.assertFalse(elbow["field_statistics"]["native_score"]["supported"])
        self.assertEqual(result["unsupported_landmarks"], [])

    def test_frame_count_order_and_saved_timestamp_origin_are_required(self):
        source = manifest(count=2)
        first, second = frame_payload(source), frame_payload(source, 1)
        with self.assertRaisesRegex(ValueError, "count"):
            summarize_native(source, [NativePoseFrame(first)])
        second["frame_index"] = 0
        with self.assertRaisesRegex(ValueError, "manifest"):
            summarize_native(source, [NativePoseFrame(first), NativePoseFrame(second)])
        second["frame_index"] = 1
        first["timestamp_ms"] = 1
        with self.assertRaisesRegex(ValueError, "zero origin"):
            summarize_native(source, [NativePoseFrame(first), NativePoseFrame(second)])


class NativeDrawTests(unittest.TestCase):
    def test_coco_edges_keep_native_indices_and_low_score(self):
        source = manifest(count=1)
        payload = frame_payload(source)
        image = np.zeros((120, 160, 3), dtype=np.uint8)
        with patch("pitch_analysis.native_pose_review.cv2.line") as lines, patch("pitch_analysis.native_pose_review.cv2.circle") as circles:
            draw_native_frame(image, payload)
        positions = [(int(point["x_px"]), int(point["y_px"])) for point in payload["landmarks"]]
        self.assertEqual([(call.args[1], call.args[2]) for call in lines.call_args_list],
                         [(positions[start], positions[end]) for start, end in TOPOLOGIES["coco_17"]["connections"]])
        self.assertEqual(circles.call_count, 17)  # .01 native score is still drawn.
        self.assertTrue(all(max(pair) < 17 for pair in TOPOLOGIES["coco_17"]["connections"]))
        self.assertIn((14, 16), TOPOLOGIES["coco_17"]["connections"])
        self.assertNotIn((27, 31), TOPOLOGIES["coco_17"]["connections"])

    def test_missing_outside_and_nonfinite_points_are_skipped_without_clipping(self):
        payload = frame_payload(manifest(count=1))
        missing(payload["landmarks"][10])
        payload["landmarks"][8]["x_px"] = -10.0
        payload["landmarks"][16]["y_px"] = float("nan")
        with patch("pitch_analysis.native_pose_review.cv2.line") as lines, patch("pitch_analysis.native_pose_review.cv2.circle") as circles:
            draw_native_frame(np.zeros((120, 160, 3), dtype=np.uint8), payload)
        self.assertEqual(circles.call_count, 14)
        self.assertTrue(all(call.args[1][0] > 0 for call in circles.call_args_list))
        skipped = {8, 10, 16}
        expected = sum(not skipped.intersection(pair) for pair in TOPOLOGIES["coco_17"]["connections"])
        self.assertEqual(lines.call_count, expected)

    def test_overlay_explicitly_uncalibrated_and_uses_saved_frame_time(self):
        payload = frame_payload(manifest(count=1))
        payload.update(frame_index=9, timestamp_ms=80.03)
        image = np.zeros((120, 160, 3), dtype=np.uint8)
        before = image.copy()
        with patch("pitch_analysis.native_pose_review.cv2.putText") as texts:
            rendered = draw_native_frame(image, payload)
        self.assertIn("cached RTMPose / COCO17 / NOT CALIBRATED", texts.call_args_list[0].args[1])
        self.assertIn("frame 9 / 80.030 ms", texts.call_args_list[1].args[1])
        np.testing.assert_array_equal(image, before)
        self.assertIsNot(rendered, image)
        payload["usable_for_analysis"] = True
        with self.assertRaisesRegex(ValueError, "uncalibrated"):
            draw_native_frame(image, payload)


class NativeOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.source = self.folder / "source.mp4"
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*"mp4v"), 30, (160, 120))
        self.assertTrue(writer.isOpened(), "Fixture MP4 encoder must be available")
        try:
            for index in range(3):
                image = np.full((120, 160, 3), index * 40, dtype=np.uint8)
                cv2.rectangle(image, (40, 60), (90, 110), (50, 180, 230), -1)
                writer.write(image)
        finally:
            writer.release()
        self.manifest = manifest()
        self.manifest["video"].update(path=str(self.source), sha256=digest(self.source))
        self.payloads = []
        capture = cv2.VideoCapture(str(self.source))
        try:
            for index in range(3):
                ok, image = capture.read()
                self.assertTrue(ok)
                payload = frame_payload(self.manifest, index)
                payload["decoded_bgr_sha256"] = hashlib.sha256(image.tobytes()).hexdigest()
                payload["timestamp_ms"] = round(capture.get(cv2.CAP_PROP_POS_MSEC))
                self.payloads.append(payload)
        finally:
            capture.release()
        self.target = self.folder / "result.mp4"

    def tearDown(self):
        self.temporary.cleanup()

    def frames(self):
        return [NativePoseFrame(payload) for payload in self.payloads]

    def test_small_mp4_is_encoded_then_fully_decoded_with_original_binding(self):
        source_digest = digest(self.source)
        result = write_native_overlay(self.source, self.manifest, self.frames(), self.target)
        self.assertEqual(result["decoded_frame_count"], 3)
        self.assertEqual((result["width"], result["height"], result["fps"]), (160, 120, 30.0))
        self.assertIn(result["codec"].lower(), ("avc1", "h264"))
        self.assertEqual(result["pixel_format"], "yuv420p")
        self.assertEqual(result["source_pixel_sha_verified_frames"], 3)
        self.assertEqual(result["source_timestamps_verified_frames"], 3)
        self.assertEqual(result["overlay_timestamps_verified_frames"], 3)
        self.assertLessEqual(result["max_source_timestamp_rounding_difference_ms"], .5)
        self.assertLessEqual(result["max_overlay_timestamp_rounding_difference_ms"], .5)
        self.assertEqual(result["source_timestamp_shift_ms"], 0)
        self.assertEqual(result["new_inference_calls"], 0)
        self.assertEqual(result["sha256"], digest(self.target))
        self.assertEqual(source_digest, digest(self.source))
        self.assertEqual(result["quality_status"], "not_calibrated")
        self.assertIsNone(result["usable_for_analysis"])

    def test_source_video_sha_mismatch_rejected_before_output(self):
        self.manifest["video"]["sha256"] = "0" * 64
        for payload in self.payloads:
            payload["source_video_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Source video SHA mismatch"):
            write_native_overlay(self.source, self.manifest, self.frames(), self.target)
        self.assertFalse(self.target.exists())

    def test_source_pixel_sha_mismatch_never_publishes_partial_overlay(self):
        self.payloads[1]["decoded_bgr_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pixel SHA mismatch at frame 1"):
            write_native_overlay(self.source, self.manifest, self.frames(), self.target)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.glob("native_overlay_*")), [])

    def test_timestamp_mismatch_is_not_silently_recomputed(self):
        self.payloads[1]["timestamp_ms"] += 1
        with self.assertRaisesRegex(ValueError, "timestamp.*frame 1"):
            write_native_overlay(self.source, self.manifest, self.frames(), self.target)
        self.assertFalse(self.target.exists())

    def test_actual_decode_detects_extra_frames(self):
        self.manifest["video"]["frame_count"] = 2
        self.payloads.pop()
        with self.assertRaisesRegex(ValueError, "more frames"):
            write_native_overlay(self.source, self.manifest, self.frames(), self.target)
        self.assertFalse(self.target.exists())

    def test_existing_target_is_preserved(self):
        self.target.write_bytes(b"existing overlay")
        with self.assertRaises(FileExistsError):
            write_native_overlay(self.source, self.manifest, self.frames(), self.target)
        self.assertEqual(self.target.read_bytes(), b"existing overlay")

    def test_mediapipe_references_existing_overlay_instead_of_reencoding(self):
        source = manifest("mediapipe_33", 1)
        with self.assertRaisesRegex(ValueError, "existing overlay"):
            write_native_overlay(self.source, source, [NativePoseFrame(frame_payload(source))], self.target)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
