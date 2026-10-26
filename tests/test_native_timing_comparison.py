"""Cross-pitcher timing compares bound manual intervals with exact fractional seconds."""
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

import test_native_motion_events as fixtures

from pitch_analysis.analysis.native_motion_events import describe_events
from pitch_analysis.analysis.native_timing_comparison import compare_timing_intervals, write_timing_comparison
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference, write_json


KEYS = ("preparation_to_leg_lift", "leg_lift_to_foot_plant",
        "foot_plant_to_release", "release_to_follow_through_end")


def timing(first=None, last=None, *, reason="Existing manual bounds"):
    return {"status": "unavailable" if first is None else "exact" if first == last else "bounded",
            "frame_bounds": None if first is None else [first, last], "reason": reason}


def overwrite_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class TimingIntervalTests(unittest.TestCase):
    def test_different_native_fps_use_frame_bounds_not_supplied_seconds(self):
        a, b = timing(1, 1), timing(2, 2)
        a.update(seconds_bounds=[999., 999.], seconds_bounds_fraction=["999", "999"])
        b.update(seconds_bounds=[-100., -100.], seconds_bounds_fraction=["-100", "-100"])
        result = compare_timing_intervals(a, "30/1", b, Fraction(60000, 1001))
        self.assertEqual(result["status"], "descriptive_manual_timing")
        self.assertEqual(result["relation"], "a_shorter")
        self.assertEqual(result["a_seconds_bounds_fraction"], ["1/30", "1/30"])
        self.assertEqual(result["b_seconds_bounds_fraction"], ["1001/30000", "1001/30000"])
        self.assertEqual(result["delta_seconds_bounds_fraction"], ["-1/30000", "-1/30000"])
        self.assertEqual(result["delta_seconds_bounds"], [float(Fraction(-1, 30000))] * 2)
        self.assertEqual(result["unavailable_reasons"], {"a": None, "b": None})

    def test_one_over_7500_second_difference_is_not_rounded_into_equality(self):
        result = compare_timing_intervals(timing(8, 8), "60000/1001", timing(4, 4), 30)
        self.assertEqual(result["a_seconds_bounds_fraction"], ["1001/7500"] * 2)
        self.assertEqual(result["b_seconds_bounds_fraction"], ["2/15"] * 2)
        self.assertEqual(result["relation"], "a_longer")
        self.assertEqual(result["delta_seconds_bounds_fraction"], ["1/7500"] * 2)
        self.assertEqual(result["delta_seconds_bounds"], [float(Fraction(1, 7500))] * 2)
        self.assertEqual(round(float(Fraction(1001, 7500)), 3), round(float(Fraction(2, 15)), 3))

    def test_identical_exact_durations_include_zero_without_inferring_pose_similarity(self):
        for frames_a, frames_b, duration in ((3, 6, "1/10"), (0, 0, "0")):
            with self.subTest(frames_a=frames_a, frames_b=frames_b):
                result = compare_timing_intervals(timing(frames_a, frames_a), 30, timing(frames_b, frames_b), 60)
                self.assertEqual(result["relation"], "identical_exact")
                self.assertEqual(result["a_seconds_bounds_fraction"], [duration] * 2)
                self.assertEqual(result["b_seconds_bounds_fraction"], [duration] * 2)
                self.assertEqual(result["delta_seconds_bounds_fraction"], ["0", "0"])
                self.assertEqual(result["delta_seconds_bounds"], [0., 0.])

    def test_touching_overlapping_and_identical_bounded_ranges_are_distinct_from_exact_equality(self):
        cases = [((1, 2), (2, 3), "touching", ["-1/15", "0"]),
                 ((2, 3), (1, 2), "touching", ["0", "1/15"]),
                 ((1, 3), (2, 4), "overlapping", ["-1/10", "1/30"]),
                 ((2, 2), (1, 3), "overlapping", ["-1/30", "1/30"]),
                 ((1, 3), (1, 3), "overlapping", ["-1/15", "1/15"])]
        for a, b, relation, delta in cases:
            with self.subTest(a=a, b=b):
                result = compare_timing_intervals(timing(*a), 30, timing(*b), 30)
                self.assertEqual(result["relation"], relation)
                self.assertEqual(result["delta_seconds_bounds_fraction"], delta)
                self.assertEqual(result["delta_seconds_bounds"], [float(Fraction(value)) for value in delta])

    def test_unavailable_sides_keep_reasons_and_null_delta_without_erasing_the_known_side(self):
        for unavailable_a, unavailable_b in ((True, False), (False, True), (True, True)):
            with self.subTest(unavailable_a=unavailable_a, unavailable_b=unavailable_b):
                a = timing(reason="Start not observable") if unavailable_a else timing(3, 3)
                b = timing(reason="Leg lift uncertain") if unavailable_b else timing(6, 6)
                result = compare_timing_intervals(a, 30, b, 60)
                self.assertEqual((result["status"], result["relation"]), ("unavailable", "unavailable"))
                self.assertEqual(result["a_seconds_bounds_fraction"], None if unavailable_a else ["1/10"] * 2)
                self.assertEqual(result["b_seconds_bounds_fraction"], None if unavailable_b else ["1/10"] * 2)
                self.assertIsNone(result["delta_seconds_bounds_fraction"])
                self.assertIsNone(result["delta_seconds_bounds"])
                self.assertEqual(result["unavailable_reasons"],
                                 {"a": "Start not observable" if unavailable_a else None,
                                  "b": "Leg lift uncertain" if unavailable_b else None})

    def test_invalid_or_approximate_fps_are_rejected_on_either_side(self):
        for fps in (0, -30, "0/1", "-1/2", "1/0", "not-fps", True, None, 29.97, float("inf")):
            for side in ("a", "b"):
                with self.subTest(fps=fps, side=side), self.assertRaises(ValueError):
                    compare_timing_intervals(timing(1, 1), fps if side == "a" else 30,
                                             timing(1, 1), fps if side == "b" else 30)

    def test_invalid_bounds_or_status_cannot_become_a_duration(self):
        cases = [{"status": "exact", "frame_bounds": value} for value in
                 (None, [], [1], [1, 1, 1], [-1, -1], [2, 1], [1., 1.], [True, True], ["1", "1"], [1, 2])]
        cases += [{"status": "bounded", "frame_bounds": [1, 1]},
                  {"status": "unavailable", "frame_bounds": [1, 2]},
                  {"status": "predicted", "frame_bounds": [1, 1]}]
        for record in cases:
            with self.subTest(record=record), self.assertRaises(ValueError):
                compare_timing_intervals(record, 30, timing(1, 1), 30)

    def test_interval_comparison_preserves_inputs_and_returns_independent_lists(self):
        a, b = timing(1, 3), timing(2, 4)
        before = deepcopy((a, b))
        result = compare_timing_intervals(a, 30, b, 30)
        self.assertEqual((a, b), before)
        result["a_seconds_bounds_fraction"][0] = "999"
        result["b_seconds_bounds_fraction"][0] = "999"
        result["delta_seconds_bounds_fraction"][0] = "999"
        result["delta_seconds_bounds"][0] = 999.
        self.assertEqual((a, b), before)


