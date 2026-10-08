"""Saved cue exposure must not invent confidence, identity or wider intervals."""
from copy import deepcopy
import csv
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("existing_cues", Path(__file__).resolve().parents[1] / "scripts/export_existing_reliability_cues.py")
cues = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cues)


def fixture():
    total = 12
    mapping = cues.role_mapping("RIGHT")
    meta = {"frame_count": total, "width": 800, "height": 800, "fps": 30., "timestamps_ms": [i * 1000 / 30 for i in range(total)]}
    pose = {"pitch_id": "pitch_test", "pitcher_id": "subject_test", "status": "partially_reliable", "reasons": ["saved signal reason"], "total_frames": total,
            "frame_indices": list(range(total)), "important_joints": mapping, "policy": {"status": "provisional", "jump_candidate": "cached whole-clip median + 6 MAD; floor 0.05"}, "joints": {}}
    records = []
    for i, ts in enumerate(meta["timestamps_ms"]):
        records.append({"frame_index": i, "timestamp_ms": ts, "landmarks": {name: {"x": .6 if role == "throwing_elbow" and i == 6 else .2, "y": .4, "usable": True, "interpolated": False, "quality_valid": True} for role, name in mapping.items()}})
    for role, name in mapping.items():
        has_jump = role == "throwing_elbow"
        pose["joints"][name] = {"frame_states": ["observed"] * total, "status": "partially_reliable" if has_jump else "reliable",
                                "frame_to_frame_jump": {"unit": "image_height_per_adjacent_frame", "observed_adjacent_pairs": 11, "median": 0., "median_absolute_deviation": 0., "max": .4 if has_jump else 0., "candidate_threshold": .05, "candidate_frames": [6, 7] if has_jump else [], "candidate_count": 2 if has_jump else 0}}
    tracking = {"pitch_id": "pitch_test", "pitcher_id": "subject_test", "status": "reliable", "reasons": [], "total_frames": total,
                "selected_frames": total, "track_breaks": [], "warning_events": [], "identity_switch_warning": False, "identity_switch_confirmed": None,
                "frames": [{"frame_index": i, "selection_status": "selected", "warnings": []} for i in range(total)]}
    return pose, tracking, meta, records


