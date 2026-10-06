# Phase 2：同模型主體 mask 隔離實驗

日期：2026-10-06。**Phase 2 = IN PROGRESS；mask 實驗尚未通過。**

最新接續：[11個人工位置的比較](phase2_subject_mask_points_20261006.md)已完成，
新run可用11／11個數值，但投手與O位置存在同值1的反例，主體歸屬驗收仍不足。
本文件下方保留先前讀取中止、missing與相容性probe的歷史紀錄。

## 人工參考已完成

HSU 回覆接續八題，並明確確認第86格3號為 P（投手腿部）。
接續八題：**3 T、1 P、4 O**；與原八題按 frame／原圖坐標合併，
最新 **11 個不同位置：3 T、2 P、6 O**。

- [原八題回答](../review_tools/feature_membership/HSU_pitch003_20261006_01.json)。
- [接續首次轉錄](../review_tools/feature_membership/HSU_pitch003_membership_supplement_20261006_01.json)：保留原話及待確認的86／3。
- [接續確認版本](../review_tools/feature_membership/HSU_pitch003_membership_supplement_20261006_02.json)：依本人澄清記錄 P，原 T 仍保留。

五個重複位置採用本次明確回答，兩個類別更新為86／3 O→P、86／4 P→O。
原回答、空白題目快照、歷史比較、解剖關節 GT 均未覆寫。
未提供新的完成時間、confidence 或其他細節時保持 null。
這些是兩格定向診斷位置，不是完整輪廓、隨機樣本或獨立驗收集。

## 實驗方式與實際限制

使用既有 MediaPipe 1.0.1、`pose_landmarker_full.task`、原 VIDEO 模式、
四個 pose 候選上限、原三個0.5信心設定，以及未改動的 PitcherSelector。
只在獨立 runner 開啟 `output_segmentation_masks`，不修改正式 wrapper。
人工回答不供推論使用；固定題目位置只在推論後抽樣。
同一 SDK result 的候選與 mask 按 ordinal 對應，不能沿用舊候選 index。

第一程序在讀取第86格 mask 時中止；另以第0格單格程序重現。
mask 物件格式為 VEC32F1（format 9）、510×628、channels 1、step 2048 bytes。
兩次在 `numpy_view()` 發生相同原生錯誤：

`Check failed: 1 == ChannelSize() (1 vs. 4)`

後續 runner 只讀取安全的 metadata，遇到此格式保持 missing，
不再呼叫會中止程序的讀取路徑。**這是安全記錄，不是相容性修復。**
沒有用 uint8 重解碼、私人指標、假 mask、插值、依賴升級或模型替換補值。

## 結果

| 項目 | 實際結果 |
|---|---|
| 隔離推論影格 | 115／115 |
| 人工位置分母 | 11 |
| 可用 mask 數值 | **0／11** |
| missing | 11，原因 `sdk_float32_numpy_reader_native_failure` |
| mask accuracy／AUC／IoU | null，不可計算 |
| 與原 baseline 的選取 trace | 115 格完全一致 |
| raw landmark 比較 | 3,795 筆、18,975 個數值；差異 0 |
| 投手身份已被證明 | 否；輸出一致可能沿用相同錯誤 |
| 新 warning／cutoff | 無 |

輸出一致不代表 mask 正確，也不代表骨架位置正確。
person mask 與 pose 出自同模型，錯誤可能相關；不能當作獨立身份真值。
本次不產生虛假的 mask 圖或使用背景圈點來修正預測。

## 保存位置

- 原失敗 run：`analysis_results/phase2_subject_mask_pilot_20261006_01/`。
  `failure_record.json` 保存原生錯誤；`producer_at_failed_run.py` 保存第一次執行程式。
- 安全報告：`analysis_results/phase2_subject_mask_pilot_20261006_02/mask_measurements.json`。
- 離線對照：同目錄 `evaluation_01/human_mask_comparison.json`，保存11點分母、
  人工版本鏈、null數值、baseline對照及來源 SHA。
