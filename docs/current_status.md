# Current status — Phase 1 finalization

Updated: 2026-09-24

**Phase 1 = PASSED**

The five formal Yoshinobu Yamamoto single-pitch inputs passed the existing
Phase 1 clip-level acceptance checks. No threshold, PitcherSelector, pose
algorithm or analysis logic was changed. Phase 2 has not started.

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

The five-pair E2E run wrote
`analysis_results/phase1_final_validation_20260924_01/`, with
`validation_summary.json`, `final_acceptance.json`,
`visual_inspection.json`, `test_suite.log`, and one analysis directory per
formal pitch under `yoshinobu_yamamoto/`. Every input-quality result is
`accepted`; every keypoint-quality result is `success`. The analysis
manifests remain `needs_event_review` because event labels are not inferred
automatically.

| Pitch | Valid pose | Mean visibility | Longest pose gap | Throwing elbow raw coverage | Lead knee raw coverage |
|---|---:|---:|---:|---:|---:|
| `pitch_001` | 87/87 (100%) | 0.814 | 0 frames | 51.72% | 93.10% |
| `pitch_002` | 175/175 (100%) | 0.816 | 0 frames | 65.14% | 98.86% |
| `pitch_003` | 115/115 (100%) | 0.823 | 0 frames | 53.04% | 90.43% |
| `pitch_004` | 112/114 (98.25%) | 0.812 | 2 frames | 50.88% | 90.35% |
| `pitch_005` | 100/101 (99.01%) | 0.827 | 1 frame | 71.29% | 86.14% |

All five exceed the unchanged 50% throwing-elbow raw-coverage requirement.
The other core raw feature coverages are at least 80%, and valid pose
coverage is at least 90%.

## Overlay inspection

The five final overlays were viewed directly. They are byte-identical to
the corresponding overlays from earlier all-frame reviews. All five show
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
**62 tests, OK, 0 skipped**. This includes the opt-in real five-pitch E2E
test. `input/` and `analysis_results/` are intentionally Git-ignored;
the finalization commit records this status document and documentation
updates, while the videos, archive, and run outputs remain local.
