"""Terminal evaluation must not turn completed review/tests into certification."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from pitch_analysis.phase2_evaluation import _screening

SPEC = importlib.util.spec_from_file_location("phase2_final_evaluation", Path(__file__).resolve().parents[1] / "scripts/finalize_phase2_evaluation.py")
final = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(final)


def evidence():
    pitches = []
    for i, pid in enumerate(final.PITCH_IDS):
        intervals = [{"start_frame": 1, "end_frame": 2, "status": "confirmed"}] if i == 2 else []
        major = _screening(intervals, set(), 4)
        comparison = {"review_profile": "phase2_full_review", "ground_truth_status": "reviewed",
                      "major_pose_failure_screening": major,
                      "major_pose_failure_with_joint_jump_cues": _screening(intervals, {1}, 4),
                      "identity_switch_warning_agreement": _screening([], set(), 4),
                      "track_break_screening": _screening([], set(), 4),
                      "joint_reliability_agreement": {}}
        pitches.append({"pitch_id": pid, "comparison": comparison})
    suite = {"tests_run": 10, "passed": 10, "failed": 0, "errors": 0, "skipped": 0,
             "formal_five_video_e2e_enabled": True}
    return pitches, suite


class Phase2FinalEvaluationTests(unittest.TestCase):
    def test_known_misses_close_evaluation_without_automatic_pass(self):
        pitches, suite = evidence()
        before = deepcopy((pitches, suite))
        result = final.terminal_verdict(pitches, suite)
        self.assertEqual(result["evaluation_status"], "COMPLETE")
        self.assertEqual(result["automatic_reliability"], "NOT PASSED")
        self.assertFalse(result["accepted"])
        self.assertEqual(result["test_gate"], "PASSED")
        self.assertEqual(result["known_major_failure_misses"], [{"pitch_id": "pitch_003", "missed_confirmed_major_failure_frames": 2,
                                                             "ranges": [{"start_frame": 1, "end_frame": 2}]}])
        self.assertEqual((pitches, suite), before)

    def test_jump_union_and_complete_tests_cannot_certify_original_detector(self):
        pitches, suite = evidence()
        pitches[2]["comparison"]["major_pose_failure_with_joint_jump_cues"] = _screening(
            [{"start_frame": 1, "end_frame": 2}], {1, 2}, 4)
        result = final.terminal_verdict(pitches, suite)
        self.assertEqual(result["aggregate"]["screening"]["major_pose_failure_with_joint_jump_cues"]["recall_on_confirmed_frames"], 1.)
        self.assertEqual(result["automatic_reliability"], "NOT PASSED")

    def test_no_miss_in_diagnostic_sample_does_not_invent_pass_rule(self):
        pitches, suite = evidence()
        pitches[2]["comparison"]["major_pose_failure_screening"] = _screening(
            [{"start_frame": 1, "end_frame": 2}], {1, 2}, 4)
        result = final.terminal_verdict(pitches, suite)
        self.assertEqual(result["automatic_reliability"], "NOT ESTABLISHED")
        self.assertFalse(result["accepted"])

    def test_zero_switch_positives_never_become_perfect_sensitivity(self):
        result = final.terminal_verdict(*evidence())
        self.assertIsNone(result["aggregate"]["screening"]["identity_switch_warning_agreement"]["recall_on_confirmed_frames"])

    def test_suite_failure_does_not_change_review_completion_or_vanish(self):
        pitches, suite = evidence()
        suite.update(passed=9, failed=1)
        result = final.terminal_verdict(pitches, suite)
        self.assertEqual(result["test_gate"], "NOT PASSED")
        self.assertEqual(result["tests"]["failed"], 1)
        self.assertEqual(result["evaluation_status"], "COMPLETE")
        self.assertFalse(result["accepted"])

    def test_missing_or_unreviewed_clip_prevents_terminal_complete(self):
        pitches, suite = evidence()
        for broken in (pitches[:-1], [pitches[0], pitches[0], *pitches[2:]]):
            with self.assertRaisesRegex(ValueError, "five formal"):
                final.terminal_verdict(broken, suite)
        pitches[0]["comparison"]["ground_truth_status"] = "in_progress"
        with self.assertRaisesRegex(ValueError, "canonical"):
            final.terminal_verdict(pitches, suite)

    def test_suite_count_provenance_is_required(self):
        pitches, suite = evidence()
        for field, value in (("passed", True), ("skipped", -1), ("tests_run", 11), ("formal_five_video_e2e_enabled", False)):
            bad = {**suite, field: value}
            with self.assertRaises(ValueError):
                final.terminal_verdict(pitches, bad)

    def test_inventory_checks_original_files_not_only_receipt_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "raw.bin"
            data.write_bytes(b"original")
            inventory = root / "inventory.json"
            inventory.write_text(json.dumps({"protected_sha256": {"raw.bin": final.review.sha256(data)}}))
            record = {"path": "inventory.json", "sha256": final.review.sha256(inventory), "key": "protected_sha256"}
            final.verify_inventory(root, record)
            data.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "binding changed"):
                final.verify_inventory(root, record)

    def test_new_output_cannot_overwrite_or_escape_analysis_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "analysis_results" / "old"
            existing.mkdir(parents=True)
            for bad in (existing, root / "input" / "new"):
                with self.assertRaisesRegex(ValueError, "new workspace"):
                    final.run(root, root / "no-plan.json", bad)

    def test_stop_gate_remains_explicit_and_new_work_is_not_authorized(self):
        result = final.terminal_verdict(*evidence())
        self.assertEqual(result["stop_before"], ["Phase 3", "shared delivery folder integration"])
        self.assertTrue(result["future_work_requires_new_instruction"])

    def test_inventory_duplicates_are_not_multiple_physical_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            entries = {"raw.bin": "a", str(root / "raw.bin"): "a", "child/../raw.bin": "a", "other.bin": "b"}
            self.assertEqual(final.physical_file_count(root, entries), 2)


if __name__ == "__main__":
    unittest.main()
