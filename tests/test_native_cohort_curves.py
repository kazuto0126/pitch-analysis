"""Two-cohort display shifts preserve source samples and every human origin."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from fractions import Fraction
from html.parser import HTMLParser
from importlib.resources import files
from io import StringIO
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit
import xml.etree.ElementTree as ET

import test_native_descriptive_profile as profile_fixtures
import test_native_motion_events as event_fixtures
import test_native_timing_comparison as timing_fixtures
from test_native_timing_viewer import HtmlData

from pitch_analysis.analysis.native_cohort_curves import prepare_cohort_curves, write_cohort_curve_review
from pitch_analysis.analysis.native_motion_events import describe_events
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


def cohorts(a=None, b=None):
    return [{"pitcher_id": "arbitrary_a", "clips": [profile_fixtures.clip(fps="60000/1001") if a is None else a]},
            {"pitcher_id": "arbitrary_b", "clips": [profile_fixtures.clip(fps="30/1") if b is None else b]}]


def event_dict():
    return {name: event_fixtures.exact(index) for name, index in (
        ("preparation_start", 0), ("leg_lift", 1), ("foot_plant", 3),
        ("approximate_release", 5), ("follow_through_end", 7))}


class CohortCurveMathTests(unittest.TestCase):
    def test_mixed_fractional_fps_uses_global_source_extent_and_fixed_angle_scale(self):
        result = prepare_cohort_curves(cohorts())
        self.assertEqual((result["clip_count"], result["source_frames"]), (2, 16))
        self.assertEqual(result["origin_counts"], {"exact": 2, "bounded": 0, "unavailable": 0})
        self.assertEqual(result["origin_candidate_paths"], 2)
        self.assertEqual(result["source_time_bounds_fraction"], ["-1/10", "2/15"])
        self.assertEqual(result["full_display_seconds_bounds"], [-.1, float(Fraction(2, 15))])
        self.assertEqual(result["zoom_display_seconds_bounds"], [-.5, .5])
        self.assertEqual(result["angle_display_bounds"], [0, 180])
        self.assertEqual([item["side"] for item in result["cohorts"]], ["a", "b"])
        for item in result["cohorts"]:
            self.assertEqual((item["clip_count"], item["source_frames"]), (1, 8))

    def test_all_bounded_origins_and_single_frame_range_remain_display_alternatives(self):
        raw = event_dict()
        raw["foot_plant"] = event_fixtures.ranged(2, 4)
        a = profile_fixtures.clip(events=raw, fps="30/1")
        result = prepare_cohort_curves(cohorts(a, profile_fixtures.clip(fps="60000/1001")))
        self.assertEqual(result["origin_counts"], {"exact": 1, "bounded": 1, "unavailable": 0})
        self.assertEqual(result["origin_candidate_paths"], 4)
        self.assertEqual(result["source_frames"], 16)
        shifted = result["cohorts"][0]["clips"][0]
        self.assertEqual(shifted["origin_candidates"], [2, 3, 4])
        self.assertEqual(len(shifted["bounded_rows"]), 8)
        self.assertEqual(result["source_time_bounds_fraction"], ["-2/15", "1/6"])
        self.assertEqual(shifted["bounded_rows"][3]["relative_seconds_bounds_fraction"], ["-1/30", "1/30"])
        raw["foot_plant"] = event_fixtures.ranged(3, 3)
        single = prepare_cohort_curves(cohorts(profile_fixtures.clip(events=raw)))
        bounded = single["cohorts"][0]["clips"][0]
        self.assertEqual(bounded["origin_status"], "bounded")
        self.assertEqual(bounded["origin_candidates"], [3])
        self.assertIsNone(bounded["events"]["foot_plant"]["frame_index"])

    def test_unknown_origins_do_not_use_candidate_and_keep_unshifted_source_rows(self):
        a_raw, b_raw = event_dict(), event_dict()
        a_raw["foot_plant"] = event_fixtures.ranged(3, 3, status="uncertain")
        b_raw["foot_plant"] = {"status": "not_observable", "frame_index": None, "note": "Hidden"}
        source = cohorts(profile_fixtures.clip(events=a_raw), profile_fixtures.clip(events=b_raw))
        before = deepcopy(source)
        result = prepare_cohort_curves(source)
        self.assertEqual(result["origin_counts"], {"exact": 0, "bounded": 0, "unavailable": 2})
        self.assertEqual(result["origin_candidate_paths"], 0)
        self.assertIsNone(result["source_time_bounds_fraction"])
        self.assertEqual(result["full_display_seconds_bounds"], [-.5, .5])
        self.assertEqual(result["source_frames"], 16)
        for cohort in result["cohorts"]:
            clip = cohort["clips"][0]
            self.assertEqual(clip["origin_status"], "unavailable")
            self.assertEqual(clip["origin_candidates"], [])
            self.assertTrue(all(row["relative_seconds_bounds_fraction"] is None for row in clip["bounded_rows"]))
        self.assertEqual(result["cohorts"][0]["clips"][0]["events"]["foot_plant"]["frame_bounds"], [3, 3])
        self.assertEqual(source, before)

    def test_zero_span_has_exact_source_extent_and_only_display_fallback(self):
        raw = {name: event_fixtures.exact(0) for name in event_dict()}
        a = profile_fixtures.clip(events=raw, values=event_fixtures.rows(1))
        b = profile_fixtures.clip(events=raw, values=event_fixtures.rows(1), fps="60000/1001")
        result = prepare_cohort_curves(cohorts(a, b))
        self.assertEqual(result["source_time_bounds_fraction"], ["0", "0"])
        self.assertEqual(result["full_display_seconds_bounds"], [-.5, .5])
        self.assertEqual((result["source_frames"], result["origin_candidate_paths"]), (2, 2))
        for item in result["cohorts"]:
            self.assertEqual(item["clips"][0]["bounded_rows"][0]["relative_seconds_bounds_fraction"], ["0", "0"])

    def test_same_pitch_id_in_distinct_cohorts_is_allowed_without_mutating_missing_samples(self):
        a, b = profile_fixtures.clip("same_pitch"), profile_fixtures.clip("same_pitch", fps="60000/1001")
        a["rows"][2]["throwing_elbow_coordinate_status"] = "missing_coordinates"
        a["rows"][2]["throwing_elbow_model_xy_deg"] = None
        a["rows"][3]["throwing_elbow_coordinate_status"] = "degenerate_geometry"
        a["rows"][3]["throwing_elbow_model_xy_deg"] = None
        source = cohorts(a, b)
        before = deepcopy(source)
        result = prepare_cohort_curves(source)
        self.assertEqual(result["clip_count"], 2)
        self.assertEqual([item["clips"][0]["pitch_id"] for item in result["cohorts"]], ["same_pitch", "same_pitch"])
        for actual, original in zip(result["cohorts"], source, strict=True):
            self.assertEqual(actual["clips"][0]["rows"], original["clips"][0]["rows"])
        self.assertEqual(source, before)

    def test_invalid_cohort_identity_count_duplicates_or_source_timeline_are_rejected(self):
        invalid = [[], cohorts()[:1], cohorts() + [deepcopy(cohorts()[0])]]
        same_pitcher = cohorts()
        same_pitcher[1]["pitcher_id"] = same_pitcher[0]["pitcher_id"]
        invalid.append(same_pitcher)
        duplicates = cohorts()
        duplicates[0]["clips"].append(deepcopy(duplicates[0]["clips"][0]))
        invalid.append(duplicates)
        changed_time = cohorts()
        changed_time[0]["clips"][0]["rows"][1]["timestamp_sec"] += .001
        invalid.append(changed_time)
        for index, value in enumerate(invalid):
            with self.subTest(case=index), self.assertRaises((ValueError, TypeError)):
                prepare_cohort_curves(value)


class Objects(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.objects, self.images = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "object":
            self.objects.append(dict(attrs))
        elif tag == "img":
            self.images.append(dict(attrs))


class CohortCurveExportTests(unittest.TestCase):
    def fixture(self, root):
        data = timing_fixtures.TimingComparisonExportTests().fixture(root)
        for bundle in data["bundles"].values():
            refs = [bundle["request_ref"]]
            for index, clip in enumerate(bundle["clips"]):
                fps = Fraction(clip["fps_fraction"])
                for row in clip["rows"]:
                    row["timestamp_sec"] = float(Fraction(row["frame_index"]) / fps)
                clip["source_refs"]["overlay_ref"] = deepcopy(clip["source_refs"]["video_ref"])
                if bundle["pitcher_id"] == "pitcher_a" and index == 0:
                    for row in clip["rows"]:
                        row["throwing_elbow_model_xy_deg"] = 90. + row["frame_index"]
                    for frame, state in ((2, "missing_coordinates"), (3, "degenerate_geometry")):
                        clip["rows"][frame]["throwing_elbow_coordinate_status"] = state
                        clip["rows"][frame]["throwing_elbow_model_xy_deg"] = None
                elif bundle["pitcher_id"] == "pitcher_a":
                    raw = event_dict()
                    raw["foot_plant"] = event_fixtures.ranged(2, 3)
                    clip.update(describe_events(raw, fps, clip["rows"]))
                refs.extend(clip["source_refs"].values())
            bundle["source_refs"] = refs
        for path, payload, bundle in zip(data["reports"], data["payloads"], data["bundles"].values(), strict=True):
            payload["clips"] = [{key: deepcopy(value) for key, value in clip.items()
                                 if key not in {"rows", "overlay_url"}} for clip in bundle["clips"]]
            timing_fixtures.overwrite_json(path, payload)
        data["review"] = root / "analysis_results" / "cohort_curves"
        return data

    def run_export(self, data, output=None):
        with patch("pitch_analysis.analysis.native_timing_comparison.load_event_clips",
                   side_effect=lambda _root, request, _output: data["bundles"][Path(request).resolve()]), \
             patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
             patch("cv2.VideoCapture", side_effect=AssertionError("saved motion only")):
            return write_cohort_curve_review(data["root"], data["reports"], data["review"] if output is None else output)

    def test_real_plots_source_links_axes_csv_and_original_player_preserve_bound_inputs(self):
        from matplotlib.figure import Figure
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            before_bundles = deepcopy(data["bundles"])
            real_savefig, snapshots = Figure.savefig, {}
            def savefig(figure, filename, *args, **kwargs):
                snapshots[Path(filename).name] = [{"x": list(axis.get_xlim()), "y": list(axis.get_ylim()),
                    "lines": [(list(line.get_xdata()), list(line.get_ydata())) for line in axis.lines]}
                    for axis in figure.axes]
                return real_savefig(figure, filename, *args, **kwargs)
            with patch.object(Figure, "savefig", new=savefig):
                result = self.run_export(data)
            self.assertEqual((result["schema_version"], result["status"]),
                             ("native-cohort-curve-review-v1", "cohort_curve_review_created"))
            self.assertEqual((result["clip_count"], result["source_frames"], result["origin_candidate_paths"]), (3, 24, 4))
            self.assertEqual(result["origin_counts"], {"exact": 2, "bounded": 1, "unavailable": 0})
            self.assertEqual(result, read_json(data["review"] / "cohort_curves.json"))
            with (data["review"] / "cohort_curves.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 24)
            self.assertEqual(len({(row["side"], row["pitch_id"], row["frame_index"]) for row in rows}), 24)
            page = Objects((data["review"] / "report.html").read_text(encoding="utf-8"))
            self.assertEqual({item["data"] for item in page.objects}, {"throwing_elbow.svg", "lead_knee.svg"})
            self.assertTrue(all(item.get("type") == "image/svg+xml" for item in page.objects))
            self.assertFalse(any(item.get("src", "").endswith(".svg") for item in page.images))
            for role, expected_links in (("throwing_elbow", 60), ("lead_knee", 64)):
                self.assertTrue((data["review"] / (role + ".png")).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
                axes = snapshots[role + ".svg"]
                self.assertEqual(len(axes), 4)
                self.assertEqual([axis["x"] for axis in axes], [result["full_display_seconds_bounds"], [-.5, .5],
                                                               result["full_display_seconds_bounds"], [-.5, .5]])
                self.assertTrue(all(axis["y"] == [0., 180.] for axis in axes))
                self.assertEqual([(axis["x"], axis["y"]) for axis in snapshots[role + ".png"]],
                                 [(axis["x"], axis["y"]) for axis in axes])
                svg = ET.parse(data["review"] / (role + ".svg")).getroot()
                groups = [node for node in svg.iter() if node.get("id", "").startswith("points_")]
                self.assertEqual(len(groups), 8)
                links = [node for group in groups for node in group.iter() if node.tag.endswith("}a")]
                self.assertEqual(len(links), expected_links)
                for node in links:
                    href = node.get("{http://www.w3.org/1999/xlink}href") or node.get("href")
                    url = urlsplit(href)
                    self.assertEqual(node.get("target"), "_blank")
                    self.assertIn("noopener", node.get("rel", ""))
                    side, pitch_id = node.get("data-cohort"), node.get("data-pitch-id")
                    frame, origin = int(node.get("data-source-frame")), int(node.get("data-origin-frame"))
                    self.assertIn(side, {"a", "b"})
                    bundle = next(value for value in data["bundles"].values() if value["pitcher_id"] == "pitcher_" + side)
                    clip = next(clip for clip in bundle["clips"] if clip["pitch_id"] == pitch_id)
                    self.assertTrue(0 <= frame < clip["frame_count"])
                    self.assertIn(origin, range(clip["events"]["foot_plant"]["frame_bounds"][0],
                                               clip["events"]["foot_plant"]["frame_bounds"][1] + 1))
                    self.assertEqual(clip["rows"][frame][role + "_coordinate_status"], "calculated_from_model_xy")
                    self.assertTrue((data["review"] / unquote(url.path)).is_file())
                    self.assertEqual(parse_qs(url.fragment), {"frame": [str(frame)], "request": ["1"]})
                    self.assertTrue(any(child.tag.endswith("}title") and child.text for child in node))
            # Missing samples may be NaN-separated or split into multiple paths;
            # neither representation may connect frames1 and4 of the first clip.
            for axis in snapshots["throwing_elbow.svg"][:2]:
                for _, values in axis["lines"]:
                    for first, second in zip(values, values[1:]):
                        if all(isinstance(value, (int, float)) and math.isfinite(value) and 90 <= value <= 97 for value in (first, second)):
                            self.assertEqual(second - first, 1.)
            for side, bundle in zip(("a", "b"), data["bundles"].values(), strict=True):
                for index, clip in enumerate(bundle["clips"]):
                    child = HtmlData((data["review"] / f"source_{side}_{index:03d}.html").read_text(encoding="utf-8"))
                    player = next(value for value in child.json_values if "clips" in value)["clips"][0]
                    self.assertEqual(player["rows"], clip["rows"])
                    self.assertEqual(player["fps_fraction"], clip["fps_fraction"])
            for name, asset in (("motion_viewer.js", "native_motion_viewer.js"), ("frame_link.js", "native_motion_frame_link.js")):
                self.assertEqual((data["review"] / name).read_bytes(), files("pitch_analysis").joinpath("review_assets", asset).read_bytes())
            for ref in result["artifacts"].values():
                self.assertEqual(reference(data["root"], data["root"] / ref["path"]), ref)
            for key in ("new_inference_calls", "new_tracking_replays", "new_ground_truth_labels"):
                self.assertEqual(result[key], 0)
            self.assertIsNone(result["usable_for_analysis"])
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertFalse(result["base_player_modified"])
            self.assertFalse(result["samples_resampled"])
            self.assertFalse(result["browser_interaction_verified"])
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertEqual(data["bundles"], before_bundles)

    def test_changed_report_or_source_is_rejected_before_plot_or_output(self):
        for change in ("source", "report"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                if change == "source":
                    path = data["root"] / "saved/a_001/source.mp4"
                    path.write_bytes(path.read_bytes() + b"changed")
                else:
                    payload = read_json(data["reports"][0])
                    payload["clips"][0]["events"]["foot_plant"]["frame_bounds"] = [0, 0]
                    timing_fixtures.overwrite_json(data["reports"][0], payload)
                with patch("pitch_analysis.analysis.native_cohort_curves._plot") as plot:
                    with self.assertRaises(ValueError):
                        self.run_export(data)
                    plot.assert_not_called()
                self.assertFalse(data["review"].exists())

    def test_existing_external_or_analysis_root_output_is_refused_without_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            data["review"].mkdir(parents=True)
            sentinel = data["review"] / "keep.txt"
            sentinel.write_text("Keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.run_export(data)
            for output in (data["root"] / "outside", data["root"] / "analysis_results"):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    self.run_export(data, output=output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "Keep")

    def test_cli_dispatches_two_saved_reports_and_returns_nonzero_on_rejection(self):
        args = ["pitch-analysis", "review-native-cohort-curves", "a.json", "b.json", "--output", "analysis_results/curves"]
        result = {"status": "cohort_curve_review_created", "clip_count": 3, "source_frames": 24,
                  "origin_candidate_paths": 4, "new_inference_calls": 0}
        with patch("sys.argv", args), \
             patch("pitch_analysis.analysis.native_cohort_curves.write_cohort_curve_review", return_value=result) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no inference")), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), ["a.json", "b.json"], "analysis_results/curves")
        self.assertEqual(json.loads(stream.getvalue())["status"], "cohort_curve_review_created")
        with patch("sys.argv", args), \
             patch("pitch_analysis.analysis.native_cohort_curves.write_cohort_curve_review", side_effect=ValueError("Source changed")), \
             redirect_stdout(StringIO()) as stream:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "failed", "error": "Source changed"})


if __name__ == "__main__":
    unittest.main()