class ExistingCueTests(unittest.TestCase):
    def test_current_endpoints_only_with_complete_timeline_and_no_accuracy_claim(self):
        args = fixture()
        before = deepcopy(args)
        result = cues.build_cues(*args)
        self.assertEqual(args, before)
        self.assertEqual(result["summary"]["focus_joint_rows"], 72)
        self.assertEqual(result["summary"]["jump_endpoint_events"], 2)
        self.assertEqual(result["summary"]["unique_cued_frames"], 2)
        self.assertEqual([e["frame_index"] for e in result["jump_events"]], [6, 7])
        self.assertEqual(result["jump_events"][0]["from_frame_index"], 5)
        self.assertEqual(result["frames"][5]["focus_joints"]["throwing_elbow"]["jump"]["state"], "no_saved_jump_candidate")
        self.assertEqual(result["automatic_coordinate_alignment"], "unverified")
        self.assertEqual(result["automatic_subject_identity"], "unverified")
        self.assertFalse(result["human_labels_used"])

    def test_zero_measured_displacement_and_first_frame_unmeasured_are_distinct(self):
        result = cues.build_cues(*fixture())
        first = result["frames"][0]["focus_joints"]["lead_knee"]["jump"]
        measured = result["frames"][1]["focus_joints"]["lead_knee"]["jump"]
        self.assertEqual(first["state"], "jump_not_measured")
        self.assertIsNone(first["displacement"])
        self.assertIsNone(first["from_frame_index"])
        self.assertEqual(measured["state"], "no_saved_jump_candidate")
        self.assertEqual(measured["displacement"], 0.)
        self.assertEqual(result["summary"]["observed_adjacent_pairs"], 66)

    def test_interpolation_excludes_both_adjacent_transitions_without_filling_cues(self):
        pose, tr, meta, records = fixture()
        name = pose["important_joints"]["throwing_elbow"]
        pose["joints"][name]["frame_states"][5] = "interpolated"
        records[5]["landmarks"][name].update(interpolated=True, quality_valid=False)
        jump = pose["joints"][name]["frame_to_frame_jump"]
        jump.update(observed_adjacent_pairs=9, candidate_frames=[7], candidate_count=1)
        result = cues.build_cues(pose, tr, meta, records)
        self.assertEqual(result["frames"][5]["focus_joints"]["throwing_elbow"]["model_state"], "interpolated")
        self.assertEqual(result["frames"][6]["focus_joints"]["throwing_elbow"]["jump"]["state"], "jump_not_measured")
        self.assertEqual([e["frame_index"] for e in result["jump_events"]], [7])

    def test_all_missing_has_null_statistics_and_no_false_good_frames(self):
        pose, tr, meta, records = fixture()
        for name, joint in pose["joints"].items():
            joint["frame_states"] = ["missing"] * 12
            joint["frame_to_frame_jump"].update(observed_adjacent_pairs=0, median=None, median_absolute_deviation=None, max=None, candidate_threshold=None, candidate_count=0, candidate_frames=[])
            for record in records:
                record["landmarks"][name].update(x=None, y=None, usable=False, quality_valid=False)
        report = cues.build_cues(pose, tr, meta, records)
        self.assertEqual(report["summary"]["jump_state_counts"], {"jump_not_measured": 72})
        self.assertTrue(all(f["automatic_coordinate_alignment"] == "unverified" for f in report["frames"]))

    def test_original_aspect_ratio_changes_displacement_and_cached_policy_must_match(self):
        pose, tr, meta, records = fixture()
        meta["width"] = 400
        with self.assertRaises(ValueError):
            cues.build_cues(pose, tr, meta, records)
        name = pose["important_joints"]["throwing_elbow"]
        pose["joints"][name]["frame_to_frame_jump"]["max"] = .2
        report = cues.build_cues(pose, tr, meta, records)
        self.assertAlmostEqual(report["jump_events"][0]["displacement"], .2)

    def test_cached_counts_thresholds_candidates_and_max_are_independently_rejected(self):
        for key, changed in (("observed_adjacent_pairs", 10), ("candidate_threshold", .06), ("candidate_frames", [5, 6, 7]), ("candidate_count", 3), ("median", .02), ("median_absolute_deviation", .01), ("max", .5)):
            args = fixture()
            name = args[0]["important_joints"]["throwing_elbow"]
            args[0]["joints"][name]["frame_to_frame_jump"][key] = changed
            with self.assertRaises(ValueError, msg=key):
                cues.build_cues(*args)

    def test_timeline_and_original_timebase_mismatches_are_rejected(self):
        for mutate in (lambda a: a[3].pop(), lambda a: a[3][1].update(frame_index=0), lambda a: a[3][1].update(timestamp_ms=33.), lambda a: a[2].update(frame_count=11), lambda a: a[0]["frame_indices"].reverse()):
            args = fixture()
            mutate(args)
            with self.assertRaises(ValueError):
                cues.build_cues(*args)

    def test_mixed_subject_handedness_and_state_provenance_fail_closed(self):
        for mutate in (lambda a: a[1].update(pitcher_id="different"), lambda a: a[1].update(pitch_id="different"),
                       lambda a: a[0]["important_joints"].update(lead_knee="RIGHT_KNEE"),
                       lambda a: a[3][1]["landmarks"]["RIGHT_ELBOW"].update(quality_valid=False),
                       lambda a: a[3][1]["landmarks"]["RIGHT_ELBOW"].update(x=float("nan")),
                       lambda a: a[3][1]["landmarks"]["RIGHT_ELBOW"].update(interpolated=True)):
            args = fixture()
            mutate(args)
            with self.assertRaises(ValueError):
                cues.build_cues(*args)

    def test_tracking_warnings_rejections_and_provisional_signal_are_retained_separately(self):
        pose, tr, meta, records = fixture()
        tr["frames"][3]["selection_status"] = "rejected"
        tr["track_breaks"] = [{"start_frame": 3, "end_frame": 3, "length_frames": 1}]
        tr["selected_frames"] = 11
        tr["frames"][6]["warnings"] = ["body_center_jump"]
        tr["warning_events"] = [{"frame_index": 6, "type": "body_center_jump", "source_value": .5}]
        tr["identity_switch_warning"] = True
        result = cues.build_cues(pose, tr, meta, records)
        self.assertEqual(result["frames"][3]["existing_model_tracking"], tr["frames"][3])
        self.assertEqual(result["original_tracking_warning_events"], tr["warning_events"])
        self.assertEqual(result["original_signal_quality"]["pose"], "partially_reliable")
        self.assertEqual(result["automatic_subject_identity"], "unverified")
        tr["track_breaks"] = []
        with self.assertRaises(ValueError):
            cues.build_cues(pose, tr, meta, records)

    def test_warning_events_cannot_disagree_with_existing_frame_cues(self):
        args = fixture()
        args[1]["warning_events"] = [{"frame_index": 6, "type": "body_center_jump"}]
        with self.assertRaises(ValueError):
            cues.build_cues(*args)

    def test_clean_csv_requires_original_raw_equality_and_preserves_outside_image_xy(self):
        args = fixture()
        for r in args[3]:
            r["landmarks"]["LEFT_KNEE"]["x"] = 1.2
        report = cues.build_cues(*args)
        fields = ("frame", "landmark", "x", "y", "x_raw", "y_raw", "usable", "interpolated", "quality_valid", "source_frame_detected")
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path = Path(temp) / "clean.csv"
            def save(changed=False):
                with path.open("w", newline="", encoding="utf-8") as target:
                    writer = csv.DictWriter(target, fieldnames=fields)
                    writer.writeheader()
                    for f in report["frames"]:
                        for j in f["focus_joints"].values():
                            p = j["processed_landmark"]
                            writer.writerow({"frame": f["frame_index"], "landmark": j["landmark"], "x": p["x"], "y": p["y"], "x_raw": p["x"] + (.1 if changed else 0), "y_raw": p["y"], "usable": p["usable"], "interpolated": p["interpolated"], "quality_valid": p["quality_valid"], "source_frame_detected": True})
            save()
            cues.check_clean_csv(path, report)
            self.assertEqual(report["frames"][0]["focus_joints"]["lead_knee"]["processed_landmark"]["x"], 1.2)
            save(True)
            with self.assertRaises(ValueError):
                cues.check_clean_csv(path, report)

    def test_source_hash_mismatch_and_existing_output_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root = Path(temp)
            path = root / "source.json"
            path.write_text("{}", encoding="utf-8")
            record = {"path": str(path), "sha256": hashlib.sha256(b"{}").hexdigest()}
            self.assertEqual(cues.bound_path(record), path)
            path.write_text('{"changed":true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                cues.bound_path(record)
            with self.assertRaises(FileExistsError):
                cues.run(root / "missing_plan.json", root)

    def test_no_human_source_roles_are_allowed_before_any_export_is_created(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root = Path(temp)
            plan = root / "plan.json"
            data = {"schema_version": "existing-reliability-cue-plan-v1", "status": "frozen_before_export", "implementation": {"runner": {"path": str(Path(cues.__file__)), "sha256": cues.sha256(cues.__file__)}}, "clips": [{"pitch_id": "p", "sources": {"ground_truth": {"path": "forbidden", "sha256": "0" * 64}}}]}
            cues.write_new(plan, data)
            output = root / "new"
            with self.assertRaises(ValueError):
                cues.run(plan, output)
            self.assertFalse(output.exists())

    def test_panel_preserves_every_source_pixel_and_uses_neutral_no_cue_guidance(self):
        import numpy as np
        from PIL import ImageFont
        report = cues.build_cues(*fixture())
        source = np.arange(598 * 512 * 3, dtype=np.uint8).reshape(598, 512, 3)
        default_font = ImageFont.load_default()
        with patch.object(ImageFont, "truetype", return_value=default_font):
            output = cues.compose_frame(source, report["frames"][0], report, "unused")
        self.assertEqual(output.shape, (598, 972, 3))
        self.assertTrue(np.array_equal(source, output[:, :512]))
        self.assertFalse(np.array_equal(output[93:133, 512:972], np.zeros((40, 460, 3), dtype=np.uint8)))


if __name__ == "__main__":
    unittest.main()
