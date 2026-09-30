# Current status — Phase 1 accepted; Phase 2 reliability baseline

Updated: 2026-09-30

**Phase 1 = PASSED**

The five formal Yoshinobu Yamamoto single-pitch inputs passed the existing
Phase 1 clip-level acceptance checks. Phase 2 now evaluates tracking and
per-joint pose reliability on those same five clips. No Phase 1 threshold,
PitcherSelector rule, pose algorithm, interpolation, or smoothing policy was
changed.

**Phase 2 = IN PROGRESS — human ground truth pending.** The baseline runner,
reports, and annotation workflow are available; program execution is not a
Phase 2 acceptance result.

## Phase 2 baseline

### Human review progress (2026-09-30)

Manual review is **2/5**. `pitch_001/ground_truth.json` and
`pitch_002/ground_truth.json` are `reviewed` by **HSU**, with completion times
`2026-09-27T16:01:04Z` and `2026-09-30T12:47:32Z`, respectively.
The read-only review validator passed the schema, full-frame joint intervals,
event ordering, and source-video hash checks. The judgments were supplied and
entered by the human reviewer; validation does not establish model accuracy.
`pitch_003` through `pitch_005` remain `unreviewed`. The next review is
`pitch_003`, frames 0–114. No prediction comparison has been performed.

For `pitch_002`, HSU confirmed continuous correct-subject tracking, no identity
switch, no obvious track break, and no major whole-pose failure. Right shoulder
and left hip/knee/ankle alignment were accepted throughout frames 0–174.
Right-wrist frames 18–19 were visible but unmarked; frames 72–92 were hidden in
the glove and frames 144–174 behind the body. Right-elbow frames 140–141,
144–155, and 166–167 were not observable; the remaining elbow intervals were
accepted. These are human observations of the imagery and raw overlay, not
replacements for processed observed/interpolated/missing states.
HSU annotated preparation start at 74, peak leg lift at 118, foot plant at 140,
approximate release within 141–143, and follow-through end at 168. Unobserved
positions remain unobserved and confidence values remain null.

The five canonical annotation JSON files under
`analysis_results/phase2_yamamoto_20260925_01/ground_truth/` are explicitly
included in Git for this review checkpoint. There is no second editable copy.
Videos, overlays, contact sheets, and generated analysis reports remain local
and ignored; source-video hashes in each annotation identify the required media.

Checkpoint verification (2026-09-28 Taiwan time): **89 passed, 0 failed,
1 skipped** (90 tests discovered). The opt-in real-video E2E was not enabled,
so this checkpoint did not rerun the five formal videos. All five annotation
files passed schema/source validation and retained their exact pre-checkpoint
contents. Test log:
`analysis_results/phase2_yamamoto_20260925_01/review_helper_20260926_01/test_suite_checkpoint_20260927T171721Z.log`.

### Ground truth review preparation (2026-09-26–27)

At preparation time, manual review was **0/5**. The five existing templates at
`analysis_results/phase2_yamamoto_20260925_01/ground_truth/pitch_00N/ground_truth.json`
now use the full-review extension of the same `ground-truth-v1` contract.
All human judgments were initially null; no ground truth was inferred or scored
by the preparation workflow. Current review progress is recorded above.
The extension supports six joints, track breaks, throwing-arm occlusion,
event frame ranges, explicit uncertainty/not-observable states, and reviewer
confidence/notes. Original blank templates are preserved in the review
package's `template_backups/` directory.

Review-preparation tests (2026-09-27): **89 passed, 0 failed, 1 skipped**
(90 discovered). The opt-in real-video E2E test was not enabled for this
annotation-helper change. Log:
`analysis_results/phase2_yamamoto_20260925_01/review_helper_20260926_01/test_suite_review_20260927.log`.

Review entry point:
`analysis_results/phase2_yamamoto_20260925_01/review_helper_20260926_01/START_HERE.md`.
The package contains 592 full-size original/overlay frame pairs, 52 contact
sheets, five per-frame state CSVs, and five checklists. Source hashes,
frame/timestamp alignment, processed joint states, and decoded frame counts
were verified. The original predictions and baseline reports remain unchanged.
See [manual review instructions](phase2_ground_truth.md) for all field formats.

Next: the human reviewer completes each clip, preserving uncertain ranges and
occlusions, then validates the annotation schema/source. Only after that review
should the comparison reader be extended to evaluate the full-review labels
without collapsing uncertainty. The legacy comparator explicitly rejects this
new profile rather than silently ignoring its additional labels. No comparison
against the five human annotations has been run, and Phase 3 has not started.

### Existing baseline findings

Latest output: `analysis_results/phase2_yamamoto_20260925_01/`. It contains
fresh five-pitch predictions and overlays, per-pitch `pose_reliability.json`
and `tracking_reliability.json`, initially blank separate `ground_truth.json` templates,
and `evaluation_summary.json`. Fresh raw pose CSV and overlay MP4 hashes match
the Phase 1 final run for all five clips after introducing the `PoseEstimator`
interface. MediaPipe remains the backend.

