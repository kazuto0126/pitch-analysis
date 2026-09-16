from __future__ import annotations
import argparse
import json
from .config import QualityConfig
from .clean_pose import clean_pose
from .events import write_template
from .phases import build_phase_sequence
from .pipeline import build_features
from .pose_capture import extract_pose
from .comparison import write_comparison
from .reference import fit_reference_scaler, fit_registry_scaler
from .reference_set import compare_reference_set
from .registry import write_registry
from .ranking import rank_pitchers
from .media_audit import audit_videos
from .segmentation import write_motion_candidates
from .validation import leave_one_reference_out
from .release import build_library_release
from .workflow import prepare_segment, rebuild_library, rebuild_segment


def _emit(value: object) -> None:
    """Keep CLI output usable in Windows consoles that cannot encode all paths."""
    print(json.dumps(value, ensure_ascii=True, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Quality-aware 2-D pitching analysis.")
    commands = parser.add_subparsers(dest="command", required=True)
    clean = commands.add_parser("clean-pose")
    clean.add_argument("pose_csv")
    clean.add_argument("output_csv")
    clean.add_argument("--frame-width", type=int, help="Required for aspect-corrected legacy pose CSVs")
    clean.add_argument("--frame-height", type=int, help="Required for aspect-corrected legacy pose CSVs")
    clean.add_argument("--fps", type=float)
    clean.add_argument("--timeline-start-frame", type=int)
    clean.add_argument("--timeline-end-frame", type=int)
    features = commands.add_parser("build-features")
    features.add_argument("pose_csv")
    features.add_argument("output_csv")
    features.add_argument("--throwing-side", required=True, choices=("LEFT", "RIGHT"))
    template = commands.add_parser("event-template")
    template.add_argument("quality_report")
    template.add_argument("output_json")
    template.add_argument("--video-id", required=True)
    template.add_argument("--season")
    template.add_argument("--team")
    template.add_argument("--view")
    for event in ("pitch-start", "peak-leg-lift", "foot-strike", "release", "follow-through-end"):
        template.add_argument(f"--{event}-candidate", type=int)
    phases = commands.add_parser("build-phases")
    phases.add_argument("features_csv")
    phases.add_argument("events_json")
    phases.add_argument("output_csv")
    phases.add_argument("--points-per-phase", type=int, default=25)
    capture = commands.add_parser("extract-pose")
    capture.add_argument("video_path")
    capture.add_argument("output_csv")
    capture.add_argument("--model", default="models/pose_landmarker_full.task")
    capture.add_argument("--start-second", type=float, default=0.0)
    capture.add_argument("--end-second", type=float)
    compare = commands.add_parser("compare-phases")
    compare.add_argument("query_csv")
    compare.add_argument("reference_csv")
    compare.add_argument("output_json")
    compare.add_argument("--scaler")
    scaler = commands.add_parser("fit-reference-scaler")
    scaler.add_argument("output_json")
    scaler.add_argument("phase_csv", nargs="+")
    scaler.add_argument("--throws", required=True, choices=("LEFT", "RIGHT"))
    registry_scaler = commands.add_parser("fit-registry-scaler")
    registry_scaler.add_argument("registry_json")
    registry_scaler.add_argument("output_json")
    registry_scaler.add_argument("--throws", required=True, choices=("LEFT", "RIGHT"))
    compare_set = commands.add_parser("compare-reference-set")
    compare_set.add_argument("query_csv")
    compare_set.add_argument("output_json")
    compare_set.add_argument("reference_csv", nargs="+")
    compare_set.add_argument("--scaler")
    registry = commands.add_parser("build-registry")
    registry.add_argument("reference_root")
    registry.add_argument("output_json")
    rank = commands.add_parser("rank-pitchers")
    rank.add_argument("query_csv")
    rank.add_argument("reference_root")
    rank.add_argument("scaler_json")
    rank.add_argument("output_json")
    rank.add_argument("--query-throws", required=True, choices=("LEFT", "RIGHT"))
    rank.add_argument("--registry")
    rank.add_argument("--query-context")
    rank.add_argument("--camera-mode", default="exploratory", choices=("exploratory", "strict"))
    audit = commands.add_parser("audit-media")
    audit.add_argument("output_dir")
    audit.add_argument("video_path", nargs="+")
    audit.add_argument("--samples", type=int, default=12)
    audit.add_argument("--start-second", type=float, default=0.0)
    audit.add_argument("--end-second", type=float)
    prepare = commands.add_parser("prepare-segment")
    prepare.add_argument("video_path")
    prepare.add_argument("output_dir")
    prepare.add_argument("--video-id", required=True)
    prepare.add_argument("--throwing-side", required=True, choices=("LEFT", "RIGHT"))
    prepare.add_argument("--model", default="models/pose_landmarker_full.task")
    prepare.add_argument("--start-second", type=float, required=True)
    prepare.add_argument("--end-second", type=float, required=True)
    prepare.add_argument("--season")
    prepare.add_argument("--team")
    prepare.add_argument("--view")
    revalidate = commands.add_parser("revalidate-segment")
    revalidate.add_argument("segment_dir")
    revalidate_library = commands.add_parser("revalidate-library")
    revalidate_library.add_argument("reference_root")
    revalidate_library.add_argument("output_json")
    motion = commands.add_parser("detect-motion-windows")
    motion.add_argument("features_csv")
    motion.add_argument("output_json")
    motion.add_argument("--method", default="multi-feature-velocity", choices=("multi-feature-velocity", "foot-separation"))
    motion.add_argument("--feature-column", default="lateral_foot_separation_smoothed")
    motion.add_argument("--baseline-frames", type=int, default=15)
    motion.add_argument("--threshold-ratio", type=float, default=0.2)
    motion.add_argument("--merge-gap-frames", type=int, default=12)
    motion.add_argument("--min-window-frames", type=int, default=3)
    motion.add_argument("--pre-roll-frames", type=int, default=15)
    motion.add_argument("--post-roll-frames", type=int, default=20)
    motion.add_argument("--activity-quantile", type=float, default=0.70)
    motion.add_argument("--smoothing-radius", type=int, default=2)
    validate_ranking = commands.add_parser("validate-ranking")
    validate_ranking.add_argument("registry_json")
    validate_ranking.add_argument("output_json")
    validate_ranking.add_argument("--throws", required=True, choices=("LEFT", "RIGHT"))
    validate_ranking.add_argument("--camera-mode", default="exploratory", choices=("exploratory", "strict"))
    release = commands.add_parser("build-library-release")
    release.add_argument("reference_root")
    release.add_argument("release_dir")
    for command in (clean, features):
        command.add_argument("--min-visibility", type=float, default=0.5)
        command.add_argument("--min-presence", type=float, default=0.5)
    args = parser.parse_args()
    if args.command == "event-template":
        candidates = {name.replace("-", "_"): value for name, value in vars(args).items() if name.endswith("_candidate") and value is not None}
        context = {key: value for key, value in {"season": args.season, "team": args.team, "view": args.view}.items() if value}
        _emit(write_template(args.quality_report, args.output_json, args.video_id, candidates, context))
        return
    if args.command == "build-phases":
        annotation = json.loads(open(args.events_json, encoding="utf-8").read())
        features_to_align = ("throwing_knee_angle_smoothed", "lead_knee_angle_smoothed", "shoulder_line_angle_smoothed", "throwing_elbow_angle_smoothed", "hip_line_angle_smoothed", "lateral_foot_separation_smoothed")
        _emit(build_phase_sequence(args.features_csv, annotation, args.output_csv, features_to_align, args.points_per_phase))
        return
    if args.command == "extract-pose":
        _emit(extract_pose(args.video_path, args.model, args.output_csv, start_second=args.start_second, end_second=args.end_second))
        return
    if args.command == "compare-phases":
        _emit(write_comparison(args.query_csv, args.reference_csv, args.output_json, args.scaler))
        return
    if args.command == "fit-reference-scaler":
        _emit(fit_reference_scaler(args.phase_csv, args.output_json, throws=args.throws))
        return
    if args.command == "fit-registry-scaler":
        _emit(fit_registry_scaler(args.registry_json, args.output_json, throws=args.throws))
        return
    if args.command == "compare-reference-set":
        _emit(compare_reference_set(args.query_csv, args.reference_csv, args.output_json, args.scaler))
        return
    if args.command == "build-registry":
        _emit(write_registry(args.reference_root, args.output_json))
        return
    if args.command == "rank-pitchers":
        _emit(rank_pitchers(args.query_csv, args.reference_root, args.scaler_json, args.output_json, args.query_throws, registry_json=args.registry, query_context_json=args.query_context, camera_mode=args.camera_mode))
        return
    if args.command == "audit-media":
        _emit(audit_videos(args.video_path, args.output_dir, args.samples, args.start_second, args.end_second))
        return
    if args.command == "prepare-segment":
        context = {key: value for key, value in {"season": args.season, "team": args.team, "view": args.view}.items() if value}
        _emit(prepare_segment(args.video_path, args.output_dir, video_id=args.video_id, throwing_side=args.throwing_side, model_path=args.model, start_second=args.start_second, end_second=args.end_second, reference_context=context))
        return
    if args.command == "revalidate-segment":
        _emit(rebuild_segment(args.segment_dir))
        return
    if args.command == "revalidate-library":
        _emit(rebuild_library(args.reference_root, args.output_json))
        return
    if args.command == "detect-motion-windows":
        _emit(
            write_motion_candidates(
                args.features_csv,
                args.output_json,
                method=args.method,
                feature_column=args.feature_column,
                baseline_frames=args.baseline_frames,
                threshold_ratio=args.threshold_ratio,
                merge_gap_frames=args.merge_gap_frames,
                min_window_frames=args.min_window_frames,
                pre_roll_frames=args.pre_roll_frames,
                post_roll_frames=args.post_roll_frames,
                activity_quantile=args.activity_quantile,
                smoothing_radius=args.smoothing_radius,
            )
        )
        return
    if args.command == "validate-ranking":
        _emit(
            leave_one_reference_out(
                args.registry_json,
                args.output_json,
                throws=args.throws,
                camera_mode=args.camera_mode,
            )
        )
        return
    if args.command == "build-library-release":
        _emit(build_library_release(args.reference_root, args.release_dir))
        return
    quality = QualityConfig(min_visibility=args.min_visibility, min_presence=args.min_presence)
    if args.command == "clean-pose":
        context = {
            key: value
            for key, value in {
                "width": args.frame_width,
                "height": args.frame_height,
                "fps": args.fps,
                "timeline_start_frame": args.timeline_start_frame,
                "timeline_end_frame": args.timeline_end_frame,
            }.items()
            if value is not None
        }
        if bool(args.frame_width) != bool(args.frame_height):
            parser.error("--frame-width and --frame-height must be supplied together")
        _emit(clean_pose(args.pose_csv, args.output_csv, quality, capture_context=context))
    else:
        _emit(build_features(args.pose_csv, args.output_csv, throwing_side=args.throwing_side, quality=quality))


if __name__ == "__main__":
    main()
