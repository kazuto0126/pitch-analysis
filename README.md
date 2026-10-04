# pitch-analysis

接收已整理好的 **單次投球 MP4 + metadata**，分析 MLB 投手的姿勢、動作時序與特徵。
長期目標包括單一投手 motion profile，以及不同投手的完整時序比較。

專案不負責影片搜尋、YouTube、下載、yt-dlp、來源管理、從長影片建立素材或指定球員 ReID。
這些能力由獨立 preprocessing 專案負責。本機 MP4 probe / validation / working-copy
standardization 屬於分析輸入品質控制，仍保留在本專案。

## Phase 0 已完成的入口

`analyze-pitch <mp4> <metadata.json>` 驗證整支影片，沿用現有 MediaPipe、confidence gate、
clean pose、2D feature 與 quality gate，輸出待人工覆核的單球結果。
Phase 0 沒有新增自動事件偵測、投手追蹤、profile 或 overlay；既有 phase、DTW、normalization、
registry 與 validation 演算法保留。現在的結果仍是 2D 投影分析，不能解讀為真實 3D biomechanical loading。

## Phase 1.1：單球 input quality gate

目前 `analyze-pitch` 僅接受 `rear_centerfield_broadcast`。它會在多人體姿態中以
畫面位置、身體尺度與時間連續性保守選取投手，並輸出逐幀原始／處理後 keypoints、
品質摘要、2D 投手手腕軌跡、`overlay.mp4` 與獨立人工檢查表。這不是球員身分 ReID；
視角與完整投球仍須目視核對。2026-09-24 完成正式五支山本由伸素材的 Phase 1
finalization，五支均通過現有 clip-level acceptance 條件；正式狀態與輸出見
[Current status](docs/current_status.md)。先前失敗素材的歷史紀錄見
[Phase 1 baseline](docs/phase1_baseline.md)。

## Phase 2：投手追蹤與姿態可靠度

正式五支山本由伸單球作為第一個 baseline dataset。Phase 2 在獨立分支上新增
逐關節 observed／interpolated／missing 狀態、關節覆蓋率與跳動檢查，以及
投手骨架的 ROI、中心、尺度、動作連續性和 track-break 警示。原有 MediaPipe
推論經共用 `PoseEstimator` 介面執行，未更換模型或修改選取門檻。
HSU 已完成五支影片的逐格定性覆核，並完成與既有可靠性警示的
[比較報告](docs/phase2_ground_truth_comparison_20261004.md)。比較顯示骨架缺失能被抓到，
仍有重大錯位及局部誤連未被可靠提示。已收到 Tsai 的手動 X/Y 回傳，
HSU 正在核對可見性與點位；完整座標覆核尚未完成，座標與事件誤差尚未量測。
Phase 2 仍在進行中；
詳見 [Phase 2 reliability](docs/phase2_reliability.md) 與
[manual ground truth](docs/phase2_ground_truth.md)。

目前 HSU 已完成 5/5 逐格定性覆核。`pitch_005` 除已記錄的問題外，
HSU 另確認其餘右肩／肘／腕及左髖／膝／踝皆可見且大致對位；
準備啟動與最高抬腿事件仍標為 uncertain。另提供可離線分享的
[同學獨立覆核流程](docs/phase2_peer_review.md)：`pitch_003` 完整覆核、
`pitch_005` 事件補充。回覆沿用相同 ground truth 格式，按 reviewer 分開保存。