- [首次固定計畫](evaluation_plans/phase2_subject_mask_pilot_20261006.json)／
  [安全報告計畫](evaluation_plans/phase2_subject_mask_pilot_20261006_02.json)。
  首次計畫的 producer SHA 對應封存程式，不是後來加上保護的 current runner。
- `scripts/measure_subject_mask_pilot.py`：不接受真人回答的隔離 producer。
- `scripts/evaluate_subject_mask_pilot.py`：收到真人回答後，離線 join 與完整性核對。

大型影片／產生輸出維持本地保存；文件、計畫與真人轉錄納入 Git。

## 測試與資料完整性

完整 suite：**171 passed／0 failed／0 errors／0 skipped**，包含正式五支影片 E2E。
新增四項測試驗證浮點抽樣、最後像素邊界、越界拒絕，以及遇到故障格式時
不呼叫原生讀取、不把其他格式解讀為假機率。
紀錄在安全報告目錄的 `full_test_suite.log`、`full_test_suite_result.json`。

295份保護檔案、44份既有來源、5份原人工對照來源均未變。
所有330個不重複 evaluator 來源 SHA 再檢查通過；首次計畫與封存程式 SHA 一致。
紀錄：`evaluation_01/evidence_integrity_check.json`。
正式 `src/`、依賴／模型、threshold、信心gate、selector、pose／平滑／插值不變。
測試只確認執行與安全行為，不能代替尚未完成的mask數值與可靠性驗收。

## 當時的下一步範圍（已接續，結果見上方連結）

公開API的最小相容性檢查已通過（見下節）。下一步先在新隔離實驗中使用逐像素
讀取，在原始坐標做固定11點比較，不需更換SDK、模型或正式wrapper。
既有失敗結果保持原樣。
如需不同 SDK，只提出隔離環境的最小驗證方案，先使用相同模型及一格，
檢查 float 數值格式、範圍、坐標與候選對應，不能直接升級正式環境。
取得可用數值後才重做這11個位置的比較；目前不需使用者重答。
不據此改 threshold、tracking／pose 邏輯或推論不可見關節。
Phase 2 尚未穩定；共用交付資料夾接入仍為待辦，Phase 3 未開始。

## 後續相容性檢查：公開逐像素讀取

本機SDK的公開`Image[row, column]`經`MpImageGetValueFloat32`取得單一float；
與`numpy_view()`的`MpImageDataFloat32`整張讀取路徑分開。
官方API列出這個公開索引方式：[Image API](https://developers.google.com/edge/api/mediapipe/python/mp/Image#__getitem__)。
官方原始碼可核對型別與stride處理：[image.cc](https://raw.githubusercontent.com/google-ai-edge/mediapipe/master/mediapipe/tasks/c/vision/core/image.cc)、
[image_frame_util.h](https://raw.githubusercontent.com/google-ai-edge/mediapipe/master/mediapipe/tasks/c/vision/core/image_frame_util.h)。
master不保證與安裝wheel完全相同，因此另以本機實際探測確認；不據master宣稱故障已修復。

- 已知float32陣列：3列、寬2／4／510；含非連續padded row及最後一列／欄。
  全部1,548個公開索引數值精確等於原輸入，差異0。
- 真mask：原`pitch_003`第0格、同模型與設定，VEC32F1、510×628、stride2048、
  non-contiguous。六個合法位置成功讀取有限0–1數值，程序正常結束。
- 與原baseline比對：選取trace及33關節165數值完全一致；295／44／5來源未改。
- 沒有呼叫故障`numpy_view()`、私人pointer、重解碼、變更依賴、裁剪／縮放或使用真人答案。

輸出：`analysis_results/phase2_mask_api_probe_20261006_01/`下的
`known_array_probe.json`、`single_frame_probe.json`、`verification.json`。
保留本機SDK Python source SHA與素材／模型來源SHA。
實驗只用合法坐標；下一步的sampler也必須自行檢查邊界，不測試越界native存取。

這是讀取相容性通過，尚不是11個人工位置的比較，也不是整張mask或投手身份驗證。
歷史0/11報告未覆寫。最新完整suite仍為先前171 passed／0 failed／0 errors／0 skipped；
這次只執行隔離probe與完整性核對，沒有宣稱再次跑完整suite。
