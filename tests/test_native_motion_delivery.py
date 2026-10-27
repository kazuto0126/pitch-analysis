"""One-command saved-motion delivery preserves three existing stage contracts."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from html.parser import HTMLParser
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import test_native_profile_viewer as viewer_fixtures
from pitch_analysis.analysis.native_motion_delivery import write_motion_report
from pitch_analysis.analysis.native_motion_events import write_event_comparison
from pitch_analysis.analysis.native_descriptive_profile import write_descriptive_profile
from pitch_analysis.analysis.native_profile_viewer import write_profile_viewer
from pitch_analysis.cli import main
from pitch_analysis.native_pose_io import read_json, reference, write_json


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.links.append(value)


def refs_in(value):
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            yield value
        else:
            for child in value.values():
                yield from refs_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs_in(child)


class NativeMotionDeliveryTests(unittest.TestCase):
    def fixture(self, root):
        data = viewer_fixtures.NativeProfileViewerTests().fixture(root)
        for clip in data["bundle"]["clips"]:
            clip["event_review_scope"] = {"kind": "full_ground_truth"}
        data["config"] = root / "request_a.json"
        data["delivery"] = root / "analysis_results" / "complete_delivery"
        return data

    def load(self, data, _root, config, output):
        loaded = deepcopy(data["bundles"][Path(config).resolve()])
        loaded["output"] = Path(output).resolve()
        for clip in loaded["clips"]:
            source = data["root"] / clip["source_refs"]["overlay_ref"]["path"]
            clip["overlay_url"] = os.path.relpath(source, loaded["output"] / "viewer").replace("\\", "/")
        return loaded

    def loaders(self, stack, data):
        loader = lambda *args: self.load(data, *args)
        for name in ("pitch_analysis.analysis.native_motion_delivery.load_event_clips",
                     "pitch_analysis.analysis.native_motion_events.load_event_clips",
                     "pitch_analysis.analysis.native_timing_comparison.load_event_clips"):
            stack.enter_context(patch(name, side_effect=loader))
        stack.enter_context(patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")))
        stack.enter_context(patch("cv2.VideoCapture", side_effect=AssertionError("saved motion only")))

    def test_real_three_stage_delivery_creates_one_bound_entry_without_source_mutation(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with ExitStack() as stack:
                self.loaders(stack, data)
                stage_curves = stack.enter_context(patch(
                    "pitch_analysis.analysis.native_motion_delivery.write_stage_curves",
                    side_effect=AssertionError("Optional stage curves are disabled by default")))
                result = write_motion_report(data["root"], data["config"], data["delivery"])
            stage_curves.assert_not_called()
            self.assertEqual(result["schema_version"], "native-descriptive-motion-delivery-v1")
            self.assertEqual(result["status"], "motion_report_created")
            self.assertEqual(result["pitcher_id"], "custom_pitcher_07")
            self.assertEqual((result["clip_count"], result["source_frames"]), (2, 16))
            self.assertEqual((result["timing_pairs"], result["comparable_pairs"], result["unavailable_pairs"]), (4, 2, 2))
            self.assertEqual(result, read_json(data["delivery"] / "delivery_manifest.json"))
            self.assertEqual(set(result["stages"]), {"events", "profile", "review"})
            self.assertNotIn("stage_curve_summary", result)
            self.assertNotIn("區段內模型讀值範圍", (data["delivery"] / "START_HERE.html").read_text(encoding="utf-8"))
            for relative in ("events/event_comparison.json", "profile/profile.json", "review/review_profile.html"):
                self.assertTrue((data["delivery"] / relative).is_file())
            self.assertIn(reference(data["root"], data["config"]), result["source_refs"])
            for ref in refs_in(result):
                self.assertEqual(reference(data["root"], data["root"] / ref["path"]), ref)
            entry = data["delivery"] / "START_HERE.html"
            links = Links(entry.read_text(encoding="utf-8")).links
            self.assertTrue(links)
            for link in links:
                url = urlsplit(link)
                self.assertEqual((url.scheme, url.netloc), ("", ""))
                path = (entry.parent / unquote(url.path)).resolve()
                self.assertTrue(path.is_relative_to(data["delivery"]))
                self.assertTrue(path.is_file())
            profile = read_json(data["delivery"] / "profile/profile.json")
            self.assertEqual(profile["clips"][1]["events"]["leg_lift"]["status"], "uncertain")
            self.assertEqual(profile["summary"]["joint_unavailable_summaries"], 4)
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertEqual(result["new_tracking_replays"], 0)
            self.assertEqual(result["new_ground_truth_labels"], 0)
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertIsNone(result["usable_for_analysis"])
            self.assertFalse(result["formal_reference_promotion"])
            self.assertFalse(result["browser_interaction_verified"])
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_existing_writers_are_called_in_order_with_only_the_previous_artifact(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            calls = []
            def wrap(name, real):
                def run(root, source, output):
                    calls.append((name, Path(source), Path(output)))
                    return real(root, source, output)
                return run
            with ExitStack() as stack:
                self.loaders(stack, data)
                for name, real in (("write_event_comparison", write_event_comparison),
                                   ("write_descriptive_profile", write_descriptive_profile),
                                   ("write_profile_viewer", write_profile_viewer)):
                    stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery." + name,
                                              side_effect=wrap(name, real)))
                write_motion_report(data["root"], data["config"], data["delivery"])
            self.assertEqual(calls, [
                ("write_event_comparison", data["config"], data["delivery"] / "events"),
                ("write_descriptive_profile", data["delivery"] / "events/event_comparison.json", data["delivery"] / "profile"),
                ("write_profile_viewer", data["delivery"] / "profile/profile.json", data["delivery"] / "review"),
            ])

    def stage_curve_fixture(self, data, root, source, output):
        self.assertEqual(Path(root), data["root"])
        self.assertEqual(Path(source), data["delivery"] / "events/event_comparison.json")
        self.assertEqual(Path(output), data["delivery"] / "stage_curves")
        output.mkdir(parents=True, exist_ok=False)
        (output / "report.html").write_text("<html>Saved model readings</html>", encoding="utf-8")
        result = {"schema_version": "native-stage-curves-v1", "status": "stage_curves_created",
                  "pitcher_id": "custom_pitcher_07", "summary": {
                      "clip_count": 2, "source_frames": 16, "stage_count": 8,
                      "event_confirmed_stages": 6, "event_unresolved_stages": 2,
                      "joint_summary_count": 16, "records": [{"kept_in_component_only": True}]}}
        write_json(output / "stage_curves.json", result)
        return result

    def test_optional_stage_curves_run_after_review_and_extend_only_the_final_entry(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            calls = []
            def wrap(name, real):
                def run(root, source, output):
                    calls.append(name)
                    return real(root, source, output)
                return run
            with ExitStack() as stack:
                self.loaders(stack, data)
                for name, real in (("write_event_comparison", write_event_comparison),
                                   ("write_descriptive_profile", write_descriptive_profile),
                                   ("write_profile_viewer", write_profile_viewer)):
                    stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery." + name,
                                              side_effect=wrap(name, real)))
                def curves(root, source, output):
                    calls.append("write_stage_curves")
                    self.assertTrue((data["delivery"] / "review/profile_viewer_manifest.json").is_file())
                    self.assertFalse((data["delivery"] / "START_HERE.html").exists())
                    return self.stage_curve_fixture(data, root, source, output)
                stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery.write_stage_curves",
                                          side_effect=curves))
                result = write_motion_report(data["root"], data["config"], data["delivery"], include_stage_curves=True)
            self.assertEqual(calls, ["write_event_comparison", "write_descriptive_profile", "write_profile_viewer", "write_stage_curves"])
            self.assertEqual(result["completed_stages"], ["events", "profile", "review", "stage_curves"])
            self.assertEqual(result["stage_curve_summary"], {
                "clip_count": 2, "source_frames": 16, "stage_count": 8,
                "event_confirmed_stages": 6, "event_unresolved_stages": 2, "joint_summary_count": 16})
            self.assertNotIn("records", result["stage_curve_summary"])
            self.assertEqual(result["stages"]["stage_curves"]["manifest_ref"],
                             reference(data["root"], data["delivery"] / "stage_curves/stage_curves.json"))
            entry = (data["delivery"] / "START_HERE.html").read_text(encoding="utf-8")
            self.assertIn("區段內模型讀值範圍", entry)
            self.assertIn("stage_curves/report.html", Links(entry).links)
            self.assertIn("缺值／退化影格", entry)
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertIsNone(result["usable_for_analysis"])
            self.assertFalse(result["formal_reference_promotion"])

    def test_real_four_stage_delivery_binds_stage_counts_and_all_report_links(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with ExitStack() as stack:
                self.loaders(stack, data)
                result = write_motion_report(data["root"], data["config"], data["delivery"], include_stage_curves=True)
            curves = read_json(data["delivery"] / "stage_curves/stage_curves.json")
            self.assertEqual(curves["schema_version"], "native-stage-curves-v1")
            self.assertEqual(curves["status"], "stage_curves_created")
            self.assertEqual(result["completed_stages"], ["events", "profile", "review", "stage_curves"])
            expected_counts = {"clip_count": 2, "source_frames": 16, "stage_count": 8,
                               "event_confirmed_stages": 6, "event_unresolved_stages": 2,
                               "joint_summary_count": 16}
            self.assertEqual(result["stage_curve_summary"], expected_counts)
            self.assertEqual({key: curves["summary"][key] for key in expected_counts}, expected_counts)
            self.assertEqual(len(curves["summary"]["records"]), 8)
            self.assertEqual(curves["source_ref"],
                             reference(data["root"], data["delivery"] / "events/event_comparison.json"))
            report = data["delivery"] / "stage_curves/report.html"
            self.assertIn("區段內模型讀值範圍", report.read_text(encoding="utf-8"))
            self.assertIn("stage_curves/report.html", Links((data["delivery"] / "START_HERE.html").read_text(encoding="utf-8")).links)
            links = Links(report.read_text(encoding="utf-8")).links
            self.assertTrue(any("#frame=" in link for link in links))
            self.assertTrue(any(link.endswith(".csv") for link in links))
            for link in links:
                url = urlsplit(link)
                self.assertEqual((url.scheme, url.netloc), ("", ""))
                target = (report.parent / unquote(url.path)).resolve()
                self.assertTrue(target.is_relative_to(data["delivery"] / "stage_curves"))
                self.assertTrue(target.is_file(), link)
            unresolved = [row for row in curves["summary"]["records"] if row["status"] == "unavailable"]
            self.assertEqual(len(unresolved), 2)
            for row in unresolved:
                for joint in row["joints"].values():
                    self.assertIsNone(joint["possible_window"]["total_frames"])
                    self.assertIsNone(joint["possible_window"]["sample_span_deg"])
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_optional_stage_failure_keeps_prior_outputs_and_marks_incomplete(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp).resolve())
            def fail(root, source, output):
                output.mkdir(parents=True)
                (output / "partial.txt").write_text("Keep failed stage evidence", encoding="utf-8")
                raise ValueError("Fixture curve failure")
            with ExitStack() as stack:
                self.loaders(stack, data)
                stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery.write_stage_curves", side_effect=fail))
                with self.assertRaisesRegex(ValueError, "Fixture curve failure"):
                    write_motion_report(data["root"], data["config"], data["delivery"], include_stage_curves=True)
            manifest = read_json(data["delivery"] / "delivery_manifest.json")
            self.assertEqual(manifest["status"], "incomplete")
            self.assertEqual(manifest["failed_stage"], "stage_curves")
            self.assertEqual(manifest["completed_stages"], ["events", "profile", "review"])
            self.assertFalse((data["delivery"] / "START_HERE.html").exists())
            self.assertTrue((data["delivery"] / "stage_curves/partial.txt").is_file())
            self.assertTrue((data["delivery"] / "events/event_comparison.json").is_file())
            self.assertTrue((data["delivery"] / "review/profile_viewer_manifest.json").is_file())
            with self.assertRaises(FileExistsError):
                write_motion_report(data["root"], data["config"], data["delivery"], include_stage_curves=True)

    def test_optional_component_cohort_or_counts_mismatch_never_creates_success_entry(self):
        for change in ("pitcher", "count", "confirmed", "boolean"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                def forged(root, source, output):
                    result = self.stage_curve_fixture(data, root, source, output)
                    if change == "pitcher":
                        result["pitcher_id"] = "wrong_pitcher"
                    elif change == "count":
                        result["summary"]["source_frames"] = 999
                    elif change == "confirmed":
                        result["summary"]["event_confirmed_stages"] = 7
                        result["summary"]["event_unresolved_stages"] = 1
                    else:
                        result["summary"]["clip_count"] = True
                    return result
                with ExitStack() as stack:
                    self.loaders(stack, data)
                    stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery.write_stage_curves", side_effect=forged))
                    with self.assertRaisesRegex(ValueError, "Stage-curve component cohort"):
                        write_motion_report(data["root"], data["config"], data["delivery"], include_stage_curves=True)
                manifest = read_json(data["delivery"] / "delivery_manifest.json")
                self.assertEqual((manifest["status"], manifest["failed_stage"]), ("incomplete", "finalize"))
                self.assertEqual(manifest["completed_stages"], ["events", "profile", "review", "stage_curves"])
                self.assertFalse((data["delivery"] / "START_HERE.html").exists())

    def test_invalid_preflight_stops_before_directory_or_any_writer(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp).resolve()
            output = root / "analysis_results" / "invalid"
            with ExitStack() as stack:
                stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery.load_event_clips",
                                          side_effect=ValueError("Source GT does not match")))
                writers = [stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery." + name))
                           for name in ("write_event_comparison", "write_descriptive_profile", "write_profile_viewer")]
                with self.assertRaisesRegex(ValueError, "Source GT does not match"):
                    write_motion_report(root, root / "bad.json", output)
            self.assertFalse(output.exists())
            for writer in writers:
                writer.assert_not_called()

    def test_stage_failure_records_partial_progress_without_success_entry_or_later_calls(self):
        stages = (("events", "write_event_comparison", write_event_comparison),
                  ("profile", "write_descriptive_profile", write_descriptive_profile),
                  ("review", "write_profile_viewer", write_profile_viewer))
        for failed_index, (failed_stage, _, _) in enumerate(stages):
            with self.subTest(stage=failed_stage), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp).resolve())
                called = []
                def wrap(stage, real):
                    def run(root, source, output):
                        called.append(stage)
                        if stage == failed_stage:
                            (data["delivery"] / "partial.txt").write_text("Keep evidence", encoding="utf-8")
                            raise ValueError("Fixture stage failure: " + stage)
                        return real(root, source, output)
                    return run
                with ExitStack() as stack:
                    self.loaders(stack, data)
                    for stage, name, real in stages:
                        stack.enter_context(patch("pitch_analysis.analysis.native_motion_delivery." + name,
                                                  side_effect=wrap(stage, real)))
                    with self.assertRaisesRegex(ValueError, "Fixture stage failure"):
                        write_motion_report(data["root"], data["config"], data["delivery"])
                self.assertEqual(called, [row[0] for row in stages[:failed_index + 1]])
                manifest = read_json(data["delivery"] / "delivery_manifest.json")
                self.assertEqual(manifest["status"], "incomplete")
                self.assertEqual(manifest["failed_stage"], failed_stage)
                self.assertEqual(manifest["completed_stages"], [row[0] for row in stages[:failed_index]])
                self.assertIn("Fixture stage failure", str(manifest["error"]))
                self.assertFalse((data["delivery"] / "START_HERE.html").exists())
                self.assertEqual((data["delivery"] / "partial.txt").read_text(encoding="utf-8"), "Keep evidence")
                with self.assertRaises(FileExistsError):
                    write_motion_report(data["root"], data["config"], data["delivery"])
                self.assertEqual(read_json(data["delivery"] / "delivery_manifest.json"), manifest)

    def test_existing_external_or_analysis_root_output_is_refused_without_writers(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp).resolve()
            existing = root / "analysis_results" / "existing"
            existing.mkdir(parents=True)
            sentinel = existing / "keep.txt"
            sentinel.write_text("Keep", encoding="utf-8")
            with patch("pitch_analysis.analysis.native_motion_delivery.load_event_clips") as loader:
                with self.assertRaises(FileExistsError):
                    write_motion_report(root, "unused.json", existing)
                for output in (root / "outside", root / "analysis_results"):
                    with self.subTest(output=output), self.assertRaises(ValueError):
                        write_motion_report(root, "unused.json", output)
                loader.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "Keep")

    def test_cli_dispatches_one_saved_motion_request_without_pose(self):
        result = {"status": "motion_report_created", "pitcher_id": "custom_pitcher_07",
                  "clip_count": 2, "source_frames": 16, "timing_pairs": 4,
                  "comparable_pairs": 2, "unavailable_pairs": 2, "new_inference_calls": 0}
        with patch("sys.argv", ["pitch-analysis", "build-native-motion-report", "request.json",
                                "--output", "analysis_results/delivery"]), \
             patch("pitch_analysis.analysis.native_motion_delivery.write_motion_report", return_value=result) as writer, \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no inference")), \
             redirect_stdout(StringIO()) as stream:
            main()
        writer.assert_called_once_with(Path.cwd(), "request.json", "analysis_results/delivery")
        emitted = json.loads(stream.getvalue())
        self.assertEqual(emitted["status"], "motion_report_created")
        self.assertEqual(emitted["new_inference_calls"], 0)

    def test_cli_rejection_returns_nonzero_without_claiming_completed_delivery(self):
        with patch("sys.argv", ["pitch-analysis", "build-native-motion-report", "request.json",
                                "--output", "analysis_results/delivery"]), \
             patch("pitch_analysis.analysis.native_motion_delivery.write_motion_report",
                   side_effect=ValueError("Source changed")), \
             patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("no inference")), \
             redirect_stdout(StringIO()) as stream:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "failed", "error": "Source changed"})


if __name__ == "__main__":
    unittest.main()