2026-10-04 確認同學任務改為 [手動骨架座標標註](docs/phase2_manual_keypoints.md)：
用 CVAT 在 `pitch_003` 原始逐格圖上標 12 個身體關節，另補 `pitch_003`／`pitch_005`
事件。人工 X/Y 與可見性另存，可量化既有 AI 的逐關節位置誤差；不自動更新模型。
同學可直接下載 [GitHub 人工骨架標註 ZIP](https://github.com/kazuto0126/pitch-analysis/releases/download/phase2-manual-pose-review-20261004-01/manual_pose_package_20261004_01.zip)，
解壓後閱讀 `START_HERE.md`；不需要 clone 專案。

目前已確認的人工座標、遮擋狀態與下一次覆核入口見
[2026-10-05 人工覆核 checkpoint](docs/phase2_manual_review_checkpoint_20261005.md)。

`validate-input-quality <mp4> <metadata.json>` 先做影片層的保守檢查；
`analyze-pitch` 會在姿態推論前執行同樣 preflight。明顯切鏡標記 `rejected`，
不執行後續 pose；其他素材執行原有 pipeline 後，將主體遺失、疑似 identity switch、
準備／follow-through 完整性與現有 pose quality gate 更新至 `input_quality.json`。
`accepted` 仍需人工確認視角、投手身分及是否為正常速度單球；`degraded` 不可
直接納入 reference。規則、證據限制與人工檢查項目見
[Input Quality Gate](docs/phase1_1_input_quality.md)。

## 安裝（Windows x64 / Python 3.12）

從專案根目錄執行：

```powershell
.\scripts\setup.ps1
```

預設用 `py -3.12` 建立 `.venv-analysis`。若沒有 Python launcher，指定可用的 Python 3.12：

```powershell
.\scripts\setup.ps1 -PythonExe "C:\path\to\Python312\python.exe"
```

腳本安裝 `requirements-lock.txt` 的全部固定版本，再以 editable mode 安裝本專案。
不需要手動設定 PYTHONPATH，也不需要啟用環境。舊 `.venv` 保留作歷史資料，不再作執行入口。
只安裝 `opencv-contrib-python`，避免兩個套件同時提供 cv2。FFmpeg 由 imageio-ffmpeg 提供。

## 輸入與使用

```text
input/
  shohei_ohtani/
    pitch_001.mp4
    pitch_001.json
  yoshinobu_yamamoto/
    pitch_001.mp4
    pitch_001.json
```

複製 [metadata 範例](examples/pitch_001.json) 到 MP4 旁，再填寫真實投手與影片資訊。
每支檔案應是一個正常速度、未鏡像、連續鏡頭、全身入鏡的投球。
這些內容宣告仍需人工確認；驗證器不會辨識球員身分或計算影片內投球次數。

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe validate-pitch input/shohei_ohtani/pitch_001.mp4 input/shohei_ohtani/pitch_001.json
.\.venv-analysis\Scripts\pitch-analysis.exe validate-input-quality input/shohei_ohtani/pitch_001.mp4 input/shohei_ohtani/pitch_001.json --output analysis_results/input_quality_review.json
.\.venv-analysis\Scripts\pitch-analysis.exe analyze-pitch input/shohei_ohtani/pitch_001.mp4 input/shohei_ohtani/pitch_001.json
```

可加 `--output-root PATH` 選擇新輸出位置，或 `--model PATH` 指定本機 Pose Landmarker 模型。
預設模型為專案根目錄下 `models/pose_landmarker_full.task`。
`--standardize` 可建立 H.264/yuv420p 工作副本，保留原始 FPS、解析度與 frame count。
不會降為固定 30 FPS、不會切段、不會修改原始 MP4。Phase 0 接受 CFR；不支援 VFR、
帶 rotation metadata 或非正方形像素的影片。完整規則見 [contracts](docs/phase0_contracts.md)。

```text
analysis_results/<pitcher_id>/<pitch_id>/
  analysis.json             # 執行狀態、版本、hash、輸出索引
  input_manifest.json       # 原始 input metadata 快照
  video_metadata.json       # 整支 decode/probe/時間軸
  input_quality_preflight.json # pose 前的影片品質判定
  input_quality.json        # 最終 input 品質；明顯切鏡時與 preflight 相同
  keypoints.json            # 每幀位置、confidence、presence
  metrics.json              # 既有 2D 特徵摘要與原始 coverage
  phases.json               # Phase 0 待覆核事件快照，沒有偽造事件
  events.json               # 現有流程的人工標註入口
  pose_raw.csv
  pose_raw.capture.json
  pose_clean.csv
  pose_clean.clean.json
  features.csv
  features.quality.json
  metadata.json             # 舊分析流程 metadata，與 input metadata 不同
```

若 preflight 已拒絕，保留 input manifest、video metadata、品質報告與
`analysis.json`，不執行 pose、不產生 keypoints/overlay。無 pose 時保留 raw capture、
keypoints、metrics 與失敗狀態，不建立事件檔。
輸出目錄存在時拒絕覆寫。品質不足會回報 `quality_gate_failed`；不會自動成為 reference。

## 事件覆核與既有分析 handoff

人工檢查姿態與五個事件，在 `events.json` 填入從 0 開始的 clip frame index，
確認後設 `review_status=human_reviewed`，再執行：

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe revalidate-segment analysis_results/shohei_ohtani/pitch_001
.\.venv-analysis\Scripts\pitch-analysis.exe build-registry analysis_results analysis_results/registry.json
```

以上保留事件順序、原始 coverage、event-window quality gate 與 registry 設計。
`phases.json` 等新契約檔是首次 preparation 快照；舊 revalidate 指令不會更新這些快照，
實際核准狀態由 events.json 與 registry 決定。詳見 [契約與限制](docs/phase0_contracts.md)。

## 現有資料與 legacy

目前 canonical library 是 `data/pitcher_database/releases/v0.6/`，包含 5 位投手、12 個
provisional references。左投/右投 scaler、camera gate、phase DTW 及留一驗證仍可使用。
舊 v0.5 release 保留，但不是目前的使用範例。小樣本驗證不是跨影片泛化能力的證明。

preprocessing 完整保存於 `integration/opencode-preprocessing` 的 `4a65c32`，
尚未合併到新的 `codex/analysis-phase-0`。舊單用途 scripts 和長影片收件命令已列入
[deprecated 清單](docs/legacy.md)，檔案仍保留。既有 Git 已追蹤的環境、模型和素材仍未清除。

## 測試

```powershell
.\.venv-analysis\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv-analysis\Scripts\python.exe -m pip check
```

自動測試使用本機合成 MP4 與確定性的 pose fixture，不依賴網路下載。
實際 MediaPipe 推論另由本機 smoke test 驗證，測試報告見 [Phase 0 狀態](docs/phase0_status.md)。

## 接續開發

Phase 0 已封存，Phase 1 已通過五支正式單球的 clip-level 驗收。Phase 2
目前聚焦於同五支影片的追蹤與關節可靠度，等待獨立人工標註來衡量實際
準確性；尚不擴充多投手或跨投手比較。
