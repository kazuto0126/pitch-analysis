# pitch-analysis

接收已整理好的 **單次投球 MP4 + metadata**，分析 MLB 投手的姿勢、動作時序與特徵。
長期目標包括單一投手 motion profile，以及不同投手的完整時序比較。

本次收尾摘要見 [STATUS](docs/STATUS.md)；外部專案供片需求見
[INPUT_REQUIREMENTS](docs/INPUT_REQUIREMENTS.md)。

2026-10-19 最新：[可選投手範圍修正已交付](docs/phase2_pitcher_lock_results_20261019.md)，
部分錯人例子已排除或改選投手，但仍有混合手臂及更多missing，五球仍degraded。
完整測試999 passed／0 failed／2 skipped（1001項）；未指定範圍時保持原預設。

前段：[大谷翔平五球初次小量試用](docs/phase2_ohtani_pilot_results_20261019.md)：五球均 degraded，0 執行異常。
山本 `pitch_003` 退出後續試用集合，原影片、人工標註與五球歷史評估保留。
人工輸入覆核5/5完成；實際overlay抽樣發現第2球部分追到打者、第5球多處追到裁判／打者。
已保存完整結果與錯例；Phase 2 原自動可靠性未通過的結論保持，尚未進 Phase 3。

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
HSU 已完成 `pitch_003` 全115格12關節覆核，並提供2026-10-05 10:14（台灣）完成時間。
[座標比較報告](docs/phase2_manual_coordinate_comparison_20261005.md)已量測1,205個可見人工點的raw 2D誤差；173個不可觀測點與2個不確定點排除。
87–104格整體偏移的平均誤差為76.90px，高visibility仍可能錯位；事件偵測誤差尚未量測。
[錯位診斷](docs/phase2_pitch003_diagnosis_20261006.md)確認誤差已存在於raw模型輸出，
現有tracking連續性警示漏掉該18格；插值與平滑未修正這段偏移。
診斷包含人工／raw／processed對照圖，未改演算法或門檻。
[警示設計與驗證清單](docs/phase2_warning_design_20261006.md)已固定五支592格及14個已知案例，
[離線影像／幾何實驗](docs/phase2_image_geometry_experiment_20261006.md)已完成五支量測及人工參考比較。
逐格移動差異提供錯位線索，但影像特徵會漂離投手、手臂證據跨片不一致；尚未實作新警示。
[特徵支援驗證](docs/phase2_feature_support_validation_20261006.md)進一步以003人工肩／髖座標核對，
低往返誤差仍無法保證特徵留在可見軀幹；該範圍也不等於完整身體輪廓或身分真值。
[八點人工特徵覆核與下一步方案](docs/phase2_subject_support_proposal_20261006.md)已完成局部對照：
HSU確認003兩格中6點屬其他人／背景、2點屬投手其他部位；小往返誤差仍不保證抓對投手。
Phase 2 baseline與本次有限修復已收尾：**evaluation = COMPLETE WITH KNOWN LIMITATIONS；自動可靠性 = NOT PASSED**。
前次結果見 [Phase 2收尾](docs/phase2_closeout_20261013.md)：五球人工覆核／可用性已重核，
離線警示聯集major TP20/FN1/FP9，尚未正式採用；完整測試619 passed、2 skipped。
原正式流程與局部肘腕限制仍保留；沒有開始Phase3。
使用者隨後要求繼續，[六關節局部警示試驗](docs/phase2_local_joint_warnings_results_20261013.md)
已完成並維持不採用：肘腕涵蓋不足，局部定性GT與可見人工XY的評估用途需分開；完整測試648 passed、2 skipped。
[人工參考校準](docs/phase2_supervised_joint_reference_results_20261013.md)完成五球交叉驗證，
肘 TP/FN/FP 為8/76/1、腕8/63/1；有有限增益，漏報仍多、未正式採用，Phase 2仍NOT PASSED。
完整測試669 passed、0 failed、2 skipped，包含正式五球E2E；正式核心、raw與GT保持原樣。
最新[人工座標角度評估](docs/phase2_manual_angle_assessment_results_20261014.md)補上003的數值誤差：
processed肘50可比格MAE25.0452°、膝106格MAE7.1532°，遮擋不補角度；其他四球未套用這些數字。
定性eligible不代表數值準確；[肢體鏈幾何試驗](docs/phase2_chain_reliability_results_20261014.md)0新增TP、不採用。
續行的[角度差異診斷](docs/phase2_angle_reference_gaps_results_20261014.md)確認003全115格原影片／封存影像／人工圖與XML來源一致，
並保存50肘／106膝共同可比格的三點誤差分解、ray方向與局部敏感度。69／105格腕位移約47／91px已存在於raw；
沒有修改座標、人工GT、門檻或正式核心。
最新[封存ROI角度比較](docs/phase2_saved_roi_angles_results_20261014.md)以同格比較取得局部增益：
VIDEO raw→ROI肘41共同格MAE23.8410°→11.2361°、膝95格7.2015°→4.6703°，同時保留18／40格變差與coverage損失。
ROI需人工初始化，未正式採用。
最新[ROI角度轉換與整合決策](docs/phase2_roi_decision_results_20261015.md)保存690列完整缺值／退步清單，
確認7個同模式有人工參考的新流失皆仍在crop內且低於原gate；角度與逐點誤差亦可能不同方向。
現有固定窄ROI正式不採用；[2×輸入範圍實測](docs/phase2_expanded_roi_results_20261015.md)已完成五球592格，亦不採用。
擴框 selected 550/587（窄框552、全圖IMAGE555）；003共同格肘／膝角度誤差比窄框增加，恢復coverage不代表修正錯位。
Phase 2約定的評估與本次有限修復已交付，停止追加倍率／小規則實驗；自動可靠性仍NOT PASSED，保留已知限制。
2026-10-16 已依授權提供[重大錯位覆核提示](docs/phase2_major_review_hints_20261016.md)：
`analyze-pitch` 新增 `major_review_hints.json`，五球非seed提示2/0/19/5/3，維持major TP20/FN1/FP9。
只適用SHA吻合的封存來源／預測；其他輸入明列未評估，沒有提示不代表可靠，003/104漏報保留。
[肘腕判斷器單次結果](docs/phase2_joint_quality_classifier_results_20261016.md)已完成核准的整片五折：
肘TP/FN/FP為13/71/13、腕20/51/24，兩者皆未達事先規則，不採用，停止調整這組訊號。
兩步授權工作已交付；剩餘缺口記為需要更好的影像或模型資訊，Phase2自動可靠性仍NOT PASSED。
該輪完整測試842 passed、0 failed、2 skipped（844項，含正式五球E2E）；未進Phase3，原核心、門檻與GT維持。
使用者隨後核准的[單次Heavy新資訊試驗](docs/phase2_heavy_information_results_20261016.md)已完成：
肘TP/FN/FP為2/82/1、腕2/69/1，原gate通過錯點只抓回1／2，兩者皆不採用。
正式Full維持，沒有降低門檻、改座標或重訓原分類器；依固定規則停止本輪，Phase2仍NOT PASSED。
該輪完整測試882 passed、0 failed、2 skipped（884項）；新模型對照並不等於自動可靠性通過。
2026-10-17完成使用者核准的[RTMPose原生回應單次試驗](docs/phase2_rtmpose_response_results_20261017.md)：
五球592格與整片五折，肘TP/FN/FP為0/84/4、腕3/68/1，皆未達固定採用規則，停止此訊號。
003可見XY平均誤差有所下降，但自動識別原錯點仍不足；沒有更換正式MediaPipe或修改GT／門檻。
該輪完整測試916 passed、0 failed、2 skipped（918項，含正式五球E2E）；Phase2仍NOT PASSED，未進Phase3。
後續[封存座標診斷](docs/phase2_rtmpose_coordinate_diagnosis_20261017.md)完成003全部十二關節／1,380列：
全片平均均改善，但左右髖多數格退步，major hold外平均誤差也增加；不能直接換正式後端。
原回應訊號維持不採用，沒有新增RTMPose推論、重校準或修改GT；該輪完整suite916 passed、2 skipped。
使用者已核准並完成[原生後端輸出接入第一版](docs/phase2_rtmpose_native_interface_results_20261018.md)：
兩後端各完整592格、原生17／33點、五支新RTMPose overlay及獨立比較，原core／gate／raw／GT保持。
**Native interface integration = PASSED；Phase2自動可靠性仍NOT PASSED**。這是cached接入，不是live模型替換。
最新完整suite **961 passed、0 failed、2 skipped**（963項，含正式五球E2E）；新RTMPose推論／校準／標註0，未進Phase3。
使用者另核准的 [交付資料夾候選讀取器](docs/handoff_reader.md) 已接入 contract v2：
驗 hash、完整解碼、分數 FPS 逐格時間與去重，保存本地待人工覆核候選。
它不自動分析、轉換正式 metadata 或取代山本正式五球，也不改 Phase 2 核心。
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
