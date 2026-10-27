# Current status — One command for the saved-motion descriptive delivery

Updated: 2026-10-27 (Asia/Taipei)

**Phase 1 = PASSED.**
**Native interface integration = PASSED (cached compatibility and optional live COCO17 entry).**
**Phase 2 evaluation = COMPLETE; Phase 2 = NOT PASSED (automatic reliability degraded).**
**User-authorized Phase3 first descriptive motion delivery = COMPLETE; overall Phase3 NOT EVALUATED.**

The new [single delivery command](native_descriptive_profile.md#建議入口一個指令整合三步)
connects the existing event report, profile and evidence-viewer writers, with one
START_HERE entry for each pitcher. The [profile review entry](native_descriptive_profile.md#從摘要直接回看影片證據)
links within-pitcher summaries and saved pairs to independent source-frame players.
The [single-pitcher summary command](native_descriptive_profile.md) reproduces
within-pitcher timing relations and model-XY elbow/knee endpoint descriptions from
bound saved event reports. The [portable02 viewing snapshot](phase3_portable_review_20261026.md) combines
[manual-event timing comparison and two-player source review](native_timing_comparison.md),
separate [Ohtani](profiles/shohei_ohtani_descriptive_v1.md)
and [Yamamoto](profiles/yoshinobu_yamamoto_descriptive_v1.md) descriptive profile drafts,
and the descriptive motion v1 described in [MOTION_ANALYSIS_V1](MOTION_ANALYSIS_V1.md).
The underlying delivery covers the accepted native skeletons
for Ohtani5 and active Yamamoto4; dated sections below preserve prior scope and results.
Automatic reliability remains unaccepted. Existing acceptance thresholds, confidence
gates, MediaPipe settings, interpolation and smoothing are unchanged. The approved
optional subject-region constraint is described below; the default selector remains compatible.
The original Phase 1 stable state and five formal videos remain unchanged.

## 2026-10-27 One command for existing descriptive writers

Added build-native-motion-report. It preflights the existing saved-curve/manual-
event request and then claims a fresh output directory, runs the unmodified event,
profile and review writers in order, and publishes START_HERE.html only when all
components succeed. delivery_manifest.json binds original sources and component
artifacts. Errors stop subsequent writers and preserve partial output with an
incomplete marker; existing output is never silently resumed or overwritten.

This is orchestration after saved skeletons/curves and reviewed events exist,
not an inference entry for a new MP4. No model, pose/tracking, gates, smoothing,
interpolation, raw predictions, GT or reference status changes. Original media
remain in project source locations; this is not a new portable package. Overall
Phase statuses and browser-playback verification remain unchanged.

Local entries: `analysis_results/phase3_native_motion_delivery_20261027_01/{ohtani,yamamoto}/START_HERE.html`.

Ohtani5/1684 frames:40 timing pairs, all comparable;40 calculable joint summaries.
Yamamoto4/477 frames:24 timing pairs (16 comparable/8 unresolved),32 joint
summaries (26 calculable/6 unresolved). Both summaries and clip records match
the previous separate outputs exactly. Each entry has10 contained file links.

Added7 integration/orchestration tests. Full Python suite1318: initial1308 passed/
0 failed/10 skipped; the8 junction capability cases passed a bounded retry.
Unique totals1316 passed/0 failed/2 skipped, including formal five-video E2E;
remaining skips are file-symlink capability limitations. JS is unchanged, so the
same Node suite was not rerun; the prior23 passing cases remain applicable.
[Delivery and exact test records](dataset_selections/phase3_native_motion_delivery_20261027.json).

## 2026-10-27 Single-pitcher summaries linked to source-frame evidence

Added review-native-profile. A stage selector and a single canonical-pair selector
show the saved timing relation, cohort direction groups and selected clips'
elbow/knee endpoints, including missing/unresolved counts. Confirmed event lower
and upper bounds navigate the two independent source-frame players. Pair identity
is retained across stage changes; no reverse or self comparisons are generated.
One-clip input uses one player and its saved duration, without a comparison.

The profile, original stage readouts, bound sources and artifact hashes are checked
before fresh output. A small shared helper packages source pages; the original
native motion player and frame-link adapter remain unchanged. Existing two-pitcher
timing mode remains available. Raw curves, events, predictions, gates and model
logic are unchanged. No new inference/tracking/GT/reference promotion or human
acceptance. Pointwise reliability remains unknown, usable_for_analysis null, and
browser playback unverified. Portable02 remains its prior snapshot.

Local pages: `analysis_results/phase3_native_profile_review_20261027_01/{ohtani,yamamoto}/review_profile.html`.

Ohtani5/1684 frames and40 original pairs (all comparable); Yamamoto4/477 frames
and24 pairs (16 comparable/8 unresolved). Nine source pages retain2161 rows,
and all72 joint summaries/pair data match the saved profiles. No reverse/self
pairs are added. Shared page URLs remain separate iframe documents.

Added8 Python/5 Node tests. Full Python suite1311: initial1301 passed/0 failed/
10 skipped; bounded retry passed the8 junction capability cases. Unique totals
1309 passed/0 failed/2 skipped, including formal five-video E2E. Remaining skips
are file-symlink capability limitations. Node23 passed/0 failed plus34 existing
event-helper assertions. Full log reports OK; the shell wrapper returned1 despite
the runner's successful=true/zero-failure result, matching the prior host anomaly.
[Delivery and exact test records](dataset_selections/phase3_native_profile_review_20261027.json).

## 2026-10-27 Reproducible single-pitcher descriptive profiles

Added describe-native-profile, accepting one existing source-bound event report
and a fresh analysis_results output. It verifies original inputs and saved manual
stage readouts, then exports profile.json, report.md, timing_relations.csv and
joint_direction_summary.csv. Arbitrary pitcher identities and one-clip input are
supported; one clip has no between-clip comparisons or repeatability inference.

Ohtani5/1684 frames:40 within-pitcher timing pairs, all comparable;40 joint stage
summaries with calculable endpoints. Active Yamamoto4/477 frames:24 timing pairs,
16 comparable/8 unresolved;32 joint stage summaries,26 calculable/6 unresolved.
All72 joint summaries match original stage readouts;64 timing CSV rows and16
direction rows match JSON. Source and artifact hashes are verified. Unresolved
events keep null counts, known events with missing endpoints retain zero counts;
partially missing endpoint pairs remain in the output, without filtering.

Timing uses exact fractional seconds. Every admitted within-pitcher pair is kept;
joint signs are classified before display rounding. Yamamoto001 follow-through
knee retains the small negative bound (-0.040605879997...) and includes_zero.
Yamamoto005 preparation0 and leg-lift33 remain uncertain candidates. Historical003
remains excluded. No new inference, tracking, GT, gates, model/core edits, reference
promotion or phase-wide acceptance. Pointwise reliability remains unknown and
usable_for_analysis null. This is not the formal pitcher-profile-v1 contract.

Outputs: `analysis_results/phase3_native_profiles_20261027_01/{ohtani,yamamoto}/`.
Portable02 remains the prior viewing snapshot; this command does not rebuild it.

Added12 tests. Full Python suite1303: initial1293 passed/0 failed/10 skipped;
the8 junction capability cases passed on a bounded host-permission retry. Unique
totals1301 passed/0 failed/2 skipped, including formal five-video E2E. Remaining
skips are file-symlink capability limitations. Node18 passed/0 failed, plus34
existing event-helper assertions. No RTMPose/detector inference in the feature or
test run. [Delivery/test receipt](dataset_selections/phase3_native_profiles_20261027.json).

## 2026-10-26 Current descriptive delivery packaged as portable02

Created a new offline review package without changing product/test code or analyses.
It combines9 raw videos/9 overlays and2161 frames, original metadata/GT/native output,
two readable HTML profile drafts with Markdown copies, both latest four-stage reports
and CSV/JSON, the80-pair timing comparison and latest two-player review pages. Existing
event/alignment dependencies referenced by the profiles are included; original JSON
paths/SHA stay as provenance, with a package source mapping for review copies.

Package183 files/34,261,702 bytes (~32.7 MiB).169 HTML/media links are package-contained;
171 source SHA references remain unchanged.43 embedded viewer URL fields are rebased,
while all other embedded labels/numbers/unknowns remain identical. Raw media, GT,
predictions, CSVs and JavaScript are unchanged copies. ZIP CRC and safe unique paths
are checked. Old portable01 output remains unchanged; the02 entry is
`analysis_results/phase3_portable_review_20261026_02/pitch_motion_review_20261026_02/START_HERE.html`.

This is a viewing/data-check copy, not a complete model/runtime or a directly
rerunnable CLI environment. Ohtani remains candidate and historical Yamamoto003 is
excluded. No new inference, GT, human page acceptance or phase-wide acceptance.
Browser playback remains unverified. No full-suite rerun for this packaging-only
change; same-code results remain1289 passed/0 failed/2 skipped, Node18 passed plus34
existing event-helper assertions.
[Download/usage](phase3_portable_review_20261026.md),
[versioned delivery receipt](dataset_selections/phase3_portable_review_20261026_02.json).

## 2026-10-26 Two-player source-frame review for saved timing pairs (previous)

Added review-native-timing and a separate viewer builder. The existing comparison
and bound source reports are verified again; altered pairs/cohorts or existing
outputs are rejected. Four stage choices and the two clip selectors expose the
same80 saved pairs (65 descriptive,15 unresolved), without modifying timing data.

Each clip uses its own page and the unchanged native_motion_viewer.js. Two iframes
play independently at their native FPS. Confirmed event lower/upper bounds become
explicit source-frame buttons; uncertain/unobservable events do not acquire seek
buttons. A thin hash adapter waits for loaded metadata, keeps the latest request,
supports repeated requests to the same frame and refuses out-of-range hashes.
It invokes the old seek control and does not claim that a requested frame has
already been presented. No time warp, joint interpolation, new inference or GT.

Actual delivery:9 source pages/2161 rows,80 identical saved comparisons,15 null
pair differences and3 unresolved events retained. Original player JS is byte-
identical. Entry:`analysis_results/phase3_manual_timing_viewer_20261026_01/review_timing.html`.
Browser playback/interaction was not inspected; simulated-DOM and pure Node tests
are software checks, not human overlay acceptance or new ground truth.

Added6 Python tests and7 Node tests. Full Python1291 tests:1281 passed/0 failed/
10 skipped initially;8 junction capability cases rerun outside the sandbox all
passed. Unique aggregate1289 passed/0 failed/2 skipped, including formal five-video
E2E. Remaining skips are Windows file-symlink limits. Node18 passed/0 failed, plus
34 existing event-helper assertions. Raw/GT, adopted skeleton method, thresholds
and phase-wide acceptance remain unchanged.
[Usage](native_timing_comparison.md),
[versioned source/test evidence](dataset_selections/phase3_manual_timing_viewer_20261026.json).

## 2026-10-26 Reusable two-pitcher manual timing comparison (previous)

Added the independent compare-native-timing CLI and native_timing_comparison module.
Two saved single-pitcher reports are rechecked through their bound request, source
curves and existing manual-event review scope. Saved clip records must match current
bound sources; altered reports and existing output directories are refused. Existing
same-pitcher modules and Phase2 core/gates remain unchanged.

Each stage compares all cross-cohort clip pairs using per-clip Fraction FPS. Delta
is[A_min-B_max,A_max-B_min] in exact fractional seconds, retaining overlap/touch/equal
relations and unavailable reasons. A1/7500-second arithmetic difference is not rounded
into equality, and is not asserted as physiological timing accuracy. No pose-angle
comparison, normalization, quality score, ranking, new inference/tracking or GT.

Ohtani5 and active Yamamoto4:9 clips/2161 frames,36 original timings,80 cross-cohort
pairs.65 are descriptive and15 retain unresolved manual events; per-stage comparable
counts are10/15/20/20. Historical003 stays excluded; Ohtani stays candidate. Source
frames/FPS, event bounds and paths/SHA remain traceable in JSON and the two CSVs.
Actual80 fractional deltas/unknowns and15 blank CSV deltas are verified; overwrite
rejection is exercised. Phase-wide acceptance and original raw/GT states are unchanged.

Added15 tests. Full1285-test suite:1275 passed/0 failed/10 skipped in the sandbox;
the8 directory-junction capability skips were rerun outside the sandbox in bounded
local temporary directories and all passed. Unique aggregate:1283 passed/0 failed/
2 skipped, including formal five-video E2E. Remaining skips are file-symlink capability
limits. Full/retry logs and validation_summary.json retain both actual runs.
Output:`analysis_results/phase3_manual_timing_comparison_20261026_02/`.
[Usage and limits](native_timing_comparison.md),
[versioned delivery evidence](dataset_selections/phase3_manual_timing_comparison_20261026.json).
Generated tracked bytecode from the CLI invocation is restored; only the new timing
module/test, CLI registration and documentation are committed.

## 2026-10-26 Yamamoto same-pitcher descriptive profile draft (previous)

Applied the same bounded narrative scope to active Yamamoto001/002/004/005:477 frames,
20 existing events,16 stage timings and32 joint summaries. Of these,17 events have
annotated bounds,13 timings are descriptive and26 joint summaries are calculable;
3 timings/6 joint summaries retain unresolved events. Historical003 remains excluded.

The draft preserves the shorter plant-to-release timing in002 compared with001/004,
and the shorter release-to-follow-through timing in001/004 compared with002/005.
All available leg-lift-to-plant ranges overlap/touch, so no strict ordering is asserted.
005 candidate preparation0/leg-lift33 remain uncertain and are not used for timing.
The001 knee release-to-follow-through interval crosses zero at full precision
(-0.04060588 to+6.27883484 degrees), despite the former rounded display of-0.0.
005 elbow endpoint signs are opposite to the other clips in the last two intervals;
no anatomical reversal or model-error conclusion is inferred from that observation.

The two same-pitcher descriptive drafts are delivered with original-frame review
links, known limitations and separate source lists. No cross-pitcher comparison,
new features, inference, labels, thresholds or core changes. Local links and
source-backed tables are checked; unchanged product suite is not rerun. Latest
code suite remains1268 passed/0 failed/2 skipped, including formal five-video E2E.
Phase-wide acceptance and original raw/GT states remain unchanged.

## 2026-10-26 Ohtani same-pitcher descriptive profile draft (previous)

The draft answers the planned question using the existing five clips: which stage
differences survive all legal manual-event frame choices, and which depend on those
choices? It combines all20 timings, the40 elbow/knee endpoint summaries, existing aligned
curves and source-frame review links. No new numeric feature, inference or manual label.

The document identifies the longer preparation-to-leg-lift intervals in001/004, the
shorter leg-lift-to-foot-plant interval in005, and the overlapping/touching intervals
that do not establish strict ordering. It retains common model endpoint signs and
exceptions, including005 knee sign ambiguity and003 negative plant-to-release knee
change. Relations are checked in integer frame bounds, not rounded display seconds.

It explicitly distinguishes this sample's descriptive observations, frame-choice
sensitivity and insufficient information. Pitch type/session metadata is missing;
pointwise quality and 3D interpretation remain unestablished. This is a readable draft,
not a formal pitcher-profile-v1 reference or phase-wide acceptance. Read the draft
before deciding Yamamoto rollout or cross-pitcher scope; neither is started here.

Documentation and interpretation only: unchanged product code, pose/tracking, raw/GT,
gates and unknown/null states. Local links and source-backed tables are checked; no
rerun of unchanged pipeline/full suite. Latest code suite remains1268 passed/0 failed/
2 skipped, including formal five-video E2E. Commit and push this bounded delivery.

## 2026-10-26 Descriptive v1 review and main-route documentation (previous)

Reviewed the nine saved curve plots, both current four-interval reports, saved summaries
and release-frame CSV readouts. All2161 frames have calculable elbow/knee model angles,
but pointwise reliability remains unknown and usable_for_analysis remains null. Of36
manual-event intervals,33 are descriptive and3 retain unresolved events. This is a bounded
descriptive delivery, not calibrated biomechanics or a full native motion profile.

The v1 guide gives one route to the latest reports, existing video/curve/event pages
and the earlier portable viewing snapshot. The existing ZIP has no manual_stage files;
it is not represented as the latest four-interval report bundle. No assets were repacked.
README now leads with the adopted native17 workflow and labels the retained MediaPipe33
path as historical compatibility; the stale Phase2-only continuation text is replaced.
Detailed development history and prior source/test records remain available.

The next planned unit is one same-pitcher profile draft using existing Ohtani5 data:
identify which stage differences survive all legal manual-event frame choices and which
depend on those choices, with original-frame review links and explicit insufficient-data
conclusions. Completion scope is written in the v1 guide. It is not implemented by this
documentation change. No new features, inference, GT, core changes or quality gates.

Documentation-only change; do not rerun the unchanged model pipeline or full test suite.
Latest product-code suite remains1268 passed/0 failed/2 skipped (Windows file-symlink
capabilities), including the formal five-video E2E. Phase-wide acceptance states above
are unchanged. Local documentation links and Git whitespace/diff checks are verified
before this checkpoint is committed.

## 2026-10-26 Four manual-event interval readouts (previous delivery)

The existing event report now includes all four intervals between the five existing
manual events, with original timing and throwing-elbow/lead-knee model-XY endpoint
differences. Ohtani5 and active Yamamoto4 cover36 intervals and72 joint summaries:
33 descriptive intervals,3 unresolved intervals (6 null joint summaries),77 legal
event-frame pairs and154 joint-pair rows. No new events or phases are inferred.

All candidate pairs retain source frames, fractional-FPS elapsed time, endpoint
states and nulls. Adjacent intervals share events; independent extrema must not be
summed into a candidate trajectory with inconsistent intermediate frames. No whole
trajectory, phase normalization, motion score or anatomy inference is introduced.

Independent saved-CSV/manual-bound audit found no differences across72 summaries
and154 joint-pair rows. All9 original clip records,90 windows,36 timings,18 legacy
single-interval summaries and40 pair rows remain identical. All8 old CSVs are byte-
identical, and585 protected source hashes are unchanged. Legacy single-interval API
and CSV remain compatible. Added8 Python tests; the43-test targeted collection passes.
Full suite:1270 run,1268 passed/0 failed/2 skipped, including the formal five-video
MediaPipe E2E. Both skips are unavailable Windows file-symlink capabilities; no unresolved
test failures. Full evidence is in the receipt. JavaScript/player unchanged; no Node rerun or
new browser/human acceptance. Pose/tracking, thresholds, raw/GT and unknown/null remain.
Output: `analysis_results/phase3_manual_stages_20261026_01/`.
[Results and usage](phase3_manual_stages_20261026.md),
[source and test receipt](dataset_selections/phase3_manual_stages_20261026.json).
Stop after full tests, documentation, commit and origin push; phase-wide states remain.

## 2026-10-26 Foot-plant to approximate-release endpoint changes (previous)

The normal event report now describes release-angle minus foot-plant-angle for the
throwing elbow and lead knee. All chronological pairs within the existing manual
event bounds are retained, including equal-frame pairs; reversed pairs are counted
separately. No midpoint, new phase label, new pose inference or imputation is used.

Ohtani5 and active Yamamoto4 produce18 joint summaries,20 legal event pairs and40
joint-pair records. Each preserves source frames, endpoint states and fractional-FPS
elapsed time. All40 are numerically calculable; pointwise quality remains unknown/null.
Candidate pairs share frames and are not independent samples. Delta extrema are model
projection endpoint differences, not within-transition range of motion, anatomical
flexion, calibrated accuracy or motion quality. Unresolved events do not supply candidates.

Independent read-only audit checked all18 summaries/40 joint pairs against saved CSV
and manual bounds, including exact fractional times and signs (16 positive/2 negative).
All original9 clip records,90 event windows and36 timings remain unchanged. The four
old timing/angle CSVs are byte-identical; all564 protected source hashes are unchanged.
Added11 Python tests. Full suite:1262 run,1260 passed/0 failed/2 skipped, including
the formal five-video MediaPipe E2E. Both skips are unavailable Windows file-symlink
capabilities; no unresolved test failures. Complete evidence is in the receipt.
JavaScript/player unchanged; no Node rerun, browser interaction or new human acceptance.
Raw/GT, skeleton workflow, thresholds and all phase-wide acceptance states remain.
Output: `analysis_results/phase3_event_transition_20261026_01/`.
[Per-pitcher results and CSVs](phase3_event_transition_20261026.md),
[source and test receipt](dataset_selections/phase3_event_transition_20261026.json).
Stop after tests, documentation, commit and origin push.

## 2026-10-26 Event-window readout integration (previous)

The existing compare-native-motion-events command now emits event angle tables in
report.md and event_angle_readouts.csv, plus explicit readout wording in the viewer.
Single-frame windows retain null sensitivity spans. Multiframe spans require at least
two calculated samples; partial windows describe calculated samples only and retain
the full denominator and missing/degenerate counts. Unresolved events do not use candidates.

Fresh Ohtani5 and active Yamamoto4 outputs cover2161 frames and90 joint windows:
60 single,24 multiframe,6 unresolved. All720 original window fields and36 timings
are unchanged, with byte-identical timing CSVs. Independent read-only audit confirmed
the90 CSV rows and null semantics; all545 protected source hashes are unchanged.
No new pose/tracking calls, labels, thresholds or core changes; base player JS unchanged.
The original raw/GT, prior outputs and portable ZIP remain intact.

Added8 Python tests and16 pure event-helper assertions (34 total). Full Python suite:
1251 run,1249 passed/0 failed/2 skipped, including the formal five-video MediaPipe E2E.
Both skips are unavailable Windows file-symlink capabilities. Pure Node runner:
11 passed/0 failed/0 skipped, without browser or DOM. New browser interaction and
human acceptance are not claimed. Pointwise unknown/null and phase statuses remain.
Output: `analysis_results/phase3_event_readout_integration_20261026_01/`.
[Result and usage](phase3_event_readout_integration_20261026.md),
[source and test receipt](dataset_selections/phase3_event_readout_integration_20261026.json).
Stop after documentation, commit and origin push.

## 2026-10-26 Event-window angle readout (previous)

Read saved curves at the45 existing events, two joints each:90 joint windows.60 single-frame
windows retain the model value with sensitivity span null,24 confirmed multiframe windows
retain min/max and max-minus-min, and6 unresolved windows do not consume candidate angles.
The unresolved entries are Yamamoto001 preparation and005 preparation/peak lift, each
for two joints; this does not claim the underlying model curves are absent.

All84 readable min/max windows were checked against original CSV values; an independent
read-only audit confirmed all90 rows,24 spans, nullable fields and9 unchanged GT files.
Example: Yamamoto005 release58–59 elbow model-XY73.2–133.9degrees spans60.7degrees.
This describes saved numerical variation only, without identifying real motion, projection
or localization error. No reliability rating or threshold is inferred from the span.

Separate-pitcher figures were visually inspected; CSV retains all event statuses, model
sample/missing/degenerate counts and source path/SHA. All65 used source hashes unchanged.
The prior portable ZIP is unchanged. No product/test code change, new pose calls or GT;
latest same-code suite remains1241 passed/0 failed/2 skipped and is not rerun here.
Unknown/null and phase-wide acceptance states remain.
Output: `analysis_results/phase3_event_angle_readout_20261026_01/`.
[Readout and figures](phase3_event_angle_readout_20261026.md),
[source receipt](dataset_selections/phase3_event_angle_readout_20261026.json).
Stop after saving, commit and origin push.

## 2026-10-26 Portable review bundle (previous)

Packaged existing nine accepted skeleton clips: Ohtani5/1684frames and active
Yamamoto4/477frames,2161 total. Yamamoto003 remains historical and is excluded.
The bundle includes original MP4s, overlays, metadata, raw native predictions/tracks,
curve artifacts, original GT, Ohtani event checkpoints, four rebased viewer pages,
same-pitcher figures, event contact sheets, a single START_HERE.html and source manifest.

ZIP:33,976,990bytes (~32.4MiB),136files. Rebased pages change only clips[].overlay_url;
all other embedded values and original JS bytes remain. Copied GT/CSV/raw assets retain
source bytes. All79 local HTML/video links resolve inside the bundle; source hashes,
archive CRC, entry path safety and uniqueness checks pass. Original outputs remain unchanged.

Full extraction is required; open START_HERE.html with Chrome/Edge. No Python/model
environment is required to view existing outputs. Original JSON references stay as
provenance; bundle_manifest maps them to local copies. Ohtani GT remains event-only
in_progress, and old Yamamoto joint-quality labels are not transferred to new skeletons.
No new human-page acceptance or browser/DOM automation is recorded.

No product/test code changes, inference, tracking replay or new GT. Latest same-code
suite remains1241 passed/0 failed/2 skipped; full suite not rerun for packaging.
Output: `analysis_results/phase3_portable_review_20261026_01/`.
[Package and opening instructions](phase3_portable_review_20261026.md),
[ZIP/source receipt](dataset_selections/phase3_portable_review_20261026.json).
ZIP remains local; only delivery documentation is committed/pushed. No GitHub release
upload or phase-wide acceptance change. Stop after this delivery, commit and origin push.

## 2026-10-25 Retained manual anchor bounds for all four Yamamoto clips (previous)

Added optional --retain-anchor-ranges to align-native-motion. The existing exact mode
continues to reject ranged anchors. In the new mode, annotated ranges retain all integer
origin candidates; uncertain/unobservable foot plant remains unavailable. Single-frame
ranges remain bounded rather than being promoted to an exact human event.

Actual four-clip delivery retains477 unique source rows.001 uses34/35,002 uses140,
004 uses65/66,005 uses55. Six alternative display shifts represent four source clips;
they are not extra observations. CSV does not duplicate samples. Each row gains [(i-anchor_max)/fps,(i-anchor_min)/fps]
and exact fractional seconds. Original fields compare equal; no midpoint or probabilities.
Existing foot-plant-to-release timing remains4–6/1–3/4–6/3–4frames.005 preparation and
peak-lift candidates remain uncertain. Both plots were visually inspected; an independent
read-only check confirmed original fields, fractional bounds and preserved event states.

All539 protected hashes unchanged. No new inference, tracking replay, GT labels,
resampling, angle recomputation, smoothing or interpolation. Exact viewer/player and
active cohort001/002/004/005 remain;003 stays historical. Unknown/null and phase states remain.
Ten new tests added; complete result is in the [source/test receipt](dataset_selections/phase3_yamamoto_anchor_bounds_20261025.json).
Full suite:1243 run /1241 passed /0 failed /0 errors /2 Windows file-symlink capability skips,
including formal five-video E2E.
Output: `analysis_results/phase3_yamamoto_anchor_bounds_20261025_01/`.
[Entry page and interpretation](phase3_yamamoto_anchor_bounds_20261025.md).
Stop after this bounded delivery, tests, commit and origin push.

## 2026-10-25 Yamamoto exact-anchor reuse and viewing index (previous)

Reused the same existing alignment/viewer commands on Yamamoto002/005:276 source rows,
30/1 FPS, exact human foot plants140/55. Source CSV fields compare equal;276 frame-time
roundtrips and552 model-angle values are preserved. Two static plots were visually inspected.
No product/test code changed, model inference, tracking replay or new human labels.
All524 protected hashes unchanged. Latest same-code suite remains1231 passed/0 failed/2 skipped;
no full-suite rerun for this configuration/data/document-only reuse.

001 foot plant34–35 and004 foot plant65–66 remain ranges in the original four-clip event page.
Neither a midpoint nor a new label is selected. The active cohort remains001/002/004/005;
003 stays historical.005 preparation candidate0 and peak-lift candidate33 remain uncertain.
002 release is+1–3frames (1/30–1/10seconds),005 is+3–4 (1/10–2/15); they touch at+3frames.
Only events are consumed from historical GT; old pose-quality labels are not transferred.

Output: `analysis_results/phase3_yamamoto_exact_alignment_20261025_01/`.
Its index.html links separately to Yamamoto exact two-clip alignment, all four original
event/curve clips, and Ohtani five-clip alignment. No cross-pitcher metric comparison.
[Delivery and entry page](phase3_yamamoto_exact_alignment_20261025.md),
[source receipt](dataset_selections/phase3_yamamoto_exact_alignment_20261025.json).
No browser/DOM automation or new human-page acceptance. Existing unknown/null and overall
phase states remain. Stop after saving, commit and origin push.

## 2026-10-25 Aligned-curve source-frame viewer delivery (previous)

Added review-native-motion-alignment from the existing bound event request. The page
draws saved multi-clip curves relative to exact human foot plant; clicking a curve
selects its clip and requests the nearest original source frame. Legend buttons return
to each exact foot plant; full/±0.5-second views retain the same samples. The original
player and its script bytes are unchanged; single-clip charts remain in a details panel.

Cross-clip requests wait until selected source/currentSrc and loaded controls agree.
Only the latest pending request is applied; manual selection/error cancels stale requests.
The aligned cursor uses the base player's frame label and distinguishes presented frames
from its explicitly labeled fallback time estimate. Release bounds remain bands/lines;
uncertain candidates remain dashed, and missing samples keep line breaks.

Actual data checks:1684 source-frame time roundtrips and3368 model-angle values preserved;
all521 protected hashes unchanged. Source CSV times/values/states and GT remain unchanged.
New pose calls0, tracking replay0, GT labels0; unknown/null reliability remains.
Eight new Python packaging/source tests and five pure Node mapping/navigation tests added.
Full suite:1233 run /1231 passed /0 failed /0 errors /2 file-symlink capability skips,
including formal five-video E2E. Existing playback Node tests5 and event assertions18 also pass.
Complete test receipt: [source and checks](dataset_selections/phase3_ohtani_alignment_viewer_20261025.json).

Output: `analysis_results/phase3_ohtani_alignment_viewer_20261025_01/viewer/review_alignment.html`.
[Opening and controls](phase3_ohtani_alignment_viewer_20261025.md).
No browser/DOM automation was performed. Code/data tests do not establish real browser
interaction; new page human acceptance is not yet recorded. Stop after this bounded
delivery, tests, commit and origin push; no phase-wide acceptance change follows.

## 2026-10-25 Ohtani foot-plant alignment delivery (previous)

HSU authorized the proposed next step with「繼續」: shift each saved curve to the
exact human foot plant, preserving release ranges. New align-native-motion reuses
the existing same-pitcher event/source loader; the default event comparison remains
compatible. The loader was factored out without changing its source or GT checks.

All1684 original CSV rows and fields compare equal. Only relative frame/time fields
are added, using (frame_index - foot_plant_frame) / Fraction(fps). Anchors001–005 are
110/129/156/124/124, with exactly one zero per clip. Two plots show complete timelines,
the same samples in a ±0.5-second display zoom, and manual release locations/ranges.
Relative release frames remain9–10/8/8/5/10–11. No midpoint, resampling, time warping,
smoothing, interpolation, angle recomputation, quality filtering or cohort averaging.

Exact annotated single-frame anchors are required; ranged or uncertain foot plant
cannot be silently assigned a zero. All513 protected hashes are unchanged. New pose
calls0, tracking replay0, GT labels0; original skeleton method, gate and unknown/null
reliability states remain. Both plots were visually inspected; an independent read-only
audit also confirmed unchanged source fields and fractional event bounds.

Eleven new tests added. Full suite:1225 run /1223 passed /0 failed /0 errors /2 skipped,
including formal five-video E2E; skips require unavailable Windows file symlinks.
The complete suite result is recorded in the
[source/test receipt](dataset_selections/phase3_ohtani_foot_plant_alignment_20261025.json).
Output: `analysis_results/phase3_ohtani_foot_plant_alignment_20261025_01/alignment/`.
[Result and command](phase3_ohtani_foot_plant_alignment_20261025.md).
Stop after this bounded delivery, tests, commit and origin push; overall phase states remain.

## 2026-10-25 Ohtani event-frame readout delivery (previous)

Read-only reuse of the completed event comparison: all 31 source frames inside the
25 confirmed event windows are exported as original/accepted-overlay pairs (62 images),
five event contact sheets, a static gallery and angle tables. Every frame in a human
range is retained, including005/96–99; no event midpoint or new label is introduced.
Viewing crops reuse the previously approved rectangles; uncut source links remain.

The report describes timing differences and saved elbow/knee model-XY windows, and
highlights that near-zero elbow XY angles at001/110 and002/129 cannot be interpreted
as true anatomical flexion. No automatic error labels, corrected coordinates, ranking,
standard motion profile, cross-pitcher comparison or new annotation task is introduced.

All five contact sheets were visually checked for pairing, frame labels and layout;
this is not human pointwise GT or browser/DOM validation. All515 protected file hashes
remain unchanged. Product/test code changes0, new inference0, tracking replay0, GT labels0.
No suite rerun for this data/document-only step; latest same-code combined test result
remains1212 passed /0 failed /2 skipped. Existing unknown/null and overall phase states remain.

Output: `analysis_results/phase3_ohtani_event_readout_20261025_01/`.
[Readout and image guide](phase3_ohtani_event_readout_20261025.md),
[source receipt](dataset_selections/phase3_ohtani_event_readout_20261025.json).
This bounded readout ends after saving, commit and origin push; it adds no new model or feature.

## 2026-10-25 Ohtani event-only comparison delivery (previous)

The existing comparison now accepts an optional source-bound event-review checkpoint,
without promoting in-progress GT to a full review. It checks exact five-event scope,
completion flags, reviewer, recording time, pitch identity and GT/video path+SHA.
The old fully-reviewed GT path remains valid; in-progress GT without a checkpoint
is still rejected. No schema/validator, pose/tracking core or acceptance gate changed.

Actual Ohtani delivery: five clips, 1684 saved curve rows, 25 unchanged manual events
(21 exact / four ranges), and 20 available timing intervals (14 exact / six bounded).
Outputs include event_comparison.json, event_timing.csv, report.md, the existing
event viewer with the accepted playback scripts, and a static timing_intervals.png.
No event midpoints, angle recomputation, new pose calls, tracking replay or GT labels.
All 512 protected hashes are unchanged. GT remains in_progress with non-event labels
and reviewed_at_utc null; pointwise reliability unknown and usable_for_analysis null.

Full suite: 1214 run, 1204 passed / 0 failed / 0 errors / 10 skipped, including formal
five-video MediaPipe E2E. Eight directory-junction cases skipped because of sandbox
limitations were retried alone with appropriate permissions: 8 passed / 0 skipped.
Combined unique outcomes: **1212 passed / 0 failed / 0 errors / 2 skipped**; the remaining
two require unavailable Windows file-symlink support. Eleven new Python tests added.
Original playback Node tests (5) and event helper assertions (18) pass. No browser/DOM
automation performed; the static timing plot was visually inspected.

Output: `analysis_results/phase3_ohtani_event_timing_20261025_01/`.
[Delivery and viewing instructions](phase3_ohtani_event_timing_20261025.md),
[source and test receipt](dataset_selections/phase3_ohtani_event_timing_20261025.json).
Next: view the event/curve page; human acceptance of this new page is not yet recorded.
Stop after this delivery, commit and origin push. No new pitcher, ranking, cross-pitcher
comparison or change to overall Phase2/Phase3 acceptance follows automatically.

## 2026-10-25 Ohtani five-clip manual event review closeout (previous)

HSU completed 004: preparation 39, peak lift 71, foot plant 124, approximate
release 129, follow-through end 180. Overview candidates 40 and 192 were corrected
to 39 and 180 after consecutive-frame review. Original answers/history remain.

HSU completed 003: preparation 105, peak lift 119, foot plant 156, approximate
release 164, follow-through end 208. The start candidate 104 was corrected to 105;
the end candidate 208 was confirmed with「對」after consecutive-frame review.
The earlier「沒有」did not establish a landing or unobservable label; 156 came
from the later direct human answer. Original answers/history remain.

HSU completed 002: preparation 78, peak lift 95, foot plant 129, approximate
release 137, follow-through end 203. Overview candidates 80 and 208 were corrected
to 78 and 203 after consecutive-frame review. Original answers/history remain.

HSU has now completed 001: preparation 28, peak lift 59, foot plant 110,
approximate release 119–120, follow-through end 160. The original final response
「對]」confirms 160 after the consecutive-frame follow-up and is preserved exactly.
The preliminary start candidate 32 was corrected to 28 by the human reviewer.

HSU reviewed consecutive original-frame sheets and supplied all five 005 events:
preparation 81–82, peak lift 96–99, foot plant 124, approximate release 134–135,
follow-through end 169. Exact frames and ranges are retained without midpoints.
The preliminary overview candidates 88 and 176 are superseded by the later human
answers, with the original statements and correction history preserved.

Existing ground-truth-v1 schema, source binding, bounds and event order validate.
The GT remains in_progress, reviewer HSU, reviewed_at_utc null; all non-event
labels remain null. A source-bound workflow checkpoint records only completion
of the five-event scope, not completion of full pose GT or pointwise reliability.
All five clips now have complete event scopes: 25 annotated events, 21 exact
frames and four frame ranges; no event answers remain unfilled.

The final 004 helper retains 338 raw viewing crops, 29 consecutive sheets and
uniform overview pages using the already approved fixed source rectangle.
All 504 protected file hashes remain unchanged. No product/test changes, model
replay or suite rerun. Latest same-code full suite remains 1201 passed / 0 failed /
2 skipped at this review checkpoint. Event-only consumption was deferred here;
the subsequent bounded integration is recorded above, without fabricating non-event labels.

[Progress/source checkpoint](dataset_selections/phase3_ohtani_event_review_progress_20261024.json),
[review workflow](phase3_ohtani_event_review_20261024.md). No further human event
answers are needed for these five clips. Stop after saving, committing and pushing
this review closeout; the subsequent comparison adapter is recorded above.

## 2026-10-24 Ohtani manual-event review preparation (previous)

Following「繼續」, preparation creates five blank existing ground-truth-v1 templates,
bound to decoded source counts 335/321/369/338/321 (1684 total). All human fields,
reviewers and completion timestamps remain null/unreviewed; no event was guessed.
Review begins with preferred supplement_005, then 001/002/003/004.

005 has all 321 raw-frame viewing crops, 27 consecutive 12-frame sheets, uniform
every-eight-frame overviews and a static frame gallery linked to the original
video and accepted player. The crop is the previously approved fixed rectangle,
not model/event-driven frame selection. Source MP4s and accepted skeletons stay.

This collects only five events. After a human answer, the existing GT can be
in_progress with that reviewer's provenance while all unreviewed non-event labels
remain null. Event completion does not establish full pose GT. Current comparison
requires full reviewed GT; scoped event-only consumption remains a later task,
without fabricating other labels or changing schema/validator this round.

504 prior data/source/product/test files retain their SHA. No production/test code
changes, model calls, tracking replay or new human labels. No suite rerun; latest
same-code results remain 1201 passed / 0 failed / 2 skipped. Image labels/layout
checked; automated browser verification is unperformed.

[Workflow/templates](phase3_ohtani_event_review_20261024.md),
[source-bound preparation](dataset_selections/phase3_ohtani_event_review_20261024.json).
Await human event answers for005; no next feature or automatic annotation starts.

## 2026-10-24 saved interval timing readout (previous)

Following「繼續」, this bounded data-only delivery reads the prior source-bound
four-clip comparison and exports a PNG plus a Chinese interpretation and all 24
pairwise interval relations. The 16 original timing rows are unchanged. Interval
relations use exact integer-frame bounds; endpoint contact counts as overlap.
Seven pairs are disjoint, nine overlap/touch, eight are unavailable. These counts
are descriptive bookkeeping, not statistical evidence or new acceptance criteria.

Peak-lift-to-plant intervals overlap for all three comparable clips. 002 plant-to-
release is separated from 001/004 under the existing manual boundaries. Neither
relation establishes motion identity, quality or a stable pitcher profile.
Viewed the exported plot: labels, bounds and missing-value messages are readable.
No midpoint is drawn for interval bars; unobservable/uncertain values remain absent.

504 protected data/source/product/test files retain their SHA. Production/test
code changes, new inference and new GT: 0. No full-suite rerun for this report-only
update; latest same-code results remain 1201 passed / 0 failed / 2 skipped.
Existing skeletons, raw, events, curves and prior human acceptance are unchanged.
003 remains historical. Phase2 NOT PASSED and overall Phase3 NOT EVALUATED remain.

The next data gap is confirmed human events for the five Ohtani clips. No event
labels, guesses, new review tool or cross-pitcher feature is started this round.
Output: `analysis_results/phase3_yamamoto_timing_readout_20261024_01/`.
[Readout](phase3_yamamoto_timing_readout_20261024.md),
[versioned evidence](dataset_selections/phase3_yamamoto_timing_readout_20261024.json).
Stop after commit/push; no next feature automatically starts.

## 2026-10-24 manual-event / saved-curve timing comparison (previous)

HSU approved this bounded next delivery with「好進行」. New compare-native-motion-events
reads the four active Yamamoto saved curve exports and exact source-bound canonical
ground-truth-v1 events. All 477 source frames and 20 manual records are retained;
17 annotated, 2 uncertain, 1 not observable. Sixteen timing rows include 13 usable
interval descriptions and 3 explicitly unavailable values with reasons.

The viewer adds exact lines, range bands and dashed uncertain candidates to the
unchanged saved curves and playback UI. Per-event model-XY windows retain full
calculated/missing/degenerate counts. Annotated interval differences retain bounds;
uncertain or unobservable endpoints never produce a guessed duration or midpoint.
005 preparation/lift candidates and 001 unobservable preparation remain unchanged.

Reviewed GT must match video SHA/name, pitch identity, full frame count and zero
origin. Only the events are used; historical joint-reliability labels are not
transferred to the new skeleton. The sole existing product-file change is additive
CLI dispatch; models, selector, gates, raw, GT, saved CSV/PNG and prior viewers stay.
New detector/pose calls, tracking replay, angle recomputation and new GT: 0.

The prior nine-clip human acceptance remains valid. This event page has no automated
browser interaction verification; no new manual annotation or acceptance gate is
introduced. Phase2 NOT PASSED and overall Phase3 NOT EVALUATED remain. No exact
event alignment, cross-pitcher comparison, profile, score or 3D inference is added.

Full Python suite: 1203 run / 1201 passed / 0 failed / 0 errors / 2 Windows file-
symlink skips, 135.796 seconds, including the formal five-video MediaPipe E2E.
Nineteen new Python tests; 5 existing pure Node timing tests and 18 new event-helper
assertions passed. No browser or DOM tests. 233 protected data files retain their
SHA; all 20 embedded manual event records match their sources without changes.

Output: `analysis_results/phase3_yamamoto_event_timing_20261024_01/comparison/`.
[Usage/formula](native_motion_events.md), [results](phase3_yamamoto_event_timing_20261024.md).
[Versioned delivery evidence](dataset_selections/phase3_yamamoto_event_timing_20261024.json).
Stop after this delivery, complete suite, commit and push; no next feature starts.

## 2026-10-24 active Yamamoto motion curves and synchronization viewer (previous)

The existing describe-native-motion and review-native-motion commands processed
the already accepted Yamamoto 001/002/004/005 without production/test code changes.
87/175/114/101 frames, 477 total, 954 calculated model-XY angles; no missing or
degenerate angles. Each clip has CSV/PNG/source summary, plus one four-clip viewer.
All sources use 30/1 FPS and original pixel aspect ratios. 003 remains historical only.

415 protected source/raw/review/prior output/product/test files retain their SHA.
New detector/pose calls, tracking replay and GT: 0. Ohtani's accepted viewer is
unchanged and was not rerun. Viewed all four plots for readable labels/layout;
raw elbow fluctuations retained, no smoothing or accuracy claim.

Source skeleton acceptance remains 4/4. HSU subsequently replied
「都正確一樣是5表現最好」, accepting all four viewer results qualitatively and
highlighting pitch_005 as the preferred demonstration. The exact statement,
reviewer, recorded UTC and page/JS/export/overlay SHA are saved separately in
annotations/motion_reviews/HSU_20261024/yamamoto_motion_sync_acceptance.json.
Current human viewer review: ACCEPTED 4/4; together with Ohtani, all nine active
viewer results have human acceptance. Original generated/pending execution
snapshots remain unchanged. Automated browser verification is still unperformed;
this acceptance establishes neither instrumented control tests nor pointwise GT.

No suite rerun for this data/document-only reuse. Latest same-code full Python
suite remains 1182 passed / 0 failed / 0 errors / 2 skipped, plus 5 pure Node tests passed.
Pointwise reliability remains unknown, usable fields null; no event alignment,
cross-pitcher comparison, profile or new quality gate. Phase2 NOT PASSED and
overall Phase3 NOT EVALUATED remain.

Output:`analysis_results/phase3_yamamoto_native_motion_20261024_01/viewer/review_motion.html`.
[Results/usage](phase3_yamamoto_native_motion_20261024.md),
[versioned evidence](dataset_selections/phase3_yamamoto_native_motion_20261024.json).
[Latest human acceptance](dataset_selections/phase3_yamamoto_motion_acceptance_20261024.json).
Stop after this bounded delivery/commit/push; no next feature automatically started.

## 2026-10-24 saved-video / motion-curve synchronization viewer (previous)

Following the user's continuation, review-native-motion creates a local single-
pitcher viewer from saved motion exports, retaining all five Ohtani clips/1684frames.
It links playback/presented-frame cursor/angle readouts and supports stepping,
frame input, slider and curve-click seek. Source CSV values are embedded unchanged;
no angle recomputation, pose/detector, tracking replay, GT or event alignment.

requestVideoFrameCallback mediaTime identifies the presented source frame; requested
target is separate until confirmed. Fallback uses explicitly marked currentTime
estimates. Loading/error disable controls; rate affects only playback. Missing
angles remain gaps. Models, raw coordinates, gates and unknown/null semantics stay.

New source/CSV checks cover exact hashes, complete frames/fractional time, state/
count consistency and single-pitcher identity. Six new Python tests and five pure
Node numeric tests passed. Full Python suite1184run/1182passed/0failed/0errors/
2Windows-file-symlinkskips,130.406s,including formal five-video MediaPipe E2E.
379protected existing inputs/outputs/core/test SHA unchanged. Existing files only
extend CLI dispatch and package-data to include the JS asset.

CUA rejected file:// observation and prohibited workarounds, so automated browser
verification remains unperformed. The original builder's browser_interaction_verified=false
and delivery's UI_REVIEW_PENDING remain historical execution snapshots.
After local opening instructions, HSU replied「都正確尤其是5最完美」,
accepting the five-clip viewer qualitatively and highlighting supplement005 as the
preferred demonstration. Exact response/reviewer/time/source SHA are saved in
annotations/motion_reviews/HSU_20261024/ohtani_motion_sync_acceptance.json.
**Current human viewer review: ACCEPTED5/5.** No instrumented per-control test log,
new pointwise GT, calibrated accuracy or algorithm change is inferred.
This review/document-only update reruns no models/tests; latest same-code full
suite remains1182passed/0failed/2skipped, plus5pureNode tests passed.

Output:`analysis_results/phase3_motion_sync_20261024_01/viewer/review_motion.html`.
[Usage](native_motion_viewer.md),[delivery/tests](phase3_motion_sync_20261024.md),
[versioned evidence](dataset_selections/phase3_motion_sync_20261024.json).
[Latest human acceptance](dataset_selections/phase3_motion_sync_acceptance_20261024.json).
Phase2 automatic acceptance remains NOT PASSED; overall Phase3 NOT EVALUATED.
Stop after this delivery/commit/push; no next feature automatically started.

## 2026-10-24 user-authorized Phase3 first delivery: native 2D motion curves (previous)

After explicitly confirming retention of the accepted Ohtani/Yamamoto skeleton
workflow, HSU authorized the previously proposed minimal next step with
「可以繼續下步驟」. Work started on codex/phase3-native-motion from48ac5bc.
The former no-Phase3 stop was superseded for this bounded delivery; Phase2's
automatic reliability NOT PASSED result is retained, not retroactively changed.

New describe-native-motion reads accepted native analysis bundles and computes
original-pixel shoulder/elbow/wrist and opposite hip/knee/ankle projected angles.
Metadata determines handedness. It retains all zero-based frames and rational
FPS timestamps, with explicit missing/degenerate/null usable fields; no score
gate, smoothing, interpolation, event alignment or 17-to-33 conversion.

All five Ohtani sources ran through the actual CLI:335/321/369/338/321frames,
1684total,3368calculated model-XY angles. Each has CSV, PNG and source-bound
summary, plus a small cohort viewer reusing unchanged overlays. Model/detector/
tracking replay/newGT0;363protected prior source/core/test files SHA unchanged
after the suite. Existing production changes are only additive CLI dispatch.

Viewed all five plots: axes/labels/limits readable, local elbow fluctuations
retained. These are uncalibrated image projections, not measured human3D angles
or automatically reliable features. Pointwise unknown/usable null remain.
No full profile, cross-pitcher comparison, event prediction or clinical claim.

Full suite1178run/1176passed/0failed/0errors/2Windows-file-symlinkskips,
99.172s;13new tests. FormalfiveMediaPipe E2E ran with prior major hints retained.
**Phase3 first descriptive delivery COMPLETE; overall Phase3 NOT EVALUATED.**
Stop after this delivery/commit/push. No further feature automatically started.

Output:`analysis_results/phase3_ohtani_native_motion_20261024_01/review_motion.html`.
[Scope](phase3_native_motion_scope_20261024.md),[usage](native_motion.md),
[results](phase3_ohtani_native_motion_20261024.md),
[versioned evidence](dataset_selections/phase3_ohtani_native_motion_20261024.json).

## 2026-10-24 active Yamamoto review recorded; nine-clip assisted delivery complete

HSU subsequently reaffirmed that the current Ohtani and Yamamoto skeleton mode
must be retained. The shared operator-seeded person-box tracking plus native17
RTMPose workflow remains the standard, with fixed runtime/model/source SHA.
Existing accepted skeletons are consumed directly for later analysis; this
retention confirmation does not authorize Phase3 or a backend change.

HSU replied「都正確」to the explicit request for active Yamamoto001/002/004/005.
The independent skeleton-overlay-review-v1 record binds exact video/overlay/native
SHA, reviewer, recorded UTC and the original response.003remains historical only.
Original rollout pending fields remain execution snapshots; current acceptance is
recorded separately in annotations/skeleton_reviews/HSU_20261024/.

Four Yamamoto clips477frames/8109landmark slots ran through the existing actual
prepare-analysis-input and report-native-reliability CLI, then the loader/raw/track
comparison. Raw frame/track/derived point mismatches0, geometric track breaks0.
The previously accepted Ohtani five reports remain byte-identical and were not rerun.
Together the active nine clips2161frames/36737slots have complete whole-clip human
acceptance, native data integration and descriptive reporting. Ohtani remains candidate;
Yamamoto003is not restored and no formal source is replaced.

323protected prior sources/reviews/production/test files SHA unchanged. Production
and test code changes0; new inference/tracking replay/interpolation/pointwiseGT0.
No full suite rerun for this data/config/document-only delivery. Latest complete
suite on identical code remains1163passed/0failed/0errors/2Windows-symlinkskips,
including formalfiveMediaPipe E2E. Actual four-clip integration completed this round.

**Assisted skeleton delivery COMPLETE; native data integration PASSED.**
**Original automatic reliability acceptance / Phase2 remains NOT PASSED.**
Pointwise reliability/visibility remain unknown, usable_for_analysis=null. No new
acceptance line or annotation requirement. Whole-clip review of the active cohort
is fully complete; stop after this delivery/commit/push, with no Phase3/new experiment.

Output:`analysis_results/phase2_active_cohort_closeout_20261024_01/`.
[Scope, acceptance and remaining limitation](phase2_active_cohort_closeout_20261024.md),
[versioned evidence](dataset_selections/phase2_active_cohort_closeout_20261024.json).

## 2026-10-24 native joint and tracking continuity reports completed (previous)

The user requested continuation. The saved accepted native analysis inputs now
support `report-native-reliability`: descriptive joint coverage/missing spans,
adjacent displacement and image-order changes, paired with saved track IoU/status,
bbox geometry, raw hip-center and torso-scale continuity. Each clip has a readable
report.md plus pose/tracking JSON and the complete frame_diagnostics.jsonl.

All five Ohtani clips ran through the actual CLI:335/321/369/338/321frames,
1684total and28628landmark slots. Original XY/state/score/missing-reason mismatches0;
geometric track breaks0.158protected source/review/formal-material SHA unchanged
after the full suite. New inference/tracking replay/interpolation/GT0.
Adjacent pair denominators exclude frame0; missing/equal samples are not bridged.
Large motion, candidate-index changes and image-order flips are not error labels.

Full suite1165run/1163passed/0failed/0errors/2Windows-file-symlinkskips,
104.141s;10new necessary tests. FormalfiveMediaPipe E2E ran with major
hints2/0/19/5/3. Only CLI dispatch was extended in existing production code;
model/pose/tracking/selector/gates/thresholds/raw/humanGT remain unchanged.

Whole-clip human acceptance remains5/5. Pointwise reliability and visibility remain
unknown, usable_for_analysis=null. Descriptive native reporting COMPLETE;
Phase2 automatic reliability remains NOT PASSED. No new classifier, calibration,
pass line or Phase3 work. Stop after this bounded delivery/commit/push.

Output:`analysis_results/phase2_native_reliability_20261024_01/`.
[Usage/formulas](native_reliability.md),[actual results](native_reliability_results_20261024.md),
[versioned evidence](dataset_selections/native_reliability_20261024.json).

## 2026-10-23 native skeleton analysis-input delivery completed (previous)

The authorized bounded integration is complete: `prepare-analysis-input` binds saved
native COCO17, same-source metadata/track and exact human overlay acceptance.
`load_native_analysis_input` lets downstream Python consume immutable raw frame
snapshots, paired tracks, clip review and explicit unknown pointwise assessments.
Output is only native_analysis_input.json plus usage_summary.json; source raw remains
referenced. No estimator, worker, tracking replay, coordinate conversion or old gate.

All five accepted Ohtani sources ran through the real CLI and downstream loader:
335/321/369/338/321frames=1684;28628native landmark slots retained. Raw frame and
tracking mismatches0; new inference/replay/GT0.002uses its already accepted saved
dataset and prior track/review directly. Whole-clip human acceptance remains5/5;
pointwise reliability/visibility unknown and usable_for_analysis=null are preserved.

Full suite1155run/1153passed/0failed/0errors/2Windows-file-symlinkskips,
98.953s;14new necessary tests. FormalfiveMediaPipe E2E ran with major
hints2/0/19/5/3. An initial sandbox run skipped8extra junction tests; the final
normal-permission verified_suite completed existing coverage. Both logs are retained.
2068protected source hashes unchanged. Only existing CLI dispatch was extended;
production pose/tracking/selector/thresholds/gates/smoothing/raw/GT remain unchanged.

**Native analysis input integration = PASSED. Bounded delivery = COMPLETE WITH KNOWN LIMITATIONS.**
**Phase2 = NOT PASSED; automatic pointwise reliability is not established.**
Clip acceptance/data access does not calibrate native scores or transfer old-model
canonical labels to RTMPose. No new pass line, annotation, classifier adjustment,
Phase3 metric/event or further experiment has started. Stop after this commit/push.

Output:`analysis_results/phase2_native_analysis_input_20261023_01/`;bundles/contains
the five data envelopes. [Usage](native_analysis_input.md),
[delivery and acceptance decision](native_analysis_input_results_20261023.md),
[versioned results](dataset_selections/native_analysis_input_20261023.json).

## 2026-10-23 Ohtani shared skeleton cohort completed (previous)

Following HSU's authorization to retain this method, the remaining Ohtani supplement
clips001/003/004/005 were processed once with the existing common entry. HSU confirmed
frame0 display choices1/1/1/2; four source-bound seed records are saved in
`config/subject_seeds/ohtani_20261023/`. The005highest-score box is the catcher;
the confirmed2nd box selects the pitcher. Candidate status is retained.

Frame counts335/369/338/321 total1363. First-frame detections4 were reused,
remaining detector calls1359, pose1363. All four outputs include complete native17
datasets and overlays; whole-frame missing0, geometric track breaks0. Accepted002
retains its original321frame result with0new calls, giving1684cohort frames.
Inference finished while the conversation was interrupted; continuation only
exported and inspected existing results, without repeated inference or tuning.

Viewed12comparison sheets/35source-prior-new frame triples. The prior005/128mixed
skeleton reaching the batter and003/158arm extension toward background are reduced;
sampled skeletons remain near the pitcher. HSU subsequently replied「可以都正確」
to the review request, accepting the four new overlays at whole-clip visual level.
Together with the previously accepted002, Ohtani overlay human acceptance is now
5/5clips,1684frames. The exact response, reviewer, recorded UTC and source/output
SHA are saved in
`annotations/skeleton_reviews/HSU_20261023/ohtani_shared_skeleton_acceptance.json`.
Execution rollout JSON keeps its original pending snapshot; this independent human
review record provides the later acceptance. No new per-point GT or event labels.

2052protected source SHA unchanged;2722new journal/binary payloads verified. Complete
source pixels and rational timestamps were checked against saved frame records;
all source/old/new overlays decode to their full counts. Production code, model,
tracking policy, thresholds, gates, original predictions and human GT are unchanged.
No full suite rerun for this configuration/data-only rollout; the latest complete
suite on the same production code remains1139passed/0failed/2Windows-symlinkskips.

Output:`analysis_results/phase2_ohtani_seeded_skeleton_20261023_01/`;open`review_all.html`.
[Report](ohtani_shared_skeleton_rollout_20261023.md),
[versioned results](dataset_selections/ohtani_shared_skeleton_rollout_20261023.json).
The Ohtani whole-video visual review is complete. Phase2 automatic reliability remains NOT PASSED;
no formal source promotion, GT changes, new model or Phase3 has started.

## 2026-10-23 shared skeleton standard adopted and applied to Yamamoto (previous)

After delivery HSU explicitly reaffirmed this as the most successful method so far
and authorized its continued use for future pitchers. New skeleton work therefore
continues through the shared operator-seeded RTMPose workflow, with each source's
initial pitcher confirmed separately. The exact statement and source-bound method
record are saved in
`annotations/skeleton_reviews/HSU_20261023/future_pitcher_method_endorsement.json`.
This method-level confirmation adds no individual video or keypoint GT labels.

HSU watched the complete Ohtani supplement_002321frame seeded overlay, accepted its
subject identity and overall joint alignment, and explicitly requested the same method
for Yamamoto and future pitchers. The exact user statement, reviewer, recorded UTC,
and source/output SHA are saved independently. This is a qualitative whole-video
acceptance and method adoption, not invented per-point human coordinates or a 100% score.

The common skeleton CLI is now `prepare-skeleton` followed by an operator-confirmed
source-bound seed and `extract-skeleton`. It uses each complete input image as its
own canvas, reuses the first-frame detector output, saves all remaining candidates,
applies the existing fixed mutual-unique positive-IoU/terminal-break policy, then
estimates native COCO17 in the selected person's bbox. No Ohtani-specific crop,
cache rule, pitcher name condition or model-specific call count is copied to new inputs.
Long inputs split detector worker evidence into bounded sessions without extra calls.

HSU confirmed first-frame display choices 001=2, 002/003/004/005=1. All five Yamamoto
sources ran once: 87/175/115/114/101frames, total592; detector5cached-firstframe plus
587remaining, pose592; whole-frame missing0, geometric breaks0.
003 remains historical_diagnostic_only; active cohort remains001/002/004/005.
Complete overlays and sampled source/old/new comparisons are delivered. The Yamamoto
outputs have agent sample inspection; full-video human acceptance is still pending.

Existing independent pitch003visible manual XY is reused on1205visible points;
173not_observable and2uncertain are excluded, missing points reported separately.
Same-point mean pixel error old→new: 22.2113→10.1057; historical87–104:
76.9003→10.5003. Per-joint and same-point counts remain explicit.
Canonical reliability labels describe the old MediaPipe overlay and are not transferred
to RTMPose TP/FN/FP. No new human labels, hidden-joint claims or acceptance threshold.

Full suite1141run/1139passed/0failed/0errors/2Windows-file-symlinkskips,98.391s.
All five formal MediaPipe E2E cases ran; major hints remain2/0/19/5/3.727protected
sources are SHA-unchanged. Only existing CLI dispatch/help was extended; production
pose/tracking/gates/thresholds/raw/GT and Phase1 material remain unchanged.

**Shared skeleton method = ADOPTED BY HSU. Phase2 automatic reliability = NOT PASSED.**
Native17 score is uncalibrated; unavailable Z/visibility/presence stay null. Legacy
`analyze-pitch`/`extract-pose`33point feature/gate compatibility stays available;
all new skeleton production uses the shared entry. Native-feature integration and
new-model automatic reliability are not silently claimed by this rollout.

Output:`analysis_results/phase2_yamamoto_seeded_skeleton_20261023_01/`;open`review_all.html`.
[Rollout results](standard_skeleton_rollout_20261023.md),
[common workflow](standard_skeleton_workflow.md),
[versioned results](dataset_selections/standard_skeleton_rollout_20261023.json).
Stop after this delivery/commit/push; no Phase3 or new experiment has started.

## 2026-10-23 explicit continuation completed:321/321native coordinate frames (history)

The user requested continuation after the prior stopped report. Implemented a
separate resume entry that verifies old claims, complete213pairedcalls/binary,
215savedpredictions and source/pixel/time/affine evidence before doing any newpose.
Only215–320ran106times;0–214records are copied unchanged, including193/194cache.
Total newpose across both seeded segments is319, plus2originalcacheframes=321.
No newdetector, trackingreplay, model, environment install or warmup/retry occurred.

Newprogress writes immutable numbered files instead of replacing one snapshot;
108events completed, including106frames. No interruption this time. Originalclaim,
stale receipt/tmp, partial, journals/binary and earlier overlays remain unchanged.
The old Windows lock root cause is still unconfirmed; the new path avoids its
repeated replace operation. This explicit continuation does not reset the old run.

Full321frame COCO17dataset andH264overlay delivered, source pixels/time verified;
whole-frame missing106→0. Viewed25source/prior/new comparisons including214/215/216:
sampled skeletons remain near pitcher across the seam and newly completed tail;
earlier improvement over batter-contaminated static-crop arms remains visible.
These are agent samples, not per-frame humanGT; local/occluded-joint accuracy is
unmeasured. not_calibrated/accuracy=null/usable_for_analysis=null remain unchanged.

Fullsuite1128run/1126passed/0failed/0errors/2Windows-symlinkskips,82.719s;11newtests.
FormalYamamotofiveE2E enabled;majorhintsunchanged2/0/19/5/3.672protectedfiles SHA
unchanged;215prefixrecords unchanged;106newbinarypayloads verified;sourcepairing
errors0. Existingproductioncore/gates/thresholds/raw/GT remain unchanged.

Output:`analysis_results/phase2_seeded_resume_native_20261023_01/`;open`review_all.html`.
[Continuation results](phase2_seeded_resume_results_20261023.md),
[execution scope](phase2_seeded_resume_20261023.md),
[versioned evidence](dataset_selections/ohtani_seeded_resume_results_20261023.json).
**Bounded continuation COMPLETE; NOT FORMALLY ADOPTED; Phase2 still NOT PASSED.**
Stop after commit/push;no otherclips,newannotations,acceptancechanges orPhase3.

## 2026-10-21 approved operator-seeded track: partial predictions preserved (history)

HSU approved the [frozen plan](phase2_seeded_native_track_plan_20261021.md) and chose
display1/output_index0 at frame0. Added separate native association/cache/producer
modules and CLI. Exactly one saved-box replay linked321/321frames (1seeded/320linked),
no geometric track break,0newdetector. Newpose213attempted/completed;193/194 reused
only after exact source/model/frame/pixel/bbox/full-affine-and-SDK geometry match.

After saving frame214, Windows denied replacement of run_receipt.json.tmp to
run_receipt.json (WinError5); the error handler then encountered the existing tmp
file. Root cause is not confirmed. The process stopped after215savedposeframes;
215–320(106frames)were never inferred. No inference/replay retries or claim reset.
Original running/stale receipt,tmp,partial,binary/journals/claim remain unchanged;
interrupted_run_receipt.json records the independently verified actual counts.

Read-only postprocessing exported a full321frame native dataset/H264overlay with
106explicitnot_run/missingframes; these indicate execution interruption, not pose
loss, occlusion, or track break. No extra inference was used for rendering/review.
Viewed22source/prior/new comparisons on6sheets: early static-crop arm contamination
near the batter is reduced in sampled new frames; uncalibrated coordinate presence
does not establish local accuracy or full-video identity. No new humanGT.

Fullsuite1117run/1115passed/0failed/0errors/2Windows-symlinkskips,81.922s;24new
synthetictests. FormalYamamotofiveE2E enabled;majorhintsunchanged2/0/19/5/3.
615protectedfiles and8interruptedrawartifacts unchanged;213binarypayloads verified,
source pairing/frozen implementation SHA errors0. Productioncore/gates/raw/GT unchanged.

Output:`analysis_results/phase2_seeded_track_native_20261021_01/`;open`review_all.html`.
[Result and known I/O issue](phase2_seeded_native_track_results_20261021.md),
[versioned evidence](dataset_selections/ohtani_seeded_track_results_20261021.json).
**Full inference incomplete; NOT ADOPTED; Phase2 automatic reliability still NOT PASSED.**
Per approved failure-stop rule, stop here: no remaining106frame rerun, policy tuning,
otherclips, formalpromotion orPhase3. Approval document retains its pre-execution
snapshot because its SHA was bound before the once-only run; current outcome is here.

## 2026-10-21 approved single-clip person-box run completed (previous)

HSU approved the [bounded plan](phase2_person_box_native_plan_20261021.md).
Implemented one optional YOLOX-m detector, source-bound person-box selection and
native per-frame bbox affine; full missing/not_run preserves no-inference semantics.
Existing fixed-crop calls and cached datasets remain compatible. Production
MediaPipe/PitcherSelector/gates/core/raw/GT are unchanged.

Only supplement_002321frames ran once:321detector/2pose completed,0failures/retries/
warmups. Onlyframes193/194 have unique candidates;319frames have exactly2eligible
boxes and are missing. Prior native coordinate availability321→2frames(0.6231%);
newmissing99.3769%, spans0–192(193frames)and195–320(126frames). This is lost
availability, not successful recovery. The policy is NOT ADOPTED.

Viewed22 source/prior/new triples in6contact sheets, includingbothrealposeframes.
The sampled boxes separate pitcher and batter, but both centers meet the original
operatorROI condition. Two new skeletons are near pitcher silhouette; localaccuracy
remains unmeasured. Agent inspection is not new human GT;quality staysnot_calibrated,
usable_for_analysis=null. Complete321frameH264overlay verifies originalfractional
timeline withmaxdifference9.095e-13ms.

Fullsuite1093run/1091passed/0failed/0errors/2skipped,83.812s;36new no-modeltests.
FormalYamamotofiveE2Eenabled,majorhintsunchanged2/0/19/5/3.541protectedfiles SHA
unchanged;all323binarypayloads verified. Five approved native geometry/contract
files have recordedbeforeSHA;no formalcore/gatechanges,0newannotations/promotions.

Output:`analysis_results/phase2_person_box_native_20261021_01/`;open`review_all.html`.
[Report/stop decision](phase2_person_box_native_results_20261021.md),
[usage](phase2_person_box_native_usage.md),
[versioned evidence](dataset_selections/ohtani_person_box_results_20261021.json).
The approved implementation/run is complete;Phase2remainsNOT_PASSED. Perplan stop
here:no ROI/score adjustment,new small rule,otherclips,model replacement orPhase3.

## 2026-10-21 approved live native implementation delivered (previous)

HSU approved the fixed [live-native plan](phase2_live_native_pose_plan_20261020.md).
Implemented an independent new-MP4 RTMPose entry using the existing model and
isolated runtime, source-bound reviewed crop, native COCO17 and original-pixel XY.
Unsupported Z/visibility/presence remain null; no 33-point padding, confidence gate,
interpolation, calibration or formal backend replacement. Default MediaPipe is unchanged.

The one approved run completed on 2026-10-20 13:18:46–13:21:01 UTC: five clips
335/321/369/338/321 frames, 1684 attempted/1684 completed, 0 execution failures.
Worker journal has exactly 1684 started/completed pairs, no retries; all binary
payload hashes verified (102602752 bytes). Five H264 overlays decode all1684 frames
at1280x720/60000/1001FPS; maximum timeline difference9.095e-13ms.

Viewed90 regular overlay samples and9 targeted original/MediaPipe/RTMPose triples,
all13 contact sheets. Some prior missing/hybrid examples return near the pitcher,
but new RTMPose preparation frames onp02 mix pitcher lower body with batter-area
upper points, andp05f128 is still severely hybrid/misaligned. This is agent sample
inspection, not human GT. Complete coordinate availability is not reliable coverage;
accuracy remains null, quality_status=not_calibrated, usable_for_analysis=null.

Full suite1057run/1055passed/0failed/0errors/2skipped,64.453s;39new tests.
Two Windows file-symlink privilege skips remain; junction tests actually ran.
Formal Yamamoto five-video MediaPipe E2E enabled, major hints unchanged2/0/19/5/3.
475protected file SHA unchanged; no formal core/gate/raw/GT changes,0new annotations,
0formal promotions. Existing supplement MediaPipe results stay5degraded.

Output:`analysis_results/phase2_ohtani_live_native_20261020_01/`; open`review_all.html`.
[Delivery report](phase2_live_native_pose_results_20261021.md),
[usage](phase2_live_native_pose_usage.md),
[versioned evidence](dataset_selections/ohtani_live_native_results_20261021.json).
The approved implementation and one-pass delivery are complete. Engineering
integration PASSED does not make Phase2 automatic reliability PASSED. This round
stops here: no repeated inference, calibration, formal replacement or Phase3.

## 2026-10-20 bounded attribution and next implementation scope (previous)

Read saved1684-frame candidate traces and raw only;0new inference,0selector replay,
0human GT changes.All85unselected frames have0eligible candidates.Only14frames
have no model candidate(allp02);71have predictions rejected under original rules.
118rejected candidate records:first failure ROI65/projected body height50/confidence3.
All50protocol failures are ankle-minus-shoulder projected height<.16;not proof of
small people or correct rejected skeletons.No thresholds or geometry changed.

p02f159/f245 andp05f251 each have0other eligible candidate,so simple re-ranking
cannot directly replace the observed hybrid skeletons.Knee raw gating is dominated
by initial lowvisibility spans81/107/82frames inp02/p03/p05,respectively.This is
model score evidence,not human occlusion truth;do not trim preparation to pass.

Output:`analysis_results/phase2_ohtani_supplement_diagnosis_20261020_01/`;
10read artifacts SHA unchanged.No product/test changes or suite rerun.
[attribution](phase2_ohtani_supplement_diagnosis_20261020.md),
[live native backend proposal](phase2_live_native_pose_plan_20261020.md).
At that checkpoint the approved RTMPose interface was cached-only.Live scope was
then awaiting confirmation:existing weight/runtime,1684new frames once,native17 outputs
and5overlays,unchanged production MediaPipe/core/gates.No Phase2 pass from interface
completion.That checkpoint started no implementation or Phase3; the subsequently
approved implementation is completed in the latest section above.

## 2026-10-20 Ohtani supplement analysis completed (previous)

HSU explicitly confirmed both new-source orange torso regions and cyan model-input
crop for all five clips, then authorized analysis. Five new trial inputs
supplement_001..005 were prepared independently; MP4 SHA preserved and pitch-input-v1
validated. Season2026 retained; unknown fields remain null, batch is not session,
and supplier motion anchors are not biomechanical events.

Fixed original-image ROI[.22,.40,.46,.88], crop[.15,.30,.60,1.0],
pixel slice[192,216,768,720),576x504 without resize. New source samples inspected
before inference; original video and all native/mapped candidates retained.
Each clip analyzed once,0execution failures;no product/core/model/gate changes.

Selected324/335,275/321,362/369,323/338,315/321;total1599/1684(94.95%).
Longest gaps9/13/5/12/2;elbow-angle raw coverage59.10/59.19/75.34/57.40/63.86%.
All exceed existing50% elbow-angle coverage, but all five quality gates still fail:
p01/p04 gaps>2;p02 pose<90%,gap>2,lead-knee-angle<80%;p03 gap>2 and knee<80%;
p05 knee<80%.Statuses remain5degraded/5quality_gate_failed;no threshold relaxed.

Viewed90 evenly spaced overlay samples plus6 targeted source/overlay pairs
(4additional unique frames).p02f159/245 wrong-person/hybrid upper-body placement;
p05f251 mixed catcher-area upper body with pitcher-area lower body,f252 returns.
All tracking partially_reliable;existing identity-switch warnings onp02/p05 retained,
confirmed staysnull.No new human per-frame GT or identity confirmation added.
Yamamoto-source major hints staynot_evaluated on all five new inputs.

305protected SHA unchanged;1684trace rows,2719native candidates,52767selected raw
points consistent with saved capture counts/transform.Five H264 playback copies
decode all1684frames at original1280x720 and60000/1001FPS.Candidates remain candidate,
no formal promotion/replacement.No Phase3.

Output:`analysis_results/phase2_ohtani_supplement_20261020_01/`,start`review_all.html`;
[report](phase2_ohtani_supplement_results_20261020.md),
[versioned results](dataset_selections/ohtani_supplement_analysis_20261020.json),
[confirmed config](../config/pilots/ohtani_supplement_regions_20261020.json).
No product/test changes,full suite not rerun;latest same-code record remains
1018run/1016passed/0failed/2skipped(e236878).Phase2automatic reliability remains
NOT PASSED.This fixed-input trial is closed;do not search crop sizes or repeat
inference to find a pass.Next repair should address hybrid skeletons and missed
joints under the existing scope/proposal requirements;no new model started here.

## 2026-10-20 Ohtani supplement intake completed (previous)

User delivered and requested only indexed batch20261020T073530Z_6gyr6IC2e0Q.
Imported5candidate clips,0rejected/0conflicts,exit0;repeat adds0/skips5,exit0.
Ledger before2batches/13pitches/57events;after3/18/63;repeat3/18/69.
Audit events grow without duplicate candidate rows.

All5CFR60000/1001,1280x720,H264/yuv420p;decoded335/321/369/338/321
frames,total1684.Declared counts equal decoded counts;max normalized PTS
deviation0.000666667ms each,fractional FPS validation strictly<1ms.
Native container offset retained as evidence,no frame0 shift;anchors not events.

At import fivecandidate/pending,0/5reviews.After viewing in-chat supplementp01
and its7-item checklist,HSU explicitly replied“七項正確”,then replied“正確”
to supplementp02,p03,p04andp05and their same7items.Recorded35pass findings,p01-p05
review_complete,5/5completed.Same-schema exact snapshots at
annotations/input_reviews/shohei_ohtani/20261020T073530Z_6gyr6IC2e0Q/p01.json throughp05.json.
Each finding transcribes that clip's human reply;none inferred from supplier description.
Input review is not frame-level joint GT.No analyze-pitch,
pose,overlay,formal input conversion,promotion or replacement performed.
14handoff files SHA/size/mtime unchanged;33prior review/input files SHA unchanged.
New sourceID6gyr6IC2e0Q distinct from oldRObvkuHpkSo,newMP4SHA not among prior candidates.
Operator exclusions preserved:6complete higher-overlap plus3incomplete/nonpitch;
no excluded video imported.Season2026 fromJSON;game date/opponent from user kept
as separate context,not injected into unknown delivery fields.

Output:`analysis_results/phase2_ohtani_supplement_intake_20261020_01/`;
[intake receipt](phase2_ohtani_supplement_intake_20261020.md),
[versioned IDs](dataset_selections/ohtani_supplement_20261020.json).
Next:set source-bound pitcher regions for this batch,then analyze each input once
with the existing model and gates.Analysis has not started in this review update.
No product/test code changes,full suite not rerun;Phase2automatic reliability
remainsNOT PASSED.No supplier code read,no Phase3.

## 2026-10-20 remaining-limit recovery bounded attempt closed (previous)

User requested continued repair. Checked003/004 data paths:249/239missing
elbow-angle frames,242/228 involve right-wrist low visibility(97.19/95.40%).
Presence,RIGHT side,timeline,raw/native mapping,clean masks and feature flags
are consistent;832trace frames/27093selected points checked,no product bug found.
Initial wrist low-score spans0-150/0-145 account for about61%angle missing;
do not infer per-frame human occlusion labels or trim preparation to improve ratios.

Independently re-detected only004's8and005's15existing missing frames inIMAGE
mode with sameFull weight,exact crop,num_poses4 and0.5settings:23calls once.
Native/mapped candidates stored separately;original selector replay without
threshold/score changes yields405vs402 and340vs338 selected,but longest gaps
remain3/13.Previously selected decisions unchanged0.Not a formal pipeline rerun.
Viewed5recovered samples plus005f200/205/208;local accuracy not human-certified.

Decision:do not integrate this fallback;it does not fix the gating failure.
005also has posture-dependent projected-scale rejection and truly absent model
candidates;changing scale alone cannot recover the whole gap.No ROI-size search,
threshold relaxation,GT/raw rewrite or live backend change.AutomaticPhase2
remainsNOT PASSED;formal crop results stay361/322/419/402/338selected.

Output:`analysis_results/phase2_ohtani_recovery_20261020_01/`;
[result and boundaries](phase2_ohtani_remaining_limits_20261020.md),
[replacement input needs](phase2_ohtani_replacement_input_needs_20261020.md).
No product/test code changed,full suite not rerun;latest same-code record
1016passed/0failed/2skipped(1018run,e236878).

User explicitly selected “先補較清楚的大谷素材（建議）”. Next input target is
at least3different complete Ohtani pitches under contract v2 and the clarified
replacement input requirements. That index check contained only the old five
clips;the newly delivered batch and completed intake are recorded in the latest section.
When a new indexed batch is available:import as candidates,complete local human
input review,then run each accepted input once.Keep001/002 and historical results;
no automatic replacement or Phase2 pass.Optional live backend planning/adoption
is not the selected route.No supplier code read or acquisition work started here.

## 2026-10-20 four-clip crop continuation delivered (previous)

User accepted applying the completed crop approach to remaining Ohtani clips.
Ran001-004 once each on2026-10-19;005 is read-only reuse,not new inference.
Same source-inspected [64,216,640,720) crop and previous operator torso ROI;
no product/test code,model,gate,threshold,raw history or GT changes.

Selected332/170/397/334 ->361/322/419/402 of362/326/422/410;
with reused005=338/353,cohort1842/1873,missing425->31.
Longest gaps1/1/1/3/13;elbow-angle raw coverage59.12/62.58/41.00/41.71/59.49%.
001/002 pass original pose gate,quality success,but analysis needs_event_review.
003/004 elbow coverage fails;004 also gap>2;005 retains196-208 missing.
001 automatic input quality still degraded(followthrough_unverified),002 accepted;
historical HSU source input review is preserved separately.No formal promotion.

Root inspected57fixed same-frame before/after pairs(114images).Main skeleton on
pitcher in samples,missing and known mixed-arm examples improved.Local shoulder/
elbow/wrist positions remain uncertified;this is not exhaustive human GT.
New four tracking reports partially_reliable;no warning is not confirmed identity.

504protected files unchanged;1520traceframes/1634candidates/53922points,
49632selected raw points preserved;6016torso checks,XYZ inverse error0.
New overlays362/326/422/410decode;8H264copies preserve original overlay fps;
005view copies reused.Product/test code unchanged:full suite not rerun this round.
Latest same-code full result remains1016passed/0failed/2skipped(1018run,82.720s)
frome236878,including formal five E2E;do not label that historical run a new run.

Output:`analysis_results/phase2_ohtani_crop_cohort_20261019_01/`;
[full result](phase2_ohtani_crop_cohort_20261019.md).
Fixed continuation is complete.Stop crop-size searches and preserve unresolved
coverage/gaps.AutomaticPhase2 remainsNOT PASSED;no Phase3.

## 2026-10-19 single Ohtani pitch_005 input crop delivered (previous)

User accepted the proposed full-motion model-input crop with “好繼續”.
Added optional input_crop with exact floor/ceil pixel bounds, native crop candidates
and mapped original-image candidates/CSV; selector and overlay use original coordinates.
No crop keeps the old path. Fixed source-inspected bounds [64,216,640,720) retain
head/limbs/follow-through; these bounds are an agent-selected operator setting,
not a new human joint annotation. No ROI-size search or other Ohtani clip inference.

One real 353-frame run: selected215->338/353 (60.91->95.75%),missing138->15,
longest gap54->13,elbow-angle raw coverage36.83->59.49%. All coverage gates now
pass but original >2-frame pose-gap rule still fails: gap196-208 remains missing.
Result degraded, not success. Right elbow raw310/353; wrist210/353,129missing.
14 fixed same-frame three-version samples inspected: previous wrong-person/mixed
examples return to pitcher; frame204 missing. This is agent sample inspection,
not exhaustive human identity/keypoint GT or an accuracy score.

Original sources/old outputs/formal materials/annotations:160 SHA checks unchanged.
353 trace rows,345 native candidates/11385 points;11154 selected raw points equal
mapped candidates,inverse XY error0,confidence/Z mismatch0. Model/gate/threshold/
selector/smoothing/interpolation unchanged. Viewing copies retain353frames,1280x720,
59.94fps; original overlays preserved.

Full suite once:1018run/1016passed/0failed/0errors/2existing Windows file-symlink
skips,82.720s,exit0;17new tests. Formal five E2E hints remain2/0/19/5/3.
Output:`analysis_results/phase2_ohtani_p05_crop_20261019_01/`;
[results and use](phase2_ohtani_p05_crop_20261019.md).
Single-clip improvement supports a next bounded trial on the remaining four;
this delivery stops at one clip. AutomaticPhase2 remainsNOT PASSED;no Phase3.

## 2026-10-19 approved optional pitcher-region repair delivered (previous)

User explicitly approved the minimal selector/capture repair and then confirmed
the displayed five-video torso region. `config/pilots/ohtani_subject_region_20261019.json`
binds each videoSHA and HSU confirmation to normalized(0.10,0.33,0.43,0.92).
All four raw shoulder/hip points must lie inside; limbs may extend outside.
This is an operator constraint, not automatic named-player identification or new GT.
No eligible candidate means missing; the original full-image model input stays.

Added opt-in subject_roi/candidate capture with necessary workflow/analysis plumbing,
backward-compatible optional provenance fields and a thin source-bound pilot runner.
When no setting is supplied, old default behavior is retained; no model/gate/threshold/interpolation changes.
Old outputs and canonical/manual GT are preserved.

Ran the new Ohtani five once:5complete/0runtime failures,all5degraded.
Selected counts333/300/397/345/302 ->332/170/397/334/215,total1677->1448;
missing196->425.251old selected become missing,22old missing become selected.
These are selection-state counts, not new human error classifications.
Source/overlay samples show clip2f177/266/325 rejected; clip5f0 rejected and
f32/64/96/128/160 now select the pitcher. Mixed arms remain in2f238 and
5f192/224/352. Root inspected70same-frame sample pairs; no exhaustive new GT.
All1873native overlay frames decode;10H264view copies retain frame count/time rate.

Full suite once:1001run/999passed/0failed/0errors/2existing Windows file-symlink
skips,89.641s,exit0,32new tests. Formal five E2E major hints remain2/0/19/5/3.
Saved trace audit:1873frames,2801poses/92433points;47784selected raw points
exactly match original candidates;425unselected frames have no raw rows,
5792torso ROI checks pass;32read source/artifact hashes unchanged,0errors.

Output:`analysis_results/phase2_ohtani_subject_lock_20261019_01/`;
[results/use limits](phase2_pitcher_lock_results_20261019.md).
Optional constrained selection is delivered, not a full reliability acceptance.
Stop this bounded repair: no ROI-size search, new model, annotation or Phase3;
automaticPhase2 remainsNOT PASSED and no new formal reference was accepted.

## 2026-10-19 Ohtani pilot complete with degraded outputs (previous)

User requested removing the high-deviation Yamamoto pitch_003 from subsequent work,
then explicitly chose Shohei Ohtani, five pitches. The new active Yamamoto directory
`input/yoshinobu_yamamoto/phase2_active_20261019/` contains only pitch_001/002/004/005,
with matching source hashes and four valid input pairs. Original phase1_final videos,
pitch_003 raw predictions/manual XY/canonical GT and historical five-clip evaluation
and regression evidence are preserved. This prospective exclusion does not revise
the old evaluation denominator or establish automatic reliability acceptance.

Completed bounded work: selected only indexed handoff batch `20261010T110737Z_RObvkuHpkSo`,
imported its five candidates with existing hash/timing/dedup checks, recorded HSU's
explicit seven-item input review for all five (35 pass findings), then ran current
MediaPipe once per clip and inspected source/overlay contact sheets. Input review
does not supply skeleton correctness GT.
The new pilot scope supersedes older prospective “no new-candidate work” stop notes;
those notes remain historical. No Phase3, profile, cross-pitcher comparison or live
RTMPose adoption is authorized. Failed warning trials stay closed.

See [current work and stopping conditions](phase2_next_dataset_20261019.md) and
[prospective dataset selection](dataset_selections/phase2_pilot_20261019.json).
Earlier “next” paragraphs below describe their dated work; they are not a current queue.

Ohtani intake is complete: 5 imported, 0 rejected/conflicts; repeat adds0/skips5.
Only selected index line2 was processed, ledger1batch/8pitches ->2batches/13pitches.
All1,873frames match60000/1001FPS; max normalized PTS deviation0.000666667ms each.
At intake all five were candidate/pending; HSU subsequently completed all input reviews.
The local review history retains both stages; there are still no formal promotions.
Intake output:`analysis_results/phase2_ohtani_intake_20261019_01/`.
Reader/CLI add optional exact indexed batch selection; production Phase2 core unchanged.
Focused handoff suite75run/73passed/0failed/2existing file-symlink skips,6.412s,
including6new tests; junction cases actually ran. No full-suite rerun this turn;
the latest historical full-suite result remains961passed/0failed/2skipped.
Analysis output:`analysis_results/phase2_ohtani_pilot_20261019_01/`.
All five completed artifacts with0runtime failures;0success/5degraded/0failed by the
unchanged keypoint quality gate. Valid pose ratios91.99/92.02/94.08/84.15/85.55%;
elbow-angle raw coverage59.12/56.44/36.49/38.78/78.19%;longest pose gaps5/6/6/11/7frames.
All1,873overlay frames decode and match input counts. Root inspected14source/overlay
samples per clip (70total), not new human GT. Clip2samples include batter selection;
clip5often tracks umpire/batter and mixes people. Coverage cannot validate identity.
The source-bound major-review hints report not_evaluated for all new inputs;
tracking identity_switch_confirmed remains null. No events or coordinate GT invented.
Per-joint coverage/visibility/gaps/interpolation and tracking reports are preserved.
See [completed trial report](phase2_ohtani_pilot_results_20261019.md).
This pilot is delivered and stopped, with no formal reference adoption, production
code/gate changes or Phase3. Future repair should focus on these reproducible
wrong-subject/cross-person failures within an explicitly confirmed core-change scope.

## 2026-10-18 approved cached native interface delivery (previous)

User explicitly approved “核准第一版接入實作”. Completed the bounded native
17/33-point output interface on`codex/phase2-native-pose-interface`;
[results and usage](phase2_rtmpose_native_interface_results_20261018.md).
The approved proposal stays at its historical SHA; execution/result receipts
record approval and completion. No live pose estimator or production backend switch.

Both backends preserve592frames. MediaPipe19536declared slots include99missing;
RTMPose10064native slots retain original decoded coordinates/scores with unsupported
Z/visibility/presence null. Full-frame MediaPipe geometry and human-seeded CSRT ROI
for RTMPose remain distinct. Native quality is not_calibrated, usable=null, with no
legacy gate applied or source confidence fabricated. New inference/calibration/
tracking/annotations/downloads=0 for the integration; existing tests rerun MediaPipe E2E.

Five H264/yuv420p overlays fully decode with original dimensions/frame counts and
592source-pixel/timestamp checks. Root actually inspected six rendered frames per
clip for drawing/alignment; this is not new correctness GT. Existing MP overlays
are referenced only. The original99MPmissing slots and11RTMout-of-image points
remain explicit, without interpolation or clipping into apparently valid points.

Independent audit checks 19,536 MP and 10,064 RTM declared landmark slots,
592 native SimCC outputs, scores, inverse affine and original CSV pixel transforms;
maximum coordinate/score difference = 0. All 1,380 human rows for 003 reproduce
the prior diagnosis; hip regressions remain visible. Other four precise XY accuracy stays null.
646 unique prediction source SHA and 736 audit-read sources match; 467 protected
current sources and 62 upstream references are unchanged. Existing production modules,
gates,raw/GT/old trials and8pending/unanalysed candidates preserved.

45new tests; full963run/961passed/0failed/0errors/2Windows file-symlink skips,
76.699s,exit0,formal5E2E major hints still2/0/19/5/3.
Output:`analysis_results/phase2_native_interface_20261018_01/`.
Final compatibility acceptance is in`integration_acceptance.json`; the original
integration_summary is retained as the pre-audit export-stage snapshot.

Engineering integrationPASSED does not repair automatic wrong-point acceptance.
Phase2 automatic reliability remains NOT PASSED; native score is uncalibrated,
old response hints remain rejected, and003/104is not patched. This approved
delivery is complete; stop without live inference, model adoption, new gates,
annotations, handoff candidate analysis or Phase3.

## 2026-10-17 native backend interface plan (previous; approved and implemented later)

User confirmed “允許規劃後端介面改動”. Delivered the
[native output integration and acceptance plan](phase2_rtmpose_native_backend_plan_20261017.md).
This authorizes planning only; implementation awaits explicit confirmation.
The proposed first version uses the saved five-video MediaPipe33/RTMPose17
outputs, additive native contracts/readers, independent overlays and comparisons.
It is a cached-output integration, not live RTMPose or a replacement backend
inside analyze-pitch. Existing production core files need no changes for this
minimal version; legacy33/v/p/Z semantics and MediaPipe defaults remain intact.

The plan preserves native score and unsupported fields, differentiates missing
coordinates from unsupported landmarks and human visibility, and blocks native
outputs from borrowing the old gate. New inference/calibration/annotations are
out of scope. Canonical Full reliability is not new-model correctness GT.

Engineering compatibility and automatic Phase2 acceptance are separate.
Completing the proposed interface would not resolve the known missed warnings
or automatically pass Phase2; new native quality/adoption work requires a
separately confirmed scope. This turn changes documents only, with no new
tests/model runs. Latest existing suite remains916passed/0failed/2skipped.
No implementation or Phase3 work has started.

## 2026-10-17 saved native-coordinate and missed-warning diagnosis (previous)

After the user requested continuation, completed a bounded read-only diagnosis
of the existing cached RTMPose outputs; [report](phase2_rtmpose_coordinate_diagnosis_20261017.md).
No new RTMPose inference, calibration, thresholds, labels or adoption decision.
All115x12manual pairs retained:1205visible/173not_observable/2uncertain;
nonseed1195/171/2. Native17 same-name joint mapping, raw pixel transforms,
1380point errors and12joint statistics independently replayed with zero differences.

All12full-clip means improve, but left/right hip get farther on67/114 and72/114
paired frames. Outside the existing major hold, mean hip errors worsen:
left9.1535->13.3563px, right7.4754->11.7197px. This prevents a blanket claim of
coordinate improvement; no per-frame model mixing or oracle selection is added.
Other four clips still have no exact XY accuracy labels for RTMPose.

ElbowFN84=81measurable-not-above-saved-threshold+3original-raw-missing;
wristFN68=59measurable+6outside-bins+3original-raw-missing. Saved training-maximum
suppliers are identified without recalibration or deleting original reliable rows.
Original Full labels do not become new-model correctness labels.

Full suite918run/916passed/0failed/0errors/2Windows file-symlink skips,60.560s,exit0,
including formal5E2E major hints2/0/19/5/3. Diagnostic reads22bound sources without
changes; the previous467+62protected inventory remains unchanged. Production
core/gates/raw/GT and8pending/unanalysed candidates preserved.
Output:`analysis_results/phase2_rtmpose_coordinate_diagnosis_20261017_01/`.

The response signal remains rejected. Automatic Phase2 remains NOT PASSED.
Native17 cannot be inserted into the current33-landmark/visibility/presence/Z
contract by padding or fabricated confidence. A future backend integration
requires a separately confirmed scope; none is implemented here. No Phase3.

## 2026-10-17 approved single RTMPose native-response benchmark (previous)

User explicitly approved the full one-time offline trial. Completed isolated
ONNX CPU compatibility, 592 real frame calls, five whole-video folds and the
predeclared decision; [results](phase2_rtmpose_response_results_20261017.md).
The original proposal remains at its historical SHA. Execution02 preserves01
and records a pre-inference metadata-validator repair: a shared symbolic joint
dimension was incorrectly rejected. Zero inference calls occurred before repair;
the sole synthetic call subsequently returned exact float32[1,17,384/512].
Model, preprocessing, signal, calibration and decision limits never changed.

ElbowTP/FN/FP/TN=0/84/4/440; wrist=3/68/1/379. Both are rejected under the frozen
rules. Gate-passed wrong points caught=0/3, below reference7/8; supported good
points additionally hinted=4/1. Hypothetical support without this hint473/477
and345/350 still includes72/46human wrong points. Unknown/missing rows stay
explicit and in the applicable denominators; wrist004/83 is an unknown warning,
not a TP or FP. No formal data/use decision was changed.

003 held out: elbow0/36/0, wrist0/12/0;104 remains unhinted. Paired visible XY
improves mean elbow27.7461->7.3101px(n92), wrist26.6556->16.8405px(n58), but wrist
maximum error worsens108.0667->127.9342px. This auxiliary one-video accuracy result
does not validate an automatic error screener, the other four videos or model
replacement. Original canonical/manual-XY visibility differences are recorded
[separately](phase2_visibility_gap_audit_20261016.md), without relabeling or exclusions.

Full suite918run/916passed/0failed/0errors/2Windows file-symlink skips,54.701s,exit0,
including formal5E2E major hints2/0/19/5/3.34new synthetic tests.467current protected
source and62upstream hashes unchanged. Original core,raw,GT,Full/MoveNet/Heavy,
classifier,formal5 and8pending/unanalysed handoff candidates remain preserved.
Output:`analysis_results/phase2_rtmpose_response_20261016_01/`.

No adoption is proposed. This approved trial is complete and sealed; stop this
signal without another cutoff, feature or model-size search. Phase2 evaluation
is COMPLETE WITH KNOWN LIMITATIONS; automatic reliability remains NOT PASSED.
The passing objective remains unmet. No new annotations or Phase3 work.

## 2026-10-16 single Heavy information benchmark (previous)

User requested “繼續修正直到phase2通過” after the bounded proposal. Completed
the proposed single offline Heavy float16/version1 trial under its fixed
scope and stopping rules; [results](phase2_heavy_information_results_20261016.md).
592 new pose calls, complete native candidates and durable journals; zero new
tracker inference, classifier FIT or human annotations. Original VIDEO options,
selector and all production algorithms/gates/predictions are unchanged.

Four-training-video reliable maximum distance calibration, strict greater-than,
sealed whole-video OOF application and evaluation are complete. ElbowTP/FN/FP
=2/82/1; wrist=2/69/1. Both fail the agreed17/27TP, non003 and cross-clip improvement
criteria. Original-gate-passed wrong points caught=1/2, worse than sample-maximum7/8;
each joint adds one gate-supported good-point hint. Remaining support475/477 and
347/350, still including71/47human wrong points. These are burden estimates only.
003/104 remains unhinted; no known answer was patched into predictions.

003 paired visible XY has limited improvements and elbow tail-error regression;
other four precise accuracy stays null. Canonical labels evaluate original Full,
not Heavy correctness. This trial rejects the new distance signal, not every
possible model or image source. The previous13-feature classifier remains closed.

Full suite884run/882passed/0failed/0errors/2Windows file-symlink skips,133.986s,exit0;
formal5E2E existing major hints still match2/0/19/5/3.436current protected sources
and62upstream hashes remain; raw/GT/manualXY,originalFull/MoveNet/core/gates and
eight pending/unanalysed candidates preserved. Output:
`analysis_results/phase2_heavy_information_20261016_01/`.

Both joints rejected: no adoption proposal, no integration or threshold adjustment.
This approved single trial is complete; stop at its predeclared decision. Phase2
evaluation is complete with known limitations; automatic reliability remains NOT
PASSED. The requested passing objective has not been achieved. No Phase3 work.

## 2026-10-16 new-information preflight (previous; subsequently executed)

The paragraph below records the historical preflight state; the completed
approved execution and decision are recorded above.

After the user requested continuation, completed a read-only audit and
[bounded Heavy-model proposal](phase2_new_information_proposal_20261016.md).
Recounted original-gate-passed human-unreliable points: elbow72, wrist49;
by-clip counts and source receipts are in the new preflight JSON.
380 current protected and62 upstream hashes match. Intake SQLite remains
1batch/8pitches/45events; imported records do not imply formal acceptance.
New inference/FIT/downloads/human annotations=0. The rejected13-feature
classifier remains sealed and closed. A single offline MediaPipe Heavy
comparison with fixed calibration and decisions is proposed, not executed;
await user confirmation as required for a new-model benchmark. Phase2
automatic reliability remains NOT PASSED. No core changes or Phase3 work.

## 2026-10-16 approved single joint-quality trial (previous)

User confirmed the fixed plan with “可以”. [Results](phase2_joint_quality_classifier_results_20261016.md).
Completed FEATURE / four-train-one-test FIT / annotation-free APPLY / sealed-OOF
EVALUATE once, 592 saved source frames, 587 per-joint effectiveness frames,
10 genuine classifier fits, all converged in 5–6 iterations; no refit or tuning.
The approved proposal text stays at its historical SHA; approval and fixed execution
are recorded in the new execution manifest. It is no longer awaiting confirmation.

Classifier major comparison is not claimed. Local elbow TP/FN/FP=13/71/13,
wrist=20/51/24. Score-only baselines=9/75/59 and19/52/114; sample-maximum=8/76/1
and8/63/1. Elbow misses TP>=17, FP<=1 and two-non003-clip improvement; wrist misses
TP>=27, FP<=1 and non003TP>=23. Neither joint qualifies: no adoption is proposed.
Stop adjusting these signals; record need for better images or model information.

Under unchanged original gates, classifier hypothetically flags13elbow/16wrist
previously supported wrong points, while flagging9/21supported good points.
Support without the new hint=453/477elbow,309/350wrist; reviewed good support
remaining376/245. These are burden/support estimates; no records or gates were changed.
003 held out: elbow3/33/1,wrist1/11/0;104elbow still unflagged and original major hold
preserved. Unknown human labels and each joint's3missing raw frames stay explicit.
Other four precise accuracy remains null;003XY is auxiliary only.

55new tests; full844run/842passed/0failed/0errors/2Windows symlink skips,
56.411s,exit0,formal5E2E. Independent1184feature rows/15392values match exactly;
10training preprocessing/gradients and1168probabilities verified, max score difference
6.11e-16. FEATURE GT reads0,APPLY annotation reads0,each FIT reads only4other GTs.
380current protected sources and62upstream hashes unchanged; original raw/GT/core,
first-step review evidence,MoveNetattempts and8pending/unanalysed candidates preserved.

Output:`analysis_results/phase2_joint_quality_classifier_20261016_01/`.
The two authorized steps are now complete. First-step major review hints remain
available; the second-step classifier stays offline and unadopted. Automatic
Phase2 reliability remains NOT PASSED under the existing requirements. No additional
small rules, model trials, new annotations or Phase3 work are started.

## 2026-10-16 additive major review hints (previous)

User-authorized Step 1 is delivered: `analyze-pitch` now writes an additional
`major_review_hints.json` and registers it in the new analysis manifest.
It preserves all existing statuses, gates, predictions and coordinates. The union
is the original tracking screen + existing bbox support + cross-clip shoulder/hip
disagreement, exactly matching the sealed major TP20/FN1/FP9/TN557 on 587 nonseed
development frames. All 592 source frames and diagnostics remain present.
003/104 is still unflagged and explicitly recorded as a known miss.

The packaged evidence is bound to exact video/identity/model/raw/capture/timeline.
Unknown or changed inputs are `not_evaluated`, with null review flags; missing or
corrupt evidence is `evidence_unavailable`. No hint implies no accuracy guarantee.
These are review prompts developed on five already inspected clips, not new-video
validation, corrected coordinates or automatic frame rejection.

The formal five-clip E2E actually matched all five fresh outputs to the evidence:
nonseed hints 2/0/19/5/3. Full suite 789 run, 787 passed, 0 failed/errors,
2 Windows symlink skips, 64.452 seconds, exit 0. Wheel packaging contains the exact
module and frozen evidence. New tests: 18. Historical protected files: 373 unchanged;
the only authorized change among 374 is the analysis artifact hook. Pose/tracking,
selector, original gates, raw and human GT remain unchanged; 62 upstream refs match.

Output: `analysis_results/phase2_major_review_hints_20261016_01/`.
[Step 1 contract and limits](phase2_major_review_hints_20261016.md).

Step 2 [classifier plan](phase2_joint_quality_classifier_plan_20261016.md) is
AWAITING_USER_CONFIRMATION. No classifier training or application has run.
Proposed per-joint decision: elbow TP>=17/FP<=1/non003 TP>=10;
wrist TP>=27/FP<=1/non003 TP>=23, each with improvement on at least two non003 clips.
All five folds must be valid; unknown/missing states remain in their proper denominators.
Only a passing joint would be proposed for user-approved review-hint adoption.
Automatic Phase 2 acceptance remains NOT PASSED; no Phase 3.

## 2026-10-15 fixed 2x ROI experiment and delivery (previous)

[Results and acceptance summary](phase2_expanded_roi_results_20261015.md).
The previously proposed single 2x arm is now complete: 592 saved source frames,
587 nonseed frames, 592 durable pose attempts/completions, 0 tracker calls.
An actual resume verified 0 additional inference calls. Same MediaPipe Full IMAGE,
original selector and gates, no production or GT modifications.

Nonseed selected frames (narrow / expanded / full IMAGE / VIDEO):
001: 81/81/84/86; 002: 174/174/174/174; 003: 108/88/89/114;
004: 102/108/109/111; 005: 87/99/99/99. Totals: 552/550/555/584.
003 same-frame narrow-to-expanded elbow MAE 11.0391→20.4522 degrees (35 frames),
knee 4.0257→5.5399 (73 frames). Visible-reference supported elbow 40/51,
knee 81/113, versus narrow 41/51 and 98/113. Other four precise errors remain null.
All missing/lost/gained records and original major/eligibility context are retained.

Decision: fixed 2x NOT_ADOPTED. Restored selection on 004/005 cannot erase the
003 losses or certify corrected joint locations. Five comparison sheets / 11 cases
were inspected as engineering evidence, without generating new human labels.

Full suite: 771 run, 769 passed, 0 failed/errors, 2 Windows symlink skips,
58.508 seconds, exit 0, including the formal five-clip E2E. The initial sandbox run
skipped 8 additional junction checks; the final ordinary-environment run covers them.
Independent arithmetic audit: 592 frames, 19,866 mapped landmarks, 28,416 joint states,
1,380 human records, 920 angle streams; maximum angle difference below 9.55e-12 degrees.
374 protected files and 62 upstream sources unchanged; original MoveNet attempts
unchanged; 8 handoff candidates remain pending/unanalysed, SQLite counts 1/8/45.

The agreed evaluation and this bounded repair delivery are complete. Automatic
reliability remains NOT PASSED because known joint errors and missed warnings remain.
No extra ROI ratios, model changes, minor warning rules, mandatory additional XY
annotations, exact uncertain events, zero-FN/FP or holdout requirement are added to
this closeout. Further automatic-reliability repair is outstanding, not silently waived.
No Phase 3. Output: `analysis_results/phase2_expanded_roi_20261015_01/`.

## 2026-10-15 ROI transitions and integration decision (previous)

[Result](phase2_roi_decision_results_20261015.md),
[integration decision and bounded next proposal](phase2_roi_integration_decision_20261015.md).
Preserved690feature/baseline/frame records,684nonseed. Original support transitions remain
independent of manual reference availability. Rebuilt prior230angle/1368point rows and summaries;
new audit keeps all missing reasons and original processed coordinates (never raw substitution).

Controlled IMAGE comparison with visible reference: elbow4loss/3gain,knee3loss/18gain.
All7loss frames have all manual members inside crop and a selected pose but original low gates;
do not infer that all losses are clipped limbs. VIDEOraw comparison elbow8loss/0gain,knee8loss/3gain.
Angle worsening and XY worsening are distinct: elbow46/55/61,knee50/94/111 have all3point errors
decreased while angle error increases. Original GT/major/eligibility unchanged; no oracle fallback.

Fixed narrow ROI is NOT_ADOPTED for production. Existing fiveclip evidence remains decisive:
587nonseed selected552crop/555IMAGE/584VIDEO,new4clips lose22vsIMAGE;003mean gains do not
establish full-cohort suitability. No new arbitrary pass thresholds,zero-FN gates or mandatory GT redo.
Next2xcenter-expanded-input proposal is prepared but NOT_STARTED: sameMediaPipeIMAGE,
savedfloatCSRTrect,sourceclip,no pad/resize/fallback;max592pose/0tracker;no core change or Phase3.

13newtests; full753run/751passed/0failed/0errors/2Windowslinkskips,54.578s,formal5E2E.
Independent690row/context recomputation;374protected/62upstream/formal5/raw/GT/core/gates
unchanged,original592MoveNetattempts unchanged,8candidatepending/unanalysed.0newinference.
Phase2evaluationCOMPLETEwithknownlimits;automaticNOTPASSED.
Output:`analysis_results/phase2_roi_decision_20261015_01/`.

## 2026-10-14 saved ROI angle comparison (previous)

[Result](phase2_saved_roi_angles_results_20261014.md). Re-evaluated already sealed crop/full IMAGE,
formal VIDEO raw and original processed base against the same visible manual 2D reference.
All115frames/230rows saved,114nonseed main denominator;51elbow/113knee manual references.
Original gates/selector/core/GT/holds preserved; human-initialized ROI,0newinference or adoption.

Same-frame VIDEOraw→ROI elbow41pairs MAE23.8410→11.2361degrees,23improve/18worsen;
knee95pairs7.2015→4.6703,55improve/40worsen. Medians increase8.3729→9.2919 /2.7556→3.3081.
Knee major18pairs24.2432→10.6508;other77pairs3.2177→3.2723,so gains concentrate on old drift.
Reference+supported elbow ROI41/51 vs VIDEOraw49/51; knee98/113 vs103/113; missing retained.
Manual reference outside crop on elbow69/knee54–55 remains in primary pairs.69still62.5092degrees
error;105ROI below original elbow gate,keptnull,not a successful repair. Major holds unchanged.

15newtests; full740run/738passed/0failed/0errors/2Windowslinkskips,72.758s,formal5E2E.
Replayed115source/crop/selector frames and1368old pointrows; independent four-stream audit.
374protected/62upstream/formal5/raw/GT/core/gates unchanged;592MoveNetattempts unchanged,
8candidatepending/unanalysed. Source diagnosis and saved comparison complete; automatic
reliability NOT PASSED,noPhase3. ROI has bounded developmental evidence,not production release.
Next: a concrete integration decision must retain human-init scope,missing/crop tradeoffs,
original gates/source isolation and same-frame evaluation;no silent core or threshold change.
Output:`analysis_results/phase2_saved_roi_angles_20261014_01/`.

## 2026-10-14 angle gap source audit and decomposition (previous)

[Result](phase2_angle_reference_gaps_results_20261014.md). All115 original decoded RGB frames,
sealed NPZ, manual PNG/ZIP/review copies, names/hashes/timestamps and original XML coordinates
agree; maximum time difference0ms. Same RIGHT-throwing/LEFT-lead mapping, no engineering
frame/crop/pixel mismatch found. This does not adjudicate human or model point correctness.

Preserved230feature rows:50elbow/106knee base/manual pairs,65/9unpaired,0degenerate hybrids.
Eight subsets/six orders decompose relative-to-manual absolute error; negative contributions
and all original holds remain. Predeclared69/105 wrist displacement46.9752/91.1373px;
all three raw-to-processed distances0px on both frames. Wrist-reference contribution58.8904/
96.8221degrees;105elbow−15.2376 shows interaction, not point correctness. Short projected rays
amplify local sensitivity; derivatives are not annotation confidence intervals or a new gate.

16newtests; full725run/723passed/0failed/0errors/2Windowslinkskips,56.164s,formal5E2E.
374protected/62upstream unchanged; original592MoveNetattempts,8candidatepending/unanalysed,
formal5/raw/GT/core/gates preserved.0newexperimentinference,0coordinatecorrection/adoption.
Source and mathematical diagnosis complete; automatic reliability NOT PASSED, noPhase3.
Next: compare already sealed tracked-ROI predictions against the same visible coordinate/angle
reference, preserving common-pair and missing/gate/crop denominators; no more ratio-rule tuning.
Output:`analysis_results/phase2_angle_reference_gaps_20261014_01/`.

## 2026-10-14 visible manual reference angle assessment (previous)

[Result](phase2_manual_angle_assessment_results_20261014.md). Evaluated two existing 2D features
against reviewed visible manual coordinates for all 115 frames of pitch_003. Elbow reference
exists on 51 frames, base pairs on 50 (MAE25.0452 degrees); knee reference exists on 114,
base pairs on 106 (MAE7.1532). Missing references and predictions are explicit; other four
clips are not assessed against coordinates here. No hidden points or angles reconstructed.

Existing qualitatively eligible subsets still show elbow MAE15.9595 on 37 comparable frames
and knee MAE3.4391 on 86. These are relative-to-manual errors, with unquantified annotation
uncertainty. Same-frame base-to-smoothed elbow MAE25.0452→27.0793 (50frames); knee
7.1532→7.1483 (106frames). Different stream denominators are not treated as improvement.
Original GT, eligibility and all major use holds remain unchanged; no binary accuracy cutoff.

The separate [chain geometry trial](phase2_chain_reliability_results_20261014.md) produced
0 added TP and 9 primary-target FP; rejected. Chain cues are not joint/major improvements.
Full suite709run/707passed/0failed/0errors/2Windowslinkskips,53.189s,includingformal5E2E;
38tests added across chain and angle work. Independent recomputation of115frames/230feature
rows/all summaries and paired strata agrees; max floating difference6.97e-12 degree.
374protected/62upstream unchanged; formal5/raw/GT/core/gates unchanged, original592MoveNet
attempts unchanged,8handoff candidate/pending/unanalysed. Phase2NOTPASSED; noPhase3.
Next: use visible-reference errors to locate the reliability gap and clarify qualitative
eligibility versus numeric feature error; do not add more disproven ratio rules.
Output:`analysis_results/phase2_manual_angle_assessment_20261014_01/`.

## 2026-10-14 supervised joint reference calibration (previous; not adopted)

[Result](phase2_supervised_joint_reference_results_20261013.md),
[frozen protocol](phase2_supervised_joint_reference_plan_20261013.md).
Implemented separate FIT, APPLY and EVALUATE stages. FIT explicitly uses existing
human-reviewed raw observations from the other four clips; each query's own GT is
excluded from its bound. APPLY uses only sealed numeric evidence and does not read GT/views.
This is supervised developmental cross-validation on the previously inspected five clips.

Same canonical local targets and full denominators: 592 frames, 3552 saved joint rows,
3522 non-seed evaluation rows. Elbow TP/FN/FP improves 1/83/0 to 8/76/1; wrist
5/66/0 to 8/63/1, plus one warning on a not-observable wrist. Shoulder is 8/13/1;
lead hip/knee/ankle are 0/4/17, 0/8/6 and 0/5/3. All missing/excluded rows remain explicit.
Large remaining FN and increased leg FP prevent adoption as a general reliability classifier.
Human-reviewed raw correctness does not establish native-reference correctness;
within-reference and candidate-dependent states do not imply reliable anatomy.

21 new tests; full suite 671 run / 669 passed / 0 failed / 0 errors / 2 Windows
symlink skips, 66.016 seconds, including formal-five E2E. Independent reconstruction
of 21312 distances, 30 folds, 3552 states and 3522 evaluation rows found no mismatches.
374 protected sources / 62 upstream references unchanged; original 592 MoveNet attempts
unchanged. Formal videos, raw predictions, GT and core preserved; eight handoff clips
remain candidate/pending and unanalysed. Local warnings are not promoted to major.
Prior offline major union remains TP20/FN1/FP9/TN557; unresolved 003/104 remains withheld
by existing human use restrictions. Phase 2 NOT PASSED; no Phase 3.

Next: establish reference-model position quality and keep qualitative labels, whole-frame
use restrictions and visible-XY targets distinct; do not retune this sealed policy.
Output: `analysis_results/phase2_supervised_joint_reference_20261013_01/`.

## 2026-10-13 six-joint local warning trial (previous; not adopted)

User resumed repair after the preceding finite closeout. [Result](phase2_local_joint_warnings_results_20261013.md),
[frozen protocol](phase2_local_joint_warnings_plan_20261013.md). Six-joint sidecars/evaluator implemented;
592frames/3552saved rows/3522nonseed rows,0new inference;GTonlyevaluator,existing gates/raw/core preserved.
Newshoulder/elbow/wrist TP/FN/FP=8/13/0,1/83/0,5/66/0;leadhip/knee/ankle=0/4/15,0/8/2,0/5/2.
Coverage too low;other-clip samplemax is an extreme screen,not a general reliability classifier;not adopted or retuned.
All19localFP occur in003major spans with visible manualXY and large raw error;canonical labels unchanged,reference targets keptdistinct.
Oldjump/localunion scores,unknownwarningburden andmodel×human×evidence strata saved;local warnings never promoted to major.
Fullsuite650run/648passed/0failures/0errors/2Windowslinkskips,58.123s,includingformal5E2E;29newtests.
Independent21312distances/30folds/states/scores verified;374protected/62upstream unchanged,GT5reviewed,592modelattemptsunchanged.
8handoffcandidatepending/unanalysed;majortrial20/1/9 unchanged;Phase2NOT PASSED,noPhase3.
Next: clarify qualitative joint labels versus reviewed visible-XY evaluation targets before selecting calibration;no further tuning of this policy.
Output:`analysis_results/phase2_local_joint_warnings_20261013_01/`.

## 2026-10-13 Phase 2 finite closeout (previous)

[Closeout report](phase2_closeout_20261013.md), [source plan](evaluation_plans/phase2_closeout_20261013_01.json).
Five-clip human review, baseline evaluation and the authorized bounded warning-repair delivery are
**COMPLETE WITH KNOWN LIMITATIONS**. **Phase 2 acceptance remains NOT PASSED; automatic_accepted=false.**
Reproduced all five reviewed-reliability/feature/cue artifacts exactly, plus the saved visible-XY assessment
and latest sealed warning evaluation.592frames/3552focus-joint rows;manualXY1205visible/173notobservable/2uncertain.
Reviewed unsmoothed2D feature eligibility remains elbow246/592,knee530/592;not numeric angle accuracy.
Production screen across592frames remainsTP3/FN18/FP9/TN562;offline587nonseedtrial20/1/9/557 is not adopted.
Remaining003/104,local-arm errors,occlusion and9major-targetFP remain explicit;no invented zero-FN or pass threshold.
Fullsuite621run/619passed/0failed/0errors/2Windowslinkskips,68.712s,includingformal5E2E.
Source protections374/62,formal5/raw/GT unchanged;handoffreader already authorized/completed,8candidatespending/unanalysed.
005independentpeer event supplement remains separatepending;canonicaluncertain is valid and review5/5 complete.
Output:`analysis_results/phase2_closeout_20261013_01/`,including machine-readable release status and full evidence.
Stop at this closeout;noPhase3,noautomaticpromotion,newmodels or additional small warning rules.
Later automatic-reliability changes require a concrete scope and acceptance agreement;no claim of stability or release.

## 2026-10-12 cross-clip disagreement warning repair (previous)

[Result](phase2_disagreement_warning_results_20261012.md), [frozen protocol](phase2_disagreement_warning_plan_20261012.md).
Implemented an offline warning candidate using the other clips' finite non-seed torso-RMS minima sample maximum.
This is an experimental data-derived threshold, not a change to existing production gates; no human labels in producer/calibration.
592sealed frames/587eligible;0new inference. Previous additive major screen TP10/FN11/FP9/TN557
becomes developmental trial **TP20/FN1/FP9/TN557**;10newTP/0newFP, original warnings preserved.
New warnings003frames87–103; added coverage87–92/96/101–103; remaining003frame104.
93candidate-dependent/458within-reference/19insufficient states are explicit; none implies correct anatomy.
104disagreement0.03128724 is inside reference0.05148073(from001frame25), despite raw torso mean visible error34.7994px.
All data previously inspected; not untouched holdout or false-alarm guarantee;003major drift raises other folds' reference.
Independent592ranges/5folds/states/587confusions verified;2engineering figures inspected;no newGT.
Fullsuite621run/619passed/0failed/0errors/2Windowslinkskips,66.526s,includingformal5E2E;29newtests.
374protected/62upstream unchanged;src/input/annotations/raw/GTpreserved;8handoff candidate/pending;592originalMoveNetattempts unchanged.
No production adoption or coordinate correction;remainingmajor/local-arm errors and validation preventPhase2pass;noPhase3.
Next: evidence for residual smaller misalignment/local-arm failures, then separate adoption/unseen-data verification;noGT-tunedbound.
Output:`analysis_results/phase2_disagreement_warning_20261012_01/`.

## 2026-10-12 same-joint disagreement validity evaluation (previous)

[Result](phase2_joint_disagreement_results_20261012.md), [frozen protocol](phase2_joint_disagreement_plan_20261012.md).
New12-joint per-slot distances, six-focus human-label/model-state/missing tables;592sealed/587non-seed frames,0new inference.
Same-slot torsoRMS min conditionalAUROC0.997576 on568available rows(18positive/550negative),19unavailable remain explicit.
All measurable major positives belong to one known003drift; no held-out generalization or99.76%accuracy claim.
Throwing elbow/wrist minAUROC0.793277/0.828164, clip-specific failures retained; lead-leg positive counts too small.
003visibleXY1195pairs Spearman min0.592146/max0.110261;100left-wrist min disagreement3.563px despite raw error151.056px.
Three figures inspected; independent42624distances/3552torsoRMS/7104states/GTdenominators verified.
Fullsuite592run/590passed/0failed/0errors/2Windowslinkskips,58.844s,includingformal5E2E;39newtests.
374protected/62upstream unchanged;formal5/raw/src/GT5of5 preserved;8handoff candidate/pending;originalMoveNet592attempts unchanged.
No new binary warning, threshold or production adoption;originaladditiveTP10/FN11/FP9 unchanged,automaticPhase2NOT PASSED.
Next: separately freeze ambiguity/missing warning semantics and calibration-validation split;noPhase3.
Output:`analysis_results/phase2_joint_disagreement_20261012_01/`.

## 2026-10-12 torso-overlap trial closed (previous)

[Result](phase2_torso_support_results_20261012.md), [frozen protocol](phase2_torso_support_plan_20261011.md).
New offline torso hull/per-joint residual diagnostics and25regressions;592sealed frames,0new pose/tracker calls.
587non-seed major evaluation exactly matches previous bbox screen: additiveTP10/FN11/FP9/TN557.
Zero additional warnings;all11misses retain overlap with every compatible torso hull, despite raw mean60.1448px error.
Overlap does not establish same-named joint alignment; this rule is not adopted or retuned after GT.
20engineering figures/5pages inspected, independent exactSAT/frame/GT audit matches592frames; no new human labels.
Fullsuite553run/551passed/0failed/0errors/2Windowslinkskips,91.495s,includingformal5E2E.
374protected/62upstream unchanged; formal5/raw/src/GT5of5 preserved;8handoff candidate/pending.
AutomaticPhase2 remainsNOT PASSED; noPhase3. Next: joint-alignment evidence/reliability semantics under a separately frozen plan.
Output:`analysis_results/phase2_torso_support_20261011_01/` (study began10/11,closed10/12Taipei).

## 2026-10-11 full-frame comparison and additive support trial (previous)

[Cohort comparison](phase2_movenet_cohort_results_20261011.md), [support warning trial](phase2_movenet_support_results_20261011.md).
Exactly592 MoveNet calls,587non-seed frames;281unique geometric candidates/290ambiguous/16none.
Only003 has visible manualXY:315 common points meanVIDEO16.9097→MoveNet10.8032px,162lower/153higher;880unassociated.
No new-output XY accuracy for other4, no hiddenXY truth or identity proof.34fixed engineering figures inspected.
GT-blind native-box support conflict sidecar,0extra inference: baseline screenTP3/FN18/FP9→additiveTP10/FN11/FP9.
7new warning frames,0new FP on known data;19abstentions retained in primary denominators.
Existing joint-jump diagnostic union separately13/8/56→16/5/56;5remaining frames90/92/96/102/103 in003.
AutomaticPhase2 staysNOT PASSED; production model/core/thresholds unchanged, no adoption orPhase3.
Finalsuite528run/526passed/0failed/0errors/2Windowslinkskips,117.824s,includingformal5E2E.
374protected sources/62upstream unchanged,5of5GT reviewed,8handoff candidates pending.
Support evaluator_01 failed on absent tracking timestamp field before output;_02 uses bound capture timestamps, preserves snapshot/log.
No producer/policy/GT change or model rerun. Next: diagnose the11screen-plus-geometry misses and local-arm reliability.
Output:`analysis_results/phase2_movenet_cohort_20261011_01/`.

## 2026-10-11 isolated MoveNet compatibility gate (previous; production unchanged)

[Result](phase2_movenet_compatibility_20261011.md),
[frozen execution](evaluation_plans/phase2_movenet_compatibility_execution_20261011_01.json),
[result seal](evaluation_plans/phase2_movenet_compatibility_result_20261011_01.json).
Status `compatible_synthetic_only`; 1 synthetic attempt, zero MoveNet formal-video calls.
Exact official MultiPose Lightning TF2 v1 / TensorFlow CPU2.21.0, separate33-distribution environment;
32wheels /405,678,583bytes verified against official PyPI SHA; pip check has no broken requirements.
Actual signature, six whole-frame preprocessing fixtures, observed padding/inverse and first-call timing saved.
Runtime executable and installed file bytes verified before/after; no production backend adoption or accuracy claim.
Fullsuite 472run/470passed/0failures/0errors/2Windowsfile-symlinkskips,69.675s,
includes real formal-five MediaPipe E2E separately from the synthetic gate;15newtests.
374protected physical sources/62upstream references unchanged; formal5/raw/GT5of5/src unchanged.
Original30package metadata entries and3dependency files unchanged; no baseline package-bytes before snapshot.
Eight handoff clips remain candidate/pending, no analysis/promotion. Automatic Phase2 staysNOT PASSED; baselineFN18 unresolved.
Output:`analysis_results/movenet_compatibility_20261010_01/`. Stop at committed/pushed clean checkpoint; no592-frame comparison orPhase3.
The10/10 proposal's pending/no-download text below is historical; this approved gate supersedes that status only.

## 2026-10-10 paired ROI loss diagnosis (previous; production unchanged)

[Diagnosis](phase2_roi_loss_diagnosis_20261010.md),
[bounded complete-input proposal](phase2_complete_input_comparison_plan_20261010.md),
[result seal](evaluation_plans/phase2_roi_loss_result_20261010_01.json).
Saved candidates replay the original selector exactly for592frames; no diagnostic pose/tracker inference.
587non-seed pairs:527both-selected/28new-loss/25gain/7both-unselected.
Newfour alone28loss/6gain, net-22;003gain19 retained separately.
28loss=12backend-empty/15original-selector-rejected/1ambiguous (001/44).
14rejections have only5/8major joints at original0.35, below original6 requirement;005/67
shoulder-to-ankle height0.1467945031<original0.16. No new-loss continuity exclusions.
Supported-gate loss/gain:rightelbow65/15,rightwrist75/17,leftknee99/28,leftankle100/29.
002selects174/174 yet loses15elbow-supported frames, all originalIMAGE proxies insidecrop;
availability/ROI containment is not anatomy, and rejection branches do not establish backend failure causes.
No newaccuracy/GT/warning policy or fix to baselineFN18; automaticPhase2 remainsNOT PASSED.
Fullsuite457run/455passed/0failures/0errors/2Windowsfile-symlinkskips,54.968s,
includes real formal-five E2E separately from saved-output diagnostic.13newregression tests.
374protected physical sources/62upstream references unchanged; formal5/GT/production src unchanged;
eight handoff clips remaincandidate/pending, no analysis/promotion.
Output:`analysis_results/phase2_roi_loss_audit_20261010_01/`.
Propose MoveNet MultiPose Lightning TF2 v1 isolated compatibility gate under prior benchmark-proposal instruction:
approval pending, at most1synthetic smoke inference and0formal-video inference; no acquisition/install yet.
MediaPipe baseline remains. A592-frame comparator requires a later sealed plan after compatibility report.
Stop at clean committed/pushed checkpoint; noPhase3.

## 2026-10-10 five-clip assisted ROI cohort (previous; not adopted)

[Results](phase2_assisted_roi_cohort_results_20261010.md),
[actual frozen execution](evaluation_plans/phase2_assisted_roi_cohort_execution_20261010_02.json).
HSU confirmed four frame0 subjects and presently visible extents: actual reply 全部正確 saved separately;
original drafts/questions unchanged, later identity/hidden anatomy/human completion time/confidence not inferred.
Four new clips477frames,4initializations/473updates/477pose calls;003 reuses sealed115frames and exact XY summary,
zero new tracker/pose/evaluation inference. All592 retained;587non-seed effectiveness frames.
Crop selected552 vs fullIMAGE555 vs originalVIDEO584. Perclip crop-IMAGE differences -3/0/+19/-7/-12;
the four NEW clips444/473 vs IMAGE466/473 regress22frames, not hidden by003's19-frame increase.
All587 subsequent native tracker updates succeed and allROIs are usable, yet extended limbs visibly leave narrow crops.
35non-selected frames =16backend-empty/18original-selector-rejected/1ambiguous; no gate change or guessed causal label.
Crop throwing-elbow supported gate availability:44/86,139/174,77/114,68/113,80/100; not anatomical accuracy.
Per12joint raw/gate/support/extrapolation/visibility/presence/missing spans/adjacent jumps saved.
Only003 has exact visible XY, reused without rerun; fourclip XY and newwarning/identity/event accuracy remainnull.
39prespecified figures inspected as engineering evidence, not new humanGT. CanonicalGT5/5 remainsreviewed.
Fixed narrow crop setting fails cohort applicability and is NOT adopted into production; automaticPhase2 staysNOT PASSED.
Next: diagnose new missing/input-extent evidence and preregister a bounded complete-input strategy, no GT-tuned padding,
automatic fallback, confidence reduction or repeated wholeGT review. Stop at this checkpoint; noPhase3.
Fullsuite444run/442passed/0failures/0errors/2Windowsfile-symlinkskips,73.972s, includes real formal-five E2E.
374protected physical sources and upstreamseals/replies unchanged; no production src/threshold/selector/pose/tracking edits.
Eight handoff clips remaincandidate/pending, no analysis or promotion. Output:`analysis_results/phase2_assisted_roi_cohort_20261010_01/`.
Execution `_01` retained unused because evaluator gained plan-document SHA guard before ANY inference; `_02` seals final code,
same source/settings, with amendment reason and previous hash. No overwritten freeze or repeated measurement.

## 2026-10-10 crop completeness diagnosis and next-gate design (preceding)

[Next-gate plan](phase2_roi_completeness_fiveclip_plan_20261010.md).
Offline replay of all115 original selector receipts matches exactly. All six rejected frames have valid ROI:
63/68/79/81 backend no-candidate,65 only5/8 major joints meet existing0.35rule,80 body height0.07945
violates existing0.16 minimum. Backend empty causal reason remains unknown; no gate change or fabricated occlusion.
44visible reference points outside crop across26frames;21left-wrist/11right-ankle dominate. Do not tune padding fromGT.
Defined missing/support/unknown semantics and five-clip prerequisites; no new detector or warning implemented.
Only003 has saved human-confirmed seed and pixelXY reference; four frame0 visual proposals and two contact sheets
are prepared, with confirmation requested in conversation. All four human-answer fields remainnull; do not execute
unreviewed proposals or transfer prior responses. Preserve drafts and save future actual replies separately.
Five assisted clips retain592sourceframes,587non-seed if excluding eachframe0; all5canonicalGT remainsreviewed.
No direct four-clip expansion/new padding/fallback selected; quantitativeXY for four clips remainsnull.
Human-seeded experiment cannot certify automatic initialization; automaticPhase2 remainsNOT PASSED.
No new inference/tracker/GT/core change;374protected hashes unchanged. Latest suite409passed/2skipped
is the preceding411-test formal-five run, not rerun for this documents/offline-audit checkpoint.
Audit:`analysis_results/phase2_roi_completeness_audit_20261010_01/failure_audit.json`.
Eight handoff clips remaincandidate/pending; no Phase3.

## 2026-10-10 tracked crop pose sensitivity checkpoint (preceding)

[Results](phase2_tracked_roi_pose_results_20261010.md),
[frozen execution](evaluation_plans/phase2_tracked_roi_pose_execution_20261010_01.json).
Added isolated crop producer/offline evaluator and 28 regressions. One003 forward run,115 native frames,
same full model/options/original selector; sealed CSRT rectangles reused without tracker replay or tuning.
Frame0 excluded:114frames/1195visible manual references,1151in/44out. All source/crop pixel/PTS,
XY/Z mapping and both crop/full-IMAGE selector receipts independently verified across115frames.
Primary supported common847points: fullIMAGE mean19.1565px -> crop9.0031px,478improved/369worsened.
Original major18 common113points:80.4089 ->10.8965px,110improved/3worsened; other96 common734:
9.7266 ->8.7116px,368improved/366worsened. Old labels are group membership, not new CROP correctness GT.
Secondary common1002withVIDEO:20.7130 ->9.6994px. Different conditional sets remain separate.
Crop108selected/6rejected; missing64visible points/below-gate95, cropgate1036vsIMAGE908/VIDEO1140.
Only1016cropgate points have reference AND prediction inside input.44out-of-crop references stay in denominator.
Visible throwing elbow87–96 remains below existing gate; no confidence reduction or fabricated observation.
Nine prespecified examples inspected; severe torso displacement improves, local errors and cropped limbs remain.
Known003/human-initialized development evidence only, no automatic promotion/core integration/other-four expansion.
Newwarningpolicy/counts/identityaccuracy/eventaccuracy/passed=null; original productionFN18 remains unchanged.
Phase2 automatic reliability staysNOT PASSED. Next: input completeness/abstention and bounded five-clip validation
design before any proposed core change; do not repeat5/5GT or automatically tune crop settings.
Fullsuite411run/409passed/0failures/0errors/2Windowsfile-symlinkskips, including real formal-five E2E.
374protected physical sources plus upstreamCSRT/replies/mode seals unchanged. Eight handoffclips candidate/pending.
Output:`analysis_results/phase2_tracked_roi_pose_20261010_01/`. No Phase3.

## 2026-10-10 human-initialized subject continuation checkpoint (preceding)

[Results](phase2_subject_assignment_results_20261010.md),
[frozen execution](evaluation_plans/phase2_subject_assignment_execution_20261010_01.json).
New isolated CSRT measurement/offline evaluation and35 regressions; production core remains unchanged.
Only003, one human-confirmed model-proposed Q1 initialization,27 installed defaults, one forward execution.
Producer reads video/metadata/technical/Q1-only input; no full review, pose or manualXY content.
All115 source receipts retained and independently pixel/PTS verified; initialization1/update114/native-success114.
Frame0 excluded:1195 visible manual points partition1151 inside/44 outside/0 unavailable;
105/105 visible torso proxies inside,9 reference-missing frames retained separately.

HSU explicitly answered all ten NEW fixed-frame rectangles are pitchers. Actual reply saved separately in
`review_tools/seeded_subject/HSU_pitch003_csrt_20261010_01.json`; extent/confidence/human completion time
remainnull. Blank generation, sealed measurements/evaluation, prior nine HOG replies and canonicalGT unchanged.
This supports limited human-initialized continuation feasibility, not114-frame identity/anatomical accuracy
or automatic initialization. Known development data only; no independent tracker replay claimed.
10/18 original major failures still contain the wrong raw torso in the tracker box;
containment alone cannot fix originalFN18. No new warning policy/counts, identity accuracy or IoU.
AutomaticPhase2 remainsNOT PASSED. Next design must handle incorrect anatomy inside a correct subject box
and ambiguity before any full592-frame warning regression; do not adopt/extend this pilot automatically.

Full suite383 run/381 passed/0 failures/0 errors/2 Windowsfile-symlink skips,
including real formal-five E2E. Initial sandbox permission failures and the intermediate E2E-not-configured
run are preserved as history; final configured suite includes all five. All374 protected physical sources,
prior HOG seals and ownership replies unchanged. Output:`analysis_results/phase2_subject_assignment_20261010_01/`.
Five formal videos/raw/GT and production thresholds/selector/pose/tracking/smoothing/interpolation unchanged.
Eight handoff clips remaincandidate/pending; no new-input analysis, promotion orPhase3.

## 2026-10-10 person-support human review checkpoint (preceding experiment)

[Bounded HOG pilot results](phase2_person_support_results_20261009.md) and
[latest frozen execution](evaluation_plans/phase2_person_support_execution_20261009_03.json).
Implemented isolated GT-blind measurement plus source-bound offline evaluation
and26 regressions; no production core or human-label edits.003's115 native frames
produce177 grouped person boxes on114 frames. Complete115-frame replay reproduces
every rectangle/rawSVM value exactly as a multiset;8 API-order-only differences
are retained and separately reported. Candidate indexes are run-local.

Existing manual proxies are available106 frames/missing9;93/106 have some box
containing all four visible shoulder/hip points. All18 known major failures have
boxes, and7/18 have a box containing even the wrong raw shoulder/hip points.
Containment cannot certify correct alignment. Nine fixed-case box ownership
answers are now saved separately in
`review_tools/person_support/HSU_pitch003_20261009_01.json`:6pitcher/3other,
including2 explicit partial pitcher boxes. Original reply and Q2/Q3 clarification
are preserved; other7 extents unspecified. Blank generation/sealed evaluation
stay unchanged. Human completion time/confidence remainnull; recording time
is separate. Existing5/5 canonical GT stays COMPLETE. No automatic pitcher selection.
Identity accuracy/IoU/new warning counts remainnull; originalFN18 remainsunfixed.

CLI dispatch and API-order comparison repairs are documented with original
seals/code snapshots and planSHA chains; neither changes detector parameters or
introduces numeric tolerance. The order comparison amendment is explicitly
post-observation, not claimed as the original prespecified rule.
Output:`analysis_results/phase2_person_support_20261009_03/`.
Full suite348 run/346 passed/0 failed/0 errors/2 Windowsfile-symlink skips,
including real formal-five E2E; all374 protected physical sources unchanged.

The nine ownership checks are COMPLETE; remaining168 boxes stay unreviewed.
Source and reply mapping verification:
`analysis_results/phase2_person_support_20261009_03/ownership_review_20261010_01/`.
Sampled frames86/105/112 include both pitcher and other-person candidates;
ownership does not certify anatomy, full-body extent or temporal identity.
This candidate is not adopted as standalone alignment evidence or extended
to the other four clips. A five-clip warning evaluation needs a separate bounded
subject-assignment/ambiguity policy and validation design first; do not tune
to these nine known cases or repeat completedGT. This review-only checkpoint
adds no inference/core change; latest full suite above remains346 passed/2 skipped.
AutomaticPhase2 remainsNOT PASSED; eight handoff
clips remaincandidate/pending; no promotion/new-input analysis or Phase3.

## 2026-10-09 capability/proposal history (before execution above)

[Bounded person-support proposal](phase2_person_support_proposal_20261009.md)
and [proposal manifest](evaluation_plans/phase2_person_support_proposal_20261009.json).
Local capability-only check confirms OpenCV5.0.0 defaultHOG/personSVM,
3781 coefficients/64x128 window with bound coefficient/native-library hashes.
Zero image/video inference, downloads or installs. No new runner or new result
is claimed; this manifest is explicitly not an execution freeze.

Proposed feasibility scope is003's full115 native frames, one fixed configuration,
all returned grouped rectangles/rawSVM scores, no poseROI/humanseed/automatic
pitcher assignment or warning policy. A person box can also support the batter;
it is not verified pitcher alignment. Existing visibleXY/TPO pixels do not
establish whole-box identity or IoU. If viable candidate evidence appears,
at most12 known-case rectangle-membership questions would be proposed separately;
no human answers have been filled, no completeGT review is reopened.

The original374 protected physical sources remain unchanged. Latest complete
code suite remains320 passed/0 failed/0 errors/2 Windows skips; this docs-only
proposal does not rerun tests or media. AutomaticPhase2 remainsNOT PASSED,
eight inputs remaincandidate/pending; no Phase3 or production model change.

## 2026-10-09 authorized repair: full-frame mode countercheck

[Results](phase2_pose_mode_results_20261009.md) and
[frozen plan](evaluation_plans/phase2_pose_mode_countercheck_20261009.json).
New isolated IMAGE-versus-saved-VIDEO measurement/evaluation tools cover all592
native frames with the same MediaPipe/model/options and unchanged selector.
No production pose/tracking/gate/smoothing/interpolation or annotation edits.

IMAGE selected560 versus original589 frames. All560 selected skeletons are
exactly identical across33 landmarks and5 fields (92,400 scalars; maximumXY
delta0px), independently reproduced. Candidate availability/selection changes
on29 frames are real, so this is not a claim that all mode behavior is identical.
003 major87–104 retains14 identically wrong selected frames;4 become ambiguous.
Its918 common existing-gate visible points have the same20.157145px mean error;
947 commonfinite points have the same21.254704px mean. Missing258 of1205 visible
references cannot be counted as accuracy improvement. Hidden173/uncertain2 excluded.

This bounded direction is not adopted. New warning policy/counts remainnull;
originalTP3/FN18/FP9/TN562 and automaticNOT PASSED remain. Same-model agreement
does not certify correctness; native stateless behavior or internal causes are
unverified. No GT re-review, new-model switch, candidate analysis or Phase3.
Next repair needs independently verifiable image/subject alignment evidence;
different-model benchmarking requires a separate bounded proposal first.

Output:`analysis_results/phase2_pose_mode_countercheck_20261009_01/`, with complete
receipts, comparison, independent audit and95/101/112 illustration panels.
All374 protected physical sources unchanged. Full suite322 run/320 passed/
0 failures/0 errors/2 Windowsfile-symlink skips, including formal-five E2E.
13 new source/missing/coordinate/receipt regressions passed. Eight handoff inputs
remaincandidate/pending; original5/5 canonical review remainsCOMPLETE.

## 2026-10-09 regression gate and return to Phase 2

[Itemized report](handoff_regression_20261009.md). Two real intake reruns each
returned0 new/8 skipped/0 refused; batches1 and pitches8 stayed fixed, events
27→36→45 are execution history. Audit found and repaired an intermediate
junction gap in the handoff human-review entry, with5 new boundary regressions.
Full suite307 passed/0 failures/0 errors/2 platform skips; original240 all passed.
Fresh formal-five predictions plus run_phase2_reliability and reviewed GT
comparison cover592 frames:10 reliability JSONs have0 field differences,
35 raw/processed/quality/metrics files byte-identical. All374 protected physical
sources unchanged; delivered21 and candidate40 files retain bytes/mtime;
9 registries contain0 handoff ID matches. Eight inputs remaincandidate/pending.

Per user direction, returned to the original reliability repair route and
prepared [the repair case index/checkpoint](phase2_reliability_repair_20261009.md):
original major-screenTP3/FN18/FP9/TN562, FN18 is00387–104. This is source-bound
case preparation, not a new detector, core change or claim of generalization.
Automatic Phase2 remainsNOT PASSED; no Phase3/new-input analysis/promotion.

## Authorized delivery candidate reader (2026-10-08)

The user approved the first intake scope independently of automatic reliability
release. [Reader guide](handoff_reader.md). Only the handoff folder's CONTRACT.md
v2 defines the upstream interface; no provider repo/code/output was accessed.
The standalone reader imports indexed MP4/JSON pairs into `data/intake/handoff/`,
checks SHA before/after copying, maps original IDs and explicit local pitcher IDs,
maps unknown to null, and retains durable SQLite deduplication/refusal records.

Each clip must declare CFR=true, fully decode to its declared frame count, and
have every normalized native PTS within strictly less than 1ms of frame index
divided by exact fractional FPS. Canonical contract timestamps separately use
fps_float. Container start is recorded, never applied; energy anchors remain
non-event provenance. No edits to analysis/pitch.py, workflow.py, pose_capture.py
or any other Phase2 core. No analysis runs or pitch-input-v1/formal promotion.

Actual batch `20261006T114959Z_Q8Bl2X4VKuw`:8 candidates,3396 decoded frames,
maximum native deviation0.000666667ms. Repeat:0 new,8 already imported; all
candidate files and delivered bytes/mtime unchanged. Each has7 pending input
review items, no fabricated human findings. Explicit reviewer/time/conclusion/
note and append history are required. Even review_complete remains candidate.
Validation evidence:`analysis_results/handoff_reader_validation_20261008_01/`.
The existing formal five, GT, predictions and protected Phase2 sources remain
unchanged. Phase2 automatic reliability remains NOT PASSED; Phase3 not started.
Full suite:302 passed/0 failed/0 errors/2 skipped,304 total, including the
existing formal five real-video E2E.64 new intake/timing/review/path cases.
Two file-symlink cases skipped due Windows creation permissions; actual
directory-junction containment tests passed. No unresolved test failures.

## Final Phase 2 result (2026-10-08)

[Final report](phase2_final_report.md). Final output:
`analysis_results/phase2_final_yamamoto_20261008_02/`.
Canonical HSU GT is 5/5 reviewed; original warning comparison, reviewed data use,
and003 coordinate assessment reproduce from bound sources across592 frames.
Known major-failure screening remains TP3/FN18/FP9:00387–104 is entirely missed.
The diagnostic union with saved joint endpoints remains TP13/FN8/FP56, not a new
adopted detector. Evaluation completion does not turn these gaps into PASSED.
Confirmed breaks3/3 match; zero confirmed switches cannot measure sensitivity.

New `scripts/export_existing_reliability_cues.py` exposes the already-saved
whole-clip jump endpoint cues on all five formal clips, without any GT input.
New Chinese H264/yuv420p videos, complete JSON and CSV live in
`analysis_results/phase2_automatic_cues_20261008_01/`.
All592 frames/3552 joint rows retained:3028 measured adjacent observed pairs,
92 saved endpoint events across59 frames,524 unmeasured joint rows.
No-cue and unmeasured remain distinct; automatic alignment/identity unverified.
No wider error intervals, real-time latency or hidden-joint recovery claim.

New finalizer separates evaluation COMPLETE from automatic NOT PASSED in
`phase2_final_assessment.json` and `release_status.json` (`accepted=false`).
It verifies canonical/model/video bindings and reconstructs prior comparisons,
reviewed reliability, feature restrictions and1380 saved003 coordinate rows.
Same1174 usable points:raw21.9504px vs clean22.0292px mean error;97.43% retention
is not accuracy. Existing reviewed feature eligibility remains elbow246/knee530
of592 frames; production analyze-pitch does not automatically consume these sidecars.

Final full suite **240 passed /0 failed /0 errors /0 skipped**, including all five
real formal videos, about42seconds.25 new tests (cue14/finalizer11). Secondary
read-only verification confirms374 unique physical source/code/test/media files,
3552 CSV rows, all592 decoded video frames and33 exact PNG source regions.
Five representative panel layouts were inspected; H264 decoded pixels are lossy.
Initial_01 assessment and exact implementation snapshots are preserved;_02 fixes
only duplicate path spellings in physical-file accounting and binds the final suite.
Source plans/code/tests/report are versioned; large generated media stays local.

The separate peer005 event supplement is still not returned. Canonical uncertain
onset/peak answers remain valid reviewed data, not an unfinished review or new
acceptance blocker. Event accuracy/identity sensitivity/unseen-video generalization
are explicitly unmeasured, without invented new work requirements.

This Phase2 evaluation is now closed with NOT PASSED rather than indefinite
IN PROGRESS. Further automatic warning repair requires a separately arranged task.
That evaluation stopped before shared-folder integration and Phase3. The later
user-approved candidate-only intake is recorded above; it does not repair the
automatic reliability result or authorize formal promotion/new analysis.

## Historical checkpoints

The dated entries below preserve earlier in-progress conclusions and next steps.
The final result above supersedes them; they do not reopen completed reviews.

## Historical Phase 2 checkpoint (2026-10-07): review-aware use of saved 2D features

[Feature-use guide](phase2_reviewed_features_20261007.md).
New evaluator-only tool `scripts/export_reviewed_feature_quality.py` exports
`reviewed_features.csv`, `reviewed_feature_quality.json` and a Chinese timeline
for each formal clip under `analysis_results/phase2_reviewed_features_20261007_02/`.
All592 frames/1184 feature rows remain. The two existing unsmoothed base values
are retained; a separate nullable eligible_value requires finite saved raw
observations and all three constituent joints' reviewed qualitative evidence,
with no whole-frame review restriction. Elbow246/592 and lead-knee530/592 rows
qualify;120/366 saved elbow values and36/566 saved knee values are withheld from
that new field. Existing raw metrics counts350/548 remain unchanged.

This prevents known questionable values being silently presented as eligible
in this reviewed export. It is not a new automatic localization detector, numeric
angle-accuracy claim, motion feature or Phase3. Original analysis files and the
production analyze-pitch flow remain unchanged; the latter does not yet consume
this sidecar. Feature-interpolated and smoothed values stay explicitly unverified
because current-frame human review does not certify their neighboring support.
Original missing states stay missing, held values null/CSV blank, and zero remains
a genuine value. No resampling, new aggregate metrics or Phase1 threshold change.

Frozen source plan checks formal identity/handedness/timestamps and reconstructs
the reviewed view from canonical/model sources. Saved base values independently
match original width/height-corrected processed geometry. Numerical tolerance is
serialization-only, not accuracy acceptance. The initial_01 output and exact
implementation snapshots remain; final_02 distinguishes uncertain/not_observable
whole-frame reasons and retains human frame evidence, without changing eligibility.

Full suite **215 passed /0 failed /0 errors /0 skipped**, including all five real
formal inputs, about43 seconds;12 new tests cover constituent dependencies,
raw/imputed provenance, alternate-variant limits, original values, missing/zero,
source/timeline/aspect-ratio mismatches, conservative frame holds and CSV blank
semantics. Test logs/results and read-only audit live under the final output.
Five timeline layouts were visually checked.
Independent read-only audit verifies all1184 rows, nullable CSV cells, complete
source values/flags/evidence, all timeline colors and summaries;349 unique
bound/protected files unchanged. All00387–104 feature rows remain held.
Phase2 remains IN PROGRESS: automatic warning gaps and the separate005 peer event supplement are not resolved
by applying reviewed evidence. Shared-folder integration remains deferred with
the user's stop/report gate; no Phase3 or new pitchers.

## Previous Phase 2 checkpoint (2026-10-07): usable reviewed baseline exports

[Reviewed-output guide](phase2_reviewed_reliability_20261007.md).
All five formal clips now have new **reviewed_overlay.mp4** and
**reviewed_reliability.json** under `analysis_results/phase2_reviewed_baseline_20261007_01/`.
The source-bound derived view covers592 frames/3552 focus-joint rows. It copies
HSU's original intervals/reasons and existing model observed/interpolated/missing
states independently. A Chinese panel marks003's87–104 human-confirmed major
failure,004's75–76 and005's54 human-confirmed breaks, and each focus joint's review.
Raw/processed coordinates, baseline warnings and canonical human annotations
are unchanged. This is usable post-review evidence for known clips, **not a new
automatic detector, new GT schema, coordinate correction or Phase2 PASSED result**.

Each output is H264/yuv420p/faststart. All original/new video frame counts,
dimensions and FPS decode checks pass; every pre-encoding source-overlay region
is unchanged. Reencoded decoded pixels are lossy. All five key-frame layouts,
including major failure, breaks and interpolation, were visually inspected.
The JSON retains uncertain events, unavailable points and per-point use restrictions;
raw-overlay reliable labels never certify cleaned interpolation or visualization median.

The [state-conditioned coordinate assessment](phase2_observation_accuracy_20261007.md)
also completes evaluation of saved003 data: all1380 reference rows and15 groups
reproduce. Of1205 visible references,1150 are observed/24 interpolated/31 missing.
On the same1174 usable points, raw mean error21.9504px vs clean22.0292px;
interpolation improves11 points and worsens13.97.43% retention is not accuracy.
No new pixel threshold or confidence gate is selected.

Full suite **203 passed /0 failed /0 errors /0 skipped**, including all five real
formal inputs, about47 seconds. Six observation-assessment tests and twelve
review-export tests added; full logs/results live in the reviewed-output directory.
Implementation/frozen source plans are committed; generated videos are local
derived artifacts and can be reproduced from the bound sources.
Independent read-only audit matches all592 frame joins/3552 rows and summaries,
all five decoded videos and22 exact PNG source regions;342 unique bound/historical
source files are unchanged. Receipt: `read_only_audit.json` in the export directory.

[Acceptance scope](phase2_acceptance_review_20261007.md) now separates original
completed **5/5 canonical reviewed GT** from the separately requested005 peer
event supplement, still awaiting its actual return. Uncertain events are allowed
review results, not proof that canonical review is incomplete. Baseline evaluation
is complete; automatic reliability remains IN PROGRESS because its known major-
failure misses/false warnings are unresolved. This export does not remedy them.
No reliable finish date follows from the earlier conditional2–4-session estimate.
At the deferred shared-folder todo, stop/report and await the user's start instruction.
No shared-folder integration, Phase3, new pitcher or production algorithm change.

## Historical Phase 2 checkpoint (2026-10-07): fixed clothing appearance diagnostic

[Result and remaining-work report](phase2_subject_appearance_results_20261007.md).
New isolated output: `analysis_results/phase2_subject_appearance_20261007_01/`.
The proposal below has now been executed on003 only, with two immutable9x9
source hypotheses from the earliest existing-gate frame0. No GT entered the
producer; all115 frames/230 patch records remain, and every match/score-map
receipt independently reproduces. Raw source pixels, competitor/tie receipts,
unavailable states and evaluator-only human geometry are stored separately.

Highest-similarity centers fall inside the four-visible-joint manual torso proxy
in33/106 and30/106 frames; outside73/106 and76/106. Even frames without major-failure
reference have56/88 and58/88 outside centers. Remaining9 frames lack a visible
manual right shoulder (70–78), so their proxy stays unavailable. These are geometry
counts, not identity errors/accuracy; source whole-patch ownership remains unreviewed.
Scores/margins overlap major-failure and other frames. This diagnostic is
**insufficient evidence; not adopted as tracking support or a warning**.
No001/002 extension, new cutoff, GT answer, raw pose correction or production change.

Preflight stopped before output creation because CSV native capture milliseconds
are integer while video PTS are fractional. Failed code/plan are preserved under
`analysis_results/phase2_subject_appearance_20261007_00_preflight/`.
The [second before-run plan](evaluation_plans/phase2_subject_appearance_execution_20261007_02.json)
binds corrected original-capture-time alignment, runner/runtime and sources; no
original timestamps or predictions changed. All295/44/5/335 earlier hash inventories
remain intact; independent read-only audit confirms350 unique source files unchanged.

Full suite **185 passed /0 failed /0 errors /0 skipped**, including five formal
real-video E2E inputs; nine additional safety/numerical/reference tests. Total
verification run about54 seconds; log/result live under the new output.
Phase2 remains IN PROGRESS. Remaining gates are evidence-backed subject/warning
policy, per-frame miss/normal-motion false-warning/abstention/coverage evaluation
across592 frames, the independent005 onset/peak event supplement, and explicit
acceptance/reporting. No identity-switch positive GT or unseen validation set
exists. If the next evidence direction works and review proceeds, provisionally
reserve2–4 working sessions (2–4 working days at one session/day); this is planning,
not a verified completion ETA. Further unresolved ambiguity needs more iterations.
At the shared-folder todo, stop and report before any integration as requested.

## Phase 2 resumed by the user (2026-10-06; historical checkpoints)

### Historical proposal: immutable source-image appearance evidence

[Bounded appearance plan](phase2_subject_appearance_plan_20261006.md) and its
[source-bound proposal manifest](evaluation_plans/phase2_subject_appearance_proposal_20261006.json)
were written; **at this historical checkpoint no implementation or measurement was run**. Pilot scope is003's
115frames, up to two9x9 immutable raw-image torso patch hypotheses. Full-frame
image matching stays separate from current skeleton/mask/KLT coordinates;
competitors, texture validity and ambiguity remain visible. No cutoff, warning,
template adaptation, pose correction or production change is proposed for this pilot.
Source patch ownership needs separate reviewer evidence; existing center-point
T/P/O and visible joint coordinates do not establish whole-patch ownership.
Human records remain evaluator-only, all frame denominators remain intact, and
known development clips cannot be relabeled as unseen validation data.
Latest full tests remain176/0/0/0 from the previous code checkpoint; this step
only adds planning documents/source checks. Phase2 remains IN PROGRESS;
the user stop gate before shared-folder integration remains in effect.

### Historical: eleven mask point values measured and compared

[Point comparison report](phase2_subject_mask_points_20261006.md).
New isolated output: `analysis_results/phase2_subject_mask_pilot_20261006_03/`.
Public indexing reads **11/11 fixed positions**, with44 raw pixel receipts and
bilinear weights. Producer receives blank question snapshots only; actual human
answers remain evaluator-only. T3/P2 all score1; O6 range~1.77e-8 to1, including
one score1 and another~.999875. Thus a monotone mask-value cutoff cannot perfectly
separate these eleven references. No cutoff, warning or identity decision is fitted.
Accuracy/AUC/IoU remain null; these two targeted frames lack independent/full-mask
validation. Historical all-missing output and every earlier reply are preserved.

All115 selection traces and3795 landmark rows (18975 values) match baseline exactly.
Both raw frames match the prior reference pixels.335 source/plan hashes and
the295/44/5 prior inventories remain unchanged; independent read-only audit agrees.
Full suite: **176 passed / 0 failed / 0 errors / 0 skipped**, including the formal
five real-video inputs. Five new tests cover public bounds, zero/invalid values
and candidate/dimension association. Production src/dependencies/model/thresholds,
canonical GT and predictions remain untouched. **Phase2 remains IN PROGRESS.**
At this historical checkpoint the additional subject-image evidence proposal
was written and its measurement remained pending. The2026-10-07 result is above.
This mask is insufficient as standalone identity truth.
The shared-folder stop gate remains deferred until Phase2 is stable; no Phase3.

### Preserved supplementary review and initial mask attempts

The user explicitly resumed Phase 2 after the stop checkpoint below. HSU has
completed all eight supplementary questions: five previous membership positions
were rechecked and three new fixed image positions supplement the sparse
reference. Raw context and separate larger crops reduce label/position ambiguity.
Frame86 has six questions; frame95 has two (new 95/q1 is the original 95/q3).
Output: `analysis_results/phase2_membership_supplement_20261006_01/`.
The [frozen query plan](evaluation_plans/phase2_membership_supplement_20261006.json)
contains coordinates/source hashes, never expected human labels.

The generation manifests remain blank snapshots. Actual replies are separate:
[initial transcription](../review_tools/feature_membership/HSU_pitch003_membership_supplement_20261006_01.json)
and [confirmed version](../review_tools/feature_membership/HSU_pitch003_membership_supplement_20261006_02.json).
HSU explicitly clarified frame86/q3 as P (pitcher leg), preserving the original
reply T and prior review O. Supplement: **3 T / 1 P / 4 O**. Latest references
at all **11 unique positions: 3 T / 2 P / 6 O**. Two explicit rechecks changed
codes (86/q3 O to P; 86/q4 P to O); older records and their historical comparison
remain intact. New positions are image samples, not anatomical joints or tracked
features. These are targeted development examples, not a random/holdout benchmark.

Two raw PNGs and untouched context panels match previous exact decoded frames;
295 protected files, 44 prior sources and original membership-comparison sources
remain unchanged. A bounded same-model shadow experiment now ran separately,
with no human replies supplied to inference. The pinned SDK's float mask reader
aborted in two isolated processes with `Check failed: 1 == ChannelSize() (1 vs. 4)`.
The subsequent fail-closed run records all **11 mask values missing**; it does
not repair the reader or fabricate mask probabilities. Accuracy/AUC/IoU remain
null. The 115-frame selection trace and 3,795 raw landmark rows exactly match
the preserved baseline; shared errors and unknown identity remain possible.
No production code, dependency, threshold, warning decision or canonical GT changed.
Report: [same-model mask experiment](phase2_subject_mask_pilot_20261006.md).
Output: `analysis_results/phase2_subject_mask_pilot_20261006_02/`;
comparison: `evaluation_01/human_mask_comparison.json`.
Full suite: **171 passed / 0 failed / 0 errors / 0 skipped**, including all five
formal real-video E2E inputs. Four new tests cover safe failure and sample edges.
Independent integrity verification preserves 295 protected files, 44 prior
sources and five original membership-comparison sources; the failed-run code
archive still matches its original frozen plan. Test logs/results and integrity
check are under the new output. Tests passing do not make unreadable masks usable.
The shared-folder todo remains deferred until Phase 2 is stable; no Phase 3.

### Read-only public mask indexing compatibility probe (2026-10-06, historical checkpoint)

The installed SDK also exposes public `Image[row, column]` indexing through a
distinct float32 native entry point. Three known-array cases (widths2/4/510,
including padded non-contiguous rows) reproduce all **1,548 values exactly**.
A same-model frame0 VIDEO probe reads six valid real-mask pixels without
`numpy_view()`, private pointers, resizing, dependency upgrades or production edits.
The frame0 selection trace and all33 raw landmarks (165 numeric values) match
the existing baseline exactly. Source integrity remains 295/44/5 unchanged.

Output: `analysis_results/phase2_mask_api_probe_20261006_01/`.
This proves bounded read compatibility, not mask membership/identity accuracy.
The prior11-query report remains0/11 usable and is preserved; the frozen query
comparison has not yet been rerun using this API. Next: use validated public
indexing in a separate experiment with explicit coordinate bounds, then compare
all11 positions without feeding human answers into inference. No SDK replacement
is needed for this next point-sampling check. Full suite remains the prior
171/0/0/0 result; this follow-up only ran the compatibility and integrity probes.
The user's stop gate before shared-folder integration remains in STATUS.md.

## Historical stop checkpoint requested by the user (2026-10-06)

At that checkpoint the current work was closed out for a stop. Concise progress, unfinished work and
known issues are in [STATUS.md](STATUS.md); external shared-folder video needs
are in [INPUT_REQUIREMENTS.md](INPUT_REQUIREMENTS.md). No new feature, mask
experiment, warning policy, input integration or Phase 3 was started.

Full suite rerun with the formal five-pitch real-video fixture enabled:
**167 passed / 0 failed / 0 errors / 0 skipped**. The real-video test writes only
temporary outputs and checks execution/artifacts; it does not certify Phase 2
accuracy. Log and result:
`analysis_results/stage1_closeout_20261006_01/`.
Dependency consistency passed. All 295 protected files, 44 prior sources and
five membership-comparison sources remain unchanged; the five E2E fixture
pairs still match their canonical video/metadata hashes.

Phase 1 remains PASSED; Phase 2 remains IN PROGRESS. Formal media, reviewed
annotations and historical predictions are preserved. Pending review and
future proposals remain documented for an explicitly requested resumption.

## Phase 2 baseline

### Eight human feature memberships reviewed and compared (2026-10-06)

The [subject-support proposal](phase2_subject_support_proposal_20261006.md)
defines the next bounded step: two pitch_003 frames (86/95), four saved image
feature queries each. HSU supplied all eight answers in chat: each frame's
queries 1/2/3 are **O** (other person/background), query 4 is **P** (other visible
pitcher part). Total: **6 O / 2 P / 0 T / 0 uncertain**. The exact reply,
source-bound query IDs/coordinates and image hashes are saved in
[the review transcript](../review_tools/feature_membership/HSU_pitch003_20261006_01.json).
No confidence, subtype or new review completion time was supplied or inferred.
Raw/marked images include separate magnified patches for every query;
completed twelve-joint annotation remains unchanged.
Output: `analysis_results/phase2_feature_membership_pilot_20261006_02/`.
The initial `_01` display draft is preserved; `_02` improves overlapping labels.

Existing contracts cannot encode arbitrary feature membership or masks; the
manifest remains the original blank generation snapshot; actual human responses
are preserved separately. The blank `REVIEW_NOTES.md` is also preserved.
No canonical/schema change or automatic annotation has occurred. A proposed
candidate uses the existing MediaPipe model's optional segmentation output;
local SDK fields and model hash were checked, but no pose/mask inference,
benchmark, new model or production change was run. Candidate masks and subject
binding require evidence; they are not independent identity truth.

The offline comparison is in `evaluation_01/human_membership_comparison.json`
under the pilot output. All eight joins match. The lowest per-frame FB rank
group's two representative queries are both O. All eight are outside the old
anatomical torso proxy, including the two P points. This supports two limited
conclusions: small FB error does not establish pitcher membership, and outside
the torso proxy does not establish non-pitcher membership. The 6/8 count is not
a full-clip error rate, identity-switch label or mask accuracy result.

All 295 protected files and 44 prior source files remain unchanged. Full suite:
**166 passed / 0 failed / 0 errors / 1 skipped**, 167 discovered; the optional
real-video handoff test requires `PITCH_ANALYSIS_REAL_BASELINE_DIR`.
Next: keep the bounded subject-mask proposal separate from production; this
pilot has no torso-positive T query, so it cannot establish torso coverage.
Phase 2 remains IN PROGRESS. Peer pitch_005 events and later Clipper handoff stay
pending under the existing sequence; no Phase 3.

### Feature support validity checked (2026-10-06)

The [feature-support report](phase2_feature_support_validation_20261006.md)
checks saved image features against pitch_003's reviewed visible shoulder/hip
geometry. The frozen GT-blind producer retains all 28,185 usable feature-frame
rows on five clips; a separate evaluator uses human coordinates only afterward.
This is an anatomical torso proxy, not foreground segmentation or identity GT.
No features are rejected, reseeded or corrected; warning thresholds remain null.

003 has proxy reference in 106/115 frames (70–78 right shoulder not observable),
and paired reference in 104/114 transitions. Of 6,783 feature-frame rows, 6,288
have current reference and 6,171 have both endpoints. Missing rows are explicit.
The lowest within-frame FB rank group still has 1,031/1,530 rows outside the
visible torso hull; low FB cannot guarantee torso support. Normal-motion frame86
has 0/55 inside with maximum FB .000829px. Outside proxy alone does not prove
background or another person, and cannot serve as a major-pose-failure label.

The other four clips lack reviewed torso XY and retain unavailable/null proxy
results. Five uniform contact sheets and the reference comparison were inspected;
agent diagnostic notes remain separate from human GT. Full suite: **166 passed /
0 failed / 0 errors / 1 skipped**, 167 discovered. All 295 protected files, 42
prior sources and 44 current sources remain unchanged; independent recomputation
passed. Output: `analysis_results/phase2_feature_support_20261006_01/`.

Next: define a bounded candidate foreground-support method and its independent
reference needs before selecting a production warning policy. Phase 2 remains
IN PROGRESS; no algorithm changes, new warning decisions, Phase 3 or Clipper handoff.

### Offline image/geometry evidence measured (2026-10-06)

The [five-clip measurement report](phase2_image_geometry_experiment_20261006.md)
compares frozen experimental image motion and raw 2D arm geometry against the
existing HSU GT and reviewed Tsai/HSU coordinates. All 592 frames were measured
without new formal-clip pose inference or production algorithm changes. Producer
inputs exclude human annotations; the separate evaluator uses them only after
measurement. No warning decisions, fitted thresholds or model training exist.

Adjacent-step discrepancy shows exploratory separation for pitch_003's 18
displaced frames (conditional AUC .924190 within that clip). Pooled evidence has
18/21 positive frames with values; the three skeleton-loss positives remain
missing, not successful detections. All measured major positives come from one
known interval. Normal motion overlaps with discrepancy, cumulative evidence is
weaker, and local elbow/wrist/geometry separation varies across clips. Actual
feature inspection shows foreground drift despite numerically successful KLT
and sometimes small round-trip error. This is not an accepted warning detector.

Output: `analysis_results/phase2_image_geometry_measurements_20261006_01/`;
final evaluator output: `evaluation_02/`. The original `evaluation/` remains
preserved; only a pooled normalized-unit key was corrected, with identical values.
1205 visible-coordinate comparisons, all GT denominators and conditional AUCs
were independently checked. 295 protected files and 42 evaluator sources are
unchanged. Full suite rerun: **158 passed / 0 failed / 0 errors / 1 skipped**
(159 discovered; real-video E2E requires explicit dataset configuration).
The initial sandbox attempt had 68 Windows strict-realpath permission errors;
unchanged tests/validators passed on the permitted retry outside the sandbox.

Next: propose a bounded image-evidence validity experiment before choosing any
new diagnostic policy. Phase 2 remains IN PROGRESS; peer pitch_005 event
supplement and evidence-based acceptance remain pending. Clipper single-pitch
MP4 + metadata handoff stays deferred until stabilization; no Phase 3.

### Warning design and regression inventory ready (2026-10-06)

The [warning design](phase2_warning_design_20261006.md) and
[machine-readable evaluation plan](evaluation_plans/phase2_warning_design_20261006.json)
fix separate targets for major pose alignment, local joint reliability, selection
breaks and insufficient image evidence. This is **design only**: no new warning
detector, diagnostic thresholds or algorithm changes were included in this
design checkpoint. The later offline measurement experiment is recorded above.
The plan restricts human GT/X/Y to evaluation, keeps source predictions immutable,
and requires exact-frame metrics, per-pitch false warnings, interval coverage,
decision abstention and source binding. Model abstention cannot remove difficult
human-scorable frames from the primary denominator.

Derived inventory: 592 frames, 14 known cases, six-joint human masks and all baseline
screen counts independently reproduced. 295 protected source hashes unchanged;
five canonical GT schemas plus direct MP4 filename/content hashes and the reviewed
manual schema passed. Output: `analysis_results/phase2_warning_design_20261006_01/`.
Existing tests remain historical (147 passed / 0 failed / 1 skipped); not rerun.
The then-planned next step was offline image-motion/geometry measurement, with evidence
and false-warning analysis before selecting a diagnostic policy or implementing
additive warnings. This dataset is known development/regression evidence, not an
independent holdout. Phase 2 acceptance, peer pitch_005 event supplement and the
later small Clipper MP4 + metadata handoff remain pending; no Phase 3.

### pitch_003 saved-data diagnosis completed (2026-10-06)

The [diagnosis report](phase2_pitch003_diagnosis_20261006.md) separates raw model
error, selection, clean/interpolation and overlay behavior without new inference.
Full prepared-clip frames enter MediaPipe; the selector ROI is a post-inference
geometry filter. Every saved frame has one returned pose and selected index 0;
this is not an identity proof. All 3,255 quality-valid clean coordinates equal raw.
The 87–104 displacement is already in raw output, with 76.90px mean error over
190 human-visible points. On the same 189 usable points, raw/clean/visualization
median means are 76.53/76.89/76.32px. Cleaning does not correct this displacement.

Tracking has no warnings in these 18 human major-failure frames: maximum center
step/scale ratio/center acceleration remain below the existing .45/1.6/.45 bounds,
and centers stay inside the ROI. Stored six-joint jump **current-frame** candidates
cover 10/18 frames; this is not an expanded-interval detector. Pose-level unreliable
status does not localize the sustained full-body failure. Batter influence remains
a hypothesis; no model-internal causal evidence or confirmed identity switch exists.

The saved overlay draws raw coordinates at min(visibility,presence) >= .35.
Processed observed/interpolated/missing uses clean's separate .5/.5 gate and
two-frame interpolation limit. Visualization median fields do not drive that overlay.
Output: `analysis_results/phase2_pitch003_diagnostics_20261006_01/`, including
13 original/manual/raw/clean comparisons, three saved-overlay extracts and a timeline.
316 protected-file hashes, 115 exact decoded-video/PNG comparisons, serialization,
schema and numerical checks passed; source/GT/predictions/algorithms remain unchanged.
No full suite rerun: prior 147 passed / 0 failed / 1 skipped remains historical.

Next: design generic sustained-displacement and local-arm reliability warnings with
regression evaluation on known failures and reliable portions of all five clips.
No warning implementation, model change, new thresholds or Phase 3 started.
HSU need not repeat the completed pitch_003 coordinate review. Independent pitch_005
event supplement remains pending. Clipper integration stays after evidence-based
Phase 2 stabilization/acceptance, followed by a small MP4 + metadata handoff test.

### Reviewed coordinate reference and comparison (2026-10-05; documented 2026-10-06)

HSU supplied completion time "2026/10/5 10.14": Taiwan 2026-10-05 10:14,
UTC `2026-10-05T02:14:00Z`. Precision is minutes; 00 seconds are formatting.
New reviewed reference: `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_42/pitch_003/manual_keypoints.json`.
115 frames / 12 joints: 1205 visible, 173 not observable, 2 uncertain, 0 unreviewed.
All frame-level labels/XY match checkpoint 41; only completion status/time and notes
changed. Confidence remains null. The notes-only peer checkpoint 44 retains its
separate in_progress status; canonical events and five-clip GT are unchanged.

Existing raw 2D predictions were measured against 1205 visible reference points:
175 nonvisible points excluded, no new inference. Raw prediction coordinates
are present on all eligible points; this does not mean quality-gated observed
status or correct placement. Throwing elbow mean/median/P95: 27.50/10.55/106.19px.
The existing human major-failure interval 87–104 averages 76.90px versus 11.67px
in 0–86. Right shoulder frame 95 visibility 0.9996 still has 147.37px error;
left wrist frame 112 visibility 0.9927 still has 252.37px error. Confidence alone
is not correctness. No new thresholds or pass score were introduced.

Output: `analysis_results/phase2_manual_coordinate_comparison_20261005_01/`.
See [full 12-joint report](phase2_manual_coordinate_comparison_20261005.md).
Schemas/source hashes and independent recalculation of distances/means passed;
raw predictions, source video, original Tsai return, canonical GT and all history
are unchanged. Private XML remains local/ignored. No full test rerun for these
data/docs changes; prior 147 passed / 0 failed / 1 skipped result remains historical.

Occluded original Tsai estimates remain preserved in the raw return. They may
serve as future explicitly uncertain auxiliary annotations; the current observed
2D coordinate benchmark retains null nonvisible XY. This does not change the schema,
pose/tracking algorithms, confidence gate, smoothing or interpolation. Single-clip
error measurements do not establish generalization or 3D/event accuracy.
The later saved-data diagnosis above identifies where displacement enters and why
existing warnings miss it; next design reliability/regression checks, with no automatic
implementation or Phase 3.
Independent pitch_005 event supplement is still pending.

### Human-label comparison completed (2026-10-04)

The extended comparison reader supports all six joints, track breaks,
occlusion records, event ranges and explicit uncertainty. It compared HSU's
five reviewed annotations against the existing baseline, covering 592 frames.
New output:
`analysis_results/phase2_gt_comparison_20261004_01/ground_truth_comparison_verified.json`.
See the [comparison report](phase2_ground_truth_comparison_20261004.md).

- Human track breaks at `pitch_004` 75–76 and `pitch_005` 54 agree with all
  three model rejection frames, with no other rejection frames.
- Tracking screening covers only 3 of 21 human major-failure frames, leaving
  `pitch_003` 87–104 (18 frames) unscreened. It also screens nine frames outside
  the human major-failure intervals, all for unavailable body-scale geometry.
- A diagnostic union with existing six-joint jump endpoints covers 13/21
  major-failure frames and leaves eight unscreened, while screening 56 frames
  outside that target. This is an audit of existing cues, not a new detector.
- Cross-tabulating human raw-overlay judgments with processed availability,
  72 elbow and 49 wrist frames are human-unreliable yet still `observed`.
  Another 20 elbow and 36 wrist frames are human-not-observable yet observed;
  these cannot be scored as coordinate errors without visible reference data.
- All five human subject judgments are correct-pitcher and no switch is
  confirmed. With zero switch-positive examples, sensitivity remains unmeasured.
- At this qualitative-comparison checkpoint, coordinate error, event error and
  independent reviewer agreement were unmeasured. The later pitch_003 coordinate
  measurement is recorded above; event accuracy and independent agreement remain unmeasured.

The comparison binds source hashes, pitch/pitcher IDs, anatomical joint roles,
frame order and timestamps to the saved predictions. All 126 input artifact
hashes remained unchanged. Formal five-video inference was not rerun; model,
tracking, gate and interpolation/smoothing code were not modified.
Full suite: **147 passed, 0 failed, 1 skipped** (148 discovered). The skipped
case is the opt-in formal-video E2E; existing synthetic-video tests ran.
Log: `analysis_results/phase2_gt_comparison_20261004_01/test_suite.log`.

### Returned manual annotations and event supplement (2026-10-04)

The classmate's `pitch_003_manual_261004.zip` was returned and checked against
the trusted frame manifest: 115 images (0–114), original 510 × 628 dimensions,
12 joints per image, and 1,380 finite in-bounds coordinate records. CVAT XML,
in-memory contract conversion, source video hash, decoded timeline and PNG
hash checks passed. The user supplied reviewer alias **Tsai** and annotation
date **2026-10-04**; a precise completion time was not supplied.

All 1,380 returned joint states are `visible`, with no reviewer notes.
Format validity does not establish that occluded coordinates are observable.
The raw return was not modified by the audit. A partial `manual-keypoints-v1`
reference has now been imported as recorded below; no completed reference or
coordinate-error comparison has been produced. The full human-review viewer
contains all 115 original/manual frame pairs and ten contact sheets under
`analysis_results/manual_pose_return_check_20261004_01/full_review_20261004_01/`.

After viewing that material, HSU supplied a new event-only supplement:
preparation start **13**, peak leg lift **46**, lead foot plant **65**,
approximate release **69**, and follow-through end **99**. These are HSU's
judgments, not events supplied by Tsai. They are saved with the existing
`ground-truth-v1` contract at
`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004/pitch_003/ground_truth.json`.
Schema, source hash and 115 decoded frames were validated. The supplement
remains `in_progress`, with other labels and completed review time null;
the original HSU canonical review and Tsai coordinates remain unchanged.

HSU's overall comment that Tsai's placements in occluded areas are "almost
completely accurate" is preserved as a human review note. It is not converted
into per-frame visibility labels or measured coordinate accuracy; fully
unobservable locations still lack direct reference evidence. No algorithm,
threshold, model weight or Phase 2 acceptance status was changed.

After HSU agreed with the observability rule, a second supplement preserved
the five events and reused only HSU's already explicit, same-source
`not_observable` intervals: right elbow 22–23; right wrist 22–23, 25–29, 83,
87–104; left ankle 65. It is stored at
`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`.
Previously judged AI overlay errors were not turned into judgments of Tsai's
placements. Both earlier reviews and the original XML remain unchanged.
Joint-specific visibility still needs clarification where the earlier notes
only described a whole hand or arm. HSU subsequently confirmed left elbow
46–48 is fully unobservable and left wrist 46–48 is judgeable; this statement
is preserved in the second supplement's notes, without treating judgeability
as confirmation of Tsai's coordinate accuracy. HSU also confirmed both left
elbow and left wrist are completely unobservable in frames 33–44; this is
preserved in the same supplement's notes. HSU then confirmed only the left
elbow is visible in frames 66–72, while the left wrist is unobservable. This
is also preserved as visibility evidence, not coordinate-placement agreement.
After viewing original/manual comparisons, HSU confirmed the left-wrist
placements at frames 46–48 and left-elbow placements at 66–72 are correct.
HSU also confirmed both left elbow and left wrist are visible and correctly
placed at frames 64–65. This batch establishes 14 visible placements and 63
unobservable joint-frames. Placement agreement is visual, not a measured
zero-pixel error. Other joint-frames remain unverified in this partial HSU
reference; no complete human coordinate reference is finalized.

This batch was also saved as a local `manual-keypoints-v1` draft at
`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_partial_draft_20261004_01.json`.
It contains 14 visible placements copied from Tsai's previously verified
display records, 63 `not_observable` points with null X/Y, and 1,303
`unreviewed` points with null X/Y. All 115 original-image hashes, schema,
source binding and event preservation checks passed. Tsai placed the
coordinates; HSU supplied the visibility and placement review. The draft
remains `in_progress`, with null confidence and completed-review time.

The returned ZIP/XML was temporarily unavailable during draft preparation.
The user reattached the ZIP; both its SHA-256 and the XML SHA-256 match the
original audit exactly. The original ZIP/XML and unmodified CVAT state claims
are now preserved locally under
`analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`.

The existing CVAT converter, manifest validator, source-timeline verifier and
manual-keypoint contract checks were used to import the partial HSU reference:
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261004_01/pitch_003/manual_keypoints.json`.
It remains `in_progress`: 14 `visible`, 63 `not_observable`, and 1,303
`unreviewed`. All 14 retained X/Y pairs match Tsai's exact original values.
The source video, all 115 decoded PNG hashes and timestamps, and all 1,380
original coordinates against the reviewed display were rechecked. Original
source, prediction and canonical annotation hashes remained unchanged.
See `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_import_check_20261004_01.json`.
The exact original XML is also retained beside the partial reference and
ignored by Git because it contains account details. The earlier draft is
preserved as a preparation checkpoint. No inference, coordinate comparison
or model training ran; full manual-coordinate review remains incomplete.

After that import checkpoint, HSU confirmed the right elbow and right wrist
at frames 33–35 and 36–44 are clearly visible and correctly placed. HSU then
confirmed the placements at 45–53 and 54–63; those joints already have explicit
same-source visibility observations. These 62 additional points and their
observations are saved in the existing event/visibility
supplement's notes. The coordinate checkpoint after those initial reviews is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261004_07/pitch_003/manual_keypoints.json`:
**96 visible, 84 not observable, 1,200 unreviewed**, still `in_progress`.
All new visible X/Y pairs match the preserved original XML; the earlier
checkpoints, canonical annotations and raw predictions retained their hashes.
Check report:
`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261004_07.json`.
HSU then judged the right-elbow/wrist placements at 64–72 correct. That
opinion is saved in the supplement's notes. In the separate raw-image
clarification, HSU confirmed both joints at 70–71 are unobservable. Those
four points now have null X/Y; the other 14 newly confirmed points at
64–69 and 72 retain Tsai's coordinates. The more specific visibility
observation is preserved independently of the old canonical blanket interval
and of the earlier placement opinion. No hidden coordinate was inferred.
HSU subsequently confirmed right wrist 73–78 is visible and correctly placed,
right elbow 73–78 is unobservable, and both joints at 79–82 are unobservable.
These six visible points and 14 unobservable points are now included in the
latest checkpoint. HSU then confirmed right wrist 84–86 is occluded, adding
three unobservable points, and right elbow 83–92 is visible. The placement
accuracy of those ten elbow points is still pending; they retain unreviewed
status and null X/Y. Previously confirmed unobservable wrists at 83 and 87–104
retain null X/Y.

### Saved manual review checkpoint (2026-10-05)

HSU's last short answer, "沒有", is preserved in the new supplementary file
`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_01/pitch_003/ground_truth.json`.
It may mean no displacement or disagreement with all placements; the exact
meaning and affected frames remain unconfirmed. None of the ten right-elbow
points at 83–92 was marked correct or incorrect from this answer.
The previous supplement and all seven coordinate checkpoints remain unchanged.

The saved overnight coordinate reference had **96 visible, 84 not observable,
1,200 unreviewed**. Per-joint counts, source checks, saved-review history and the
next review entry are in the [manual review checkpoint](phase2_manual_review_checkpoint_20261005.md).
An offline helper provides ten enlarged original/Tsai pairs for the pending
elbow review; it neither supplies human decisions nor writes ground truth.
No formal-video inference, coordinate-error comparison, algorithm change,
Phase 2 acceptance or Phase 3 work was performed in this cleanup.
All seven coordinate checkpoints and three supplementary GT files passed
schema/source checks. The 126 baseline/media hashes and 232 historical protected
hash comparisons were unchanged. The full suite passed in the normal host
execution context: **147 passed, 0 failed, 1 skipped** (148 tests). The opt-in
formal-video E2E stayed skipped; synthetic-video MediaPipe tests ran.
The first restricted-context attempt was blocked by temporary-directory access,
with its log preserved; no code was changed to make the rerun pass.
Verified log: `analysis_results/manual_pose_return_check_20261004_01/autonomous_cleanup_20261005_01/test_suite_verified.log`.

HSU subsequently clarified the ten right-elbow placements at 83–92 with
"位置正確". Their visibility was already explicitly confirmed. The new
coordinate checkpoint is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_01/pitch_003/manual_keypoints.json`:
**106 visible, 84 not observable, 1,190 unreviewed**, still `in_progress`.
The exact original Tsai X/Y pairs were retained; all previous checkpoints and
protected source/prediction hashes remained unchanged. The clarification is
preserved in
`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_02/pitch_003/ground_truth.json`.
The previous ambiguous answer remains in the review history but is no longer
an open placement question for 83–92. The next review targets are right elbow
93–104; unobservable right wrists in this range are not reconsidered.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_01.json`.

HSU then explicitly confirmed right elbow 93–96 is visible and correctly
placed ("看的到且正確"). Four more original Tsai coordinate pairs are saved in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_02/pitch_003/manual_keypoints.json`:
**110 visible, 84 not observable, 1,186 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_03/pitch_003/ground_truth.json`;
source/schema checks and protected-history hashes passed. The next four frames
to review are right elbow 97–100. No other joints or frames were changed.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_02.json`.

HSU confirmed right elbow 97–100 is hidden ("都看不到被遮住了"). These four
points are now `not_observable`, with null X/Y, in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_03/pitch_003/manual_keypoints.json`:
**110 visible, 88 not observable, 1,182 unreviewed**, still `in_progress`.
The new supplemental GT is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_04/pitch_003/ground_truth.json`.
No occluder was inferred, no right-wrist records were changed, and the earlier
canonical observations remain preserved. Source/schema checks and protected
hashes passed. The next review targets are right elbow 101–104.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_03.json`.

HSU confirmed right elbow 101–104 is not visible ("看不到"). These four
points are `not_observable` with null X/Y in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_04/pitch_003/manual_keypoints.json`:
**110 visible, 92 not observable, 1,178 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_05/pitch_003/ground_truth.json`.
No cause of invisibility was inferred and no other joint records were changed.
Source/schema validation and protected hashes passed. The next review is right
elbow 105–108, followed by 109–114.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_04.json`.

HSU replied "正確" about right-elbow placements at 105–108. This placement
opinion is saved in `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_06/pitch_003/ground_truth.json`.
Direct source visibility remains to be clarified; the four manual points stay
unreviewed with null X/Y and the latest counts remain 110/92/1,178.
The earlier full-clip visibility principle is preserved separately; it is not
used to substitute for this finer review's direct visibility answer.

HSU then explicitly answered "可以" to direct right-elbow visibility at
105–108. Together with the preceding placement confirmation, four original
Tsai X/Y pairs were added in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_05/pitch_003/manual_keypoints.json`:
**114 visible, 92 not observable, 1,174 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_07/pitch_003/ground_truth.json`.
Source/schema checks passed and protected source/prediction/history hashes
remain unchanged. The next four-frame review is right elbow 109–112.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_05.json`.

HSU confirmed right elbow 109–112 is directly visible and correctly placed
("看的見且正確"). Four original coordinate pairs were added in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_06/pitch_003/manual_keypoints.json`:
**118 visible, 92 not observable, 1,170 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_08/pitch_003/ground_truth.json`.
Source/schema checks and protected hashes passed; no other points were changed.
The next review targets are right elbow 113–114.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_06.json`.

HSU confirmed right elbow 113–114 is directly visible and correctly placed
("正確可以"). Two original coordinate pairs were added in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_07/pitch_003/manual_keypoints.json`:
**120 visible, 92 not observable, 1,168 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_09/pitch_003/ground_truth.json`.
Source/schema checks and protected hashes passed. Right elbow 33–114 is now
reviewed, including explicitly unobservable intervals. The remaining 31
right-elbow points are frames 0–21 and 24–32; 22–23 was already unobservable.
Resume at 0–3 rather than rechecking finished ranges. Other joints remain
incomplete and Phase 2 is not accepted.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_07.json`.

HSU answered "正確" to the combined direct-visibility/correct-placement
question for right elbow 0–3. These four original coordinate pairs were added in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_08/pitch_003/manual_keypoints.json`:
**124 visible, 92 not observable, 1,164 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_10/pitch_003/ground_truth.json`.
Source/schema checks and protected hashes passed. The remaining right-elbow
review ranges are 4–21 and 24–32; resume at 4–7 without revisiting completed frames.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_08.json`.

HSU answered "正確" to the combined direct-visibility/correct-placement
question for right elbow 4–7. Four original coordinate pairs were added in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_09/pitch_003/manual_keypoints.json`:
**128 visible, 92 not observable, 1,160 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_11/pitch_003/ground_truth.json`.
Source/schema checks and protected hashes passed. No other joint records changed;
resume at right elbow 8–11.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_09.json`.

HSU confirmed right elbow 8–11 with "正確你一次給我多點": the first part
affirms the combined direct-visibility/placement question; the second requests
larger future batches. Four original coordinate pairs were added in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_10/pitch_003/manual_keypoints.json`:
**132 visible, 92 not observable, 1,156 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_12/pitch_003/ground_truth.json`.
Source/schema checks and protected hashes passed. Present all remaining 19
right-elbow frames, 12–21 and 24–32, as one review batch; no answers for that
batch have been supplied yet. Already-unobservable 22–23 stays unchanged.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_10.json`.

HSU answered "全部都正確" for the remaining 19 right-elbow placements at
12–21 and 24–32. Same-source human visibility evidence exists separately:
25–29 explicitly visible, and other frames covered by HSU's full-review
"unmentioned portions are clear" principle and joint-specific observable intervals.
Combining that visibility evidence with the new Tsai placement judgment,
19 original coordinate pairs were saved in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_11/pitch_003/manual_keypoints.json`:
**151 visible, 92 not observable, 1,137 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_13/pitch_003/ground_truth.json`.
Right elbow is complete for all 115 frames: **93 visible, 22 not observable,
0 unreviewed**. Other joints and full-clip manual acceptance remain incomplete.
Source/schema checks and protected hashes passed. Next review right wrist,
whose remaining 36 frames are 0–21, 24, 30–32 and 105–114; start with 0–15 as
one larger batch. No coordinate-error comparison or model changes were performed.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_11.json`.

HSU answered "位置正確但是看不到" for right wrist 0–15. The inferred-placement
opinion is retained in notes; these 16 points are `not_observable` with null
X/Y, rather than visible coordinate truth. No cause of invisibility was inferred.
The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_12/pitch_003/manual_keypoints.json`:
**151 visible, 108 not observable, 1,121 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_14/pitch_003/ground_truth.json`.
Right wrist now has **44 visible, 51 not observable, 20 unreviewed**;
review the remaining 16–21, 24, 30–32 and 105–114 together. Right elbow remains
complete at 93 visible / 22 not observable. Source/schema checks and protected
hashes passed; previous annotations and raw predictions remain unchanged.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_12.json`.

HSU answered "16-21位置正確但看不到，其他都看的到且位置正確" for the
displayed remaining 20 right-wrist frames (16–21, 24, 30–32, 105–114).
Six points at 16–21 are `not_observable` with null X/Y; the inferred-placement
opinion is retained without assigning an invisibility cause. The other 14
displayed points are visible and correctly placed, retaining Tsai's original X/Y.
The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_13/pitch_003/manual_keypoints.json`:
**165 visible, 114 not observable, 1,101 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_15/pitch_003/ground_truth.json`.
Right wrist is complete for all 115 frames: **58 visible, 57 not observable,
0 unreviewed**. Right elbow remains complete at 93 visible / 22 not observable.
Source/schema checks and protected hashes passed. Next review left elbow and
left wrist together at 0–15; no human answers for that batch have been supplied.
Full-clip coordinate review and error comparison remain incomplete.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_13.json`.

HSU reviewed left elbow and wrist at 0–15, answering
"看不到左腕但是位置正確，左肘位置正確". The 16 left-wrist points were
saved as `not_observable` with null X/Y; their inferred-placement opinion is
retained without assigning an invisibility cause. Left-elbow placement was
confirmed first, while direct visibility remained pending in checkpoint
`HSU_TSAI_RETURN_20261005_14` (165 visible / 130 not observable / 1,085 unreviewed).
HSU then explicitly answered "全部看得見" to the left-elbow visibility
question for the same 0–15 frames. Those 16 elbow points now retain Tsai's
original visible X/Y in the latest partial reference
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_15/pitch_003/manual_keypoints.json`:
**181 visible, 130 not observable, 1,069 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_17/pitch_003/ground_truth.json`;
the preceding `_20261005_16` supplement and all previous checkpoints are preserved.
Left elbow now has 25 visible / 15 not observable / 75 unreviewed; left wrist
has 5 visible / 35 not observable / 75 unreviewed. Next review both at 16–32,
17 frames / 34 points; that batch still has no human judgments.
Source/schema checks and protected hashes passed. No coordinate-error
comparison, inference or model changes were performed.
Checks: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_14.json`
and `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_15.json`.

HSU answered "全部都被遮住但位置正確" for the displayed left elbow and
left wrist at 16–32. All 34 points are `not_observable` with null X/Y;
the inferred-placement opinion is retained separately from visible truth.
Occlusion is explicitly human-confirmed, but no occluding object was specified.
The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_16/pitch_003/manual_keypoints.json`:
**181 visible, 164 not observable, 1,035 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_18/pitch_003/ground_truth.json`.
Left elbow now has 25 visible / 32 not observable / 58 unreviewed; left wrist
has 5 visible / 52 not observable / 58 unreviewed. Next review both at
45 and 49–63 (16 frames / 32 points); already reviewed 33–44 and 46–48 are skipped.
Source/schema checks and protected hashes passed. Previous annotations and raw
predictions remain unchanged; no coordinate-error comparison or model changes.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_16.json`.

HSU answered "皆可看到位置正確" for the displayed left elbow and left wrist
at 45 and 49–63. These 32 points are visible and correctly placed, retaining
Tsai's original X/Y without claiming zero pixel error. The judgment applies
only to the displayed batch; previously reviewed 46–48 and 64–72 remain unchanged.
The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_17/pitch_003/manual_keypoints.json`:
**213 visible, 164 not observable, 1,003 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_19/pitch_003/ground_truth.json`.
Left elbow now has 41 visible / 32 not observable / 42 unreviewed; left wrist
has 21 visible / 52 not observable / 42 unreviewed. Both are reviewed through
0–72; next review both at 73–88 (16 frames / 32 points), which still lack human judgments.
Source/schema checks and protected hashes passed. Previous annotations and raw
predictions remain unchanged; no coordinate-error comparison, inference or model changes.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_17.json`.

HSU reviewed left elbow and wrist at 73–88, first answering
"85-86左腕看不清之外其他都正確", then explicitly confirming
"其餘全部看得見" for all remaining points in that batch. Left elbow 73–88
and left wrist 73–84 / 87–88 (30 points) are visible and correctly placed,
retaining Tsai's original X/Y. Left wrist 85–86 (two points) is `uncertain`
with null X/Y: lack of clarity was not forced into complete invisibility
or an exact coordinate, and no cause was inferred.
The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_18/pitch_003/manual_keypoints.json`:
**243 visible, 164 not observable, 2 uncertain, 971 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_20/pitch_003/ground_truth.json`.
Left elbow has 57 visible / 32 not observable / 26 unreviewed; left wrist
has 35 visible / 52 not observable / 2 uncertain / 26 unreviewed.
Both have been reviewed through 0–88, retaining the two uncertain judgments.
Next review both at 89–104 (16 frames / 32 points), which lack human judgments.
Source/schema checks and protected hashes passed. Existing schema and raw
predictions are unchanged; only the local transcription helper was extended
to store explicit `uncertain` answers. No inference, training or pose/tracking changes.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_18.json`.

HSU viewed the 89–104 original/Tsai comparisons directly in this conversation,
first answering "皆清楚可見" and then explicitly confirming "全部位置正確"
for the left-elbow and left-wrist placements. These 32 points retain Tsai's
original visible X/Y. Left wrist 85–86 remains uncertain with null X/Y.
The partial reference at this checkpoint is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_19/pitch_003/manual_keypoints.json`:
**275 visible, 164 not observable, 2 uncertain, 939 unreviewed**, still `in_progress`.
Its supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_21/pitch_003/ground_truth.json`.
Left elbow has 73 visible / 32 not observable / 10 unreviewed; left wrist
has 51 visible / 52 not observable / 2 uncertain / 10 unreviewed.
Both have been reviewed through 0–104. The final left-arm batch is 105–114
(10 frames / 20 points), which still lacks human judgments; display its
comparisons directly in the conversation for the user's phone review.
Source/schema checks and protected hashes passed. Previous annotations and raw
predictions remain unchanged; no inference, coordinate-error comparison or model changes.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_19.json`.

HSU answered "正確" to the combined question asking whether LEFT_ELBOW
(cyan 3) and LEFT_WRIST (cyan 5) at 105–114 are all clearly visible and correctly
placed. These 20 points retain Tsai's original X/Y in the latest partial reference,
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_20/pitch_003/manual_keypoints.json`:
**295 visible, 164 not observable, 2 uncertain, 919 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_22/pitch_003/ground_truth.json`.
Left elbow has 83 visible / 32 not observable / 0 unreviewed; left wrist has
61 visible / 52 not observable / 2 uncertain / 0 unreviewed. Right elbow remains
93 visible / 22 not observable and right wrist 58 visible / 57 not observable.
All four elbow/wrist joints have been reviewed across 0–114; left wrist 85–86
remains uncertain with null X/Y. The full 12-joint reference remains in progress.
Next review only both shoulders at 0–15 (32 unreviewed points): cyan 1 is LEFT_SHOULDER
and red 2 is RIGHT_SHOULDER. The two comparisons are
`analysis_results/shoulder_review_20261005_01/shoulders_0000_0007.png` and
`analysis_results/shoulder_review_20261005_01/shoulders_0008_0015.png`.
This annotation checkpoint uses schema/source-hash checks. The previously recorded
full suite result, 147 passed / 0 failed / 1 skipped, is historical and was not rerun
for this batch. Phase 2 remains in progress.


HSU reviewed both shoulders at 0–15 in the two inline original/Tsai comparisons
and answered "都正確清楚" to the combined visibility/placement question. These
32 points retain exact original Tsai X/Y in the latest partial reference,
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_21/pitch_003/manual_keypoints.json`:
**327 visible, 164 not observable, 2 uncertain, 887 unreviewed**, still `in_progress`.
The new supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_23/pitch_003/ground_truth.json`;
it appends only the human response/context to notes. Each shoulder has 16 visible
and 99 unreviewed points. Left wrist 85–86 remains uncertain with null X/Y.
Previous checkpoints, canonical GT, source files and predictions are unchanged;
schema/source-hash validation passed and no inference or full test rerun occurred.
Next review only both shoulders at 16–31 (32 unreviewed points), cyan 1 left and
red 2 right, using `analysis_results/shoulder_review_20261005_02/`.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_21.json`.
No subagents were used for this batch. Phase 2 remains in progress.

HSU then answered "正確" to the combined visibility/placement question for
both shoulders at 16–31 after the original/Tsai images were embedded directly
in the final response. These 32 points retain original Tsai X/Y in
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_22/pitch_003/manual_keypoints.json`:
**359 visible, 164 not observable, 2 uncertain, 855 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_24/pitch_003/ground_truth.json`;
only notes were appended. Each shoulder now has 32 visible / 83 unreviewed.
Schema/source checks passed; prior checkpoints, canonical GT, source files,
predictions and left-wrist uncertainty at 85–86 are unchanged.
Next review only both shoulders at 32–47 (32 unreviewed points) using
`analysis_results/shoulder_review_20261005_03/`, cyan 1 left / red 2 right.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_22.json`.
No subagents, model inference or full test rerun were used for this batch.

HSU answered "都正確" to the combined visibility/placement question for both
shoulders at 32–47, after reviewing the original/Tsai images in the final response.
The new partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_23/pitch_003/manual_keypoints.json`:
**391 visible, 164 not observable, 2 uncertain, 823 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_25/pitch_003/ground_truth.json`;
only notes were appended. Each shoulder has 48 visible / 67 unreviewed.
The 32 new points retain exact original Tsai X/Y. Schema/source checks passed;
old checkpoints, canonical GT, model predictions and left-wrist uncertainty at
85–86 are unchanged. Next review only both shoulders at 48–63 using
`analysis_results/shoulder_review_20261005_04/`, cyan 1 left / red 2 right.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_23.json`.
No subagents, model inference or full test rerun were used.

HSU answered "正確" to the combined visibility/placement question for both
shoulders at 48–63 after reviewing the original/Tsai images in the final response.
The new partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_24/pitch_003/manual_keypoints.json`:
**423 visible, 164 not observable, 2 uncertain, 791 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_26/pitch_003/ground_truth.json`;
only notes were appended. Each shoulder has 64 visible / 51 unreviewed.
The 32 new points retain exact original Tsai X/Y; schema/source checks passed.
Historical checkpoints, canonical GT, source files, predictions and left-wrist
uncertainty at 85–86 are unchanged. Next review only both shoulders at 64–79
using `analysis_results/shoulder_review_20261005_05/`, cyan 1 left / red 2 right.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_24.json`.
No subagents, model inference or full test rerun were used.

HSU reported "70-78誘姦被遮住其他沒問題" for the shoulder 64–79 batch and
explicitly clarified "對，是右肩" when asked which side was occluded. The new
partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_25/pitch_003/manual_keypoints.json`:
**446 visible, 173 not observable, 2 uncertain, 759 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_27/pitch_003/ground_truth.json`;
only notes were appended. RIGHT_SHOULDER 70–78 (9 points) is not observable with
null X/Y; the occluder and exact hidden position were not supplied. The other
23 points in this batch retain original Tsai X/Y. LEFT_SHOULDER has 80 visible /
35 unreviewed, RIGHT_SHOULDER 71 visible / 9 not observable / 35 unreviewed.
Schema/source checks passed; historical records, source files, canonical GT,
predictions and left-wrist uncertainty at 85–86 are unchanged. Next review only
both shoulders at 80–95 using `analysis_results/shoulder_review_20261005_06/`.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_25.json`.
No subagents, model inference or full test rerun were used.

HSU answered "都沒問替" to the combined question whether both shoulders in
80–95 are clearly visible and correctly placed, after the original/Tsai sheets
were embedded in the conversation. The answer is recorded verbatim and interpreted
as "都沒問題" in that question context. The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_26/pitch_003/manual_keypoints.json`:
**478 visible, 173 not observable, 2 uncertain, 727 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_28/pitch_003/ground_truth.json`;
only notes were appended. The 32 newly confirmed points retain original Tsai X/Y.
LEFT_SHOULDER has 96 visible / 19 unreviewed; RIGHT_SHOULDER has 87 visible /
9 not observable / 19 unreviewed. Right-shoulder 70–78 occlusion and left-wrist
85–86 uncertainty are unchanged. Schema/source checks passed; historical records,
source files, canonical GT and predictions are unchanged. Next review only both
shoulders at 96–114, the final shoulder batch, using
`analysis_results/shoulder_review_20261005_07/` (38 unreviewed points).
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_26.json`.
No subagents, model inference or full test rerun were used.

HSU answered "正確" to the combined question whether both shoulders in 96–114
are clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_27/pitch_003/manual_keypoints.json`:
**516 visible, 173 not observable, 2 uncertain, 689 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_29/pitch_003/ground_truth.json`;
only notes were appended. The 38 newly confirmed points retain original Tsai X/Y.
Both shoulders have now been reviewed for all 115 frames: LEFT_SHOULDER has
115 visible; RIGHT_SHOULDER has 106 visible / 9 not observable (70–78).
Both shoulders, elbows and wrists are complete at the joint-frame review level;
the 12-joint reference is incomplete. Left-wrist 85–86 uncertainty is preserved.
Schema/source checks passed; historical records, source files, canonical GT and
predictions are unchanged. Next review only both hips at 0–15 using
`analysis_results/hip_review_20261005_01/` (32 unreviewed points). No hip visibility
or placement judgments were assigned while preparing the sheets.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_27.json`.
No subagents, model inference or full test rerun were used. Tsai placed the original
coordinates on 2026-10-04; HSU personally reviewed the images and Codex transcribed
the answers. Phase 2 remains IN PROGRESS; no Phase 3 work was started.

HSU answered "正確" to the combined question whether both hips in 0–15 are
clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_28/pitch_003/manual_keypoints.json`:
**548 visible, 173 not observable, 2 uncertain, 657 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_30/pitch_003/ground_truth.json`;
only notes were appended. The 32 newly confirmed hip points retain original Tsai
X/Y; each hip has 16 visible / 99 unreviewed. Historical references, canonical
GT, predictions, source files, shoulder occlusion and wrist uncertainty are
unchanged. Schema and source checks passed. Next review only both hips at 16–31
using `analysis_results/hip_review_20261005_02/` (32 unreviewed points).
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_28.json`.
No subagents, model inference, comparison, training or full test rerun were used.
Phase 2 remains IN PROGRESS; the original shoulder checkpoint backup is GitHub
commit `457d11aaf1e90843860652df82cea111942c0132`. This hip batch is saved locally.

HSU answered "可以" to the combined question whether both hips in 16–31 are
clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_29/pitch_003/manual_keypoints.json`:
**580 visible, 173 not observable, 2 uncertain, 625 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_31/pitch_003/ground_truth.json`;
only notes were appended. The 32 new points retain original Tsai X/Y; each hip
has 32 visible / 83 unreviewed. Schema/source checks passed and protected sources,
predictions, canonical GT and historical references are unchanged. Next review
only both hips at 32–47 using `analysis_results/hip_review_20261005_03/`
(32 unreviewed points). HSU's subsequent "繼續" requests the next display batch;
it does not assign labels to the unreviewed points.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_29.json`.
No subagents, model inference, comparison, training or full test rerun were used.
This hip batch is saved locally; Phase 2 remains IN PROGRESS.

HSU answered "正確" to the combined question whether both hips in 32–47 are
clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_30/pitch_003/manual_keypoints.json`:
**612 visible, 173 not observable, 2 uncertain, 593 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_32/pitch_003/ground_truth.json`;
only notes were appended. The 32 new points retain original Tsai X/Y; each hip
has 48 visible / 67 unreviewed. Schema/source checks passed and protected sources,
predictions, canonical GT and historical references are unchanged. Next review
only both hips at 48–63 using `analysis_results/hip_review_20261005_04/`
(32 unreviewed points); no labels were assigned to those points during display
preparation. Check:
`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_30.json`.
No subagents, model inference, comparison, training or full test rerun were used.
This hip batch is saved locally; Phase 2 remains IN PROGRESS.

HSU answered "可以" to the combined question whether both hips in 48–63 are
clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The latest partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_31/pitch_003/manual_keypoints.json`:
**644 visible, 173 not observable, 2 uncertain, 561 unreviewed**, still `in_progress`.
The latest supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_33/pitch_003/ground_truth.json`;
only notes were appended. The 32 new points retain original Tsai X/Y; each hip
has 64 visible / 51 unreviewed. Schema/source checks passed and protected sources,
predictions, canonical GT and historical references are unchanged. Next review
only both hips at 64–79 using `analysis_results/hip_review_20261005_05/`
(32 unreviewed points); no labels were assigned during display preparation.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_31.json`.
No subagents, model inference, comparison, training or full test rerun were used.
This hip batch is saved locally; Phase 2 remains IN PROGRESS.

HSU answered "都正確" to the combined question whether both hips in 64–79 are
clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The partial reference saved at that point is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_32/pitch_003/manual_keypoints.json`:
**676 visible, 173 not observable, 2 uncertain, 529 unreviewed**, still `in_progress`.
The supplement saved at that point is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_34/pitch_003/ground_truth.json`;
only notes were appended. The 32 new points retain original Tsai X/Y; each hip
has 80 visible / 35 unreviewed. Schema/source checks passed and protected sources,
predictions, canonical GT and historical references are unchanged. Next review
only both hips at 80–95 using `analysis_results/hip_review_20261005_06/`
(32 unreviewed points); no labels were assigned during display preparation.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_32.json`.
No subagents, model inference, comparison, training or full test rerun were used.
This hip batch is saved locally; Phase 2 remains IN PROGRESS.

HSU answered "正確" to the combined question whether both hips in 80–95 are
clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The partial reference saved at that point is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_33/pitch_003/manual_keypoints.json`:
**708 visible, 173 not observable, 2 uncertain, 497 unreviewed**, still `in_progress`.
The supplement saved at that point is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_35/pitch_003/ground_truth.json`;
only notes were appended. The 32 new points retain original Tsai X/Y; each hip
has 96 visible / 19 unreviewed. Schema/source checks passed and protected sources,
predictions, canonical GT and historical references are unchanged. Next review
only the final hips at 96–114 using `analysis_results/hip_review_20261005_07/`
(38 unreviewed points); no labels were assigned during display preparation.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_33.json`.
No subagents, model inference, comparison, training or full test rerun were used.
This hip batch is saved locally; Phase 2 remains IN PROGRESS.

HSU answered "都正確" to the combined question whether both hips in 96–114 are
clearly visible and correctly placed, after both original/Tsai sheets were
embedded in the conversation. The partial reference saved at that point is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_34/pitch_003/manual_keypoints.json`:
**746 visible, 173 not observable, 2 uncertain, 459 unreviewed**, still `in_progress`.
The supplement saved at that point is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_36/pitch_003/ground_truth.json`;
only notes were appended. The 38 new points retain original Tsai X/Y. Both hips
are now reviewed for all 115 frames, with 115 visible and correctly placed points
on each side. Both shoulders, elbows, wrists and hips are reviewed throughout.
The four knee/ankle joints still require review; left ankle frame 65 retains its
existing not-observable label. Whole-reference completion time and confidence
remain null. Protected sources, predictions, canonical GT and history are unchanged.
At HSU's request, review both knees and both ankles together in each batch.
Next review the four leg joints at 0–15 using `analysis_results/leg_review_20261005_01/`
(64 unreviewed points). Cyan 9/11 are left knee/ankle; red 10/12 are right
knee/ankle. The earlier knee-only helper is preserved. This display/workflow
change assigned no human labels and changed no reference counts or coordinates.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_34.json`.
The seven hip checkpoints and seven peer supplements are saved with human
attribution for the authorized GitHub checkpoint. Private XML and local media
remain excluded. No subagents, model inference, comparison, training or full
test rerun were used; Phase 2 remains IN PROGRESS.

HSU answered "正確" to the combined question whether all four knee/ankle points
in 0–15 are clearly visible and correctly placed, after both original/Tsai
sheets were embedded in the conversation. The partial reference saved at that point is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_35/pitch_003/manual_keypoints.json`:
**810 visible, 173 not observable, 2 uncertain, 395 unreviewed**, still `in_progress`.
The supplement saved at that point is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_37/pitch_003/ground_truth.json`;
only notes were appended. All 64 new points retain original Tsai X/Y. Both knees
and right ankle have 16 visible / 99 unreviewed points; left ankle has 16 visible,
1 existing not-observable point (65), and 98 unreviewed. Schema/source checks
passed; protected sources, predictions, canonical GT and history are unchanged.
Next review all four knee/ankle joints at 16–31 using `analysis_results/leg_review_20261005_02/`
(64 unreviewed points). No labels were assigned during display preparation.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_35.json`.
This batch is saved locally. No subagents, model inference, comparison, training
or full test rerun were used; Phase 2 remains IN PROGRESS.

HSU answered "可以" to the combined visibility/placement question for all four
knee/ankle points in 16–31 after the original/Tsai sheets were shown. That batch's
reference is `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_36/pitch_003/manual_keypoints.json`:
**874 visible, 173 not observable, 2 uncertain, 331 unreviewed**, still `in_progress`.
That batch's notes-only supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_38/pitch_003/ground_truth.json`.
All 64 new points retain original Tsai X/Y. Both knees and right ankle have
32 visible / 83 unreviewed; left ankle has 32 visible / 1 not observable / 82 unreviewed.
Schema/source checks passed; history, canonical GT, predictions and existing
hidden/uncertain labels are unchanged. Next combined review is 32–47 at
`analysis_results/leg_review_20261005_03/` (64 unreviewed points).
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_36.json`.
This batch is saved locally. No subagents, inference, comparison, training or full
test rerun; Phase 2 remains IN PROGRESS.

HSU answered "正確" to the combined visibility/placement question for all four
knee/ankle points in 32–47 after the original/Tsai sheets were shown. That batch's
reference is `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_37/pitch_003/manual_keypoints.json`:
**938 visible, 173 not observable, 2 uncertain, 267 unreviewed**, still `in_progress`.
That batch's notes-only supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_39/pitch_003/ground_truth.json`.
All 64 new points retain original Tsai X/Y. Both knees and right ankle have
48 visible / 67 unreviewed; left ankle has 48 visible / 1 not observable / 66 unreviewed.
Schema/source checks passed; history, canonical GT, predictions and existing
hidden/uncertain labels are unchanged. Next combined review is 48–63 at
`analysis_results/leg_review_20261005_04/` (64 unreviewed points).
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_37.json`.
This batch is saved locally. No subagents, inference, comparison, training or full
test rerun; Phase 2 remains IN PROGRESS.

HSU answered "正確" to the combined visibility/placement question for all four
knee/ankle points in 48–63 after reviewing the original/Tsai sheets. That batch's
reference is `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_38/pitch_003/manual_keypoints.json`:
**1002 visible, 173 not observable, 2 uncertain, 203 unreviewed**, still `in_progress`.
That batch's notes-only supplement is `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_40/pitch_003/ground_truth.json`.
All 64 new points retain exact original Tsai X/Y. Both knees and right ankle have
64 visible / 51 unreviewed; left ankle has 64 visible / 1 not observable / 50 unreviewed.
Schema/source checks passed; history, canonical GT, predictions and existing
hidden/uncertain labels are unchanged. Next combined review is 64–79 at
`analysis_results/leg_review_20261005_05/`: 64 displayed points, 63 unreviewed.
Frame 65 left ankle is already not observable with null X/Y; preserve it and exclude
it from the next question. Original/Tsai source pixels match in all 32 panels.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_38.json`.
Saved locally; no subagents, inference, comparison, training or full test rerun.
Phase 2 remains IN PROGRESS.

HSU answered "都可以" to the combined visibility/placement question for knees
and ankles in 64–79. The question explicitly excluded the previously reviewed
left ankle at frame 65; only the other 63 unreviewed points were saved as visible
and correctly placed using original Tsai X/Y. Left ankle 65 remains not observable
with null coordinates. That batch's partial reference is
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_39/pitch_003/manual_keypoints.json`:
**1065 visible, 173 not observable, 2 uncertain, 140 unreviewed**, still `in_progress`.
That batch's notes-only supplement: `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_41/pitch_003/ground_truth.json`.
Both knees and right ankle: 80 visible / 35 unreviewed; left ankle:
79 visible / 1 not observable / 35 unreviewed. Schema/source checks passed;
history, canonical GT, predictions, confidence and completion timestamps unchanged.
Next combined review: 80–95 in `analysis_results/leg_review_20261005_06/`,
64 unreviewed points. Both sheets viewed for layout; all 32 panels match source pixels.
Check: `analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_39.json`.
Saved locally; no subagents, inference, comparison, training or full test rerun.
Phase 2 remains IN PROGRESS.

HSU answered "正確" to the combined visibility/placement question for all four
knee/ankle points in 80–95 after reviewing both original/Tsai sheets. That batch's
partial reference is `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_40/pitch_003/manual_keypoints.json`:
**1129 visible, 173 not observable, 2 uncertain, 76 unreviewed**, still `in_progress`.
That batch's notes-only supplement: `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_42/pitch_003/ground_truth.json`.
All 64 new points retain original Tsai X/Y. Both knees and right ankle:
96 visible / 19 unreviewed; left ankle: 95 visible / 1 not observable / 19 unreviewed.
Frame 65 left ankle remains not observable. Schema/source checks passed; history,
canonical GT, raw predictions and hidden/uncertain points unchanged. Confidence
and completion timestamps remain null. Final combined batch: 96–114 in
`analysis_results/leg_review_20261005_07/`, 19 frames / 76 unreviewed points.
Both sheets viewed for layout; all 38 panels preserve source pixels. No human
labels inferred during preparation. Check:
`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_40.json`.
Saved locally; no subagents, inference, comparison, training or full test rerun.
Phase 2 remains IN PROGRESS.

HSU answered "都正確" to the combined visibility/placement question for all four
knee/ankle points in the final 96–114 batch. All 76 points retain original Tsai X/Y.
**All 115 frames and 12 joints have now been individually reviewed: 1,380 states,
1,205 visible and correctly placed, 173 not observable, 2 uncertain, 0 unreviewed.**
Latest coordinate reference: `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_41/pitch_003/manual_keypoints.json`.
Latest notes-only supplement: `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_43/pitch_003/ground_truth.json`.
Both knees and right ankle: 115 visible each; left ankle: 114 visible / 1 not observable
(frame 65). Left wrist 85–86 remains uncertain. All 175 nonvisible points keep null XY.
Tsai manually placed original coordinates on 2026-10-04; HSU personally reviewed
visibility and placement on 2026-10-05; Codex only transcribed and verified evidence.
Point review is complete, but actual completion provenance has not been supplied:
annotation_status remains in_progress, reviewed_at_utc and confidence remain null.
Next: obtain actual completion provenance, preserve a new reviewed checkpoint,
then evaluate existing raw 2D predictions against visible reference coordinates.
Do not re-review hidden points or force uncertain coordinates. Schema/source checks
passed; historical references, canonical five-clip GT, raw predictions, video and
Tsai source are unchanged. Supplemental events 13/46/65/69/99 remain separate
from canonical 12/47/66/69/99. Check:
`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_41.json`.
This checkpoint publishes the seven leg batches and human attribution. No model,
threshold, inference, training or Phase 3 changes; no full test rerun for annotations.
**Phase 2 = IN PROGRESS.** Completing this clip's reference does not establish pose accuracy.

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
Tsai's X/Y annotations have now been returned; visibility review remains
pending and no real coordinate comparison has run. HSU full qualitative review
is now 5/5 and the qualitative warning
comparison is available above; Phase 2 remains in progress.
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

At this review checkpoint, no prediction comparison had run and no classmate
X/Y annotation had returned. It completed the human qualitative review,
with the diagnostic comparison subsequently recorded above. The
unchanged full suite then reported 138 passed, 0 failed, 1 skipped; this data
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

The original Phase2 evaluation ended with automatic reliability NOT PASSED.
The user subsequently authorized the isolated repair work recorded above.
Keep all original inputs, canonical annotations and raw predictions unchanged;
the mode countercheck is complete and not adopted. Future repair must address
independently verifiable subject alignment rather than reuse same-model agreement
as correctness or tune gates to the known003 misses.
The separate005 peer supplement may be source-validated when actually returned;
its absence does not reopen canonical5/5 completed review.

Do not automatically begin Phase3 or new-candidate analysis/formal promotion.
The approved reader scope ends at candidate intake and explicit local input review.

## MLB Pitch Clipper handoff boundary

`mlb-pitch-clipper` owns search, acquisition, cleaning, and cutting. Its current
release candidate should remain unchanged unless a reproducible product bug
requires a fix. `pitch-analysis` owns MP4 input validation, pose/tracking
reliability, motion analysis, and later comparison/reporting. Do not duplicate
Clipper's M1/M2 logic or depend on its internal temporary clips or event files.

The current delivery folder's CONTRACT.md v2 supplies index.jsonl, batch.json,
individual single-pitch MP4/JSON pairs and an optional viewing-only compilation.
Only indexed individual pairs are imported. The provider JSON is not the
analysis project's pitch-input-v1 and is preserved unchanged. No provider-side
implementation or repo dependency is introduced.

First intake scope is complete as candidates. Pitcher identity, actual delivery,
replay/mirror/full-body checks and preparation/follow-through require explicit
human review. Unknown context or handedness is not guessed. Formal conversion,
promotion and pipeline execution are separate future work; none was begun.
Shared-folder requirements remain documented in INPUT_REQUIREMENTS.md, and
version2 mapping, timeline evidence and review workflow in handoff_reader.md.
