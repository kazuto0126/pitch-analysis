"""Exact closed-set geometry cases independent of models and annotations."""
from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import torso_geometry as geometry
finally:
    sys.path.pop(0)


SQUARE = [(0., 0.), (2., 0.), (2., 2.), (0., 2.)]


class ConvexHullTests(unittest.TestCase):
    def test_order_deduplication_and_counterclockwise_boundary(self):
        points = [(2, 2), (1, 1), (0, 2), (0, 0), (2, 0), (0, 0), (1, 0)]
        expected = SQUARE
        self.assertEqual(geometry.convex_hull(points), expected)
        self.assertEqual(geometry.convex_hull(reversed(points)), expected)
        self.assertGreater(geometry.signed_polygon_area(expected), 0)

    def test_empty_point_and_collinear_hulls(self):
        self.assertEqual(geometry.convex_hull([]), [])
        self.assertEqual(geometry.convex_hull([(1, 2), (1, 2)]), [(1., 2.)])
        self.assertEqual(geometry.convex_hull([(2, 2), (0, 0), (1, 1)]),
                         [(0., 0.), (2., 2.)])
        for points in ([], [(1, 2)], [(0, 0), (1, 1), (2, 2)]):
            self.assertEqual(geometry.polygon_area(points), 0)

    def test_nonfinite_and_malformed_points_rejected(self):
        for points in ([(math.nan, 0)], [(0, math.inf)], [(-math.inf, 0)],
                       [(0,)], [(0, 1, 2)], [(None, 1)]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                geometry.convex_hull(points)
            with self.subTest(points=points), self.assertRaises(ValueError):
                geometry.polygon_area(points)

    def test_signed_and_absolute_area_accept_closed_boundary(self):
        self.assertEqual(geometry.signed_polygon_area(SQUARE), 4.)
        self.assertEqual(geometry.signed_polygon_area(reversed(SQUARE)), -4.)
        self.assertEqual(geometry.polygon_area(reversed(SQUARE)), 4.)
        self.assertEqual(geometry.polygon_area(SQUARE + [SQUARE[0]]), 4.)


class ClosedIntersectionTests(unittest.TestCase):
    def assert_intersection(self, a, b, expected):
        a, b = list(a), list(b)
        self.assertEqual(geometry.closed_convex_polygons_intersect(a, b), expected)
        self.assertEqual(geometry.closed_convex_polygons_intersect(b, a), expected)

    def test_disjoint_despite_positive_bounding_box_overlap(self):
        a = [(0, 0), (3, 0), (0, 3)]
        b = [(2, 2), (5, 2), (2, 5)]
        self.assert_intersection(a, b, False)

    def test_containment_and_equal_polygons(self):
        self.assert_intersection(SQUARE, [(0.5, 0.5), (1.5, 0.5), (1, 1.5)], True)
        self.assert_intersection(SQUARE, reversed(SQUARE), True)

    def test_shared_edge_is_closed_intersection(self):
        self.assert_intersection(SQUARE, [(2, 0), (3, 0), (3, 2), (2, 2)], True)

    def test_only_shared_corner_is_closed_intersection(self):
        self.assert_intersection(SQUARE, [(2, 2), (3, 2), (3, 3), (2, 3)], True)

    def test_rotated_thin_polygons_cross_without_vertex_containment(self):
        a = [(-3, -2.9), (-2.9, -3), (3, 2.9), (2.9, 3)]
        b = [(-3, 2.9), (-2.9, 3), (3, -2.9), (2.9, -3)]
        self.assert_intersection(a, b, True)

    def test_rotated_parallel_thin_polygons_are_disjoint(self):
        a = [(-3, -2.9), (-2.9, -3), (3, 2.9), (2.9, 3)]
        b = [(x, y + 0.3) for x, y in a]
        self.assert_intersection(a, b, False)

    def test_a_representable_gap_is_not_treated_as_touching(self):
        x = math.nextafter(2., math.inf)
        self.assert_intersection(SQUARE, [(x, 0), (3, 0), (3, 2), (x, 2)], False)

    def test_degenerate_hulls_are_rejected(self):
        for bad in ([], [(0, 0)], [(0, 0), (1, 1)], [(0, 0), (1, 1), (2, 2)]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                geometry.closed_convex_polygons_intersect(bad, SQUARE)

    def test_tiny_finite_coordinates_keep_nonzero_orientation(self):
        scale = 1e-200
        a = [(0, 0), (scale, 0), (scale, scale), (0, scale)]
        b = [(2 * scale, 0), (3 * scale, 0), (3 * scale, scale), (2 * scale, scale)]
        self.assertEqual(len(geometry.convex_hull(a)), 4)
        self.assert_intersection(a, a, True)
        self.assert_intersection(a, b, False)


if __name__ == "__main__":
    unittest.main()
