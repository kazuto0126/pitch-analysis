# pitch-analysis

接收已整理好的 **單次投球 MP4 + metadata**，分析 MLB 投手的姿勢、動作時序與特徵。
長期目標包括單一投手 motion profile，以及不同投手的完整時序比較。

## 目前主線（2026-10-27）

**[投球動作描述第一版](docs/MOTION_ANALYSIS_V1.md)已交付**：大谷五球、山本啟用四球，
共2161格。沿用已接受的原生骨架，提供影片／曲線回看、人工五事件、四段時距與肘／膝模型XY讀值。
36段中33段可描述、3段事件未確認；逐點可靠性仍unknown，不能把座標完整當成精確度通過。

Phase 1 PASSED；原生資料介面接入PASSED；**Phase 2自動可靠性NOT PASSED**；
本批描述性交付COMPLETE，Phase 3整體尚未驗收。完整profile及跨投手動作相似度仍是後續目標；
現已提供獨立的[兩位投手人工事件時距對照](docs/native_timing_comparison.md)，保留來源與未知範圍。

| 要做的事 | 入口 |
|---|---|
| 在單一入口看最新完整成果，或帶到另一台電腦 | [新版可攜成果包](docs/phase3_portable_review_20261026.md#最新完整描述性交付02)：九球影片、兩份草案、最新四段／時距資料與雙側回看頁 |
| 看單投手動作特徵草案 | [大谷五球](docs/profiles/shohei_ohtani_descriptive_v1.md)／[山本四球](docs/profiles/yoshinobu_yamamoto_descriptive_v1.md)：各自的可描述差異、選格影響與資料限制 |
| 自動產生單投手動作摘要 | [describe-native-profile](docs/native_descriptive_profile.md)：沿用原事件報告，輸出全部同投手時距配對及肘／膝端點差分組，適用後續投手 |
| 從單投手摘要回看影片證據 | [review-native-profile](docs/native_descriptive_profile.md#從摘要直接回看影片證據)：選區段與原球對，查看肘／膝端點差並跳回原事件界線 |
| 重跑兩位投手的人工時距對照 | [compare-native-timing](docs/native_timing_comparison.md)：分數秒、全部配對與缺值 |
| 從時距差值回看兩側影片 | [review-native-timing](docs/native_timing_comparison.md#直接從差值回看兩側影片)：選球／區段、人工事件界線定位與兩側獨立播放器 |
| 查看目前結果、解讀限制與下一步 | [動作描述第一版](docs/MOTION_ANALYSIS_V1.md) |
| 對照目前狀態與歷史進度 | [STATUS](docs/STATUS.md)／[詳細歷史紀錄](docs/current_status.md) |
| 準備新影片或交付素材 | [輸入需求](docs/INPUT_REQUIREMENTS.md)／[交付資料夾讀取器](docs/handoff_reader.md) |
| 產生新骨架 | [人工選定投手＋人物框追蹤＋RTMPose原生17點](docs/standard_skeleton_workflow.md) |
| 讀取已保存骨架並查看動作 | [原生資料入口](docs/native_analysis_input.md) → [2D曲線](docs/native_motion.md) → [人工事件與逐球報告](docs/native_motion_events.md) |
| 查輸入契約或重現舊33點流程 | [Phase 0契約](docs/phase0_contracts.md)／下方歷史相容指令 |

新骨架統一走`prepare-skeleton` → 人工確認首格投手 → `extract-skeleton`，
已接受九球直接讀取保存結果。原生17點分數與舊MediaPipe33點的visibility／gate語義不同。
完整流程、固定runtime及新片人工確認方式見上列骨架文件。

本專案只接收已整理的影片；供片端搜尋、下載與剪輯不在本repo內。
交付資料夾唯讀，新匯入先列候選；現有大谷五球也不因骨架接受而自動升為正式reference。
`analysis_results/`影片與報告保存在本機，不包含在GitHub原始碼中。
最新可攜02包已包含四段讀值、兩份草案與雙側回看頁；舊01包作歷史快照保留。

## 安裝（Windows x64 / Python 3.12）

以下建立基本專案環境；原生骨架另使用[固定隔離runtime](docs/standard_skeleton_workflow.md)。

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

## 舊33點流程的輸入與使用（歷史相容）

下列`analyze-pitch`使用MediaPipe33點及原品質gate，保留供歷史重現。
新骨架走上方共用原生17點流程；兩者的分數、輸出與人工事件核准方式不能直接互換。

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

## 舊33點事件覆核與registry

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

既有33點 canonical library 是 `data/pitcher_database/releases/v0.6/`，包含 5 位投手、12 個
provisional references；它不是目前已接受原生骨架九球的資料集。左投/右投 scaler、camera gate、phase DTW 及留一驗證仍可使用。
舊 v0.5 release 保留，但不是目前的使用範例。小樣本驗證不是跨影片泛化能力的證明。

舊單用途scripts與長影片收件命令見[deprecated清單](docs/legacy.md)。
新供片由外部專案提供，本專案不搜尋、下載或剪輯來源影片。

## 測試

```powershell
.\.venv-analysis\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv-analysis\Scripts\python.exe -m pip check
```

測試使用本機合成MP4、確定性pose fixture及既有本機素材；完整suite包含正式山本五球E2E。
最新產品程式紀錄為2026-10-27：**1309 passed／0 failed／2 skipped**，
包含八項新增摘要回看測試及正式五球E2E；八項junction環境案例已補跑，剩餘兩項為檔案符號連結能力限制。
另Node **23 passed／0 failed**及34項既有事件helper斷言通過；新頁尚未作實際瀏覽器播放覆核。

## 接續開發

目前九球的描述性第一版已收束；[大谷五球草案](docs/profiles/shohei_ohtani_descriptive_v1.md)
及[山本四球草案](docs/profiles/yoshinobu_yamamoto_descriptive_v1.md)均已說明各自哪些階段差異在合法人工選格下仍成立、哪些受選格影響，附原片查核位置。
兩份單投手草案已完成本批交付；`describe-native-profile`可從原事件報告重現單投手摘要，
九球共64組同投手時距配對，56可比、8未定；肘／膝72筆摘要中66筆有可算端點、6筆事件未定。
`compare-native-timing`另提供跨投手80組時距對照（65可比／15未定）。完整動作比較所需的可靠特徵仍須另行界定。
Phase 2自動可靠性仍NOT PASSED，Phase 3整體尚未驗收。範圍見[第一版與後續工作](docs/MOTION_ANALYSIS_V1.md)。
