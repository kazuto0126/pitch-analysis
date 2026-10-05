# Current status — Phase 1 accepted; Phase 2 reliability baseline

Updated: 2026-10-05

**Phase 1 = PASSED**

The five formal Yoshinobu Yamamoto single-pitch inputs passed the existing
Phase 1 clip-level acceptance checks. Phase 2 now evaluates tracking and
per-joint pose reliability on those same five clips. No Phase 1 threshold,
PitcherSelector rule, pose algorithm, interpolation, or smoothing policy was
changed.

**Phase 2 = IN PROGRESS — reliability gaps identified; manual X/Y review pending.** HSU's
five qualitative reviews and their warning comparison are complete. The baseline runner,
reports, and annotation workflow are available; program execution is not a
Phase 2 acceptance result.

## Phase 2 baseline

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
- Exact/range/uncertain event records were preserved; coordinate error, event
  error, and independent reviewer agreement remain unmeasured.

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

Keep the five formal clips and the superseded archive unchanged. Follow this
sequence agreed with the user on 2026-09-28:

1. Preserve all five completed HSU qualitative reviews and their uncertainty.
   Review the returned complete `pitch_003` coordinates, whose format/source
   checks passed. The four elbow/wrist joints are reviewed across 0–114, with
   left wrist 85–86 retained as uncertain. Next review only both shoulders at 0–15,
   using cyan 1 for left shoulder and red 2 for right shoulder. Resolve remaining
   visibility and placement questions with the reviewers,
   obtain the remaining independent event supplements and completion provenance,
   and preserve the HSU event supplement recorded above. Do not automatically
   merge or turn inferred hidden locations into observable reference points.
2. Review the measured gaps in the qualitative comparison, especially the
   unscreened `pitch_003` displacement and observed states on human-unreliable
   arm frames. Measure coordinate error after visible reference points are verified;
   keep raw-overlay judgments distinct from processed availability.
3. Use both forms of evidence to decide whether pose/tracking reliability needs
   changes. Any such change is separate from this completed diagnostic comparison;
   do not treat successful execution as Phase 2 acceptance.
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
