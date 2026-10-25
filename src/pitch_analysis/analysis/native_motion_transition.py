"""Describe model-XY endpoint differences between two manual events."""
from copy import deepcopy
from fractions import Fraction
from itertools import product


ROLES = ("throwing_elbow", "lead_knee")
START_EVENT = "foot_plant"
END_EVENT = "approximate_release"
CALCULATED = "calculated_from_model_xy"


def describe_event_transition(clip: dict) -> dict:
    """Retain every chronological endpoint pair without guessing either event.

    Inputs are the validated, saved curves and normalized human events from the
    existing event loader. Differences describe model projections, not anatomical
    motion or reliability. Missing and degenerate endpoint counts can overlap.
    """
    start, end = (clip["events"][name] for name in (START_EVENT, END_EVENT))
    result = {
        "start_event": START_EVENT, "end_event": END_EVENT,
        "status": "unavailable", "reason": "人工事件未確認；未取候選影格計算",
        "start_frame_bounds": deepcopy(start["frame_bounds"]),
        "end_frame_bounds": deepcopy(end["frame_bounds"]),
        "timing": deepcopy(clip["timing"]["foot_plant_to_release"]),
        "all_endpoint_pairs": None, "chronological_pairs": None,
        "excluded_nonchronological_pairs": None,
        "joints": {role: {
            "total_pairs": None, "calculated_pairs": None, "unavailable_pairs": None,
            "missing_endpoint_pairs": None, "degenerate_endpoint_pairs": None,
            "min_delta_deg": None, "max_delta_deg": None, "delta_direction": "unavailable",
            "pointwise_reliability": "unknown", "usable_for_analysis": None, "pairs": [],
        } for role in ROLES},
    }
    if any(event["status"] != "annotated" or event["frame_bounds"] is None for event in (start, end)):
        return result

    endpoints = list(product(range(start["frame_bounds"][0], start["frame_bounds"][1] + 1),
                             range(end["frame_bounds"][0], end["frame_bounds"][1] + 1)))
    ordered = [(first, last) for first, last in endpoints if first <= last]
    fps = Fraction(clip["fps_fraction"])
    result.update(status="descriptive_model_xy_transition",
                  reason="出手模型XY角減落地模型XY角；保留全部合法影格配對，未選中點",
                  all_endpoint_pairs=len(endpoints), chronological_pairs=len(ordered),
                  excluded_nonchronological_pairs=len(endpoints) - len(ordered))
    for role, joint in result["joints"].items():
        for first, last in ordered:
            rows = [clip["rows"][index] for index in (first, last)]
            states = [row[f"{role}_coordinate_status"] for row in rows]
            values = [row[f"{role}_model_xy_deg"] for row in rows]
            missing, degenerate = "missing_coordinates" in states, "degenerate_geometry" in states
            status = ("missing_and_degenerate" if missing and degenerate else
                      "missing_coordinates" if missing else "degenerate_geometry" if degenerate else CALCULATED)
            elapsed = Fraction(last - first) / fps
            joint["pairs"].append({
                "start_frame": first, "end_frame": last, "elapsed_frames": last - first,
                "elapsed_seconds": float(elapsed), "elapsed_seconds_fraction": str(elapsed),
                "start_model_xy_deg": values[0], "end_model_xy_deg": values[1],
                "start_coordinate_status": states[0], "end_coordinate_status": states[1],
                "delta_model_xy_deg": values[1] - values[0] if states == [CALCULATED, CALCULATED] else None,
                "status": status,
            })
        pairs = joint["pairs"]
        values = [pair["delta_model_xy_deg"] for pair in pairs if pair["status"] == CALCULATED]
        low, high = (min(values), max(values)) if values else (None, None)
        direction = ("unavailable" if not values else "positive" if low > 0 else
                     "negative" if high < 0 else "zero" if low == high == 0 else "includes_zero")
        joint.update(
            total_pairs=len(pairs), calculated_pairs=len(values), unavailable_pairs=len(pairs) - len(values),
            missing_endpoint_pairs=sum(pair["status"] in {"missing_coordinates", "missing_and_degenerate"} for pair in pairs),
            degenerate_endpoint_pairs=sum(pair["status"] in {"degenerate_geometry", "missing_and_degenerate"} for pair in pairs),
            min_delta_deg=low, max_delta_deg=high, delta_direction=direction,
        )
    return result
