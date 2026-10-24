"""Saved event comparisons retain human uncertainty and unmodified model curves."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_analysis_input as fixtures

from pitch_analysis.analysis.native_motion_events import describe_events, write_event_comparison
from pitch_analysis.analysis.native_motion_report import write_native_motion
from pitch_analysis.cli import main
from pitch_analysis.ground_truth import EVENT_NAMES, blank_ground_truth, validate_ground_truth
from pitch_analysis.native_pose_io import read_json, reference, write_json


def exact(frame, *, note="Human event", confidence=None):
    return {"status": "annotated", "frame_index": frame,
            "confidence": confidence, "note": note}


def ranged(first, last, *, status="annotated", note="Human uncertainty interval"):
    return {"status": status, "frame_index": None,
            "frame_range": {"start_frame": first, "end_frame": last},
            "confidence": None, "note": note}


def rows(count=8):
    return [{"frame_index": index, "timestamp_sec": float(Fraction(index * 1001, 60000)),
             "pointwise_reliability": "unknown",
             **{f"{role}_{field}": value for role in ("throwing_elbow", "lead_knee")
                for field, value in (("model_xy_deg", 10. + index),
                                     ("coordinate_status", "calculated_from_model_xy"),
                                     ("usable_deg", None))}}
            for index in range(count)]


class NativeMotionEventMathTests(unittest.TestCase):
    def events(self):
        return {"preparation_start": exact(0), "leg_lift": ranged(1, 2),
                "foot_plant": ranged(3, 4), "approximate_release": ranged(4, 5),
                "follow_through_end": ranged(6, 7)}

    def test_hand_calculated_interval_differences_and_fractional_seconds(self):
        fps = Fraction(60000, 1001)
        result = describe_events(self.events(), fps, rows())
        expected = {"preparation_to_leg_lift": [1, 2],
                    "leg_lift_to_foot_plant": [1, 3],
                    "foot_plant_to_release": [0, 2],
                    "release_to_follow_through_end": [1, 3]}
        for name, bounds in expected.items():
            with self.subTest(timing=name):
                timing = result["timing"][name]
                self.assertEqual(timing["status"], "bounded")
                self.assertEqual(timing["frame_bounds"], bounds)
                self.assertEqual(timing["seconds_bounds"],
                                 [float(Fraction(value) / fps) for value in bounds])
        event = result["events"]["approximate_release"]
        self.assertEqual(event["frame_bounds"], [4, 5])
        self.assertEqual(event["time_bounds_sec"], [float(Fraction(value) / fps) for value in (4, 5)])
        self.assertEqual(event["marker_kind"], "range")
        self.assertIsNone(event["frame_index"])

    def test_exact_events_keep_exact_timing_and_zero_origin(self):
        events = {name: exact(frame) for name, frame in zip(EVENT_NAMES, [0, 1, 2, 4, 7], strict=True)}
        result = describe_events(events, Fraction(30, 1), rows())
        self.assertEqual(result["events"]["preparation_start"]["time_bounds_sec"], [0., 0.])
        self.assertEqual(result["events"]["preparation_start"]["marker_kind"], "exact")
        timing = result["timing"]["foot_plant_to_release"]
        self.assertEqual(timing["status"], "exact")
        self.assertEqual(timing["frame_bounds"], [2, 2])
        self.assertEqual(timing["seconds_bounds"], [2 / 30, 2 / 30])

    def test_single_frame_human_range_remains_a_range_not_an_exact_mark(self):
        events = self.events()
        events["leg_lift"] = ranged(2, 2)
        result = describe_events(events, Fraction(30), rows())
        event = result["events"]["leg_lift"]
        self.assertEqual(event["marker_kind"], "range")
        self.assertIsNone(event["frame_index"])
        self.assertEqual(event["frame_range"], {"start_frame": 2, "end_frame": 2})
        self.assertEqual(event["frame_bounds"], [2, 2])
        self.assertEqual(event["angle_windows"]["throwing_elbow"]["total_frames"], 1)

    def test_uncertain_candidate_is_preserved_but_not_used_for_timing_or_angles(self):
        events = self.events()
        events["leg_lift"] = ranged(2, 2, status="uncertain", note="A candidate, not an exact judgment")
        events["leg_lift"]["confidence"] = .3
        result = describe_events(events, Fraction(30), rows())
        event = result["events"]["leg_lift"]
        for field, value in events["leg_lift"].items():
            self.assertEqual(event[field], value)
        self.assertEqual(event["marker_kind"], "uncertain")
        self.assertEqual(event["frame_bounds"], [2, 2])
        self.assertEqual(event["time_bounds_sec"], [2 / 30, 2 / 30])
        for role in ("throwing_elbow", "lead_knee"):
            window = event["angle_windows"][role]
            self.assertEqual(window["status"], "unavailable")
            for field in ("total_frames", "calculated_frames", "missing_frames", "degenerate_frames",
                          "min_deg", "max_deg", "usable_deg"):
                self.assertIsNone(window[field])
        for name in ("preparation_to_leg_lift", "leg_lift_to_foot_plant"):
            self.assertEqual(result["timing"][name]["status"], "unavailable")
            self.assertIsNone(result["timing"][name]["frame_bounds"])
            self.assertIsNone(result["timing"][name]["seconds_bounds"])
            self.assertTrue(result["timing"][name]["reason"])

    def test_unobservable_and_legacy_not_visible_keep_the_original_status(self):
        for status in ("not_observable", "not_visible"):
            with self.subTest(status=status):
                events = self.events()
                events["preparation_start"] = {"status": status, "frame_index": None,
                                                "confidence": None, "note": "Before clip start"}
                result = describe_events(events, Fraction(30), rows())
                event = result["events"]["preparation_start"]
                self.assertEqual(event["status"], status)
                self.assertEqual(event["marker_kind"], "not_observable")
                self.assertIsNone(event["frame_bounds"])
                self.assertIsNone(event["time_bounds_sec"])
                self.assertEqual(result["timing"]["preparation_to_leg_lift"]["status"], "unavailable")

    def test_windows_keep_missing_and_degenerate_in_the_full_inclusive_denominator(self):
        events, values = self.events(), rows()
        events["leg_lift"] = ranged(1, 3)
        values[2].update(throwing_elbow_model_xy_deg=None,
                         throwing_elbow_coordinate_status="missing_coordinates")
        values[3].update(throwing_elbow_model_xy_deg=None,
                         throwing_elbow_coordinate_status="degenerate_geometry")
        event = describe_events(events, Fraction(30), values)["events"]["leg_lift"]
        elbow, knee = event["angle_windows"]["throwing_elbow"], event["angle_windows"]["lead_knee"]
        self.assertEqual(elbow["status"], "descriptive_model_xy_window")
        self.assertEqual([elbow[name] for name in ("total_frames", "calculated_frames", "missing_frames",
                                                 "degenerate_frames")], [3, 1, 1, 1])
        self.assertEqual((elbow["min_deg"], elbow["max_deg"]), (11., 11.))
        self.assertEqual([knee[name] for name in ("total_frames", "calculated_frames", "missing_frames",
                                                "degenerate_frames")], [3, 3, 0, 0])
        self.assertIsNone(elbow["usable_deg"])
        self.assertIsNone(knee["usable_deg"])

    def test_describing_and_mutating_the_result_cannot_change_human_labels_or_curves(self):
        events, values = self.events(), rows()
        before_events, before_values = deepcopy(events), deepcopy(values)
        result = describe_events(events, Fraction(30), values)
        for name, source in events.items():
            for field, value in source.items():
                self.assertEqual(result["events"][name][field], value)
        result["events"]["leg_lift"]["frame_range"]["start_frame"] = 999
        result["events"]["preparation_start"]["note"] = "changed output"
        self.assertEqual(events, before_events)
        self.assertEqual(values, before_values)


class NativeMotionEventExportTests(unittest.TestCase):
    def fixture(self, root):
        helper = fixtures.NativeAnalysisInputTests()
        data = helper.fixture(root)
        helper.prepare(data)
        motion = root / "analysis_results" / "motion"
        # Plot rendering is covered by the motion-export tests. This fixture only
        # needs its saved artifact and SHA; event comparison must not redraw it.
        with patch("pitch_analysis.analysis.native_motion_report._plot",
                   side_effect=lambda _rows, _id, path: path.write_bytes(b"saved plot fixture")):
            write_native_motion(root, data["output"], motion)
        truth = blank_ground_truth(data["video"], "pitch_fixture", 3)
        truth.update(annotation_status="reviewed")
        truth["provenance"].update(reviewer="Human fixture", reviewed_at_utc="2026-10-24T00:00:00Z")
        truth["labels"].update(
            pitcher_correctly_selected=True, identity_switch_intervals=[], major_pose_failure_intervals=[],
            throwing_elbow_reliability=[{"start_frame": 0, "end_frame": 2, "status": "unreliable",
                                         "confidence": None, "reason": "Historical model label only"}],
            lead_knee_reliability=[{"start_frame": 0, "end_frame": 2, "status": "reliable",
                                   "confidence": None, "reason": "Historical model label only"}],
            events={name: exact(frame) for name, frame in zip(EVENT_NAMES, [0, 0, 1, 1, 2], strict=True)})
        validate_ground_truth(truth, source_video_path=data["video"])
        truth_path = root / "ground_truth.json"
        write_json(truth_path, truth)
        request = {"schema_version": "native-motion-events-request-v1", "pitcher_id": "fixture_pitcher",
                   "clips": [{"pitch_id": "pitch_fixture", "motion_dir": motion.relative_to(root).as_posix(),
                              "ground_truth_ref": reference(root, truth_path)}]}
        request_path = root / "request.json"
        write_json(request_path, request)
        return {**data, "motion": motion, "truth": truth, "truth_path": truth_path,
                "request": request, "request_path": request_path,
                "comparison": root / "analysis_results" / "events"}

    @staticmethod
    def refresh(data):
        fixtures.NativeAnalysisInputTests.json(data["truth_path"], data["truth"])
        data["request"]["clips"][0]["ground_truth_ref"] = reference(data["root"], data["truth_path"])
        fixtures.NativeAnalysisInputTests.json(data["request_path"], data["request"])

    def test_one_clip_export_uses_saved_curves_without_models_recalculation_or_source_writes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with patch("subprocess.Popen", side_effect=AssertionError("no model process or browser")), \
                 patch("cv2.VideoCapture", side_effect=AssertionError("no video decoding")), \
                 patch("pitch_analysis.analysis.native_motion_report.describe_native_motion",
                       side_effect=AssertionError("use saved angles, do not recalculate")):
                summary = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            self.assertEqual(summary["status"], "event_comparison_created")
            self.assertEqual((summary["clip_count"], summary["source_frames"]), (1, 3))
            self.assertFalse(summary["angle_values_recomputed"])
            self.assertEqual(summary["new_inference_calls"], 0)
            self.assertEqual(summary["new_ground_truth_labels"], 0)
            self.assertEqual(summary["quality_status"], "not_calibrated")
            self.assertIsNone(summary["usable_for_analysis"])
            self.assertEqual(read_json(data["comparison"] / "event_comparison.json"), summary)
            self.assertTrue((data["comparison"] / "event_timing.csv").is_file())
            self.assertTrue((data["comparison"] / "report.md").is_file())
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_unreviewed_or_in_progress_ground_truth_cannot_supply_events(self):
        for status in ("unreviewed", "in_progress"):
            with self.subTest(status=status), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                if status == "unreviewed":
                    data["truth"] = blank_ground_truth(data["video"], "pitch_fixture", 3)
                else:
                    data["truth"].update(annotation_status="in_progress")
                    data["truth"]["provenance"]["reviewed_at_utc"] = None
                self.refresh(data)
                with self.assertRaises(ValueError):
                    write_event_comparison(data["root"], data["request_path"], data["comparison"])
                self.assertFalse(data["comparison"].exists())

    def test_ground_truth_must_match_pitch_frame_count_filename_video_sha_and_zero_origin(self):
        changes = {"pitch_id": "some_other_clip", "total_frames": 4, "filename": "another.mp4",
                   "sha256": "f" * 64, "frame_index_base": 1}
        for field, value in changes.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                data["truth"]["source_video"][field] = value
                self.refresh(data)
                with self.assertRaises(ValueError):
                    write_event_comparison(data["root"], data["request_path"], data["comparison"])
                self.assertFalse(data["comparison"].exists())

    def test_changed_ground_truth_bytes_or_saved_curves_are_rejected(self):
        for changed in ("ground_truth", "curves"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                path = data["truth_path"] if changed == "ground_truth" else data["motion"] / "motion_curves.csv"
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("\n")
                with self.assertRaises(ValueError):
                    write_event_comparison(data["root"], data["request_path"], data["comparison"])
                self.assertFalse(data["comparison"].exists())

    def test_wrong_pitcher_or_duplicate_clips_are_rejected(self):
        for changed in ("pitcher", "duplicate", "clip_id"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                if changed == "pitcher":
                    data["request"]["pitcher_id"] = "different_pitcher"
                elif changed == "duplicate":
                    data["request"]["clips"].append(deepcopy(data["request"]["clips"][0]))
                else:
                    data["request"]["clips"][0]["pitch_id"] = "different_clip"
                fixtures.NativeAnalysisInputTests.json(data["request_path"], data["request"])
                with self.assertRaises(ValueError):
                    write_event_comparison(data["root"], data["request_path"], data["comparison"])
                self.assertFalse(data["comparison"].exists())

    def test_existing_or_non_analysis_output_is_rejected_without_overwriting(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            data["comparison"].mkdir()
            sentinel = data["comparison"] / "keep.txt"
            sentinel.write_text("preserve existing result", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_event_comparison(data["root"], data["request_path"], data["comparison"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve existing result")
            outside = data["root"] / "not_analysis_results"
            with self.assertRaises(ValueError):
                write_event_comparison(data["root"], data["request_path"], outside)
            self.assertFalse(outside.exists())

    def test_request_or_ground_truth_outside_project_is_rejected(self):
        for changed in ("request", "ground_truth"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                container = Path(temp)
                root = container / "project"
                root.mkdir()
                data = self.fixture(root)
                external = container / "outside.json"
                if changed == "request":
                    write_json(external, data["request"])
                    data["request_path"] = external
                else:
                    write_json(external, data["truth"])
                    data["request"]["clips"][0]["ground_truth_ref"] = {
                        "path": "../outside.json", "sha256": reference(container, external)["sha256"]}
                    fixtures.NativeAnalysisInputTests.json(data["request_path"], data["request"])
                with self.assertRaises(ValueError):
                    write_event_comparison(root, data["request_path"], data["comparison"])
                self.assertFalse(data["comparison"].exists())


class NativeMotionEventCliTests(unittest.TestCase):
    def test_cli_only_dispatches_the_saved_event_comparison(self):
        with patch("sys.argv", ["pitch-analysis", "compare-native-motion-events", "request.json",
                                "--output", "analysis_results/events"]), \
             patch("pitch_analysis.analysis.native_motion_events.write_event_comparison",
                   return_value={"status": "event_comparison_created", "clip_count": 4,
                                 "source_frames": 477}) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose inference")), \
             redirect_stdout(StringIO()) as output:
            main()
        writer.assert_called_once_with(Path.cwd(), "request.json", "analysis_results/events")
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "event_comparison_created")
        self.assertEqual((result["clip_count"], result["source_frames"]), (4, 477))
        self.assertEqual(result["new_inference_calls"], 0)

    def test_cli_rejects_failed_source_with_nonzero_exit_without_pose(self):
        with patch("sys.argv", ["pitch-analysis", "compare-native-motion-events", "bad.json",
                                "--output", "analysis_results/events"]), \
             patch("pitch_analysis.analysis.native_motion_events.write_event_comparison",
                   side_effect=ValueError("source mismatch")), \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose inference")), \
             redirect_stdout(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(output.getvalue()), {"status": "failed", "error": "source mismatch"})


if __name__ == "__main__":
    unittest.main()
