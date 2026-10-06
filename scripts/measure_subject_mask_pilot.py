"""Independent baseline-model mask measurement; no GT, warning or pose correction."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from pitch_analysis.subject import PitcherSelector


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sample_mask(mask, x, y):
    """Bilinear probability, with the final row/column kept at its edge value."""
    height, width = mask.shape
    if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < width and 0 <= y < height):
        raise ValueError("Query outside original image")
    left, top = math.floor(x), math.floor(y)
    right, bottom = min(left + 1, width - 1), min(top + 1, height - 1)
    dx, dy = x-left, y-top
    return float((1-dy)*((1-dx)*mask[top,left]+dx*mask[top,right])
                 + dy*((1-dx)*mask[bottom,left]+dx*mask[bottom,right]))


def read_mask(image):
    """Fail closed for the float reader that aborts this pinned SDK process.

    Two isolated real-mask probes failed inside numpy_view before returning.
    No uint8 reinterpretation, private pointer access or synthesized mask.
    """
    if int(image.image_format) == 9:  # SDK ImageFormat.VEC32F1
        return None, "sdk_float32_numpy_reader_native_failure"
    return None, "unexpected_pose_mask_format"


def run(plan_path, output):
    import mediapipe as mp

    if output.exists():
        raise FileExistsError("Fresh experimental output required")
    plan = read(plan_path)
    for path, expected in plan["source_hashes"].items():
        if sha(path) != expected:
            raise ValueError("Frozen source changed: " + path)
    positions = {}
    for path in plan["question_snapshots"]:
        manifest = read(path)
        if manifest["source_video"]["sha256"] != plan["source_video"]["sha256"]:
            raise ValueError("Question/video mismatch")
        rows = manifest.get("queries", manifest.get("questions"))
        for q in rows:
            if q["human_status"] != "unreviewed" or q.get("human_code") is not None:
                raise ValueError("Producer accepts only blank question snapshots")
            xy = q.get("queried_image_xy_px", q.get("image_xy_px"))
            key = (q["frame_index"], *xy)
            positions.setdefault(key, []).append(q["query_id"])
    output.mkdir(parents=True)
    (output / "masks").mkdir()
    reader = cv2.VideoCapture(plan["source_video"]["path"])
    width, height = int(reader.get(cv2.CAP_PROP_FRAME_WIDTH)), int(reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
    count = int(reader.get(cv2.CAP_PROP_FRAME_COUNT))
    if (width, height, count) != (plan["width"], plan["height"], plan["total_frames"]):
        raise ValueError("Video dimensions/timeline changed")
    cfg = plan["options"]
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=plan["model_path"]),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, **cfg)
    selector = PitcherSelector()
    frames, samples, files = [], [], []
    try:
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            for index in range(count):
                ok, frame = reader.read()
                if not ok:
                    raise ValueError("Incomplete clip decode")
                timestamp = round(reader.get(cv2.CAP_PROP_POS_MSEC))
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                result = detector.detect_for_video(image, timestamp)
                choice = selector.select(result.pose_landmarks)
                masks = result.segmentation_masks or []
                trace = {"frame_index":index, "timestamp_ms":timestamp, **asdict(choice),
                         "mask_count":len(masks),
                         "candidates":[[{"x":float(p.x),"y":float(p.y),"z":float(p.z),
                                        "visibility":float(p.visibility),"presence":float(p.presence)}
                                       for p in pose] for pose in result.pose_landmarks]}
                frames.append(trace)
                current = [(key,aliases) for key,aliases in positions.items() if key[0]==index]
                if not current:
                    continue
                decoded = [read_mask(m) for m in masks]
                arrays = [a for a,_ in decoded]
                trace["mask_metadata"] = [{"candidate_index":i,"format":int(m.image_format),
                                           "width":m.width,"height":m.height,"channels":m.channels,
                                           "step_bytes":m.step,"read_status":decoded[i][1]}
                                          for i,m in enumerate(masks)]
                reason = None
                selected = None
                if choice.index is None:
                    reason = "no_selected_subject"
                elif len(masks) != len(result.pose_landmarks):
                    reason = "mask_candidate_count_mismatch"
                elif choice.index >= len(arrays):
                    reason = "selected_mask_absent"
                else:
                    selected = arrays[choice.index]
                    if selected is None:
                        reason = decoded[choice.index][1]
                    elif selected.shape != (height,width) or not np.isfinite(selected).all():
                        selected, reason = None, "invalid_mask_shape_or_values"
                for (_,x,y),aliases in current:
                    samples.append({"frame_index":index,"image_xy_px":[x,y],"source_query_ids":aliases,
                                    "selected_candidate_index":choice.index,
                                    "mask_probability":sample_mask(selected,x,y) if selected is not None else None,
                                    "measurement_status":"available" if selected is not None else "missing",
                                    "missing_reason":reason})
                if selected is not None:
                    gray = (np.clip(selected,0,1)*255).astype(np.uint8)
                    rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    alpha = np.clip(selected,0,1)[...,None]*.4
                    color = np.array([40,210,230])
                    soft = ((1-alpha)*rgb + alpha*color).astype(np.uint8)
                    panel = np.concatenate((rgb,np.repeat(gray[...,None],3,axis=2),soft),axis=1)
                    display = output/f"frame_{index:04d}_mask_debug.png"
                    Image.fromarray(panel).save(display)
                    files.append({"path":str(display),"sha256":sha(display)})
    finally:
        reader.release()
    if len(samples) != len(positions):
        raise ValueError("Fixed questions missing from output")
    for path, expected in plan["source_hashes"].items():
        if sha(path) != expected:
            raise ValueError("Source changed during measurement")
    available = sum(s['measurement_status']=='available' for s in samples)
    report = {"status":"measured" if available==len(positions) else "insufficient_mask_evidence", "plan_path":str(plan_path),"plan_sha256":sha(plan_path),
              "producer_code_sha256":sha(__file__),"source_hashes":plan["source_hashes"],
              "options":cfg,"source_video":plan["source_video"],"frames":frames,"samples":samples,
              "unique_image_queries":len(positions),"available_samples":available,
              "files":files,"human_annotation_inputs":[],"warning_thresholds":None,
              "warning_predictions_generated":False,"predictions_or_gt_modified":False,
              "association":"same SDK result ordinal; mismatch stays missing, no old candidate index reused",
              "identity_verified":False,"phase2_acceptance":"IN PROGRESS"}
    (output/"mask_measurements.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    result=run(args.plan,args.output)
    print(json.dumps({"frames":len(result["frames"]),"queries":result["unique_image_queries"],
                      "available":result["available_samples"],"gt_inputs":[]}))
