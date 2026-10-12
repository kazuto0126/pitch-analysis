"""Evaluate a sealed developmental disagreement warning without changing GT.

The query clip is excluded from its empirical calibration. An out-of-reference
disagreement is a review warning, not an identity or coordinate-correctness fact.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
import evaluate_movenet_support as support
from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.phase2_evaluation import frame_ranges

STATES = ("warning", "candidate_dependent", "within_reference_range", "insufficient_evidence", "seed_excluded")
SCREENS = ("original_tracking_screen", "previous_additive_screen", "new_disagreement_screen", "additive_trial_screen")
ASSOCIATIONS = ("unique_geometric_candidate", "ambiguous", "none")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_trial_receipt(run, producer, producer_sha):
    if (run["status"] != "sealed_disagreement_warning_trial" or run["plan_sha256"] != producer_sha or
            run["producer_sha256"] != producer["code"]["producer_code"]["sha256"] or
            run["policy"] != producer["policy"] or run["human_annotation_inputs"] != [] or
            run["production_adoption"] is not False or run["source_frames"] != 592 or run["non_seed_frames"] != 587 or
            any(type(run[key]) is not int or run[key] != 0 for key in ("pose_inference_calls", "tracker_inference_calls"))):
        raise ValueError("Changed, contaminated, or incomplete warning receipt")


def verify_sidecar(data, target, source, run, producer_sha):
    if (data["status"] != "sealed_disagreement_warning_sidecar" or data["target"] != target or
            data["source_reference"] != source or data["plan_sha256"] != producer_sha or
            data["producer_sha256"] != run["producer_sha256"] or data["policy"] != run["policy"] or
            data["human_annotation_inputs"] != [] or data["production_adoption"] is not False or
            any(type(data[key]) is not int or data[key] != 0 for key in ("pose_inference_calls", "tracker_inference_calls"))):
        raise ValueError("Changed or contaminated warning sidecar binding")
    total = target["total_frames"]
    frames = data["frames"]
    if [frame["frame_index"] for frame in frames] != list(range(total)):
        raise ValueError("Incomplete, duplicate, or reordered warning timeline")
    for frame in frames:
        index, state = frame["frame_index"], frame["evidence_state"]
        if (type(index) is not int or state not in STATES or
                frame["effectiveness_eligible"] is not (index != 0) or
                frame["warning"] is not (state == "warning") or
                (state == "seed_excluded") != (index == 0)):
            raise ValueError("Invalid warning state, flag, or seed denominator")
    counts = Counter(frame["evidence_state"] for frame in frames[1:])
    expected = {state: counts[state] for state in STATES if state != "seed_excluded"}
    if data["state_counts_non_seed"] != expected:
        raise ValueError("Changed warning state summary")


def query_state_strata(frames):
    """Keep every non-seed query, including missing and ambiguous evidence."""
    by_association = {key: dict.fromkeys(STATES[:-1], 0) for key in ASSOCIATIONS}
    by_count = {str(key): dict.fromkeys(STATES[:-1], 0) for key in range(7)}
    for frame in frames:
        if not frame["effectiveness_eligible"]:
            continue
        association, count, state = (frame["association_status"],
            str(len(frame["candidate_slot_indices"])), frame["evidence_state"])
        if association not in by_association or count not in by_count or state not in STATES[:-1]:
            raise ValueError("Invalid query state stratum")
        by_association[association][state] += 1
        by_count[count][state] += 1
    return {"query_state_by_association": by_association, "query_state_by_candidate_count": by_count}


def score_screens(intervals, old, bbox, new, bbox_abstain, new_abstain, total):
    """Preserve all old warnings; missing evidence stays in exact denominators."""
    old, bbox, new, bbox_abstain, new_abstain = map(set, (old, bbox, new, bbox_abstain, new_abstain))
    previous, combined = old | bbox, old | bbox | new
    scores = {
        "original_tracking_screen": support.score(intervals, old, set(), total),
        "previous_additive_screen": support.score(intervals, previous, bbox_abstain - old, total),
        "new_disagreement_screen": support.score(intervals, new, new_abstain, total),
        "additive_trial_screen": support.score(intervals, combined, (bbox_abstain & new_abstain) - old, total),
    }
    eligible = set(range(1, total))
    positive, excluded = set(), set()
    for span in intervals:
        frames = set(range(span["start_frame"], span["end_frame"] + 1))
        if span.get("status", "confirmed") == "confirmed":
            positive |= frames
        else:
            excluded |= frames
    negative = eligible - positive - excluded
    added = (new - previous) & eligible
    caught, false_positive = added & positive, added & negative
    remaining = (positive & eligible) - combined
    scores["change_from_previous"] = {
        "added_warning_count": len(added), "added_warning_ranges": frame_ranges(added),
        "newly_caught_major_count": len(caught), "newly_caught_major_ranges": frame_ranges(caught),
        "added_false_positive_count": len(false_positive), "added_false_positive_ranges": frame_ranges(false_positive),
        "added_human_excluded_count": len(added & excluded),
        "remaining_false_negative_count": len(remaining), "remaining_false_negative_ranges": frame_ranges(remaining),
        "previous_warnings_preserved": previous <= combined,
    }
    return scores


def evaluate(root, plan_path, run_path, output):
    import measure_disagreement_warning as producer_module

    root, plan_path, run_path, output = (Path(p).resolve() for p in (root, plan_path, run_path, output))
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive evaluation output required")
    plan, run = read(plan_path), read(run_path)
    plan_sha, run_sha = sha(plan_path), sha(run_path)
    if plan["status"] != "frozen_before_disagreement_warning_evaluation":
        raise ValueError("Unfrozen warning evaluation plan")
    producer_path = bound(root, plan["producer_plan"])
    producer, producer_sha = read(producer_path), sha(producer_path)
    producer_module.verify_plan(root, producer)
    refs = [plan["producer_plan"], *plan["code"].values(), *producer["code"].values(), *run["clips"]]
    for ref in refs:
        bound(root, ref)
    verify_trial_receipt(run, producer, producer_sha)
    if (producer["policy"] != producer_module.POLICY or
            producer["code"]["producer_code"]["sha256"] != sha(producer_module.__file__) or
            plan["code"]["evaluator"]["sha256"] != sha(__file__) or
            plan["code"]["support_evaluator"]["sha256"] != sha(support.__file__)):
        raise ValueError("Running producer/evaluator differs from frozen policy or code")
    names = [clip["target"]["pitch_id"] for clip in plan["clips"]]
    if (len(names) != 5 or len(set(names)) != 5 or
            names != [c["target"]["pitch_id"] for c in producer["clips"]] or
            names != [c["pitch_id"] for c in run["clips"]] or
            sum(c["target"]["total_frames"] for c in plan["clips"]) != 592):
        raise ValueError("Changed five-clip cohort denominator")
    loaded, measurements = [], []
    for setup, binding, source in zip(plan["clips"], run["clips"], producer["clips"], strict=True):
        refs.extend([*setup["sources"].values(), source["source"]])
        for ref in [*setup["sources"].values(), source["source"]]:
            bound(root, ref)
        target, total = setup["target"], setup["target"]["total_frames"]
        if source["target"] != target:
            raise ValueError("Producer and evaluator targets differ")
        data, measurement = read(bound(root, binding)), read(bound(root, source["source"]))
        verify_sidecar(data, target, source["source"], run, producer_sha)
        if (measurement["status"] != "sealed_joint_disagreement_only" or measurement["target"] != target or
                measurement["human_annotation_inputs"] != [] or measurement["production_adoption"] is not False or
                any(type(measurement[key]) is not int or measurement[key] != 0
                    for key in ("pose_inference_calls", "tracker_inference_calls")) or
                measurement["source_references"]["capture"] != setup["sources"]["capture"]):
            raise ValueError("Invalid source measurement or original capture binding")
        capture = read(bound(root, setup["sources"]["capture"]))
        tracking = read(bound(root, setup["sources"]["tracking"]))
        bbox = read(bound(root, setup["sources"]["bbox_support"]))
        if (tracking["pitch_id"] != target["pitch_id"] or tracking["total_frames"] != total or
                bbox["status"] != "sealed_support_diagnostics_only" or bbox["target"] != target or
                bbox["human_annotation_inputs"] != [] or bbox["production_adoption"] is not False or
                any(type(bbox[key]) is not int or bbox[key] != 0
                    for key in ("pose_inference_calls", "tracker_inference_calls")) or
                bbox["source_references"]["capture"] != setup["sources"]["capture"] or
                [f["frame_index"] for f in bbox["frames"]] != list(range(total)) or
                any(f["status"] not in ("warning", "no_warning", "insufficient_evidence") for f in bbox["frames"])):
            raise ValueError("Changed original tracking or bbox denominator/binding")
        support.verify_tracking_timeline(tracking, data["frames"], capture, total)
        if any(frame["capture_timestamp_ms"] != old["timestamp_ms"]
               for frame, old in zip(data["frames"], capture["selection_frames"], strict=True)):
            raise ValueError("Changed original capture timestamp")
        video = bound(root, setup["sources"]["video"])
        capture_video = Path(capture["video"])
        if not capture_video.is_absolute():
            capture_video = root / capture_video
        if (capture_video.resolve() != video or
                tuple(capture[key] for key in ("width", "height", "start_frame", "end_frame", "requested_frames", "processed_frames")) !=
                (target["width"], target["height"], 0, total - 1, total, total)):
            raise ValueError("Ground truth video differs from measured source")
        loaded.append((setup, data, tracking, bbox, video))
        measurements.append(measurement)
    recomputed = producer_module.make_sidecars(measurements)
    if len(recomputed) != len(loaded):
        raise ValueError("Incomplete sidecar recomputation")
    for (_, data, _, _, _), expected in zip(loaded, recomputed, strict=True):
        if any(data[key] != expected[key] for key in ("target", "calibration", "frames", "state_counts_non_seed")):
            raise ValueError("Warning state or calibration differs from GT-free recomputation")
    reports = []
    for setup, data, tracking, bbox, video in loaded:
        target, total = setup["target"], setup["target"]["total_frames"]
        canonical = read(bound(root, setup["sources"]["canonical_review"]))
        validate_ground_truth(canonical, source_video_path=video)
        if (canonical["annotation_status"] != "reviewed" or canonical["review_profile"] != "phase2_full_review" or
                tuple(canonical["source_video"][key] for key in ("pitch_id", "total_frames", "sha256")) !=
                (target["pitch_id"], total, setup["sources"]["video"]["sha256"])):
            raise ValueError("Wrong or incomplete canonical review")
        old = {f["frame_index"] for f in tracking["frames"] if f["selection_status"] != "selected" or f["warnings"]}
        previous = {f["frame_index"] for f in bbox["frames"] if f["status"] == "warning"}
        bbox_abstain = {f["frame_index"] for f in bbox["frames"] if f["status"] == "insufficient_evidence"}
        new = {f["frame_index"] for f in data["frames"] if f["warning"]}
        new_abstain = {f["frame_index"] for f in data["frames"] if f["evidence_state"] == "insufficient_evidence"}
        reports.append({"pitch_id": target["pitch_id"], "source_frames": total, "non_seed_frames": total - 1,
            "calibration": data["calibration"], "state_counts_non_seed": data["state_counts_non_seed"],
            **query_state_strata(data["frames"]),
            **score_screens(canonical["labels"]["major_pose_failure_intervals"], old, previous, new,
                            bbox_abstain, new_abstain, total)})
    for ref in refs:
        bound(root, ref)
    producer_module.verify_plan(root, producer)
    if sha(plan_path) != plan_sha or sha(run_path) != run_sha:
        raise ValueError("Evidence changed during evaluation")
    counts = Counter()
    for report in reports:
        counts.update(report["state_counts_non_seed"])
    result = {"status": "complete_offline_disagreement_warning_evaluation", "plan_sha256": plan_sha,
        "run_sha256": run_sha, "policy": producer["policy"], "source_frames": 592, "non_seed_frames": 587,
        "clips": reports, "state_counts_non_seed": dict(counts),
        **query_state_strata([frame for _, data, _, _, _ in loaded for frame in data["frames"]]),
        "aggregate": {key: support.aggregate([report[key] for report in reports]) for key in SCREENS},
        "change_from_previous": {key: sum(report["change_from_previous"][key] for report in reports) for key in
            ("added_warning_count", "newly_caught_major_count", "added_false_positive_count", "added_human_excluded_count", "remaining_false_negative_count")},
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "phase2_automatic_reliability": "NOT PASSED",
        "interpretation": "Developmental leave-one-clip-out empirical range, not untouched generalization or calibrated false-alarm probability. Candidate-dependent states issue no major warning and remain in denominators. Missing evidence remains in major denominators. Old warnings are preserved; model disagreement is not confirmed identity or coordinate error."}
    output.mkdir()
    write(output / "disagreement_warning_evaluation.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "run", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = evaluate(Path(__file__).resolve().parents[1], args.plan, args.run, args.output)
    print(json.dumps(report["aggregate"]))
