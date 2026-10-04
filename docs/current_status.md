# Current status — Phase 1 accepted; Phase 2 reliability baseline

Updated: 2026-10-04

**Phase 1 = PASSED**

The five formal Yoshinobu Yamamoto single-pitch inputs passed the existing
Phase 1 clip-level acceptance checks. Phase 2 now evaluates tracking and
per-joint pose reliability on those same five clips. No Phase 1 threshold,
PitcherSelector rule, pose algorithm, interpolation, or smoothing policy was
changed.

**Phase 2 = IN PROGRESS — ground-truth comparison pending.** HSU's five
qualitative reviews are complete; independent manual X/Y is still pending. The baseline runner,
reports, and annotation workflow are available; program execution is not a
Phase 2 acceptance result.

## Phase 2 baseline

### Manual skeleton coordinate handoff (2026-10-04)

The user clarified that the classmate should manually place skeleton X/Y,
instead of only filling qualitative reliability intervals. The earlier
`peer_review_package_20261003_01` has no human coordinate fields and is retained
as the review history. The current handoff is
`analysis_results/phase2_yamamoto_20260925_01/manual_pose_package_20261004_01.zip`.

Use CVAT to mark all 115 original `pitch_003` frames (0–114), with the 12
bilateral shoulder/elbow/wrist/hip/knee/ankle joints in original 510 × 628
image pixels. No AI annotations are seeded. Each point must be explicitly
visible, uncertain, not observable, or unreviewed; only manually confirmed
visible points retain X/Y. Fully occluded or uncertain points carry no inferred
coordinate. Start with frames 0–4 and return a pilot export to check the format
before completing the rest. `pitch_003` and `pitch_005` events use the existing
ground-truth-v1 exact/range/uncertainty workflow.

The CVAT XML/ZIP importer validates the source filename/hash, decoded
timeline and original PNG hashes, image names/dimensions, and manual point
states. It stores an independent `manual-keypoints-v1` reference plus the
original XML under `annotations/manual_keypoints/<review-id>/pitch_003/`.
The original HSU ground truth and raw model predictions remain separate.
The new evaluator is ready to report per-joint pixel errors and missing raw
predictions using only human-visible coordinates. It creates no new pass
threshold, does not change pose/tracking logic, and does not train MediaPipe.
No human X/Y annotations have been returned and no real coordinate comparison
has run. HSU full qualitative review is now 5/5; Phase 2 remains in progress.
See [manual coordinate instructions](phase2_manual_keypoints.md).

Handoff verification: 115 lossless PNG frame hashes and both blank event
templates validated; portable HTML links and ZIP CRCs passed. The ZIP is
80.4 MiB (240 files). All 25 existing source-video, HSU annotation, raw CSV,
overlay, and raw keypoint JSON hashes remain unchanged. The current CVAT
configuration follows its official Raw-label format; a logged-in CVAT task
was not created here, so the first five manually annotated frames are the
required pilot to verify the classmate's actual export before completing
the clip. The preparation step performed no third-party upload. The user's
subsequent explicit request authorized publishing the complete media package
as a public GitHub Release asset so the classmate can download it independently.

