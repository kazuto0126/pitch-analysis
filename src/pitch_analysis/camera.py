"""Camera compatibility checks for broadcast pitching references."""
from __future__ import annotations

from collections.abc import Mapping


FULL_BODY_VALUES = {"full_body", "full_delivery", "pitcher_full_body"}


def camera_context(payload: Mapping | None) -> dict:
    """Return the fields that matter for rear-view 2-D comparisons."""
    payload = payload or {}
    return {
        "view": payload.get("view", "unknown"),
        "horizontal_mirror": payload.get("horizontal_mirror"),
        "subject_framing": payload.get("subject_framing", "unknown"),
    }


def compare_camera_contexts(query: Mapping | None, reference: Mapping | None, *, mode: str = "exploratory") -> dict:
    """Check whether a query and reference can be compared under a camera policy.

    ``strict`` is intended for production-like rankings and requires explicit
    mirror/framing metadata. ``exploratory`` keeps older reviewed references
    usable, but records warnings so the output does not overclaim precision.
    """
    if mode not in {"strict", "exploratory"}:
        raise ValueError(f"unknown camera compatibility mode: {mode}")

    query_context = camera_context(query)
    reference_context = camera_context(reference)
    reasons: list[str] = []
    warnings: list[str] = []

    if query_context["view"] == "unknown" or reference_context["view"] == "unknown":
        message = "camera_view_missing"
        if mode == "strict":
            reasons.append(message)
        else:
            warnings.append(message)
    elif query_context["view"] != reference_context["view"]:
        reasons.append("camera_view_mismatch")

    query_mirror = query_context["horizontal_mirror"]
    reference_mirror = reference_context["horizontal_mirror"]
    if not isinstance(query_mirror, bool) or not isinstance(reference_mirror, bool):
        message = "horizontal_mirror_unknown"
        if mode == "strict":
            reasons.append(message)
        else:
            warnings.append(message)
    elif query_mirror != reference_mirror:
        reasons.append("horizontal_mirror_mismatch")

    query_framing = query_context["subject_framing"]
    reference_framing = reference_context["subject_framing"]
    if query_framing not in FULL_BODY_VALUES or reference_framing not in FULL_BODY_VALUES:
        message = "subject_framing_not_confirmed_full_body"
        if mode == "strict":
            reasons.append(message)
        else:
            warnings.append(message)

    return {
        "compatible": not reasons,
        "mode": mode,
        "query_context": query_context,
        "reference_context": reference_context,
        "reasons": reasons,
        "warnings": warnings,
    }
