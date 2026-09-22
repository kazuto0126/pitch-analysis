# 基於人體姿態估計與動作特徵分析之棒球投球姿勢相似度分析系統

## 1. 專題簡介

本專題旨在建立一套棒球投球姿勢分析系統。

使用者輸入一段棒球投球影片後，系統透過人體姿態估計取得人體關節位置，再進一步計算投球動作中的姿勢與動作特徵。

最後將使用者的投球動作與 MLB 投手資料進行比較，找出動作較為相似的投手。

## 2. 專題目標

本專題主要完成以下功能：

1. 讀取棒球投球影片
2. 使用人體姿態估計取得人體關節座標
3. 擷取肩膀、手肘、髖部與膝蓋等關節資訊
4. 計算投球動作特徵
5. 將投球動作分成不同階段
6. 建立 MLB 投手動作特徵資料
7. 計算投球動作之間的相似度
8. 將分析結果視覺化

## 3. 系統流程

影片輸入

↓

影片處理

↓

人體姿態估計

↓

關節資料擷取

↓

動作特徵計算

↓

投球動作分期

↓

MLB 投手資料庫

↓

相似度分析

↓

結果視覺化

## 4. 主要分析部位

目前主要分析以下身體部位：

- 肩膀
- 手肘
- 髖部
- 膝蓋

手腕等其他部位將視實作進度決定是否加入。

## 5. 專題範圍

本專題第一階段以二維人體姿態分析為主。

暫不包含：

- 3D 人體重建
- 多攝影機同步分析
- 即時攝影機分析
- 大型深度學習模型訓練
- 手機 App

## 6. 專案資料夾

```text
pitch-analysis/
│
├─ src/
│  └─ Python 程式
│
├─ data/
│  ├─ raw_videos/
│  ├─ pose_data/
│  └─ pitcher_database/
│
├─ tests/
│  └─ 測試程式
│
├─ docs/
│  └─ 專題文件與設計紀錄
│
└─ README.md
```

## 開發中的新版 pipeline

舊有 `src/*.py` 腳本與既有 CSV 均保留不動。新的程式碼位於
`src/pitch_analysis/`，先提供**品質感知**的特徵輸出：低於 visibility
threshold 的 landmark 不會被誤當成有效座標，也不會把遺失 frame 靜默移除。

### 從影片連結直接準備投球 MP4

`preprocess-video` 接受 HTTP(S) 影片連結或本機路徑，先下載／讀取來源，轉成 30 fps、
H.264、`yuv420p` MP4，再依指定時間輸出互不覆寫的候選投球 clips。每個工作目錄均有
`manifest.json` 保存來源、checksum、轉檔設定與原始時間邊界：

```powershell
$env:PYTHONPATH = "src"
python -m pitch_analysis.cli preprocess-video "VIDEO_URL" data/intake/darvish_job_01 --pitcher-id yu_darvish --season 2025 --throws RIGHT --view rear_centerfield_broadcast --clip 00:11-00:16 --clip 00:24-00:29
```

若尚未知道投球時間，可讓系統先依畫面運動產生待審核候選：

```powershell
python -m pitch_analysis.cli preprocess-video "VIDEO_URL" data/intake/darvish_job_02 --pitcher-id yu_darvish --season 2025 --throws RIGHT --view rear_centerfield_broadcast --auto-detect
```

自動模式不會在偵測失敗時硬切固定長度影片，也不會把候選直接視為有效投球。

若有目標投手照片，可加上一次或多次 `--reference-photo PATH`。系統會對多張照片等權建立
CLIP prototype，並以 clip 多幀中位數回報 `matched`、`ambiguous` 或 `unknown`；結果只作為
人工審核證據。此選配功能需先安裝 `requirements-reid.txt`。

clips 會出現在 `data/intake/darvish_job_01/candidates/`。它們的狀態是
`needs_human_review`，確認內容後再交給既有 `prepare-segment`；下載或剪輯不會自動把素材
加入 reference registry。網址下載需要 `yt-dlp`，FFmpeg 由 `imageio-ffmpeg` 提供或以
`--ffmpeg PATH` 指定。

在修復 Python 環境後，可由專案根目錄執行：

```powershell
$env:PYTHONPATH = "src"
python -m pitch_analysis.cli clean-pose data/pose_data/test_pitch_pose_named.csv data/pose_data/test_pitch_pose_clean.csv
python -m pitch_analysis.cli build-features data/pose_data/test_pitch_pose_clean.csv data/pose_data/test_pitch_features_v3.csv --throwing-side RIGHT
```

這會額外產生對應的 `.quality.json`，記錄缺失 frame、每項特徵
無效的 frame 數與使用的品質閾值。`throwing-side` 必須依已人工確認的投手慣用手設定；
不能由畫面左右直接推論。

新 pipeline 不會對單支 query 影片做 Min-Max。跨投手比較應使用 canonical release 內、
由合格 reference set 擬合的 z-score scaler；資料庫結構見
[`docs/reference_dataset_schema.md`](docs/reference_dataset_schema.md)。

在使用 phase-aware DTW 前，先產生並人工填寫事件標註（frame number）：

```powershell
python -m pitch_analysis.cli event-template data/pose_data/test_pitch_features_v3.quality.json data/pose_data/test_pitch_events.json --video-id test_pitch
# 人工覆核後，將 events 的五個 frame 值填入 JSON
python -m pitch_analysis.cli build-phases data/pose_data/test_pitch_features_v3.csv data/pose_data/test_pitch_events.json data/pose_data/test_pitch_phase_sequence.csv
```

