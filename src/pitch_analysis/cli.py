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
    skeleton_prepare = commands.add_parser("prepare-skeleton", help="Standard skeleton flow: prepare numbered first-frame people for operator selection")
    skeleton_prepare.add_argument("mp4")
    skeleton_prepare.add_argument("metadata_json")
    skeleton_prepare.add_argument("--fps-fraction", required=True, help="Verified source FPS, e.g. 30 or 60000/1001")
    skeleton_prepare.add_argument("--runtime-config", default="config/seeded_skeleton_runtime.json")
    skeleton_prepare.add_argument("--output", required=True)
    skeleton_run = commands.add_parser("extract-skeleton", help="Standard skeleton flow: operator-seeded person tracking and native COCO17 pose")
    skeleton_run.add_argument("preparation_json")
    skeleton_run.add_argument("seed_json")
    skeleton_run.add_argument("--output", required=True)
    native_input = commands.add_parser("prepare-analysis-input", help="Prepare a read-only analysis input from saved native COCO17 pose, tracking and human overlay acceptance")
    native_input.add_argument("native_dir")
    native_input.add_argument("metadata_json")
    native_input.add_argument("--subject-track", required=True)
    native_input.add_argument("--human-review", required=True)
    native_input.add_argument("--output", required=True)
    native_reliability = commands.add_parser("report-native-reliability", help="Describe saved native joint and tracking continuity without inference or quality thresholds")
    native_reliability.add_argument("analysis_input_dir")
    native_reliability.add_argument("--output", required=True)
    native_motion = commands.add_parser("describe-native-motion", help="Export 2D elbow and lead-knee curves from accepted saved native skeletons")
    native_motion.add_argument("analysis_input_dir")
    native_motion.add_argument("--output", required=True)
    motion_viewer = commands.add_parser("review-native-motion", help="Build a local frame-linked viewer of saved native motion curves and overlays")
    motion_viewer.add_argument("motion_dirs", nargs="+")
    motion_viewer.add_argument("--output", required=True)
    event_comparison = commands.add_parser("compare-native-motion-events", help="Describe saved same-pitcher curves at existing manual event frames or ranges")
    event_comparison.add_argument("config_json")
    event_comparison.add_argument("--output", required=True)
    descriptive_profile = commands.add_parser("describe-native-profile", help="Summarize one pitcher's source-bound manual timings and model-XY endpoints")
    descriptive_profile.add_argument("event_report_json")
    descriptive_profile.add_argument("--output", required=True)
    profile_viewer = commands.add_parser("review-native-profile", help="Link a saved single-pitcher profile to independent source-frame players")
    profile_viewer.add_argument("profile_json")
    profile_viewer.add_argument("--output", required=True)
    motion_report = commands.add_parser("build-native-motion-report", help="Build events, a single-pitcher profile and source review from saved curves with one entry")
    motion_report.add_argument("config_json")
    motion_report.add_argument("--output", required=True)
    motion_report.add_argument("--include-stage-curves", action="store_true", help="Add interior model-XY sample ranges under all legal manual event choices")
    stage_curves = commands.add_parser("describe-native-stage-curves", help="Describe saved interior model-XY samples for all legal manual event intervals")
    stage_curves.add_argument("event_report_json")
    stage_curves.add_argument("--output", required=True)
    timing_comparison = commands.add_parser("compare-native-timing", help="Compare source-bound manual event durations for two pitchers using exact fractional seconds")
    timing_comparison.add_argument("report_a")
    timing_comparison.add_argument("report_b")
    timing_comparison.add_argument("--output", required=True)
    timing_viewer = commands.add_parser("review-native-timing", help="Build two independent source-frame players for a saved manual timing comparison")
    timing_viewer.add_argument("comparison_json")
    timing_viewer.add_argument("--output", required=True)
    motion_alignment = commands.add_parser("align-native-motion", help="Plot saved same-pitcher curves relative to exact human foot plant")
    motion_alignment.add_argument("config_json")
    motion_alignment.add_argument("--output", required=True)
    motion_alignment.add_argument("--retain-anchor-ranges", action="store_true", help="Retain all annotated foot-plant candidates as display-time bounds")
    alignment_viewer = commands.add_parser("review-native-motion-alignment", help="Build a source-frame-linked viewer of foot-plant-aligned curves")
    alignment_viewer.add_argument("config_json")
    alignment_viewer.add_argument("--output", required=True)
    analyze = commands.add_parser("analyze-pitch", help="Analyze one prepared local MP4 plus pitch-input-v1 metadata")
    analyze.add_argument("mp4")
    analyze.add_argument("metadata_json")
    analyze.add_argument("--output-root", default="analysis_results")
    analyze.add_argument("--model", default="models/pose_landmarker_full.task")
    analyze.add_argument("--standardize", action="store_true", help="Create H.264/yuv420p working copy at native FPS")
    validate = commands.add_parser("validate-pitch", help="Validate metadata and decode a prepared MP4 without pose inference")
    validate.add_argument("mp4")
    validate.add_argument("metadata_json")
    input_quality = commands.add_parser("validate-input-quality", help="Run conservative video-only input preflight before pose analysis")
    input_quality.add_argument("mp4")
    input_quality.add_argument("metadata_json")
    input_quality.add_argument("--output", help="Optional new input-quality JSON report path")
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
    capture = commands.add_parser("extract-pose", help="Legacy MediaPipe feature input; use extract-skeleton for the standard skeleton workflow")
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
    if args.command == "review-native-motion-alignment":
        from pathlib import Path
        from .analysis.native_motion_alignment_viewer import write_alignment_viewer
        try:
            result = write_alignment_viewer(Path.cwd(), args.config_json, args.output)
            _emit({"status": result["status"], "clip_count": result["clip_count"],
                   "source_frames": result["source_frames"], "output_dir": args.output,
                   "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "align-native-motion":
        from pathlib import Path
        from .analysis.native_motion_alignment import write_native_alignment
        writer = write_native_alignment
        if args.retain_anchor_ranges:
            from .analysis.native_motion_anchor_bounds import write_bounded_alignment
            writer = write_bounded_alignment
        try:
            result = writer(Path.cwd(), args.config_json, args.output)
            _emit({"status": result["status"], "clip_count": result["clip_count"],
                   "source_frames": result["source_frames"], "output_dir": args.output,
                   "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "describe-native-stage-curves":
        from pathlib import Path
        from .analysis.native_stage_curves import write_stage_curves
        try:
            result = write_stage_curves(Path.cwd(), args.event_report_json, args.output)
            _emit({"status": result["status"], "pitcher_id": result["pitcher_id"],
                   "clip_count": result["summary"]["clip_count"], "stage_count": result["summary"]["stage_count"],
                   "output_dir": args.output, "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, ZeroDivisionError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "build-native-motion-report":
        from pathlib import Path
        from .analysis.native_motion_delivery import write_motion_report
        try:
            options = {"include_stage_curves": True} if args.include_stage_curves else {}
            result = write_motion_report(Path.cwd(), args.config_json, args.output, **options)
            _emit({"status": result["status"], "pitcher_id": result["pitcher_id"],
                   "clip_count": result["clip_count"], "source_frames": result["source_frames"],
                   "output_dir": args.output, "entry": str(Path(args.output) / "START_HERE.html"),
                   "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, ZeroDivisionError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "review-native-profile":
        from pathlib import Path
        from .analysis.native_profile_viewer import write_profile_viewer
        try:
            result = write_profile_viewer(Path.cwd(), args.profile_json, args.output)
            _emit({"status": result["status"], "clip_count": result["clip_count"],
                   "total_pairs": result["total_pairs"], "output_dir": args.output,
                   "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, ZeroDivisionError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "describe-native-profile":
        from pathlib import Path
        from .analysis.native_descriptive_profile import write_descriptive_profile
        try:
            result = write_descriptive_profile(Path.cwd(), args.event_report_json, args.output)
            _emit({"status": result["status"], "pitcher_id": result["pitcher_id"],
                   "clip_count": result["summary"]["clip_count"], "output_dir": args.output,
                   "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, ZeroDivisionError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "review-native-timing":
        from pathlib import Path
        from .analysis.native_timing_viewer import write_timing_viewer
        try:
            result = write_timing_viewer(Path.cwd(), args.comparison_json, args.output)
            _emit({"status": result["status"], "clip_count": result["clip_count"],
                   "total_pairs": result["total_pairs"], "output_dir": args.output,
                   "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, ZeroDivisionError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "compare-native-timing":
        from pathlib import Path
        from .analysis.native_timing_comparison import write_timing_comparison
        try:
            result = write_timing_comparison(Path.cwd(), [args.report_a, args.report_b], args.output)
            _emit({"status": result["status"], "total_pairs": result["total_pairs"],
                   "comparable_pairs": result["comparable_pairs"], "unavailable_pairs": result["unavailable_pairs"],
                   "output_dir": args.output, "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, ZeroDivisionError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "compare-native-motion-events":
        from pathlib import Path
        from .analysis.native_motion_events import write_event_comparison
        try:
            result = write_event_comparison(Path.cwd(), args.config_json, args.output)
            _emit({"status": result["status"], "clip_count": result["clip_count"],
                   "source_frames": result["source_frames"], "output_dir": args.output,
                   "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "review-native-motion":
        from pathlib import Path
        from .analysis.native_motion_viewer import write_motion_viewer
        try:
            result = write_motion_viewer(Path.cwd(), args.motion_dirs, args.output)
            _emit({"status": result["status"], "clip_count": result["clip_count"], "source_frames": result["source_frames"],
                   "output_dir": args.output, "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError, KeyError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "describe-native-motion":
        from pathlib import Path
        from .analysis.native_motion_report import write_native_motion
        try:
            result = write_native_motion(Path.cwd(), args.analysis_input_dir, args.output)
            _emit({**result, "output_dir": args.output})
        except (ValueError, OSError, RuntimeError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "report-native-reliability":
        from pathlib import Path
        from .analysis.native_reliability import write_native_reliability
        try:
            result = write_native_reliability(Path.cwd(), args.analysis_input_dir, args.output)
            _emit({**result, "output_dir": args.output})
        except (ValueError, OSError, RuntimeError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command == "prepare-analysis-input":
        from pathlib import Path
        from .analysis.native_input import prepare_native_analysis_input
        try:
            result = prepare_native_analysis_input(Path.cwd(), args.native_dir, args.metadata_json,
                                                  args.subject_track, args.human_review, args.output)
            _emit({"status": result["status"], "pitch_id": result["pitch_id"],
                   "output_dir": args.output, "new_inference_calls": 0})
        except (ValueError, OSError, RuntimeError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command in {"prepare-skeleton", "extract-skeleton"}:
        from pathlib import Path
        try:
            if args.command == "prepare-skeleton":
                from .native_skeleton_prepare import prepare_skeleton
                result = prepare_skeleton(Path.cwd(), args.mp4, args.metadata_json, args.runtime_config,
                                          args.output, fps_fraction=args.fps_fraction)
                _emit({"status": result["status"], "pitch_id": result["pitch_id"],
                       "output": args.output, "display_choices": result["display_choices"],
                       "pose_calls": result["pose_calls_during_preparation"]})
            else:
                from .seeded_skeleton import run_seeded_skeleton
                _emit(run_seeded_skeleton(Path.cwd(), args.preparation_json, args.seed_json, args.output))
        except (ValueError, OSError, RuntimeError) as error:
            _emit({"status": "failed", "error": str(error)})
            raise SystemExit(1)
        return
    if args.command in {"analyze-pitch", "validate-pitch", "validate-input-quality"}:
        try:
            if args.command == "analyze-pitch":
                from .analysis.pitch import analyze_pitch
                result = analyze_pitch(args.mp4, args.metadata_json, output_root=args.output_root, model_path=args.model, standardize=args.standardize)
            elif args.command == "validate-pitch":
                from .contracts import load_input
                from .video.validation import validate_mp4
                load_input(args.mp4, args.metadata_json)
                result = validate_mp4(args.mp4)
            else:
                from pathlib import Path
                from .contracts import load_input, write_contract
                from .video.validation import validate_mp4
                from .video.input_quality import scan_input_quality
                load_input(args.mp4, args.metadata_json)
                result = scan_input_quality(validate_mp4(args.mp4))
                if args.output:
                    target = Path(args.output)
                    if target.exists():
                        raise FileExistsError(f"Input-quality report already exists: {target}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    write_contract(target, result, "input-quality-v1")
            _emit(result)
        except (ValueError, OSError, RuntimeError) as error:
            parser.exit(2, f"{type(error).__name__}: {error}\n")
        return
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
