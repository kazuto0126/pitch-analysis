# Phase 1 — single-pitch real MLB baseline

Phase 1 supports only `rear_centerfield_broadcast`, normal-speed, unmirrored,
continuous, full-body single-pitch MP4 input. The metadata declaration cannot
prove the camera view or the pitcher identity; the reviewer must check both.
Other camera views are rejected at the `pitch-input-v1` contract boundary.

## What the new analysis emits

`analyze-pitch` still calls the existing confidence-aware cleaning, 2D features,
quality gate and event-review pipeline. MediaPipe now requests up to four poses
for this entry. `PitcherSelector` uses a broad rear-centerfield spatial ROI,
projected body scale, major-joint visibility/presence and short-term hip
continuity. It rejects ambiguous or implausible frames instead of switching
silently. This is **subject selection, not MLB player ReID**.

The following files are added beside the Phase 0 artifacts:

| File | Meaning |
|---|---|
| `keypoints.jsonl` | One record per decoded frame: PTS, selected/rejected status and raw model coordinates/visibility/presence. |
| `processed_keypoints.jsonl` | Confidence-gated, short-gap-interpolated coordinates and masks; an additional 3-frame median for visualization only. Existing features still use the pre-median clean coordinates and their own feature smoothing. |
| `keypoint_quality.json` | Selection decisions plus valid, rejected, interpolated, confidence and longest-gap summary. |
| `wrist_trajectory.json` | Hip-centered, torso-scaled *projected 2D* throwing-wrist path; null when unavailable. Not 3D motion or a measured release position. |
| `overlay.mp4` | Raw selected skeleton over source frames, frame/PTS, mean candidate confidence, throwing/lead side; rejected frames show red text. Debug only. |
| `review/human_validation_template.json` | Separate, unfilled manual review; never auto-adds to the registry. |

The quality summary's `success/degraded/failed` measures technical pose/quality
coverage only. It is **not** a statement that the selected body is truly the
named pitcher or that the whole delivery is present. `analysis.json` retains
the Phase 0 event-review status. Ball release is not guessed.
`success` requires at least 90% selected frames and the existing quality gate;
`degraded` requires at least 50% selected frames; otherwise the technical status
is `failed`. These are provisional triage thresholds, not calibrated accuracy.

## Genuine 3–5-clip acceptance run

Place 3–5 already prepared single-pitch MP4/JSON pairs of **one** MLB pitcher
in one directory. Match each JSON basename to its MP4. Fill `pitcher.throws`,
camera, mirror, playback and framing declarations honestly. Do not use the old
raw multi-pitch footage as a positive fixture.

```powershell
$env:PITCH_ANALYSIS_REAL_BASELINE_DIR = 'D:\project\pitch-analysis\input\<pitcher_id>'
.\.venv-analysis\Scripts\python.exe -B -m unittest discover -s tests -p test_real_mlb_e2e.py -v
.\.venv-analysis\Scripts\python.exe -B scripts\run_real_baseline.py $env:PITCH_ANALYSIS_REAL_BASELINE_DIR --output-root analysis_results\phase1_baseline_01
```

The first command checks the positive handoff without retaining its temporary
outputs. The second retains outputs and `validation_summary.json`. A repeat run
must use a new output root; analyzed pitch directories are not overwritten.

Open each `overlay.mp4` and record in the separate human review template:

- Whether the skeleton belongs to the pitcher throughout, including identity switches.
- Whether throwing arm and lead leg are labeled correctly.
- Whether shoulders/elbows/wrists/hips/knees/ankles are plausible at key moments.
- Whether the clip covers set/leg lift through follow-through without replay/cut.

Human confirmation does not change `events.json`, the quality gate or registry.
Event boundaries still require the existing manual workflow.

## Current acceptance state

As of 2026-09-23, five prepared Yoshinobu Yamamoto MP4/JSON pairs are present
locally under `input/yoshinobu_yamamoto/`; the MP4 files are ignored from Git.
Phase 1 real E2E found `pitch_002` to be the only technically passing baseline.
`pitch_001` loses the pitching view after delivery, `pitch_003` mixes in other
shots, `pitch_004` has a camera cut and observed identity switch in the earlier
overlay review, and `pitch_005` begins after preparation. These are genuine
failure results, not reasons to loosen the existing confidence threshold.
The opt-in *positive* test is for 3–5 known-good clips and is not suitable for
this mixed-quality set. Phase 1.1 now writes separate input-quality evidence;
see [Input Quality Gate](phase1_1_input_quality.md).

A diagnostic (not acceptance) run on frames 0–150 of the existing 29.6-second
Yamamoto spring-training clip selected 104/151 frames. The broadcast cuts
from pitcher to catcher around 4 seconds: 59/60 frames in seconds 0–1 had a
selected pose, while seconds 4–5 were rejected in 30/31 frames. One selected
frame near the cut remains a potential false selection pending overlay review.
This illustrates why unprepared, cut-heavy footage cannot be counted as a
successful single-pitch baseline.

## Scientific limits

Selector spatial thresholds are camera-protocol heuristics, not a trained
pitcher detector. Occlusions, zooms and camera cuts can cause rejection or
identity switches. MediaPipe visibility is not calibrated positional accuracy.
The elbow/knee and shoulder/hip-line curves remain image-plane projections;
no 3D rotation, torque, true velocity or release frame is inferred. Those
questions belong to later phases with an explicit ground-truth evaluation set.
