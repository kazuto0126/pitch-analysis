"""Stage transitions retain all chronological endpoint pairs and unknown quality."""
from copy import deepcopy
import csv
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_motion_events as fixtures

from pitch_analysis.analysis.native_motion_events import describe_events, write_event_comparison
from pitch_analysis.analysis.native_motion_transition import describe_event_transition
from pitch_analysis.native_pose_io import read_json, reference


ROLES = ("throwing_elbow", "lead_knee")
PAIR_COUNTS = ("total_pairs", "calculated_pairs", "unavailable_pairs",
               "missing_endpoint_pairs", "degenerate_endpoint_pairs")


def clip(start=None, end=None, *, values=None, fps=Fraction(60000, 1001)):
    values = fixtures.rows() if values is None else values
    events = {"preparation_start": fixtures.exact(0), "leg_lift": fixtures.exact(0),
              "foot_plant": fixtures.ranged(1, 2) if start is None else start,
              "approximate_release": fixtures.ranged(4, 5) if end is None else end,
              "follow_through_end": fixtures.exact(len(values) - 1)}
    return {"pitch_id": "pitch_fixture", "fps_fraction": str(fps), "rows": values,
            **describe_events(events, fps, values)}


def set_angle(values, frame, angle, *, role="throwing_elbow", status="calculated_from_model_xy"):
    values[frame][f"{role}_model_xy_deg"] = angle
    values[frame][f"{role}_coordinate_status"] = status


