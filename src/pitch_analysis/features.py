from __future__ import annotations
from .geometry import joint_angle, line_angle


def _point(
    frame: dict,
    name: str,
    visibility_threshold: float,
    presence_threshold: float,
    *,
    coordinate_x_scale: float = 1.0,
    require_raw: bool = False,
):
    value = frame.get(name)
    if not value or ("usable" in value and not value["usable"]):
        return None
    if require_raw and (
        value.get("source_frame_detected", True) is False
        or value.get("quality_valid", True) is False
        or value.get("interpolated", False) is True
    ):
        return None
    if "usable" not in value and (value.get("visibility", 0.0) < visibility_threshold or value.get("presence", 1.0) < presence_threshold):
        return None
    if "x" not in value or "y" not in value:
        return None
    return (float(value["x"]) * coordinate_x_scale, float(value["y"]))


def _angle(
    frame: dict,
    names: tuple[str, str, str],
    visibility_threshold: float,
    presence_threshold: float,
    *,
    coordinate_x_scale: float,
    require_raw: bool,
):
    points = [
        _point(frame, name, visibility_threshold, presence_threshold, coordinate_x_scale=coordinate_x_scale, require_raw=require_raw)
        for name in names
    ]
    return joint_angle(*points) if all(points) else None


def extract_frame_features(
    frame: dict,
    throwing_side: str,
    min_visibility: float,
    min_presence: float = 0.5,
    *,
    coordinate_x_scale: float = 1.0,
    require_raw: bool = False,
) -> dict[str, float | None]:
    """Return projection-only features in a width/height-corrected image plane.

    ``require_raw`` is used for quality accounting.  It rejects coordinates that
    were filled over short gaps, while the ordinary feature value may retain that
    bounded interpolation for diagnostics and smoothing.
    """
    if throwing_side not in {"LEFT", "RIGHT"}:
        raise ValueError("throwing_side must be LEFT or RIGHT")
    if coordinate_x_scale <= 0:
        raise ValueError("coordinate_x_scale must be positive")
    lead = "RIGHT" if throwing_side == "LEFT" else "LEFT"
    point_args = {"coordinate_x_scale": coordinate_x_scale, "require_raw": require_raw}
    shoulder = [_point(frame, f"{side}_SHOULDER", min_visibility, min_presence, **point_args) for side in ("LEFT", "RIGHT")]
    hip = [_point(frame, f"{side}_HIP", min_visibility, min_presence, **point_args) for side in ("LEFT", "RIGHT")]
    ankles = [_point(frame, f"{side}_ANKLE", min_visibility, min_presence, **point_args) for side in ("LEFT", "RIGHT")]
    return {
        "throwing_knee_angle": _angle(frame, tuple(f"{throwing_side}_{part}" for part in ("HIP", "KNEE", "ANKLE")), min_visibility, min_presence, **point_args),
        "lead_knee_angle": _angle(frame, tuple(f"{lead}_{part}" for part in ("HIP", "KNEE", "ANKLE")), min_visibility, min_presence, **point_args),
        "throwing_elbow_angle": _angle(frame, tuple(f"{throwing_side}_{part}" for part in ("SHOULDER", "ELBOW", "WRIST")), min_visibility, min_presence, **point_args),
        "shoulder_line_angle": line_angle(*shoulder) if all(shoulder) else None,
        "hip_line_angle": line_angle(*hip) if all(hip) else None,
        # Deliberately not called stride: rear-view x separation is not true stride length.
        "lateral_foot_separation": abs(ankles[0][0] - ankles[1][0]) if all(ankles) else None,
    }
