"""Export descriptive native model-XY angles without running pose or a gate."""
from __future__ import annotations

import csv
from pathlib import Path

from .native_input import MANIFEST_NAME, SUMMARY_NAME, load_native_analysis_input
from .native_motion import describe_native_motion
from ..native_pose_io import BoundReader, reference, write_json


def _plot(rows: list[dict], pitch_id: str, output: Path) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(10, 6), dpi=140, layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 1, sharex=True)
    times = [row["timestamp_sec"] for row in rows]
    for axis, field, title, color in (
        (axes[0], "throwing_elbow_model_xy_deg", "Throwing elbow", "#1479b8"),
        (axes[1], "lead_knee_model_xy_deg", "Lead knee", "#cc6c18"),
    ):
        values = [row[field] if row[field] is not None else float("nan") for row in rows]
        axis.plot(times, values, color=color, linewidth=1.3)
        axis.set(title=title, ylabel="2D angle (degrees)", ylim=(-3, 183))
        axis.set_yticks([0, 45, 90, 135, 180])
        axis.grid(alpha=.22)
        axis.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xlabel("Seconds from clip frame 0 (no event alignment)")
    if len(rows) > 1:
        axes[-1].set_xlim(times[0], times[-1])
    figure.suptitle(f"{pitch_id} | saved model-XY projection\n"
                   "Pointwise quality unknown; occluded joints may still have model estimates", fontsize=11)
    figure.savefig(output, metadata={"Description": "Descriptive 2D model coordinates; uncalibrated; no interpolation or event alignment"})
    figure.clear()


def write_native_motion(root: str | Path, bundle_dir: str | Path, output: str | Path) -> dict:
    """Export complete raw projected curves to a fresh project output directory."""
    root = Path(root).resolve(strict=True)
    bundle = Path(bundle_dir)
    bundle = (bundle if bundle.is_absolute() else root / bundle).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Native motion output must be inside this project's analysis_results")
    if output.exists():
        raise FileExistsError("Native motion output already exists")
    refs = {"analysis_input_ref": reference(root, bundle / MANIFEST_NAME),
            "usage_summary_ref": reference(root, bundle / SUMMARY_NAME)}
    pitch = load_native_analysis_input(root, bundle)
    summary, rows = describe_native_motion(pitch)
    refs.update(pitch.manifest["source_refs"])
    reader = BoundReader(root, refs.values())
    for ref in refs.values():
        reader.path(ref)
    output.mkdir(parents=True, exist_ok=False)
    csv_path, plot_path = output / "motion_curves.csv", output / "motion_curves.png"
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _plot(rows, summary["pitch_id"], plot_path)
    for ref in refs.values():
        reader.path(ref)
    summary.update(source_refs=refs,
                   artifacts={"curves_ref": reference(root, csv_path), "plot_ref": reference(root, plot_path)},
                   new_inference_calls=0, new_tracking_replays=0, new_ground_truth_labels=0)
    write_json(output / "motion_summary.json", summary)
    return {"status": "descriptive_motion_complete", "pitch_id": summary["pitch_id"],
            "total_frames": summary["total_frames"], "scope": "descriptive_model_xy_projection",
            "usable_for_analysis": None, "new_inference_calls": 0}