`events.json` 未經人工覆核的 reference 不會進入排名。資料庫應以不可覆寫的 release
為單位建立；下列命令會依序重建衍生檔、產生 registry、左右投 scaler、留一投球驗證與
manifest。目標資料夾必須是全新空目錄，避免意外混用不同版本：

```powershell
python -m pitch_analysis.cli build-library-release data/pitcher_database data/pitcher_database/releases/v0.6
```

目前完成的 canonical bundle 是 `releases/v0.5/`。使用該 bundle 執行右投 query：

```powershell
python -m pitch_analysis.cli rank-pitchers data/pose_data/test_pitch_phase_sequence_v0.4.csv data/pitcher_database data/pitcher_database/releases/v0.5/scaler_right.json data/pose_data/pitcher_ranking_right_v1.5_camera_gated.json --query-throws RIGHT --registry data/pitcher_database/releases/v0.5/registry.json --query-context data/pose_data/test_pitch_query_context_v0.4.json --camera-mode exploratory
```

長影片可先用多項姿態特徵的逐幀變化找出候選動作窗。輸出只是供目視審核的提示，
不會自動宣稱某段一定是投球，也不會自動加入 reference registry：

```powershell
python -m pitch_analysis.cli detect-motion-windows data/pose_data/test_pitch_features_v0.3.csv data/pose_data/test_pitch_motion_candidates_v0.2.json
```

可用留一投球驗證檢查資料庫內部辨識能力；每一折都會排除 query 後重新擬合 scaler：

```powershell
python -m pitch_analysis.cli validate-ranking data/pitcher_database/releases/v0.5/registry.json data/pitcher_database/validation_right_check.json --throws RIGHT
python -m pitch_analysis.cli validate-ranking data/pitcher_database/releases/v0.5/registry.json data/pitcher_database/validation_left_check.json --throws LEFT
```

For cross-season references, supply season, team, and view with the event template. Rankings
retain per-season contribution rather than silently mixing every career phase sequence:

```powershell
python -m pitch_analysis.cli event-template FEATURES_QUALITY.json EVENTS.json --video-id yamamoto_orix_bullpen_01 --season unknown --team "Orix Buffaloes" --view rear_bullpen
```

從任何已授權的 reference MP4 擷取姿態時，可指定影片秒數區段；輸出的 `frame` 仍保留來源影片的原始 frame 編號：

```powershell
python -m pitch_analysis.cli extract-pose data/pitcher_database/yamamoto_2024_spring_training.mp4 data/pitcher_database/yamamoto_11_30_pose.csv --start-second 11 --end-second 30
```

## 素材收件與命名

原始影片先放在 `data/pitcher_database/raw/<pitcher_id>/<season>/`，並由
`data/pitcher_database/raw/source_catalog.json` 記錄來源檔名、投球慣用手、賽季與
鏡頭類型。這一層的 `accepted_for_segmentation` **不是**可直接比較的 reference；
仍必須逐球切出完整投球、擷取姿態、人工檢查事件後，才會出現在 registry。

收件時可先建立不會改動原影片的聯絡表：

```powershell
python -m pitch_analysis.cli audit-media data/pitcher_database/intake_review C:\path\to\candidate.mp4 --samples 12
# 可加 --start-second 與 --end-second，密集審核一段已選中的投球
```

將某個確認可能完整的片段準備成待審核資料夾時，使用單一工作流程（它不會自動把資料列入 ranking）：

```powershell
python -m pitch_analysis.cli prepare-segment data/pitcher_database/raw/yoshinobu_yamamoto/2026/yoshinobu_yamamoto_2026_centerfield_clip_08_01.mp4 data/pitcher_database/yoshinobu_yamamoto/2026_centerfield_clip_08_01/pitch_01 --video-id yamamoto_2026_clip_08_01_pitch_01 --throwing-side RIGHT --start-second 35.5 --end-second 39.5 --season 2026 --team "Los Angeles Dodgers" --view rear_centerfield_broadcast
```

這會產生 raw pose、clean pose、features、品質報告、`metadata.json` 和尚待人工填寫的
`events.json`。輸出資料夾若已有資料會拒絕覆寫，保護既有人工事件標註。
它還會以 landmark feature coverage 做切段前的初步 gate（主要下肢／軀幹至少 80%、投球手肘至少
50%、pose 偵測至少 90%、連續缺失至多 2 幀）；通過者仍需視覺與事件審查。若只有投球前後的
padding 造成全片未達標，人工覆核事件後可改以真正的 event window 套用完全相同門檻；門檻本身
不會因人工覆核而放寬。

reference scaler 必須一手一份。建議由 registry 自動擬合
（`fit-registry-scaler ... --throws RIGHT` 或 `LEFT`），避免漏列或誤列 reference；
排名會強制只取與 query 相同慣用手的 reference，並拒絕使用另一手的 scaler。鏡頭視角仍需以 `events.json` 的
`reference_context.view` 記錄並在報告中審核；scaler 內的 registry 路徑與 schema provenance
也必須與排名使用的 registry 一致，否則流程會停止。目前的 2-D 結果不可被解讀為 3-D 生物力學量測。

目前可比較資料量、品質限制與下一個驗收門檻見
[`docs/development_status.md`](docs/development_status.md)。
