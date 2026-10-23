"""Descriptive continuity of accepted native output; no quality classifier.

Only adjacent source frames are compared. Large motion, image-order changes and
multiple person candidates are measurements, not automatic errors or identity GT.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
from pathlib import Path

from .native_input import MANIFEST_NAME, SUMMARY_NAME, NativeAnalysisInput, load_native_analysis_input
from ..native_pose_io import BoundReader, reference, write_json
from ..native_pose_review import _statistics


_PAIRS = ("shoulder", "elbow", "wrist", "hip", "knee", "ankle")
_BREAKS = {"track_break_no_overlap", "track_break_tie", "track_break_non_mutual"}
_SEMANTICS = {
    "assessment": "descriptive_only", "joint_reliability": "unknown",
    "human_visibility": "unknown", "usable_for_analysis": None,
    "quality_gate_applied": False, "native_score_is_visibility": False,
    "large_motion_is_error": False, "image_order_flip_is_identity_switch": False,
    "candidate_index_is_person_identity": False, "interpolation_applied": False,
}


def _xy(point: dict) -> list[float] | None:
    return [point["x_px"], point["y_px"]] if point["coordinate_state"] == "model_observed" else None


def _distance(first, second):
    if first is None or second is None:
        return None
    return math.hypot(second[0] - first[0], second[1] - first[1])


def _midpoint(first, second):
    return [(first[0] + second[0]) / 2, (first[1] + second[1]) / 2] if first is not None and second is not None else None


def _ratio(current, previous):
    return current / previous if current is not None and previous is not None and previous > 0 else None


def _box_geometry(box):
    if box is None:
        return {"center_xy_px": None, "width_px": None, "height_px": None,
                "area_px2": None, "diagonal_px": None}
    width, height = box[2] - box[0], box[3] - box[1]
    return {"center_xy_px": [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2],
            "width_px": width, "height_px": height, "area_px2": width * height,
            "diagonal_px": math.hypot(width, height)}


def _spans(values, fps):
    """Inclusive frame spans; duration counts covered frame periods."""
    result = []
    for index, active in enumerate(values):
        if not active:
            continue
        if not result or result[-1]["end_frame"] != index - 1:
            result.append({"start_frame": index, "end_frame": index})
        else:
            result[-1]["end_frame"] = index
    for item in result:
        count = item["end_frame"] - item["start_frame"] + 1
        item.update(frame_count=count, start_sec=float(Fraction(item["start_frame"]) / fps),
                    end_sec=float(Fraction(item["end_frame"]) / fps),
                    duration_sec=float(Fraction(count) / fps))
    return result


def _series(values, *, start_frame=0):
    """Keep missing denominators and first min/max frame, including frame zero."""
    provided = [(index, value) for index, value in enumerate(values) if index >= start_frame and value is not None]
    result = _statistics([value for _, value in provided])
    result.update(total_count=max(0, len(values) - start_frame),
                  missing_count=max(0, len(values) - start_frame) - len(provided),
                  min_frame=min(provided, key=lambda pair: pair[1])[0] if provided else None,
                  max_frame=max(provided, key=lambda pair: pair[1])[0] if provided else None)
    return result


def describe_native_reliability(pitch: NativeAnalysisInput) -> tuple[dict, dict, list[dict]]:
    """Measure saved coordinates and tracks without changing their decisions."""
    manifest, metadata = pitch.manifest, pitch.metadata
    fps = Fraction(manifest["timebase"]["fps_fraction"])
    dt = float(1 / fps)
    rows = []
    for frame in pitch.iter_frames():
        native, track = frame.native.to_dict(), frame.tracking
        points = {point["name"]: point for point in native["landmarks"]}
        xy = {name: _xy(point) for name, point in points.items()}
        box = _box_geometry(track["selected_bbox_xyxy_px"])
        previous = rows[-1] if rows else None
        hip_center = _midpoint(xy["LEFT_HIP"], xy["RIGHT_HIP"])
        diagonal_a = _distance(xy["LEFT_SHOULDER"], xy["RIGHT_HIP"])
        diagonal_b = _distance(xy["RIGHT_SHOULDER"], xy["LEFT_HIP"])
        torso = (diagonal_a + diagonal_b) / 2 if diagonal_a is not None and diagonal_b is not None else None
        joints = {}
        for name, point in points.items():
            step = _distance(previous["joints"][name]["xy_px"], xy[name]) if previous else None
            joints[name] = {
                "coordinate_state": point["coordinate_state"], "xy_px": xy[name],
                "native_score": point["native_score"], "missing_reason": point["missing_reason"],
                "step_px": step, "speed_px_per_sec": step / dt if step is not None else None,
                "step_over_previous_bbox_diagonal": _ratio(step, previous["bbox"]["diagonal_px"]) if previous else None,
            }
        orders = {}
        flips = {}
        for part in _PAIRS:
            left, right = xy[f"LEFT_{part.upper()}"], xy[f"RIGHT_{part.upper()}"]
            order = None if left is None or right is None else (left[0] > right[0]) - (left[0] < right[0])
            orders[part] = order
            prior = previous["left_minus_right_x_sign"][part] if previous else None
            flips[part] = (order != prior) if order in (-1, 1) and prior in (-1, 1) else None
        continuity = {
            "bbox_center_step_px": _distance(previous["bbox"]["center_xy_px"], box["center_xy_px"]) if previous else None,
            "bbox_area_ratio": _ratio(box["area_px2"], previous["bbox"]["area_px2"]) if previous else None,
            "bbox_diagonal_ratio": _ratio(box["diagonal_px"], previous["bbox"]["diagonal_px"]) if previous else None,
            "hip_center_step_px": _distance(previous["hip_center_xy_px"], hip_center) if previous else None,
            "torso_diagonal_ratio": _ratio(torso, previous["torso_diagonal_px"]) if previous else None,
        }
        rows.append({
            "frame_index": frame.frame_index, "timestamp_sec": float(Fraction(frame.frame_index) / fps),
            "track_status": track["status"], "eligible_candidate_count": track["eligible_count"],
            "selected_output_index": track["selected_output_index"],
            "saved_match_iou": track.get("match_iou"), "bbox": box,
            "hip_center_xy_px": hip_center, "torso_diagonal_px": torso,
            "continuity": continuity, "joints": joints,
            "left_minus_right_x_sign": orders, "adjacent_image_order_flip": flips,
        })
    summary = pitch.usage_summary["native_coordinate_summary"]
    total = len(rows)
    joints = {}
    for name, existing in summary["joints"].items():
        joints[name] = {**existing,
            "reliability": "unknown", "human_visibility": "unknown",
            "missing_spans": _spans([row["joints"][name]["coordinate_state"] == "missing" for row in rows], fps),
            "adjacent_motion": {key: _series([row["joints"][name][key] for row in rows], start_frame=1) for key in
                                ("step_px", "speed_px_per_sec", "step_over_previous_bbox_diagonal")},
        }
    throwing = metadata["pitcher"]["throws"]
    lead = "LEFT" if throwing == "RIGHT" else "RIGHT"
    focus = {f"throwing_{part}": f"{throwing}_{part.upper()}" for part in ("shoulder", "elbow", "wrist")}
    focus.update({f"lead_{part}": f"{lead}_{part.upper()}" for part in ("hip", "knee", "ankle")})
    common = {"pitch_id": manifest["pitch_id"], "total_frames": total,
              "timebase": manifest["timebase"], "semantics": dict(_SEMANTICS),
              "human_overlay_review": pitch.review, "quality_status": "not_calibrated",
              "usable_for_analysis": None, "new_inference_calls": 0,
              "new_tracking_replays": 0, "new_ground_truth_labels": 0}
    pose = {**common, "schema_version": "native-pose-reliability-description-v1",
            "focus_joints": focus, "joints": joints, "left_right_image_order": {},
            "retained_landmark_slots": total * len(joints),
            "coordinate_availability_is_accuracy": False, "interpolated_coordinates": 0}
    for part in _PAIRS:
        orders = [row["left_minus_right_x_sign"][part] for row in rows]
        flips = [row["adjacent_image_order_flip"][part] for row in rows]
        pose["left_right_image_order"][part] = {
            "missing_frames": sum(order is None for order in orders),
            "equal_x_frames": [i for i, order in enumerate(orders) if order == 0],
            "comparable_adjacent_pairs": sum(flip is not None for flip in flips),
            "changed_at_frames": [i for i, flip in enumerate(flips) if flip is True],
            "meaning": "anatomical left x minus right x in image; rotation may change sign",
        }
    tracking = {**common, "schema_version": "native-tracking-reliability-description-v1",
                "track_status_counts": pitch.usage_summary["track_status_counts"],
                "break_frames": [row["frame_index"] for row in rows if row["track_status"] in _BREAKS],
                "unselected_spans": _spans([row["track_status"] not in ("seeded", "linked") for row in rows], fps),
                "saved_match_iou": _series([row["saved_match_iou"] for row in rows], start_frame=1),
                "eligible_candidate_count": _series([row["eligible_candidate_count"] for row in rows]),
                "multiple_candidate_frames": sum(row["eligible_candidate_count"] > 1 for row in rows),
                "automatic_identity_switch_assessment": "unknown",
                "hip_center_available_frames": sum(row["hip_center_xy_px"] is not None for row in rows),
                "torso_diagonal_px": _series([row["torso_diagonal_px"] for row in rows]),
                "adjacent_continuity": {key: _series([row["continuity"][key] for row in rows], start_frame=1) for key in
                                        rows[0]["continuity"]},
                "geometry_definitions": {
                    "hip_center": "midpoint of both model hip coordinates; null if either missing",
                    "torso_diagonal": "mean of left-shoulder/right-hip and right-shoulder/left-hip distances; all four required",
                    "bbox": "saved selected person rectangle; not skeleton extent",
                    "saved_match_iou": "copied from saved tracking; null when absent; no association recomputed",
                    "ratios": "current divided by previous; null for missing or zero denominator",
                }}
    return pose, tracking, rows


def _markdown(pose, tracking):
    lines = [f"# {pose['pitch_id']}：原生骨架資料摘要", "",
             f"影格：{pose['total_frames']}；人工 overlay：{pose['human_overlay_review']['status']}。",
             "數值描述模型輸出，座標存在不代表人體關節可見或正確。逐點可靠性仍為 unknown。", "",
             "| 關節角色 | 模型座標格數 | 缺值格數 | 最長缺值 | 最大相鄰位移（px） | 發生格 |",
             "|---|---:|---:|---:|---:|---:|"]
    for role, name in pose["focus_joints"].items():
        joint = pose["joints"][name]
        motion = joint["adjacent_motion"]["step_px"]
        amount = f"{motion['max']:.3f}" if motion["max"] is not None else "—"
        frame = motion["max_frame"] if motion["max_frame"] is not None else "—"
        lines.append(f"| {role} ({name}) | {joint['model_observed_coordinates']} | {joint['missing_coordinates']} | "
                     f"{joint['longest_missing_span_frames']} | {amount} | {frame} |")
    lines += ["", f"追蹤狀態：`{json.dumps(tracking['track_status_counts'])}`；"
              f"幾何中斷開始格：`{tracking['break_frames']}`。",
              f"有多個候選人物的格數：{tracking['multiple_candidate_frames']}；這不等於追錯人。", "",
              "格號由 0 開始；第 i 格位移比較 i−1 → i。缺值前後不跨格計算，也不補點。",
              "大位移可能是快速揮臂；左右影像順序改變可能是身體轉動。兩者均未設為錯誤警示。",
              "人物框 output_index 只是當格候選編號，換號不表示換人。", "",
              "`pose_reliability.json`：17點覆蓋率、缺值區段、原生分數、相鄰位移與左右順序。",
              "`tracking_reliability.json`：已保存框連接、框／雙髖中心、框／軀幹尺度描述。",
              "`frame_diagnostics.jsonl`：完整逐格測量、原座標與分數的衍生檢視副本。",
              "原始骨架／人工紀錄不變；沒有推論、插值、品質門檻或新增人工GT。", ""]
    return "\n".join(lines)


def write_native_reliability(root: str | Path, bundle_dir: str | Path, output: str | Path) -> dict:
    """Write a fresh description of an existing source-validated analysis bundle."""
    root = Path(root).resolve(strict=True)
    bundle = Path(bundle_dir)
    bundle = (bundle if bundle.is_absolute() else root / bundle).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Reliability reports must be inside this project's analysis_results")
    if output.exists():
        raise FileExistsError("Reliability report output already exists")
    refs = {"analysis_input_ref": reference(root, bundle / MANIFEST_NAME),
            "usage_summary_ref": reference(root, bundle / SUMMARY_NAME)}
    pitch = load_native_analysis_input(root, bundle)
    pose, tracking, rows = describe_native_reliability(pitch)
    refs.update(pitch.manifest["source_refs"])
    reader = BoundReader(root, refs.values())
    for ref in refs.values():
        reader.path(ref)
    for report in (pose, tracking):
        report["source_refs"] = refs
    # Serialize fully before creating output, rejecting nonfinite measurements.
    serialized = [json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows]
    for report in (pose, tracking):
        json.dumps(report, allow_nan=False)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "pose_reliability.json", pose)
    write_json(output / "tracking_reliability.json", tracking)
    with (output / "frame_diagnostics.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        stream.writelines(serialized)
    with (output / "report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(_markdown(pose, tracking))
    return {"status": "descriptive_report_complete", "pitch_id": pose["pitch_id"],
            "total_frames": len(rows), "quality_status": "not_calibrated", "new_inference_calls": 0}
