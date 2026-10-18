"""Read sealed native predictions without running a pose or tracking backend.

This adapter deliberately does not open canonical annotations, warning results,
or classifier outputs. It converts representation, never prediction quality.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import math
from pathlib import Path
from typing import Any

from .native_pose import CAPABILITIES, TOPOLOGIES, NativePoseFrame, validate_manifest
from .native_pose_io import BoundReader, reference


class CachedNativePoseSource:
    """An immutable in-memory view of one source-bound cached sequence."""

    def __init__(self, manifest: dict, frames: list[dict], read_paths: list[str]):
        validate_manifest(manifest)
        if len(frames) != manifest["video"]["frame_count"]:
            raise ValueError("Native source frame denominator differs")
        self._manifest = deepcopy(manifest)
        self._frames = tuple(NativePoseFrame(frame) for frame in frames)
        self.read_paths = tuple(dict.fromkeys(read_paths))

    @property
    def manifest(self) -> dict:
        return deepcopy(self._manifest)

    def __len__(self) -> int:
        return len(self._frames)

    def read_frame(self, index: int) -> NativePoseFrame:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self):
            raise IndexError("Native source frame is outside the sealed timeline")
        return NativePoseFrame(self._frames[index].to_dict())


class _Inputs:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.refs: dict[str, dict] = {}
        self.opened: list[str] = []

    def path(self, ref: dict) -> Path:
        ref = {"path": ref["path"], "sha256": ref["sha256"]}
        key = ref["path"]
        if key in self.refs and self.refs[key]["sha256"] != ref["sha256"]:
            raise ValueError("Conflicting cached source hashes: " + key)
        reader = BoundReader(self.root, [ref])
        value = reader.path(ref)
        self.refs[key] = {"path": key, "sha256": ref["sha256"]}
        self.opened.extend(reader.opened)
        return value

    def json(self, ref: dict) -> dict:
        ref = {"path": ref["path"], "sha256": ref["sha256"]}
        key = ref["path"]
        if key in self.refs and self.refs[key]["sha256"] != ref["sha256"]:
            raise ValueError("Conflicting cached source hashes: " + key)
        reader = BoundReader(self.root, [ref])
        value = reader.json(ref)
        self.refs[key] = {"path": key, "sha256": ref["sha256"]}
        self.opened.extend(reader.opened)
        return value


def _finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _number(value: str) -> float | None:
    if not value.strip():
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError("Malformed raw landmark number") from exc
    return number if math.isfinite(number) else None


def _timeline(data: dict, total: int, key: str = "frames") -> list[dict]:
    frames = data[key]
    if [row["frame_index"] for row in frames] != list(range(total)):
        raise ValueError("Incomplete, repeated or reordered cached frame timeline")
    return frames


def _same_path(stored: str, relative: str) -> bool:
    # Old capture receipts contain the original checkout's absolute Windows path.
    normalized = stored.replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized == relative or normalized.endswith("/" + relative)


def _raw_frames(path: Path, capture: dict, total: int) -> tuple[list[dict], list[dict]]:
    names = TOPOLOGIES["mediapipe_33"]["names"]
    values: list[dict] = [{} for _ in range(total)]
    records: list[dict] = [{} for _ in range(total)]
    choices = _timeline(capture, total, "selection_frames")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = {"frame", "timestamp_ms", "landmark", "x", "y", "z", "visibility", "presence"}
        if set(reader.fieldnames or ()) != expected:
            raise ValueError("Unexpected MediaPipe raw CSV contract")
        for record in reader:
            index = int(record["frame"])
            name = record["landmark"]
            if not 0 <= index < total or name not in names or name in values[index]:
                raise ValueError("Invalid/repeated original frame or landmark")
            if _number(record["timestamp_ms"]) != choices[index]["timestamp_ms"]:
                raise ValueError("Original raw/capture time mismatch")
            values[index][name] = {key: _number(record[key]) for key in ("x", "y", "z", "visibility", "presence")}
            records[index][name] = dict(record)
    for points, choice in zip(values, choices, strict=True):
        if len(points) not in (0, len(names)) or (len(points) == len(names)) != (choice["status"] == "selected"):
            raise ValueError("Original raw/selection cardinality mismatch")
    return values, records


def _protected_ref(protected: dict, path: str) -> dict:
    current = protected.get("current_source_hashes", {})
    upstream = protected.get("upstream", {})
    if path in current:
        result = {"path": path, "sha256": current[path]}
    elif path in upstream:
        result = upstream[path]
    else:
        raise ValueError("Original source lacks frozen receipt: " + path)
    if path in upstream and upstream[path]["sha256"] != result["sha256"]:
        raise ValueError("Original model/overlay frozen hashes conflict")
    return result


def _manifest(pid: str, backend: str, topology: str, model_ref: dict, size: dict,
              video: dict, refs: list[dict], roi: dict, overlay: dict | None) -> dict:
    return {
        "schema_version": "native-pose-manifest-v1", "pitch_id": pid,
        "backend": {"name": backend, "model_sha256": model_ref["sha256"],
                    "model_version": "pose_landmarker_full.task" if backend == "mediapipe" else "rtmpose-m-body7-20230504-e48f03d0",
                    "score_semantics": "visibility_and_presence_distinct_not_calibrated" if backend == "mediapipe" else "minimum_of_native_axis_maxima_not_probability"},
        "topology": topology, "image_size": size, "video": video,
        "timebase": {"frame_index_base": 0, "timestamp_semantics": "original_pose_capture_timestamp_ms_rounded_native_decode_no_shift"},
        "capabilities": dict(CAPABILITIES[topology]), "quality_status": "not_calibrated",
        "usable_for_analysis": None, "inference_mode": "cached_read_only",
        "source_refs": deepcopy(refs), "roi_provenance": roi, "original_overlay": overlay,
    }


def _base_frame(pid: str, backend: str, topology: str, context: dict, size: dict,
                video_sha: str, geometry: dict, selection: dict) -> dict:
    return {
        "schema_version": "native-keypoints-v1", "pitch_id": pid, "backend": backend,
        "topology": topology, "frame_index": context["frame_index"], "timestamp_ms": context["timestamp_ms"],
        "source_video_sha256": video_sha, "decoded_bgr_sha256": context["decoded_bgr_sha256"],
        "image_size": size, "coordinate_space": "original_image_pixels_xy",
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "input_geometry": geometry, "model_selection": selection, "landmarks": [],
    }


def load_cached_sources(root: Path, execution_path: Path, result_path: Path) -> dict[str, dict[str, CachedNativePoseSource]]:
    """Verify the completed trial chain and expose its 33/17-point sequences.

    SHA checks include the original videos, metadata, CSV/capture, model assets,
    ROI measurements, completed export/measurement receipts, and every native NPZ.
    Saved native XY/score are copied exactly; native vectors are not decoded here.
    """
    inputs = _Inputs(root)
    execution_ref = reference(inputs.root, execution_path)
    result_ref = reference(inputs.root, result_path)
    execution = inputs.json(execution_ref)
    result = inputs.json(result_ref)
    plan_sha = execution_ref["sha256"]
    if (result["execution"] != execution_ref or not result["status"].startswith("completed_once_")
            or execution["status"] != "approved_frozen_before_any_inference"):
        raise ValueError("Cached execution/result seal mismatch")
    artifacts = result["artifacts"]
    export = inputs.json(artifacts["exports/export_run.json"])
    measurement = inputs.json(artifacts["measurements/measurement_run.json"])
    native = inputs.json(artifacts["native/native_run.json"])
    child_ref = artifacts["native_execution.json"]
    child = inputs.json(child_ref)
    protected = inputs.json(execution["protected_before"])
    if (export["status"] != "sealed_gt_blind_rtmpose_inputs" or measurement["status"] != "sealed_all_rtmpose_response_measurements"
            or native["status"] != "sealed_native_rtmpose_run" or export["plan_sha256"] != plan_sha
            or measurement["plan_sha256"] != plan_sha or native["plan_sha256"] != child_ref["sha256"]
            or child["parent_plan_sha256"] != plan_sha or child["model"] != execution["model"]
            or child["export_run"] != artifacts["exports/export_run.json"]
            or any(row["human_annotation_inputs"] != [] for row in (export, measurement, native))):
        raise ValueError("Cached GT-blind source chain differs")
    clips = execution["clips"]
    pids = [clip["pitch_id"] for clip in clips]
    total_frames = sum(clip["total_frames"] for clip in clips)
    if (len(set(pids)) != len(pids) or result["source_frames"] != total_frames
            or native["native_frames"] != total_frames or [c["pitch_id"] for c in export["clips"]] != pids
            or len(measurement["clips"]) != len(clips)):
        raise ValueError("Cached clip/frame denominator differs")
    native_refs: dict[tuple[str, int], dict] = {}
    for ref in native["frames"]:
        key = (ref["pitch_id"], ref["frame_index"])
        if key in native_refs:
            raise ValueError("Repeated native frame receipt")
        native_refs[key] = ref
    if set(native_refs) != {(c["pitch_id"], i) for c in clips for i in range(c["total_frames"])}:
        raise ValueError("Native frame receipt timeline differs")
    rtm_model = execution["model"]
    inputs.path(rtm_model)
    common_refs = dict(inputs.refs)
    common_paths = list(dict.fromkeys(inputs.opened))
    sources: dict[str, dict[str, CachedNativePoseSource]] = {}
    for clip, exported, measured in zip(clips, export["clips"], measurement["clips"], strict=True):
        start = len(inputs.opened)
        pid, total, refs = clip["pitch_id"], clip["total_frames"], clip["measurement_sources"]
        inputs.path(refs["video"])
        metadata = inputs.json(refs["metadata"])
        technical = inputs.json(refs["video_metadata"])
        capture = inputs.json(refs["capture"])
        roi = inputs.json(refs["roi"])
        context = inputs.json(exported["context"])
        measured_data = inputs.json(measured)
        raw, records = _raw_frames(inputs.path(refs["raw_csv"]), capture, total)
        model_path = "models/" + capture["model"].replace("\\", "/").rsplit("/", 1)[-1]
        mp_model = _protected_ref(protected, model_path)
        inputs.path(mp_model)
        overlay_path = str(Path(refs["capture"]["path"]).parent / "overlay.mp4").replace("\\", "/")
        overlay = _protected_ref(protected, overlay_path)
        inputs.path(overlay)
        size = {"width": technical["width"], "height": technical["height"]}
        video_sha = refs["video"]["sha256"]
        if (metadata["pitch_id"] != pid or technical["sha256"] != video_sha or technical["frame_count"] != total
                or capture["processed_frames"] != total or capture["start_frame"] != 0 or capture["end_frame"] != total - 1
                or exported["total_frames"] != total or not _same_path(capture["video"], refs["video"]["path"])
                or not _same_path(capture["model"], model_path)
                or any(data[k] != size[k] for data in (capture, context, measured_data) for k in size)
                or any(data["video_sha256"] != video_sha or data["total_frames"] != total
                       or data["pitch_id"] != pid or data["plan_sha256"] != plan_sha for data in (context, measured_data))
                or context["human_annotation_inputs"] != [] or measured_data["human_annotation_inputs"] != []
                or measured_data["status"] != "sealed_rtmpose_response_measurements"):
            raise ValueError("Source video/geometry/capture binding differs: " + pid)
        contexts = _timeline(context, total)
        native_frames = _timeline(measured_data, total)
        roi_frames = _timeline(roi, total)
        choices = _timeline(capture, total, "selection_frames")
        times = [choice["timestamp_ms"] for choice in choices]
        if (times[0] != 0 or any(b <= a for a, b in zip(times, times[1:]))
                or len(technical["timestamps_ms"]) != total
                or any(round(t) != expected for t, expected in zip(technical["timestamps_ms"], times, strict=True))
                or not _finite(capture["fps"]) or capture["fps"] <= 0
                or not math.isclose(capture["fps"], technical["fps"], rel_tol=1e-9)):
            raise ValueError("Original capture timebase differs")
        mp_frames, rtm_frames = [], []
        for index, (ctx, native_frame, roi_frame, choice) in enumerate(zip(contexts, native_frames, roi_frames, choices, strict=True)):
            expected_ref = native_refs[(pid, index)]
            if (ctx["original_raw"] != raw[index] or ctx["timestamp_ms"] != choice["timestamp_ms"]
                    or ctx["geometry"] != native_frame["geometry"] or native_frame["native_ref"] != expected_ref
                    or ctx["geometry"]["roi_xywh"] != roi_frame["usable_rectangle_xywh"]
                    or any(native_frame[k] != ctx[k] for k in ("timestamp_ms", "decoded_bgr_sha256"))
                    or ctx["decoded_bgr_sha256"] != roi_frame["decoded_bgr_sha256"]
                    or ctx["geometry"]["source_size"] != [size["width"], size["height"]]):
                raise ValueError("Cached frame/pixel/raw/ROI binding differs: " + pid + "/" + str(index))
            inputs.path(expected_ref)
            mp = _base_frame(pid, "mediapipe", "mediapipe_33", ctx, size, video_sha,
                             {"input_mode": "full_frame", "roi_xywh": None, "affine_src_to_input": None,
                              "affine_input_to_src": None, "sdk_geometry": None}, deepcopy(choice))
            for j, name in enumerate(TOPOLOGIES["mediapipe_33"]["names"]):
                point = raw[index].get(name)
                observed = point is not None and _finite(point["x"]) and _finite(point["y"])
                mp["landmarks"].append({
                    "name": name, "index": j, "x_px": point["x"] * size["width"] if observed else None,
                    "y_px": point["y"] * size["height"] if observed else None,
                    "z": point["z"] if point else None, "visibility": point["visibility"] if point else None,
                    "presence": point["presence"] if point else None, "native_score": None,
                    "coordinate_state": "model_observed" if observed else "missing",
                    "missing_reason": None if observed else "original_selected_pose_missing" if point is None else "nonfinite_original_xy",
                    "source_record": deepcopy(records[index].get(name)),
                })
            mp_frames.append(mp)
            geom = deepcopy(ctx["geometry"])
            rtm = _base_frame(pid, "rtmpose", "coco_17", ctx, size, video_sha,
                              {"input_mode": "roi_affine", "roi_xywh": geom["roi_xywh"],
                               "affine_src_to_input": geom["affine_src_to_input"], "affine_input_to_src": geom["affine_input_to_src"],
                               "sdk_geometry": geom},
                              {"method": "sealed_human_seeded_csrt_roi", "human_initialized": True,
                               "native_response_source": {"path": expected_ref["path"], "sha256": expected_ref["sha256"]}})
            points = native_frame["native_keypoints"]
            if native_frame["native_contract"]["landmark_count"] != 17 or len(points) != 17:
                raise ValueError("Cached native topology differs")
            for j, (name, point) in enumerate(zip(TOPOLOGIES["coco_17"]["names"], points, strict=True)):
                if point["name"] != name or point["index"] != j:
                    raise ValueError("Cached native landmark name/order differs")
                x, y = point["x_px"], point["y_px"]
                if (x is None) != (y is None) or (x is not None and (not _finite(x) or not _finite(y))):
                    raise ValueError("Invalid saved native XY; refuse silent correction")
                observed = x is not None
                if observed != (point["decode_status"] == "decoded"):
                    raise ValueError("Saved native decode state/XY differ")
                rtm["landmarks"].append({
                    "name": name, "index": j, "x_px": x, "y_px": y, "z": None,
                    "visibility": None, "presence": None, "native_score": point["score"],
                    "coordinate_state": "model_observed" if observed else "missing",
                    "missing_reason": None if observed else point["decode_status"], "source_record": deepcopy(point),
                })
            rtm_frames.append(rtm)
        paths = list(dict.fromkeys(common_paths + inputs.opened[start:]))
        bound = [inputs.refs[path] for path in paths]
        video = {"path": refs["video"]["path"], "sha256": video_sha, "frame_count": total, "fps": capture["fps"]}
        sources[pid] = {
            "mediapipe": CachedNativePoseSource(_manifest(pid, "mediapipe", "mediapipe_33", mp_model, size, video, bound,
                {"input_mode": "full_frame", "roi_source": None, "human_initialized": False}, overlay), mp_frames, paths),
            "rtmpose": CachedNativePoseSource(_manifest(pid, "rtmpose", "coco_17", rtm_model, size, video, bound,
                {"input_mode": "roi_affine", "roi_source": deepcopy(refs["roi"]), "human_initialized": True,
                 "initialization_reference": deepcopy(roi.get("producer_sources", {}).get("initialization")),
                 "identity_verified_by_this_adapter": False}, None), rtm_frames, paths),
        }
    return sources
