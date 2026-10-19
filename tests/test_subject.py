"""The subject selector must reject ambiguity and avoid easy identity switches."""
from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import asdict
import json
from types import SimpleNamespace

from pitch_analysis.subject import PitcherSelector


def pose(hip_x: float, hip_y: float = .5, confidence: float = .9) -> list:
    points = [SimpleNamespace(x=hip_x, y=hip_y, visibility=confidence,
                              presence=confidence) for _ in range(33)]
    for index in (11, 12):
        points[index].y = hip_y - .2
    for index in (27, 28):
        points[index].y = hip_y + .3
    return points


class PitcherSelectorTests(unittest.TestCase):
    def test_selects_centered_full_body_without_assuming_first_pose(self):
        selector = PitcherSelector()
        choice = selector.select([pose(.8), pose(.5)])
        self.assertEqual((choice.index, choice.status), (1, "selected"))
        self.assertEqual(selector.select([pose(.8), pose(.51)]).index, 1)

    def test_rejects_ambiguous_and_distant_identity_switch(self):
        selector = PitcherSelector()
        self.assertEqual(selector.select([pose(.49), pose(.51)]).status, "ambiguous")
        self.assertEqual(selector.select([pose(.5)]).status, "selected")
        self.assertEqual(selector.select([pose(.8)]).status, "rejected")

    def test_rejects_low_confidence_or_out_of_protocol_roi(self):
        selector = PitcherSelector()
        self.assertEqual(selector.select([pose(.5, confidence=.1)]).status, "rejected")
        self.assertEqual(selector.select([pose(.95)]).status, "rejected")

    def test_default_scores_state_and_selection_fields_remain_unchanged(self):
        selector = PitcherSelector()
        first = selector.select([pose(.8), pose(.5)])
        self.assertEqual(asdict(first), {
            "index": 1, "status": "selected",
            "reason": "rear_centerfield_spatial_scale_continuity",
            "candidate_count": 2, "score": .9550000000000001, "mean_confidence": .9,
        })
        self.assertAlmostEqual(selector.select([pose(.5)]).score, 1.205)
        self.assertEqual(selector.select([pose(.8)]).status, "rejected")
        self.assertEqual(selector.previous, (.5, .5, .5))
        for _ in range(6):
            selector.select([])
        self.assertEqual(selector.gap, 7)
        self.assertEqual(selector.select([pose(.8)]).status, "selected")