| Pitch | Tracking reliability | Track break | Pose signal reliability | Throwing elbow joint raw | Throwing elbow angle raw | Throwing wrist raw / longest missing |
|---|---|---:|---|---:|---:|---:|
| `pitch_001` | reliable | 0 | unreliable | 66.7% | 51.72% | 51.7% / 32 frames |
| `pitch_002` | reliable | 0 | unreliable | 88.6% | 65.14% | 65.1% / 31 frames |
| `pitch_003` | reliable | 0 | unreliable | 84.3% | 53.04% | 53.9% / 18 frames |
| `pitch_004` | partially_reliable | frames 75–76 | unreliable | 72.8% | 50.88% | 51.8% / 18 frames |
| `pitch_005` | partially_reliable | frame 54 | unreliable | 88.1% | 71.29% | 71.3% / 13 frames |

The tracking audit found no raw-continuity identity-switch warning. A warning
cannot confirm identity, and its absence cannot prove correct pitcher
selection. The provisional pose policy conservatively marks all five clip
signals unreliable because of long throwing-wrist missing spans. This does
not change the Phase 1 clip acceptance outcome. All five ground-truth files
were initially `unreviewed`; current human review progress is recorded above.
Prediction agreement and actual tracking/keypoint accuracy remain unmeasured.
See [Phase 2 reliability](phase2_reliability.md) and
[manual ground truth](phase2_ground_truth.md).
The earlier baseline suite on 2026-09-25, including the real five-pitch E2E
test, reported **84 passed, 0 failed, 0 skipped**.

## Formal inputs and preservation

The formal `input/yoshinobu_yamamoto/pitch_001` through `pitch_005` MP4/JSON
pairs are current. A five-pair snapshot used by the E2E runner is at
`input/yoshinobu_yamamoto/phase1_final/`. Both copies were verified to have
matching video and metadata hashes. Metadata `pitch_id` and `video.file`
match each formal filename.

| Formal pitch | Source | Video SHA-256 |
|---|---|---|
| `pitch_001` | Retained | `7c9fe20e39c1b5358aa8e13b739222aebb6bf3ebfadf3569ccb3042c64f10190` |
| `pitch_002` | Retained | `b38258e682370349d085d0b43683f183afc632f682dc85b758604c9d1489f01a` |
| `pitch_003` | `candidate_007` | `5c08dba98504d998536dfd0f0fab598760400612c9049445a68120e68fdf024c` |
| `pitch_004` | `candidate_008` | `e5a57bfc2e0746bb19af2a073d94abb7265d8dfb9ad37de06cee1de29f63d11a` |
| `pitch_005` | `candidate_009` | `e289cb1159e5863583f85915214123d6afe03baa6f32ac6040040878093c873b` |

Before replacement, the previous `pitch_003`–`pitch_005` MP4 and JSON files
were copied to
`input/yoshinobu_yamamoto/archive/superseded_20260924_01/`. All six archived
files were checked against their original SHA-256 hashes; see
`archive_manifest.json` there. The old inputs remain recoverable.

## Final Phase 1 validation

The fresh five-pair E2E run wrote
`analysis_results/phase1_final_yamamoto_20260925_01/`, with
`validation_summary.json`, `artifact_audit.json`, `final_acceptance.json`,
`visual_inspection.json`, `test_suite.log`, five overlay contact sheets, and
one analysis directory per formal pitch under `yoshinobu_yamamoto/`. Every
input-quality result is `accepted`; every MP4 technical result is `validated`;
every keypoint-quality result is `success`.
All five output directories contain raw and processed keypoints, quality files,
metrics, and decodable overlays with one frame per input frame. The analysis
manifests remain `needs_event_review` because event labels are not inferred
automatically.

| Pitch | Total | Valid pose | Rejected | Interpolated | Mean visibility | Longest pose gap | Throwing elbow raw coverage | Lead knee raw coverage | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `pitch_001` | 87 | 87 (100%) | 0 | 16 | 0.814 | 0 frames | 51.72% | 93.10% | success |
| `pitch_002` | 175 | 175 (100%) | 0 | 25 | 0.816 | 0 frames | 65.14% | 98.86% | success |
| `pitch_003` | 115 | 115 (100%) | 0 | 32 | 0.823 | 0 frames | 53.04% | 90.43% | success |
| `pitch_004` | 114 | 112 (98.25%) | 2 | 22 | 0.812 | 2 frames | 50.88% | 90.35% | success |
| `pitch_005` | 101 | 100 (99.01%) | 1 | 19 | 0.827 | 1 frame | 71.29% | 86.14% | success |

