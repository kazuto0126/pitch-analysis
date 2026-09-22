# MLB reference dataset schema

本資料庫以「一次投球（pitch instance）」為最小可比較單位，而不是以單一投手的平均值取代所有投球。

URL 或長影片的自動前處理先寫入 staging，不會直接成為 reference：

```text
data/intake/<job_id>/
  manifest.json
  source/downloaded.<ext>       # URL 輸入時保存
  standardized/source.mp4      # CFR H.264/yuv420p
  candidates/<normalized_pitch_name>.mp4
```

`manifest.json` 記錄來源、checksum、轉檔參數、候選起訖時間、motion evidence、選配的
CLIP ReID evidence，以及每個 clip 的 `prepare-segment` handoff。所有 candidate 初始狀態均為
`needs_human_review`；只有人工接受後才能放入 `raw/`，再經既有 pose quality 與事件審核流程。

```text
data/pitcher_database/
  raw/<pitcher_id>/<season>/<clean_video_name>.mp4
  raw/source_catalog.json       # original file name, asserted identity, hand, season, view
  <pitcher_id>/<session_id>/<pitch_id>/
    source.mp4                 # 僅在授權允許時保存
    pose_raw.csv
    pose_raw.capture.json
    pose_clean.csv
    pose_clean.clean.json
    features.csv
    features.quality.json
    events.json
    phase_sequence.csv
    phase_sequence.quality.json
    metadata.json
  releases/<version>/
    manifest.json
    registry.json
    scaler_left.json
    scaler_right.json
    validation_left.json
    validation_right.json
    revalidation.json
```

`raw/source_catalog.json` 的 `accepted_for_segmentation` 只代表影片含有值得切段的後方鏡頭；
它不是 reference。每一個準備中的 pitch folder 都以 `metadata.json` 記錄來源秒數、MediaPipe
模型、feature coverage 與 quality gate，並以 `events.json.review_status` 區分
`needs_human_review`、`provisional_candidates_accepted`、`human_reviewed` 和 `rejected`。

`prepare-segment` 先對整個候選片段套用品質 gate。人工確認事件後，registry 會再對真正的
pitch start 到 follow-through end 套用同一組門檻：pose 偵測率至少 90%、連續缺失來源姿態
至多 2 幀、核心特徵原始覆蓋率至少 80%、投球手肘原始覆蓋率至少 50%。只有 event window
本身通過時，才能取代因片段前後 padding 導致的全片失敗；人工標註不能放寬門檻。

`manifest.csv` 至少包含：`pitch_id`, `pitcher_id`, `pitcher_name`, `throws`, `pitch_type`, `video_view`, `camera_side`, `fps`, `width`, `height`, `source_url`, `license`, `pose_model`, `feature_schema_version`, `event_annotation_version`。

比較前必須篩選相同的 `video_view`、相容的 camera protocol，並依 `throws` canonicalize 成 throwing/lead/trail 側。每個 `events.json` 都應保存人工或自動偵測的 pitch start、foot-strike candidate、release candidate、follow-through end，以及各事件 confidence 和 annotation source。

scaler 必須依投球慣用手分開擬合，並將 `reference_scope.throws` 寫進 scaler JSON。建議用
`fit-registry-scaler` 從合格 registry 自動選取資料。scaler 亦保存來源 registry 的路徑與
schema；ranking 會拒絕慣用手不符或 registry provenance 不一致的 scaler，也不會比較另一手的 reference。

scaler 只能由 reference/training split 擬合；query pitch 不得自行 Min-Max。留一投球驗證的每一折
都必須排除 held-out query 後重新擬合 scaler。若某投手只有一個 reference，該折應標記為
`unscored`，不可算錯也不可灌入 accuracy。任何 ranking result 都要寫入它使用的 schema、scaler、
feature weights、DTW band、camera compatibility 與 reference pitch ids。

`build-library-release` 會在全新空目錄內一次建立上述 bundle，並拒絕覆寫既有 release。
release manifest 是後續重現排名的入口；不要任意混用不同 release 的 registry 與 scaler。