class NativeMotionTransitionTests(unittest.TestCase):
    def test_delta_is_end_minus_start_not_the_intervening_curve_amplitude(self):
        values = fixtures.rows()
        set_angle(values, 1, 70.)
        set_angle(values, 3, 179.)
        set_angle(values, 5, 40.)
        set_angle(values, 1, 100., role="lead_knee")
        set_angle(values, 5, 140., role="lead_knee")
        result = describe_event_transition(clip(fixtures.exact(1), fixtures.exact(5), values=values))
        self.assertEqual((result["start_event"], result["end_event"]),
                         ("foot_plant", "approximate_release"))
        self.assertEqual(result["status"], "descriptive_model_xy_transition")
        elbow, knee = result["joints"]["throwing_elbow"], result["joints"]["lead_knee"]
        self.assertEqual((elbow["min_delta_deg"], elbow["max_delta_deg"], elbow["delta_direction"]),
                         (-30., -30., "negative"))
        self.assertEqual((knee["min_delta_deg"], knee["max_delta_deg"], knee["delta_direction"]),
                         (40., 40., "positive"))
        pair = elbow["pairs"][0]
        self.assertEqual((pair["start_model_xy_deg"], pair["end_model_xy_deg"],
                          pair["delta_model_xy_deg"]), (70., 40., -30.))
        self.assertEqual(pair["status"], "calculated_from_model_xy")
        self.assertEqual((pair["start_coordinate_status"], pair["end_coordinate_status"]),
                         ("calculated_from_model_xy", "calculated_from_model_xy"))

    def test_all_endpoint_combinations_are_retained_without_midpoint_or_deduplication(self):
        values = fixtures.rows()
        for frame, angle in ((1, 10.), (2, 50.), (4, 20.), (5, 60.), (6, 30.)):
            set_angle(values, frame, angle)
        result = describe_event_transition(clip(fixtures.ranged(1, 2), fixtures.ranged(4, 6), values=values))
        self.assertEqual((result["all_endpoint_pairs"], result["chronological_pairs"],
                          result["excluded_nonchronological_pairs"]), (6, 6, 0))
        elbow = result["joints"]["throwing_elbow"]
        self.assertEqual({(pair["start_frame"], pair["end_frame"]) for pair in elbow["pairs"]},
                         {(1, 4), (1, 5), (1, 6), (2, 4), (2, 5), (2, 6)})
        self.assertEqual(sorted(pair["delta_model_xy_deg"] for pair in elbow["pairs"]),
                         [-30., -20., 10., 10., 20., 50.])
        self.assertEqual([elbow[key] for key in PAIR_COUNTS], [6, 6, 0, 0, 0])
        self.assertEqual((elbow["min_delta_deg"], elbow["max_delta_deg"], elbow["delta_direction"]),
                         (-30., 50., "includes_zero"))

    def test_overlapping_events_exclude_reverse_pairs_but_keep_equal_frame_pairs(self):
        values = fixtures.rows()
        for frame, angle in ((3, 20.), (4, 10.), (5, 170.), (6, 100.)):
            set_angle(values, frame, angle)
        result = describe_event_transition(clip(fixtures.ranged(3, 5), fixtures.ranged(4, 6), values=values))
        self.assertEqual((result["all_endpoint_pairs"], result["chronological_pairs"],
                          result["excluded_nonchronological_pairs"]), (9, 8, 1))
        elbow = result["joints"]["throwing_elbow"]
        pairs = {(pair["start_frame"], pair["end_frame"]): pair for pair in elbow["pairs"]}
        self.assertEqual(set(pairs), {(3, 4), (3, 5), (3, 6), (4, 4), (4, 5), (4, 6), (5, 5), (5, 6)})
        self.assertEqual((elbow["min_delta_deg"], elbow["max_delta_deg"]), (-70., 160.))
        self.assertEqual(elbow["total_pairs"], 8)
        for endpoint in ((4, 4), (5, 5)):
            self.assertEqual(pairs[endpoint]["elapsed_frames"], 0)
            self.assertEqual(pairs[endpoint]["elapsed_seconds"], 0.)
            self.assertEqual(pairs[endpoint]["elapsed_seconds_fraction"], "0")
            self.assertEqual(pairs[endpoint]["delta_model_xy_deg"], 0.)

    def test_pair_time_uses_exact_fractional_fps(self):
        source = clip(fixtures.exact(1), fixtures.exact(4), fps=Fraction(60000, 1001))
        result = describe_event_transition(source)
        for joint in result["joints"].values():
            pair = joint["pairs"][0]
            self.assertEqual((pair["start_frame"], pair["end_frame"], pair["elapsed_frames"]), (1, 4, 3))
            self.assertEqual(pair["elapsed_seconds_fraction"], "1001/20000")
            self.assertEqual(pair["elapsed_seconds"], float(Fraction(1001, 20000)))
        self.assertEqual(result["timing"], source["timing"]["foot_plant_to_release"])

    def test_missing_and_degenerate_counts_overlap_while_unavailable_counts_the_union(self):
        values = fixtures.rows()
        set_angle(values, 1, None, status="missing_coordinates")
        set_angle(values, 2, 20.)
        set_angle(values, 4, None, status="degenerate_geometry")
        set_angle(values, 5, 35.)
        result = describe_event_transition(clip(values=values))
        elbow = result["joints"]["throwing_elbow"]
        self.assertEqual([elbow[key] for key in PAIR_COUNTS], [4, 1, 3, 2, 2])
        pairs = {(pair["start_frame"], pair["end_frame"]): pair for pair in elbow["pairs"]}
        self.assertEqual({key: pair["status"] for key, pair in pairs.items()},
                         {(1, 4): "missing_and_degenerate", (1, 5): "missing_coordinates",
                          (2, 4): "degenerate_geometry", (2, 5): "calculated_from_model_xy"})
        self.assertTrue(all(pairs[key]["delta_model_xy_deg"] is None for key in ((1, 4), (1, 5), (2, 4))))
        self.assertIsNone(pairs[(1, 4)]["start_model_xy_deg"])
        self.assertIsNone(pairs[(1, 4)]["end_model_xy_deg"])
        self.assertEqual((elbow["min_delta_deg"], elbow["max_delta_deg"], elbow["delta_direction"]),
                         (15., 15., "positive"))
        self.assertEqual(result["joints"]["lead_knee"]["calculated_pairs"], 4)
        self.assertEqual(result["joints"]["lead_knee"]["unavailable_pairs"], 0)

    def test_zero_calculated_pairs_keep_null_extrema_and_all_unavailable_pairs(self):
        values = fixtures.rows()
        set_angle(values, 1, None, status="missing_coordinates")
        set_angle(values, 4, None, status="degenerate_geometry")
        result = describe_event_transition(clip(fixtures.exact(1), fixtures.exact(4), values=values))
        self.assertEqual(result["status"], "descriptive_model_xy_transition")
        elbow = result["joints"]["throwing_elbow"]
        self.assertEqual([elbow[key] for key in PAIR_COUNTS], [1, 0, 1, 1, 1])
        self.assertIsNone(elbow["min_delta_deg"])
        self.assertIsNone(elbow["max_delta_deg"])
        self.assertEqual(elbow["delta_direction"], "unavailable")
        self.assertEqual(len(elbow["pairs"]), 1)
        self.assertIsNone(elbow["pairs"][0]["delta_model_xy_deg"])
        self.assertEqual(elbow["pairs"][0]["status"], "missing_and_degenerate")

    def test_direction_distinguishes_zero_from_ranges_that_include_zero(self):
        cases = [((20., 30.), "positive", (10., 20.)),
                 ((5., 7.), "negative", (-5., -3.)),
                 ((10., 10.), "zero", (0., 0.)),
                 ((5., 15.), "includes_zero", (-5., 5.)),
                 ((10., 15.), "includes_zero", (0., 5.)),
                 ((5., 10.), "includes_zero", (-5., 0.))]
        for endpoints, direction, bounds in cases:
            with self.subTest(endpoints=endpoints):
                values = fixtures.rows()
                set_angle(values, 1, 10.)
                set_angle(values, 4, endpoints[0])
                set_angle(values, 5, endpoints[1])
                result = describe_event_transition(clip(fixtures.exact(1), fixtures.ranged(4, 5), values=values))
                elbow = result["joints"]["throwing_elbow"]
                self.assertEqual(elbow["delta_direction"], direction)
                self.assertEqual((elbow["min_delta_deg"], elbow["max_delta_deg"]), bounds)
                self.assertEqual(elbow["pointwise_reliability"], "unknown")
                self.assertIsNone(elbow["usable_for_analysis"])

    def test_unresolved_events_preserve_candidate_bounds_without_reading_candidate_rows(self):
        class UnreadableRows:
            def __getitem__(self, key):
                raise AssertionError("Unresolved event candidates must not supply endpoint values")

            def __iter__(self):
                raise AssertionError("Unresolved event candidates must not be scanned")

        cases = [(fixtures.ranged(1, 2, status="uncertain"), fixtures.exact(5)),
                 (fixtures.exact(1), fixtures.ranged(4, 5, status="uncertain")),
                 ({"status": "not_observable", "frame_index": None}, fixtures.exact(5))]
        for start, end in cases:
            with self.subTest(start=start, end=end):
                source = clip(start, end)
                source["rows"] = UnreadableRows()
                result = describe_event_transition(source)
                self.assertEqual(result["status"], "unavailable")
                self.assertTrue(result["reason"])
                self.assertEqual(result["start_frame_bounds"], source["events"]["foot_plant"]["frame_bounds"])
                self.assertEqual(result["end_frame_bounds"], source["events"]["approximate_release"]["frame_bounds"])
                self.assertEqual(result["timing"], source["timing"]["foot_plant_to_release"])
                for key in ("all_endpoint_pairs", "chronological_pairs", "excluded_nonchronological_pairs"):
                    self.assertIsNone(result[key])
                for joint in result["joints"].values():
                    for key in (*PAIR_COUNTS, "min_delta_deg", "max_delta_deg"):
                        self.assertIsNone(joint[key])
                    self.assertEqual(joint["delta_direction"], "unavailable")
                    self.assertEqual(joint["pairs"], [])
                    self.assertEqual(joint["pointwise_reliability"], "unknown")
                    self.assertIsNone(joint["usable_for_analysis"])

    def test_results_and_nested_timing_are_independent_of_source_data(self):
        source = clip()
        before = deepcopy(source)
        result = describe_event_transition(source)
        self.assertEqual(source, before)
        self.assertEqual(result["timing"], source["timing"]["foot_plant_to_release"])
        self.assertIsNot(result["timing"], source["timing"]["foot_plant_to_release"])
        result["start_frame_bounds"][0] = 999
        result["end_frame_bounds"][0] = 999
        result["timing"]["frame_bounds"][0] = 999
        result["timing"]["seconds_bounds"][0] = 999.
        result["joints"]["throwing_elbow"]["pairs"][0]["start_model_xy_deg"] = 999.
        self.assertEqual(source, before)


