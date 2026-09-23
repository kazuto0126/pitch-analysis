# Phase 0 contracts

## Input boundary

The only supported new entry is one **local, already prepared single-pitch MP4** plus
`pitch-input-v1` metadata. `examples/pitch_001.json` is a copyable example, not an
assertion about any existing recording. Put the JSON beside the MP4. `video.file`
is a basename and must identify the same file supplied on the command line.
`pitcher.id` and `pitch_id` are lowercase alphanumeric/underscore IDs (max 80 characters).
The pair uniquely identifies the output. A repeated pitch ID under a different pitcher is valid.
Do not infer handedness, season or identity from filenames.

Required fields: `schema_version`, `pitch_id`, `pitcher.id`, `pitcher.throws`, and
`video.file/camera_view/horizontal_mirror/playback_speed/contains_single_pitch/continuous_shot/subject_framing`.
Optional: pitcher display name and `context.season/team/pitch_type/session_id`.
Unknown fields, including URL/source-download metadata, are rejected.

Phase 0 supports declared unmirrored, real-time, continuous, full-body single pitches.
Mirrored/slow-motion/partial-body clips are rejected because the existing analysis core
does not correct these inputs. These are **caller declarations**; passing the validator
does not prove the clip contains one pitch or the correct person. Visual pose/event
review remains required. Identity is supplied by metadata, not ReID.

The decoder checks every frame, dimensions, positive FPS (up to 240), declared/decoded
frame counts and monotonic presentation timestamps. A strict FFmpeg decode checks
bitstream errors. Phase 0 accepts CFR only: each interval and total timestamp drift
must match the decoded presentation cadence within max(2 ms, 5% of one frame).
The reported FPS comes from presentation timestamps; an approximate header FPS
is recorded separately and warned about when it differs by more than 0.05%.
A header/presentation discrepancy over 1%, VFR/unknown timestamps,
rotation metadata, non-square pixels and clips over 30 seconds are rejected. These
are compatibility limits, not biomechanical accuracy thresholds. Native 29.97/59.94
FPS is preserved. Native <29 FPS is allowed with a timing warning. There is no
unvalidated minimum image-size claim; downstream pose quality gates decide usability.

`--standardize` creates a local H.264/yuv420p video-only working copy, retains native
FPS, resolution and frame count, and never crops/extracts pitches. Even dimensions
are required for this option. Analysis can use decodable native MP4 without conversion.
Inputs are not modified; output folders are never overwritten. A failed run is retained
with `analysis.json.status=failed`; retry with a new `--output-root`.

## Schemas and outputs

JSON Schemas (Draft 2020-12) live in `src/pitch_analysis/contracts/schemas/`, are included
in the installed package and are validated before writing. No network schema lookup.
`pitcher-profile-v1` and `pitcher-comparison-v1` are reserved structural contracts for
reviewed multi-pitch data. Phase 0 does not emit them or claim those algorithms.

| Artifact | Contract | Meaning |
|---|---|---|
| input_manifest.json | pitch-input-v1 | Snapshot of supplied metadata; original video location is in video_metadata.json |
| video_metadata.json | video-validation-v1 | Input hash, codec FOURCC, decoded size/count/FPS and clip-relative timestamps |
| working_video_metadata.json | video-validation-v1 | Optional standardized working-copy probe |
| keypoints.json | keypoints-v1 | Raw 33-point observations, frame/timestamp/x/y/z/visibility/presence; empty landmarks for missing frames |
| phases.json | pitch-events-v1 | Phase 0 event template snapshot; all event values null, awaiting review |
| metrics.json | pitch-metrics-v1 | Existing projected 2D feature summaries and raw coverage, not event-specific biomechanics |
| analysis.json | pitch-analysis-v1 | Status, artifact paths, input/model hashes, package versions and quality configuration |

Output layout: `analysis_results/<pitcher_id>/<pitch_id>/`. Legacy `pose_raw.csv`,
`pose_clean.csv`, `features.csv`, quality sidecars, `metadata.json` and `events.json`
remain directly in that folder so existing commands can read them. There is no
automatic registry insertion. `metadata.json` is **legacy analysis metadata**, not
the input contract; use `input_manifest.json` to inspect the submitted metadata.

`phases.json` is deliberately a **pending snapshot in Phase 0**, not another editable
source of truth. Review/edit `events.json`, whose integer boundaries are consumed by
the existing `build-phases`/`revalidate-segment` commands. These legacy commands do
not refresh the new snapshots (`analysis.json`, `phases.json`, `metrics.json`). Their
statuses describe initial preparation. An event refresh/finalization API is deferred.
No event detector, overlay generator, profile schema/implementation or cross-pitcher
report generator is claimed by Phase 0. Versioned contracts for those results follow
when their behavior is implemented; unknown measurements are not fabricated.

`keypoints.json.confidence` explicitly aliases visibility, **not coordinate accuracy**.
Coordinates are raw model output, not smoothed/body-normalized coordinates. `z` is
not calibrated 3D. Smoothing and raw-vs-imputed masks remain in legacy CSVs.
Metric summaries use raw observed frames only. Shoulder/hip line summaries remain
null because ordinary min/median/max would mishandle the 180-degree wrap; their full
curves remain in features.csv. Foot separation has image-height units and is excluded
from existing comparisons. Native frame timing is retained; no per-video Min-Max.

Terminal statuses: `needs_event_review`, `quality_gate_failed`, `no_pose`, `failed`.
CLI exit 0 means preparation completed and its status must be inspected; it does not
mean reference eligibility. Invalid input/execution failure exits nonzero.

## Compatibility handoff

After visual review, fill the five **zero-based clip frame indices** in events.json
and set `review_status=human_reviewed`. Then run:

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe revalidate-segment analysis_results/shohei_ohtani/pitch_001
.\.venv-analysis\Scripts\pitch-analysis.exe build-registry analysis_results analysis_results/registry.json
```

Registry still applies the existing raw-quality and event-window gates. The command
does not waive low-quality input. An incomplete/failed pitch may keep diagnostic
outputs while being ineligible for a reference registry.
