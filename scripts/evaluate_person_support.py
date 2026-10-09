"""Offline, source-bound HOG feasibility audit; no automatic subject ownership."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import math
from pathlib import Path

import cv2

from measure_person_support import (create_detector, detect, read, sha, verify_execution,
                                    verify_sources, write)
from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.manual_keypoints import validate_manual_keypoints
from pitch_analysis.pose_capture import LANDMARK_NAMES


TORSO = ("LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP")


def compare_replay(expected, actual):
    for receipt in (expected, actual):
        if [candidate["candidate_index"] for candidate in receipt] != list(range(len(receipt))):
            raise ValueError("Candidate indexes must preserve each API receipt's native order")
        if any(candidate["subject_assignment"] is not None for candidate in receipt):
            raise ValueError("Unexpected candidate subject assignment")
    def values(candidate):
        return (*candidate["rectangle_xywh"], candidate["raw_svm_score"],
                candidate["entirely_inside_image"], candidate["subject_assignment"])
    return {"api_order_equal": expected == actual,
            "candidate_values_equal_ignoring_order": Counter(map(values, expected)) == Counter(map(values, actual))}


def contains(rectangle_xywh, point_xy):
    """Native image geometry only; membership of a point is not box identity."""
    x, y, w, h = rectangle_xywh
    px, py = point_xy
    return x <= px < x + w and y <= py < y + h


def torso_context(manual_frame, candidates):
    joints = {joint["name"]: joint for joint in manual_frame["joints"]}
    missing = [name for name in TORSO if joints[name]["status"] != "visible"]
    visible = {name: (joints[name]["x_px"], joints[name]["y_px"])
               for name in TORSO if name not in missing}
    rows = []
    for candidate in candidates:
        inside = [name for name, point in visible.items() if contains(candidate["rectangle_xywh"], point)]
        rows.append({"candidate_index": candidate["candidate_index"],
                     "visible_torso_points_inside": inside,
                     "visible_torso_points_outside": [name for name in visible if name not in inside],
                     "all_four_inside": len(inside) == 4 if not missing else None})
    return {"available": not missing, "missing_joint_names": missing, "candidates": rows}


def join_memberships(original, supplement):
    def key(query):
        point = query.get("image_xy_px", query.get("queried_image_xy_px"))
        if point is None or len(point) != 2 or not all(math.isfinite(v) for v in point):
            raise ValueError("Invalid membership position")
        return (query["frame_index"], *point)

    original_ids, references = {}, {}
    for query in original["queries"]:
        if query["query_id"] in original_ids or key(query) in references or query["human_code"] not in ("T", "P", "O", "?"):
            raise ValueError("Duplicate or invalid original membership")
        original_ids[query["query_id"]] = query
        references[key(query)] = [{"query_id": query["query_id"], "code": query["human_code"]}]
    seen = set(original_ids)
    for query in supplement["queries"]:
        prior = query["previous_query_id"]
        if query["query_id"] in seen or query["region_status"] != "human_confirmed" or query["resolved_code"] not in ("T", "P", "O", "?"):
            raise ValueError("Duplicate or unresolved supplementary membership")
        if prior is not None and (prior not in original_ids or key(query) != key(original_ids[prior])):
            raise ValueError("Recheck does not match the original position")
        if prior is None and key(query) in references:
            raise ValueError("Repeated position needs an explicit prior query link")
        seen.add(query["query_id"])
        references.setdefault(key(query), []).append({"query_id": query["query_id"],
            "actual_reply_code": query["actual_reply_code"], "code": query["resolved_code"]})
    return [{"frame_index": key[0], "image_xy_px": list(key[1:]),
             "latest_human_code": history[-1]["code"], "human_history": history}
            for key, history in sorted(references.items())]


def make_questions(frames, sampling):
    questions = []
    for frame in frames:
        if frame["frame_index"] not in sampling["frames"]:
            continue
        candidates = sorted(frame["candidates"], key=lambda c: (-c["raw_svm_score"], *c["rectangle_xywh"], c["candidate_index"]))
        for candidate in candidates[:sampling["max_boxes_per_frame"]]:
            questions.append({"query_id": f"pitch_003_f{frame['frame_index']:04d}_box{candidate['candidate_index']}",
                "frame_index": frame["frame_index"], "native_timestamp_ms": frame["native_timestamp_ms"],
                "decoded_bgr_sha256": frame["decoded_bgr_sha256"], **candidate,
                "reviewer": None, "reviewed_at_utc": None, "conclusion": None, "note": None,
                "raw_user_reply": None})
    if len(questions) > sampling["maximum_questions"]:
        raise ValueError("Fixed review budget exceeded")
    return questions


def protected_inventory(root, proposal):
    reference = proposal["protected_source_inventory"]
    path = root / reference["path"]
    if sha(path) != reference["sha256"]:
        raise ValueError("Protected inventory manifest changed")
    hashes = read(path)[reference["key"]]
    if len(hashes) != reference["physical_files"]:
        raise ValueError("Protected inventory denominator changed")
    verify_sources(root, {name: {"path": name, "sha256": value} for name, value in hashes.items()})
    return hashes


def verify_reviews(root, sources, measured, manual, canonical, original, supplement):
    video = root / sources["video"]["path"]
    validate_manual_keypoints(manual, source_video_path=video)
    validate_ground_truth(canonical, source_video_path=video)
    if any(data["annotation_status"] != "reviewed" for data in (manual, canonical)):
        raise ValueError("Unfinished reference")
    target = measured["target"]
    for data in (manual, canonical):
        source = data["source_video"]
        if (source["pitch_id"], source["total_frames"], source["frame_index_base"]) != (target["pitch_id"], target["total_frames"], 0):
            raise ValueError("Human reference timeline/identity mismatch")
    if manual["image_size"] != {"width": target["width"], "height": target["height"]}:
        raise ValueError("Manual pixel coordinate dimensions differ")
    for review in (original, supplement):
        if review["source_video"]["sha256"] != sources["video"]["sha256"]:
            raise ValueError("Membership video mismatch")
        for field in ("source_query_manifest", "source_video", "prior_review_version"):
            if field in review:
                verify_sources(root, {field: review[field]})
        for image in review["display_files"]:
            verify_sources(root, {"raw": {"path": image["raw_image"], "sha256": image["raw_sha256"]},
                                  "display": {"path": image["display_image"], "sha256": image["display_sha256"]}})
        for query in review["queries"]:
            frame = measured["frames"][query["frame_index"]]
            if not math.isclose(query["timestamp_ms"], frame["native_timestamp_ms"], abs_tol=1e-6, rel_tol=0):
                raise ValueError("Membership timestamp mismatch")
    if supplement["region_clarification_pending"] or supplement["review_status"] != "all_eight_memberships_confirmed":
        raise ValueError("Membership review unresolved")


def evaluate(root, plan_path, measurements, output):
    root, output = root.resolve(), output.resolve()
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("New evaluator output required within analysis_results")
    plan, measured = read(plan_path), read(measurements)
    measurement_sha = sha(measurements)
    verify_execution(root, plan, evaluator=True)
    proposal = read(root / plan["proposal_manifest"])
    if sha(root / proposal["proposal_path"]) != proposal["proposal_sha256"]:
        raise ValueError("Approved proposal document changed")
    if (plan["evaluator_sources"] != proposal["evaluator_only_sources"] or
        plan["review_sampling"] != proposal["review_if_evidence_exists"]):
        raise ValueError("Evaluator sources or sampling changed")
    verify_sources(root, plan["evaluator_sources"])
    inventory = protected_inventory(root, proposal)
    for field, expected in (("status", "sealed_measurements_only"), ("plan_sha256", sha(plan_path)),
                            ("producer_sha256", plan["producer_sha256"]), ("producer_sources", plan["producer_sources"]),
                            ("runtime", plan["runtime"]), ("parameters", plan["parameters"]),
                            ("detector_signature", plan["detector_signature"]), ("target", plan["target"]),
                            ("human_annotation_inputs", []), ("pose_inputs", []), ("warning_policy", None),
                            ("subject_assignment", None)):
        if measured[field] != expected:
            raise ValueError("Measurement receipt mismatch: " + field)
    count = plan["target"]["total_frames"]
    if [f["frame_index"] for f in measured["frames"]] != list(range(count)):
        raise ValueError("Incomplete or reordered measurement timeline")
    if any(f["warning_prediction"] is not None or f["subject_assignment"] is not None for f in measured["frames"]):
        raise ValueError("Measurement contains a per-frame warning or subject decision")
    data = {name: read(root / plan["evaluator_sources"][name]["path"])
            for name in ("capture", "manual_xy", "canonical_review", "membership_original", "membership_supplement")}
    manual, canonical = data["manual_xy"], data["canonical_review"]
    verify_reviews(root, plan["producer_sources"], measured, manual, canonical,
                   data["membership_original"], data["membership_supplement"])
    memberships = join_memberships(data["membership_original"], data["membership_supplement"])
    trace = data["capture"]["selection_frames"]
    if [f["frame_index"] for f in trace] != list(range(count)):
        raise ValueError("Baseline selection timeline mismatch")
    with (root / plan["evaluator_sources"]["original_raw"]["path"]).open(encoding="utf-8-sig", newline="") as handle:
        raw = list(csv.DictReader(handle))
    raw_by_frame = [dict() for _ in range(count)]
    for row in raw:
        index, name = int(row["frame"]), row["landmark"]
        if not 0 <= index < count or name not in LANDMARK_NAMES or name in raw_by_frame[index]:
            raise ValueError("Invalid or duplicate original raw row")
        if int(row["timestamp_ms"]) != trace[index]["timestamp_ms"]:
            raise ValueError("Raw and capture timestamps differ")
        raw_by_frame[index][name] = row
    if any(set(rows) != set(LANDMARK_NAMES) for rows in raw_by_frame):
        raise ValueError("Original raw frame/joint coverage differs")
    questions = make_questions(measured["frames"], plan["review_sampling"])
    output.mkdir(parents=True)
    hog, signature = create_detector()
    if signature != plan["detector_signature"]:
        raise ValueError("Verification detector changed")
    capture = cv2.VideoCapture(str(root / plan["producer_sources"]["video"]["path"]))
    rows = []
    try:
        for frame, manual_frame in zip(measured["frames"], manual["frames"], strict=True):
            index = frame["frame_index"]
            ok, pixels = capture.read()
            if not ok or pixels.shape != (plan["target"]["height"], plan["target"]["width"], 3):
                raise ValueError("Verification frame decode differs")
            if hashlib.sha256(pixels.tobytes()).hexdigest() != frame["decoded_bgr_sha256"]:
                raise ValueError("Verification native pixels differ")
            if not math.isclose(capture.get(cv2.CAP_PROP_POS_MSEC), frame["native_timestamp_ms"], rel_tol=0, abs_tol=1e-6):
                raise ValueError("Verification PTS differs")
            if trace[index]["timestamp_ms"] != round(frame["native_timestamp_ms"]) or not math.isclose(manual_frame["timestamp_ms"], frame["native_timestamp_ms"], rel_tol=0, abs_tol=1e-6):
                raise ValueError("Baseline/manual timeline mapping differs")
            replay = detect(hog, pixels)
            replay_check = compare_replay(frame["candidates"], replay)
            if not replay_check["candidate_values_equal_ignoring_order"]:
                raise ValueError("Independent replay changed candidates or scores")
            context = torso_context(manual_frame, frame["candidates"])
            candidates = []
            for candidate in frame["candidates"]:
                rectangle = candidate["rectangle_xywh"]
                visible_inside = [j["name"] for j in manual_frame["joints"] if j["status"] == "visible" and contains(rectangle, (j["x_px"], j["y_px"]))]
                raw_inside = [name for name, row in raw_by_frame[index].items()
                              if contains(rectangle, (float(row["x"]) * pixels.shape[1], float(row["y"]) * pixels.shape[0]))]
                candidates.append({**candidate, "visible_manual_joints_inside": visible_inside,
                                   "original_raw_joints_inside": raw_inside})
            major = any(interval["status"] == "confirmed" and interval["start_frame"] <= index <= interval["end_frame"]
                        for interval in canonical["labels"]["major_pose_failure_intervals"])
            rows.append({**frame, "torso_context": context, "candidate_context": candidates,
                         "replay_candidates": replay, "replay_check": replay_check,
                         "canonical_major_pose_failure": major})
            for question in (q for q in questions if q["frame_index"] == index):
                image = pixels.copy()
                x, y, w, h = question["rectangle_xywh"]
                cv2.rectangle(image, (x, y), (x + w - 1, y + h - 1), (0, 220, 255), 2)
                cv2.putText(image, f"frame {index} box {question['candidate_index']} / subject unreviewed", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .43, (0, 220, 255), 1)
                image_path = output / (question["query_id"] + ".png")
                if not cv2.imwrite(str(image_path), image):
                    raise ValueError("Cannot save review image")
                question.update({"image_path": image_path.relative_to(root).as_posix(), "image_sha256": sha(image_path)})
        if capture.read()[0]:
            raise ValueError("Verification has extra decoded frames")
    finally:
        capture.release()
    for membership in memberships:
        frame = measured["frames"][membership["frame_index"]]
        membership["candidate_indexes_containing_point"] = [c["candidate_index"] for c in frame["candidates"] if contains(c["rectangle_xywh"], membership["image_xy_px"])]
    total = sum(len(f["candidates"]) for f in rows)
    visibility = Counter(j["status"] for f in manual["frames"] for j in f["joints"])
    summary = {"status": "no_person_candidates" if not total else "candidates_require_independent_ownership_review",
        "frames": count, "candidate_rectangles": total, "frames_with_candidates": sum(bool(f["candidates"]) for f in rows),
        "frames_without_candidates": sum(not f["candidates"] for f in rows),
        "major_failure_frames": sum(f["canonical_major_pose_failure"] for f in rows),
        "major_failure_frames_with_candidates": sum(f["canonical_major_pose_failure"] and bool(f["candidates"]) for f in rows),
        "torso_proxy_available_frames": sum(f["torso_context"]["available"] for f in rows),
        "torso_proxy_unavailable_frames": sum(not f["torso_context"]["available"] for f in rows),
        "frames_with_all_four_torso_points_in_any_candidate": sum(any(c["all_four_inside"] is True for c in f["torso_context"]["candidates"]) for f in rows),
        "manual_joint_status_counts": dict(visibility), "membership_unique_positions": len(memberships),
        "latest_membership_counts": dict(Counter(m["latest_human_code"] for m in memberships)),
        "ownership_questions": len(questions), "ownership_answers": 0,
        "independent_replay_frames": count, "replay_candidate_differences": 0,
        "replay_api_order_difference_frames": [f["frame_index"] for f in rows if not f["replay_check"]["api_order_equal"]],
        "candidate_indexes_are_run_local": True,
        "original_raw_rows_checked": len(raw), "original_fn_frames_unchanged": 18,
        "warning_policy": None, "new_warning_counts": None, "pitcher_identity_accuracy": None, "box_iou": None,
        "phase2_automatic_reliability": "NOT PASSED"}
    verify_execution(root, plan, evaluator=True)
    verify_sources(root, plan["evaluator_sources"])
    protected_inventory(root, proposal)
    if sha(measurements) != measurement_sha:
        raise ValueError("Sealed receipt changed during evaluation")
    report = {"summary": summary, "plan_sha256": sha(plan_path), "measurements_sha256": measurement_sha,
        "evaluator_sha256": sha(__file__), "evaluator_sources": plan["evaluator_sources"],
        "frames": rows, "membership_context": memberships,
        "limits": ["A box can belong to a batter or another person; no automatic pitcher assignment",
                   "Four visible torso points are descriptive proxies, not a full-body box reference",
                   "Hidden/uncertain joint XY is excluded; raw SVM scores are not calibrated probabilities",
                   "Known development cases are not a holdout or an identity-switch sensitivity benchmark",
                   "No inference parameters, production algorithms, raw predictions or GT were changed"]}
    write(output / "person_support_evaluation.json", report)
    write(output / "ownership_questions.json", {"status": "unreviewed" if questions else "no_questions_no_candidates",
        "source_video": plan["producer_sources"]["video"], "measurements_sha256": measurement_sha,
        "sampling": plan["review_sampling"], "allowed_conclusions": ["pitcher", "other", "mixed", "uncertain"],
        "instruction": "Review the outlined rectangle's visible person ownership; never infer invisible anatomy", "questions": questions})
    write(output / "source_integrity_check.json", {"protected_physical_files": len(inventory),
        "unchanged": True, "protected_source_hashes": inventory, "producer_sources": plan["producer_sources"],
        "evaluator_sources": plan["evaluator_sources"], "sealed_measurements_sha256": measurement_sha})
    return summary


if __name__ == "__main__":
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_path", type=Path)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    print(json.dumps(evaluate(**vars(parser.parse_args())), indent=2))
