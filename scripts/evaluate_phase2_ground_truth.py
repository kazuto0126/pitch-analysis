"""Score Phase 2 predictions against independently reviewed annotations.

Writes a new comparison JSON; never edits source predictions, ground truth,
or the original baseline evaluation summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from pitch_analysis.ground_truth import load_ground_truth
from pitch_analysis.phase2_evaluation import evaluate_against_ground_truth


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise ValueError("Invalid pitch/pitcher identifier in baseline summary")
    return value


def _verify_binding(pitch: dict, pitcher_id: str, annotation: dict, pose: dict,
                    tracking: dict, analysis: Path) -> None:
    """Bind existing reports to the same video and frame order without inference."""
    metadata = _read(analysis / "video_metadata.json")
    manifest = _read(analysis / "input_manifest.json")
    raw = _read(analysis / "keypoints.json")
    capture = _read(analysis / "pose_raw.capture.json")
    pitch_id, total = pitch["pitch_id"], annotation["source_video"]["total_frames"]
    sha = annotation["source_video"]["sha256"]
    if metadata["status"] != "validated" or metadata["sha256"] != sha or pitch["video_sha256"] != sha:
        raise ValueError(f"Prediction/source hash mismatch for {pitch_id}")
    if metadata["frame_count"] != total or pitch["total_frames"] != total:
        raise ValueError(f"Prediction/source frame count mismatch for {pitch_id}")
    if (manifest["pitch_id"] != pitch_id or manifest["video"]["file"] != annotation["source_video"]["filename"]
            or manifest["pitcher"]["id"] != pitcher_id or raw["pitch_id"] != pitch_id
            or raw["pitcher_id"] != pitcher_id or pose["pitcher_id"] != pitcher_id
            or tracking["pitcher_id"] != pitcher_id):
        raise ValueError(f"Prediction subject binding mismatch for {pitch_id}")
    throwing = manifest["pitcher"]["throws"]
    if throwing not in ("LEFT", "RIGHT"):
        raise ValueError("Unknown throwing side")
    lead = "LEFT" if throwing == "RIGHT" else "RIGHT"
    expected = {f"throwing_{joint.lower()}": f"{throwing}_{joint}" for joint in ("SHOULDER", "ELBOW", "WRIST")}
    expected.update({f"lead_{joint.lower()}": f"{lead}_{joint}" for joint in ("HIP", "KNEE", "ANKLE")})
    if pose["important_joints"] != expected:
        raise ValueError(f"Joint roles differ from input handedness for {pitch_id}")
    if pose["source_artifacts"]["pose_clean_sha256"] != _sha256(analysis / "pose_clean.csv"):
        raise ValueError(f"Pose report no longer matches its source artifact for {pitch_id}")
    timeline = metadata["timestamps_ms"]
    frames = raw["frames"]
    if (len(timeline) != total or len(frames) != total
            or [f["frame_index"] for f in frames] != list(range(total))
            or any(not math.isfinite(t) for t in timeline)
            or timeline[0] != 0 or any(b <= a for a, b in zip(timeline, timeline[1:]))
            or any(not math.isfinite(f["timestamp_ms"]) or abs(f["timestamp_ms"] - t) > 1
                   for f, t in zip(frames, timeline))):
        raise ValueError(f"Raw prediction timestamps/timeline mismatch for {pitch_id}")
    selected = capture["selection_frames"]
    if ([f["frame_index"] for f in selected] != list(range(total))
            or [f["status"] for f in selected] != [f["selection_status"] for f in tracking["frames"]]
            or any(not math.isfinite(f["timestamp_ms"]) or abs(f["timestamp_ms"] - t) > 1
                   for f, t in zip(selected, timeline))):
        raise ValueError(f"Tracking report differs from raw selector states for {pitch_id}")
    for field, expected_value in (("requested_frames", total), ("processed_frames", total),
                                  ("start_frame", 0), ("end_frame", total - 1)):
        if field in capture and capture[field] != expected_value:
            raise ValueError(f"Raw capture {field} differs from the source timeline for {pitch_id}")


def _aggregate(comparisons: list[dict]) -> dict:
    available = [item["comparison"] for item in comparisons
                 if item["comparison"].get("review_profile") == "phase2_full_review"]
    if not available:
        return {}
    screens = {}
    for name in ("identity_switch_warning_agreement", "track_break_screening",
                 "major_pose_failure_screening", "major_pose_failure_with_joint_jump_cues"):
        fields = ("human_positive_frames", "human_negative_frames", "screened_frames_total",
                  "screened_excluded_frames", "true_positive_frames", "false_negative_frames",
                  "false_positive_frames", "true_negative_frames", "confirmed_interval_count",
                  "confirmed_intervals_with_any_screen")
        row = {field: sum(c[name][field] for c in available) for field in fields}
        tp, fp, positives = row["true_positive_frames"], row["false_positive_frames"], row["human_positive_frames"]
        row["recall_on_confirmed_frames"] = tp / positives if positives else None
        row["precision_on_scorable_frames"] = tp / (tp + fp) if tp + fp else None
        row["excluded_frames_by_status"] = {s: sum(c[name]["excluded_frames_by_status"][s] for c in available)
                                             for s in ("uncertain", "not_observable")}
        screens[name] = row
    joints = {}
    for role in available[0]["joint_reliability_agreement"]:
        rows = [c["joint_reliability_agreement"][role] for c in available]
        matrix = {h: {m: sum(r["human_label_by_model_state"][h][m] for r in rows)
                      for m in ("observed", "interpolated", "missing")}
                  for h in ("reliable", "unreliable", "uncertain", "not_observable")}
        joints[role] = {
            "human_label_by_model_state": matrix,
            "human_frame_counts": {h: sum(v.values()) for h, v in matrix.items()},
            "observed_but_human_unreliable_frames": matrix["unreliable"]["observed"],
            "observed_but_human_not_observable_frames": matrix["not_observable"]["observed"],
        }
    return {"full_review_pitch_count": len(available), "screening": screens, "joints": joints}


def evaluate_baseline(input_dir: Path, baseline_root: Path, output_path: Path) -> dict:
    input_dir = input_dir.resolve(strict=True)
    baseline_root = baseline_root.resolve(strict=True)
    if output_path.exists():
        raise FileExistsError(f"Comparison output already exists: {output_path}")
    baseline = _read(baseline_root / "evaluation_summary.json")
    pitcher_id = _identifier(baseline["pitcher_id"])
    pitch_ids = [_identifier(p["pitch_id"]) for p in baseline["pitches"]]
    if not pitch_ids or len(set(pitch_ids)) != len(pitch_ids) or baseline["pitch_count"] != len(pitch_ids):
        raise ValueError("Baseline pitch list is empty, duplicated or inconsistent")
    protected = {baseline_root / "evaluation_summary.json"}
    for pitch_id in pitch_ids:
        protected.add(input_dir / f"{pitch_id}.mp4")
        protected.add(baseline_root / "ground_truth" / pitch_id / "ground_truth.json")
        protected.update((baseline_root / "reliability" / pitch_id).glob("*.json"))
        protected.update(p for p in (baseline_root / "predictions" / pitcher_id / pitch_id).iterdir() if p.is_file())
    before = {path: _sha256(path) for path in protected}
    comparisons = []
    for pitch in baseline["pitches"]:
        pitch_id = pitch["pitch_id"]
        video = input_dir / f"{pitch_id}.mp4"
        reliability_dir = baseline_root / "reliability" / pitch_id
        pose = _read(reliability_dir / "pose_reliability.json")
        tracking = _read(reliability_dir / "tracking_reliability.json")
        ground_truth = load_ground_truth(
            baseline_root / "ground_truth" / pitch_id / "ground_truth.json",
            source_video_path=video,
        )
        analysis = baseline_root / "predictions" / pitcher_id / pitch_id
        _verify_binding(pitch, pitcher_id, ground_truth, pose, tracking, analysis)
        comparisons.append({
            "pitch_id": pitch_id,
            "total_frames": ground_truth["source_video"]["total_frames"],
            "reviewer": ground_truth["provenance"]["reviewer"],
            "ground_truth_reviewed_at_utc": ground_truth["provenance"]["reviewed_at_utc"],
            "ground_truth_status": ground_truth["annotation_status"],
            "comparison": evaluate_against_ground_truth(ground_truth, pose, tracking),
        })
    reviewed = sum(item["ground_truth_status"] == "reviewed" for item in comparisons)
    result = {
        "schema_version": "phase2-ground-truth-comparison-v2",
        "status": "human_comparison_available" if reviewed == len(comparisons) else "pending_human_ground_truth",
        "pitch_count": len(comparisons),
        "reviewed_count": reviewed,
        "baseline_root": str(baseline_root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total_frames": sum(p["total_frames"] for p in comparisons),
        "phase2_acceptance": "not_established_by_diagnostic_comparison",
        "aggregate": _aggregate(comparisons),
        "pitches": comparisons,
        "input_artifact_sha256": {
            ("baseline/" + path.relative_to(baseline_root).as_posix()
             if path.is_relative_to(baseline_root) else "source/" + path.name): sha
            for path, sha in sorted(before.items())
        },
    }
    if any(_sha256(path) != sha for path, sha in before.items()):
        raise ValueError("A comparison input changed during evaluation; no output written")
    result["input_artifacts_unchanged"] = True
    result["protected_artifact_count"] = len(before)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=False, allow_nan=False)
        target.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("baseline_root", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    result = evaluate_baseline(args.input_dir, args.baseline_root, args.output_path)
    print(json.dumps({"status": result["status"], "reviewed_count": result["reviewed_count"],
                      "pitch_count": result["pitch_count"], "output": str(args.output_path)}))


if __name__ == "__main__":
    main()