class TimingComparisonExportTests(unittest.TestCase):
    def fixture(self, root):
        reports, bundles, payloads = [], {}, []
        for side, pitcher_id, pitch_ids, fps in (
            ("a", "pitcher_a", ("a_001", "a_002"), "60000/1001"),
            ("b", "pitcher_b", ("b_001",), "30/1"),
        ):
            clips, refs = [], []
            request_path = root / f"request_{side}.json"
            write_json(request_path, {"schema_version": "native-motion-events-request-v1",
                                      "pitcher_id": pitcher_id, "clips": []})
            request_ref = reference(root, request_path)
            refs.append(request_ref)
            for pitch_id in pitch_ids:
                folder = root / "saved" / pitch_id
                folder.mkdir(parents=True)
                video, gt = folder / "source.mp4", folder / "ground_truth.json"
                video.write_bytes(b"synthetic source: loader is mocked; do not decode")
                events = {"preparation_start": fixtures.exact(0), "leg_lift": fixtures.exact(1),
                          "foot_plant": fixtures.exact(3), "approximate_release": fixtures.exact(5),
                          "follow_through_end": fixtures.exact(7)}
                if side == "b":
                    events["preparation_start"] = {"status": "not_observable", "frame_index": None,
                                                    "confidence": None, "note": "Already in progress"}
                write_json(gt, {"labels": {"events": events}})
                source_refs = {"video_ref": reference(root, video), "ground_truth_ref": reference(root, gt)}
                refs.extend(source_refs.values())
                values = fixtures.rows()
                clips.append({"pitch_id": pitch_id, "frame_count": len(values), "fps_fraction": fps,
                              "rows": values, "overlay_url": "unused-in-timing-only-export.mp4",
                              **describe_events(events, Fraction(fps), values), "source_refs": source_refs,
                              "pointwise_reliability": "unknown", "usable_for_analysis": None})
            bundle = {"root": root, "output": root / "analysis_results" / "unused_reload",
                      "pitcher_id": pitcher_id, "clips": clips, "source_refs": refs, "request_ref": request_ref}
            bundles[request_path.resolve()] = bundle
            report = root / f"saved_report_{side}.json"
            payload = {"schema_version": "native-motion-event-comparison-v1", "status": "event_comparison_created",
                       "pitcher_id": pitcher_id, "clip_count": len(clips),
                       "clips": [{key: value for key, value in c.items() if key not in {"rows", "overlay_url"}}
                                 for c in clips], "source_refs": {"request_ref": request_ref}}
            write_json(report, payload)
            reports.append(report)
            payloads.append(deepcopy(payload))
        return {"root": root, "reports": reports, "bundles": bundles, "payloads": payloads,
                "output": root / "analysis_results" / "timing"}

    def run_export(self, data, *, output=None):
        def load(_root, config, _output):
            return data["bundles"][Path(config).resolve()]
        with patch("pitch_analysis.analysis.native_timing_comparison.load_event_clips", side_effect=load) as loader, \
             patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
             patch("cv2.VideoCapture", side_effect=AssertionError("no video decoding")):
            result = write_timing_comparison(data["root"], data["reports"], data["output"] if output is None else output)
        self.assertEqual(loader.call_count, 2)
        return result

    def test_export_retains_every_pair_null_reasons_sources_and_original_inputs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before_files = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            before_bundles = deepcopy(data["bundles"])
            result = self.run_export(data)
            self.assertEqual((result["total_pairs"], result["comparable_pairs"], result["unavailable_pairs"]), (8, 6, 2))
            self.assertEqual([(row["pitcher_id"], row["clip_count"]) for row in result["cohorts"]],
                             [("pitcher_a", 2), ("pitcher_b", 1)])
            self.assertEqual(len(result["pairs"]), 8)
            self.assertEqual({(row["timing_key"], row["a_pitch_id"], row["b_pitch_id"]) for row in result["pairs"]},
                             {(key, a, "b_001") for key in KEYS for a in ("a_001", "a_002")})
            rows = csv_rows(data["output"] / "timing_pairs.csv")
            self.assertEqual(len(rows), 8)
            self.assertEqual(len(csv_rows(data["output"] / "pitch_timings.csv")), 12)
            unavailable_rows = [row for row in rows if row["status"] == "unavailable"]
            self.assertEqual(len(unavailable_rows), 2)
            for row in unavailable_rows:
                self.assertEqual(row["relation"], "unavailable")
                self.assertEqual(row["a_unavailable_reason"], "")
                self.assertTrue(row["b_unavailable_reason"])
                for key in ("delta_min_seconds_fraction", "delta_max_seconds_fraction",
                            "delta_min_seconds", "delta_max_seconds"):
                    self.assertEqual(row[key], "")
            for row in rows:
                pair = next(pair for pair in result["pairs"] if (pair["timing_key"], pair["a_pitch_id"], pair["b_pitch_id"])
                            == (row["timing_key"], row["a_pitch_id"], row["b_pitch_id"]))
                self.assertEqual(row["relation"], pair["relation"])
                fractions = pair["delta_seconds_bounds_fraction"]
                self.assertEqual(row["delta_min_seconds_fraction"], "" if fractions is None else fractions[0])
                self.assertEqual(row["delta_max_seconds_fraction"], "" if fractions is None else fractions[1])
            self.assertEqual(read_json(data["output"] / "timing_comparison.json"), result)
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertFalse(result["angle_comparison_performed"])
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertIsNone(result["usable_for_analysis"])
            for ref in result["artifacts"].values():
                self.assertEqual(reference(data["root"], data["root"] / ref["path"]), ref)
            self.assertEqual({path: path.read_bytes() for path in before_files}, before_files)
            self.assertEqual(data["bundles"], before_bundles)
            result["pairs"][0]["a_frame_bounds"][0] = 999
            result["pitch_timings"][0]["start_event"]["frame_bounds"][0] = 999
            self.assertEqual(data["bundles"], before_bundles)

    def test_modified_saved_frame_or_seconds_fields_are_rejected_against_bound_events(self):
        for field, replacement in (("frame_bounds", [0, 0]), ("seconds_bounds", [999., 999.]),
                                   ("seconds_bounds_fraction", ["999", "999"])):
            with self.subTest(field=field), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                data["payloads"][0]["clips"][0]["timing"]["foot_plant_to_release"][field] = replacement
                overwrite_json(data["reports"][0], data["payloads"][0])
                with self.assertRaises(ValueError):
                    self.run_export(data)
                self.assertFalse(data["output"].exists())

    def test_same_pitcher_reports_are_rejected_without_output(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            second = data["payloads"][1]
            second["pitcher_id"] = "pitcher_a"
            data["bundles"][data["root"] / "request_b.json"]["pitcher_id"] = "pitcher_a"
            overwrite_json(data["reports"][1], second)
            with self.assertRaises(ValueError):
                self.run_export(data)
            self.assertFalse(data["output"].exists())

    def test_changed_request_hash_is_rejected_even_when_the_loader_is_mocked(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            request = data["root"] / "request_a.json"
            request.write_bytes(request.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                self.run_export(data)
            self.assertFalse(data["output"].exists())

    def test_existing_external_and_non_two_report_outputs_are_rejected_without_overwriting(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            data["output"].mkdir(parents=True)
            sentinel = data["output"] / "keep.txt"
            sentinel.write_text("existing output", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_timing_comparison(data["root"], data["reports"], data["output"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing output")
            outside = data["root"] / "outside_analysis_results"
            with self.assertRaises(ValueError):
                write_timing_comparison(data["root"], data["reports"], outside)
            self.assertFalse(outside.exists())
            for report_count in (0, 1, 3):
                with self.subTest(report_count=report_count), self.assertRaises(ValueError):
                    write_timing_comparison(data["root"], (data["reports"] * 2)[:report_count],
                                            data["root"] / "analysis_results" / f"invalid_{report_count}")


class TimingComparisonCliTests(unittest.TestCase):
    def test_cli_dispatches_two_saved_reports_without_pose(self):
        result = {"status": "timing_comparison_created", "total_pairs": 8, "comparable_pairs": 6,
                  "unavailable_pairs": 2, "new_inference_calls": 0}
        with patch("sys.argv", ["pitch-analysis", "compare-native-timing", "a.json", "b.json",
                                "--output", "analysis_results/new"]), \
             patch("pitch_analysis.analysis.native_timing_comparison.write_timing_comparison", return_value=result) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose")), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), ["a.json", "b.json"], "analysis_results/new")
        emitted = json.loads(stream.getvalue())
        for key, value in result.items():
            self.assertEqual(emitted[key], value)

    def test_cli_returns_nonzero_for_rejected_bound_report(self):
        with patch("sys.argv", ["pitch-analysis", "compare-native-timing", "a.json", "b.json",
                                "--output", "analysis_results/new"]), \
             patch("pitch_analysis.analysis.native_timing_comparison.write_timing_comparison",
                   side_effect=ValueError("saved report changed")), \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose")), \
             redirect_stdout(StringIO()) as stream:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "failed", "error": "saved report changed"})


if __name__ == "__main__":
    unittest.main()
