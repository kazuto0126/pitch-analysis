"""Synthetic source binding and native semantic preservation; no inference."""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pitch_analysis.native_pose import TOPOLOGIES
from pitch_analysis.native_pose_io import reference
from pitch_analysis.native_pose_sources import load_cached_sources


class CachedFixture:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True)
        self.pid = "pitch_001"
        self.total = 2
        self.width, self.height = 100, 200
        self.names = TOPOLOGIES["mediapipe_33"]["names"]
        self.model = "models/pose_landmarker_full.task"
        self.rtm_model = "model/end2end.onnx"
        self.overlay = "predictions/pitch_001/overlay.mp4"
        self.raw_path = "predictions/pitch_001/pose_raw.csv"
        self.geometry = {"source_size": [100, 200], "roi_xywh": [5., 7., 90., 180.],
                         "affine_src_to_input": [[1., 0., 5.], [0., 1., 7.]],
                         "affine_input_to_src": [[1., 0., -5.], [0., 1., -7.]],
                         "input_size": [192, 256], "simcc_split_ratio": 2}
        self.raw = [{name: {"x": 1.25, "y": .5, "z": -.2, "visibility": .001, "presence": .002}
                     for name in self.names}, {}]
        self.choices = [{"frame_index": i, "timestamp_ms": i * 33,
                         "status": "selected" if i == 0 else "no_selection",
                         "selected_index": 0 if i == 0 else None, "candidate_count": 1 if i == 0 else 0}
                        for i in range(2)]
        self.context_frames = [{"frame_index": i, "timestamp_ms": i * 33,
                                "decoded_bgr_sha256": str(i + 1) * 64,
                                "geometry": deepcopy(self.geometry), "original_raw": self.raw[i]}
                               for i in range(2)]
        self.roi_frames = [{"frame_index": i, "usable_rectangle_xywh": deepcopy(self.geometry["roi_xywh"]),
                            "decoded_bgr_sha256": str(i + 1) * 64} for i in range(2)]
        self.native_points = [[{"index": j, "name": name, "x_px": 150.125 + j, "y_px": 75.5,
                                "score": 1.5, "decode_status": "decoded", "argmax_x_bin": j,
                                "finite_response": True}
                               for j, name in enumerate(TOPOLOGIES["coco_17"]["names"])] for _ in range(2)]
        self.native_points[1][10].update(x_px=None, y_px=None, score=-.1,
                                         decode_status="nonpositive_native_score")
        self.metadata = {"pitch_id": self.pid}
        self.write_bytes("input/pitch_001.mp4", b"original video")
        self.write_bytes(self.model, b"original full model")
        self.write_bytes(self.rtm_model, b"cached rtmpose model")
        self.write_bytes(self.overlay, b"original overlay")
        self.seal()

    def write_bytes(self, path: str, content: bytes) -> dict:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return reference(self.root, target)

    def write(self, path: str, data: dict) -> dict:
        return self.write_bytes(path, (json.dumps(data, allow_nan=False) + "\n").encode())

    def seal(self) -> None:
        video = reference(self.root, self.root / "input/pitch_001.mp4")
        metadata = self.write("input/pitch_001.json", self.metadata)
        technical = self.write("predictions/pitch_001/video_metadata.json", {
            "sha256": video["sha256"], "frame_count": 2, "width": 100, "height": 200,
            "fps": 30., "timestamps_ms": [0., 33.333333333333336]})
        capture = self.write("predictions/pitch_001/pose_raw.capture.json", {
            "video": str(self.root / video["path"]), "model": str(self.root / self.model),
            "processed_frames": 2, "start_frame": 0, "end_frame": 1, "fps": 30.,
            "width": 100, "height": 200, "selection_frames": self.choices})
        roi = self.write("roi/pitch_001.json", {"frames": self.roi_frames,
            "producer_sources": {"initialization": {"path": "never_open_human_seed.json", "sha256": "e" * 64}}})
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=("frame", "timestamp_ms", "landmark", "x", "y", "z", "visibility", "presence"))
        writer.writeheader()
        for i, points in enumerate(self.raw):
            for name, point in points.items():
                writer.writerow({"frame": i, "timestamp_ms": i * 33, "landmark": name,
                                 **{key: "nan" if value is None else value for key, value in point.items()}})
        raw = self.write_bytes(self.raw_path, buf.getvalue().encode())
        protected = self.write("protected.json", {"current_source_hashes": {
            self.model: reference(self.root, self.root / self.model)["sha256"],
            self.overlay: reference(self.root, self.root / self.overlay)["sha256"]}, "upstream": {}})
        self.execution = self.root / "execution.json"
        execution = self.write("execution.json", {"status": "approved_frozen_before_any_inference",
            "model": reference(self.root, self.root / self.rtm_model), "protected_before": protected,
            "clips": [{"pitch_id": self.pid, "total_frames": 2,
                "measurement_sources": {"video": video, "metadata": metadata,
                    "video_metadata": technical, "capture": capture, "raw_csv": raw, "roi": roi},
                "canonical_gt": {"path": "never_open_ground_truth.json", "sha256": "f" * 64},
                "major_hints": {"path": "never_open_hints.json", "sha256": "f" * 64}}],
            "baseline_evaluation": {"path": "never_open_evaluation.json", "sha256": "f" * 64}})
        context = self.write("exports/pitch_001.json", {"pitch_id": self.pid, "total_frames": 2,
            "width": 100, "height": 200, "video_sha256": video["sha256"],
            "frames": self.context_frames, "plan_sha256": execution["sha256"], "human_annotation_inputs": []})
        export = self.write("exports/export_run.json", {"status": "sealed_gt_blind_rtmpose_inputs",
            "plan_sha256": execution["sha256"], "human_annotation_inputs": [],
            "clips": [{"pitch_id": self.pid, "total_frames": 2, "context": context}]})
        child = self.write("native_execution.json", {"parent_plan_sha256": execution["sha256"],
            "model": reference(self.root, self.root / self.rtm_model), "export_run": export})
        native_refs = [{"pitch_id": self.pid, "frame_index": i,
                        **self.write_bytes(f"native/pitch_001/frame_{i:04d}.npz", b"cached binary response " + bytes([i]))}
                       for i in range(2)]
        native = self.write("native/native_run.json", {"status": "sealed_native_rtmpose_run",
            "plan_sha256": child["sha256"], "human_annotation_inputs": [], "native_frames": 2, "frames": native_refs})
        frames = [{"frame_index": i, "timestamp_ms": i * 33,
            "decoded_bgr_sha256": self.context_frames[i]["decoded_bgr_sha256"],
            "geometry": deepcopy(self.context_frames[i]["geometry"]), "native_ref": native_refs[i],
            "native_contract": {"landmark_count": 17}, "native_keypoints": self.native_points[i]}
            for i in range(2)]
        measured = self.write("measurements/pitch_001.json", {"pitch_id": self.pid, "total_frames": 2,
            "width": 100, "height": 200, "video_sha256": video["sha256"], "frames": frames,
            "plan_sha256": execution["sha256"], "human_annotation_inputs": [], "status": "sealed_rtmpose_response_measurements"})
        measurement = self.write("measurements/measurement_run.json", {"status": "sealed_all_rtmpose_response_measurements",
            "plan_sha256": execution["sha256"], "human_annotation_inputs": [], "clips": [measured]})
        self.result = self.root / "result.json"
        self.write("result.json", {"execution": execution, "status": "completed_once_both_rtmpose_response_hints_rejected",
            "source_frames": 2, "artifacts": {"exports/export_run.json": export,
                "measurements/measurement_run.json": measurement, "native/native_run.json": native,
                "native_execution.json": child,
                "evaluation/evaluation.json": {"path": "never_open_evaluation.json", "sha256": "f" * 64}}})

    def load(self) -> dict:
        return load_cached_sources(self.root, self.execution, self.result)[self.pid]


class NativePoseSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = CachedFixture(Path(self.temp.name) / "fixture")

    def test_original_pixel_conversion_preserves_low_scores_and_missing_frame(self):
        sources = self.fixture.load()
        mp, rtm = sources["mediapipe"], sources["rtmpose"]
        self.assertEqual((len(mp), len(rtm)), (2, 2))
        first = mp.read_frame(0).to_dict()
        point = first["landmarks"][14]
        self.assertEqual((point["x_px"], point["y_px"]), (125., 100.))
        self.assertEqual((point["visibility"], point["presence"], point["z"]), (.001, .002, -.2))
        self.assertEqual(point["coordinate_state"], "model_observed")
        self.assertIsNone(point["native_score"])
        self.assertEqual(point["source_record"]["x"], "1.25")
        missing = mp.read_frame(1).to_dict()
        self.assertEqual(len(missing["landmarks"]), 33)
        self.assertTrue(all(p["coordinate_state"] == "missing" and p["x_px"] is None for p in missing["landmarks"]))
        self.assertEqual(missing["timestamp_ms"], 33)
        self.assertEqual(first["model_selection"], self.fixture.choices[0])
        self.assertEqual(first["input_geometry"]["input_mode"], "full_frame")
        self.assertIsNone(first["input_geometry"]["sdk_geometry"])

    def test_cached_coco_values_are_exact_without_padding_or_fake_capabilities(self):
        source = self.fixture.load()["rtmpose"]
        first = source.read_frame(0).to_dict()
        self.assertEqual(len(first["landmarks"]), 17)
        self.assertEqual(first["landmarks"][8]["x_px"], self.fixture.native_points[0][8]["x_px"])
        self.assertEqual(first["landmarks"][8]["native_score"], 1.5)
        self.assertTrue(all(p["visibility"] is None and p["presence"] is None and p["z"] is None for p in first["landmarks"]))
        self.assertEqual(first["input_geometry"]["sdk_geometry"], self.fixture.geometry)
        self.assertEqual(first["landmarks"][8]["source_record"], self.fixture.native_points[0][8])
        self.assertEqual(first["quality_status"], "not_calibrated")
        self.assertIsNone(first["usable_for_analysis"])
        missing = source.read_frame(1).to_dict()["landmarks"][10]
        self.assertEqual(missing["native_score"], -.1)
        self.assertEqual(missing["missing_reason"], "nonpositive_native_score")
        self.assertIsNone(missing["x_px"])
        self.assertTrue(source.manifest["roi_provenance"]["human_initialized"])
        self.assertIsNone(source.manifest["original_overlay"])

    def test_no_ground_truth_or_warning_reads_and_no_model_runtime_import(self):
        import builtins
        original = builtins.__import__
        def controlled(name, *args, **kwargs):
            if name.split(".")[0] in {"mediapipe", "onnxruntime", "numpy", "tensorflow", "cv2"}:
                raise AssertionError("Unexpected model/runtime import " + name)
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=controlled):
            sources = self.fixture.load()
        paths = sources["rtmpose"].read_paths
        self.assertFalse(any("never_open" in name for name in paths))
        self.assertTrue(any(name.endswith("frame_0000.npz") for name in paths))
        self.assertTrue(any(name.endswith("pose_raw.csv") for name in paths))
        self.assertEqual(sources["mediapipe"].manifest["original_overlay"]["path"], self.fixture.overlay)

    def test_bound_source_mutations_are_rejected(self):
        for path in (self.fixture.raw_path, self.fixture.model, self.fixture.rtm_model,
                     self.fixture.overlay, "native/pitch_001/frame_0000.npz"):
            with self.subTest(path=path):
                target = self.fixture.root / path
                original = target.read_bytes()
                target.write_bytes(original + b"changed")
                with self.assertRaisesRegex(ValueError, "Changed or external"):
                    self.fixture.load()
                target.write_bytes(original)

    def test_raw_context_changes_are_rejected_even_with_new_receipts(self):
        self.fixture.context_frames[0]["original_raw"] = deepcopy(self.fixture.raw[0])
        self.fixture.context_frames[0]["original_raw"]["RIGHT_ELBOW"]["x"] = .4
        self.fixture.seal()
        with self.assertRaisesRegex(ValueError, "frame/pixel/raw/ROI"):
            self.fixture.load()

    def test_pixel_roi_and_landmark_order_changes_are_rejected(self):
        for kind in ("pixel", "roi", "order", "partial_xy"):
            with self.subTest(kind=kind):
                fixture = CachedFixture(Path(self.temp.name) / kind)
                if kind == "pixel":
                    fixture.roi_frames[0]["decoded_bgr_sha256"] = "f" * 64
                elif kind == "roi":
                    fixture.roi_frames[0]["usable_rectangle_xywh"][0] = 1.
                elif kind == "order":
                    fixture.native_points[0][0], fixture.native_points[0][1] = fixture.native_points[0][1], fixture.native_points[0][0]
                else:
                    fixture.native_points[0][0]["x_px"] = None
                fixture.seal()
                with self.assertRaises(ValueError):
                    fixture.load()

    def test_nonfinite_original_xy_stays_missing_with_raw_string_evidence(self):
        self.fixture.raw[0]["RIGHT_ELBOW"]["x"] = None
        self.fixture.seal()
        point = self.fixture.load()["mediapipe"].read_frame(0).to_dict()["landmarks"][14]
        self.assertEqual(point["coordinate_state"], "missing")
        self.assertEqual(point["missing_reason"], "nonfinite_original_xy")
        self.assertEqual(point["source_record"]["x"], "nan")
        self.assertIsNone(point["x_px"])
        self.assertIsNone(point["y_px"])

    def test_snapshot_and_frame_access_do_not_mutate_the_source(self):
        source = self.fixture.load()["rtmpose"]
        value = source.read_frame(0).to_dict()
        value["landmarks"][0]["x_px"] = -1000.
        manifest = source.manifest
        manifest["usable_for_analysis"] = True
        self.assertEqual(source.read_frame(0).to_dict()["landmarks"][0]["x_px"], 150.125)
        self.assertIsNone(source.manifest["usable_for_analysis"])
        for index in (-1, 2, True, .5):
            with self.assertRaises(IndexError):
                source.read_frame(index)

    def test_capture_timebase_and_partial_selected_pose_are_rejected(self):
        for kind in ("timeline", "partial"):
            with self.subTest(kind=kind):
                fixture = CachedFixture(Path(self.temp.name) / kind)
                if kind == "timeline":
                    fixture.choices[1]["timestamp_ms"] = 34
                else:
                    del fixture.raw[0]["NOSE"]
                fixture.seal()
                with self.assertRaises(ValueError):
                    fixture.load()


if __name__ == "__main__":
    unittest.main()