class PitcherRegionTests(unittest.TestCase):
    def test_roi_rejects_high_scoring_other_person_and_selects_lower_score_pitcher(self):
        poses = [pose(.5, confidence=1), pose(.2, confidence=.85)]
        self.assertEqual(PitcherSelector().select(poses).index, 0)
        selector = PitcherSelector(subject_roi=(.15, .25, .3, .6))
        self.assertEqual(selector.select(poses).index, 1)
        self.assertEqual(selector.last_decision["candidates"][0]["rejection_reason"],
                         "outside_subject_roi")

    def test_each_raw_shoulder_and_hip_must_fit_not_only_body_center(self):
        for joint in (11, 12, 23, 24):
            for axis in ("x", "y"):
                with self.subTest(joint=joint, axis=axis):
                    candidate = pose(.5)
                    setattr(candidate[joint], axis, .71)
                    selector = PitcherSelector(subject_roi=(.3, .2, .7, .6))
                    self.assertIsNone(selector.select([candidate]).index)

    def test_all_roi_mismatches_remain_missing_and_keep_previous_anchor(self):
        selector = PitcherSelector(subject_roi=(.3, .2, .7, .6))
        selector.select([pose(.5)])
        choice = selector.select([pose(.2), pose(.8)])
        self.assertEqual((choice.index, choice.status, choice.reason),
                         (None, "rejected", "no_reliable_pitcher_candidate"))
        self.assertEqual((selector.previous, selector.gap), ((.5, .5, .5), 1))
        self.assertTrue(all(not row["eligible"] for row in selector.last_decision["candidates"]))

    def test_long_gap_never_allows_reacquisition_outside_roi(self):
        selector = PitcherSelector(subject_roi=(.3, .2, .7, .6))
        selector.select([pose(.5)])
        for _ in range(10):
            self.assertEqual(selector.select([pose(.8, confidence=1)]).status, "rejected")
        self.assertEqual((selector.previous, selector.gap), ((.5, .5, .5), 10))
        self.assertEqual(selector.select([pose(.5)]).status, "selected")

    def test_ambiguity_inside_roi_keeps_original_behavior(self):
        selector = PitcherSelector(subject_roi=(.3, .2, .7, .6))
        choice = selector.select([pose(.49), pose(.51), pose(.8)])
        self.assertEqual((choice.index, choice.status), (None, "ambiguous"))
        self.assertIsNone(selector.previous)
        self.assertEqual(selector.gap, 1)
        self.assertEqual([row["eligible"] for row in selector.last_decision["candidates"]],
                         [True, True, False])

    def test_limbs_can_extend_outside_roi_without_changing_any_coordinate(self):
        candidate = pose(.5)
        candidate[13].x = .01
        candidate[14].x = .99
        candidate[15].y = .01
        candidate[16].y = .99
        candidate[27].x = .01
        candidate[28].x = .99
        before = deepcopy(candidate)
        selector = PitcherSelector(subject_roi=(.3, .3, .7, .5))
        self.assertEqual(selector.select([candidate]).status, "selected")
        self.assertEqual(candidate, before)

    def test_roi_rejects_nonfinite_raw_anchor_and_trace_stays_json_safe(self):
        candidate = pose(.5)
        candidate[11].x = float("nan")
        selector = PitcherSelector(subject_roi=(.3, .2, .7, .6))
        self.assertEqual(selector.select([candidate]).status, "rejected")
        self.assertEqual(selector.last_decision["candidates"][0]["rejection_reason"],
                         "outside_subject_roi")
        json.dumps(selector.last_decision, allow_nan=False)

    def test_roi_validation_rejects_wrong_shape_types_and_order(self):
        invalid = [(), (.1, .2, .3), (.1, .2, .3, .4, .5), "0,0,1,1",
                   (False, 0, 1, 1), (0, 0, True, 1), ("0", 0, 1, 1),
                   (0, 0, float("nan"), 1), (0, 0, float("inf"), 1),
                   (-.1, 0, 1, 1), (0, 0, 1.1, 1), (0, .2, 1, .2),
                   (.5, 0, .5, 1), (.6, 0, .4, 1), (0, .7, 1, .6)]
        for value in invalid:
            with self.subTest(roi=value), self.assertRaises(ValueError):
                PitcherSelector(subject_roi=value)
        self.assertEqual(PitcherSelector(subject_roi=(0, 0, 1, 1)).subject_roi,
                         (0., 0., 1., 1.))

    def test_roi_list_is_copied_to_immutable_configuration(self):
        configuration = [.3, .2, .7, .6]
        selector = PitcherSelector(subject_roi=configuration)
        configuration[0] = .9
        self.assertEqual(selector.subject_roi, (.3, .2, .7, .6))

    def test_trace_contains_applied_scores_and_state_without_changing_selection(self):
        selector = PitcherSelector(subject_roi=(.3, .2, .7, .6))
        selector.select([pose(.5)])
        choice = selector.select([pose(.51)])
        trace = selector.last_decision
        self.assertEqual(trace["subject_roi"], [.3, .2, .7, .6])
        self.assertEqual(trace["anchor_before"], [.5, .5, .5])
        self.assertEqual(trace["anchor_after"], [.51, .5, .5])
        self.assertEqual((trace["gap_before"], trace["gap_after"]), (0, 0))
        self.assertEqual((trace["selected_index"], trace["status"], trace["reason"]),
                         (choice.index, choice.status, choice.reason))
        row = trace["candidates"][0]
        self.assertTrue(row["eligible"])
        self.assertIsNone(row["rejection_reason"])
        self.assertEqual(row["hip_xy"], [.51, .5])
        self.assertEqual(row["body_height"], .5)
        self.assertAlmostEqual(row["confidence"], .9)
        self.assertAlmostEqual(row["spatial"], 1 - .01 / .35)
        self.assertEqual(row["scale"], 1)
        self.assertAlmostEqual(row["continuity"], .25 * (1 - .01 / .18))
        self.assertAlmostEqual(row["base_total"] + row["continuity"], choice.score)
        self.assertEqual((row["score"], row["final_score"]), (choice.score, choice.score))
        json.dumps(trace, allow_nan=False)

    def test_trace_is_fresh_for_empty_and_continuity_rejected_frames(self):
        selector = PitcherSelector()
        selector.select([pose(.5)])
        selector.select([pose(.8)])
        trace = selector.last_decision
        self.assertEqual(trace["candidates"][0]["rejection_reason"],
                         "outside_short_term_continuity")
        self.assertEqual((trace["gap_before"], trace["gap_after"]), (0, 1))
        selector.select([])
        self.assertEqual(selector.last_decision["candidates"], [])
        self.assertEqual(selector.last_decision["candidate_count"], 0)
        self.assertEqual((selector.last_decision["gap_before"], selector.last_decision["gap_after"]),
                         (1, 2))


if __name__ == "__main__":
    unittest.main()
