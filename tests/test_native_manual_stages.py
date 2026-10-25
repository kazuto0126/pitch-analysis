"""Four manual stages preserve endpoint uncertainty and the original single stage."""
from copy import deepcopy
import csv
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_native_motion_events as fixtures

from pitch_analysis.analysis.native_motion_events import describe_events, write_event_comparison
from pitch_analysis.analysis.native_motion_transition import (
    describe_event_transition, describe_manual_event_transitions,
)
from pitch_analysis.native_pose_io import read_json, reference


ROLES = ("throwing_elbow", "lead_knee")
KEYS = ("preparation_to_leg_lift", "leg_lift_to_foot_plant",
        "foot_plant_to_release", "release_to_follow_through_end")
PAIR_COUNTS = ("total_pairs", "calculated_pairs", "unavailable_pairs",
               "missing_endpoint_pairs", "degenerate_endpoint_pairs")


def clip(*, values=None, event_overrides=None):
    values = fixtures.rows() if values is None else values
    events = {"preparation_start": fixtures.exact(0), "leg_lift": fixtures.exact(1),
              "foot_plant": fixtures.exact(3), "approximate_release": fixtures.exact(5),
              "follow_through_end": fixtures.exact(7)}
    events.update(event_overrides or {})
    fps = Fraction(60000, 1001)
    return {"pitch_id": "pitch_fixture", "fps_fraction": str(fps), "rows": values,
            **describe_events(events, fps, values)}


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


