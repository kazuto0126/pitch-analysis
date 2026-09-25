# Phase 2 manual ground truth

The ground-truth contract is `ground-truth-v1`. It stores a human review of one
specific MP4 separately from `keypoints.json`, `pose_raw.csv`, tracking output,
and other model predictions. A generated file is an **unreviewed template**;
its null labels are not evidence that the model was correct.

## Create a template

The Phase 2 runner can call:

```python
from pitch_analysis.ground_truth import create_blank_ground_truth

path = create_blank_ground_truth(
    video_path="input/yoshinobu_yamamoto/phase1_final/pitch_001.mp4",
    pitch_id="pitch_001",
    total_frames=87,  # independently decoded MP4 frame count
    ground_truth_root="analysis_results/phase2_yamamoto/ground_truth",
)
```

This writes `ground_truth/pitch_001/ground_truth.json`. It refuses to replace an
existing file, including a partially or fully reviewed annotation. The file
contains the source MP4 filename, SHA-256, total decoded frames and a zero-based
frame index convention. Keep the `ground_truth/` directory outside each pitch's
prediction directory. Do not copy prediction values into human labels.

## Annotate the video

Watch the original video and overlay together. The reviewer records their name,
UTC review time, and optional notes. Use inclusive zero-based frame intervals;
for a 10-frame clip the last frame is 9.

- `pitcher_correctly_selected`: true only if the selected skeleton belongs to
  the intended pitcher whenever a skeleton is selected. Mark false if a wrong
  subject is selected, even briefly. A missing skeleton alone is a pose failure.
- `identity_switch_intervals`: frames where the selected skeleton changes from
  the pitcher to another subject. Use `[]` only after checking the full video
  and finding none. Use `null` while unreviewed.
- `major_pose_failure_intervals`: frames where the predicted body skeleton is
  substantially misplaced, absent, or unusable. Use `[]` only after review.
- `throwing_elbow_reliability` and `lead_knee_reliability`: ordered intervals
  labeled `reliable`, `unreliable`, or `uncertain`. In a completed review these
  intervals must cover every frame without overlap or gaps. Add a reason for
  every unreliable or uncertain interval, such as occlusion, blur, or overlap
  with the batter. Do not infer invisible joint positions.
- `events`: `preparation_start`, `leg_lift` (peak), `foot_plant` (first
  visible contact), `approximate_release`, and `follow_through_end`.
  For a visible event use `{"status": "annotated", "frame_index": 42,
  "note": "..."}`. For an event that cannot be judged, use `status` of
  `uncertain` or `not_visible`, `frame_index: null`, and an explanatory note.
  Events with frame indices must appear in chronological order.

`null` means **not yet reviewed**. An empty interval list means **reviewed and
none found**. `uncertain` is an explicit human judgment; it must not be replaced
with model interpolation. Set `annotation_status` to `in_progress` during
annotation. Set it to `reviewed` only after all clip, interval, joint and event
fields have been assessed. A reviewed file may still contain explicit
`uncertain` or `not_visible` labels.

## Validate before scoring

```python
from pitch_analysis.ground_truth import load_ground_truth

annotation = load_ground_truth(
    "analysis_results/phase2_yamamoto/ground_truth/pitch_001/ground_truth.json",
    source_video_path="input/yoshinobu_yamamoto/phase1_final/pitch_001.mp4",
)
if annotation["annotation_status"] != "reviewed":
    raise ValueError("Human ground truth remains pending")
```

Validation checks the schema, source filename and hash, frame bounds, interval
order, complete joint timelines, event order, and human-review provenance.
Tracking and keypoint accuracy metrics should be reported as **unmeasured**
until a `reviewed` annotation exists. Human edits belong only in the ground
truth file; preserve the raw predictions for reproducible comparison.

Once annotations are reviewed, write a separate comparison report:

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\evaluate_phase2_ground_truth.py input\yoshinobu_yamamoto\phase1_final analysis_results\phase2_yamamoto_20260925_01 analysis_results\phase2_yamamoto_20260925_01\ground_truth_comparison_reviewed.json
```

This command refuses to overwrite an existing comparison. It reports warning
agreement and joint observed/interpolated/missing states against manual labels.
It leaves coordinate localization and event timing accuracy unmeasured until
corresponding reference coordinates and automatic event predictions exist.
