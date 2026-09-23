# Analysis dataset and legacy reference schema

新輸入只接受已整理 MP4 與 `pitch-input-v1`。必要 metadata、輸出 JSON Schemas、
frame/timebase 與人工 review handoff 以 [Phase 0 contracts](phase0_contracts.md) 為準。
不再要求 URL、license、原始完整比賽位置或下載資訊。

```text
input/<pitcher_id>/<pitch_id>.mp4
input/<pitcher_id>/<pitch_id>.json

analysis_results/<pitcher_id>/<pitch_id>/
  input_manifest.json
  analysis.json
  video_metadata.json
  keypoints.json
  metrics.json
  phases.json
  pose_raw.csv
  pose_raw.capture.json
  pose_clean.csv
  pose_clean.clean.json
  features.csv
  features.quality.json
  metadata.json
  events.json
  phase_sequence.csv           # 人工事件審核並 revalidate 後產生
  phase_sequence.quality.json
```

Registry root 必須指向投手資料夾的共同父目錄（例如 analysis_results），使 pitcher ID
仍由第一層資料夾辨識。pitch ID 在投手內唯一；不同投手可各有 pitch_001。
新 video ID 使用 `<pitcher_id>__<pitch_id>`，既有 video ID 保持不變。

現有 legacy library `data/pitcher_database/<pitcher_id>/<session_id>/<pitch_id>/` 原樣保留。
其中 raw/source_catalog.json 和 intake_review 僅為歷史來源記錄；新 analysis 不讀取它們。
舊資料 frame index 可能來自長影片，不能直接當成新 MP4 從 0 開始的 frame index。
由外部專案交付逐球 MP4 後，應建立新 metadata 並重新分析，避免錯用事件時間。

現有核心 gate 不變：raw pose detection 至少 90%、主要特徵 raw coverage 至少 80%、
投球手肘至少 50%、連續缺失來源姿態至多 2 幀。人工事件覆核不會放寬門檻。
這些是當前原型政策，不是已校準的生物力學準確度。

比較前須檢查 view、mirror、full-body framing 與 throws。目前跨左右投不比較；
scaler 由同手 reference 擬合，query 不自行 Min-Max。留一驗證每折排除 held-out query。
Strict camera mode 要求完整鏡頭資訊；exploratory 允許未知資訊但列出警告。

目前 canonical release 是 `data/pitcher_database/releases/v0.6/`：

```text
manifest.json
registry.json
scaler_left.json
scaler_right.json
validation_left.json
validation_right.json
revalidation.json
```

不要覆寫已存在 release，也不要混用不同 release 的 registry/scaler。
registry schema 的 `0.5-reviewed-event-window-provisional` 是獨立 schema version，
不是 canonical release v0.5；不應因 release 升至 v0.6 而改寫 schema 字串。
