"""Source-bound inputs for consumers of accepted native skeletons.

This adapter reads saved output only.  It does not estimate, smooth, interpolate,
classify joint quality, or translate native scores to MediaPipe visibility.
Whole-clip visual acceptance and pointwise reliability are separate facts.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fractions import Fraction
import math
from pathlib import Path
from typing import Iterator

from ..contracts import load_input
from ..native_pose import NativePoseFrame
from ..native_pose_io import BoundReader, _loads, read_dataset, read_json, reference, write_json
from ..native_pose_review import summarize_native
from ..native_seeded_track import TRACK_POLICY


SCHEMA_VERSION = "native-analysis-input-v1"
MANIFEST_NAME = "native_analysis_input.json"
SUMMARY_NAME = "usage_summary.json"
_LINKED = {"seeded", "linked"}
_BREAKS = {"track_break_no_overlap", "track_break_tie", "track_break_non_mutual"}
_SEMANTICS = {
    "human_review_scope": "whole_clip_qualitative_acceptance",
    "model_coordinate_state": "preserved_from_raw_native_prediction",
    "joint_reliability": "unknown",
    "joint_human_visibility": "unknown",
    "joint_usable_for_analysis": None,
    "native_score_is_visibility": False,
    "native_score_is_calibrated_accuracy": False,
    "quality_gate_applied": False,
    "coordinates_copied_or_changed": False,
    "source_admission_changed": False,
    "unsupported_fields": ["presence", "visibility", "z"],
}


def _path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve(strict=True)


def _rows(path: Path) -> list[dict]:
    result = []
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip():
                raise ValueError("Blank tracking row is not permitted")
            item = _loads(line)
            if not isinstance(item, dict):
                raise ValueError("Tracking rows must be JSON objects")
            result.append(item)
    return result


def _utc(value: object) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() != timedelta(0):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Human review requires a recorded UTC timestamp") from None
    return value


def _review(review: dict, refs: dict, manifest: dict, metadata: dict) -> dict:
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Human review requires a named reviewer")
    recorded = _utc(review.get("recorded_at_utc"))
    schema = review.get("schema_version")
    if schema == "skeleton-overlay-review-v1":
        clips = review.get("clips")
        if not isinstance(clips, list):
            raise ValueError("Grouped human review requires clip records")
        matches = [item for item in clips if isinstance(item, dict)
                   and item.get("pitch_id") == manifest["pitch_id"]]
        if len(matches) != 1:
            raise ValueError("Human review must contain exactly one matching pitch")
        entry = matches[0]
        if (entry.get("human_overlay_review") != f"accepted_by_{reviewer}"
                or entry.get("overall_joint_alignment_review") != f"accepted_by_{reviewer}"
                or entry.get("frame_count") != manifest["video"]["frame_count"]):
            raise ValueError("Human review has not accepted this complete overlay")
    elif schema == "skeleton-method-adoption-v1":
        entry = review
        if (entry.get("source_pitch_id") != manifest["pitch_id"]
                or entry.get("source_pitcher_id") != metadata["pitcher"]["id"]
                or entry.get("subject_identity_review") != f"confirmed_pitcher_throughout_by_{reviewer}"
                or entry.get("overall_joint_alignment_review") != f"accepted_by_{reviewer}"
                or entry.get("adoption_decision") != "ADOPT_METHOD_AS_SHARED_SKELETON_STANDARD"):
            raise ValueError("Human adoption review does not accept this pitcher and overlay")
    else:
        raise ValueError("Unsupported human overlay review schema")
    for key in ("video_ref", "native_manifest_ref", "native_keypoints_ref", "overlay_ref"):
        if entry.get(key) != refs[key]:
            raise ValueError(f"Human review {key} differs from the selected native output")
    scope, method = review.get("judgment_scope"), review.get("review_method")
    if any(not isinstance(value, str) or not value.strip() for value in (scope, method)):
        raise ValueError("Human review must preserve its method and judgment scope")
    return {
        "status": "human_accepted", "scope": "whole_clip_qualitative_acceptance",
        "reviewer": reviewer, "recorded_at_utc": recorded,
        "source_schema": schema, "review_method": method, "source_judgment_scope": scope,
        "review_ref": refs["review_ref"],
        "candidate_status_from_review": entry.get("candidate_status"),
        "pointwise_reliability_established": False,
        "pointwise_visibility_established": False,
    }


def _validate_pairing(manifest: dict, frames: list[NativePoseFrame], tracks: list[dict]) -> None:
    if len(tracks) != len(frames):
        raise ValueError("Tracking must preserve the complete native frame count")
    fps = Fraction(manifest["timebase"]["fps_fraction"])
    broken_at = None
    for index, (frame, track) in enumerate(zip(frames, tracks, strict=True)):
        value = frame.to_dict()
        expected_time = float(Fraction(index * 1000) / fps)
        if (track.get("frame_index") != index or isinstance(track.get("frame_index"), bool)
                or track.get("timestamp_ms") != expected_time
                or value["timestamp_ms"] != expected_time
                or track.get("decoded_bgr_sha256") != value["decoded_bgr_sha256"]):
            raise ValueError(f"Tracking/native frame, pixel or rational timeline pairing differs at {index}")
        selection = value["model_selection"]
        selected = selection.get("person_box_selection")
        expected = {key: track.get(key) for key in
                    ("status", "eligible_count", "selected_output_index", "selected_bbox_xyxy_px")}
        if (selected != expected or selection.get("track_policy") != TRACK_POLICY
                or track.get("track_policy") != TRACK_POLICY):
            raise ValueError(f"Tracking/native selected box mapping differs at {index}")
        status = track.get("status")
        if index == 0 and status != "seeded":
            raise ValueError("Tracking must begin with the operator-selected seed")
        if broken_at is None:
            if index and status in _BREAKS:
                broken_at = index
            elif index and status != "linked":
                raise ValueError("Tracking contains an unsupported state before a terminal break")
        elif status != "after_track_break":
            raise ValueError("A terminal tracking break cannot reacquire a subject")
        if track.get("break_frame_index") != broken_at:
            raise ValueError("Tracking break origin is inconsistent")
        output_index, box = track.get("selected_output_index"), track.get("selected_bbox_xyxy_px")
        count = track.get("eligible_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("Tracking eligible count must be a nonnegative integer")
        if status in _LINKED:
            if (not isinstance(output_index, int) or isinstance(output_index, bool) or output_index < 0
                    or not isinstance(box, list) or len(box) != 4
                    or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in box)
                    or box[2] <= box[0] or box[3] <= box[1]
                    or output_index not in track.get("current_eligible_output_indices", [])):
                raise ValueError("A selected subject requires an eligible positive-area box")
        elif (output_index is not None or box is not None
              or value["input_geometry"]["input_mode"] != "not_run"
              or selection.get("pose_not_run") is not True
              or selection.get("pose_not_run_reason") != status):
            raise ValueError("A tracking break must retain explicit missing native pose")


def _validated_sources(root: Path, refs: dict) -> tuple[dict, dict, dict, list[NativePoseFrame], list[dict]]:
    required = {"native_manifest_ref", "native_keypoints_ref", "metadata_ref", "track_ref", "review_ref",
                "video_ref", "overlay_ref"}
    if set(refs) != required:
        raise ValueError("Analysis input requires its exact declared source references")
    reader = BoundReader(root, refs.values())
    paths = {key: reader.path(value) for key, value in refs.items()}
    native_dir = paths["native_manifest_ref"].parent
    if (paths["native_manifest_ref"].name != "native_pose_manifest.json"
            or paths["native_keypoints_ref"] != native_dir / "native_keypoints.jsonl"
            or paths["overlay_ref"] != native_dir / "overlay_native.mp4"):
        raise ValueError("Native manifest, keypoints and reviewed overlay must form one dataset")
    manifest, frames = read_dataset(native_dir)
    if (manifest["topology"] != "coco_17" or manifest["inference_mode"] != "live_stateless_roi"
            or "rtmpose" not in manifest["backend"]["name"].lower()
            or manifest["roi_provenance"].get("track_policy") != TRACK_POLICY):
        raise ValueError("Analysis adapter requires an operator-seeded RTMPose native17 source")
    BoundReader(root, manifest["source_refs"])
    declared = manifest["source_refs"]
    if refs["video_ref"] != {key: manifest["video"][key] for key in ("path", "sha256")}:
        raise ValueError("Native source video identity differs")
    for key in ("video_ref", "metadata_ref", "track_ref"):
        if refs[key] not in declared:
            raise ValueError(f"The native manifest does not bind this {key}")
    metadata = load_input(paths["video_ref"], paths["metadata_ref"])
    if metadata["pitch_id"] != manifest["pitch_id"]:
        raise ValueError("Metadata pitch identity differs from native output")
    if metadata["video"]["camera_view"] != "rear_centerfield_broadcast":
        raise ValueError("The shared native workflow requires rear_centerfield_broadcast metadata")
    tracks = _rows(paths["track_ref"])
    _validate_pairing(manifest, frames, tracks)
    review = _review(read_json(paths["review_ref"]), refs, manifest, metadata)
    # Check the consumed bytes once more after parsing; never read models or workers.
    for ref in refs.values():
        reader.path(ref)
    return manifest, metadata, review, frames, tracks


def _summary(manifest: dict, review: dict, frames: list[NativePoseFrame], tracks: list[dict]) -> dict:
    descriptive = summarize_native(manifest, frames)
    values = [frame.to_dict() for frame in frames]
    return {
        "schema_version": "native-analysis-usage-summary-v1", "pitch_id": manifest["pitch_id"],
        "total_frames": len(frames), "paired_tracking_frames": len(tracks),
        "retained_native_landmark_slots": len(frames) * 17,
        "track_status_counts": dict(Counter(track["status"] for track in tracks)),
        "first_track_break_frame": next((track["frame_index"] for track in tracks
                                         if track["status"] in _BREAKS), None),
        "pose_not_run_frames": [value["frame_index"] for value in values
                                if value["input_geometry"]["input_mode"] == "not_run"],
        "human_overlay_review": review, "data_semantics": deepcopy(_SEMANTICS),
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "joint_reliability_unknown_slots": len(frames) * 17,
        "joint_visibility_unknown_slots": len(frames) * 17,
        "native_coordinate_summary": descriptive,
        "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
    }


def _envelope(refs: dict, manifest: dict, metadata: dict, review: dict, summary_ref: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION, "status": "ready_for_native_consumption",
        "pitch_id": manifest["pitch_id"], "pitcher_id": metadata["pitcher"]["id"],
        "topology": manifest["topology"], "image_size": manifest["image_size"],
        "frame_count": manifest["video"]["frame_count"], "timebase": manifest["timebase"],
        "source_refs": refs, "usage_summary_ref": summary_ref,
        "human_overlay_review": review, "data_semantics": deepcopy(_SEMANTICS),
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
    }


def prepare_native_analysis_input(root: str | Path, native_dir: str | Path,
                                  metadata_path: str | Path, track_path: str | Path,
                                  review_path: str | Path, output: str | Path) -> dict:
    """Validate accepted saved sources and write a fresh reference-only bundle."""
    root = Path(root).resolve(strict=True)
    native_dir = _path(root, native_dir)
    source = read_json(native_dir / "native_pose_manifest.json")
    refs = {
        "native_manifest_ref": reference(root, native_dir / "native_pose_manifest.json"),
        "native_keypoints_ref": reference(root, native_dir / "native_keypoints.jsonl"),
        "metadata_ref": reference(root, _path(root, metadata_path)),
        "track_ref": reference(root, _path(root, track_path)),
        "review_ref": reference(root, _path(root, review_path)),
        "video_ref": {key: source["video"][key] for key in ("path", "sha256")},
        "overlay_ref": reference(root, native_dir / "overlay_native.mp4"),
    }
    manifest, metadata, review, frames, tracks = _validated_sources(root, refs)
    summary = _summary(manifest, review, frames, tracks)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if not output.is_relative_to(root / "analysis_results"):
        raise ValueError("New analysis-input output must be inside this project's analysis_results")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / SUMMARY_NAME, summary)
    envelope = _envelope(refs, manifest, metadata, review, reference(root, output / SUMMARY_NAME))
    write_json(output / MANIFEST_NAME, envelope)
    return deepcopy(envelope)


@dataclass(frozen=True, init=False)
class NativeAnalysisFrame:
    """An isolated raw frame snapshot plus its unchanged tracking evidence."""

    _native: NativePoseFrame = field(repr=False)
    _tracking: dict = field(repr=False)

    def __init__(self, native: NativePoseFrame, tracking: dict) -> None:
        object.__setattr__(self, "_native", NativePoseFrame(native.to_dict()))
        object.__setattr__(self, "_tracking", deepcopy(tracking))

    @property
    def native(self) -> NativePoseFrame:
        return NativePoseFrame(self._native.to_dict())

    @property
    def frame_index(self) -> int:
        return self._native.to_dict()["frame_index"]

    @property
    def tracking(self) -> dict:
        return deepcopy(self._tracking)

    @property
    def joint_assessments(self) -> dict:
        return {point["name"]: {
            "coordinate_state": point["coordinate_state"],
            "reliability": "unknown", "human_visibility": "unknown", "usable_for_analysis": None,
        } for point in self._native.to_dict()["landmarks"]}


@dataclass(frozen=True, init=False)
class NativeAnalysisInput:
    """Read-only consumer snapshot; exported dictionaries never mutate it."""

    _manifest: dict = field(repr=False)
    _metadata: dict = field(repr=False)
    _usage_summary: dict = field(repr=False)
    _frames: tuple[NativeAnalysisFrame, ...] = field(repr=False)

    def __init__(self, manifest: dict, metadata: dict, summary: dict,
                 frames: list[NativePoseFrame], tracks: list[dict]) -> None:
        object.__setattr__(self, "_manifest", deepcopy(manifest))
        object.__setattr__(self, "_metadata", deepcopy(metadata))
        object.__setattr__(self, "_usage_summary", deepcopy(summary))
        object.__setattr__(self, "_frames", tuple(NativeAnalysisFrame(frame, track)
                                                 for frame, track in zip(frames, tracks, strict=True)))

    @property
    def manifest(self) -> dict:
        return deepcopy(self._manifest)

    @property
    def metadata(self) -> dict:
        return deepcopy(self._metadata)

    @property
    def review(self) -> dict:
        return deepcopy(self._manifest["human_overlay_review"])

    @property
    def usage_summary(self) -> dict:
        return deepcopy(self._usage_summary)

    def __len__(self) -> int:
        return len(self._frames)

    def read_frame(self, index: int) -> NativeAnalysisFrame:
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(self):
            raise IndexError("Native analysis frame index is outside the complete timeline")
        item = self._frames[index]
        return NativeAnalysisFrame(item.native, item.tracking)

    def iter_frames(self) -> Iterator[NativeAnalysisFrame]:
        for index in range(len(self)):
            yield self.read_frame(index)


def load_native_analysis_input(root: str | Path, bundle_dir: str | Path) -> NativeAnalysisInput:
    """Revalidate every consumed source and return exact saved native frames."""
    root = Path(root).resolve(strict=True)
    bundle_dir = _path(root, bundle_dir)
    envelope = read_json(bundle_dir / MANIFEST_NAME)
    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported native analysis-input schema")
    refs = envelope.get("source_refs")
    if not isinstance(refs, dict):
        raise ValueError("Missing analysis-input source references")
    manifest, metadata, review, frames, tracks = _validated_sources(root, refs)
    summary_ref = envelope.get("usage_summary_ref")
    reader = BoundReader(root, [summary_ref])
    summary_path = reader.path(summary_ref)
    if summary_path != bundle_dir / SUMMARY_NAME:
        raise ValueError("Usage summary must be the source-bound sibling of this bundle")
    summary = _summary(manifest, review, frames, tracks)
    if reader.json(summary_ref) != summary:
        raise ValueError("Usage summary differs from the consumed native sources")
    if envelope != _envelope(refs, manifest, metadata, review, summary_ref):
        raise ValueError("Analysis-input semantics or source facts differ from saved evidence")
    return NativeAnalysisInput(envelope, metadata, summary, frames, tracks)