class NativeManualStageTests(unittest.TestCase):
    def test_four_stages_have_hand_calculated_endpoint_differences_and_fractional_times(self):
        values = fixtures.rows()
        for role, angles in (("throwing_elbow", (15., 45., 10., 80., 50.)),
                             ("lead_knee", (80., 100., 130., 120., 120.))):
            for frame, angle in zip((0, 1, 3, 5, 7), angles, strict=True):
                values[frame][f"{role}_model_xy_deg"] = angle
        source = clip(values=values)
        results = describe_manual_event_transitions(source)
        self.assertEqual([result["transition_key"] for result in results], list(KEYS))
        expected = {"throwing_elbow": (30., -35., 70., -30.),
                    "lead_knee": (20., 30., -10., 0.)}
        for index, (result, frames) in enumerate(zip(results, (1, 2, 2, 2), strict=True)):
            self.assertEqual(result["status"], "descriptive_model_xy_transition")
            self.assertEqual(result["timing"], source["timing"][KEYS[index]])
            self.assertEqual((result["all_endpoint_pairs"], result["chronological_pairs"]), (1, 1))
            for role in ROLES:
                joint = result["joints"][role]
                self.assertEqual((joint["min_delta_deg"], joint["max_delta_deg"]),
                                 (expected[role][index], expected[role][index]))
                pair = joint["pairs"][0]
                self.assertEqual(pair["delta_model_xy_deg"], expected[role][index])
                self.assertEqual(pair["elapsed_frames"], frames)
                self.assertEqual(pair["elapsed_seconds_fraction"], str(Fraction(frames * 1001, 60000)))
                self.assertEqual(pair["elapsed_seconds"], float(Fraction(frames * 1001, 60000)))
                self.assertEqual(joint["pointwise_reliability"], "unknown")
                self.assertIsNone(joint["usable_for_analysis"])

    def test_stage_order_and_event_names_follow_the_supplied_timing_records(self):
        source = clip()
        order = (KEYS[3], KEYS[1], KEYS[0], KEYS[2])
        source["timing"] = {key: source["timing"][key] for key in order}
        results = describe_manual_event_transitions(source)
        self.assertEqual([item["transition_key"] for item in results], list(order))
        for result, key in zip(results, order, strict=True):
            record = source["timing"][key]
            self.assertEqual(result["start_event"], record["start_event"])
            self.assertEqual(result["end_event"], record["end_event"])
            self.assertEqual(result["start_frame_bounds"], source["events"][record["start_event"]]["frame_bounds"])
            self.assertEqual(result["end_frame_bounds"], source["events"][record["end_event"]]["frame_bounds"])
            self.assertEqual(result["timing"], record)

    def test_uncertain_shared_event_leaves_both_adjacent_stages_unavailable(self):
        class CandidateRow(dict):
            def __getitem__(self, key):
                if key.startswith(ROLES):
                    raise AssertionError("Uncertain shared-event candidate angles must not be read")
                return super().__getitem__(key)

        source = clip(event_overrides={"leg_lift": fixtures.ranged(1, 2, status="uncertain")})
        for frame in (1, 2):
            source["rows"][frame] = CandidateRow(source["rows"][frame])
        results = describe_manual_event_transitions(source)
        self.assertEqual([result["status"] for result in results],
                         ["unavailable", "unavailable", "descriptive_model_xy_transition", "descriptive_model_xy_transition"])
        self.assertEqual(results[0]["end_frame_bounds"], [1, 2])
        self.assertEqual(results[1]["start_frame_bounds"], [1, 2])
        for result in results[:2]:
            self.assertTrue(result["reason"])
            self.assertIsNone(result["all_endpoint_pairs"])
            self.assertIsNone(result["chronological_pairs"])
            for joint in result["joints"].values():
                self.assertTrue(all(joint[key] is None for key in (*PAIR_COUNTS, "min_delta_deg", "max_delta_deg")))
                self.assertEqual(joint["pairs"], [])
                self.assertEqual(joint["delta_direction"], "unavailable")

    def test_missing_joint_at_a_shared_endpoint_only_affects_its_adjacent_stages(self):
        values = fixtures.rows()
        values[3].update(throwing_elbow_model_xy_deg=None,
                         throwing_elbow_coordinate_status="missing_coordinates")
        results = describe_manual_event_transitions(clip(values=values))
        for index, result in enumerate(results):
            self.assertEqual(result["status"], "descriptive_model_xy_transition")
            elbow, knee = result["joints"]["throwing_elbow"], result["joints"]["lead_knee"]
            self.assertEqual(knee["calculated_pairs"], 1)
            self.assertEqual(knee["unavailable_pairs"], 0)
            if index in (1, 2):
                self.assertEqual([elbow[key] for key in PAIR_COUNTS], [1, 0, 1, 1, 0])
                self.assertIsNone(elbow["min_delta_deg"])
                self.assertIsNone(elbow["max_delta_deg"])
                self.assertEqual(elbow["pairs"][0]["status"], "missing_coordinates")
            else:
                self.assertEqual([elbow[key] for key in PAIR_COUNTS], [1, 1, 0, 0, 0])
                self.assertIsNotNone(elbow["min_delta_deg"])

    def test_default_single_stage_remains_identical_without_the_new_transition_key(self):
        for overrides, reason in ((None, "出手模型XY角減落地模型XY角；保留全部合法影格配對，未選中點"),
                                  ({"foot_plant": fixtures.ranged(3, 3, status="uncertain")},
                                   "人工事件未確認；未取候選影格計算")):
            with self.subTest(overrides=overrides):
                source = clip(event_overrides=overrides)
                single = describe_event_transition(source)
                stage = next(item for item in describe_manual_event_transitions(source)
                             if item["transition_key"] == "foot_plant_to_release")
                self.assertNotIn("transition_key", single)
                self.assertEqual({key: value for key, value in stage.items() if key != "transition_key"}, single)
                self.assertEqual(single["reason"], reason)

    def test_stage_results_deep_copy_source_timing_bounds_and_shared_event_data(self):
        source = clip()
        before = deepcopy(source)
        results = describe_manual_event_transitions(source)
        self.assertEqual(source, before)
        untouched_second = deepcopy(results[1])
        results[0]["end_frame_bounds"][0] = 999
        results[0]["timing"]["frame_bounds"][0] = 999
        results[0]["timing"]["seconds_bounds"][0] = 999.
        results[0]["joints"]["throwing_elbow"]["pairs"][0]["end_model_xy_deg"] = 999.
        self.assertEqual(source, before)
        self.assertEqual(results[1], untouched_second)


