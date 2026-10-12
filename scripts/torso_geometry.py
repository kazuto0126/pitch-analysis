"""Closed convex geometry with no distance, confidence, or area tolerance.

Coordinates are finite Python floats. Orientation uses their exact rational
values so rounding, underflow, and overflow do not introduce a hidden geometry
tolerance. Public area results use the ordinary floating point representation.
This module has no video, subject-selection, or annotation dependencies.
"""
from __future__ import annotations

from fractions import Fraction
import math
from typing import Iterable, Sequence

Point = tuple[float, float]
ExactPoint = tuple[Fraction, Fraction]


def _points(points: Iterable[Sequence[float]]) -> list[Point]:
    result = []
    for point in points:
        if len(point) != 2:
            raise ValueError("Each point must contain exactly two coordinates")
        try:
            x, y = float(point[0]), float(point[1])
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Coordinates must be finite numbers") from error
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Coordinates must be finite numbers")
        # Canonicalize signed zero as well as duplicate coordinate pairs.
        result.append((x if x else 0.0, y if y else 0.0))
    return result


def _exact(point: Point) -> ExactPoint:
    return Fraction.from_float(point[0]), Fraction.from_float(point[1])


def _cross(a: ExactPoint, b: ExactPoint, c: ExactPoint) -> Fraction:
    return ((b[0] - a[0]) * (c[1] - a[1])
            - (b[1] - a[1]) * (c[0] - a[0]))


def convex_hull(points: Iterable[Sequence[float]]) -> list[Point]:
    """Return the deterministic monotonic-chain hull, CCW from its least point.

Duplicate points and collinear intermediate vertices are removed. Empty input
returns []; coincident input returns one point; collinear input returns its two
extreme points. No closing vertex is repeated at the end.
"""
    ordered = sorted(set(_points(points)))
    if len(ordered) <= 1:
        return ordered
    exact = {point: _exact(point) for point in ordered}

    def chain(vertices: Iterable[Point]) -> list[Point]:
        boundary: list[Point] = []
        for point in vertices:
            while (len(boundary) >= 2
                   and _cross(exact[boundary[-2]], exact[boundary[-1]],
                              exact[point]) <= 0):
                boundary.pop()
            boundary.append(point)
        return boundary

    return chain(ordered)[:-1] + chain(reversed(ordered))[:-1]


def signed_polygon_area(polygon: Iterable[Sequence[float]]) -> float:
    """Return signed shoelace area for vertices in boundary order.

CCW is positive and CW negative. Empty, point, and segment polygons have zero
area. A repeated closing vertex is allowed. Exact arithmetic is retained until
the returned float conversion; an unrepresentably large area returns signed
infinity and a sufficiently small area may underflow to zero.
"""
    vertices = [_exact(point) for point in _points(polygon)]
    if len(vertices) < 3:
        return 0.0
    origin = vertices[0]
    area = sum((_cross(origin, vertices[i], vertices[i + 1])
                for i in range(1, len(vertices) - 1)), Fraction(0)) / 2
    try:
        return float(area)
    except OverflowError:
        return math.inf if area > 0 else -math.inf


def polygon_area(polygon: Iterable[Sequence[float]]) -> float:
    """Return the absolute polygon area; see signed_polygon_area."""
    return abs(signed_polygon_area(polygon))


def closed_convex_polygons_intersect(
    a: Iterable[Sequence[float]], b: Iterable[Sequence[float]],
) -> bool:
    """Whether two nondegenerate closed convex polygons intersect.

Convex vertex sets are canonicalized with convex_hull, accepting either winding
and redundant or repeated vertices. A point or line hull raises ValueError.
An edge or corner contact is an intersection. Separation uses exact orientation
along every hull edge, without an epsilon or positive-overlap requirement.
"""
    hull_a, hull_b = convex_hull(a), convex_hull(b)
    if len(hull_a) < 3 or len(hull_b) < 3:
        raise ValueError("Intersection requires two nondegenerate convex polygons")
    exact_a = [_exact(point) for point in hull_a]
    exact_b = [_exact(point) for point in hull_b]

    def separated(first: list[ExactPoint], second: list[ExactPoint]) -> bool:
        for index, start in enumerate(first):
            end = first[(index + 1) % len(first)]
            if all(_cross(start, end, point) < 0 for point in second):
                return True
        return False

    return not separated(exact_a, exact_b) and not separated(exact_b, exact_a)
