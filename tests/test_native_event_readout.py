"""Event readouts describe saved model samples without inventing reliability."""
from copy import deepcopy
import csv
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_motion_events as fixtures

from pitch_analysis.analysis.native_motion_events import describe_events, write_event_comparison
from pitch_analysis.ground_truth import EVENT_NAMES
from pitch_analysis.native_pose_io import read_json, reference


ROLES = ("throwing_elbow", "lead_knee")
LEGACY_FIELDS = ("status", "total_frames", "calculated_frames", "missing_frames",
                 "degenerate_frames", "min_deg", "max_deg", "usable_deg")
CSV_FIELDS = ["pitch_id", "event", "joint", "event_status", "frame_start", "frame_end",
              "total_frames", "calculated_frames", "missing_frames", "degenerate_frames",
              "min_deg", "max_deg", "reading_kind", "sample_span_deg", "sample_span_scope",
              "pointwise_reliability", "usable_for_analysis", "confidence", "note"]


class NativeEventReadoutTests(unittest.TestCase):
    @staticmethod
    def describe(event, values=None):
        events = fixtures.NativeMotionEventMathTests().events()
        events["leg_lift"] = event
        return describe_events(events, Fraction(30), fixtures.rows() if values is None else values)

    def test_exact_and_single_frame_ranges_leave_sensitivity_unassessed(self):
        for event in (fixtures.exact(2), fixtures.ranged(2, 2)):
            with self.subTest(event=event):
                result = self.describe(event)["events"]["leg_lift"]
                for window in result["angle_windows"].values():
                    self.assertEqual(window["reading_kind"], "single_frame")
                    self.assertIsNone(window["sample_span_deg"])
                    self.assertEqual(window["sample_span_scope"], "not_assessable")
                    self.assertEqual((window["min_deg"], window["max_deg"]), (12., 12.))
                    self.assertEqual((window["total_frames"], window["calculated_frames"]), (1, 1))
                    self.assertIsNone(window["usable_deg"])
                self.assertEqual(result["marker_kind"], "exact" if "frame_range" not in event else "range")

    def test_complete_multiple_frames_report_exact_extrema_span(self):
        values = fixtures.rows()
        for frame, angle in ((1, 48.125), (2, 12.5), (3, 73.875)):
            values[frame]["throwing_elbow_model_xy_deg"] = angle
        result = self.describe(fixtures.ranged(1, 3), values)["events"]["leg_lift"]["angle_windows"]
        elbow, knee = result["throwing_elbow"], result["lead_knee"]
        self.assertEqual(elbow["reading_kind"], "multiple_frames")
        self.assertEqual((elbow["min_deg"], elbow["max_deg"], elbow["sample_span_deg"]),
                         (12.5, 73.875, 61.375))
        self.assertEqual(elbow["sample_span_scope"], "complete_window")
        self.assertEqual(knee["sample_span_deg"], 2.)
        self.assertEqual(knee["sample_span_scope"], "complete_window")

    def test_partial_window_span_uses_only_its_two_calculated_samples(self):
        values = fixtures.rows()
        values[1]["throwing_elbow_model_xy_deg"] = 22.5
        values[2].update(throwing_elbow_model_xy_deg=None,
                         throwing_elbow_coordinate_status="missing_coordinates")
        values[3].update(throwing_elbow_model_xy_deg=None,
                         throwing_elbow_coordinate_status="degenerate_geometry")
        values[4]["throwing_elbow_model_xy_deg"] = 67.125
        result = self.describe(fixtures.ranged(1, 4), values)["events"]["leg_lift"]["angle_windows"]
        elbow = result["throwing_elbow"]
        self.assertEqual(elbow["reading_kind"], "multiple_frames")
        self.assertEqual(elbow["sample_span_deg"], 44.625)
        self.assertEqual(elbow["sample_span_scope"], "calculated_samples_only")
        self.assertEqual([elbow[key] for key in ("total_frames", "calculated_frames",
                                               "missing_frames", "degenerate_frames")], [4, 2, 1, 1])
        self.assertEqual(result["lead_knee"]["sample_span_scope"], "complete_window")

    def test_one_or_no_calculated_samples_cannot_supply_a_multi_frame_span(self):
        for calculated in (0, 1):
            with self.subTest(calculated=calculated):
                values = fixtures.rows()
                for frame in range(1 + calculated, 4):
                    values[frame].update(throwing_elbow_model_xy_deg=None,
                                         throwing_elbow_coordinate_status="missing_coordinates")
                window = self.describe(fixtures.ranged(1, 3), values)["events"]["leg_lift"]["angle_windows"]["throwing_elbow"]
                self.assertEqual(window["reading_kind"], "multiple_frames")
                self.assertEqual(window["calculated_frames"], calculated)
                self.assertIsNone(window["sample_span_deg"])
                self.assertEqual(window["sample_span_scope"], "not_assessable")
                self.assertEqual(window["min_deg"], 11. if calculated else None)
                self.assertEqual(window["max_deg"], 11. if calculated else None)

    def test_unobservable_and_uncertain_candidates_never_acquire_angle_readouts(self):
        unresolved = [fixtures.ranged(1, 2, status="uncertain"),
                      {"status": "uncertain", "frame_index": None, "confidence": None},
                      {"status": "not_observable", "frame_index": None, "confidence": None}]
        for event in unresolved:
            with self.subTest(event=event):
                result = self.describe(event)["events"]["leg_lift"]
                self.assertEqual(result["status"], event["status"])
                for window in result["angle_windows"].values():
                    self.assertEqual(window["reading_kind"], "event_unresolved")
                    self.assertIsNone(window["sample_span_deg"])
                    self.assertEqual(window["sample_span_scope"], "not_assessable")
                    self.assertEqual(window["status"], "unavailable")
                    self.assertTrue(all(window[key] is None for key in LEGACY_FIELDS[1:]))
                self.assertIsNone(result["confidence"])

    def test_new_readout_fields_preserve_legacy_values_and_source_labels(self):
        events = fixtures.NativeMotionEventMathTests().events()
        events["leg_lift"] = fixtures.ranged(1, 3)
        values = fixtures.rows()
        values[2].update(throwing_elbow_model_xy_deg=None,
                         throwing_elbow_coordinate_status="missing_coordinates")
        values[3].update(throwing_elbow_model_xy_deg=None,
                         throwing_elbow_coordinate_status="degenerate_geometry")
        before_events, before_values = deepcopy(events), deepcopy(values)
        result = describe_events(events, Fraction(30), values)
        windows = result["events"]["leg_lift"]["angle_windows"]
        expected = {"throwing_elbow": ("descriptive_model_xy_window", 3, 1, 1, 1, 11., 11., None),
                    "lead_knee": ("descriptive_model_xy_window", 3, 3, 0, 0, 11., 13., None)}
        for role, legacy in expected.items():
            self.assertEqual({key: windows[role][key] for key in LEGACY_FIELDS},
                             dict(zip(LEGACY_FIELDS, legacy, strict=True)))
        self.assertEqual(events, before_events)
        self.assertEqual(values, before_values)
        self.assertTrue(all(row["pointwise_reliability"] == "unknown" for row in values))
        result["events"]["leg_lift"]["frame_range"]["start_frame"] = 999
        self.assertEqual(events, before_events)


