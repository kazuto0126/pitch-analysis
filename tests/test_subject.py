"""The subject selector must reject ambiguity and avoid easy identity switches."""
from __future__ import annotations

import unittest
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


if __name__ == "__main__":
    unittest.main()
