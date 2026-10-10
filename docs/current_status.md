# Current status — Phase 2 repair checkpoint; candidate intake isolated

Updated: 2026-10-10

**Phase 1 = PASSED.**
**Phase 2 evaluation = COMPLETE; Phase 2 = NOT PASSED (automatic reliability degraded).**

This is the terminal result of the existing baseline evaluation, not an automatic
reliability release. No new numeric acceptance bar, model, confidence gate,
PitcherSelector, pose/tracking algorithm, interpolation or smoothing change.
The original Phase 1 stable state and five formal videos remain unchanged.

## 2026-10-10 paired ROI loss diagnosis (latest; production unchanged)

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
