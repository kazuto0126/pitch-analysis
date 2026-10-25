"""A bound event-only checkpoint never promotes incomplete pose ground truth."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_motion_events as helpers

from pitch_analysis.analysis.native_motion_events import write_event_comparison
from pitch_analysis.ground_truth import EVENT_NAMES, validate_ground_truth
from pitch_analysis.native_pose_io import read_json, reference, write_json


class NativeMotionEventScopeTests(unittest.TestCase):
    @staticmethod
    def overwrite(path, payload):
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def fixture(self, root):
        data = helpers.NativeMotionEventExportTests().fixture(root)
        truth = data["truth"]
        truth["annotation_status"] = "in_progress"
        truth["provenance"]["reviewed_at_utc"] = None
        for name in truth["labels"]:
            if name != "events":
                truth["labels"][name] = None
        truth["labels"]["events"]["approximate_release"] = helpers.ranged(1, 2)
        self.overwrite(data["truth_path"], truth)
        validate_ground_truth(truth, source_video_path=data["video"])
        entry = data["request"]["clips"][0]
        entry["ground_truth_ref"] = reference(root, data["truth_path"])
        checkpoint = {
            "schema_version": "manual-event-review-checkpoint-v1",
            "reviewer": truth["provenance"]["reviewer"],
            "recorded_at_utc": "2026-10-25T01:00:00Z",
            "pitch_id": "pitch_fixture", "review_scope": list(EVENT_NAMES),
            "events_complete": True, "full_pose_gt_complete": False,
            "ground_truth_ref": deepcopy(entry["ground_truth_ref"]),
            "source_video_ref": reference(root, data["video"]),
            "non_event_labels_filled": 0,
            "scope_note": "Only the five events are complete; pose labels remain unreviewed.",
        }
        checkpoint_path = root / "event_review_checkpoint.json"
        write_json(checkpoint_path, checkpoint)
        entry["event_review_ref"] = reference(root, checkpoint_path)
        self.overwrite(data["request_path"], data["request"])
        return {**data, "checkpoint": checkpoint, "checkpoint_path": checkpoint_path}

    def refresh_checkpoint(self, data):
        self.overwrite(data["checkpoint_path"], data["checkpoint"])
        data["request"]["clips"][0]["event_review_ref"] = reference(data["root"], data["checkpoint_path"])
        self.overwrite(data["request_path"], data["request"])

    def refresh_truth_and_checkpoint(self, data):
        self.overwrite(data["truth_path"], data["truth"])
        new_ref = reference(data["root"], data["truth_path"])
        data["request"]["clips"][0]["ground_truth_ref"] = new_ref
        data["checkpoint"]["ground_truth_ref"] = deepcopy(new_ref)
        self.refresh_checkpoint(data)

    def assert_rejected(self, data):
        with self.assertRaises((ValueError, OSError)):
            write_event_comparison(data["root"], data["request_path"], data["comparison"])
        self.assertFalse(data["comparison"].exists())

    def test_bound_event_only_checkpoint_accepts_events_without_promoting_gt_or_modifying_sources(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
                 patch("cv2.VideoCapture", side_effect=AssertionError("saved data only")), \
                 patch("pitch_analysis.analysis.native_motion_report.describe_native_motion",
                       side_effect=AssertionError("do not recompute angles")):
                result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            clip = result["clips"][0]
            self.assertEqual(clip["event_review_scope"], {
                "kind": "event_only", "events_complete": True, "full_pose_gt_complete": False,
                "annotation_status": "in_progress", "reviewer": "Human fixture",
                "recorded_at_utc": "2026-10-25T01:00:00Z",
            })
            self.assertEqual(clip["source_refs"]["event_review_ref"],
                             data["request"]["clips"][0]["event_review_ref"])
            self.assertEqual(clip["events"]["approximate_release"]["frame_bounds"], [1, 2])
            self.assertIsNone(clip["events"]["approximate_release"]["frame_index"])
            self.assertEqual(clip["pointwise_reliability"], "unknown")
            self.assertIsNone(clip["usable_for_analysis"])
            self.assertEqual(result["new_ground_truth_labels"], 0)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            gt = read_json(data["truth_path"])
            self.assertEqual(gt["annotation_status"], "in_progress")
            self.assertIsNone(gt["provenance"]["reviewed_at_utc"])
            self.assertTrue(all(value is None for key, value in gt["labels"].items() if key != "events"))

    def test_event_only_scope_preserves_uncertain_unobservable_and_nullable_confidence(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            events = data["truth"]["labels"]["events"]
            events["preparation_start"] = {"status": "not_observable", "frame_index": None,
                                            "confidence": None, "note": "Before clip start"}
            events["leg_lift"] = helpers.ranged(0, 0, status="uncertain")
            self.refresh_truth_and_checkpoint(data)
            result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            clip = result["clips"][0]
            for name, original in events.items():
                for key, value in original.items():
                    self.assertEqual(clip["events"][name][key], value)
                self.assertIsNone(clip["events"][name]["confidence"])
            for metric in ("preparation_to_leg_lift", "leg_lift_to_foot_plant"):
                self.assertEqual(clip["timing"][metric]["status"], "unavailable")
                self.assertIsNone(clip["timing"][metric]["seconds_bounds"])
            self.assertFalse(clip["event_review_scope"]["full_pose_gt_complete"])

    def test_in_progress_gt_without_checkpoint_is_still_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            del data["request"]["clips"][0]["event_review_ref"]
            self.overwrite(data["request_path"], data["request"])
            self.assert_rejected(data)

    def test_legacy_reviewed_gt_still_uses_the_full_ground_truth_path(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = helpers.NativeMotionEventExportTests().fixture(Path(temp))
            before = data["truth_path"].read_bytes()
            result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            clip = result["clips"][0]
            self.assertEqual(clip["event_review_scope"], {
                "kind": "full_ground_truth", "events_complete": True, "full_pose_gt_complete": True,
                "annotation_status": "reviewed", "reviewer": "Human fixture",
                "recorded_at_utc": "2026-10-24T00:00:00Z",
            })
            self.assertNotIn("event_review_ref", clip["source_refs"])
            self.assertEqual(data["truth_path"].read_bytes(), before)

    def test_missing_changed_or_stale_checkpoint_cannot_authorize_gt(self):
        for changed in ("missing", "changed", "stale_gt"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                if changed == "missing":
                    data["request"]["clips"][0]["event_review_ref"]["path"] = "missing_checkpoint.json"
                    self.overwrite(data["request_path"], data["request"])
                elif changed == "changed":
                    with data["checkpoint_path"].open("a", encoding="utf-8") as stream:
                        stream.write("\n")
                else:
                    data["truth"]["labels"]["events"]["foot_plant"]["note"] = "New human revision"
                    self.overwrite(data["truth_path"], data["truth"])
                    data["request"]["clips"][0]["ground_truth_ref"] = reference(data["root"], data["truth_path"])
                    self.overwrite(data["request_path"], data["request"])
                self.assert_rejected(data)

    def test_checkpoint_requires_strict_completion_flags_and_integer_zero_other_labels(self):
        changes = [("schema_version", "another-checkpoint-v1"),
                   ("events_complete", False), ("events_complete", 1), ("events_complete", "true"),
                   ("full_pose_gt_complete", True), ("full_pose_gt_complete", 0),
                   ("non_event_labels_filled", 1), ("non_event_labels_filled", False),
                   ("non_event_labels_filled", 0.0)]
        for key, value in changes:
            with self.subTest(field=key, value=value), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                data["checkpoint"][key] = value
                self.refresh_checkpoint(data)
                self.assert_rejected(data)

    def test_checkpoint_pitch_reviewer_and_exact_five_event_scope_must_match(self):
        changes = [("pitch_id", "different_pitch"), ("reviewer", "Another reviewer"),
                   ("review_scope", list(EVENT_NAMES[:-1])),
                   ("review_scope", [*EVENT_NAMES, EVENT_NAMES[0]]),
                   ("review_scope", [*EVENT_NAMES[:-1], EVENT_NAMES[0]]),
                   ("review_scope", [*EVENT_NAMES[:-1], "not_an_event"])]
        for key, value in changes:
            with self.subTest(field=key, value=value), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                data["checkpoint"][key] = value
                self.refresh_checkpoint(data)
                self.assert_rejected(data)

    def test_checkpoint_requires_a_valid_timezone_aware_completion_time(self):
        for value in (None, "", "not-a-time", "2026-10-25T01:00:00", "2026-02-30T01:00:00Z"):
            with self.subTest(value=value), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                data["checkpoint"]["recorded_at_utc"] = value
                self.refresh_checkpoint(data)
                self.assert_rejected(data)

    def test_checkpoint_exact_gt_and_source_references_cannot_be_swapped_even_with_same_bytes(self):
        for key, source in (("ground_truth_ref", "truth_path"), ("source_video_ref", "video")):
            with self.subTest(reference=key), tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
                data = self.fixture(Path(temp))
                duplicate = data["root"] / ("alias.json" if key == "ground_truth_ref" else "alias.mp4")
                duplicate.write_bytes(data[source].read_bytes())
                data["checkpoint"][key] = reference(data["root"], duplicate)
                self.refresh_checkpoint(data)
                self.assert_rejected(data)

    def test_checkpoint_cannot_claim_complete_when_an_event_is_unfilled(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            data["truth"]["labels"]["events"]["foot_plant"] = None
            self.refresh_truth_and_checkpoint(data)
            self.assert_rejected(data)

    def test_unreviewed_template_cannot_be_promoted_by_a_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = self.fixture(Path(temp))
            data["truth"] = helpers.blank_ground_truth(data["video"], "pitch_fixture", 3)
            self.refresh_truth_and_checkpoint(data)
            self.assert_rejected(data)


if __name__ == "__main__":
    unittest.main()
