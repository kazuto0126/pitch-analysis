"""Describe saved model XY projections without establishing joint usability.

These angles belong to the model's two-dimensional image projection.  Human
acceptance of the overlay does not supply pointwise reliability or visibility.
No estimator, event detector, score gate, interpolation or smoothing runs here.
"""
from __future__ import annotations

from fractions import Fraction

from ..geometry import joint_angle
from .native_input import NativeAnalysisInput


def _projected_angle(points: dict, names: list[str]) -> tuple[float | None, str]:
    selected = [points[name] for name in names]
    if any(point["coordinate_state"] != "model_observed"
           or point["x_px"] is None or point["y_px"] is None for point in selected):
        return None, "missing_coordinates"
    # Original image pixels preserve the aspect ratio of non-square images.
    # Native model scores, visibility and presence never enter this calculation.
    angle = joint_angle(*[(point["x_px"], point["y_px"]) for point in selected])
    if angle is None:
        return None, "degenerate_geometry"
    return angle, "calculated_from_model_xy"


def describe_native_motion(pitch: NativeAnalysisInput) -> tuple[dict, list[dict]]:
    """Return a full source-time description of throwing elbow and lead knee.

    Calculated values are descriptive model projections only.  The corresponding
    usable angles remain null even where all three model coordinates exist.
    """
    if not isinstance(pitch, NativeAnalysisInput):
        raise TypeError("Motion description requires a validated NativeAnalysisInput")
    metadata, manifest = pitch.metadata, pitch.manifest
    throws = metadata["pitcher"]["throws"]
    if throws not in ("RIGHT", "LEFT"):
        raise ValueError("Motion roles require explicit LEFT or RIGHT throwing hand")
    lead = "LEFT" if throws == "RIGHT" else "RIGHT"
    roles = {
        "throwing_elbow": [f"{throws}_{joint}" for joint in ("SHOULDER", "ELBOW", "WRIST")],
        "lead_knee": [f"{lead}_{joint}" for joint in ("HIP", "KNEE", "ANKLE")],
    }
    fps = Fraction(manifest["timebase"]["fps_fraction"])
    curves = {name: {"total_frames": len(pitch), "calculated": 0, "missing": 0, "degenerate": 0}
              for name in roles}
    count_key = {"calculated_from_model_xy": "calculated", "missing_coordinates": "missing",
                 "degenerate_geometry": "degenerate"}
    rows = []
    for index, frame in enumerate(pitch.iter_frames()):
        native = frame.native.to_dict()
        if native["frame_index"] != index:
            raise ValueError("Motion description requires a complete ordered zero-based timeline")
        points = {point["name"]: point for point in native["landmarks"]}
        row = {"frame_index": index, "timestamp_sec": float(Fraction(index) / fps),
               "pointwise_reliability": "unknown"}
        for role, names in roles.items():
            angle, status = _projected_angle(points, names)
            row[f"{role}_model_xy_deg"] = angle
            row[f"{role}_coordinate_status"] = status
            row[f"{role}_usable_deg"] = None
            curves[role][count_key[status]] += 1
        rows.append(row)
    if len(rows) != manifest["frame_count"] or len(rows) != len(pitch):
        raise ValueError("Motion description must retain every source frame")
    summary = {
        "schema_version": "native-motion-description-v1",
        "scope": "descriptive_model_xy_projection",
        "pitch_id": manifest["pitch_id"], "pitcher_id": metadata["pitcher"]["id"],
        "throws": throws, "coordinate_space": "original_image_pixels_xy",
        "timebase": {"frame_index_base": 0, "fps_fraction": manifest["timebase"]["fps_fraction"],
                     "timestamp_semantics": "frame_index / fractional_fps; zero origin",
                     "timestamp_unit": "seconds"},
        "total_frames": len(rows), "role_joints": roles, "curves": curves,
        "human_overlay_review": pitch.review,
        "pointwise_reliability": "unknown", "quality_status": "not_calibrated",
        "usable_for_analysis": None, "new_inference_calls": 0,
        "interpolated_angles": 0, "smoothed_angles": 0,
        "notes": [
            "Model XY projections are not true 3D joint angles or clinical measurements.",
            "Whole-clip acceptance does not establish per-frame joint reliability or visibility.",
            "Missing coordinates and degenerate limbs remain null; no events or timing normalization are inferred.",
        ],
    }
    return summary, rows