class NativeMotionTransitionExportTests(unittest.TestCase):
    @staticmethod
    def csv_rows(path):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            return reader.fieldnames, list(reader)

    def test_normal_event_export_adds_summary_pair_csvs_and_report_without_source_changes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = fixtures.NativeMotionEventExportTests().fixture(Path(temp))
            data["truth"]["labels"]["events"]["approximate_release"] = fixtures.ranged(1, 2)
            fixtures.NativeMotionEventExportTests.refresh(data)
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
                 patch("cv2.VideoCapture", side_effect=AssertionError("saved curves only")), \
                 patch("pitch_analysis.analysis.native_motion_report.describe_native_motion",
                       side_effect=AssertionError("do not recompute source angles")):
                result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            transitions = result["event_transition_readouts"]
            self.assertEqual(len(transitions), 1)
            transition = transitions[0]
            self.assertEqual(transition["pitch_id"], "pitch_fixture")
            self.assertEqual(transition["timing"], result["clips"][0]["timing"]["foot_plant_to_release"])
            summary_path = data["comparison"] / "event_transition_readouts.csv"
            pair_path = data["comparison"] / "event_transition_pairs.csv"
            summary_fields, summaries = self.csv_rows(summary_path)
            pair_fields, pairs = self.csv_rows(pair_path)
            self.assertEqual(len(summaries), 2)
            self.assertEqual({row["joint"] for row in summaries}, set(ROLES))
            self.assertEqual(len(pairs), 4)
            self.assertEqual({(row["joint"], row["start_frame"], row["end_frame"]) for row in pairs},
                             {(role, "1", end) for role in ROLES for end in ("1", "2")})
            for row in summaries:
                self.assertEqual(row["pitch_id"], "pitch_fixture")
                joint = transition["joints"][row["joint"]]
                for key in (*PAIR_COUNTS, "min_delta_deg", "max_delta_deg", "delta_direction"):
                    self.assertIn(key, summary_fields)
                    self.assertEqual(row[key], str(joint[key]))
                self.assertEqual(row["pointwise_reliability"], "unknown")
                self.assertEqual(row["usable_for_analysis"], "")
            for row in pairs:
                joint = transition["joints"][row["joint"]]
                pair = next(pair for pair in joint["pairs"] if pair["start_frame"] == int(row["start_frame"])
                            and pair["end_frame"] == int(row["end_frame"]))
                self.assertEqual(row["pitch_id"], "pitch_fixture")
                for key, value in pair.items():
                    self.assertIn(key, pair_fields)
                    self.assertEqual(row[key], "" if value is None else str(value))
            report = (data["comparison"] / "report.md").read_text(encoding="utf-8")
            self.assertIn("落地→大致出手的模型XY變化", report)
            self.assertIn("unknown", report)
            self.assertIn("null", report)
            for key, path in (("transition_readouts_csv_ref", summary_path), ("transition_pairs_csv_ref", pair_path)):
                self.assertEqual(result["artifacts"][key], reference(data["root"], path))
            self.assertEqual(read_json(data["comparison"] / "event_comparison.json"), result)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertFalse(result["angle_values_recomputed"])
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertEqual(result["new_ground_truth_labels"], 0)
            self.assertEqual(result["pointwise_reliability"], "unknown")
            self.assertIsNone(result["usable_for_analysis"])

    def test_unresolved_transition_exports_null_summary_counts_and_no_pair_rows(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = fixtures.NativeMotionEventExportTests().fixture(Path(temp))
            events = data["truth"]["labels"]["events"]
            events["foot_plant"] = fixtures.ranged(1, 1, status="uncertain")
            events["approximate_release"] = fixtures.exact(2)
            fixtures.NativeMotionEventExportTests.refresh(data)
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            transition = result["event_transition_readouts"][0]
            self.assertEqual(transition["status"], "unavailable")
            self.assertEqual(transition["start_frame_bounds"], [1, 1])
            _, summaries = self.csv_rows(data["comparison"] / "event_transition_readouts.csv")
            fields, pairs = self.csv_rows(data["comparison"] / "event_transition_pairs.csv")
            self.assertEqual(len(summaries), 2)
            self.assertEqual(pairs, [])
            self.assertIn("delta_model_xy_deg", fields)
            for row in summaries:
                for key in (*PAIR_COUNTS, "min_delta_deg", "max_delta_deg"):
                    self.assertEqual(row[key], "")
                self.assertEqual(row["delta_direction"], "unavailable")
                self.assertEqual(row["pointwise_reliability"], "unknown")
                self.assertEqual(row["usable_for_analysis"], "")
            self.assertEqual({path: path.read_bytes() for path in before}, before)


if __name__ == "__main__":
    unittest.main()
