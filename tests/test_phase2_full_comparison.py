import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

import test_ground_truth
from pitch_analysis.ground_truth import FULL_JOINT_LABELS
from pitch_analysis.phase2_evaluation import evaluate_against_ground_truth


spec = importlib.util.spec_from_file_location(
    "evaluate_phase2_ground_truth", Path(__file__).resolve().parents[1] / "scripts/evaluate_phase2_ground_truth.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def interval(start, end, status):
    return {"start_frame": start, "end_frame": end, "status": status,
            "reason": "Synthetic human judgment", "confidence": None}


class FullComparisonTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_ground_truth.GroundTruthTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.gt = self.fixture._reviewed()
        self.gt["review_profile"] = "phase2_full_review"
        labels = self.gt["labels"]
        labels.update({"track_break_intervals": [], "throwing_arm_occlusion_intervals": [],
                       "major_pose_failure_intervals": [],
                       "pitcher_selection_review": {"status": "annotated", "confidence": None, "note": "Synthetic review"}})
        for name in FULL_JOINT_LABELS:
            labels[name] = [interval(0, 9, "reliable")]
        roles = {"throwing_shoulder": "RIGHT_SHOULDER", "throwing_elbow": "RIGHT_ELBOW",
                 "throwing_wrist": "RIGHT_WRIST", "lead_hip": "LEFT_HIP",
                 "lead_knee": "LEFT_KNEE", "lead_ankle": "LEFT_ANKLE"}
        self.pose = {"pitch_id": "pitch_001", "pitcher_id": "test_pitcher", "total_frames": 10,
                     "frame_indices": list(range(10)), "important_joints": roles,
                     "joints": {landmark: {"frame_states": ["observed"] * 10,
                                            "status": "reliable", "reasons": ["Synthetic model flag"],
                                            "frame_to_frame_jump": {"candidate_frames": []}}
                                for landmark in roles.values()}}
        self.tracking = {"pitch_id": "pitch_001", "pitcher_id": "test_pitcher", "total_frames": 10,
                         "status": "reliable", "reasons": [], "warning_events": [], "track_breaks": [],
                         "frames": [{"frame_index": i, "selection_status": "selected", "warnings": []}
                                    for i in range(10)]}

    def evaluate(self):
        return evaluate_against_ground_truth(self.gt, self.pose, self.tracking)

    def test_all_six_joints_keep_unknowns_out_of_endpoint_scores_and_preserve_inputs(self):
        for name in FULL_JOINT_LABELS:
            self.gt["labels"][name] = [interval(0, 1, "reliable"), interval(2, 3, "unreliable"),
                                       interval(4, 5, "uncertain"), interval(6, 7, "not_observable"),
                                       interval(8, 9, "reliable")]
        for joint in self.pose["joints"].values():
            joint["frame_states"] = ["observed", "interpolated", "observed", "missing", "observed",
                                     "missing", "observed", "interpolated", "observed", "missing"]
            joint["frame_to_frame_jump"]["candidate_frames"] = [2, 4, 6, 8]
        before = copy.deepcopy((self.gt, self.pose, self.tracking))
        result = self.evaluate()
        self.assertEqual((self.gt, self.pose, self.tracking), before)
        self.assertEqual(len(result["joint_reliability_agreement"]), 6)
        for row in result["joint_reliability_agreement"].values():
            self.assertEqual(row["observed_but_human_unreliable_frames"], 1)
            self.assertEqual(row["observed_but_human_not_observable_frames"], 1)
            self.assertEqual(row["human_reliable_but_model_unobserved_frames"], 2)
            self.assertEqual(row["human_label_by_model_state"]["not_observable"],
                             {"observed": 1, "interpolated": 1, "missing": 0})
            screen = row["joint_jump_endpoint_screening"]
            self.assertEqual([screen[k] for k in ("true_positive_frames", "false_negative_frames",
                              "false_positive_frames", "true_negative_frames", "screened_excluded_frames")],
                             [1, 1, 1, 3, 2])
            self.assertEqual(screen["recall_on_confirmed_frames"], .5)
            self.assertEqual(screen["precision_on_scorable_frames"], .5)
            self.assertEqual(screen["ranges"]["false_negative"], [{"start_frame": 3, "end_frame": 3}])

    def test_tracking_uncertainty_is_excluded_and_boundary_hits_do_not_fill_intervals(self):
        self.gt["labels"]["identity_switch_intervals"] = [interval(1, 2, "confirmed"),
            interval(3, 3, "uncertain"), interval(4, 4, "not_observable")]
        for i in (1, 3, 4, 5):
            self.tracking["frames"][i]["warnings"] = ["body_center_jump"]
            self.tracking["warning_events"].append({"frame_index": i, "type": "body_center_jump"})
        row = self.evaluate()["identity_switch_warning_agreement"]
        self.assertEqual(row["true_positive_frames"], 1)
        self.assertEqual(row["false_negative_frames"], 1)
        self.assertEqual(row["false_positive_frames"], 1)
        self.assertEqual(row["screened_excluded_frames"], 2)
        self.assertEqual(row["confirmed_intervals_with_any_screen"], 1)
        self.assertEqual(row["human_intervals"][0]["screened_ranges"], [{"start_frame": 1, "end_frame": 1}])

    def test_break_screen_and_secondary_joint_cues_remain_distinct(self):
        self.gt["labels"]["major_pose_failure_intervals"] = [interval(5, 7, "confirmed")]
        self.gt["labels"]["track_break_intervals"] = [interval(7, 7, "confirmed"), interval(8, 8, "uncertain")]
        for i in (7, 8):
            self.tracking["frames"][i]["selection_status"] = "rejected"
        self.tracking["track_breaks"] = [{"start_frame": 7, "end_frame": 8}]
        self.pose["joints"]["RIGHT_ELBOW"]["frame_to_frame_jump"]["candidate_frames"] = [5]
        result = self.evaluate()
        self.assertEqual(result["track_break_screening"]["true_positive_frames"], 1)
        self.assertEqual(result["track_break_screening"]["screened_excluded_frames"], 1)
        self.assertEqual(result["major_pose_failure_screening"]["true_positive_frames"], 1)
        self.assertEqual(result["major_pose_failure_with_joint_jump_cues"]["true_positive_frames"], 2)
        self.assertEqual(result["major_pose_failure_with_joint_jump_cues"]["false_negative_frames"], 1)

    def test_human_ranges_subject_uncertainty_and_notes_survive_without_scores(self):
        labels = self.gt["labels"]
        labels["pitcher_correctly_selected"] = None
        labels["pitcher_selection_review"] = {"status": "uncertain", "confidence": None, "note": "Synthetic overlap"}
        labels["events"]["preparation_start"] = {"status": "uncertain", "frame_index": None,
            "frame_range": {"start_frame": 0, "end_frame": 1}, "confidence": None, "note": "Onset ambiguous"}
        labels["events"]["approximate_release"] = {"status": "annotated", "frame_index": None,
            "frame_range": {"start_frame": 5, "end_frame": 7}, "confidence": .7, "note": "Between images"}
        labels["events"]["follow_through_end"] = {"status": "not_observable", "frame_index": None, "note": "Outside clip"}
        labels["throwing_arm_occlusion_intervals"] = [interval(3, 4, "not_observable")]
        result = self.evaluate()
        self.assertEqual(result["human_events"], labels["events"])
        self.assertIsNone(result["correct_pitcher"])
        self.assertIsNone(result["event_accuracy"])
        self.assertIsNone(result["keypoint_coordinate_accuracy"])
        self.assertEqual(result["human_arm_occlusion"]["frame_counts_by_status"]["confirmed"], 0)
        self.assertEqual(result["human_arm_occlusion"]["frame_counts_by_status"]["not_observable"], 2)

    def test_no_positive_switches_does_not_produce_perfect_sensitivity(self):
        screen = self.evaluate()["identity_switch_warning_agreement"]
        self.assertIsNone(screen["recall_on_confirmed_frames"])
        self.assertIsNone(screen["precision_on_scorable_frames"])
        self.assertEqual(screen["true_negative_frames"], 10)

    def test_bad_prediction_alignment_and_states_are_rejected(self):
        edits = [lambda p, t: p.update(pitch_id="other"),
                 lambda p, t: t.update(pitcher_id="different_pitcher"),
                 lambda p, t: p.update(frame_indices=list(reversed(range(10)))),
                 lambda p, t: p["joints"]["RIGHT_ELBOW"].update(frame_states=["observed"] * 9),
                 lambda p, t: p["joints"]["RIGHT_ELBOW"].update(frame_states=["made_up"] * 10),
                 lambda p, t: p["joints"]["RIGHT_ELBOW"]["frame_to_frame_jump"].update(candidate_frames=[10]),
                 lambda p, t: t["frames"].reverse(),
                 lambda p, t: t.update(track_breaks=[{"start_frame": 3, "end_frame": 3}]),
                 lambda p, t: t.update(warning_events=[{"frame_index": 3, "type": "body_center_jump"}])]
        for edit in edits:
            with self.subTest(edit=edit):
                pose, tracking = copy.deepcopy((self.pose, self.tracking))
                edit(pose, tracking)
                with self.assertRaises(ValueError):
                    evaluate_against_ground_truth(self.gt, pose, tracking)

    def test_partial_review_is_unmeasured_even_if_predictions_exist(self):
        self.gt["annotation_status"] = "in_progress"
        result = self.evaluate()
        self.assertEqual(result["status"], "pending_human_ground_truth")
        self.assertIsNone(result["joint_reliability_agreement"])


class ComparisonRunnerTests(unittest.TestCase):
    # Reuse the synthetic fixture while keeping these checks separate from video inference.
    def setUp(self):
        FullComparisonTests.setUp(self)

    def prepare(self):
        root = self.fixture.root
        baseline = root / "baseline"
        analysis = baseline / "predictions/test_pitcher/pitch_001"
        analysis.mkdir(parents=True)

        def write(path, payload):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

        self.write = write
        sha = self.gt["source_video"]["sha256"]
        write(baseline / "evaluation_summary.json", {"pitch_count": 1, "pitcher_id": "test_pitcher", "pitches": [
            {"pitch_id": "pitch_001", "video_sha256": sha, "total_frames": 10}]})
        write(baseline / "ground_truth/pitch_001/ground_truth.json", self.gt)
        (analysis / "pose_clean.csv").write_bytes(b"synthetic clean source")
        self.pose["source_artifacts"] = {"pose_clean_sha256": hashlib.sha256(b"synthetic clean source").hexdigest()}
        write(baseline / "reliability/pitch_001/pose_reliability.json", self.pose)
        write(baseline / "reliability/pitch_001/tracking_reliability.json", self.tracking)
        write(analysis / "video_metadata.json", {"status": "validated", "sha256": sha,
              "frame_count": 10, "timestamps_ms": [i * 1000 / 30 for i in range(10)]})
        write(analysis / "input_manifest.json", {"pitch_id": "pitch_001", "video": {"file": "pitch_001.mp4"},
              "pitcher": {"id": "test_pitcher", "throws": "RIGHT"}})
        write(analysis / "keypoints.json", {"pitch_id": "pitch_001", "pitcher_id": "test_pitcher", "frames": [
            {"frame_index": i, "timestamp_ms": i * 1000 / 30} for i in range(10)]})
        write(analysis / "pose_raw.capture.json", {"requested_frames": 10, "processed_frames": 10,
              "start_frame": 0, "end_frame": 9, "selection_frames": [
            {"frame_index": i, "timestamp_ms": i * 1000 / 30, "status": "selected"} for i in range(10)]})
        return root, baseline, analysis

    def test_source_bound_report_preserves_inputs_and_refuses_overwrite(self):
        root, baseline, _ = self.prepare()
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        out = root / "comparison.json"
        result = runner.evaluate_baseline(root, baseline, out)
        self.assertEqual(result["reviewed_count"], 1)
        self.assertTrue(result["input_artifacts_unchanged"])
        self.assertEqual(result["aggregate"]["screening"]["identity_switch_warning_agreement"]["true_negative_frames"], 10)
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))
        original_output = out.read_bytes()
        with self.assertRaises(FileExistsError):
            runner.evaluate_baseline(root, baseline, out)
        self.assertEqual(out.read_bytes(), original_output)

    def test_mismatched_hash_roles_clean_artifact_and_timestamps_fail_before_output(self):
        root, baseline, analysis = self.prepare()
        changes = [
            (analysis / "video_metadata.json", lambda d: d.update(sha256="0" * 64)),
            (analysis / "input_manifest.json", lambda d: d["pitcher"].update(throws="LEFT")),
            (baseline / "reliability/pitch_001/pose_reliability.json",
             lambda d: d["source_artifacts"].update(pose_clean_sha256="0" * 64)),
            (analysis / "keypoints.json", lambda d: d["frames"][0].update(timestamp_ms=33)),
            (analysis / "pose_raw.capture.json", lambda d: d["selection_frames"][0].update(status="rejected")),
            (analysis / "pose_raw.capture.json", lambda d: d["selection_frames"][1].update(timestamp_ms=0)),
            (analysis / "pose_raw.capture.json", lambda d: d.update(processed_frames=9)),
        ]
        for path, edit in changes:
            original = path.read_text(encoding="utf-8")
            payload = json.loads(original)
            edit(payload)
            self.write(path, payload)
            with self.assertRaises(ValueError):
                runner.evaluate_baseline(root, baseline, root / "invalid.json")
            self.assertFalse((root / "invalid.json").exists())
            path.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
