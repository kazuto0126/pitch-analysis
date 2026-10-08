"""Expose saved offline reliability cues without GT, inference or new thresholds.

Jump candidates are current endpoints of adjacent observed samples. The cached
median/MAD uses the entire clip; these are review cues, not real-time detections
or proof of coordinate accuracy/identity. Original states and pixels are retained.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("throwing_shoulder", "throwing_elbow", "throwing_wrist", "lead_hip", "lead_knee", "lead_ankle")
STATES = {"observed", "interpolated", "missing"}
SIGNAL_STATUSES = {"reliable", "partially_reliable", "unreliable"}
SWITCH_WARNINGS = {"body_center_jump", "skeleton_scale_jump", "motion_discontinuity"}
REQUIRED_SOURCES = {"input_manifest", "video_metadata", "pose_clean", "processed_keypoints", "pose_reliability", "tracking_reliability", "original_overlay"}
ROLE_ZH = dict(zip(ROLES, ("投球肩", "投球肘", "投球腕", "前導髖", "前導膝", "前導踝")))
STATE_ZH = {"observed": "直接模型資料", "interpolated": "插值資料", "missing": "缺失"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, data):
    with Path(path).open("x", encoding="utf-8", newline="\n") as target:
        json.dump(data, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")


def bound_path(record):
    path = ROOT / record["path"]
    require(path.is_file() and sha256(path) == record["sha256"], f"source binding changed: {record['path']}")
    return path


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def same_number(actual, expected):
    # Floating serialization equality only, never an accuracy acceptance cutoff.
    if actual is None or expected is None:
        return actual is expected
    return finite(actual) and finite(expected) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12)


def role_mapping(throws):
    require(throws in {"RIGHT", "LEFT"}, "invalid throwing side")
    lead = "LEFT" if throws == "RIGHT" else "RIGHT"
    return {role: (throws if role.startswith("throwing_") else lead) + "_" + role.split("_")[1].upper() for role in ROLES}


def interval_frames(intervals, total):
    result, previous = set(), -1
    for item in intervals:
        start, end = item["start_frame"], item["end_frame"]
        require(type(start) is int and type(end) is int and previous < start <= end < total, "invalid tracking break interval")
        if "length_frames" in item:
            require(item["length_frames"] == end - start + 1, "tracking break length differs")
        result.update(range(start, end + 1))
        previous = end
    return result


def build_cues(pose, tracking, meta, processed_records):
    """Verify/re-expose six saved cue streams; no human labels are accepted."""
    total = meta["frame_count"]
    require(type(total) is int and total > 0, "positive complete frame count required")
    require(all(type(meta[k]) is int and meta[k] > 0 for k in ("width", "height")), "positive native dimensions required")
    require(finite(meta["fps"]) and meta["fps"] > 0, "positive native FPS required")
    indices = list(range(total))
    require(pose["total_frames"] == tracking["total_frames"] == total, "source frame-count mismatch")
    require(pose["pitch_id"] == tracking["pitch_id"] and isinstance(pose["pitch_id"], str) and pose["pitch_id"].strip(), "source pitch identity mismatch")
    require(pose["pitcher_id"] == tracking["pitcher_id"] and isinstance(pose["pitcher_id"], str) and pose["pitcher_id"].strip(), "source subject identifier mismatch")
    require(pose["status"] in SIGNAL_STATUSES and tracking["status"] in SIGNAL_STATUSES, "invalid provisional signal status")
    require(pose["frame_indices"] == indices and [f["frame_index"] for f in tracking["frames"]] == indices and [f["frame_index"] for f in processed_records] == indices, "complete ordered original timeline required")
    timestamps = meta["timestamps_ms"]
    require(len(timestamps) == total and all(finite(t) for t in timestamps) and all(a < b for a, b in zip(timestamps, timestamps[1:])), "invalid original timestamps")
    for record, timestamp in zip(processed_records, timestamps):
        require(same_number(record["timestamp_ms"], timestamp), "processed/original timestamp mismatch")
    mapping = pose["important_joints"]
    require(set(mapping) == set(ROLES), "exactly six existing focus roles required")
    throws = mapping["throwing_shoulder"].split("_")[0]
    require(mapping == role_mapping(throws), "focus-role/handedness mismatch")
    rejected = set()
    for f in tracking["frames"]:
        require(f["selection_status"] in {"selected", "rejected"} and isinstance(f["warnings"], list) and all(isinstance(w, str) for w in f["warnings"]), "invalid existing tracking frame")
        if f["selection_status"] == "rejected":
            rejected.add(f["frame_index"])
    require(interval_frames(tracking["track_breaks"], total) == rejected, "tracking break intervals differ from selection states")
    if "selected_frames" in tracking:
        require(tracking["selected_frames"] == total - len(rejected), "tracking selected count differs")
    event_frames = set()
    for event in tracking["warning_events"]:
        require(type(event["frame_index"]) is int and 0 <= event["frame_index"] < total and isinstance(event["type"], str), "invalid saved tracking event")
        if event["type"] in SWITCH_WARNINGS:
            event_frames.add(event["frame_index"])
    require(event_frames == {f["frame_index"] for f in tracking["frames"] if SWITCH_WARNINGS.intersection(f["warnings"])}, "tracking events and frame warnings differ")
    scale, streams, events = meta["width"] / meta["height"], {}, []
    for role in ROLES:
        name, saved = mapping[role], pose["joints"][mapping[role]]
        states = saved["frame_states"]
        require(len(states) == total and all(s in STATES for s in states) and saved["status"] in SIGNAL_STATUSES, "invalid joint state/signal timeline")
        points = []
        for state, record in zip(states, processed_records):
            point = record["landmarks"][name]
            require(all(type(point[k]) is bool for k in ("usable", "interpolated", "quality_valid")), "explicit processed provenance booleans required")
            xy_valid = finite(point.get("x")) and finite(point.get("y"))
            if state == "missing":
                require(not point["usable"] or not xy_valid, "missing state disagrees with usable processed coordinate")
            else:
                require(point["usable"] and xy_valid, "usable state needs finite saved XY")
                require(point["interpolated"] == (state == "interpolated"), "state differs from coordinate interpolation flag")
                if state == "observed":
                    require(point["quality_valid"], "observed coordinate lacks original quality validity")
            points.append(point)
        steps = {i: math.hypot((points[i]["x"] - points[i - 1]["x"]) * scale, points[i]["y"] - points[i - 1]["y"])
                 for i in range(1, total) if states[i - 1] == states[i] == "observed"}
        distances = list(steps.values())
        typical = median(distances) if distances else None
        mad = median(abs(d - typical) for d in distances) if distances else None
        threshold = max(0.05, typical + 6 * mad) if distances else None
        candidate_indices = [i for i, distance in steps.items() if distance > threshold] if distances else []
        cached = saved["frame_to_frame_jump"]
        require(cached["unit"] == "image_height_per_adjacent_frame", "unsupported cached jump unit")
        require(cached["observed_adjacent_pairs"] == len(steps) and cached["candidate_count"] == len(candidate_indices), "cached jump counts differ from original coordinates")
        require(cached["candidate_frames"] == candidate_indices and all(type(i) is int for i in cached["candidate_frames"]), "cached jump candidates differ from original coordinates")
        for key, expected in (("median", typical), ("median_absolute_deviation", mad), ("candidate_threshold", threshold), ("max", max(distances) if distances else None)):
            require(same_number(cached[key], expected), f"cached jump {key} differs from original coordinates")
        stream = []
        for i, state in enumerate(states):
            measured = i in steps
            cue_state = "saved_jump_candidate" if i in candidate_indices else ("no_saved_jump_candidate" if measured else "jump_not_measured")
            item = {"landmark": name, "model_state": state, "processed_landmark": deepcopy(points[i]),
                    "original_provisional_signal_status": saved["status"],
                    "jump": {"state": cue_state, "from_frame_index": i - 1 if measured else None, "to_frame_index": i,
                             "displacement": steps.get(i), "unit": cached["unit"], "cached_candidate_threshold": cached["candidate_threshold"],
                             "not_measured_reason": None if measured else ("no_previous_frame" if i == 0 else "both_adjacent_endpoints_must_be_observed")}}
            stream.append(item)
            if cue_state == "saved_jump_candidate":
                events.append({"frame_index": i, "timestamp_ms": timestamps[i], "role": role, "landmark": name, **deepcopy(item["jump"])})
        streams[role] = stream
    frames = [{"frame_index": i, "timestamp_ms": timestamps[i],
               "automatic_coordinate_alignment": "unverified", "automatic_subject_identity": "unverified",
               "existing_model_tracking": deepcopy(tracking["frames"][i]),
               "focus_joints": {role: streams[role][i] for role in ROLES}} for i in indices]
    events.sort(key=lambda e: (e["frame_index"], ROLES.index(e["role"])))
    counts = Counter(j["jump"]["state"] for f in frames for j in f["focus_joints"].values())
    return {"schema_version": "existing-reliability-cues-v1", "output_kind": "saved_offline_review_cues_not_new_detection",
            "pitch_id": pose["pitch_id"], "pitcher_id": pose["pitcher_id"], "important_joints": deepcopy(mapping),
            "mode": "offline_whole_clip_cached_policy", "human_labels_used": False,
            "automatic_coordinate_alignment": "unverified", "automatic_subject_identity": "unverified",
            "original_signal_quality": {"pose": pose["status"], "pose_reasons": deepcopy(pose["reasons"]), "tracking": tracking["status"], "tracking_reasons": deepcopy(tracking["reasons"])},
            "original_pose_policy": deepcopy(pose["policy"]), "original_tracking_warning_events": deepcopy(tracking["warning_events"]),
            "original_tracking_identity_switch_warning": tracking["identity_switch_warning"],
            "original_tracking_identity_switch_confirmed": tracking["identity_switch_confirmed"],
            "summary": {"total_frames": total, "focus_joint_rows": total * 6, "jump_state_counts": dict(counts),
                        "observed_adjacent_pairs": sum(counts[s] for s in ("saved_jump_candidate", "no_saved_jump_candidate")),
                        "jump_endpoint_events": len(events), "unique_cued_frames": len({e['frame_index'] for e in events}),
                        "model_state_counts": dict(Counter(j["model_state"] for f in frames for j in f["focus_joints"].values())),
                        "selector_rejected_frames": len(rejected)},
            "limitations": ["Signal quality and confidence do not establish coordinate accuracy or identity.",
                            "No saved cue does not certify alignment; unmeasured adjacent pairs are separate.",
                            "Whole-clip median/MAD uses future samples; no real-time issue time or latency is claimed.",
                            "Only the current endpoint is marked; no previous-frame or interval expansion.",
                            "Fast genuine motion can trigger a cue; interpolation remains unverified and missing remains missing.",
                            "No human review, GT, inference, new threshold or new automatic detector is used."],
            "frames": frames, "jump_events": events}


def check_clean_csv(path, report):
    """Bind saved CSV provenance to processed XY and original state arrays."""
    rows = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (int(row["frame"]), row["landmark"])
            require(key not in rows, "duplicate saved clean row")
            rows[key] = row
    def flag(value):
        require(value in {"True", "False", "true", "false"}, "invalid clean provenance flag")
        return value.lower() == "true"
    def number(value):
        if value == "":
            return None
        value = float(value)
        require(finite(value), "nonfinite saved clean coordinate")
        return value
    for frame in report["frames"]:
        for joint in frame["focus_joints"].values():
            row = rows[(frame["frame_index"], joint["landmark"])]
            point = joint["processed_landmark"]
            for key in ("usable", "interpolated", "quality_valid"):
                require(flag(row[key]) == point[key], "CSV/processed provenance differs")
            require(all(same_number(number(row[k]), point[k]) for k in ("x", "y")), "CSV/processed saved XY differs")
            if joint["model_state"] == "observed":
                require(flag(row["source_frame_detected"]) and all(same_number(number(row[k + "_raw"]), point[k]) for k in ("x", "y")), "observed coordinate differs from detected raw source")


def video_receipt(path, meta, extra_width=0, ffprobe=None):
    import cv2
    cap = cv2.VideoCapture(str(path))
    count = 0
    try:
        require(cap.isOpened() and math.isclose(cap.get(cv2.CAP_PROP_FPS), meta["fps"], abs_tol=1e-5), "video open/FPS mismatch")
        while True:
            ok, image = cap.read()
            if not ok:
                break
            require(image.shape[:2] == (meta["height"], meta["width"] + extra_width), "video geometry mismatch")
            count += 1
    finally:
        cap.release()
    require(count == meta["frame_count"], "decoded video frame-count mismatch")
    receipt = {"path": str(path), "sha256": sha256(path), "decoded_frames": count, "width": meta["width"] + extra_width, "height": meta["height"], "fps": meta["fps"]}
    if ffprobe:
        result = subprocess.run([str(ffprobe), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt", "-of", "json", str(path)], capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)["streams"][0]
        require(info["codec_name"] == "h264" and info["pix_fmt"] == "yuv420p", "expected H264/yuv420p export")
        receipt.update(info)
    return receipt


def compose_frame(image, frame, report, font_path):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    require(image.shape[0] >= 598, "panel needs native height >=598; source cannot be resized")
    panel = Image.new("RGB", (460, image.shape[0]), (20, 25, 34))
    draw = ImageDraw.Draw(panel)
    font, small, title = (ImageFont.truetype(str(font_path), size) for size in (19, 15, 23))
    white, gray, yellow = (235, 240, 245), (165, 180, 197), (235, 197, 107)
    draw.text((14, 8), report["pitch_id"] + "  既有自動覆核線索", font=title, fill=white)
    draw.text((14, 40), f"第 {frame['frame_index']} 格 · {frame['timestamp_ms']/1000:.3f} 秒", font=font, fill=white)
    draw.text((14, 69), "離線完整影片計算；不是即時錯位偵測", font=small, fill=gray)
    candidates = sum(j["jump"]["state"] == "saved_jump_candidate" for j in frame["focus_joints"].values())
    draw.rounded_rectangle((10, 93, 450, 133), radius=5, fill=(76, 61, 34) if candidates else (33, 47, 62))
    draw.text((18, 104), f"既有關節跳動：{candidates} 個目前端點待查看" if candidates else "此格無保存的跳動提示；對位仍未驗證", font=small, fill=yellow if candidates else white)
    track = frame["existing_model_tracking"]
    selection = "選取" if track["selection_status"] == "selected" else "拒絕／骨架中斷"
    draw.text((14, 143), f"原模型：{selection}　追蹤提示 {len(track['warnings'])} 項", font=small, fill=gray)
    draw.text((14, 164), "資料狀態與位置正確性分開；不讀人工答案", font=small, fill=gray)
    cue_zh = {"saved_jump_candidate": "跳動目前端點：待查看", "no_saved_jump_candidate": "已量測，未觸發既有界線", "jump_not_measured": "未量測相鄰直接觀測"}
    for n, role in enumerate(ROLES):
        j, y = frame["focus_joints"][role], 193 + n * 53
        draw.text((14, y), ROLE_ZH[role], font=font, fill=white)
        draw.text((116, y), STATE_ZH[j["model_state"]], font=font, fill=gray)
        draw.text((116, y + 25), cue_zh[j["jump"]["state"]], font=small, fill=yellow if j["jump"]["state"] == "saved_jump_candidate" else gray)
        draw.line((14, y + 48, 446, y + 48), fill=(45, 56, 71))
    for y, message in ((521, "無提示不代表正確；主體身分／對位未驗證。"), (544, "插值未認證；原骨架、座標與門檻均未修正。"), (567, "逐點量測、原模型提示與來源：見同目錄 JSON。")):
        draw.text((14, y), message, font=small, fill=gray)
    return np.concatenate((image, np.asarray(panel)[:, :, ::-1]), axis=1)


def render_overlay(source, directory, report, meta, runtime):
    import cv2
    output = directory / "autocue_overlay.mp4"
    require(not output.exists(), "fresh media path required")
    samples = {0, meta["frame_count"] - 1}
    for predicate in (lambda f: any(j["jump"]["state"] == "saved_jump_candidate" for j in f["focus_joints"].values()), lambda f: f["existing_model_tracking"]["selection_status"] == "rejected", lambda f: any(j["model_state"] == "interpolated" for j in f["focus_joints"].values())):
        hits = [f["frame_index"] for f in report["frames"] if predicate(f)]
        if hits:
            samples.update((hits[0], hits[-1]))
    cap, snapshots = cv2.VideoCapture(str(source)), []
    with (directory / "encoding.log").open("xb") as log:
        process = subprocess.Popen([str(runtime["ffmpeg"]), "-hide_banner", "-loglevel", "warning", "-nostdin", "-n", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{meta['width']+460}x{meta['height']}", "-r", format(meta["fps"], ".12g"), "-i", "pipe:0", "-an", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
        try:
            for frame in report["frames"]:
                ok, image = cap.read()
                require(ok, "original overlay ended early")
                composed = compose_frame(image, frame, report, runtime["font"])
                require((composed[:, :meta["width"]] == image).all(), "source panel changed before encoding")
                process.stdin.write(composed.tobytes())
                if frame["frame_index"] in samples:
                    name = f"cue_frame_{frame['frame_index']:04d}.png"
                    require(cv2.imwrite(str(directory / name), composed), "cue snapshot write failed")
                    snapshots.append(name)
            require(not cap.read()[0], "original overlay has extra frames")
            process.stdin.close()
            require(process.wait(timeout=60) == 0, "encoder failed; see encoding.log")
        finally:
            cap.release()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    receipt = video_receipt(output, meta, 460, runtime.get("ffprobe"))
    receipt.update({"pre_encoding_source_area_exact": True, "lossy_reencoding": True, "snapshots": snapshots})
    return receipt


def run(plan_path, output, *, render=False):
    plan_path, output = Path(plan_path), Path(output)
    if output.exists():
        raise FileExistsError("new output directory required")
    plan_hash, plan = sha256(plan_path), read_json(plan_path)
    require(plan["schema_version"] == "existing-reliability-cue-plan-v1" and sha256(plan_path) == plan_hash, "unsupported/changed frozen plan")
    require(str(plan.get("status", "")).startswith("frozen"), "frozen plan status required")
    implementation = [bound_path(r) for r in plan["implementation"].values()]
    require(Path(__file__).resolve() in [p.resolve() for p in implementation], "frozen plan must bind this producer")
    runtime = {name: bound_path(record) for name, record in plan.get("runtime", {}).items()}
    if render:
        require({"ffmpeg", "font"}.issubset(runtime), "rendering needs bound encoder/font")
    prepared, seen = [], set()
    for spec in plan["clips"]:
        keys = set(spec["sources"])
        require(keys in (REQUIRED_SOURCES, REQUIRED_SOURCES | {"original_video"}) and spec["pitch_id"] not in seen, "duplicate clip or unsupported sources; GT inputs are forbidden")
        seen.add(spec["pitch_id"])
        sources = {k: bound_path(v) for k, v in spec["sources"].items()}
        pose, tracking, meta, manifest = (read_json(sources[k]) for k in ("pose_reliability", "tracking_reliability", "video_metadata", "input_manifest"))
        records = [json.loads(line) for line in sources["processed_keypoints"].read_text(encoding="utf-8").splitlines()]
        require(manifest["pitch_id"] == spec["pitch_id"] == pose["pitch_id"] and manifest["pitcher"]["id"] == pose["pitcher_id"], "formal input/source identity differs")
        require(role_mapping(manifest["pitcher"]["throws"]) == pose["important_joints"], "formal throwing side differs")
        require(pose["source_artifacts"]["pose_clean_sha256"] == spec["sources"]["pose_clean"]["sha256"], "pose state clean-source hash differs")
        if "original_video" in sources:
            require(spec["sources"]["original_video"]["sha256"] == meta["sha256"] and sources["original_video"].name == manifest["video"]["file"], "original video binding differs")
        report = build_cues(pose, tracking, meta, records)
        check_clean_csv(sources["pose_clean"], report)
        report.update({"source_artifacts": deepcopy(spec["sources"]), "source_hashes_verified": True, "frozen_plan_sha256": plan_hash})
        if render:
            video_receipt(sources["original_overlay"], meta)
            require(meta["height"] >= 598, "source height cannot fit panel")
        prepared.append((report, sources, meta))
    require(prepared, "at least one bound clip required")
    output.mkdir(parents=True, exist_ok=False)
    for report, sources, meta in prepared:
        directory = output / report["pitch_id"]
        directory.mkdir()
        if render:
            report["rendered_overlay"] = render_overlay(sources["original_overlay"], directory, report, meta, runtime)
        write_new(directory / "automatic_reliability_cues.json", report)
        with (directory / "cue_index.csv").open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=("frame_index", "timestamp_ms", "role", "landmark", "model_state", "jump_state", "displacement", "cached_candidate_threshold", "automatic_coordinate_alignment", "automatic_subject_identity"))
            writer.writeheader()
            for frame in report["frames"]:
                for role, joint in frame["focus_joints"].items():
                    writer.writerow({"frame_index": frame["frame_index"], "timestamp_ms": frame["timestamp_ms"], "role": role, "landmark": joint["landmark"], "model_state": joint["model_state"], "jump_state": joint["jump"]["state"], "displacement": joint["jump"]["displacement"], "cached_candidate_threshold": joint["jump"]["cached_candidate_threshold"], "automatic_coordinate_alignment": "unverified", "automatic_subject_identity": "unverified"})
    for spec in plan["clips"]:
        for record in spec["sources"].values():
            bound_path(record)
    for record in [*plan["implementation"].values(), *plan.get("runtime", {}).values()]:
        bound_path(record)
    require(sha256(plan_path) == plan_hash, "frozen plan changed during export")
    summary = {"schema_version": "existing-reliability-cue-receipt-v1", "status": "exported_saved_cues_not_accuracy_acceptance", "frozen_plan_sha256": plan_hash, "source_hashes_verified_after_export": True, "rendered": render, "total_frames": sum(r["summary"]["total_frames"] for r, _, _ in prepared), "focus_joint_rows": sum(r["summary"]["focus_joint_rows"] for r, _, _ in prepared), "clips": [{"pitch_id": r["pitch_id"], "summary": r["summary"]} for r, _, _ in prepared]}
    write_new(output / "export_summary.json", summary)
    lines = ["# 既有離線自動覆核線索", "", "完整保留資料狀態與原模型提示。未讀人工答案、未修正骨架或改門檻。", "", "跳動只標目前端點；完整影片median/MAD不能冒充即時警示。無提示不代表位置或身分正確。", "", "全部影格與六關節保留；未量測、未觸發與跳動提示分開。JSON／CSV中的對位與身分一律未驗證。", ""]
    for report, _, _ in prepared:
        pid = report["pitch_id"]
        lines.append(f"- [{pid} 逐格資料]({pid}/automatic_reliability_cues.json) · [索引CSV]({pid}/cue_index.csv)" + (f" · [提示影片]({pid}/autocue_overlay.mp4)" if render else ""))
    with (output / "START_HERE.md").open("x", encoding="utf-8") as target:
        target.write("\n".join(lines) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.plan, args.output, render=args.render), ensure_ascii=False))
