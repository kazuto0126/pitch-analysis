"""Additional, source-bound review hints from the reviewed development cohort.

This module reads a packaged warning cache. It does not estimate poses, read
human annotations, change a gate, or infer that an unflagged frame is reliable.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re


BUNDLE_PATH = Path(__file__).with_name("review_evidence") / "major_review_development_v1.json"
BUNDLE_SHA256 = "0d14a463306c3936e881a8eb719a4fcf3640e2f7e097cec6223580e8b06e241e"
CAPTURE_SIGNATURE_KEYS = (
    "width", "height", "start_frame", "end_frame", "requested_frames",
    "processed_frames", "subject_selection", "selection_frames",
)
EVIDENCE_COMPONENTS = (
    "original_warning", "bbox_warning", "shoulder_hip_disagreement_warning",
)
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LIMITATIONS = [
    "These hints were developed on the five already-reviewed Yamamoto clips; this is development evidence, not an unseen-video accuracy claim.",
    "No review hint does not mean a frame, joint, or selected subject is reliable.",
    "Hints are additional review requests only; raw predictions, coordinates, gates, and established analysis judgments are unchanged.",
    "The packaged hints apply only to the exact source video, metadata identity, model, raw prediction, capture selection, and timeline recorded in the evidence.",
]


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("Capture signature is not finite JSON") from error


def capture_semantic_sha256(capture: dict) -> str:
    """Bind capture semantics while excluding environment-dependent file paths."""
    if not isinstance(capture, dict) or any(key not in capture for key in CAPTURE_SIGNATURE_KEYS):
        raise ValueError("Capture signature fields are incomplete")
    signature = {key: capture[key] for key in CAPTURE_SIGNATURE_KEYS}
    return hashlib.sha256(_canonical(signature)).hexdigest()


def _integer(value: object, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _sha(value: object) -> bool:
    return isinstance(value, str) and _HEX_SHA256.fullmatch(value) is not None


def _timeline(total: object, timestamps: object) -> bool:
    if not _integer(total, 1) or not isinstance(timestamps, list) or len(timestamps) != total:
        return False
    if not all(_finite(value) and value >= 0 for value in timestamps):
        return False
    return timestamps[0] == 0 and all(left < right for left, right in zip(timestamps, timestamps[1:]))


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence JSON key")
        result[key] = value
    return result


def _validate_bundle(bundle: object) -> dict:
    if not isinstance(bundle, dict) or bundle.get("schema_version") != "major-review-development-evidence-v1":
        raise ValueError("Unsupported review evidence schema")
    if bundle.get("status") != "sealed_development_evidence":
        raise ValueError("Review evidence is not sealed")
    scope, clips = bundle.get("development_scope"), bundle.get("clips")
    if not isinstance(scope, dict) or not isinstance(clips, list) or not clips:
        raise ValueError("Review evidence has no development cohort")
    if scope.get("clip_count") != len(clips) or type(scope.get("clip_count")) is not int:
        raise ValueError("Development clip count differs from evidence")
    if not isinstance(scope.get("dataset"), str) or not scope["dataset"]:
        raise ValueError("Development dataset must be named")
    for key in ("major_tp", "major_fn", "major_fp"):
        if not _integer(scope.get(key)):
            raise ValueError("Invalid development confusion counts")
    for key in ("source_frames", "evaluation_non_seed_frames", "major_tn"):
        if key in scope and not _integer(scope[key]):
            raise ValueError("Invalid development summary count")
    refs = bundle.get("source_evidence")
    if not isinstance(refs, list) or not refs:
        raise ValueError("Missing warning evidence provenance")
    ref_ids = set()
    for ref in refs:
        if (not isinstance(ref, dict) or not isinstance(ref.get("id"), str) or not ref["id"]
                or ref["id"] in ref_ids or not isinstance(ref.get("path"), str) or not ref["path"]
                or not _sha(ref.get("sha256"))):
            raise ValueError("Invalid warning evidence provenance")
        ref_ids.add(ref["id"])
    seen = set()
    frame_counts = {}
    for clip in clips:
        if not isinstance(clip, dict):
            raise ValueError("Invalid clip evidence")
        identity_key = (clip.get("pitcher_id"), clip.get("pitch_id"))
        if any(not isinstance(value, str) or not value for value in identity_key) or identity_key in seen:
            raise ValueError("Duplicate or missing clip identity")
        seen.add(identity_key)
        identity, source = clip.get("identity"), clip.get("source")
        if not isinstance(identity, dict) or not isinstance(source, dict):
            raise ValueError("Missing clip source binding")
        if (identity.get("throws") not in {"RIGHT", "LEFT"}
                or identity.get("camera_view") != "rear_centerfield_broadcast"
                or identity.get("horizontal_mirror") is not False
                or not _finite(identity.get("playback_speed")) or identity["playback_speed"] != 1
                or identity.get("contains_single_pitch") is not True):
            raise ValueError("Unsupported development video identity")
        for key in ("video_sha256", "raw_csv_sha256", "capture_semantic_sha256", "model_sha256"):
            if not _sha(source.get(key)):
                raise ValueError("Invalid clip source SHA256")
        total, frames = clip.get("frame_count"), clip.get("frames")
        if not _integer(total, 1) or not isinstance(frames, list) or len(frames) != total:
            raise ValueError("Incomplete warning timeline")
        timestamps = []
        for index, frame in enumerate(frames):
            if not isinstance(frame, dict) or type(frame.get("frame_index")) is not int or frame["frame_index"] != index:
                raise ValueError("Warning frames are not consecutive")
            timestamps.append(frame.get("timestamp_ms"))
            required, reasons, components = frame.get("review_required"), frame.get("reasons"), frame.get("evidence_state")
            if type(required) is not bool or not isinstance(components, dict) or set(components) != set(EVIDENCE_COMPONENTS):
                raise ValueError("Invalid review warning components")
            if not all(type(components[key]) is bool for key in EVIDENCE_COMPONENTS) or required != any(components.values()):
                raise ValueError("Warning differs from frozen component union")
            if (not isinstance(reasons, list) or any(not isinstance(reason, str) or not reason for reason in reasons)
                    or len(reasons) != len(set(reasons)) or bool(reasons) != required):
                raise ValueError("Review warning reasons do not match the warning")
            if "diagnostics" in frame:
                _validate_diagnostics(frame["diagnostics"])
        if not _timeline(total, timestamps):
            raise ValueError("Invalid warning timestamps")
        frame_counts[clip["pitch_id"]] = total
    misses = scope.get("known_misses")
    if not isinstance(misses, list):
        raise ValueError("Missing known development misses")
    for miss in misses:
        if (not isinstance(miss, dict) or miss.get("pitch_id") not in frame_counts
                or not _integer(miss.get("frame_index")) or miss["frame_index"] >= frame_counts[miss["pitch_id"]]):
            raise ValueError("Invalid known development miss")
    if "source_frames" in scope and scope["source_frames"] != sum(clip["frame_count"] for clip in clips):
        raise ValueError("Development source frame count differs")
    if "evaluation_non_seed_frames" in scope and scope["evaluation_non_seed_frames"] != sum(clip["frame_count"] - 1 for clip in clips):
        raise ValueError("Development nonseed frame count differs")
    return bundle


def _validate_diagnostics(value: object) -> None:
    """Diagnostic states retain missing/ambiguous evidence, never correctness."""
    if not isinstance(value, dict) or not set(value) <= {
        "bbox_state", "disagreement_state", "candidate_slot_indices", "association_status",
    }:
        raise ValueError("Invalid warning diagnostics")
    # These labels describe evidence availability/association, not reliable joints.
    states = {
        "bbox_state": {"insufficient_evidence", "no_warning", "warning"},
        "disagreement_state": {"candidate_dependent", "insufficient_evidence", "seed_excluded", "warning", "within_reference_range"},
        "association_status": {"ambiguous", "none", "unique_geometric_candidate"},
    }
    for key, allowed in states.items():
        if key in value and value[key] not in allowed:
            raise ValueError("Unsupported warning diagnostic state")
    if "candidate_slot_indices" in value:
        slots = value["candidate_slot_indices"]
        if slots is not None and (not isinstance(slots, list) or any(not _integer(slot) for slot in slots)):
            raise ValueError("Invalid candidate slot indices")


def _load_bundle() -> dict:
    data = BUNDLE_PATH.read_bytes()
    if not _sha(BUNDLE_SHA256) or hashlib.sha256(data).hexdigest() != BUNDLE_SHA256:
        raise ValueError("Packaged review evidence SHA256 mismatch")
    bundle = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite review evidence")))
    return _validate_bundle(bundle)


def _capture_timeline_valid(capture: dict, video: dict) -> bool:
    total, timestamps = video.get("frame_count"), video.get("timestamps_ms")
    if not _timeline(total, timestamps) or not isinstance(capture, dict):
        return False
    for key in ("width", "height"):
        if not _integer(video.get(key), 1) or type(capture.get(key)) is not int or capture[key] != video[key]:
            return False
    expected = {"start_frame": 0, "end_frame": total - 1, "requested_frames": total, "processed_frames": total}
    if any(type(capture.get(key)) is not int or capture[key] != value for key, value in expected.items()):
        return False
    if capture.get("subject_selection") != "rear_centerfield_broadcast":
        return False
    frames = capture.get("selection_frames")
    if not isinstance(frames, list) or len(frames) != total:
        return False
    return all(isinstance(frame, dict) and type(frame.get("frame_index")) is int
               and frame["frame_index"] == index and _finite(frame.get("timestamp_ms"))
               and abs(frame["timestamp_ms"] - timestamps[index]) <= .500001
               for index, frame in enumerate(frames))


def _identity_matches(clip: dict, metadata: dict) -> bool:
    if not isinstance(metadata, dict) or metadata.get("schema_version") != "pitch-input-v1":
        return False
    pitcher, video = metadata.get("pitcher"), metadata.get("video")
    if not isinstance(pitcher, dict) or not isinstance(video, dict):
        return False
    identity = clip["identity"]
    return (metadata.get("pitch_id") == clip["pitch_id"] and pitcher.get("id") == clip["pitcher_id"]
            and pitcher.get("throws") == identity["throws"]
            and video.get("camera_view") == identity["camera_view"]
            and type(video.get("horizontal_mirror")) is bool
            and video["horizontal_mirror"] == identity["horizontal_mirror"]
            and _finite(video.get("playback_speed")) and video["playback_speed"] == identity["playback_speed"]
            and type(video.get("contains_single_pitch")) is bool
            and video["contains_single_pitch"] == identity["contains_single_pitch"])


def write_major_review_hints(analysis_dir: Path, *, input_metadata: dict,
                             video_metadata: dict, capture: dict, model_sha256: str) -> Path:
    """Write one exclusive additional sidecar; unfamiliar predictions remain unknown.

    A missing, altered, or malformed evidence bundle produces an explicit
    ``evidence_unavailable`` sidecar, so packaging cannot change core success.
    The existing sidecar is never overwritten; that is an output collision.
    """
    directory = Path(analysis_dir).resolve(strict=True)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    output = directory / "major_review_hints.json"
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Major review hints already exist: {output}")
    video = video_metadata if isinstance(video_metadata, dict) else {}
    metadata = input_metadata if isinstance(input_metadata, dict) else {}
    status, reasons, bundle, selected = "not_evaluated", [], None, None
    raw_digest = capture_digest = None
    raw_path = directory / "pose_raw.csv"
    try:
        # A symlink to a different artifact must not accidentally bind that file.
        if raw_path.resolve(strict=True) != raw_path or not raw_path.is_file():
            reasons.append("raw_prediction_outside_analysis_directory")
        else:
            raw_digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    except OSError:
        reasons.append("raw_prediction_unavailable")
    try:
        capture_digest = capture_semantic_sha256(capture)
    except ValueError:
        reasons.append("capture_signature_unavailable")
    if not _capture_timeline_valid(capture, video):
        reasons.append("capture_or_video_timeline_mismatch")
    try:
        bundle = _load_bundle()
    except (OSError, ValueError, UnicodeError, TypeError, KeyError) as error:
        status = "evidence_unavailable"
        reasons.append(f"packaged_evidence_unavailable:{type(error).__name__}")
    if bundle is not None:
        identity_clips = [clip for clip in bundle["clips"] if _identity_matches(clip, metadata)]
        if not identity_clips:
            reasons.append("input_identity_not_in_development_evidence")
        else:
            clip = identity_clips[0]
            actual = {"video_sha256": video.get("sha256"), "raw_csv_sha256": raw_digest,
                      "capture_semantic_sha256": capture_digest, "model_sha256": model_sha256}
            for key, value in actual.items():
                if not _sha(value) or value != clip["source"][key]:
                    reasons.append(f"source_mismatch:{key}")
            timestamps = video.get("timestamps_ms")
            if (not _timeline(video.get("frame_count"), timestamps)
                    or video["frame_count"] != clip["frame_count"]
                    or any(abs(frame["timestamp_ms"] - timestamps[index]) > 1e-6
                           for index, frame in enumerate(clip["frames"]))):
                reasons.append("source_mismatch:warning_timeline")
            if not reasons:
                status, selected = "evaluated_development_evidence", clip
    frames = deepcopy(selected["frames"]) if selected is not None else [
        {"frame_index": index, "timestamp_ms": timestamp, "review_required": None,
         "reasons": [], "evidence_state": {key: None for key in EVIDENCE_COMPONENTS}}
        for index, timestamp in enumerate(video.get("timestamps_ms", []))
    ] if _timeline(video.get("frame_count"), video.get("timestamps_ms")) else []
    scope = deepcopy(bundle["development_scope"]) if bundle else None
    payload = {
        "schema_version": "major-review-hints-v1", "status": status,
        "pitch_id": metadata.get("pitch_id"),
        "pitcher_id": metadata.get("pitcher", {}).get("id") if isinstance(metadata.get("pitcher"), dict) else None,
        "purpose": "additional_requires_human_review_hint",
        "review_required_semantics": "true = frozen warning present; false = no frozen warning, not reliable; null = not evaluated",
        "reason_codes": reasons, "development_scope": scope,
        "source_binding": {"video_sha256": video.get("sha256"), "raw_csv_sha256": raw_digest,
                           "capture_semantic_sha256": capture_digest, "model_sha256": model_sha256},
        "packaged_evidence": {"sha256": BUNDLE_SHA256, "source_evidence": deepcopy(bundle["source_evidence"]) if bundle else []},
        "limitations": _LIMITATIONS, "frame_count": video.get("frame_count"),
        "review_required_frames": sum(frame["review_required"] is True for frame in frames) if selected is not None else None,
        "frames": frames,
    }
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return output
