"""Frozen, GT-blind appearance diagnostics; never infer identity or alter poses."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

import cv2
import numpy as np


TORSO = ("LEFT_SHOULDER", "RIGHT_SHOULDER", "RIGHT_HIP", "LEFT_HIP")
PARAMETERS = {
    "source_rule": "earliest_raw_four_torso_gate_only_no_later_fallback",
    "patch_size_px": 9,
    "center_fractions": [1 / 3, 2 / 3],
    "rounding": "floor",
    "search": "full_native_grayscale_frame",
    "method": "TM_CCOEFF_NORMED",
    "maximum_nonoverlapping_candidates": 3,
    "equal_score_order": "row_then_column",
    "template_updates": False,
    "reseed": False,
    "warning_threshold": None,
    "matching_cutoff": None,
    "minmax_normalization": False,
    "constant_denominator": "unavailable",
}


def sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as target:
        json.dump(value, target, indent=2, allow_nan=False)
        target.write("\n")


def array_hash(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def write_image(path, pixels):
    if not cv2.imwrite(str(path), pixels):
        raise OSError(f"Could not save source image: {path}")


def runtime():
    return {"python": platform.python_version(), "executable_sha256": sha256(sys.executable),
            "opencv": cv2.__version__, "numpy": np.__version__}


def source_patch_rect(center, torso, width, height, size=9):
    """Return an inclusive pixel rectangle only if all corners fit the raw hull."""
    points = np.asarray(torso, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        return None, "invalid_raw_torso_geometry"
    hull = cv2.convexHull(points)
    if cv2.contourArea(hull) <= 0:
        return None, "degenerate_raw_torso_hull"
    if not np.isfinite(center).all():
        return None, "invalid_source_center"
    half = size // 2
    cx, cy = (math.floor(float(v)) for v in center)
    left, top = cx - half, cy - half
    right, bottom = left + size - 1, top + size - 1
    if left < 0 or top < 0 or right >= width or bottom >= height:
        return None, "source_patch_out_of_image"
    if any(cv2.pointPolygonTest(hull, (float(x), float(y)), False) < 0
           for x, y in ((left, top), (right, top), (right, bottom), (left, bottom))):
        return None, "source_patch_corners_outside_raw_hull"
    return [left, top, size, size], None


def rectangles_overlap(first, second):
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def patch_variances(gray, size):
    """Exact integer-pixel moments; no texture confidence gate is introduced."""
    value = gray.astype(np.float64)
    sums = cv2.integral(value, sdepth=cv2.CV_64F)
    squares = cv2.integral(value * value, sdepth=cv2.CV_64F)

    def windows(integral):
        return integral[size:, size:] - integral[:-size, size:] - integral[size:, :-size] + integral[:-size, :-size]

    count = size * size
    return windows(squares) / count - (windows(sums) / count) ** 2


def matching_candidates(gray, template, limit=3):
    if gray.ndim != 2 or template.ndim != 2 or template.shape[0] != template.shape[1]:
        raise ValueError("Expected square grayscale template and frame")
    size = template.shape[0]
    if min(gray.shape) < size:
        raise ValueError("Template larger than frame")
    if float(np.var(template.astype(np.float64))) == 0:
        return {"status": "unavailable", "reason": "constant_template_denominator", "candidates": []}
    scores = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    variances = patch_variances(gray, size)
    constant = variances <= 0
    invalid = ~np.isfinite(scores)
    scores[constant | invalid] = np.nan
    receipt = {"shape": list(scores.shape), "dtype": str(scores.dtype), "sha256": array_hash(scores),
               "constant_search_positions": int(np.count_nonzero(constant)),
               "nonfinite_opencv_positions": int(np.count_nonzero(invalid)),
               "available_search_positions": int(np.count_nonzero(np.isfinite(scores)))}
    work = scores.copy()
    candidates = []
    for rank in range(limit):
        if not np.isfinite(work).any():
            break
        best = float(np.nanmax(work))
        tied = work == best
        # np.flatnonzero is row-major: never silently interpret a tie as identity.
        position = int(np.flatnonzero(tied)[0])
        y, x = np.unravel_index(position, work.shape)
        candidates.append({"rank": rank + 1, "rectangle_xywh": [int(x), int(y), size, size],
                           "center_xy_px": [int(x) + size // 2, int(y) + size // 2],
                           "score": best, "equal_score_positions_before_this_suppression": int(np.count_nonzero(tied)),
                           "search_patch_variance": float(variances[y, x])})
        # Remove every rectangle that overlaps this complete patch, not just its center.
        work[max(0, y-size+1):y+size, max(0, x-size+1):x+size] = np.nan
    return {"status": "available" if candidates else "unavailable",
            "reason": None if candidates else "no_finite_nonconstant_search_patch",
            "candidates": candidates, "score_map": receipt,
            "top_competitor_margin": candidates[0]["score"] - candidates[1]["score"] if len(candidates) > 1 else None,
            "identity_decision": None}


def load_raw(path, meta, capture):
    frames = [dict() for _ in range(meta["frame_count"])]
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            index = int(row["frame"])
            if not 0 <= index < len(frames) or row["landmark"] in frames[index]:
                raise ValueError("Invalid or repeated raw frame/landmark")
            native_timestamp = capture["selection_frames"][index]["timestamp_ms"]
            if native_timestamp != round(meta["timestamps_ms"][index]):
                raise ValueError("Capture timestamp differs from rounded native video PTS")
            if not math.isclose(float(row["timestamp_ms"]), native_timestamp, abs_tol=1e-7):
                raise ValueError("Raw timestamp differs from original capture timestamp")
            frames[index][row["landmark"]] = {key: float(row[key]) for key in ("x", "y", "visibility", "presence")}
    return frames


def first_gate_frame(frames, config):
    for index, pose in enumerate(frames):
        if all(name in pose and all(math.isfinite(pose[name][key]) for key in ("x", "y", "visibility", "presence"))
               and pose[name]["visibility"] >= config["min_visibility"]
               and pose[name]["presence"] >= config["min_presence"] for name in TORSO):
            return index
    return None


def measure(root, plan_path, output):
    root, plan_path, output = root.resolve(), plan_path.resolve(), output.resolve()
    plan = read(plan_path)
    if plan["status"] != "frozen_before_measurement" or plan["parameters"] != PARAMETERS:
        raise ValueError("Measurement requires unchanged frozen parameters")
    if plan["producer_sha256"] != sha256(__file__) or plan["runtime"] != runtime():
        raise ValueError("Runner/runtime differ from the frozen plan")
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Output must be a new workspace analysis_results directory")
    # Only these explicitly bound six inputs are opened here. Evaluator-only hashes
    # may occur in the plan, but their files/annotations never enter this producer.
    roles = plan["measurement_source_roles"]
    if set(roles) != {"video", "metadata", "raw_csv", "capture", "clean_config", "video_metadata"}:
        raise ValueError("Unexpected producer source roles")
    if set(roles.values()) != set(plan["measurement_source_hashes"]):
        raise ValueError("Unexpected extra producer input")
    for relative, expected in plan["measurement_source_hashes"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or sha256(path) != expected:
            raise ValueError("Producer source binding mismatch")
    paths = {role: root / relative for role, relative in roles.items()}
    meta, config, metadata, capture = (read(paths[k]) for k in ("video_metadata", "clean_config", "metadata", "capture"))
    if meta["sha256"] != plan["measurement_source_hashes"][roles["video"]] or metadata["pitch_id"] != plan["pitch_id"]:
        raise ValueError("Video/pitch binding mismatch")
    total, width, height = (meta[k] for k in ("frame_count", "width", "height"))
    if total != plan["total_frames"] or [f["frame_index"] for f in capture["selection_frames"]] != list(range(total)):
        raise ValueError("Capture/frame denominator mismatch")
    if len(meta["timestamps_ms"]) != total:
        raise ValueError("Video timestamp denominator mismatch")
    raw = load_raw(paths["raw_csv"], meta, capture)
    seed = first_gate_frame(raw, config)
    patches, templates, records = [], {}, []
    if seed is None:
        patches = [{"patch_id": i, "source_frame": None, "fraction": fraction,
                    "unrounded_center_xy_px": None, "rectangle_xywh": None,
                    "status": "unavailable", "reason": "no_existing_gate_source_frame",
                    "whole_patch_ownership": "unreviewed", "anatomical_joint_reference": False}
                   for i, fraction in enumerate(PARAMETERS["center_fractions"], 1)]
    output.mkdir(parents=True)
    video = cv2.VideoCapture(str(paths["video"]))
    if not video.isOpened():
        raise ValueError("Cannot decode prepared video")
    try:
        for index in range(total):
            ok, bgr = video.read()
            if not ok or bgr.shape[:2] != (height, width):
                raise ValueError("Decoded frame count/dimensions mismatch")
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            if index == seed:
                write_image(output / "source_frame_raw.png", bgr)
                torso = np.asarray([[raw[index][n]["x"]*width, raw[index][n]["y"]*height] for n in TORSO])
                shoulder = (torso[0] + torso[1]) / 2
                hip = (torso[2] + torso[3]) / 2
                overlay = bgr.copy()
                prior_rects = []
                for patch_id, fraction in enumerate(PARAMETERS["center_fractions"], 1):
                    center = shoulder + (hip-shoulder)*fraction
                    rect, reason = source_patch_rect(center, torso, width, height)
                    if rect and any(rectangles_overlap(rect, old) for old in prior_rects):
                        reason = "source_patches_overlap"
                        rect = None
                    patch = {"patch_id": patch_id, "source_frame": seed, "fraction": fraction,
                             "unrounded_center_xy_px": center.tolist(), "rectangle_xywh": rect,
                             "status": "unavailable", "reason": reason, "whole_patch_ownership": "unreviewed",
                             "anatomical_joint_reference": False}
                    if rect:
                        prior_rects.append(rect)
                        x, y, w, h = rect
                        pixels = gray[y:y+h, x:x+w].copy()
                        color = bgr[y:y+h, x:x+w].copy()
                        patch.update({"gray_pixels": pixels.tolist(), "gray_sha256": array_hash(pixels),
                                      "variance": float(np.var(pixels.astype(np.float64))),
                                      "bgr_sha256": array_hash(color), "image_filename": f"source_patch_{patch_id}.png"})
                        write_image(output / patch["image_filename"], color)
                        write_image(output / f"source_patch_{patch_id}_enlarged.png", cv2.resize(color, (180, 180), interpolation=cv2.INTER_NEAREST))
                        cv2.rectangle(overlay, (x, y), (x+w-1, y+h-1), (0, 220, 255), 1)
                        cv2.putText(overlay, str(patch_id), (x+w+3, y+h//2), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 220, 255), 1)
                        if patch["variance"] > 0:
                            templates[patch_id] = pixels
                            patch.update({"status": "available_unverified_ownership", "reason": None})
                        else:
                            patch["reason"] = "constant_template_denominator"
                    patches.append(patch)
                write_image(output / "source_frame_patch_context.png", overlay)
            result = {"frame_index": index, "timestamp_ms": meta["timestamps_ms"][index],
                      "decoded_gray_sha256": array_hash(gray), "selection_status": capture["selection_frames"][index]["status"],
                      "patch_matches": [], "subject_identity": None, "warning_prediction": None}
            for patch_id in (1, 2):
                if seed is None or index < seed:
                    match = {"status": "unavailable", "reason": "before_source_frame_or_no_gate_frame", "candidates": []}
                elif patch_id not in templates:
                    match = {"status": "unavailable", "reason": patches[patch_id-1]["reason"], "candidates": []}
                else:
                    match = matching_candidates(gray, templates[patch_id])
                result["patch_matches"].append({"patch_id": patch_id, **match})
            records.append(result)
        if video.read()[0]:
            raise ValueError("Extra decoded frames")
    finally:
        video.release()
    for relative, expected in plan["measurement_source_hashes"].items():
        if sha256(root / relative) != expected:
            raise ValueError("Input changed during measurement")
    result = {"status": "measured_unverified_source_ownership", "pitch_id": plan["pitch_id"],
              "total_frames": total, "width": width, "height": height, "source_frame": seed,
              "existing_gate": {k: config[k] for k in ("min_visibility", "min_presence")},
              "plan_path": str(plan_path.relative_to(root)), "plan_sha256": sha256(plan_path),
              "producer_sha256": sha256(__file__), "runtime": runtime(), "parameters": PARAMETERS,
              "source_hashes": plan["measurement_source_hashes"], "source_patches": patches, "frames": records,
              "human_files_read": [], "pose_inference_rerun": False, "template_updates": [], "reset_frames": [],
              "warning_predictions": None, "identity_predictions": None, "production_changes": False,
              "output_image_hashes": {p.name: sha256(p) for p in sorted(output.glob("*.png"))}}
    write(output / "appearance_measurements.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = measure(args.root, args.plan, args.output)
    print(json.dumps({k: result[k] for k in ("status", "total_frames", "source_frame", "source_patches")}))
