"""Mocked boundaries for confirmed initialization and sealed five-clip reuse."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("measure_assisted_roi_cohort", ROOT / "scripts/measure_assisted_roi_cohort.py")
    measure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(measure)
finally:
    sys.path.pop(0)

DIGEST = "a" * 64


def reference(path):
    return {"path": path, "sha256": DIGEST}


def fixture():
    clips, files = [], {}
    for pitch_id, count in zip(measure.CLIP_IDS, (87, 175, 115, 114, 101)):
        target = {"pitch_id": pitch_id, "total_frames": count, "width": 40, "height": 32}
        sources = {role: reference(f"synthetic/{pitch_id}/{role}.json") for role in measure.SOURCE_ROLES}
        sources["video"] = reference(f"synthetic/{pitch_id}/{pitch_id}.mp4")
        clip = {"kind": "reuse_sealed" if pitch_id == "pitch_003" else "new_measurement",
                "target": target, "sources": sources}
        if pitch_id == "pitch_003":
            clip.update(reused_tracking=reference("synthetic/reused_tracking.json"),
                        reused_pose=reference("synthetic/reused_pose.json"))
        clips.append(clip)
        files[sources["metadata"]["path"]] = {
            "schema_version": "pitch-input-v1", "pitch_id": pitch_id,
            "video": {"file": pitch_id + ".mp4"},
        }
        files[sources["video_technical"]["path"]] = {
            "sha256": DIGEST, "frame_count": count, "width": 40, "height": 32,
            "timestamps_ms": [index * 1000 / 30 for index in range(count)],
        }
        files[sources["initialization"]["path"]] = {
            "status": "human_confirmed_initialization", "pitch_id": pitch_id, "frame_index": 0,
            "native_timestamp_ms": 0., "rectangle_xywh": [3, 4, 12, 20],
            "decoded_bgr_sha256": DIGEST, "source_video": sources["video"],
            "source_kind": "assistant_visual_proposed_human_confirmed", "human_conclusion": "pitcher",
            "extent_observation": measure.VISIBLE_EXTENT, "actual_reply_token": "全部正確",
            "producer_must_not_open_lineage_sources": True, "excluded_from_effectiveness_evaluation": True,
            "lineage_for_parent_preflight_only": {"source_review": {"path": "must-not-open-review.json"}},
        }
    plan = {
        "status": "frozen_before_measurement", "proposal_manifest": "synthetic/proposal.json",
        "proposal_manifest_sha256": DIGEST, "clips": clips, "model": reference("synthetic/model.task"),
        "tracker_parameters": {name: 0 for name in measure.tracking.PARAMETER_NAMES},
        "pose_options": copy.deepcopy(measure.roi.OPTIONS), "crop_parameters": copy.deepcopy(measure.roi.PARAMETERS),
        "runtime": {"synthetic": True}, "native_binding_hashes": {name: DIGEST for name in measure.NATIVE_BINDING_PATHS},
        "producer_dependencies": {name: reference(name) for name in measure.DEPENDENCY_PATHS},
        "producer_sha256": DIGEST, "producer_test_sha256": DIGEST,
    }
    proposal = {key: copy.deepcopy(plan[key]) for key in measure.FROZEN_FIELDS}
    proposal["status"] = "proposal_only"
    files[plan["proposal_manifest"]] = proposal
    files["synthetic/plan.json"] = plan
    clip = clips[2]
    frames = [{"frame_index": index, "native_timestamp_ms": index * 1000 / 30,
               "decoded_bgr_sha256": DIGEST, "usable_rectangle_xywh": [3, 4, 12, 20]}
              for index in range(115)]
    files[clip["reused_tracking"]["path"]] = {
        "status": "sealed_measurements_only", "target": clip["target"], "frames": frames,
        "producer_sources": clip["sources"], "initialization_frame_excluded_from_effectiveness": True,
        "parameters": plan["tracker_parameters"], "failure_policy": measure.tracking.FAILURE_POLICY,
        "raw_score_policy": measure.tracking.RAW_SCORE_POLICY,
        "initialization_failure_policy": measure.tracking.INITIALIZATION_FAILURE_POLICY,
        "integrity_failure_policy": measure.tracking.INTEGRITY_FAILURE_POLICY,
    }
    files[clip["reused_pose"]["path"]] = {
        "status": "sealed_measurements_only", "target": clip["target"], "frames": copy.deepcopy(frames),
        "parameters": plan["crop_parameters"], "options": plan["pose_options"], "runtime": plan["runtime"],
        "upstream_roi_requires_human_initialization": True,
        "producer_sources": {**{role: clip["sources"][role] for role in ("video", "metadata", "video_technical")},
                             "model": plan["model"], "tracked_roi": clip["reused_tracking"]},
    }
    return plan, files


class AssistedFreezeTests(unittest.TestCase):
    def verify(self, plan, files, changed_path=None):
        opened = []

        def file_hash(path):
            name = Path(path).relative_to(ROOT).as_posix()
            return "b" * 64 if name == changed_path else DIGEST

        def allowed_read(path):
            name = Path(path).relative_to(ROOT).as_posix()
            opened.append(name)
            return files[name]

        with patch.object(measure, "runtime", return_value={"synthetic": True}), \
                patch.object(measure.tracking, "default_parameters", return_value={name: 0 for name in measure.tracking.PARAMETER_NAMES}), \
                patch.object(measure, "read", side_effect=allowed_read), \
                patch.object(measure, "sha", side_effect=file_hash), \
                patch.object(measure.tracking, "sha", side_effect=file_hash):
            measure.verify_execution(ROOT, plan)
        return opened

    def test_five_sources_and_reused_receipts_validate_without_review_or_gt(self):
        plan, files = fixture()
        opened = self.verify(plan, files)
        self.assertEqual(len(opened), 17)
        self.assertNotIn("must-not-open-review.json", opened)
        self.assertNotIn(plan["clips"][2]["sources"]["initialization"]["path"], opened)
        self.assertIn("synthetic/reused_tracking.json", opened)
        self.assertIn("synthetic/reused_pose.json", opened)

    def test_order_kinds_extra_source_roles_and_dependency_roles_are_rejected(self):
        for variant in ("order", "kind", "source", "dependency"):
            plan, files = fixture()
            if variant == "order":
                plan["clips"][0], plan["clips"][1] = plan["clips"][1], plan["clips"][0]
            elif variant == "kind":
                plan["clips"][2]["kind"] = "new_measurement"
            elif variant == "source":
                plan["clips"][0]["sources"]["manual_xy"] = reference("must-not-open-gt.json")
            else:
                plan["producer_dependencies"]["manual_xy"] = reference("must-not-open-gt.json")
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.verify(plan, files)

    def test_frozen_settings_model_and_proposal_changes_are_rejected(self):
        for variant in ("padding", "mode", "model", "proposal"):
            plan, files = fixture()
            if variant == "padding":
                plan["crop_parameters"]["padding"] = 16
            elif variant == "mode":
                plan["pose_options"]["num_poses"] = 1
            elif variant == "model":
                plan["model"] = reference("synthetic/another.task")
            else:
                files[plan["proposal_manifest"]]["status"] = "already_measured"
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.verify(plan, files)

    def test_source_code_test_and_native_edits_are_rejected(self):
        plan, files = fixture()
        changed = [plan["clips"][0]["sources"]["video"]["path"], "scripts/measure_seeded_subject.py",
                   "scripts/measure_assisted_roi_cohort.py", "tests/test_assisted_roi_cohort.py",
                   next(iter(measure.NATIVE_BINDING_PATHS)), "synthetic/reused_pose.json"]
        for path in changed:
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "changed"):
                self.verify(plan, files, changed_path=path)

    def test_source_dimensions_sha_and_fractional_timeline_mismatch_are_rejected(self):
        for variant in ("dimensions", "sha", "timestamps", "extra"):
            plan, files = fixture()
            technical = files[plan["clips"][0]["sources"]["video_technical"]["path"]]
            if variant == "dimensions":
                technical["height"] += 1
            elif variant == "sha":
                technical["sha256"] = "b" * 64
            elif variant == "timestamps":
                technical["timestamps_ms"][1] = float("nan")
            else:
                technical["timestamps_ms"].append(9999.)
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.verify(plan, files)

    def test_reused_frame_or_tracked_source_mismatch_is_rejected_without_inference(self):
        for variant in ("pixel", "target", "tracked_source"):
            plan, files = fixture()
            reused = files["synthetic/reused_pose.json"]
            if variant == "pixel":
                reused["frames"][2]["decoded_bgr_sha256"] = "b" * 64
            elif variant == "target":
                reused["target"] = {**reused["target"], "width": 41}
            else:
                reused["producer_sources"]["tracked_roi"] = reference("synthetic/wrong_tracking.json")
            with patch.object(measure.tracking, "measure_frames") as track, \
                    patch.object(measure.roi, "measure_frames") as pose, \
                    self.subTest(variant=variant), self.assertRaises(ValueError):
                self.verify(plan, files)
            track.assert_not_called()
            pose.assert_not_called()


class AssistedSeedTests(unittest.TestCase):
    def test_unreviewed_wrong_subject_extent_source_or_reply_is_rejected(self):
        plan, files = fixture()
        clip = plan["clips"][0]
        seed = files[clip["sources"]["initialization"]["path"]]
        measure.validate_initialization(seed, clip)
        variants = [("status", "unreviewed_not_used"), ("source_kind", "assistant_visual_proposal_unreviewed"),
                    ("human_conclusion", "other"), ("extent_observation", "full_body"),
                    ("actual_reply_token", None), ("source_video", reference("other.mp4")),
                    ("decoded_bgr_sha256", "bad"), ("frame_index", True), ("native_timestamp_ms", float("nan")),
                    ("producer_must_not_open_lineage_sources", False)]
        for key, value in variants:
            wrong = {**seed, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                measure.validate_initialization(wrong, clip)

    def test_finite_in_image_rectangle_is_required(self):
        plan, files = fixture()
        clip = plan["clips"][0]
        seed = files[clip["sources"]["initialization"]["path"]]
        for rectangle in ([0, 0, 0, 3], [-1, 0, 2, 3], [0, 0, 41, 30], [0, 0, 3, float("inf")], [True, 0, 3, 4]):
            with self.subTest(rectangle=rectangle), self.assertRaises(ValueError):
                measure.validate_initialization({**seed, "rectangle_xywh": rectangle}, clip)

    def test_decoded_frame0_sha_mismatch_aborts_before_tracker_init_or_pose(self):
        plan, files = fixture()
        clip = plan["clips"][0]
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((32, 40, 3), np.uint8))
        capture.get.return_value = 0.
        tracker = Mock()
        api = Mock()
        api.Params.return_value = SimpleNamespace(**plan["tracker_parameters"])
        api.create.return_value = tracker
        writer, check = Mock(), Mock()
        with patch.object(measure, "read", side_effect=lambda path: files[Path(path).relative_to(ROOT).as_posix()]), \
                patch.object(Path, "mkdir"), patch.object(measure.cv2, "TrackerCSRT", api), \
                patch.object(measure.cv2, "VideoCapture", return_value=capture), \
                patch.object(measure, "write", writer), patch.object(measure.roi, "measure_frames") as pose, \
                self.assertRaisesRegex(ValueError, "Initialization frame"):
            measure._new_clip(ROOT, plan, clip, ROOT / "analysis_results/synthetic", DIGEST, check)
        tracker.init.assert_not_called()
        pose.assert_not_called()
        writer.assert_not_called()
        capture.release.assert_called_once()


class AssistedClipIntegrationTests(unittest.TestCase):
    def test_frozen_helpers_keep_full_timeline_and_terminal_missing_crops(self):
        for success in (True, False):
            plan, files = fixture()
            clip = copy.deepcopy(plan["clips"][0])
            clip["target"]["total_frames"] = 3
            pixels = np.zeros((32, 40, 3), np.uint8)
            technical = files[clip["sources"]["video_technical"]["path"]]
            technical["frame_count"], technical["timestamps_ms"] = 3, [0., 1000 / 30, 2000 / 30]
            seed = files[clip["sources"]["initialization"]["path"]]
            seed["decoded_bgr_sha256"] = hashlib.sha256(pixels.tobytes()).hexdigest()
            captures = []
            for _ in range(2):
                capture = Mock()
                capture.isOpened.return_value = True
                capture.read.side_effect = [(True, pixels.copy()) for _ in range(3)] + [(False, None)]
                capture.get.side_effect = technical["timestamps_ms"]
                captures.append(capture)
            tracker = Mock()
            tracker.init.return_value = None
            tracker.update.return_value = (success, (3, 4, 12, 20))
            tracker.getTrackingScore.return_value = .7
            api = Mock()
            api.Params.return_value = SimpleNamespace(**plan["tracker_parameters"])
            api.create.return_value = tracker
            detector = Mock()
            detector.detect.return_value = SimpleNamespace(pose_landmarks=[])
            context = Mock(__enter__=Mock(return_value=detector), __exit__=Mock(return_value=False))
            landmarker = Mock()
            landmarker.create_from_options.return_value = context
            options_constructor = Mock()
            media = SimpleNamespace(
                tasks=SimpleNamespace(BaseOptions=Mock(), vision=SimpleNamespace(
                    PoseLandmarkerOptions=options_constructor, PoseLandmarker=landmarker,
                    RunningMode=SimpleNamespace(IMAGE="IMAGE"))),
                Image=Mock(side_effect=lambda **kwargs: kwargs["data"]),
                ImageFormat=SimpleNamespace(SRGB="SRGB"))
            sealed = {}
            writer = lambda path, data: sealed.__setitem__(Path(path).name, data)
            check = Mock()
            with self.subTest(success=success), \
                    patch.object(measure, "read", side_effect=lambda path: files[Path(path).relative_to(ROOT).as_posix()]), \
                    patch.object(Path, "mkdir"), patch.object(measure.cv2, "TrackerCSRT", api), \
                    patch.object(measure.cv2, "VideoCapture", side_effect=captures), \
                    patch.object(measure.tracking, "runtime", return_value={"synthetic": True}), \
                    patch.object(measure, "runtime", return_value={"synthetic": True}), \
                    patch.object(measure, "sha", return_value=DIGEST), patch.object(measure, "verify_sources"), \
                    patch.object(measure, "write", side_effect=writer), \
                    patch.object(measure, "PitcherSelector", wraps=measure.PitcherSelector) as selector, \
                    patch.dict(sys.modules, {"mediapipe": media}):
                entry = measure._new_clip(ROOT, plan, clip, ROOT / "analysis_results/synthetic", DIGEST, check)
            self.assertEqual(entry["new_tracker_initialization_calls"], 1)
            self.assertEqual(entry["new_tracker_update_calls"], 2 if success else 1)
            self.assertEqual(entry["new_pose_inference_calls"], 3 if success else 1)
            self.assertEqual(detector.detect.call_count, 3 if success else 1)
            self.assertEqual(len(sealed["seeded_subject_measurements.json"]["frames"]), 3)
            pose = sealed["roi_pose_measurements.json"]
            self.assertEqual(len(pose["frames"]), 3)
            self.assertEqual(pose["plan_sha256"], DIGEST)
            self.assertEqual(pose["producer_sources"]["tracked_roi"], entry["tracking"])
            self.assertEqual(pose["human_annotation_inputs"], [])
            self.assertEqual([frame["inference_status"] for frame in pose["frames"]],
                             ["measured"] * 3 if success else ["measured", "roi_unavailable", "roi_unavailable"])
            self.assertEqual(check.call_count, 2)
            selector.assert_called_once_with()
            api.create.assert_called_once()
            landmarker.create_from_options.assert_called_once()
            self.assertEqual(options_constructor.call_args.kwargs["running_mode"], "IMAGE")
            for capture in captures:
                capture.release.assert_called_once()


class AssistedCohortRunTests(unittest.TestCase):
    def invoke(self, fail=False, changed_plan=False, writer=None):
        plan, files = fixture()
        writer = Mock() if writer is None else writer

        def fake_new(root, frozen, clip, directory, plan_sha, check):
            if fail:
                raise RuntimeError("synthetic runtime failure")
            count = clip["target"]["total_frames"]
            return {"pitch_id": clip["target"]["pitch_id"], "kind": "new_measurement", "target": clip["target"],
                    "tracking": reference(directory.relative_to(root).as_posix() + "/seeded_subject_measurements.json"),
                    "pose": reference(directory.relative_to(root).as_posix() + "/roi_pose_measurements.json"),
                    "new_tracker_initialization_calls": 1, "new_tracker_update_calls": count - 1,
                    "new_pose_inference_calls": count}

        hashes = Mock(side_effect=[DIGEST, "b" * 64]) if changed_plan else Mock(return_value=DIGEST)
        with patch.object(measure, "read", side_effect=lambda path: files[Path(path).relative_to(ROOT).as_posix()]), \
                patch.object(measure, "sha", hashes), patch.object(measure, "verify_execution"), \
                patch.object(measure, "verify_sources"), patch.object(Path, "mkdir"), \
                patch.object(Path, "exists", return_value=False), patch.object(measure, "write", writer), \
                patch.object(measure, "_new_clip", side_effect=fake_new) as new:
            result = measure.run(ROOT, "synthetic/plan.json", ROOT / "analysis_results/synthetic-cohort-never-written")
        return result, new, writer

    def test_new_four_only_are_measured_and_003_remains_original_pointer(self):
        result, new, writer = self.invoke()
        self.assertEqual([call.args[2]["target"]["pitch_id"] for call in new.call_args_list],
                         ["pitch_001", "pitch_002", "pitch_004", "pitch_005"])
        reused = result["clips"][2]
        self.assertEqual(reused["tracking"], reference("synthetic/reused_tracking.json"))
        self.assertEqual(reused["pose"], reference("synthetic/reused_pose.json"))
        self.assertEqual(reused["new_tracker_initialization_calls"], 0)
        self.assertEqual(reused["new_tracker_update_calls"], 0)
        self.assertEqual(reused["new_pose_inference_calls"], 0)
        self.assertEqual((result["source_frames"], result["non_seed_frames"], result["new_source_frames"], result["reused_source_frames"]),
                         (592, 587, 477, 115))
        self.assertEqual((result["new_tracker_initialization_calls"], result["new_tracker_update_calls"], result["new_pose_inference_calls"]),
                         (4, 473, 477))
        self.assertEqual(result["phase2_automatic_reliability"], "NOT PASSED")
        self.assertIsNone(result["warning_policy"])
        writer.assert_called_once()
        self.assertEqual(writer.call_args.args[0].name, "cohort_measurements.json")

    def test_runtime_or_manifest_failure_does_not_seal_cohort(self):
        for kwargs in ({"fail": True}, {"changed_plan": True}):
            writer = Mock()
            with self.subTest(kwargs=kwargs), self.assertRaises((RuntimeError, ValueError)):
                self.invoke(**kwargs, writer=writer)
            writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
