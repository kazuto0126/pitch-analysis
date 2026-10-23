"""Consumer inputs preserve saved predictions and separate clip review from GT."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pitch_analysis.analysis.native_input import (
    load_native_analysis_input, prepare_native_analysis_input,
)
from pitch_analysis.native_pose import CAPABILITIES, TOPOLOGIES
from pitch_analysis.native_pose_io import reference, write_dataset, write_json


class NativeAnalysisInputTests(unittest.TestCase):
    def fixture(self, root: Path, *, legacy=False, broken=False, missing_joint=False):
        video, metadata = root / "pitch_fixture.mp4", root / "pitch_fixture.json"
        video.write_bytes(b"a saved source; adapter must not decode or infer")
        write_json(metadata, {
            "schema_version": "pitch-input-v1", "pitch_id": "pitch_fixture",
            "pitcher": {"id": "fixture_pitcher", "throws": "RIGHT"},
            "video": {"file": video.name, "camera_view": "rear_centerfield_broadcast",
                      "horizontal_mirror": False, "playback_speed": 1.0,
                      "contains_single_pitch": True, "continuous_shot": True,
                      "subject_framing": "full_body"},
        })
        # These model/runtime references deliberately do not exist. The consumer
        # validates the consumed output, and must never open or execute a backend.
        config_ref = {"path": "not_installed/config.json", "sha256": "a" * 64}
        seed_ref = {"path": "not_installed/seed.json", "sha256": "b" * 64}
        model_ref = {"path": "not_installed/model.onnx", "sha256": "c" * 64}
        fps = Fraction(60000, 1001)
        tracks = []
        payloads = []
        for index in range(3):
            status = "seeded" if index == 0 else "linked"
            if broken and index == 1:
                status = "track_break_no_overlap"
            elif broken and index == 2:
                status = "after_track_break"
            linked = status in ("seeded", "linked")
            track = {
                "track_policy": "operator_seeded_mutual_unique_max_iou_v1",
                "frame_index": index, "timestamp_ms": float(Fraction(index * 1000) / fps),
                "decoded_bgr_sha256": str(index + 1) * 64,
                "status": status, "reason": "saved reason", "eligible_count": 2,
                "selected_output_index": 1 if linked else None,
                "selected_bbox_xyxy_px": [10, 10, 50, 90] if linked else None,
                "current_eligible_output_indices": [0, 1],
                "break_frame_index": 1 if broken and index else None,
            }
            tracks.append(track)
            points = [{
                "name": name, "index": number, "x_px": 20. + number, "y_px": 30.,
                "z": None, "visibility": None, "presence": None,
                "native_score": 12.0 if number == 0 else -0.25,
                "coordinate_state": "model_observed", "missing_reason": None,
                "source_record": {"original": "kept exactly"},
            } for number, name in enumerate(TOPOLOGIES["coco_17"]["names"])]
            if not linked:
                for point in points:
                    point.update(x_px=None, y_px=None, coordinate_state="missing",
                                 native_score=None, missing_reason=status)
            elif missing_joint and index == 1:
                points[10].update(x_px=None, y_px=None, coordinate_state="missing",
                                  missing_reason="saved_native_missing")
            payloads.append({
                "schema_version": "native-keypoints-v1", "pitch_id": "pitch_fixture",
                "backend": "rtmpose_live_onnx", "topology": "coco_17",
                "frame_index": index, "timestamp_ms": track["timestamp_ms"],
                "source_video_sha256": reference(root, video)["sha256"],
                "decoded_bgr_sha256": track["decoded_bgr_sha256"],
                "image_size": {"width": 160, "height": 120},
                "coordinate_space": "original_image_pixels_xy",
                "quality_status": "not_calibrated", "usable_for_analysis": None,
                "input_geometry": {
                    "input_mode": "roi_affine" if linked else "not_run",
                    "roi_xywh": [0, 0, 160, 120] if linked else None,
                    "affine_src_to_input": [[1, 0, 0], [0, 1, 0]] if linked else None,
                    "affine_input_to_src": [[1, 0, 0], [0, 1, 0]] if linked else None,
                    "sdk_geometry": {"saved": True} if linked else None,
                },
                "model_selection": {
                    "inference_mode": "live_stateless_roi", "pose_not_run": not linked,
                    "pose_not_run_reason": None if linked else status,
                    "track_policy": track["track_policy"],
                    "person_box_selection": {key: track[key] for key in
                                             ("status", "eligible_count", "selected_output_index",
                                              "selected_bbox_xyxy_px")},
                }, "landmarks": points,
            })
        track_path = root / "subject_track.jsonl"
        self.rows(track_path, tracks)
        native = root / "saved_native"
        source = {
            "schema_version": "native-pose-manifest-v1", "pitch_id": "pitch_fixture",
            "backend": {"name": "rtmpose_live_onnx", "model_sha256": model_ref["sha256"],
                        "model_version": "saved", "score_semantics": "uncalibrated native response"},
            "topology": "coco_17", "image_size": {"width": 160, "height": 120},
            "video": {**reference(root, video), "frame_count": 3, "fps": float(fps)},
            "timebase": {"frame_index_base": 0, "timestamp_semantics": "zero-based index / fractional fps",
                         "fps_fraction": "60000/1001"},
            "capabilities": deepcopy(CAPABILITIES["coco_17"]),
            "quality_status": "not_calibrated", "usable_for_analysis": None,
            "inference_mode": "live_stateless_roi",
            "source_refs": [reference(root, video), reference(root, metadata),
                            reference(root, track_path), config_ref, seed_ref, model_ref],
            "roi_provenance": {"config_ref": config_ref, "review_ref": seed_ref,
                               "reviewer": "Fixture reviewer", "reviewed_at_utc": "2026-10-23T00:00:00Z",
                               "roi_source": "operator seed", "track_policy": tracks[0]["track_policy"]},
            "original_overlay": None,
        }
        write_dataset(native, source, payloads)
        (native / "overlay_native.mp4").write_bytes(b"the exact overlay accepted by a person")
        review_path = root / "human_review.json"
        entry = {
            "pitch_id": "pitch_fixture", "frame_count": 3,
            "video_ref": reference(root, video),
            "native_manifest_ref": reference(root, native / "native_pose_manifest.json"),
            "native_keypoints_ref": reference(root, native / "native_keypoints.jsonl"),
            "overlay_ref": reference(root, native / "overlay_native.mp4"),
            "human_overlay_review": "accepted_by_Reviewer",
            "overall_joint_alignment_review": "accepted_by_Reviewer", "candidate_status": "candidate",
        }
        review = {
            "schema_version": "skeleton-overlay-review-v1", "reviewer": "Reviewer",
            "recorded_at_utc": "2026-10-23T00:00:00Z", "review_method": "human overlay review",
            "judgment_scope": "whole-clip qualitative; not pointwise visibility or accuracy",
            "clips": [entry],
        }
        if legacy:
            review.update(schema_version="skeleton-method-adoption-v1", source_pitch_id="pitch_fixture",
                          source_pitcher_id="fixture_pitcher", **{key: entry[key] for key in
                            ("video_ref", "native_manifest_ref", "native_keypoints_ref", "overlay_ref",
                             "overall_joint_alignment_review")},
                          subject_identity_review="confirmed_pitcher_throughout_by_Reviewer",
                          adoption_decision="ADOPT_METHOD_AS_SHARED_SKELETON_STANDARD")
            del review["clips"]
        write_json(review_path, review)
        return {"root": root, "video": video, "metadata": metadata, "native": native,
                "track": track_path, "review": review_path, "source": source, "payloads": payloads,
                "tracks": tracks, "review_payload": review, "entry": entry,
                "output": root / "analysis_results" / "consumer_input"}

    @staticmethod
    def rows(path, values):
        path.write_text("".join(json.dumps(value) + "\n" for value in values), encoding="utf-8")

    @staticmethod
    def json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def refresh(self, data, *, track=False, raw=False):
        root, native = data["root"], data["native"]
        if track:
            self.rows(data["track"], data["tracks"])
            source = data["source"]
            source["source_refs"] = [ref for ref in source["source_refs"]
                                     if ref["path"] != data["track"].relative_to(root).as_posix()]
            source["source_refs"].append(reference(root, data["track"]))
            self.json(native / "native_pose_manifest.json", source)
        if raw:
            self.rows(native / "native_keypoints.jsonl", data["payloads"])
        entry = data["review_payload"] if "clips" not in data["review_payload"] else data["entry"]
        for key, name in (("native_manifest_ref", "native_pose_manifest.json"),
                          ("native_keypoints_ref", "native_keypoints.jsonl")):
            entry[key] = reference(root, native / name)
        self.json(data["review"], data["review_payload"])

    @staticmethod
    def prepare(data):
        return prepare_native_analysis_input(data["root"], data["native"], data["metadata"],
                                             data["track"], data["review"], data["output"])

    def test_saved_frames_load_exactly_without_backend_or_video_execution(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp), missing_joint=True)
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with patch("subprocess.Popen", side_effect=AssertionError("no subprocess allowed")), \
                    patch("cv2.VideoCapture", side_effect=AssertionError("no decoder allowed")):
                envelope = self.prepare(data)
                loaded = load_native_analysis_input(data["root"], data["output"])
            self.assertEqual(envelope["status"], "ready_for_native_consumption")
            self.assertEqual(len(loaded), 3)
            self.assertEqual([item.native.to_dict() for item in loaded.iter_frames()], data["payloads"])
            self.assertEqual(loaded.review["status"], "human_accepted")
            self.assertEqual(loaded.review["candidate_status_from_review"], "candidate")
            self.assertFalse(loaded.review["pointwise_reliability_established"])
            self.assertIsNone(loaded.manifest["usable_for_analysis"])
            point = loaded.read_frame(1).native.to_dict()["landmarks"][10]
            self.assertEqual((point["coordinate_state"], point["missing_reason"]),
                             ("missing", "saved_native_missing"))
            self.assertIsNone(point["visibility"])
            self.assertEqual(loaded.usage_summary["joint_reliability_unknown_slots"], 51)
            self.assertEqual(loaded.read_frame(0).native.to_dict()["landmarks"][0]["native_score"], 12.0)
            self.assertEqual(loaded.read_frame(0).native.to_dict()["landmarks"][1]["native_score"], -.25)
            self.assertEqual({path.name for path in data["output"].iterdir()},
                             {"native_analysis_input.json", "usage_summary.json"})
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_terminal_break_retains_all_missing_frames_and_unknown_joint_assessments(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp), broken=True)
            self.prepare(data)
            loaded = load_native_analysis_input(data["root"], data["output"])
            self.assertEqual(loaded.usage_summary["first_track_break_frame"], 1)
            self.assertEqual(loaded.usage_summary["pose_not_run_frames"], [1, 2])
            for index in (1, 2):
                item = loaded.read_frame(index)
                self.assertTrue(item.native.to_dict()["model_selection"]["pose_not_run"])
                for assessment in item.joint_assessments.values():
                    self.assertEqual(assessment, {"coordinate_state": "missing", "reliability": "unknown",
                                                  "human_visibility": "unknown", "usable_for_analysis": None})
            self.assertEqual(loaded.usage_summary["retained_native_landmark_slots"], 51)

    def test_legacy_single_clip_adoption_is_supported_with_same_evidence_requirements(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp), legacy=True)
            self.prepare(data)
            loaded = load_native_analysis_input(data["root"], data["output"])
            self.assertEqual(loaded.review["source_schema"], "skeleton-method-adoption-v1")
            self.assertFalse(loaded.review["pointwise_visibility_established"])

    def test_public_snapshots_cannot_modify_raw_frames_or_loaded_evidence(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            self.prepare(data)
            loaded = load_native_analysis_input(data["root"], data["output"])
            original = loaded.read_frame(0).native.to_dict()
            item = loaded.read_frame(0)
            exported = item.native.to_dict()
            exported["landmarks"][0]["x_px"] = 99999
            item.tracking["selected_bbox_xyxy_px"][0] = -5
            item.joint_assessments["RIGHT_WRIST"]["reliability"] = "reliable"
            loaded.manifest["usable_for_analysis"] = True
            loaded.metadata["pitcher"]["id"] = "somebody_else"
            with self.assertRaises(FrozenInstanceError):
                item._tracking = {}
            self.assertEqual(loaded.read_frame(0).native.to_dict(), original)
            self.assertEqual(loaded.read_frame(0).tracking["selected_bbox_xyxy_px"][0], 10)
            self.assertIsNone(loaded.manifest["usable_for_analysis"])
            self.assertEqual(loaded.metadata["pitcher"]["id"], "fixture_pitcher")
            with self.assertRaises(IndexError):
                loaded.read_frame(-1)

    def test_review_binding_rejects_wrong_overlay_missing_acceptance_and_duplicate_pitch(self):
        for problem in ("overlay", "not_accepted", "duplicate"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                if problem == "overlay":
                    data["entry"]["overlay_ref"]["sha256"] = "f" * 64
                elif problem == "not_accepted":
                    data["entry"]["human_overlay_review"] = "pending"
                else:
                    data["review_payload"]["clips"].append(deepcopy(data["entry"]))
                self.json(data["review"], data["review_payload"])
                with self.assertRaisesRegex(ValueError, "Human review"):
                    self.prepare(data)
                self.assertFalse(data["output"].exists())

    def test_changed_video_or_metadata_is_rejected_before_output_creation(self):
        for name in ("video", "metadata"):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                with data[name].open("ab") as stream:
                    stream.write(b"changed")
                with self.assertRaisesRegex(ValueError, "Changed or external source|does not bind"):
                    self.prepare(data)
                self.assertFalse(data["output"].exists())

    def test_track_must_be_bound_in_native_manifest(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            other = data["root"] / "unbound_track.jsonl"
            other.write_bytes(data["track"].read_bytes())
            data["track"] = other
            with self.assertRaisesRegex(ValueError, "does not bind this track_ref"):
                self.prepare(data)

    def test_bad_frame_pixel_box_or_rational_timeline_pairing_is_rejected(self):
        for problem in ("frame", "pixel", "box", "rounded_time", "missing_row"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                if problem == "frame":
                    data["tracks"][1]["frame_index"] = 2
                elif problem == "pixel":
                    data["tracks"][1]["decoded_bgr_sha256"] = "e" * 64
                elif problem == "box":
                    data["tracks"][1]["selected_bbox_xyxy_px"][0] += 3
                elif problem == "rounded_time":
                    data["tracks"][1]["timestamp_ms"] = round(data["tracks"][1]["timestamp_ms"])
                else:
                    data["tracks"].pop()
                self.refresh(data, track=True)
                with self.assertRaisesRegex(ValueError, "pairing differs|mapping differs|complete native frame count"):
                    self.prepare(data)

    def test_consistently_shifted_or_rounded_native_time_is_not_accepted(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            data["tracks"][1]["timestamp_ms"] = 17
            data["payloads"][1]["timestamp_ms"] = 17
            self.refresh(data, track=True, raw=True)
            with self.assertRaisesRegex(ValueError, "rational timeline pairing"):
                self.prepare(data)

    def test_tracking_cannot_reacquire_after_break_even_when_raw_claims_same_mapping(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp), broken=True)
            data["tracks"][2]["status"] = "linked"
            data["payloads"][2]["model_selection"]["person_box_selection"]["status"] = "linked"
            self.refresh(data, track=True, raw=True)
            with self.assertRaisesRegex(ValueError, "cannot reacquire"):
                self.prepare(data)

    def test_fresh_output_required_and_loader_rejects_later_source_mutation(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            self.prepare(data)
            with self.assertRaises(FileExistsError):
                self.prepare(data)
            with (data["native"] / "native_keypoints.jsonl").open("ab") as stream:
                stream.write(b"\n")
            with self.assertRaisesRegex(ValueError, "Changed or external source"):
                load_native_analysis_input(data["root"], data["output"])

    def test_loader_rejects_promoted_usability_or_forged_summary(self):
        for problem in ("usability", "summary"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                envelope = self.prepare(data)
                if problem == "usability":
                    envelope["usable_for_analysis"] = True
                else:
                    summary_path = data["output"] / "usage_summary.json"
                    summary = json.loads(summary_path.read_text())
                    summary["joint_reliability_unknown_slots"] = 0
                    self.json(summary_path, summary)
                    envelope["usage_summary_ref"] = reference(data["root"], summary_path)
                self.json(data["output"] / "native_analysis_input.json", envelope)
                with self.assertRaisesRegex(ValueError, "semantics|Usage summary differs"):
                    load_native_analysis_input(data["root"], data["output"])


if __name__ == "__main__":
    unittest.main()
