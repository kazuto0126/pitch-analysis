"""Export a source-bound review view; never run inference or edit predictions/GT.

This is a derived cache for already-reviewed clips, not another annotation schema
or a detector. Human labels target the original raw overlay. Clean interpolation
does not inherit a raw-coordinate accuracy judgment.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pitch_analysis.ground_truth import FULL_JOINT_LABELS, validate_ground_truth

ROLES = tuple(label.removesuffix("_reliability") for label in FULL_JOINT_LABELS)
HUMAN_STATES = {"reliable", "unreliable", "uncertain", "not_observable"}
MODEL_STATES = {"observed", "interpolated", "missing"}
REQUIRED_SOURCES = {
    "original_video", "input_metadata", "input_manifest", "video_metadata",
    "ground_truth", "raw_keypoints", "processed_keypoints", "pose_clean",
    "pose_reliability", "tracking_reliability", "original_overlay",
}
ROLE_ZH = {
    "throwing_shoulder": "投球肩", "throwing_elbow": "投球肘",
    "throwing_wrist": "投球腕", "lead_hip": "前導髖",
    "lead_knee": "前導膝", "lead_ankle": "前導踝",
}
HUMAN_ZH = {"reliable": "人工：對位可核對", "unreliable": "人工：不可靠",
            "uncertain": "人工：不確定", "not_observable": "人工：無法觀測"}
STATE_ZH = {"observed": "直接觀測", "interpolated": "插值", "missing": "缺失"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, data):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def bound_path(root, record):
    path = root / record["path"]
    if not path.is_file() or sha256(path) != record["sha256"]:
        raise ValueError(f"source binding changed: {record['path']}")
    return path


def lookup_joint(intervals, frame):
    matches = [(i, interval) for i, interval in enumerate(intervals)
               if interval["start_frame"] <= frame <= interval["end_frame"]]
    if len(matches) != 1 or matches[0][1]["status"] not in HUMAN_STATES:
        raise ValueError("each focus joint needs exactly one reviewed interval per frame")
    index, interval = matches[0]
    return {"interval_index": index, **deepcopy(interval)}


def interval_evidence(labels, name, frame):
    return [{"interval_index": i, **deepcopy(item)}
            for i, item in enumerate(labels[name])
            if item["start_frame"] <= frame <= item["end_frame"]]


def confirmed(intervals):
    # Historical confirmed intervals may omit status. Preserve actual payload.
    return any(item.get("status", "confirmed") == "confirmed" for item in intervals)


def saved_state(point, raw_frame, raw_point):
    xy = (point.get("x"), point.get("y"))
    if not point["usable"]:
        return "missing"
    if any(value is None or not math.isfinite(value) for value in xy):
        raise ValueError("usable saved coordinate must have finite x/y")
    if point["interpolated"]:
        return "interpolated"
    if not point["quality_valid"] or not raw_frame["detected"] or raw_point is None:
        raise ValueError("observed point needs a detected, quality-valid raw source")
    if any(raw_point.get(key) is None or not math.isfinite(raw_point[key]) for key in ("x", "y")):
        raise ValueError("observed raw coordinate must have finite x/y")
    if xy != (raw_point["x"], raw_point["y"]):
        raise ValueError("saved observed coordinate differs from its raw source")
    return "observed"


def disposition(human_status, model_state, human_frame):
    """Conservative use guidance, not a new prediction or accuracy threshold."""
    if human_status not in HUMAN_STATES or model_state not in MODEL_STATES:
        raise ValueError("unknown human/model state")
    restrictions = []
    for key in ("major_pose_failure", "track_break", "identity_switch"):
        if confirmed(human_frame[key]):
            restrictions.append("human_confirmed_" + key)
    if human_frame["pitcher_correctly_selected"] is not True:
        restrictions.append("subject_review_does_not_confirm_pitcher")
    if human_status != "reliable":
        restrictions.append("human_raw_" + human_status)
    if model_state == "interpolated":
        restrictions.append("processed_interpolation_not_manually_reviewed")
    elif model_state == "missing":
        restrictions.append("no_usable_processed_coordinate")
    if model_state == "missing":
        status = "unavailable_missing"
    elif any(value.startswith("human_confirmed_") or value.startswith("subject_review_")
             for value in restrictions):
        status = "hold_frame_review"
    elif human_status != "reliable":
        status = "hold_raw_" + human_status
    elif model_state == "interpolated":
        status = "unverified_processed_interpolation"
    else:
        status = "reviewed_raw_observation"
    verification = "not_reviewed"
    if model_state == "missing":
        verification = "no_usable_coordinate"
    elif model_state == "observed" and human_status == "reliable":
        verification = "qualitative_same_coordinate_as_reviewed_raw"
    return {"status": status, "restrictions": restrictions,
            "processed_coordinate_review": verification,
            "accuracy_claim": "no exact pixel-accuracy or 3D certification"}


def role_mapping(throws):
    if throws not in {"RIGHT", "LEFT"}:
        raise ValueError("unknown throwing side")
    lead = "LEFT" if throws == "RIGHT" else "RIGHT"
    return {role: f"{throws if role.startswith('throwing_') else lead}_{role.split('_')[1].upper()}"
            for role in ROLES}


def validate_review(gt):
    validate_ground_truth(gt)
    if gt["annotation_status"] != "reviewed" or gt.get("review_profile") != "phase2_full_review":
        raise ValueError("requires completed full human review; templates are not negative truth")
    for label in FULL_JOINT_LABELS:
        if label not in gt["labels"] or gt["labels"][label] is None:
            raise ValueError("requires all six reviewed focus joints")


def derive_clip(spec, sources):
    gt = read_json(sources["ground_truth"])
    validate_review(gt)
    raw = read_json(sources["raw_keypoints"])
    meta = read_json(sources["video_metadata"])
    manifest = read_json(sources["input_manifest"])
    input_meta = read_json(sources["input_metadata"])
    pose = read_json(sources["pose_reliability"])
    tracking = read_json(sources["tracking_reliability"])
    processed = [json.loads(line) for line in sources["processed_keypoints"].read_text(encoding="utf-8").splitlines()]
    pid = spec["pitch_id"]
    total = gt["source_video"]["total_frames"]
    if not (total == meta["frame_count"] == pose["total_frames"] == tracking["total_frames"]):
        raise ValueError("source frame-count disagreement")
    if manifest != input_meta or manifest["pitch_id"] != pid:
        raise ValueError("formal metadata differs from prediction input")
    pitcher = manifest["pitcher"]
    if gt["source_video"]["pitch_id"] != pid or any(d["pitch_id"] != pid for d in (raw, pose, tracking)):
        raise ValueError("pitch identity disagreement")
    if any(d["pitcher_id"] != pitcher["id"] for d in (raw, pose, tracking)):
        raise ValueError("pitcher identity disagreement")
    if (gt["source_video"]["sha256"] != spec["sources"]["original_video"]["sha256"]
            or meta["sha256"] != gt["source_video"]["sha256"]
            or gt["source_video"]["filename"] != sources["original_video"].name
            or manifest["video"]["file"] != sources["original_video"].name):
        raise ValueError("GT/prediction/video binding disagreement")
    if not raw["coordinate_system"].startswith("normalized_image_xy;"):
        raise ValueError("unsupported coordinate system")
    if pose["source_artifacts"]["pose_clean_sha256"] != spec["sources"]["pose_clean"]["sha256"]:
        raise ValueError("pose state source binding disagreement")
    roles = role_mapping(pitcher["throws"])
    if roles != pose["important_joints"]:
        raise ValueError("handedness/focus-role disagreement")
    indices = list(range(total))
    if (pose["frame_indices"] != indices
            or any([f["frame_index"] for f in seq] != indices for seq in (raw["frames"], processed, tracking["frames"]))
            or len(meta["timestamps_ms"]) != total):
        raise ValueError("timeline must include every original frame exactly once")
    for role, name in roles.items():
        if len(pose["joints"][name]["frame_states"]) != total:
            raise ValueError("joint state timeline incomplete")
    labels = gt["labels"]
    frames = []
    for index in indices:
        timestamp = meta["timestamps_ms"][index]
        rf, pf = raw["frames"][index], processed[index]
        if not all(math.isfinite(value) and abs(value - timestamp) < 1e-8
                   for value in (rf["timestamp_ms"], pf["timestamp_ms"])):
            raise ValueError("raw/processed/original timestamp disagreement")
        raw_points = {point["name"]: point for point in rf["landmarks"]}
        if len(raw_points) != len(rf["landmarks"]):
            raise ValueError("duplicate raw joint")
        human = {"pitcher_correctly_selected": labels["pitcher_correctly_selected"],
                 "pitcher_selection_review": deepcopy(labels["pitcher_selection_review"])}
        for short, full in (("major_pose_failure", "major_pose_failure_intervals"),
                            ("track_break", "track_break_intervals"),
                            ("identity_switch", "identity_switch_intervals"),
                            ("throwing_arm_occlusion", "throwing_arm_occlusion_intervals")):
            human[short] = interval_evidence(labels, full, index)
        joints = {}
        for role, name in roles.items():
            human_joint = lookup_joint(labels[role + "_reliability"], index)
            rp, pp = raw_points.get(name), pf["landmarks"][name]
            state = saved_state(pp, rf, rp)
            if state != pose["joints"][name]["frame_states"][index]:
                raise ValueError("saved clean point and existing reliability state disagree")
            joints[role] = {
                "landmark": name, "human_raw_overlay_review": human_joint,
                "model_state": state, "raw_landmark": deepcopy(rp),
                "processed_landmark": deepcopy(pp),
                "use_disposition": disposition(human_joint["status"], state, human),
            }
        frames.append({"frame_index": index, "timestamp_ms": timestamp,
                       "human_review": human, "existing_model_tracking": deepcopy(tracking["frames"][index]),
                       "focus_joints": joints})
    summary = {
        "total_frames": total, "focus_joint_rows": total * len(roles),
        "human_major_pose_failure_frames": sum(confirmed(f["human_review"]["major_pose_failure"]) for f in frames),
        "human_track_break_frames": sum(confirmed(f["human_review"]["track_break"]) for f in frames),
        "human_identity_switch_frames": sum(confirmed(f["human_review"]["identity_switch"]) for f in frames),
        "human_joint_status_counts": dict(Counter(j["human_raw_overlay_review"]["status"] for f in frames for j in f["focus_joints"].values())),
        "model_state_counts": dict(Counter(j["model_state"] for f in frames for j in f["focus_joints"].values())),
        "use_disposition_counts": dict(Counter(j["use_disposition"]["status"] for f in frames for j in f["focus_joints"].values())),
        "by_focus_joint": {role: {
            "landmark": name,
            "human_status_counts": dict(Counter(f["focus_joints"][role]["human_raw_overlay_review"]["status"] for f in frames)),
            "model_state_counts": dict(Counter(f["focus_joints"][role]["model_state"] for f in frames)),
            "existing_provisional_model_joint_status": pose["joints"][name]["status"],
        } for role, name in roles.items()},
    }
    return {
        "schema_version": "reviewed-reliability-view-v1",
        "output_kind": "derived_reviewed_reliability_view_not_editable_ground_truth",
        "pitch_id": pid, "pitcher": deepcopy(pitcher), "review_scope": "raw_overlay",
        "ground_truth_provenance": deepcopy(gt["provenance"]),
        "source_artifacts": deepcopy(spec["sources"]),
        "events_as_reviewed": deepcopy(labels["events"]),
        "existing_model_status": {"pose": pose["status"], "tracking": tracking["status"],
                                  "identity_switch_confirmed": tracking["identity_switch_confirmed"]},
        "limitations": [
            "Human flags are copied reviewed evidence, not new automatic warnings.",
            "Qualitative raw-overlay review does not certify interpolated/median coordinates.",
            "No major failure interval does not certify all 33 keypoints; six focus joints only.",
            "not_observable means unable to verify; do not infer wrong position or known occlusion cause.",
            "Original coordinates, states, event uncertainty and raw reasons remain unchanged.",
            "Known development clips only; no unseen-video generalization or true 3D accuracy claim.",
        ],
        "summary": summary, "frames": frames,
    }


def compose_frame(overlay_bgr, frame, view, font_path, panel_width=460):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    height = overlay_bgr.shape[0]
    if height < 598 or panel_width != 460:
        raise ValueError("review panel requires height >= 598 and width 460; no clipped text")
    panel = Image.new("RGB", (panel_width, height), (20, 25, 34))
    draw = ImageDraw.Draw(panel)
    font = ImageFont.truetype(str(font_path), 19)
    small = ImageFont.truetype(str(font_path), 15)
    title = ImageFont.truetype(str(font_path), 23)
    white, gray = (235, 240, 245), (165, 180, 197)
    draw.text((14, 8), view["pitch_id"] + "  人工覆核視圖", font=title, fill=white)
    draw.text((14, 40), f"第 {frame['frame_index']} 格  ·  {frame['timestamp_ms']/1000:.3f} 秒", font=font, fill=white)
    draw.text((14, 67), f"覆核：{view['ground_truth_provenance']['reviewer']}  |  原始骨架未修正", font=small, fill=gray)
    human = frame["human_review"]
    major = confirmed(human["major_pose_failure"])
    broken = confirmed(human["track_break"])
    switched = confirmed(human["identity_switch"])
    if switched:
        banner = "人工確認：身份切換"
    elif broken and major:
        banner = "人工確認：骨架中斷／重大失敗"
    elif broken:
        banner = "人工確認：骨架中斷"
    elif major:
        banner = "人工確認：重大骨架錯位"
    else:
        banner = "此格未記錄人工重大失敗（詳見各關節）"
    draw.rounded_rectangle((10, 93, 450, 133), radius=5, fill=(116, 37, 40) if major or broken or switched else (33, 47, 62))
    draw.text((18, 103), banner, font=font if major or broken or switched else small, fill=white)
    track = frame["existing_model_tracking"]
    draw.text((14, 142), f"原模型選取：{track['selection_status']}　警示 {len(track['warnings'])} 項", font=small, fill=gray)
    draw.text((14, 162), "以下人工標籤與模型資料狀態分開呈現", font=small, fill=gray)
    colors = {"reliable": (118, 220, 168), "unreliable": (255, 137, 129),
              "not_observable": (230, 195, 113), "uncertain": (198, 170, 245)}
    for i, role in enumerate(ROLES):
        joint = frame["focus_joints"][role]
        y = 192 + 53 * i
        label = joint["human_raw_overlay_review"]["status"]
        draw.text((14, y), ROLE_ZH[role], font=font, fill=white)
        draw.text((118, y), HUMAN_ZH[label], font=font, fill=colors[label])
        tail = "；處理後插值未覆核" if joint["model_state"] == "interpolated" else ""
        draw.text((118, y + 25), "模型資料：" + STATE_ZH[joint["model_state"]] + tail, font=small, fill=gray)
        draw.line((14, y + 48, 446, y + 48), fill=(45, 56, 71))
    draw.text((14, 521), "人工判讀針對左方原始骨架；插值未被認證。", font=small, fill=gray)
    draw.text((14, 544), "不是新的自動偵測／不是精確座標或 3D 認證。", font=small, fill=gray)
    draw.text((14, 567), "逐格原因、原模型警示與事件：見同目錄 JSON。", font=small, fill=gray)
    panel_bgr = np.asarray(panel)[:, :, ::-1]
    return np.concatenate((overlay_bgr, panel_bgr), axis=1)


def video_receipt(path, meta, *, ffprobe=None, reviewed=False):
    import cv2
    cap = cv2.VideoCapture(str(path))
    count = 0
    expected_width = meta["width"] + (460 if reviewed else 0)
    if not cap.isOpened() or not math.isclose(cap.get(cv2.CAP_PROP_FPS), meta["fps"], abs_tol=1e-5):
        cap.release()
        raise ValueError("video open/fps mismatch")
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                break
            if image.shape[:2] != (meta["height"], expected_width):
                raise ValueError("decoded video dimensions mismatch")
            count += 1
    finally:
        cap.release()
    if count != meta["frame_count"]:
        raise ValueError("decoded frame-count mismatch")
    receipt = {"path": str(path), "decoded_frames": count, "width": expected_width,
               "height": meta["height"], "fps": meta["fps"], "sha256": sha256(path)}
    if ffprobe:
        result = subprocess.run([str(ffprobe), "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=codec_name,pix_fmt", "-of", "json", str(path)],
                                capture_output=True, text=True, check=True)
        stream = json.loads(result.stdout)["streams"][0]
        if stream["codec_name"] != "h264" or stream["pix_fmt"] != "yuv420p":
            raise ValueError("reviewed export must be browser-friendly H264/yuv420p")
        receipt.update(stream)
    return receipt


def render_overlay(source, outdir, view, meta, ffmpeg, font_path):
    import cv2
    output = outdir / "reviewed_overlay.mp4"
    if output.exists():
        raise FileExistsError(output)
    video_receipt(source, meta)
    cap = cv2.VideoCapture(str(source))
    width, height = meta["width"] + 460, meta["height"]
    samples = {0, meta["frame_count"] - 1}
    # Export evidence examples, not new labels or event predictions.
    for key in ("major_pose_failure", "track_break"):
        hits = [f["frame_index"] for f in view["frames"] if confirmed(f["human_review"][key])]
        if hits:
            samples.update((hits[0], hits[len(hits)//2], hits[-1]))
    for state in ("interpolated", "missing"):
        hits = [f["frame_index"] for f in view["frames"]
                if any(j["model_state"] == state for j in f["focus_joints"].values())]
        if hits:
            samples.add(hits[0])
    snapshots = []
    with (outdir / "encoding.log").open("xb") as log:
        process = subprocess.Popen([
            str(ffmpeg), "-hide_banner", "-loglevel", "warning", "-nostdin", "-n",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", format(meta["fps"], ".12g"), "-i", "pipe:0", "-an",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(output),
        ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
        try:
            for frame in view["frames"]:
                ok, image = cap.read()
                if not ok:
                    raise ValueError("original overlay decode stopped early")
                composed = compose_frame(image, frame, view, font_path)
                # Only the added panel changes geometry; H264 reencoding is lossy.
                if (composed[:, :meta["width"]] != image).any():
                    raise ValueError("source overlay area changed before encoding")
                process.stdin.write(composed.tobytes())
                if frame["frame_index"] in samples:
                    name = f"review_frame_{frame['frame_index']:04d}.png"
                    if not cv2.imwrite(str(outdir / name), composed):
                        raise ValueError("review snapshot write failed")
                    snapshots.append(name)
            if cap.read()[0]:
                raise ValueError("original overlay has extra frames")
            process.stdin.close()
            if process.wait(timeout=60) != 0:
                raise ValueError("H264 encoder failed; see encoding.log")
        finally:
            cap.release()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    return output, snapshots


def run(plan_path, output):
    plan_path, output = Path(plan_path), Path(output)
    if output.exists():
        raise FileExistsError("new output directory required; existing results are immutable")
    plan_hash = sha256(plan_path)
    plan = read_json(plan_path)
    if plan["schema_version"] != "reviewed-export-plan-v1":
        raise ValueError("unsupported frozen plan")
    if sha256(plan_path) != plan_hash:
        raise ValueError("frozen plan changed while loading")
    tools = {name: bound_path(ROOT, record) for name, record in plan["runtime"].items()}
    for record in plan["implementation"].values():
        bound_path(ROOT, record)
    views = []
    sources_by_clip = []
    seen = set()
    for spec in plan["clips"]:
        if spec["pitch_id"] in seen or set(spec["sources"]) != REQUIRED_SOURCES:
            raise ValueError("duplicate clip or incomplete source bindings")
        seen.add(spec["pitch_id"])
        sources = {role: bound_path(ROOT, record) for role, record in spec["sources"].items()}
        view = derive_clip(spec, sources)
        meta = read_json(sources["video_metadata"])
        video_receipt(sources["original_video"], meta)
        video_receipt(sources["original_overlay"], meta)
        views.append(view)
        sources_by_clip.append(sources)
    if not views:
        raise ValueError("plan has no reviewed clips")
    output.mkdir(parents=True, exist_ok=False)
    receipts = []
    for view, sources in zip(views, sources_by_clip):
        outdir = output / view["pitch_id"]
        outdir.mkdir()
        meta = read_json(sources["video_metadata"])
        overlay, snapshots = render_overlay(sources["original_overlay"], outdir, view, meta, tools["ffmpeg"], tools["font"])
        receipt = video_receipt(overlay, meta, ffprobe=tools["ffprobe"], reviewed=True)
        receipt["pre_encoding_source_area_exact"] = True
        receipt["lossy_reencoding"] = True
        receipt["review_snapshot_files"] = snapshots
        view["export"] = {"overlay": "reviewed_overlay.mp4", "encoding": receipt,
                          "frozen_plan_sha256": plan_hash}
        write_new(outdir / "reviewed_reliability.json", view)
        receipts.append({"pitch_id": view["pitch_id"], "summary": view["summary"], "video": receipt})
    # Never change source artifacts, even when labels contradict predictions.
    for spec in plan["clips"]:
        for record in spec["sources"].values():
            bound_path(ROOT, record)
    for record in [*plan["runtime"].values(), *plan["implementation"].values()]:
        bound_path(ROOT, record)
    if sha256(plan_path) != plan_hash:
        raise ValueError("frozen plan changed during export")
    result = {"schema_version": "reviewed-export-receipt-v1", "status": "exported_not_phase2_acceptance",
              "frozen_plan_sha256": plan_hash, "source_hashes_verified_after_export": True,
              "total_frames": sum(r["summary"]["total_frames"] for r in receipts),
              "focus_joint_rows": sum(r["summary"]["focus_joint_rows"] for r in receipts), "clips": receipts}
    write_new(output / "export_summary.json", result)
    lines = ["# 五支 baseline 人工覆核視圖", "", "人工紀錄與原模型結果分開顯示；左方原始骨架未修正。",
             "這是已覆核影片的可用資料檢視，不是新的自動偵測或 Phase 2 通過宣告。", "",
             "播放 reviewed_overlay.mp4；逐格原因、資料狀態、限制與事件見 reviewed_reliability.json。", "",
             "模型 observed＝既有品質門檻下直接觀測，並不保證正確。interpolated 未經人工座標覆核；missing 保留缺失。", "",
             "not_observable 表示人工無法核對，不強迫推定位置正確、錯誤或遮擋原因。", ""]
    for view in views:
        pid = view["pitch_id"]
        lines.append(f"- [{pid} 影片]({pid}/reviewed_overlay.mp4) · [逐格資料]({pid}/reviewed_reliability.json)")
    (output / "START_HERE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.plan, args.output)
    print(json.dumps({"status": result["status"], "frames": result["total_frames"], "rows": result["focus_joint_rows"]}))
