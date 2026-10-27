"""Stage curve ranges retain legal event choices, source frames and unknowns."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from fractions import Fraction
from html.parser import HTMLParser
from importlib.resources import files
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import test_native_descriptive_profile as profile_fixtures
import test_native_motion_events as event_fixtures
import test_native_profile_viewer as viewer_fixtures
import test_native_timing_comparison as timing_fixtures
from test_native_timing_viewer import HtmlData

from pitch_analysis.analysis.native_stage_curves import describe_stage_curves, write_stage_curves
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


ROLES = ("throwing_elbow", "lead_knee")
COUNTS = ("total_frames", "calculated_frames", "missing_frames", "degenerate_frames")
LISTS = ("min_frames", "max_frames", "min_seconds_fraction", "max_seconds_fraction")


def events():
    return {name: event_fixtures.exact(index) for name, index in (
        ("preparation_start", 0), ("leg_lift", 1), ("foot_plant", 3),
        ("approximate_release", 5), ("follow_through_end", 7))}


def record(result, timing_key="foot_plant_to_release", pitch_id="custom_001"):
    return next(row for row in result["records"] if row["pitch_id"] == pitch_id and row["timing_key"] == timing_key)


class StageCurveMathTests(unittest.TestCase):
    def test_exact_window_uses_interior_extrema_all_ties_and_original_fractional_time(self):
        values = event_fixtures.rows()
        for index, value in ((3, 10.), (4, 40.), (5, 10.)):
            values[index]["throwing_elbow_model_xy_deg"] = value
        for index, value in ((3, 50.), (4, 10.), (5, 60.)):
            values[index]["lead_knee_model_xy_deg"] = value
        clip = profile_fixtures.clip(fps="60000/1001", values=values)
        before = deepcopy(clip)
        result = describe_stage_curves([clip])
        self.assertEqual((result["clip_count"], result["source_frames"], result["stage_count"],
                          result["event_confirmed_stages"], result["event_unresolved_stages"],
                          result["joint_summary_count"]), (1, 8, 4, 4, 0, 8))
        stage = record(result)
        self.assertEqual(stage["status"], "descriptive_model_xy_stage_curve")
        self.assertEqual(stage["start_event"], clip["events"]["foot_plant"])
        self.assertEqual(stage["end_event"], clip["events"]["approximate_release"])
        self.assertEqual(stage["union_frame_bounds"], [3, 5])
        self.assertEqual(stage["common_frame_bounds"], [3, 5])
        elbow = stage["joints"]["throwing_elbow"]
        for window in (elbow["possible_window"], elbow["common_window"], elbow["intervals"][0]):
            self.assertEqual(tuple(window[key] for key in COUNTS), (3, 3, 0, 0))
            self.assertEqual((window["min_deg"], window["max_deg"], window["sample_span_deg"]), (10., 40., 30.))
            self.assertEqual(window["min_frames"], [3, 5])
            self.assertEqual(window["max_frames"], [4])
            self.assertEqual(window["min_seconds_fraction"], ["1001/20000", "1001/12000"])
            self.assertEqual(window["max_seconds_fraction"], ["1001/15000"])
            self.assertEqual(window["sample_span_scope"], "complete_window")
        knee = stage["joints"]["lead_knee"]["possible_window"]
        self.assertEqual((knee["min_frames"], knee["max_frames"], knee["sample_span_deg"]), ([4], [5], 50.))
        self.assertEqual(clip, before)

    def test_union_and_common_are_computed_after_excluding_nonchronological_endpoints(self):
        raw = events()
        raw["foot_plant"] = event_fixtures.ranged(4, 7)
        raw["approximate_release"] = event_fixtures.ranged(2, 4)
        stage = record(describe_stage_curves([profile_fixtures.clip(events=raw)]))
        self.assertEqual((stage["all_endpoint_pairs"], stage["chronological_pairs"],
                          stage["excluded_nonchronological_pairs"]), (12, 1, 11))
        self.assertEqual(stage["union_frame_bounds"], [4, 4])
        self.assertEqual(stage["common_frame_bounds"], [4, 4])
        for joint in stage["joints"].values():
            self.assertEqual([(item["start_frame"], item["end_frame"]) for item in joint["intervals"]], [(4, 4)])
            self.assertEqual(joint["common_window"]["total_frames"], 1)
            self.assertIsNone(joint["common_window"]["sample_span_deg"])

    def test_empty_common_intersection_has_zero_counts_and_no_extrema_not_unknown(self):
        raw = events()
        raw["foot_plant"] = event_fixtures.ranged(2, 4)
        raw["approximate_release"] = event_fixtures.ranged(3, 5)
        stage = record(describe_stage_curves([profile_fixtures.clip(events=raw)]))
        self.assertEqual((stage["all_endpoint_pairs"], stage["chronological_pairs"],
                          stage["excluded_nonchronological_pairs"]), (9, 8, 1))
        self.assertEqual(stage["union_frame_bounds"], [2, 5])
        self.assertIsNone(stage["common_frame_bounds"])
        for joint in stage["joints"].values():
            self.assertEqual(len(joint["intervals"]), 8)
            common = joint["common_window"]
            self.assertEqual(common["status"], "empty_intersection")
            self.assertEqual(tuple(common[key] for key in COUNTS), (0, 0, 0, 0))
            self.assertIsNone(common["frame_bounds"])
            self.assertEqual(tuple(common[key] for key in LISTS), ([], [], [], []))
            self.assertEqual(common["reading_kind"], "empty_window")
            self.assertEqual(common["sample_span_scope"], "not_assessable")
            self.assertIsNone(common["sample_span_deg"])
            self.assertIsNone(common["min_deg"])

    def test_uncertain_single_frame_candidate_never_becomes_a_window_or_pair(self):
        raw = events()
        raw["leg_lift"] = event_fixtures.ranged(1, 1, status="uncertain", note="Only a candidate")
        clip = profile_fixtures.clip(events=raw)
        result = describe_stage_curves([clip])
        self.assertEqual((result["event_confirmed_stages"], result["event_unresolved_stages"]), (2, 2))
        for key in ("preparation_to_leg_lift", "leg_lift_to_foot_plant"):
            stage = record(result, key)
            self.assertEqual(stage["status"], "unavailable")
            for name in ("all_endpoint_pairs", "chronological_pairs", "excluded_nonchronological_pairs",
                         "union_frame_bounds", "common_frame_bounds"):
                self.assertIsNone(stage[name])
            for joint in stage["joints"].values():
                self.assertEqual(joint["intervals"], [])
                for window in (joint["possible_window"], joint["common_window"]):
                    self.assertEqual(window["status"], "unavailable")
                    self.assertEqual(window["reading_kind"], "event_unresolved")
                    for name in (*COUNTS, *LISTS, "frame_bounds", "min_deg", "max_deg", "sample_span_deg"):
                        self.assertIsNone(window[name])
        self.assertEqual(result["records"][0]["end_event"], clip["events"]["leg_lift"])
        self.assertEqual(clip["events"]["leg_lift"]["frame_bounds"], [1, 1])

    def test_full_denominators_missing_degenerate_single_sample_and_true_zero_span(self):
        raw = events()
        raw["foot_plant"] = event_fixtures.exact(2)
        values = event_fixtures.rows()
        for index, state in ((2, "missing_coordinates"), (3, "degenerate_geometry"), (5, "missing_coordinates")):
            values[index]["throwing_elbow_coordinate_status"] = state
            values[index]["throwing_elbow_model_xy_deg"] = None
        for index in range(2, 6):
            values[index]["lead_knee_model_xy_deg"] = 7.
        stage = record(describe_stage_curves([profile_fixtures.clip(events=raw, values=values)]))
        elbow = stage["joints"]["throwing_elbow"]["possible_window"]
        self.assertEqual(tuple(elbow[key] for key in COUNTS), (4, 1, 2, 1))
        self.assertEqual((elbow["min_frames"], elbow["max_frames"]), ([4], [4]))
        self.assertIsNone(elbow["sample_span_deg"])
        self.assertEqual(elbow["sample_span_scope"], "not_assessable")
        knee = stage["joints"]["lead_knee"]["possible_window"]
        self.assertEqual(knee["sample_span_deg"], 0.)
        self.assertEqual((knee["min_frames"], knee["max_frames"]), ([2, 3, 4, 5], [2, 3, 4, 5]))
        for index in range(2, 6):
            values[index]["throwing_elbow_coordinate_status"] = "missing_coordinates"
            values[index]["throwing_elbow_model_xy_deg"] = None
        empty = record(describe_stage_curves([profile_fixtures.clip(events=raw, values=values)]))["joints"]["throwing_elbow"]["possible_window"]
        self.assertEqual(tuple(empty[key] for key in COUNTS), (4, 0, 4, 0))
        self.assertEqual(tuple(empty[key] for key in LISTS), ([], [], [], []))
        self.assertIsNone(empty["min_deg"])
        self.assertIsNone(empty["sample_span_deg"])

    def test_each_legal_interval_keeps_its_own_span_and_partial_sample_scope(self):
        raw = events()
        raw["foot_plant"] = event_fixtures.ranged(2, 3)
        raw["approximate_release"] = event_fixtures.ranged(4, 5)
        values = event_fixtures.rows()
        for index, value in ((2, 10.), (3, 20.), (4, 30.), (5, 5.)):
            values[index]["throwing_elbow_model_xy_deg"] = value
        clip = profile_fixtures.clip(events=raw, values=values)
        joint = record(describe_stage_curves([clip]))["joints"]["throwing_elbow"]
        self.assertEqual(joint["possible_window"]["frame_bounds"], [2, 5])
        self.assertEqual(joint["common_window"]["frame_bounds"], [3, 4])
        self.assertEqual([(row["start_frame"], row["end_frame"], row["sample_span_deg"]) for row in joint["intervals"]],
                         [(2, 4, 20.), (2, 5, 25.), (3, 4, 10.), (3, 5, 25.)])
        clip["rows"][4]["throwing_elbow_coordinate_status"] = "missing_coordinates"
        clip["rows"][4]["throwing_elbow_model_xy_deg"] = None
        partial = record(describe_stage_curves([clip]))["joints"]["throwing_elbow"]
        self.assertEqual(partial["possible_window"]["sample_span_scope"], "calculated_samples_only")
        self.assertEqual(partial["possible_window"]["calculated_frames"], 3)
        interval = next(row for row in partial["intervals"] if (row["start_frame"], row["end_frame"]) == (3, 4))
        self.assertEqual(interval["calculated_frames"], 1)
        self.assertIsNone(interval["sample_span_deg"])

    def test_no_chronological_interval_and_non_source_timeline_are_rejected(self):
        clip = profile_fixtures.clip()
        clip["events"]["foot_plant"].update(frame_bounds=[6, 6], frame_index=6)
        with self.assertRaises(ValueError):
            describe_stage_curves([clip])
        clip = profile_fixtures.clip()
        clip["rows"][0]["timestamp_sec"] = .1
        with self.assertRaises(ValueError):
            describe_stage_curves([clip])
        with self.assertRaises(ValueError):
            describe_stage_curves([])
        with self.assertRaises(ValueError):
            describe_stage_curves([profile_fixtures.clip(), profile_fixtures.clip()])


class Hrefs(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.hrefs = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(value for key, value in attrs if key == "href")


class StageCurveExportTests(unittest.TestCase):
    def fixture(self, root):
        data = viewer_fixtures.NativeProfileViewerTests().fixture(root)
        data["curves"] = root / "analysis_results" / "stage_curves"
        return data

    def run_export(self, data, output=None):
        with patch("pitch_analysis.analysis.native_timing_comparison.load_event_clips",
                   side_effect=lambda _root, request, _output: data["bundles"][Path(request).resolve()]), \
             patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
             patch("cv2.VideoCapture", side_effect=AssertionError("saved motion only")):
            return write_stage_curves(data["root"], data["reports"][0], data["curves"] if output is None else output)

    def test_source_bound_export_keeps_all_windows_intervals_frames_and_original_player(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before_files = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            before_bundle = deepcopy(data["bundle"])
            result = self.run_export(data)
            self.assertEqual((result["schema_version"], result["status"]), ("native-stage-curves-v1", "stage_curves_created"))
            self.assertEqual(result["pitcher_id"], "custom_pitcher_07")
            summary = result["summary"]
            self.assertEqual((summary["clip_count"], summary["source_frames"], summary["stage_count"],
                              summary["event_confirmed_stages"], summary["event_unresolved_stages"],
                              summary["joint_summary_count"]), (2, 16, 8, 6, 2, 16))
            self.assertEqual(result, read_json(data["curves"] / "stage_curves.json"))
            for filename, count in (("stage_windows.csv", 32), ("stage_intervals.csv", 12)):
                with (data["curves"] / filename).open(encoding="utf-8-sig", newline="") as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))), count)
            report = data["curves"] / "report.html"
            hrefs = Hrefs(report.read_text(encoding="utf-8")).hrefs
            frame_links = [urlsplit(href) for href in hrefs if urlsplit(href).fragment.startswith("frame=")]
            self.assertTrue(frame_links)
            for link in frame_links:
                self.assertIn(Path(unquote(link.path)).name, {"source_000.html", "source_001.html"})
                self.assertTrue((report.parent / unquote(link.path)).is_file())
                self.assertIn(link.fragment.split("&")[0], {f"frame={index}" for index in range(8)})
            for index, clip in enumerate(data["bundle"]["clips"]):
                child = HtmlData((data["curves"] / f"source_{index:03d}.html").read_text(encoding="utf-8"))
                source = next(value for value in child.json_values if "clips" in value)["clips"][0]
                self.assertEqual(source["rows"], clip["rows"])
                self.assertEqual(source["fps_fraction"], clip["fps_fraction"])
            for filename, asset in (("motion_viewer.js", "native_motion_viewer.js"), ("frame_link.js", "native_motion_frame_link.js")):
                self.assertEqual((data["curves"] / filename).read_bytes(), files("pitch_analysis").joinpath("review_assets", asset).read_bytes())
            self.assertEqual(result["source_ref"], reference(data["root"], data["reports"][0]))
            for ref in result["artifacts"].values():
                self.assertEqual(reference(data["root"], data["root"] / ref["path"]), ref)
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertEqual(result["new_tracking_replays"], 0)
            self.assertEqual(result["new_ground_truth_labels"], 0)
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertIsNone(result["usable_for_analysis"])
            self.assertFalse(result["browser_interaction_verified"])
            self.assertEqual({path: path.read_bytes() for path in before_files}, before_files)
            self.assertEqual(data["bundle"], before_bundle)

    def test_changed_source_or_stale_missing_stage_readouts_are_refused_before_output(self):
        for change in ("video", "stale", "missing"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                if change == "video":
                    video = data["root"] / "saved/a_001/source.mp4"
                    video.write_bytes(video.read_bytes() + b"changed")
                else:
                    payload = read_json(data["reports"][0])
                    if change == "missing":
                        del payload["manual_stage_readouts"]
                    else:
                        payload["manual_stage_readouts"][0]["joints"]["lead_knee"]["min_delta_deg"] = 999.
                    timing_fixtures.overwrite_json(data["reports"][0], payload)
                with self.assertRaises(ValueError):
                    self.run_export(data)
                self.assertFalse(data["curves"].exists())

    def test_existing_external_or_analysis_root_output_is_refused_without_changes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            data["curves"].mkdir(parents=True)
            sentinel = data["curves"] / "keep.txt"
            sentinel.write_text("Keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.run_export(data)
            for output in (data["root"] / "outside", data["root"] / "analysis_results"):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    self.run_export(data, output=output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "Keep")

    def test_cli_dispatches_saved_report_and_returns_nonzero_for_rejected_sources(self):
        result = {"status": "stage_curves_created", "pitcher_id": "custom_pitcher_07",
                  "summary": {"clip_count": 2, "source_frames": 16, "stage_count": 8,
                              "event_confirmed_stages": 6, "event_unresolved_stages": 2}, "new_inference_calls": 0}
        args = ["pitch-analysis", "describe-native-stage-curves", "events.json", "--output", "analysis_results/curves"]
        with patch("sys.argv", args), \
             patch("pitch_analysis.analysis.native_stage_curves.write_stage_curves", return_value=result) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no inference")), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), "events.json", "analysis_results/curves")
        self.assertEqual(json.loads(stream.getvalue())["status"], "stage_curves_created")
        with patch("sys.argv", args), \
             patch("pitch_analysis.analysis.native_stage_curves.write_stage_curves", side_effect=ValueError("Source changed")), \
             redirect_stdout(StringIO()) as stream:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "failed", "error": "Source changed"})


if __name__ == "__main__":
    unittest.main()