All five exceed the unchanged 50% throwing-elbow raw-coverage requirement.
The other core raw feature coverages are at least 80%, and valid pose
coverage is at least 90%. None has a degradation or failure reason.

## Overlay inspection

The five final overlays were reviewed visually using contact sheets that span
each clip. The freshly rendered overlay MP4s are byte-identical to the
corresponding overlays from the earlier all-frame review, and the contact
sheets are retained in the new output directory. All five show
a continuous, plausible rear-centerfield view, preparation through leg lift,
delivery, and follow-through. The selected skeleton remains on pitcher #18;
no whole-subject identity switch or camera cut was observed. No replay or
slow motion was visually observed, although native playback speed cannot be
independently proved from these files.

- `pitch_001`: hands are set at the beginning and the full leg lift is
  visible. The back foot is already beginning to move in the first frame.
  The throwing-elbow margin above 50% is 1.72 percentage points.
- `pitch_002`: a long continuous set precedes leg lift; pose remains on
  the pitcher through recovery.
- `pitch_003`: preparation and follow-through are visible; the pitcher
  remains selected throughout.
- `pitch_004`: frames 75–76 lose the pose briefly during late delivery,
  then reacquire the same pitcher. The elbow margin is 0.88 percentage points.
- `pitch_005`: frame 54 loses the pose briefly, then reacquires the same
  pitcher. Some arm landmarks overlap the batter in image projection, so
  exact joint placement remains a review caveat.

This is an agent visual inspection, not player identity ground truth. The
separate human validation templates, event annotations, and registry
approval remain pending. They do not alter the completed clip-level
Phase 1 acceptance result.

## Tests and repository scope

The full unittest suite ran with
`PITCH_ANALYSIS_REAL_BASELINE_DIR=input/yoshinobu_yamamoto/phase1_final`:
**62 passed, 0 failed, 0 skipped**. This includes the opt-in real five-pitch E2E
test. `input/` and generated `analysis_results/` content remain Git-ignored,
with the five canonical Phase 2 ground-truth JSON files as an explicit exception.
Git records the review code, documentation, and annotation progress; videos,
the media archive, and generated run outputs remain local.

## Next step recommendation

Keep the five formal clips and the superseded archive unchanged. Follow this
sequence agreed with the user on 2026-09-28:

1. Finish human ground truth for `pitch_003` through `pitch_005`, one clip at a
   time. Preserve `pitch_001` and `pitch_002` as completed reviews. Human judgments must not
   be inferred or filled automatically; validate each completed annotation.
2. Extend the comparison reader to support the full-review contract, including
   all six joints, track breaks, occlusion, event ranges, and uncertainty. Then
   compare the five human annotations against the existing baseline predictions
   in a new report. Keep raw-overlay judgments distinct from processed
   observed/interpolated/missing states. Do not claim coordinate or event-timing
   accuracy without matching reference data and predictions.
3. Use those findings to decide whether pose/tracking reliability needs changes.
   Do not change models, algorithms, or thresholds during manual review, and do
   not treat successful execution as Phase 2 acceptance.
4. Once Phase 2 is stable and accepted on evidence, proceed to the agreed
   pitcher-motion analysis work. Do not automatically begin Phase 3.
5. Subsequently integrate a small batch of MLB Pitch Clipper outputs under the
   external handoff requirements below, then evaluate another pitcher.

## Deferred MLB Pitch Clipper handoff

`mlb-pitch-clipper` owns search, acquisition, cleaning, and cutting. Its current
release candidate should remain unchanged unless a reproducible product bug
requires a fix. `pitch-analysis` owns MP4 input validation, pose/tracking
reliability, motion analysis, and later comparison/reporting. Do not duplicate
Clipper's M1/M2 logic or depend on its internal temporary clips or event files.

The current Clipper v0.1.0-rc1 downstream contract exports
`<Pitcher_Name>_<Game_Year>.mp4`: chronological pitching clips in H.264/yuv420p,
at original speed. This can be a multi-pitch compilation and may retain replays.
It is not automatically a valid `pitch-input-v1` input. A shared folder or
filename change alone does not resolve that difference.

Before formal integration, the upstream handoff must provide individually
prepared single-pitch MP4s plus adjacent `pitch-input-v1` JSON, with verified
pitcher identity/handedness, continuous rear-centerfield full-body footage,
normal speed, no mirror, and complete preparation/follow-through. Existing
technical and quality gates still apply, including CFR and the 30-second limit.
Keep the original Clipper product and available run/source manifests for
traceability, outside the strict pitch metadata fields. Use a distinct batch
directory and new analysis output root; never overwrite the Yamamoto baseline.

The missing formal single-pitch handoff is a deferred integration requirement,
not evidence of a Clipper bug or authorization to change Clipper now. Revisit it
after the sequence above; GT completion alone does not authorize automatic
integration. External MP4/JSON pairs can be read from a shared local folder, so
merging repositories is unnecessary.
