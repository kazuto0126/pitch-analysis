"""Descriptive pitcher profiles preserve source time, unknowns and model limits."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_motion_events as event_fixtures
import test_native_timing_comparison as timing_fixtures

from pitch_analysis.analysis.native_descriptive_profile import summarize_profile, write_descriptive_profile
from pitch_analysis.analysis.native_motion_events import describe_events
from pitch_analysis.analysis.native_motion_transition import describe_manual_event_transitions
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


KEYS = timing_fixtures.KEYS


def clip(pitch_id="custom_001", *, fps="30/1", events=None, values=None):
    values = event_fixtures.rows() if values is None else values
    for index, row in enumerate(values):
        row["timestamp_sec"] = float(Fraction(index) / Fraction(fps))
    if events is None:
        events = {name: event_fixtures.exact(index) for name, index in (
            ("preparation_start", 0), ("leg_lift", 1), ("foot_plant", 3),
            ("approximate_release", 5), ("follow_through_end", 7))}
    return {"pitch_id": pitch_id, "frame_count": len(values), "fps_fraction": fps,
            "rows": values, "overlay_url": "saved-overlay.mp4",
            **describe_events(events, Fraction(fps), values),
            "pointwise_reliability": "unknown", "usable_for_analysis": None}


def by_stage(result, key):
    return next(stage for stage in result["stages"] if stage["timing_key"] == key)


class DescriptiveProfileMathTests(unittest.TestCase):
    def test_single_clip_is_supported_without_inventing_repeatability(self):
        result = summarize_profile([clip()])
        self.assertEqual((result["clip_count"], result["source_frames"]), (1, 8))
        self.assertEqual((result["timing_pair_count"], result["timing_comparable_pairs"],
                          result["timing_unavailable_pairs"]), (0, 0, 0))
        self.assertEqual((result["joint_summary_count"], result["joint_calculable_summaries"],
                          result["joint_unavailable_summaries"]), (8, 8, 0))
        self.assertEqual([stage["timing_key"] for stage in result["stages"]], list(KEYS))
        for stage in result["stages"]:
            self.assertEqual(stage["timing_pairs"], [])
            self.assertEqual(stage["timing_available_clip_ids"], ["custom_001"])

    def test_pair_durations_use_each_native_fractional_fps_without_rounding(self):
        a, b = clip("a", fps="60000/1001"), clip("b", fps="30/1")
        result = summarize_profile([a, b])
        first = by_stage(result, KEYS[0])
        self.assertEqual(first["timing_envelope_seconds_fraction"], ["1001/60000", "1/30"])
        pair = first["timing_pairs"][0]
        self.assertEqual((pair["a_pitch_id"], pair["b_pitch_id"]), ("a", "b"))
        self.assertEqual(pair["relation"], "a_shorter")
        self.assertEqual(pair["delta_seconds_bounds_fraction"], ["-333/20000"] * 2)
        self.assertEqual((result["timing_pair_count"], result["timing_comparable_pairs"]), (4, 4))

    def test_uncertain_event_keeps_candidate_without_becoming_timing_or_joint_data(self):
        a, b = clip("a"), clip("b")
        raw = {name: event_fixtures.exact(index) for name, index in (
            ("preparation_start", 0), ("leg_lift", 1), ("foot_plant", 3),
            ("approximate_release", 5), ("follow_through_end", 7))}
        raw["leg_lift"] = event_fixtures.ranged(1, 1, status="uncertain")
        b.update(describe_events(raw, Fraction(30), b["rows"]))
        before = deepcopy([a, b])
        result = summarize_profile([a, b])
        self.assertEqual((result["timing_comparable_pairs"], result["timing_unavailable_pairs"]), (2, 2))
        self.assertEqual((result["joint_calculable_summaries"], result["joint_unavailable_summaries"]), (12, 4))
        for key in KEYS[:2]:
            stage = by_stage(result, key)
            self.assertEqual(stage["timing_unavailable_clip_ids"], ["b"])
            pair = stage["timing_pairs"][0]
            self.assertIsNone(pair["delta_seconds_bounds_fraction"])
            self.assertTrue(pair["unavailable_reasons"]["b"])
            for joint in stage["joints"].values():
                self.assertIsNone(joint["common_direction"])
                unavailable = next(row for row in joint["clip_summaries"] if row["pitch_id"] == "b")
                self.assertIsNone(unavailable["total_pairs"])
                self.assertIsNone(unavailable["calculated_pairs"])
                self.assertTrue(unavailable["transition_reason"])
        self.assertEqual([a, b], before)
        self.assertEqual(b["events"]["leg_lift"]["frame_bounds"], [1, 1])

    def test_missing_geometry_is_distinct_from_unresolved_event_and_never_filtered(self):
        a, b = clip("a"), clip("b")
        b["rows"][1]["throwing_elbow_coordinate_status"] = "missing_coordinates"
        b["rows"][1]["throwing_elbow_model_xy_deg"] = None
        result = summarize_profile([a, b])
        self.assertEqual((result["joint_summary_count"], result["joint_calculable_summaries"],
                          result["joint_unavailable_summaries"]), (16, 14, 2))
        self.assertEqual(result["timing_comparable_pairs"], 4)
        first = by_stage(result, KEYS[0])["joints"]["throwing_elbow"]
        row = next(row for row in first["clip_summaries"] if row["pitch_id"] == "b")
        self.assertEqual((row["total_pairs"], row["calculated_pairs"], row["missing_endpoint_pairs"]), (1, 0, 1))
        self.assertEqual(row["transition_status"], "descriptive_model_xy_transition")
        self.assertEqual(first["direction_counts"]["unavailable"], 1)
        self.assertEqual(first["clip_ids_by_direction"]["unavailable"], ["b"])
        self.assertIsNone(first["common_direction"])

    def test_common_direction_requires_every_clip_and_preserves_tiny_negative_crossing(self):
        a, b = clip("a"), clip("b")
        first = summarize_profile([a, b])["stages"][0]["joints"]["throwing_elbow"]
        self.assertEqual(first["common_direction"], "positive")
        raw = {name: event_fixtures.exact(index) for name, index in (
            ("preparation_start", 0), ("leg_lift", 1), ("foot_plant", 3),
            ("approximate_release", 5), ("follow_through_end", 7))}
        raw["leg_lift"] = event_fixtures.ranged(1, 2)
        b["rows"][0]["throwing_elbow_model_xy_deg"] = 10.
        b["rows"][1]["throwing_elbow_model_xy_deg"] = 10. - .0000001
        b["rows"][2]["throwing_elbow_model_xy_deg"] = 11.
        b.update(describe_events(raw, Fraction(30), b["rows"]))
        result = summarize_profile([a, b])
        joint = result["stages"][0]["joints"]["throwing_elbow"]
        self.assertIsNone(joint["common_direction"])
        self.assertEqual(joint["direction_counts"]["positive"], 1)
        self.assertEqual(joint["direction_counts"]["includes_zero"], 1)
        row = next(row for row in joint["clip_summaries"] if row["pitch_id"] == "b")
        self.assertLess(row["min_delta_deg"], 0.)
        self.assertGreater(row["max_delta_deg"], 0.)

    def test_duplicate_identity_or_non_source_timestamps_are_rejected(self):
        a, b = clip("a"), clip("a")
        with self.assertRaises(ValueError):
            summarize_profile([a, b])
        a["rows"][1]["timestamp_sec"] += .001
        with self.assertRaises(ValueError):
            summarize_profile([a])
        with self.assertRaises(ValueError):
            summarize_profile([])


class DescriptiveProfileExportTests(unittest.TestCase):
    def fixture(self, root):
        data = timing_fixtures.TimingComparisonExportTests().fixture(root)
        bundle = data["bundles"][root / "request_a.json"]
        bundle["pitcher_id"] = "custom_pitcher_07"
        clips = bundle["clips"]
        for item in clips:
            for index, row in enumerate(item["rows"]):
                row["timestamp_sec"] = float(Fraction(index) / Fraction(item["fps_fraction"]))
        events = {name: event_fixtures.exact(index) for name, index in (
            ("preparation_start", 0), ("leg_lift", 1), ("foot_plant", 3),
            ("approximate_release", 5), ("follow_through_end", 7))}
        events["preparation_start"] = {"status": "not_observable", "frame_index": None,
                                        "confidence": None, "note": "Already underway"}
        clips[1].update(describe_events(events, Fraction(clips[1]["fps_fraction"]), clips[1]["rows"]))
        payload = data["payloads"][0]
        payload["pitcher_id"] = bundle["pitcher_id"]
        payload["clips"] = [{key: value for key, value in item.items() if key not in {"rows", "overlay_url"}}
                            for item in clips]
        payload["manual_stage_readouts"] = [{"pitch_id": item["pitch_id"], **stage}
                                            for item in clips for stage in describe_manual_event_transitions(item)]
        timing_fixtures.overwrite_json(data["reports"][0], payload)
        data["output"] = root / "analysis_results" / "profile"
        return data

    def run_export(self, data, output=None):
        with patch("pitch_analysis.analysis.native_timing_comparison.load_event_clips",
                   side_effect=lambda _root, request, _output: data["bundles"][Path(request).resolve()]), \
             patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
             patch("cv2.VideoCapture", side_effect=AssertionError("no decoding")):
            return write_descriptive_profile(data["root"], data["reports"][0],
                                             data["output"] if output is None else output)

    def test_export_has_source_bound_null_preserving_outputs_and_immutable_inputs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before_files = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            before = deepcopy(data["bundles"])
            result = self.run_export(data)
            self.assertEqual(result["schema_version"], "native-descriptive-pitcher-profile-v1")
            self.assertEqual(result["status"], "descriptive_profile_created")
            self.assertEqual(result["pitcher_id"], "custom_pitcher_07")
            summary = result["summary"]
            self.assertEqual((summary["clip_count"], summary["timing_pair_count"], summary["timing_comparable_pairs"],
                              summary["timing_unavailable_pairs"]), (2, 4, 3, 1))
            self.assertEqual((summary["joint_summary_count"], summary["joint_calculable_summaries"],
                              summary["joint_unavailable_summaries"]), (16, 14, 2))
            rows = timing_fixtures.csv_rows(data["output"] / "timing_relations.csv")
            self.assertEqual(len(rows), 4)
            unavailable = next(row for row in rows if row["status"] == "unavailable")
            self.assertEqual(unavailable["delta_min_seconds_fraction"], "")
            self.assertEqual(unavailable["delta_max_seconds_fraction"], "")
            self.assertTrue(unavailable["b_unavailable_reason"])
            self.assertEqual(len(timing_fixtures.csv_rows(data["output"] / "joint_direction_summary.csv")), 8)
            self.assertTrue((data["output"] / "report.md").is_file())
            self.assertEqual(read_json(data["output"] / "profile.json"), result)
            self.assertEqual(result["source_ref"], reference(data["root"], data["reports"][0]))
            for ref in result["artifacts"].values():
                self.assertEqual(reference(data["root"], data["root"] / ref["path"]), ref)
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertEqual(result["new_tracking_replays"], 0)
            self.assertEqual(result["new_ground_truth_labels"], 0)
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertEqual(result["quality_status"], "not_calibrated")
            self.assertIsNone(result["usable_for_analysis"])
            self.assertFalse(result["formal_reference_promotion"])
            self.assertEqual({path: path.read_bytes() for path in before_files}, before_files)
            self.assertEqual(data["bundles"], before)
            result["summary"]["stages"][0]["joints"]["throwing_elbow"]["clip_summaries"][0]["pairs"][0]["start_frame"] = 999
            self.assertEqual(data["bundles"], before)

    def test_stale_or_missing_stage_readouts_cannot_be_reinterpreted_as_current(self):
        for mode in ("changed", "missing"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                payload = read_json(data["reports"][0])
                if mode == "missing":
                    del payload["manual_stage_readouts"]
                else:
                    payload["manual_stage_readouts"][0]["joints"]["throwing_elbow"]["min_delta_deg"] = 999.
                timing_fixtures.overwrite_json(data["reports"][0], payload)
                with self.assertRaises(ValueError):
                    self.run_export(data)
                self.assertFalse(data["output"].exists())

    def test_changed_bound_request_or_source_is_rejected_before_output(self):
        for target in ("request", "video"):
            with self.subTest(target=target), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                path = data["root"] / "request_a.json" if target == "request" else data["root"] / "saved/a_001/source.mp4"
                path.write_bytes(path.read_bytes() + b"changed")
                with self.assertRaises(ValueError):
                    self.run_export(data)
                self.assertFalse(data["output"].exists())

    def test_existing_external_or_analysis_root_output_is_refused_without_changes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            data["output"].mkdir(parents=True)
            sentinel = data["output"] / "keep.txt"
            sentinel.write_text("Keep existing output", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.run_export(data)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "Keep existing output")
            for output in (data["root"] / "external", data["root"] / "analysis_results"):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    self.run_export(data, output=output)


class DescriptiveProfileCliTests(unittest.TestCase):
    def test_cli_dispatches_one_saved_report_without_pose(self):
        result = {"status": "descriptive_profile_created", "pitcher_id": "custom_pitcher_07",
                  "summary": {"clip_count": 2}, "new_inference_calls": 0}
        with patch("sys.argv", ["pitch-analysis", "describe-native-profile", "saved.json",
                                "--output", "analysis_results/new"]), \
             patch("pitch_analysis.analysis.native_descriptive_profile.write_descriptive_profile", return_value=result) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose")), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), "saved.json", "analysis_results/new")
        emitted = json.loads(stream.getvalue())
        self.assertEqual(emitted["status"], result["status"])
        self.assertEqual(emitted["pitcher_id"], "custom_pitcher_07")
        self.assertEqual(emitted["clip_count"], 2)
        self.assertEqual(emitted["new_inference_calls"], 0)

    def test_cli_returns_nonzero_for_rejected_source_report(self):
        with patch("sys.argv", ["pitch-analysis", "describe-native-profile", "saved.json",
                                "--output", "analysis_results/new"]), \
             patch("pitch_analysis.analysis.native_descriptive_profile.write_descriptive_profile",
                   side_effect=ValueError("Source report changed")), \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose")), \
             redirect_stdout(StringIO()) as stream:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "failed", "error": "Source report changed"})


if __name__ == "__main__":
    unittest.main()
