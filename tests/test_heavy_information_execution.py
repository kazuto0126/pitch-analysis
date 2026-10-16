"""Synthetic stage-isolation tests; no real video, GT or model is opened."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_heavy_information as execution


class HeavyExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.output = self.root / "analysis_results" / "synthetic_heavy"
        self.measurements = self.output / "measurements"
        self.measurements.mkdir(parents=True)
        self.gt_folder = self.root / "synthetic_annotations"
        self.gt_folder.mkdir()
        self.plan = {"_sha256": "f" * 64, "clips": [],
                     "heavy_model": {"path": "unused_heavy.task", "sha256": "b" * 64}}
        self.gt_paths = {}
        measured_refs = []
        for pitch_id in execution.NAMES:
            gt_path = self.gt_folder / (pitch_id + ".json")
            gt = {"schema_version": "ground-truth-v1", "annotation_status": "reviewed",
                  "source_video": {"pitch_id": pitch_id, "total_frames": 4, "sha256": "a" * 64},
                  "labels": {role + "_reliability": [
                      {"start_frame": 0, "end_frame": 2, "status": "reliable"},
                      {"start_frame": 3, "end_frame": 3, "status": "unreliable"},
                  ] for role in execution.ROLES}}
            execution.save(gt_path, gt)
            self.gt_paths[pitch_id] = gt_path
            self.plan["clips"].append({"pitch_id": pitch_id, "total_frames": 4,
                "canonical_gt": execution.reference(self.root, gt_path),
                "measurement_sources": {"video": {"path": "unused_" + pitch_id + ".mp4",
                                                     "sha256": "a" * 64}}})
            distances = [99., .1, .2, .4]
            if pitch_id == "pitch_003":
                distances = [99., .2, .200001, None]
            item = {"status": "sealed_heavy_measurement", "plan_sha256": self.plan["_sha256"],
                    "pitch_id": pitch_id, "total_frames": 4,
                    "frames": [{"frame_index": index, "roles": {
                        role: {"distance_diagonal": distance} for role in execution.ROLES}}
                        for index, distance in enumerate(distances)]}
            path = self.measurements / (pitch_id + ".json")
            execution.save(path, item)
            measured_refs.append(execution.reference(self.root, path))
        execution.save(self.measurements / "measurement_run.json", {
            "status": "sealed_all_heavy_measurements", "plan_sha256": self.plan["_sha256"],
            "clips": measured_refs, "human_annotation_inputs": []})

    def test_reader_rejects_unlisted_changed_and_external_sources(self):
        path = self.root / "test_input.json"
        execution.save(path, {"synthetic": True})
        ref = execution.reference(self.root, path)
        with self.assertRaisesRegex(ValueError, "not allowed"):
            execution.Reader(self.root, []).json(ref)
        reader = execution.Reader(self.root, [ref])
        path.write_text('{"synthetic": false}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Changed or external"):
            reader.json(ref)
        outside = self.root.parent / "external.json"
        execution.save(outside, {"synthetic": "outside"})
        external_ref = {"path": "../external.json", "sha256": execution.sha(outside)}
        with self.assertRaisesRegex(ValueError, "Changed or external"):
            execution.Reader(self.root, [external_ref]).json(external_ref)
        self.assertEqual(reader.opened, [])

    def test_calibration_reads_exact_four_training_gt_not_missing_query_gt(self):
        query = "pitch_003"
        self.gt_paths[query].unlink()
        saved = execution.calibrate_stage(self.root, self.plan, self.output, query)
        gt_reads = [path for path in saved["read_paths"] if path.startswith("synthetic_annotations/")]
        self.assertEqual(sorted(gt_reads), sorted(
            "synthetic_annotations/" + pitch_id + ".json"
            for pitch_id in execution.NAMES if pitch_id != query))
        self.assertEqual(len(saved["read_paths"]), 8)
        self.assertFalse(any(query in path for path in saved["read_paths"]))
        for role in execution.ROLES:
            self.assertEqual(saved["roles"][role]["threshold_diagonal"], .2)
            self.assertEqual(saved["roles"][role]["status"], "calibrated")
            self.assertEqual(saved["roles"][role]["used_reliable_rows"], 8)

    def test_completed_calibration_repeat_never_recalibrates_or_reads_gt(self):
        query = "pitch_003"
        first = execution.calibrate_stage(self.root, self.plan, self.output, query)
        path = self.output / "folds" / query / "calibration.json"
        saved_sha = execution.sha(path)
        for gt_path in self.gt_paths.values():
            gt_path.unlink()
        with patch.object(execution.policy, "calibrate", side_effect=AssertionError("refit forbidden")):
            again = execution.calibrate_stage(self.root, self.plan, self.output, query)
        self.assertEqual(again, first)
        self.assertEqual(execution.sha(path), saved_sha)

    def test_apply_only_numeric_query_measurement_without_gt_or_recalibration(self):
        query = "pitch_003"
        execution.calibrate_stage(self.root, self.plan, self.output, query)
        for gt_path in self.gt_paths.values():
            gt_path.unlink()
        with patch.object(execution.policy, "calibrate", side_effect=AssertionError("calibration forbidden")):
            result = execution.apply_stage(self.root, self.plan, self.output, query)
        self.assertEqual(result["warnings"], {role: 1 for role in execution.ROLES})
        saved = execution.read(self.output / "predictions" / (query + ".json"))
        self.assertFalse(saved["reads_annotations"])
        self.assertEqual(saved["read_paths"], [
            "analysis_results/synthetic_heavy/measurements/pitch_003.json",
            "analysis_results/synthetic_heavy/folds/pitch_003/calibration.json"])
        for role in execution.ROLES:
            rows = [frame["roles"][role] for frame in saved["frames"]]
            self.assertEqual([row["status"] for row in rows], [
                "seed_excluded", "no_warning", "warning", "insufficient_evidence"])
            self.assertEqual([row["evaluated_warning"] for row in rows], [False, False, True, False])
            self.assertFalse(rows[0]["effectiveness_eligible"])
            self.assertTrue(rows[3]["effectiveness_eligible"])
            self.assertIsNone(rows[3]["review_required"])
        execution.apply_stage(self.root, self.plan, self.output, query)
        self.assertEqual(execution.read(self.output / "predictions" / (query + ".json")), saved)

    def test_unfinished_calibration_attempt_refuses_automatic_retry(self):
        query = "pitch_003"
        folder = self.output / "folds" / query
        folder.mkdir(parents=True)
        execution.save(folder / "calibration_attempt.json", {"synthetic": "interrupted"})
        with patch.object(execution.policy, "calibrate", side_effect=AssertionError("retry forbidden")):
            with self.assertRaisesRegex(ValueError, "automatic retry refused"):
                execution.calibrate_stage(self.root, self.plan, self.output, query)

    def test_measurement_journal_without_artifact_refuses_new_inference(self):
        query = "pitch_003"
        (self.measurements / (query + ".json")).unlink()
        journal = self.measurements / (query + "_attempts.jsonl")
        journal.write_text('{"event":"started","frame_index":0}\n', encoding="utf-8")
        factory = Mock(side_effect=AssertionError("inference forbidden"))
        with self.assertRaisesRegex(ValueError, "automatic remeasurement refused"):
            execution.measure_clip(self.root, self.plan, self.output, query, factory)
        factory.assert_not_called()

    def test_completed_measurement_skips_only_matching_plan_and_journal(self):
        query = "pitch_003"
        target = self.measurements / (query + ".json")
        item = execution.read(target)
        journal = self.measurements / (query + "_attempts.jsonl")
        journal.write_text('{"event":"completed","frame_index":3}\n', encoding="utf-8")
        item["journal_sha256"] = execution.sha(journal)
        target.unlink(); execution.save(target, item)
        factory = Mock(side_effect=AssertionError("inference forbidden"))
        result = execution.measure_clip(self.root, self.plan, self.output, query, factory)
        self.assertEqual(result, {"status": "skipped_completed_measurement",
                                  "pitch_id": query, "new_inference_calls": 0})
        factory.assert_not_called()
        journal.write_text('{"event":"changed"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Persisted Heavy clip differs"):
            execution.measure_clip(self.root, self.plan, self.output, query, factory)

    def test_measured_roles_keeps_low_heavy_scores_and_original_gate(self):
        point = {"x": .2, "y": .3, "visibility": .9, "presence": .95}
        original = {name: deepcopy(point) for name in execution.JOINTS.values()}
        candidate = [dict(point) for _ in execution.LANDMARK_NAMES]
        for index, name in enumerate(execution.LANDMARK_NAMES):
            if name in execution.JOINTS.values():
                candidate[index].update(x=.5, visibility=.001, presence=.001)
        result = execution.measured_roles(original, [candidate], {"status": "selected", "index": 0},
                                           300, 400, {"min_visibility": .5, "min_presence": .5})
        for role in execution.ROLES:
            self.assertAlmostEqual(result[role]["distance_px"], 90.)
            self.assertAlmostEqual(result[role]["distance_diagonal"], .18)
            self.assertEqual(result[role]["evidence_status"], "measured")
            self.assertTrue(result[role]["raw_gate_pass"])

    def test_nonfinite_or_unselected_measurement_is_null_not_success(self):
        point = {"x": .2, "y": .3, "visibility": .9, "presence": .95}
        original = {name: deepcopy(point) for name in execution.JOINTS.values()}
        candidate = [dict(point) for _ in execution.LANDMARK_NAMES]
        for index, name in enumerate(execution.LANDMARK_NAMES):
            if name in execution.JOINTS.values():
                candidate[index]["x"] = None
        for choices, candidates in (({"status": "selected", "index": 0}, [candidate]),
                                     ({"status": "ambiguous", "index": None}, []),
                                     ({"status": "rejected", "index": None}, [])):
            result = execution.measured_roles(original, candidates, choices, 300, 400,
                                               {"min_visibility": .5, "min_presence": .5})
            for role in execution.ROLES:
                self.assertIsNone(result[role]["distance_diagonal"])
                self.assertIsNone(result[role]["distance_px"])
                self.assertEqual(result[role]["evidence_status"], "insufficient_evidence")
        original["RIGHT_ELBOW"]["visibility"] = float("nan")
        finite_candidate = [dict(point) for _ in execution.LANDMARK_NAMES]
        result = execution.measured_roles(original, [finite_candidate], {"status": "selected", "index": 0},
                                           300, 400, {"min_visibility": .5, "min_presence": .5})
        self.assertFalse(result["throwing_elbow"]["raw_finite"])
        self.assertIsNone(result["throwing_elbow"]["distance_diagonal"])
        self.assertEqual(result["throwing_wrist"]["distance_diagonal"], 0.)


if __name__ == "__main__":
    unittest.main()
