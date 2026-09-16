"""Build an auditable reference-library release with one command."""
from __future__ import annotations

import json
from pathlib import Path

from .config import QualityConfig
from .reference import fit_registry_scaler
from .registry import write_registry
from .validation import leave_one_reference_out
from .workflow import rebuild_library


def build_library_release(
    reference_root: str | Path,
    release_dir: str | Path,
    *,
    quality: QualityConfig = QualityConfig(),
) -> dict:
    """Revalidate and package registry, scalers, and validation reports.

    ``release_dir`` must be empty so an older release cannot be partially
    overwritten. Raw pose captures and event annotations remain untouched.
    """
    root = Path(reference_root)
    release = Path(release_dir)
    if release.exists() and any(release.iterdir()):
        raise FileExistsError(f"Release directory is not empty: {release}")
    release.mkdir(parents=True, exist_ok=True)

    revalidation_path = release / "revalidation.json"
    registry_path = release / "registry.json"
    revalidation = rebuild_library(root, revalidation_path, quality)
    registry = write_registry(root, registry_path)

    sides = sorted(
        {
            entry["throws"]
            for entries in (registry.get("pitchers") or {}).values()
            for entry in entries
            if entry.get("throws") in {"LEFT", "RIGHT"}
        }
    )
    side_artifacts = {}
    for side in sides:
        label = side.lower()
        scaler_path = release / f"scaler_{label}.json"
        validation_path = release / f"validation_{label}.json"
        scaler = fit_registry_scaler(registry_path, scaler_path, throws=side)
        validation = leave_one_reference_out(
            registry_path,
            validation_path,
            throws=side,
            camera_mode="exploratory",
        )
        side_artifacts[side] = {
            "scaler": str(scaler_path),
            "reference_sequences": scaler["reference_sequences"],
            "validation": str(validation_path),
            "scored_fold_count": validation["scored_fold_count"],
            "unscored_fold_count": validation["unscored_fold_count"],
            "top1_accuracy": validation["top1_accuracy"],
        }

    manifest = {
        "schema_version": "library-release-v0.1",
        "status": "provisional",
        "reference_root": str(root),
        "release_dir": str(release),
        "registry": str(registry_path),
        "registry_schema_version": registry.get("schema_version"),
        "accepted_reference_count": registry.get("accepted_reference_count", 0),
        "excluded_reference_count": registry.get("excluded_reference_count", 0),
        "pitcher_count": len(registry.get("pitchers") or {}),
        "revalidation": {
            "report": str(revalidation_path),
            "segment_count": revalidation.get("segment_count", 0),
        },
        "throwing_sides": side_artifacts,
        "warning": "Provisional until camera metadata is explicit and each pitcher has sufficient reviewed references.",
    }
    manifest_path = release / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {**manifest, "manifest": str(manifest_path)}
