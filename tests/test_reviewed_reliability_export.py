"""Human evidence never becomes an automatic warning or invented coordinate."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("reviewed_export", Path(__file__).resolve().parents[1] / "scripts/export_reviewed_reliability.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def human_frame():
    return {"pitcher_correctly_selected": True, "major_pose_failure": [],
            "track_break": [], "identity_switch": []}


def fixture():
    roles = export.role_mapping("RIGHT")
    total = 3
    labels = {key: [] for key in ("identity_switch_intervals", "track_break_intervals", "major_pose_failure_intervals", "throwing_arm_occlusion_intervals")}
    labels.update({key: [{"start_frame": 0, "end_frame": 2, "status": "reliable", "reason": "actual review", "confidence": None}]
                   for key in export.FULL_JOINT_LABELS})
    labels.update({"pitcher_correctly_selected": True,
                   "pitcher_selection_review": {"status": "annotated", "note": "reviewed", "confidence": None},
                   "events": {key: {"status": "uncertain", "frame_index": None, "confidence": None, "note": "unresolved"}
                              for key in ("preparation_start", "leg_lift", "foot_plant", "approximate_release", "follow_through_end")}})
    gt = {"schema_version": "ground-truth-v1", "annotation_status": "reviewed", "review_profile": "phase2_full_review",
          "source_video": {"pitch_id": "pitch_test", "filename": "source.mp4", "sha256": "0" * 64, "total_frames": total, "frame_index_base": 0},
          "provenance": {"reviewer": "human", "reviewed_at_utc": "2026-10-07T00:00:00Z", "method": "manual_video_review", "guidelines_version": "ground-truth-guidelines-v1"},
          "labels": labels, "notes": []}
    manifest = {"pitch_id": "pitch_test", "pitcher": {"id": "test", "throws": "RIGHT"}, "video": {"file": "source.mp4"}}
    raw = {"pitch_id": "pitch_test", "pitcher_id": "test", "coordinate_system": "normalized_image_xy;", "frames": []}
    processed = []
    for i in range(total):
        points = [{"name": name, "x": .4, "y": .5} for name in roles.values()]
        raw["frames"].append({"frame_index": i, "timestamp_ms": i * 1000 / 30, "detected": True, "landmarks": points})
        clean = {name: {"x": .4, "y": .5, "usable": True, "quality_valid": True, "interpolated": False} for name in roles.values()}
        clean["RIGHT_WRIST"].update({"usable": i != 2, "quality_valid": i == 0, "interpolated": i == 1})
        processed.append({"frame_index": i, "timestamp_ms": i * 1000 / 30, "landmarks": clean})
    pose = {"pitch_id": "pitch_test", "pitcher_id": "test", "total_frames": total,
            "frame_indices": [0, 1, 2], "important_joints": roles, "status": "provisional",
            "source_artifacts": {"pose_clean_sha256": "1" * 64},
            "joints": {name: {"frame_states": ["observed"] * total, "status": "provisional"} for name in roles.values()}}
    pose["joints"]["RIGHT_WRIST"]["frame_states"] = ["observed", "interpolated", "missing"]
    tracking = {"pitch_id": "pitch_test", "pitcher_id": "test", "total_frames": total, "status": "provisional", "identity_switch_confirmed": None,
                "frames": [{"frame_index": i, "selection_status": "selected", "warnings": []} for i in range(total)]}
    source_spec = {key: {"path": key, "sha256": "0" * 64} for key in export.REQUIRED_SOURCES}
    source_spec["pose_clean"]["sha256"] = "1" * 64
    spec = {"pitch_id": "pitch_test", "sources": source_spec}
    sources = {key: Path(key) for key in export.REQUIRED_SOURCES}
    sources["original_video"] = Path("source.mp4")
    sources["processed_keypoints"] = Mock()
    sources["processed_keypoints"].read_text.return_value = "\n".join(json.dumps(frame) for frame in processed)
    payloads = {sources["ground_truth"]: gt, sources["raw_keypoints"]: raw,
                sources["video_metadata"]: {"frame_count": total, "sha256": "0" * 64, "timestamps_ms": [i * 1000 / 30 for i in range(total)]},
                sources["input_metadata"]: manifest, sources["input_manifest"]: deepcopy(manifest),
                sources["pose_reliability"]: pose, sources["tracking_reliability"]: tracking}
    return spec, sources, payloads


class ReviewedExportTests(unittest.TestCase):
    def test_inclusive_interval_join_has_no_boundary_leak_or_missing_label(self):
        intervals = [{"start_frame": 0, "end_frame": 1, "status": "reliable", "reason": "reviewed"},
                     {"start_frame": 2, "end_frame": 3, "status": "unreliable", "reason": "wrong"}]
        self.assertEqual(export.lookup_joint(intervals, 1)["status"], "reliable")
        self.assertEqual(export.lookup_joint(intervals, 2)["interval_index"], 1)
        self.assertEqual(export.lookup_joint(intervals, 3)["reason"], "wrong")
        for frame in (-1, 4):
            with self.assertRaises(ValueError):
                export.lookup_joint(intervals, frame)
        with self.assertRaises(ValueError):
            export.lookup_joint(intervals + [intervals[1]], 2)

    def test_hidden_is_unverifiable_not_confirmed_wrong_or_known_occlusion(self):
        hidden = export.disposition("not_observable", "observed", human_frame())
        self.assertEqual(hidden["status"], "hold_raw_not_observable")
        self.assertEqual(hidden["restrictions"], ["human_raw_not_observable"])
        self.assertEqual(hidden["processed_coordinate_review"], "not_reviewed")
        uncertain = export.disposition("uncertain", "observed", human_frame())
        self.assertEqual(uncertain["status"], "hold_raw_uncertain")

    def test_raw_reliable_does_not_certify_interpolation_or_replace_missing(self):
        interpolated = export.disposition("reliable", "interpolated", human_frame())
        self.assertEqual(interpolated["status"], "unverified_processed_interpolation")
        self.assertEqual(interpolated["processed_coordinate_review"], "not_reviewed")
        missing = export.disposition("reliable", "missing", human_frame())
        self.assertEqual(missing["status"], "unavailable_missing")
        observed = export.disposition("reliable", "observed", human_frame())
        self.assertEqual(observed["status"], "reviewed_raw_observation")
        self.assertIn("qualitative", observed["processed_coordinate_review"])

    def test_major_failure_hold_does_not_invent_identity_switch_or_wrong_every_joint(self):
        frame = human_frame()
        frame["major_pose_failure"] = [{"start_frame": 87, "end_frame": 104, "reason": "shifted"}]
        result = export.disposition("reliable", "observed", frame)
        self.assertEqual(result["status"], "hold_frame_review")
        self.assertEqual(result["restrictions"], ["human_confirmed_major_pose_failure"])
        self.assertEqual(frame["identity_switch"], [])
        self.assertEqual(result["processed_coordinate_review"], "qualitative_same_coordinate_as_reviewed_raw")

    def test_unconfirmed_interval_and_unknown_subject_are_preserved_conservatively(self):
        frame = human_frame()
        frame["major_pose_failure"] = [{"status": "uncertain"}]
        self.assertFalse(export.confirmed(frame["major_pose_failure"]))
        self.assertEqual(export.disposition("reliable", "observed", frame)["status"], "reviewed_raw_observation")
        frame["pitcher_correctly_selected"] = None
        result = export.disposition("reliable", "observed", frame)
        self.assertEqual(result["status"], "hold_frame_review")
        self.assertEqual(result["restrictions"], ["subject_review_does_not_confirm_pitcher"])

    def test_saved_state_requires_observed_same_raw_coordinate_and_keeps_outside_xy(self):
        raw = {"x": 1.2, "y": .4}
        point = {"x": 1.2, "y": .4, "usable": True, "interpolated": False, "quality_valid": True}
        self.assertEqual(export.saved_state(point, {"detected": True}, raw), "observed")
        changed = {**point, "x": 1.3}
        with self.assertRaises(ValueError):
            export.saved_state(changed, {"detected": True}, raw)
        self.assertEqual(export.saved_state({**changed, "interpolated": True}, {"detected": False}, None), "interpolated")
        self.assertEqual(export.saved_state({**point, "usable": False}, {"detected": True}, raw), "missing")
        with self.assertRaises(ValueError):
            export.saved_state({**point, "x": float("nan")}, {"detected": True}, raw)

    def test_roles_derive_from_handedness_not_pitcher_identity(self):
        self.assertEqual(export.role_mapping("RIGHT")["throwing_elbow"], "RIGHT_ELBOW")
        self.assertEqual(export.role_mapping("LEFT")["throwing_elbow"], "LEFT_ELBOW")
        self.assertEqual(export.role_mapping("LEFT")["lead_ankle"], "RIGHT_ANKLE")
        with self.assertRaises(ValueError):
            export.role_mapping("UNKNOWN")

    def test_source_hash_binding_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "source.json"
            path.write_text("{}", encoding="utf-8")
            record = {"path": "source.json", "sha256": export.sha256(path)}
            self.assertEqual(export.bound_path(root, record), path)
            path.write_text('{"changed": true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                export.bound_path(root, record)
            with self.assertRaises(FileExistsError):
                export.write_new(path, {})
            with self.assertRaises(FileExistsError):
                export.run(root / "no_plan.json", root)

    def test_reviewed_uncertain_events_are_valid_but_template_is_never_truth(self):
        # Full validation fixture is independent of local ignored baseline files.
        labels = {key: [] for key in ("identity_switch_intervals", "track_break_intervals", "major_pose_failure_intervals", "throwing_arm_occlusion_intervals")}
        labels.update({key: [{"start_frame": 0, "end_frame": 1, "status": "reliable", "reason": "reviewed", "confidence": None}]
                       for key in export.FULL_JOINT_LABELS})
        labels.update({"pitcher_correctly_selected": True,
                       "pitcher_selection_review": {"status": "annotated", "note": "reviewed", "confidence": None},
                       "events": {key: {"status": "uncertain", "frame_index": None, "confidence": None, "note": "unresolved"}
                                  for key in ("preparation_start", "leg_lift", "foot_plant", "approximate_release", "follow_through_end")}})
        gt = {"schema_version": "ground-truth-v1", "annotation_status": "reviewed", "review_profile": "phase2_full_review",
              "source_video": {"pitch_id": "pitch_test", "filename": "pitch_test.mp4", "sha256": "0" * 64, "total_frames": 2, "frame_index_base": 0},
              "provenance": {"reviewer": "human", "reviewed_at_utc": "2026-10-07T00:00:00Z", "method": "manual_video_review", "guidelines_version": "ground-truth-guidelines-v1"},
              "labels": labels, "notes": []}
        export.validate_review(gt)
        original = deepcopy(gt)
        for status in ("in_progress", "unreviewed"):
            gt["annotation_status"] = status
            with self.assertRaises(ValueError):
                export.validate_review(gt)
        gt = deepcopy(original)
        del gt["labels"]["throwing_shoulder_reliability"]
        with self.assertRaises(ValueError):
            export.validate_review(gt)
        self.assertEqual(original["labels"]["events"]["leg_lift"]["status"], "uncertain")

    def test_derived_view_retains_all_frames_sources_uncertainty_and_original_states(self):
        spec, sources, payloads = fixture()
        snapshot = deepcopy(payloads)
        with patch.object(export, "read_json", side_effect=lambda path: payloads[path]):
            view = export.derive_clip(spec, sources)
        self.assertEqual(view["summary"]["total_frames"], 3)
        self.assertEqual(view["summary"]["focus_joint_rows"], 18)
        self.assertEqual(view["summary"]["human_joint_status_counts"], {"reliable": 18})
        self.assertEqual(view["events_as_reviewed"]["leg_lift"]["status"], "uncertain")
        self.assertEqual(view["frames"][1]["focus_joints"]["throwing_wrist"]["model_state"], "interpolated")
        self.assertEqual(view["frames"][2]["focus_joints"]["throwing_wrist"]["use_disposition"]["status"], "unavailable_missing")
        self.assertEqual(payloads, snapshot)

    def test_derivation_rejects_mixed_video_identity_handedness_and_saved_state(self):
        mutations = [
            lambda s, p: p[s["ground_truth"]]["source_video"].update(sha256="2" * 64),
            lambda s, p: p[s["raw_keypoints"]].update(pitch_id="other"),
            lambda s, p: p[s["input_manifest"]]["pitcher"].update(throws="LEFT"),
            lambda s, p: p[s["pose_reliability"]]["joints"]["RIGHT_WRIST"]["frame_states"].__setitem__(1, "observed"),
        ]
        for mutate in mutations:
            spec, sources, payloads = fixture()
            mutate(sources, payloads)
            with patch.object(export, "read_json", side_effect=lambda path: payloads[path]):
                with self.assertRaises(ValueError):
                    export.derive_clip(spec, sources)

    def test_derivation_rejects_duplicate_frame_or_timestamp_drift(self):
        for field, value in (("frame_index", 0), ("timestamp_ms", 34)):
            spec, sources, payloads = fixture()
            payloads[sources["raw_keypoints"]]["frames"][1][field] = value
            with patch.object(export, "read_json", side_effect=lambda path: payloads[path]):
                with self.assertRaises(ValueError):
                    export.derive_clip(spec, sources)


if __name__ == "__main__":
    unittest.main()