class NativeEventReadoutExportTests(unittest.TestCase):
    def test_csv_has_one_nullable_readout_per_event_and_joint(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = fixtures.NativeMotionEventExportTests().fixture(Path(temp))
            events = data["truth"]["labels"]["events"]
            events["preparation_start"] = {"status": "not_observable", "frame_index": None,
                                            "confidence": None, "note": "Already moving"}
            events["leg_lift"] = fixtures.ranged(0, 0, status="uncertain", note="Human candidate, not a measured angle")
            events["leg_lift"]["confidence"] = .3
            events["approximate_release"] = fixtures.ranged(1, 2)
            fixtures.NativeMotionEventExportTests.refresh(data)
            result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            path = data["comparison"] / "event_angle_readouts.csv"
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                exported = list(reader)
                self.assertEqual(reader.fieldnames, CSV_FIELDS)
            # Every clip contributes five events times two joints, including unresolved events.
            # The nine-clip request therefore has 90 rows; this small fixture checks that unit.
            self.assertEqual(len(exported), 10)
            self.assertEqual({(row["event"], row["joint"]) for row in exported},
                             {(name, role) for name in EVENT_NAMES for role in ROLES})
            for row in exported:
                self.assertEqual(row["pitch_id"], "pitch_fixture")
                self.assertEqual(row["pointwise_reliability"], "unknown")
                self.assertEqual(row["usable_for_analysis"], "")
                event = result["clips"][0]["events"][row["event"]]
                window = event["angle_windows"][row["joint"]]
                self.assertEqual(row["event_status"], event["status"])
                self.assertEqual(row["reading_kind"], window["reading_kind"])
                self.assertEqual(row["sample_span_scope"], window["sample_span_scope"])
                for field in ("total_frames", "calculated_frames", "missing_frames", "degenerate_frames",
                              "min_deg", "max_deg", "sample_span_deg"):
                    self.assertEqual(row[field], "" if window[field] is None else str(window[field]))
                self.assertEqual(row["note"], event["note"])
                self.assertEqual(row["confidence"], "" if event["confidence"] is None else str(event["confidence"]))
                if row["event"] in {"preparation_start", "leg_lift"}:
                    for field in ("total_frames", "calculated_frames", "missing_frames", "degenerate_frames",
                                  "min_deg", "max_deg", "sample_span_deg"):
                        self.assertEqual(row[field], "")
                elif window["reading_kind"] == "single_frame":
                    self.assertEqual(row["sample_span_deg"], "")
            candidate = next(row for row in exported if row["event"] == "leg_lift")
            self.assertEqual((candidate["frame_start"], candidate["frame_end"]), ("0", "0"))
            invisible = next(row for row in exported if row["event"] == "preparation_start")
            self.assertEqual((invisible["frame_start"], invisible["frame_end"]), ("", ""))
            self.assertEqual(result["artifacts"]["angle_readouts_csv_ref"], reference(data["root"], path))
            self.assertEqual(read_json(data["comparison"] / "event_comparison.json"), result)

    def test_report_and_export_reuse_saved_sources_and_keep_quality_unknown(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = fixtures.NativeMotionEventExportTests().fixture(Path(temp))
            data["truth"]["labels"]["events"]["approximate_release"] = fixtures.ranged(1, 2)
            fixtures.NativeMotionEventExportTests.refresh(data)
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with patch("subprocess.Popen", side_effect=AssertionError("no model process or browser")), \
                 patch("cv2.VideoCapture", side_effect=AssertionError("saved data only")), \
                 patch("pitch_analysis.analysis.native_motion_report.describe_native_motion",
                       side_effect=AssertionError("do not recompute angles")):
                result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            report = (data["comparison"] / "report.md").read_text(encoding="utf-8")
            self.assertIn("事件角度讀值（模型XY）", report)
            self.assertIn("單格", report)
            self.assertIn("敏感度未評估", report)
            self.assertIn("跨度", report)
            self.assertIn("unknown", report)
            self.assertIn("null", report)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertFalse(result["angle_values_recomputed"])
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertEqual(result["new_ground_truth_labels"], 0)
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertEqual(result["quality_status"], "not_calibrated")
            self.assertIsNone(result["usable_for_analysis"])
            for ref in result["artifacts"].values():
                self.assertEqual(reference(data["root"], data["root"] / ref["path"]), ref)


if __name__ == "__main__":
    unittest.main()
