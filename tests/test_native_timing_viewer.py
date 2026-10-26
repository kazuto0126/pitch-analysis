"""Independent timing-review players preserve bound events and existing playback."""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction
from html.parser import HTMLParser
from importlib.resources import files
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import test_native_motion_events as event_fixtures
import test_native_timing_comparison as timing_fixtures

from pitch_analysis.analysis.native_motion_events import describe_events
from pitch_analysis.analysis.native_timing_viewer import write_timing_viewer
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


class HtmlData(HTMLParser):
    """Inspect embedded public player data without depending on layout or CSS."""
    def __init__(self, html):
        super().__init__()
        self.iframes, self.scripts, self.json_values = [], [], []
        self.current_script = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "iframe":
            self.iframes.append(attrs)
        if tag == "script":
            self.scripts.append(attrs)
            self.current_script = {"attrs": attrs, "text": ""}

    def handle_data(self, text):
        if self.current_script is not None:
            self.current_script["text"] += text

    def handle_endtag(self, tag):
        if tag == "script" and self.current_script is not None:
            if self.current_script["attrs"].get("type") == "application/json":
                self.json_values.append(json.loads(self.current_script["text"]))
            self.current_script = None


def dict_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from dict_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from dict_nodes(child)


class NativeTimingViewerTests(unittest.TestCase):
    def fixture(self, root):
        helper = timing_fixtures.TimingComparisonExportTests()
        data = helper.fixture(root)
        for bundle in data["bundles"].values():
            refs = [bundle["request_ref"]]
            for clip in bundle["clips"]:
                fps = Fraction(clip["fps_fraction"])
                for row in clip["rows"]:
                    row["timestamp_sec"] = float(Fraction(row["frame_index"]) / fps)
                clip["source_refs"]["overlay_ref"] = deepcopy(clip["source_refs"]["video_ref"])
                if bundle["pitcher_id"] == "pitcher_b":
                    gt_path = root / clip["source_refs"]["ground_truth_ref"]["path"]
                    gt = read_json(gt_path)
                    gt["labels"]["events"]["leg_lift"] = event_fixtures.ranged(
                        1, 1, status="uncertain", note="Candidate only, not a confirmed exact event")
                    timing_fixtures.overwrite_json(gt_path, gt)
                    clip["source_refs"]["ground_truth_ref"] = reference(root, gt_path)
                    clip.update(describe_events(gt["labels"]["events"], fps, clip["rows"]))
                refs.extend(clip["source_refs"].values())
            bundle["source_refs"] = refs
        for report, payload, bundle in zip(data["reports"], data["payloads"], data["bundles"].values(), strict=True):
            payload["clips"] = deepcopy([{key: value for key, value in clip.items() if key not in {"rows", "overlay_url"}}
                                          for clip in bundle["clips"]])
            timing_fixtures.overwrite_json(report, payload)
        data["comparison_result"] = helper.run_export(data)
        data["comparison"] = data["output"] / "timing_comparison.json"
        data["viewer"] = root / "analysis_results" / "timing_viewer"
        return data

    def run_viewer(self, data, *, loader_error=None):
        def load(_root, config, _output):
            if loader_error is not None:
                raise loader_error
            return data["bundles"][Path(config).resolve()]
        with patch("pitch_analysis.analysis.native_timing_comparison.load_event_clips", side_effect=load), \
             patch("subprocess.Popen", side_effect=AssertionError("no model process or browser")), \
             patch("cv2.VideoCapture", side_effect=AssertionError("saved sources only; do not decode")):
            return write_timing_viewer(data["root"], data["comparison"], data["viewer"])

    def test_scope_independent_players_original_script_and_source_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before_files = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            before_bundles = deepcopy(data["bundles"])
            result = self.run_viewer(data)
            self.assertEqual(result["status"], "timing_viewer_created")
            self.assertEqual((result["clip_count"], result["source_frames"]), (3, 24))
            self.assertEqual((result["total_pairs"], result["comparable_pairs"], result["unavailable_pairs"]), (8, 4, 4))
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertFalse(result["browser_interaction_verified"])
            self.assertEqual(read_json(data["viewer"] / "timing_viewer_manifest.json"), result)
            self.assertEqual((data["viewer"] / "motion_viewer.js").read_bytes(),
                             files("pitch_analysis").joinpath("review_assets/native_motion_viewer.js").read_bytes())
            for name in ("review_timing.html", "frame_link.js", "timing_viewer.js"):
                self.assertTrue((data["viewer"] / name).is_file())
            parent = HtmlData((data["viewer"] / "review_timing.html").read_text(encoding="utf-8"))
            self.assertEqual(len(parent.iframes), 2)
            pages = sorted([*data["viewer"].glob("a_*.html"), *data["viewer"].glob("b_*.html")])
            self.assertEqual([path.name for path in pages], ["a_000.html", "a_001.html", "b_000.html"])
            sources = {clip["pitch_id"]: clip for bundle in data["bundles"].values() for clip in bundle["clips"]}
            for path in pages:
                page = HtmlData(path.read_text(encoding="utf-8"))
                player_data = next(value for value in page.json_values if "clips" in value)
                self.assertEqual(len(player_data["clips"]), 1)
                clip = player_data["clips"][0]
                source = sources[clip["pitch_id"]]
                self.assertEqual(clip["fps_fraction"], source["fps_fraction"])
                self.assertEqual(clip["frame_count"], source["frame_count"])
                self.assertEqual(clip["rows"], source["rows"])
                self.assertEqual((path.parent / unquote(clip["overlay_url"])).resolve(),
                                 data["root"] / source["source_refs"]["overlay_ref"]["path"])
                script_names = [attrs.get("src") for attrs in page.scripts]
                self.assertLess(script_names.index("motion_viewer.js"), script_names.index("frame_link.js"))
            for node in dict_nodes(result["artifacts"]):
                if set(node) == {"path", "sha256"}:
                    self.assertEqual(reference(data["root"], data["root"] / node["path"]), node)
            self.assertEqual(data["bundles"], before_bundles)
            self.assertEqual({path: path.read_bytes() for path in before_files}, before_files)

    def test_uncertain_single_frame_candidates_stay_uncertain_in_parent_data(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            result = self.run_viewer(data)
            parent = HtmlData((data["viewer"] / "review_timing.html").read_text(encoding="utf-8"))
            candidates = [node for value in parent.json_values for node in dict_nodes(value)
                          if node.get("status") == "uncertain" and node.get("frame_bounds") == [1, 1]]
            self.assertTrue(candidates)
            self.assertTrue(all(node.get("frame_index") is None for node in candidates))
            self.assertEqual(result["unavailable_pairs"], 4)
            self.assertEqual(read_json(data["comparison"]), data["comparison_result"])
            original = next(bundle for bundle in data["bundles"].values() if bundle["pitcher_id"] == "pitcher_b")
            self.assertEqual(original["clips"][0]["events"]["leg_lift"]["status"], "uncertain")
            self.assertIsNone(original["clips"][0]["events"]["leg_lift"]["frame_index"])

    def test_forged_cached_deltas_ids_missing_duplicate_pairs_and_cohort_counts_are_rejected(self):
        for change in ("delta", "id", "missing_pair", "duplicate_pair", "cohort_count"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                payload = read_json(data["comparison"])
                if change == "delta":
                    pair = next(pair for pair in payload["pairs"] if pair["status"] != "unavailable")
                    pair["delta_seconds_bounds_fraction"] = ["999", "999"]
                elif change == "id":
                    payload["pairs"][0]["a_pitch_id"] = "invented_pitch"
                elif change == "missing_pair":
                    payload["pairs"].pop()
                elif change == "duplicate_pair":
                    payload["pairs"][-1] = deepcopy(payload["pairs"][0])
                else:
                    payload["cohorts"][0]["clip_count"] += 1
                timing_fixtures.overwrite_json(data["comparison"], payload)
                with self.assertRaises(ValueError):
                    self.run_viewer(data)
                self.assertFalse(data["viewer"].exists())

    def test_invalid_timeline_and_source_loader_out_of_bounds_errors_fail_before_output(self):
        for change in ("timeline", "event_bounds"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                if change == "timeline":
                    bundle = next(iter(data["bundles"].values()))
                    bundle["clips"][0]["rows"][0]["timestamp_sec"] = 999.
                    error = None
                else:
                    error = ValueError("Event frame bounds are outside the saved timeline")
                with self.assertRaises(ValueError):
                    self.run_viewer(data, loader_error=error)
                self.assertFalse(data["viewer"].exists())

    def test_existing_output_and_external_target_are_rejected_without_source_writes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            data["viewer"].mkdir(parents=True)
            sentinel = data["viewer"] / "keep.txt"
            sentinel.write_text("preserve existing viewer", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_timing_viewer(data["root"], data["comparison"], data["viewer"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve existing viewer")
            outside = data["root"] / "outside_analysis_results"
            with self.assertRaises(ValueError):
                write_timing_viewer(data["root"], data["comparison"], outside)
            self.assertFalse(outside.exists())

    def test_cli_dispatches_saved_comparison_and_returns_nonzero_on_rejection(self):
        result = {"status": "timing_viewer_created", "clip_count": 3, "source_frames": 24,
                  "total_pairs": 8, "comparable_pairs": 4, "unavailable_pairs": 4,
                  "new_inference_calls": 0, "browser_interaction_verified": False}
        args = ["pitch-analysis", "review-native-timing", "comparison.json", "--output", "analysis_results/viewer"]
        with patch("sys.argv", args), \
             patch("pitch_analysis.analysis.native_timing_viewer.write_timing_viewer", return_value=result) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no inference")), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), "comparison.json", "analysis_results/viewer")
        emitted = json.loads(stream.getvalue())
        self.assertEqual(emitted["status"], "timing_viewer_created")
        self.assertEqual(emitted["new_inference_calls"], 0)
        with patch("sys.argv", args), \
             patch("pitch_analysis.analysis.native_timing_viewer.write_timing_viewer", side_effect=ValueError("cached pair changed")), \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no inference")), \
             redirect_stdout(StringIO()) as stream:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "failed", "error": "cached pair changed"})


if __name__ == "__main__":
    unittest.main()
