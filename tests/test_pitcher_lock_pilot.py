"""The optional pilot binds operator regions to sources before any inference."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pitcher_lock_pilot", ROOT / "scripts/run_pitcher_lock_pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PitcherLockPilotTests(unittest.TestCase):
    def setUp(self):
        task_temp = ROOT / "temp" / "pitcher_lock_pilot_tests"
        task_temp.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=task_temp)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.output = self.root / "new_parent" / "output"
        self.config_path = self.root / "regions.json"
        self.model = self.root / "model.task"
        self.model.write_bytes(b"fixture model; never inferred")
        self.config = {"schema_version": "pitcher-region-pilot-v1", "status": "operator_confirmed",
                       "operator_confirmation": {"reviewer": "HSU", "reviewed_at_utc": "2026-10-19T01:02:03Z",
                                                 "note": "Regions checked on the original images"},
                       "pitcher_id": "fixture_pitcher", "region_semantics": pilot.REGION_SEMANTICS, "clips": []}
        self.original_metadata = {}
        for i in range(1, 4):
            pitch_id = f"pitch_{i:03d}"
            video = self.inputs / f"{pitch_id}.mp4"
            video.write_bytes(f"Fixture video {i}; no decoding required".encode())
            payload = {"schema_version": "pitch-input-v1", "pitch_id": pitch_id,
                       "pitcher": {"id": "fixture_pitcher", "throws": "RIGHT"},
                       "video": {"file": video.name, "camera_view": "rear_centerfield_broadcast",
                                 "horizontal_mirror": False, "playback_speed": 1.0,
                                 "contains_single_pitch": True, "continuous_shot": True,
                                 "subject_framing": "full_body"},
                       "context": {"season": None, "team": None, "pitch_type": None, "session_id": None}}
            metadata = self.inputs / f"{pitch_id}.json"
            metadata.write_text(json.dumps(payload), encoding="utf-8")
            self.original_metadata[pitch_id] = metadata.read_bytes()
            self.config["clips"].append({"pitch_id": pitch_id,
                                         "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                                         "subject_roi": [.1, .2, .4, .9]})
        self.write_config()

    def write_config(self):
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8")

    def run_pilot(self, **kwargs):
        return pilot.run_pilot(self.inputs, self.config_path, self.output, model_path=kwargs.get("model_path", self.model))

    def assert_preflight_rejection(self, message):
        with patch.object(pilot, "analyze_pitch") as analyze, self.assertRaisesRegex(ValueError, message):
            self.run_pilot()
        analyze.assert_not_called()
        self.assertFalse(self.output.parent.exists())

    def test_unconfirmed_rejected_before_model_resolution_or_output_creation(self):
        self.config["status"] = "proposed"
        self.config["operator_confirmation"] = None
        self.write_config()
        with patch.object(pilot, "analyze_pitch") as analyze, self.assertRaisesRegex(ValueError, "Operator confirmation"):
            self.run_pilot(model_path=self.root / "missing_model.task")
        analyze.assert_not_called()
        self.assertFalse(self.output.parent.exists())

    def test_confirmation_requires_reviewer_note_and_timezone_aware_datetime(self):
        original = deepcopy(self.config)
        for field, value in (("reviewer", " "), ("note", ""), ("reviewed_at_utc", "not-a-date"),
                             ("reviewed_at_utc", "2026-10-19T01:02:03"),
                             ("reviewed_at_utc", "2026-10-19")):
            with self.subTest(field=field, value=value):
                self.config = deepcopy(original)
                self.config["operator_confirmation"][field] = value
                self.write_config()
                self.assert_preflight_rejection("operator_confirmation")

    def test_one_late_video_sha_mismatch_rejects_the_entire_batch(self):
        (self.inputs / "pitch_003.mp4").write_bytes(b"changed last source")
        self.assert_preflight_rejection("pitch_003: video SHA-256")

    def test_metadata_must_match_pitch_id_pitcher_and_actual_video_filename(self):
        metadata = self.inputs / "pitch_003.json"
        original = json.loads(metadata.read_text(encoding="utf-8"))
        mutations = (("pitch_id", "pitch_004"), ("pitcher", {"id": "other_pitcher", "throws": "RIGHT"}),
                     ("video", {**original["video"], "file": "pitch_001.mp4"}))
        for field, value in mutations:
            with self.subTest(field=field):
                payload = {**original, field: value}
                metadata.write_text(json.dumps(payload), encoding="utf-8")
                self.assert_preflight_rejection("metadata|MP4 argument")

    def test_duplicate_or_unsafe_ids_and_invalid_count_rejected(self):
        original = deepcopy(self.config)
        for ids in (("pitch_001", "pitch_002", "pitch_001"),
                    ("pitch_001", "pitch_002", "../pitch_003"), ("pitch_001", "pitch_002")):
            with self.subTest(ids=ids):
                self.config = deepcopy(original)
                self.config["clips"] = [dict(original["clips"][0], pitch_id=value) for value in ids]
                self.write_config()
                self.assert_preflight_rejection("Duplicate|identifier|3–5")

    def test_roi_rejects_boolean_nonfinite_outside_and_reversed_values(self):
        invalid = ([True, .2, .4, .9], [float("nan"), .2, .4, .9], [.1, .2, float("inf"), .9],
                   [-.1, .2, .4, .9], [.1, .2, 1.1, .9], [.4, .2, .1, .9],
                   [.1, .2, .1, .9], [.1, .9, .4, .2], [".1", .2, .4, .9], [.1, .2, .4],
                   [10 ** 400, .2, .4, .9])
        for value in invalid:
            with self.subTest(value=value):
                self.config["clips"][-1]["subject_roi"] = value
                self.write_config()
                self.assert_preflight_rejection("subject_roi")

    def test_confirmed_regions_and_record_flag_passed_once_per_clip(self):
        seen = []

        def analyze(video, metadata, **kwargs):
            seen.append((Path(video).stem, kwargs))
            self.assertEqual(Path(metadata).read_bytes(), self.original_metadata[Path(video).stem])
            return {"status": "quality_gate_failed", "input_quality_status": "degraded",
                    "quality_gate_passed": False, "output_dir": str(self.output / "predictions" / Path(video).stem),
                    "review_required": True}

        with patch.object(pilot, "analyze_pitch", side_effect=analyze) as function:
            summary_path = self.run_pilot()
        self.assertEqual(function.call_count, 3)
        self.assertEqual([value[0] for value in seen], ["pitch_001", "pitch_002", "pitch_003"])
        for pitch_id, kwargs in seen:
            self.assertEqual(kwargs, {"output_root": self.output / "predictions", "model_path": self.model,
                                      "subject_roi": (.1, .2, .4, .9), "record_candidates": True})
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["attempted_count"], 3)
        self.assertEqual(summary["state"], "completed")
        self.assertEqual([item["status"] for item in summary["results"]], ["quality_gate_failed"] * 3)
        self.assertTrue(all(item["input_quality_status"] == "degraded" and not item["quality_gate_passed"]
                            for item in summary["results"]))
        self.assertEqual((self.output / "subject_region_config.json").read_bytes(), self.config_path.read_bytes())
        mapping = json.loads((self.output / "source_mapping.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping["model_sha256"], hashlib.sha256(self.model.read_bytes()).hexdigest())
        self.assertEqual(mapping["execution_type"], "explicit_operator_region_pilot")
        self.assertEqual(len(mapping["clips"]), 3)
        for source in mapping["clips"]:
            self.assertEqual(source["metadata_sha256"], hashlib.sha256(self.original_metadata[source["pitch_id"]]).hexdigest())
            self.assertEqual(Path(source["metadata_path"]).read_bytes(), self.original_metadata[source["pitch_id"]])
            context = json.loads(Path(source["metadata_path"]).read_text(encoding="utf-8"))["context"]
            self.assertTrue(all(value is None for value in context.values()))

    def test_summary_saved_after_each_attempt_exception_continues_without_retry(self):
        calls = []

        def analyze(video, metadata, **kwargs):
            durable = json.loads((self.output / "validation_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(durable["attempted_count"], len(calls))
            calls.append(Path(video).stem)
            if len(calls) == 2:
                raise RuntimeError("fixture model failed")
            return {"status": "needs_event_review", "input_quality_status": "accepted", "quality_gate_passed": True}

        with patch.object(pilot, "analyze_pitch", side_effect=analyze) as function:
            summary_path = self.run_pilot()
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(function.call_count, 3)
        self.assertEqual(summary["state"], "completed_with_failures")
        self.assertEqual([item["status"] for item in summary["results"]], ["needs_event_review", "failed", "needs_event_review"])
        self.assertEqual(summary["results"][1]["failure_reason"], "RuntimeError: fixture model failed")
        self.assertFalse((self.output / "validation_summary.json.tmp").exists())

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir(parents=True)
        sentinel = self.output / "validation_summary.json"
        sentinel.write_bytes(b"previous run")
        with patch.object(pilot, "analyze_pitch") as analyze, self.assertRaisesRegex(FileExistsError, "already exists"):
            self.run_pilot()
        analyze.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"previous run")
        self.assertEqual([path.name for path in self.output.iterdir()], ["validation_summary.json"])


if __name__ == "__main__":
    unittest.main()
