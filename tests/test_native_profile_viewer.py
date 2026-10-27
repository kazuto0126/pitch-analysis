"""Profile summaries link only to their bound source frames and saved ball pairs."""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction
from importlib.resources import files
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import test_native_descriptive_profile as profile_fixtures
import test_native_motion_events as event_fixtures
import test_native_timing_comparison as timing_fixtures
from test_native_timing_viewer import HtmlData

from pitch_analysis.analysis.native_motion_events import describe_events
from pitch_analysis.analysis.native_motion_transition import describe_manual_event_transitions
from pitch_analysis.analysis.native_profile_viewer import write_profile_viewer
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference


class NativeProfileViewerTests(unittest.TestCase):
    def fixture(self, root, *, single=False):
        helper = profile_fixtures.DescriptiveProfileExportTests()
        data = helper.fixture(root)
        bundle = data["bundles"][root / "request_a.json"]
        if single:
            bundle["clips"] = bundle["clips"][:1]
        else:
            clip = bundle["clips"][1]
            raw = {name: event_fixtures.exact(index) for name, index in (
                ("preparation_start", 0), ("leg_lift", 1), ("foot_plant", 3),
                ("approximate_release", 5), ("follow_through_end", 7))}
            raw["leg_lift"] = event_fixtures.ranged(1, 1, status="uncertain", note="Candidate only")
            clip.update(describe_events(raw, Fraction(clip["fps_fraction"]), clip["rows"]))
        refs = [bundle["request_ref"]]
        for clip in bundle["clips"]:
            clip["source_refs"]["overlay_ref"] = deepcopy(clip["source_refs"]["video_ref"])
            refs.extend(clip["source_refs"].values())
        bundle["source_refs"] = refs
        payload = data["payloads"][0]
        payload["clip_count"] = len(bundle["clips"])
        payload["clips"] = [{key: deepcopy(value) for key, value in clip.items()
                             if key not in {"rows", "overlay_url"}} for clip in bundle["clips"]]
        payload["manual_stage_readouts"] = [{"pitch_id": clip["pitch_id"], **stage}
                                            for clip in bundle["clips"]
                                            for stage in describe_manual_event_transitions(clip)]
        timing_fixtures.overwrite_json(data["reports"][0], payload)
        data["profile_result"] = helper.run_export(data)
        data["profile"] = data["output"] / "profile.json"
        data["viewer"] = root / "analysis_results" / "profile_viewer"
        data["bundle"] = bundle
        return data

    def run_viewer(self, data, output=None):
        with patch("pitch_analysis.analysis.native_timing_comparison.load_event_clips",
                   side_effect=lambda _root, request, _output: data["bundles"][Path(request).resolve()]), \
             patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
             patch("cv2.VideoCapture", side_effect=AssertionError("saved curves only; no decoding")):
            return write_profile_viewer(data["root"], data["profile"], data["viewer"] if output is None else output)

    def main_data(self, data):
        html = HtmlData((data["viewer"] / "review_profile.html").read_text(encoding="utf-8"))
        return html, next(value for value in html.json_values if value.get("mode") == "same_pitcher_profile")

    def test_canonical_pairs_source_rows_scripts_and_inputs_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before_files = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            before_bundle = deepcopy(data["bundle"])
            result = self.run_viewer(data)
            self.assertEqual(result["schema_version"], "native-descriptive-profile-viewer-v1")
            self.assertEqual(result["status"], "profile_viewer_created")
            self.assertEqual((result["clip_count"], result["source_frames"]), (2, 16))
            self.assertEqual((result["total_pairs"], result["comparable_pairs"], result["unavailable_pairs"]), (4, 2, 2))
            self.assertEqual(result["profile_ref"], reference(data["root"], data["profile"]))
            self.assertEqual(read_json(data["viewer"] / "profile_viewer_manifest.json"), result)
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertEqual(result["new_tracking_replays"], 0)
            self.assertEqual(result["new_ground_truth_labels"], 0)
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertIsNone(result["usable_for_analysis"])
            self.assertFalse(result["browser_interaction_verified"])
            self.assertFalse(result["base_player_modified"])
            parent, embedded = self.main_data(data)
            self.assertEqual(len(parent.iframes), 2)
            self.assertEqual(embedded["pitcher_id"], "custom_pitcher_07")
            expected_pairs = [{"timing_key": stage["timing_key"], **pair}
                              for stage in data["profile_result"]["summary"]["stages"] for pair in stage["timing_pairs"]]
            self.assertEqual(embedded["pairs"], expected_pairs)
            self.assertTrue(all(pair["a_pitch_id"] != pair["b_pitch_id"] for pair in embedded["pairs"]))
            self.assertEqual([stage["key"] for stage in embedded["stages"]], list(profile_fixtures.KEYS))
            for stage, expected in zip(embedded["stages"], data["profile_result"]["summary"]["stages"], strict=True):
                self.assertEqual(stage["joints"], expected["joints"])
                self.assertEqual(stage["timing_envelope_seconds_fraction"], expected["timing_envelope_seconds_fraction"])
            self.assertEqual([cohort["side"] for cohort in embedded["cohorts"]], ["a", "b"])
            self.assertEqual(embedded["cohorts"][0]["clips"], embedded["cohorts"][1]["clips"])
            self.assertEqual([path.name for path in sorted(data["viewer"].glob("source_*.html"))],
                             ["source_000.html", "source_001.html"])
            for index, source in enumerate(data["bundle"]["clips"]):
                path = data["viewer"] / f"source_{index:03d}.html"
                child = HtmlData(path.read_text(encoding="utf-8"))
                player = next(value for value in child.json_values if "clips" in value)["clips"][0]
                self.assertEqual(player["pitch_id"], source["pitch_id"])
                self.assertEqual(player["rows"], source["rows"])
                self.assertEqual(player["fps_fraction"], source["fps_fraction"])
                self.assertEqual(player["events"], source["events"])
                self.assertEqual((path.parent / unquote(player["overlay_url"])).resolve(),
                                 data["root"] / source["source_refs"]["overlay_ref"]["path"])
            for output_name, asset in (("motion_viewer.js", "native_motion_viewer.js"),
                                       ("frame_link.js", "native_motion_frame_link.js"),
                                       ("timing_viewer.js", "native_timing_viewer.js")):
                self.assertEqual((data["viewer"] / output_name).read_bytes(),
                                 files("pitch_analysis").joinpath("review_assets", asset).read_bytes())
            for ref in result["artifacts"].values():
                self.assertEqual(reference(data["root"], data["root"] / ref["path"]), ref)
            self.assertEqual({path: path.read_bytes() for path in before_files}, before_files)
            self.assertEqual(data["bundle"], before_bundle)

    def test_unknown_candidate_and_null_joint_counts_remain_unknown(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            self.run_viewer(data)
            _, embedded = self.main_data(data)
            candidate = embedded["cohorts"][0]["clips"][1]["events"]["leg_lift"]
            self.assertEqual(candidate["status"], "uncertain")
            self.assertEqual(candidate["frame_bounds"], [1, 1])
            self.assertIsNone(candidate["frame_index"])
            for stage in embedded["stages"][:2]:
                self.assertEqual(stage["timing_unavailable_clip_ids"], ["a_002"])
                for joint in stage["joints"].values():
                    row = next(row for row in joint["clip_summaries"] if row["pitch_id"] == "a_002")
                    self.assertIsNone(row["total_pairs"])
                    self.assertIsNone(row["calculated_pairs"])
                    self.assertIsNone(row["min_delta_deg"])
            self.assertEqual(read_json(data["profile"]), data["profile_result"])

    def test_single_clip_has_one_source_and_does_not_invent_a_self_comparison(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve(), single=True)
            result = self.run_viewer(data)
            self.assertEqual((result["clip_count"], result["source_frames"]), (1, 8))
            self.assertEqual((result["total_pairs"], result["comparable_pairs"], result["unavailable_pairs"]), (0, 0, 0))
            _, embedded = self.main_data(data)
            self.assertEqual(embedded["pairs"], [])
            self.assertEqual([cohort["side"] for cohort in embedded["cohorts"]], ["a"])
            self.assertEqual(len(list(data["viewer"].glob("source_*.html"))), 1)

    def test_tampered_summary_identity_or_clip_list_is_rejected_before_output(self):
        for change in ("count", "joint", "missing_stage", "pair", "pitcher", "clips"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                payload = read_json(data["profile"])
                if change == "count":
                    payload["summary"]["timing_comparable_pairs"] = 999
                elif change == "joint":
                    payload["summary"]["stages"][2]["joints"]["throwing_elbow"]["clip_summaries"][0]["max_delta_deg"] = 999.
                elif change == "missing_stage":
                    payload["summary"]["stages"].pop()
                elif change == "pair":
                    payload["summary"]["stages"][0]["timing_pairs"][0]["a_pitch_id"] = "invented"
                elif change == "pitcher":
                    payload["pitcher_id"] = "another_pitcher"
                else:
                    payload["clips"].reverse()
                timing_fixtures.overwrite_json(data["profile"], payload)
                with self.assertRaises(ValueError):
                    self.run_viewer(data)
                self.assertFalse(data["viewer"].exists())

    def test_changed_bound_report_or_media_is_rejected_before_output(self):
        for target in ("report", "video"):
            with self.subTest(target=target), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                path = data["reports"][0] if target == "report" else data["root"] / "saved/a_001/source.mp4"
                path.write_bytes(path.read_bytes() + b"changed")
                with self.assertRaises(ValueError):
                    self.run_viewer(data)
                self.assertFalse(data["viewer"].exists())

    def test_existing_external_and_analysis_root_outputs_are_refused(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            data["viewer"].mkdir(parents=True)
            sentinel = data["viewer"] / "keep.txt"
            sentinel.write_text("Keep existing output", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.run_viewer(data)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "Keep existing output")
            for output in (data["root"] / "external", data["root"] / "analysis_results"):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    self.run_viewer(data, output=output)

    def test_cli_dispatches_one_saved_profile_without_inference(self):
        result = {"status": "profile_viewer_created", "clip_count": 2, "source_frames": 16,
                  "total_pairs": 4, "new_inference_calls": 0}
        with patch("sys.argv", ["pitch-analysis", "review-native-profile", "profile.json",
                                "--output", "analysis_results/viewer"]), \
             patch("pitch_analysis.analysis.native_profile_viewer.write_profile_viewer", return_value=result) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose")), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), "profile.json", "analysis_results/viewer")
        emitted = json.loads(stream.getvalue())
        self.assertEqual(emitted["status"], "profile_viewer_created")
        self.assertEqual(emitted["new_inference_calls"], 0)

    def test_cli_returns_nonzero_when_profile_is_rejected(self):
        with patch("sys.argv", ["pitch-analysis", "review-native-profile", "profile.json",
                                "--output", "analysis_results/viewer"]), \
             patch("pitch_analysis.analysis.native_profile_viewer.write_profile_viewer",
                   side_effect=ValueError("Saved summary changed")), \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no pose")), \
             redirect_stdout(StringIO()) as stream:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "failed", "error": "Saved summary changed"})


if __name__ == "__main__":
    unittest.main()
