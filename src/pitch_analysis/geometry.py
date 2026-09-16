"""Small, tested geometry functions.  Coordinates are normalized image x/y."""
from __future__ import annotations
import math
from typing import Sequence


Point = Sequence[float]


def joint_angle(a: Point, b: Point, c: Point) -> float | None:
    """Return the projected A-B-C angle in degrees, or None for a degenerate limb."""
    bax, bay = a[0] - b[0], a[1] - b[1]
    bcx, bcy = c[0] - b[0], c[1] - b[1]
    length_a, length_c = math.hypot(bax, bay), math.hypot(bcx, bcy)
    if not length_a or not length_c:
        return None
    cosine = max(-1.0, min(1.0, (bax * bcx + bay * bcy) / (length_a * length_c)))
    return math.degrees(math.acos(cosine))


def line_angle(a: Point, b: Point) -> float | None:
    """Return a line orientation in [-90, 90), avoiding the 180-degree wrap."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if not dx and not dy:
        return None
    angle = math.degrees(math.atan2(dy, dx))
    return ((angle + 90.0) % 180.0) - 90.0