Published annotation package:
[Release page](https://github.com/kazuto0126/pitch-analysis/releases/tag/phase2-manual-pose-review-20261004-01)
and [direct ZIP download](https://github.com/kazuto0126/pitch-analysis/releases/download/phase2-manual-pose-review-20261004-01/manual_pose_package_20261004_01.zip).
The asset is 84,347,750 bytes; SHA-256
`3b568e9065e0ec712c17bbd4d9ad741d39b1e1c7d5174d874ce6e2de7ffbe80e`.
The data release points to tool commit `9eeb5eadf7014bf960e11e985d2126fb69929407`.
It provides blank annotation tasks and does not indicate Phase 2 acceptance.
GitHub's automatic Source code archives do not include these ignored media.
GitHub reports the asset as uploaded with the matching SHA-256. Anonymous
download verification returned HTTP 200 and the exact 84,347,750-byte length.

Full suite: **138 passed, 0 failed, 1 skipped** (139 discovered). The skipped
test is the opt-in real-video E2E; no pose/tracking pipeline was rerun.
Log: `analysis_results/phase2_yamamoto_20260925_01/test_suite_manual_pose_20261004_01.log`.

### HSU qualitative review completed (2026-10-04)

HSU's five canonical `ground_truth.json` files are now `reviewed` (**5/5**).
After reviewing all `pitch_005` frames, HSU explicitly confirmed that, outside
the already recorded exceptions, the remaining right shoulder/elbow/wrist and
left hip/knee/ankle are visible and approximately aligned. Codex transcribed
that confirmation only into the missing joint intervals; all previous error,
missing-output and not-observable intervals, source binding, event labels,
and null confidence values were retained. Each joint covers frames 0–100.
`pitch_005` completed at `2026-10-04T02:56:16Z` (Taiwan 10:56:16).

Preparation onset at candidate frame 0 and peak leg lift at candidate frame 33
remain `uncertain`. Foot plant is 55, approximate release is the range 58–59,
and follow-through end is 83. A reviewed annotation may retain uncertainty;
the classmate's independent event supplements will be stored separately.
All five annotations passed schema, interval-completeness, event-order and
source-hash validation. The four other HSU annotations, five source videos,
and existing raw artifacts retained their hashes (34 protected files).
The previous partial `pitch_005` JSON is also preserved locally under
`analysis_results/phase2_yamamoto_20260925_01/review_checkpoints/pitch005_before_completion_20261004T025616Z.json`.

No prediction comparison has run and no classmate X/Y annotation has returned.
This completes the human qualitative review, not Phase 2 acceptance. The
unchanged full suite last reported 138 passed, 0 failed, 1 skipped; this data
checkpoint used the read-only annotation/source validator, with no inference.

### Human review history (2026-10-03)

At that checkpoint, manual review was **4/5**. `pitch_001`, `pitch_002`, `pitch_003`, and `pitch_004`
ground truth files are `reviewed` by **HSU**, with completion times
`2026-09-27T16:01:04Z`, `2026-09-30T12:47:32Z`,
`2026-10-03T02:54:48Z`, and `2026-10-03T09:21:10Z`, respectively.
The read-only review validator passed the schema, full-frame joint intervals,
event ordering, and source-video hash checks. HSU supplied the human judgments
for all four clips and entered the first two JSON files personally. For
`pitch_003` and `pitch_004`, HSU explicitly authorized Codex to transcribe those judgments;
the reviewer remains HSU. Validation does not establish model accuracy.
`pitch_004` was `reviewed`; `pitch_005` was `in_progress` under HSU, with partial
human observations saved in its canonical JSON. These include visible elbow
errors at 6–23 and 29–33, visible wrist errors at 24–28, visible lower-leg
errors at 45, and whole-skeleton loss at 54. HSU identified foot plant at 55,
release within 58–59, and follow-through end at 83. HSU clarified that frame 0 is already
ready to initiate; the actual preparation onset remains uncertain, as does
the tentative peak at 33. Non-throwing-arm errors and remaining visibility
questions are preserved in notes. HSU confirmed no whole-subject identity
switch; the frame 54 output break and local joint errors remain recorded.
No unreported joint interval is filled as reliable.
The remaining `pitch_005` intervals were subsequently confirmed on 2026-10-04,
as recorded above. HSU observations for `pitch_004` are saved in its canonical
JSON: visible right-elbow errors at 27–32, visible left-knee error at 65,
and visible right-wrist misses at 66–67. HSU also confirmed right-wrist
deviation at 11–26, complete skeleton loss at 75–76, visible right-wrist errors at
77–80, and an unseen right hand with false points on the batter's foot at
81–87. HSU has completed the full-frame description and reports that the
remaining frames are generally okay. HSU confirmed wrist deviation at 27–32
and right-elbow invisibility throughout 77–87; wrist visibility is retained
at 77–80, while both elbow and wrist are not observable at 81–87. HSU confirmed
that the main body skeleton remains on the pitcher whenever present, with no
whole-subject identity switch; the 75–76 skeleton break and limb errors remain
recorded. All six joint intervals cover frames 0–113. HSU annotated preparation
start at 4, peak leg lift at 44, foot plant within 65–66, approximate release
within 70–71, and follow-through end at 89. Human ranges and not-observable
intervals are preserved; confidence values remain null. No prediction comparison
has been performed.

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

For `pitch_003`, HSU clarified that the subject remains near the pitcher;
frames 87–104 show major pose displacement rather than a confirmed switch
to the batter. Right shoulder/elbow points are displaced during 87–104,
whereas left hip/knee/ankle points are displaced only during 101–102 and
recover at 103. At 65, the left hip is correct, the visible left knee is
unmarked, and the left ankle is not observable. Other right-arm errors and
non-throwing-arm observations are retained in the annotation; a point drawn
on the batter's foot is not accepted as evidence of an unseen joint's location.
Invisible throwing-arm intervals retain `not_observable`; the specific
occlusion cause was not confirmed. HSU's suggestion that the batter/view
affected pose is recorded as a hypothesis. Exact human event labels are
preparation 12, peak leg lift 47, foot plant 66, approximate release 69, and
follow-through end 99. Pose errors after 99 remain included. Per HSU's
explicit instruction after a full-frame review, otherwise unreported
intervals are clear and have no reported alignment issue. Confidence is null.

The five canonical HSU annotation JSON files under
`analysis_results/phase2_yamamoto_20260925_01/ground_truth/` are explicitly
included in Git for this review checkpoint. Independent peer reviews use the
same contract and are stored separately by reviewer/version; they do not replace
these canonical files.
Videos, overlays, contact sheets, and generated analysis reports remain local
and ignored; source-video hashes in each annotation identify the required media.

### Independent classmate review (2026-10-03)

HSU's manual-review checkpoint was pushed to GitHub as
[`a02f190`](https://github.com/kazuto0126/pitch-analysis/commit/a02f1900d4b3eb77214cbf12bdfc37eb98fa1153).
The user confirmed `pitch_003` for a complete independent review and
`pitch_005` for event supplementation. `pitch_003` was selected because HSU
recorded the longest whole-pose major displacement among these five reviews
(18 frames, 87–104), without assigning a combined score or claiming an
identity switch. The student handout does not expose HSU's answers.

Portable package:
`analysis_results/phase2_yamamoto_20260925_01/peer_review_package_20261003_01.zip`.
Extract it completely, open `START_HERE.html`, and fill each pitch's
`REVIEW_NOTES.md` or blank `ground_truth.json`. It includes the existing original
and browser-compatible raw-overlay videos, all 216 frame pairs, 19 contact
sheets, and model-state CSVs. The export performs no analysis or inference.
Media remain local and Git-ignored; the user shares the ZIP with the classmate.

Returned judgments must retain the classmate's actual reviewer, review scope,
time/timezone, source binding, and uncertainty. After faithful transcription
and schema/source validation, save them under
`annotations/phase2_peer_reviews/<review-id>/<pitch-id>/ground_truth.json`.
The importer refuses existing destinations and preserves the supplied JSON
bytes. Event-only peer `pitch_005` remains `in_progress`; this task is separate
from HSU's completed joint review. No peer answers exist yet, no canonical labels
have been changed for the handoff, and no prediction comparison has run.
Occluded joints remain `not_observable`; no imagined positions are annotated.
See [peer review instructions](phase2_peer_review.md).

Handoff verification: the ZIP contains 253 files (48.0 MiB), with valid CRCs
and relative HTML links that resolve inside the package. Both blank templates
passed the existing schema validator and contain no HSU judgments. Source and
overlay playback counts/timestamps match the frame CSVs: 115 and 101 frames,
both at 30 FPS, with timestamp error below 1 ms. The five canonical JSONs and
ten raw CSV/overlay artifacts retained their pre-handoff SHA-256 hashes.
The in-app browser blocks `file:` URLs, so browser rendering from a local file
was not verified there; the package includes direct media/image access and an
optional loopback server for playback fallback.

Full suite after the review tools were added: **107 passed, 0 failed,
1 skipped** (108 discovered). The skipped test is the opt-in real five-video
E2E; it was not enabled because this handoff changes no pose/tracking logic.
Log: `analysis_results/phase2_yamamoto_20260925_01/test_suite_peer_review_20261003_01.log`.

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

This was an agent visual inspection, not player identity ground truth. At
Phase 1 finalization, the separate human validation templates, event annotations,
and registry approval were still pending. Current HSU review progress is
recorded above; it does not alter the completed clip-level Phase 1 result.

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

1. Preserve all five completed HSU qualitative reviews and their uncertainty.
   Collect the classmate's manual `pitch_003` coordinate pilot, validate its
   format/source, then collect the complete annotation and the two clips'
   independent event supplements. Review disagreements together, preserving
   reviewer provenance and the original labels; do not automatically merge.
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