class NativeManualStageExportTests(unittest.TestCase):
    def test_export_has_eight_summary_rows_all_pairs_and_compatible_existing_outputs(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = fixtures.NativeMotionEventExportTests().fixture(Path(temp))
            data["truth"]["labels"]["events"]["approximate_release"] = fixtures.ranged(1, 2)
            fixtures.NativeMotionEventExportTests.refresh(data)
            before = {path: path.read_bytes() for path in data["root"].rglob("*") if path.is_file()}
            with patch("subprocess.Popen", side_effect=AssertionError("no inference or browser")), \
                 patch("cv2.VideoCapture", side_effect=AssertionError("saved data only")), \
                 patch("pitch_analysis.analysis.native_motion_report.describe_native_motion",
                       side_effect=AssertionError("do not recompute angles")):
                result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            stages = result["manual_stage_readouts"]
            self.assertEqual([item["transition_key"] for item in stages], list(KEYS))
            self.assertTrue(all(item["pitch_id"] == "pitch_fixture" for item in stages))
            old_fields, old_rows = csv_rows(data["comparison"] / "event_transition_readouts.csv")
            old_pair_fields, old_pairs = csv_rows(data["comparison"] / "event_transition_pairs.csv")
            fields, rows = csv_rows(data["comparison"] / "manual_stage_readouts.csv")
            pair_fields, pairs = csv_rows(data["comparison"] / "manual_stage_pairs.csv")
            self.assertEqual(fields, ["transition_key", *old_fields])
            self.assertEqual(pair_fields, ["transition_key", *old_pair_fields])
            self.assertEqual(len(old_rows), 2)
            self.assertEqual(len(old_pairs), 4)
            self.assertEqual(len(rows), 8)
            self.assertEqual(len(pairs), 12)
            self.assertEqual({(row["transition_key"], row["joint"]) for row in rows},
                             {(key, role) for key in KEYS for role in ROLES})
            pair_map = {(row["transition_key"], row["joint"], int(row["start_frame"]), int(row["end_frame"])): row
                        for row in pairs}
            self.assertEqual(len(pair_map), len(pairs))
            for stage in stages:
                for role, joint in stage["joints"].items():
                    row = next(row for row in rows if row["transition_key"] == stage["transition_key"] and row["joint"] == role)
                    for key in (*PAIR_COUNTS, "min_delta_deg", "max_delta_deg", "delta_direction"):
                        self.assertEqual(row[key], str(joint[key]))
                    self.assertEqual(row["pointwise_reliability"], "unknown")
                    self.assertEqual(row["usable_for_analysis"], "")
                    for pair in joint["pairs"]:
                        row = pair_map[(stage["transition_key"], role, pair["start_frame"], pair["end_frame"])]
                        for key, value in pair.items():
                            self.assertEqual(row[key], "" if value is None else str(value))
            foot = next(item for item in stages if item["transition_key"] == "foot_plant_to_release")
            self.assertEqual({key: value for key, value in foot.items() if key != "transition_key"},
                             result["event_transition_readouts"][0])
            self.assertEqual([{key: value for key, value in row.items() if key != "transition_key"}
                              for row in rows if row["transition_key"] == "foot_plant_to_release"], old_rows)
            self.assertEqual([{key: value for key, value in row.items() if key != "transition_key"}
                              for row in pairs if row["transition_key"] == "foot_plant_to_release"], old_pairs)
            self.assertEqual(len(csv_rows(data["comparison"] / "event_timing.csv")[1]), 4)
            self.assertEqual(len(csv_rows(data["comparison"] / "event_angle_readouts.csv")[1]), 10)
            report = (data["comparison"] / "report.md").read_text(encoding="utf-8")
            self.assertIn("不能直接相加", report)
            self.assertIn("落地→大致出手的模型XY變化", report)
            for key, name in (("manual_stage_readouts_csv_ref", "manual_stage_readouts.csv"),
                              ("manual_stage_pairs_csv_ref", "manual_stage_pairs.csv")):
                self.assertEqual(result["artifacts"][key], reference(data["root"], data["comparison"] / name))
            self.assertEqual(read_json(data["comparison"] / "event_comparison.json"), result)
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_unresolved_shared_event_still_exports_all_summary_rows_with_null_counts(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            data = fixtures.NativeMotionEventExportTests().fixture(Path(temp))
            events = data["truth"]["labels"]["events"]
            events["leg_lift"] = fixtures.ranged(0, 0, status="uncertain")
            events["approximate_release"] = fixtures.ranged(1, 2)
            fixtures.NativeMotionEventExportTests.refresh(data)
            result = write_event_comparison(data["root"], data["request_path"], data["comparison"])
            stages = result["manual_stage_readouts"]
            self.assertEqual([item["status"] for item in stages],
                             ["unavailable", "unavailable", "descriptive_model_xy_transition", "descriptive_model_xy_transition"])
            _, rows = csv_rows(data["comparison"] / "manual_stage_readouts.csv")
            _, pairs = csv_rows(data["comparison"] / "manual_stage_pairs.csv")
            self.assertEqual(len(rows), 8)
            self.assertEqual(len(pairs), 8)
            self.assertEqual({row["transition_key"] for row in pairs}, set(KEYS[2:]))
            for row in rows:
                if row["transition_key"] in KEYS[:2]:
                    self.assertEqual(row["status"], "unavailable")
                    for key in (*PAIR_COUNTS, "min_delta_deg", "max_delta_deg"):
                        self.assertEqual(row[key], "")
                    self.assertEqual(row["delta_direction"], "unavailable")
                self.assertEqual(row["pointwise_reliability"], "unknown")
                self.assertEqual(row["usable_for_analysis"], "")
            self.assertEqual(stages[0]["end_frame_bounds"], [0, 0])
            self.assertEqual(stages[1]["start_frame_bounds"], [0, 0])


if __name__ == "__main__":
    unittest.main()
