# Phase 2 — Pitcher tracking and pose reliability

Phase 1 accepted five prepared Yoshinobu Yamamoto single-pitch clips. Phase 2
uses only those clips to measure what the rear-centerfield pose pipeline can
and cannot observe. MediaPipe remains the baseline backend. The selector,
confidence gates, interpolation, smoothing, and Phase 1 thresholds are not
changed by this evaluation. No player re-identification or 3-D biomechanics is
inferred.

## Reproducible baseline

Run on a new output root; neither command overwrites prior results:

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\run_real_baseline.py input\yoshinobu_yamamoto\phase1_final --output-root analysis_results\phase2_yamamoto_20260925_01\predictions
.\.venv-analysis\Scripts\python.exe -B scripts\run_phase2_reliability.py input\yoshinobu_yamamoto\phase1_final analysis_results\phase2_yamamoto_20260925_01
```

The output keeps prediction and annotation apart:

```text
analysis_results/phase2_yamamoto_20260925_01/
  predictions/yoshinobu_yamamoto/pitch_001..pitch_005/  # original E2E files, including overlay.mp4
  reliability/pitch_001..pitch_005/
    pose_reliability.json
    tracking_reliability.json
  ground_truth/pitch_001..pitch_005/ground_truth.json  # blank human templates
  evaluation_summary.json
  ground_truth_comparison_initial.json
  test_suite.log
```

The new raw pose CSV and overlay MP4 for each clip have the same SHA-256 as the
Phase 1 final run. The new `PoseEstimator` interface returns the same ordered
33-landmark contract; the MediaPipe settings and output are unchanged. Other
backends must map to that contract before comparison. A model benchmark would
require a separate plan and human-labeled evaluation set.

## What the reliability reports mean

`pose_reliability.json` includes all joints, with extra summaries for throwing
shoulder, elbow, wrist, and lead hip, knee, ankle. Each joint has one state per
frame: `observed` only when a direct model coordinate passes the existing
quality gate, `interpolated` when the existing short-gap cleaner supplies it,
and `missing` otherwise. Interpolation never counts as raw coverage. Reports
also include raw-prediction coverage, quality-gated raw coverage, visibility
statistics, longest missing and unobserved spans, interpolation use,
observed-to-observed jump candidates, and left/right image-order changes.
Image-order flips can reflect real body rotation; jumps can reflect fast motion.
Both are review cues, not confirmed errors.

The reliability policy is **provisional and uncalibrated**: `reliable` needs at
least 85% directly observed joint frames, at most a two-frame missing span, at
most 10% interpolation, and no jump candidates. A joint is `unreliable` below
50% raw coverage or when its longest missing span exceeds the greater of five
frames and 10% of the clip. The remaining cases are `partially_reliable`.
The clip label conservatively takes the weakest of the six focus joints. This
policy is separate from the unchanged Phase 1 feature-angle gate. In
particular, a directly observed elbow joint does not mean the three-point
throwing-elbow angle is fully observed.

`tracking_reliability.json` audits the selected skeleton's raw hip center,
projected height, ROI, motion continuity, and selector breaks. It can warn of
a possible identity change; `identity_switch_confirmed` stays null until a
human review. A stable skeleton can still belong to the wrong person.

## Five-clip baseline findings

| Pitch | Tracking | Selector break | Pose signal | Throwing elbow joint raw | Throwing elbow angle raw | Throwing wrist raw / longest missing |
|---|---|---:|---|---:|---:|---:|
| `pitch_001` | reliable | 0 | unreliable | 66.7% | 51.72% | 51.7% / 32 frames |
| `pitch_002` | reliable | 0 | unreliable | 88.6% | 65.14% | 65.1% / 31 frames |
| `pitch_003` | reliable | 0 | unreliable | 84.3% | 53.04% | 53.9% / 18 frames |
| `pitch_004` | partially_reliable | frames 75–76 | unreliable | 72.8% | 50.88% | 51.8% / 18 frames |
| `pitch_005` | partially_reliable | frame 54 | unreliable | 88.1% | 71.29% | 71.3% / 13 frames |

No raw-continuity identity-switch warning fired in these five clips. The
long throwing-wrist missing spans drive the conservative clip-level pose
labels; elbow and lead-leg statuses vary by clip and are in each JSON report.
These reports expose a reliability gap; they do not retroactively fail Phase 1
clip acceptance.

Per-joint provisional flags (`R` = reliable, `P` = partially reliable, `U` =
unreliable):

| Pitch | Throwing shoulder | Throwing elbow | Throwing wrist | Lead hip | Lead knee | Lead ankle |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `pitch_001` | R | U | U | R | P | P |
| `pitch_002` | P | P | U | R | P | P |
| `pitch_003` | P | P | U | P | P | P |
| `pitch_004` | P | U | U | P | P | P |
| `pitch_005` | P | P | U | R | P | P |

## Human ground truth and acceptance

Five `ground_truth.json` files were initially created as blank templates with
`annotation_status = unreviewed`. As of 2026-10-03, `pitch_001`, `pitch_002`,
`pitch_003`, and `pitch_004` are reviewed by HSU and have passed schema/source
validation; `pitch_005` is in progress, with partial human observations and
events saved, including foot plant at 55. HSU confirmed no whole-subject
identity switch; the frame 54 output break and local joint errors are retained.
Unreported joint intervals remain for HSU to confirm; onset and peak retain uncertainty.
For `pitch_003` and `pitch_004`, HSU supplied the complete
human observations and explicitly authorized Codex to transcribe the JSON.
Follow [manual ground-truth guidelines](phase2_ground_truth.md)
to record correct-subject selection, switches, track breaks, major failures,
throwing-arm occlusion, all six focus-joint reliability intervals, and five event
landmarks. The same ground-truth-v1 contract now supports exact frames, ranges,
uncertainty, not-observable states, confidence, and reviewer notes. A reviewer must
inspect the source video and overlay. No prediction values are copied into
human labels.

The user also authorized a separate classmate review: full `pitch_003` and
event supplementation for `pitch_005`. The [portable review workflow](phase2_peer_review.md)
uses blank templates of the same contract and stores returned judgments under
`annotations/phase2_peer_reviews/`, preserving reviewer provenance and
disagreements. HSU's canonical files remain separate. Event supplementation
alone does not complete `pitch_005` or establish Phase 2 acceptance.

The review package is at
`analysis_results/phase2_yamamoto_20260925_01/review_helper_20260926_01/START_HERE.md`.
Human review is 4/5 complete. After all five reviews, extend the comparison
reader for the full-review fields and uncertainty before producing a *new*
comparison report. The current legacy reader rejects this profile rather than
silently interpreting uncertain intervals as confirmed errors. The following is
the legacy invocation, **not a command to run during review preparation**:

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\evaluate_phase2_ground_truth.py input\yoshinobu_yamamoto\phase1_final analysis_results\phase2_yamamoto_20260925_01 analysis_results\phase2_yamamoto_20260925_01\ground_truth_comparison_reviewed.json
```

The comparison counts warnings against human switch/failure intervals and
tabulates observed/interpolated/missing states against human joint reliability
labels. It explicitly leaves keypoint coordinate error and event timing error
unmeasured: this baseline contains no human reference X/Y coordinates and does
not automatically predict the five event frames. Phase 2 acceptance remains
pending until the five annotations are reviewed and the warnings and joint
flags are judged against those labels. Program execution alone is not a pass.
