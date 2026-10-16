"""Additional warnings require exact prediction lineage and never edit core data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pitch_analysis import major_review_hints as hints


def fixture():
    raw = b"frame_index,landmark,x,y,visibility\n0,RIGHT_ELBOW,.4,.5,.8\n"
    metadata = {"schema_version": "pitch-input-v1", "pitch_id": "synthetic_pitch",
                "pitcher": {"id": "synthetic_person", "throws": "LEFT"},
                "video": {"file": "clip.mp4", "camera_view": "rear_centerfield_broadcast",
                          "horizontal_mirror": False, "playback_speed": 1., "contains_single_pitch": True}}
    video = {"sha256": "1" * 64, "width": 10, "height": 20, "frame_count": 3,
             "timestamps_ms": [0., 1000 / 30, 2000 / 30]}
    capture = {"video": "unused/source.mp4", "model": "unused/model.task", "width": 10, "height": 20,
               "start_frame": 0, "end_frame": 2, "requested_frames": 3, "processed_frames": 3,
               "subject_selection": "rear_centerfield_broadcast",
               "selection_frames": [{"frame_index": index, "timestamp_ms": round(timestamp),
                                     "status": "selected", "selected_index": 0}
                                    for index, timestamp in enumerate(video["timestamps_ms"])]}
    frames = []
    for index, timestamp in enumerate(video["timestamps_ms"]):
        components = {key: False for key in hints.EVIDENCE_COMPONENTS}
        components[hints.EVIDENCE_COMPONENTS[index]] = index != 2
        frames.append({"frame_index": index, "timestamp_ms": timestamp,
                       "review_required": any(components.values()),
                       "reasons": [hints.EVIDENCE_COMPONENTS[index]] if any(components.values()) else [],
                       "evidence_state": components,
                       "diagnostics": {"bbox_state": "warning" if index == 1 else "no_warning",
                                       "disagreement_state": "seed_excluded" if index == 0 else "candidate_dependent",
                                       "association_status": "ambiguous", "candidate_slot_indices": [0, 2]}})
    clip = {"pitch_id": metadata["pitch_id"], "pitcher_id": metadata["pitcher"]["id"],
            "identity": {"throws": "LEFT", **{key: value for key, value in metadata["video"].items() if key != "file"}},
            "source": {"video_sha256": video["sha256"], "raw_csv_sha256": hashlib.sha256(raw).hexdigest(),
                       "capture_semantic_sha256": hints.capture_semantic_sha256(capture), "model_sha256": "2" * 64},
            "frame_count": 3, "frames": frames}
    bundle = {"schema_version": "major-review-development-evidence-v1", "status": "sealed_development_evidence",
              "development_scope": {"dataset": "synthetic test cohort", "clip_count": 1, "source_frames": 3,
                                    "evaluation_non_seed_frames": 2, "major_tp": 1, "major_fn": 1, "major_fp": 0,
                                    "known_misses": [{"pitch_id": metadata["pitch_id"], "frame_index": 2}]},
              "source_evidence": [{"id": "warnings", "path": "absent/do-not-read.json", "sha256": "3" * 64}],
              "clips": [clip]}
    return raw, metadata, video, capture, bundle


class MajorReviewHintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "analysis"
        self.output.mkdir()
        self.raw, self.metadata, self.video, self.capture, self.bundle = fixture()
        (self.output / "pose_raw.csv").write_bytes(self.raw)
        self.evidence = self.root / "bundle.json"
        self._write_bundle()
        self.addCleanup(patch.stopall)
        patch.object(hints, "BUNDLE_PATH", self.evidence).start()
        self.hash_patch = patch.object(hints, "BUNDLE_SHA256", hashlib.sha256(self.evidence.read_bytes()).hexdigest())
        self.hash_patch.start()

    def _write_bundle(self):
        self.evidence.write_text(json.dumps(self.bundle, allow_nan=False), encoding="utf-8")

    def _rebind_bundle(self):
        self._write_bundle()
        self.hash_patch.stop()
        self.hash_patch = patch.object(hints, "BUNDLE_SHA256", hashlib.sha256(self.evidence.read_bytes()).hexdigest())
        self.hash_patch.start()

    def _run(self, **overrides):
        params = {"input_metadata": self.metadata, "video_metadata": self.video,
                  "capture": self.capture, "model_sha256": "2" * 64}
        params.update(overrides)
        return json.loads(hints.write_major_review_hints(self.output, **params).read_text(encoding="utf-8"))

    def test_exact_source_preserves_union_seed_ambiguity_and_known_miss(self):
        result = self._run()
        self.assertEqual(result["status"], "evaluated_development_evidence")
        self.assertEqual(result["frames"], self.bundle["clips"][0]["frames"])
        self.assertEqual([row["review_required"] for row in result["frames"]], [True, True, False])
        self.assertEqual(result["review_required_frames"], 2)
        self.assertEqual(result["development_scope"]["known_misses"][0]["frame_index"], 2)
        self.assertIn("not reliable", result["review_required_semantics"])
        self.assertEqual(result["frames"][2]["diagnostics"]["disagreement_state"], "candidate_dependent")

    def test_only_new_sidecar_is_written_and_arguments_are_unchanged(self):
        (self.output / "pose_clean.csv").write_bytes(b"keep all coordinates\n")
        (self.output / "analysis.json").write_bytes(b'{"status":"quality_gate_failed"}\n')
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        inputs = deepcopy((self.metadata, self.video, self.capture))
        self._run()
        self.assertEqual(before, {name: (self.output / name).read_bytes() for name in before})
        self.assertEqual((self.metadata, self.video, self.capture), inputs)
        self.assertEqual(set(path.name for path in self.output.iterdir()), set(before) | {"major_review_hints.json"})

    def test_changed_raw_prediction_is_unknown_not_false(self):
        (self.output / "pose_raw.csv").write_bytes(self.raw + b"1,RIGHT_ELBOW,.2,.8,.9\n")
        result = self._run()
        self.assertEqual(result["status"], "not_evaluated")
        self.assertIn("source_mismatch:raw_csv_sha256", result["reason_codes"])
        self.assertTrue(all(frame["review_required"] is None for frame in result["frames"]))
        self.assertIsNone(result["review_required_frames"])

    def test_changed_capture_selection_is_unknown(self):
        self.capture["selection_frames"][1]["selected_index"] = 1
        result = self._run()
        self.assertIn("source_mismatch:capture_semantic_sha256", result["reason_codes"])
        self.assertIsNone(result["frames"][1]["review_required"])

    def test_capture_paths_do_not_affect_semantic_binding(self):
        self.capture.update(video="different/computer/input.mp4", model="different/model.task")
        self.assertEqual(self._run()["status"], "evaluated_development_evidence")

    def test_unknown_clip_does_not_reuse_development_warnings(self):
        self.metadata["pitch_id"] = "new_clip"
        result = self._run()
        self.assertEqual(result["status"], "not_evaluated")
        self.assertIn("input_identity_not_in_development_evidence", result["reason_codes"])
        self.assertEqual([frame["review_required"] for frame in result["frames"]], [None] * 3)

    def test_model_video_or_metadata_changes_prevent_application(self):
        variants = [({"model_sha256": "4" * 64}, "source_mismatch:model_sha256"),
                    ({"video_metadata": {**self.video, "sha256": "5" * 64}}, "source_mismatch:video_sha256")]
        for index, (override, reason) in enumerate(variants):
            with self.subTest(index=index):
                result = self._run(**override)
                self.assertIn(reason, result["reason_codes"])
                self.assertEqual(result["status"], "not_evaluated")
                (self.output / "major_review_hints.json").unlink()
        for field, value in [("camera_view", "side"), ("horizontal_mirror", True),
                             ("playback_speed", .5), ("contains_single_pitch", False)]:
            with self.subTest(field=field):
                metadata = deepcopy(self.metadata)
                metadata["video"][field] = value
                self.assertEqual(self._run(input_metadata=metadata)["status"], "not_evaluated")
                (self.output / "major_review_hints.json").unlink()
        for field, value in [("throws", "RIGHT"), ("id", "another_person")]:
            with self.subTest(field=field):
                metadata = deepcopy(self.metadata)
                metadata["pitcher"][field] = value
                self.assertEqual(self._run(input_metadata=metadata)["status"], "not_evaluated")
                (self.output / "major_review_hints.json").unlink()

    def test_missing_or_corrupted_bundle_cannot_turn_analysis_into_failure(self):
        self.evidence.unlink()
        self.assertEqual(self._run()["status"], "evidence_unavailable")
        (self.output / "major_review_hints.json").unlink()
        self.evidence.write_text('{"altered":true}', encoding="utf-8")
        result = self._run()
        self.assertEqual(result["status"], "evidence_unavailable")
        self.assertTrue(all(frame["review_required"] is None for frame in result["frames"]))

    def test_invalid_component_union_timeline_or_diagnostic_is_unavailable(self):
        modifications = [lambda: self.bundle["clips"][0]["frames"][0].update(review_required=False),
                         lambda: self.bundle["clips"][0]["frames"][1].update(frame_index=0),
                         lambda: self.bundle["clips"][0]["frames"][1].update(timestamp_ms=0),
                         lambda: self.bundle["clips"][0]["frames"][1]["diagnostics"].update(disagreement_state="reliable")]
        for index, modify in enumerate(modifications):
            with self.subTest(index=index):
                self.bundle = fixture()[-1]
                modify()
                self._rebind_bundle()
                self.assertEqual(self._run()["status"], "evidence_unavailable")
                (self.output / "major_review_hints.json").unlink()

    def test_bundle_duplicate_json_key_is_unavailable_even_if_hash_is_bound(self):
        data = self.evidence.read_text(encoding="utf-8").replace('"status": "sealed_development_evidence"',
                                                               '"status": "sealed_development_evidence", "status": "other"')
        self.evidence.write_text(data, encoding="utf-8")
        self.hash_patch.stop()
        self.hash_patch = patch.object(hints, "BUNDLE_SHA256", hashlib.sha256(self.evidence.read_bytes()).hexdigest())
        self.hash_patch.start()
        self.assertEqual(self._run()["status"], "evidence_unavailable")

    def test_incomplete_or_shifted_capture_does_not_apply_cached_warning(self):
        for field, value in [("start_frame", 1), ("processed_frames", 2), ("subject_selection", "none")]:
            with self.subTest(field=field):
                capture = {**self.capture, field: value}
                result = self._run(capture=capture)
                self.assertEqual(result["status"], "not_evaluated")
                self.assertIn("capture_or_video_timeline_mismatch", result["reason_codes"])
                (self.output / "major_review_hints.json").unlink()
        self.video["timestamps_ms"][1] += .01
        self.assertIn("source_mismatch:warning_timeline", self._run()["reason_codes"])

    def test_boolean_is_not_a_frame_index_or_numeric_timestamp(self):
        self.capture["selection_frames"][0]["frame_index"] = False
        self.assertEqual(self._run()["status"], "not_evaluated")

    def test_missing_raw_or_capture_remains_not_evaluated(self):
        (self.output / "pose_raw.csv").unlink()
        result = self._run(capture={})
        self.assertEqual(result["status"], "not_evaluated")
        self.assertIn("raw_prediction_unavailable", result["reason_codes"])
        self.assertIn("capture_signature_unavailable", result["reason_codes"])

    def test_existing_sidecar_is_never_overwritten(self):
        path = self.output / "major_review_hints.json"
        path.write_bytes(b"preserve previous result")
        with self.assertRaises(FileExistsError):
            self._run()
        self.assertEqual(path.read_bytes(), b"preserve previous result")

    def test_source_symlink_outside_output_is_rejected_without_reading_target(self):
        raw_path = self.output / "pose_raw.csv"
        raw_path.unlink()
        target = self.root / "unrelated.csv"
        target.write_bytes(self.raw)
        try:
            raw_path.symlink_to(target)
        except OSError:
            # Keep the boundary test meaningful on Windows without symlink privileges.
            actual_resolve = Path.resolve
            def simulated_resolve(path, *args, **kwargs):
                if path == raw_path:
                    return target
                return actual_resolve(path, *args, **kwargs)
            with patch.object(Path, "resolve", simulated_resolve):
                result = self._run()
        else:
            result = self._run()
        self.assertEqual(result["status"], "not_evaluated")
        self.assertIn("raw_prediction_outside_analysis_directory", result["reason_codes"])
        self.assertEqual(target.read_bytes(), self.raw)

    def test_packaged_actual_bundle_preserves_existing_development_counts(self):
        # This checks the shipped evidence cache only, without GT or model calls.
        patch.stopall()
        bundle = hints._load_bundle()
        scope = bundle["development_scope"]
        self.assertEqual((scope["major_tp"], scope["major_fn"], scope["major_fp"]), (20, 1, 9))
        self.assertEqual((scope["source_frames"], scope["evaluation_non_seed_frames"]), (592, 587))
        self.assertEqual([sum(row["review_required"] for row in clip["frames"][1:]) for clip in bundle["clips"]], [2, 0, 19, 5, 3])
        clip = next(clip for clip in bundle["clips"] if clip["pitch_id"] == "pitch_003")
        self.assertFalse(clip["frames"][104]["review_required"])
        self.assertIn({"pitch_id": "pitch_003", "frame_index": 104}, scope["known_misses"])


if __name__ == "__main__":
    unittest.main()
