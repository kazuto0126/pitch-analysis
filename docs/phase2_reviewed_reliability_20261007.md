# Phase 2：人工覆核成果變成可用的逐格視圖

日期：2026-10-07。**Phase 2 = IN PROGRESS。**

## 本次可直接使用的改進

五支正式 baseline 都新增兩個輸出，讓 HSU 已完成的人工覆核可以直接查看和讀取：

- `reviewed_overlay.mp4`：原 overlay 旁新增中文狀態面板，逐格顯示人工判讀、
  原模型選取／警示數及六個重要關節的 observed／interpolated／missing。
- `reviewed_reliability.json`：每格、每關節有原人工區間與原因、原始／處理後模型資料、
  使用限制、來源 SHA-256、覆核者和事件紀錄；是可重建的衍生檢視，不是第二套可編輯 GT。

例如 `pitch_003` 87–104 格現在會顯示「人工確認：重大骨架錯位」，
`pitch_004` 75–76 和 `pitch_005` 54 格顯示人工確認的中斷。
其他格也逐關節顯示不可靠／無法觀測，不用再從長篇覆核筆記找回答案。
六關節的限制與重大失效範圍各自保存，不把整體異常強迫改成每個關節都錯。

這是**人工覆核後**對已知五支素材的改進。自動 tracking／pose 結果沒有修正；
人工標記不輸入 inference、ROI、選取、座標修補或新警示模型。
既有 `analyze-pitch` 不會自動讀取此側檔。它可供現在覆核與後續資料使用判斷，
不宣稱新影片也能自動得到同等人工結論。

## 開啟方式

輸出：`analysis_results/phase2_reviewed_baseline_20261007_01/`。

先開同目錄 `START_HERE.md`，選影片的 `reviewed_overlay.mp4`。
影片中左方是原骨架，右方是覆核狀態；完整原因和不確定事件在該片 JSON。
使用 H264／yuv420p／faststart，解決原 MP4v 在部分瀏覽器不易播放的問題。
原 overlay 區域的尺寸、位置、骨架不改；編碼前像素逐格相同。
H264 是有損壓縮，因此**不宣稱新 MP4 解碼像素逐位相同**。

## 五片實際輸出

| 影片 | 格數 | 六關節列數 | 人工 reliable | 人工 unreliable | 人工 not_observable | 人工重大失效格 |
|---|---:|---:|---:|---:|---:|---:|
| pitch_001 | 87 | 522 | 411 | 30 | 81 | 0 |
| pitch_002 | 175 | 1,050 | 980 | 2 | 68 | 0 |
| pitch_003 | 115 | 690 | 588 | 73 | 29 | 18 |
| pitch_004 | 114 | 684 | 619 | 47 | 18 | 2 |
| pitch_005 | 101 | 606 | 559 | 41 | 6 | 1 |
| 合計 | 592 | 3,552 | 3,157 | 193 | 202 | 21 |

表格是原人工標籤的完整展開，**不是自動偵測準確率、總分或影片排名**。
3 格人工 track break 已包含在 21 格重大失效內，不重複相加。
五片沒有人工 confirmed identity switch，不能據此量測 switch recall。

## 使用限制如何明確保留

- `human_raw_overlay_review`：直接保存原人工區間、狀態、原因、confidence／note。
  `not_observable` 表示无法核對，不代表已確認位置錯誤，也不推定一定被身體遮擋。
- `model_state`：原模型品質處理後的可用性狀態；observed 不代表人工可見或位置正確。
- `use_disposition`：針對後續使用處理後點位的保守檢視。原人工不可靠、不可觀測、
  不確定、主體不明或重大失效各附原因；missing 沒有可用處理後座標。
- 人工 raw reliable＋模型 interpolated：保留 raw 人工判讀，但處理後插值仍為未覆核。
  不把人工可靠性直接套給插值或 visualization median。
- 人工 reliable＋模型 observed，且無已確認整體失效：只代表有原人工定性對位證據。
  不宣稱精確像素容忍度、所有33點正確、真實3D或未見影片泛化。
- 六個角色依 metadata 的投球側決定，不加入山本專用映射或補點規則。
- 人工事件 exact／range／uncertain 逐項保留；005未確認事件不升級成精確答案。

## 實作與驗證

- 新工具：`scripts/export_reviewed_reliability.py`。以完成的 full-profile GT 為前提，
  來源 hash、投手／pitch ID、metadata、frame count、原時間戳、投球側與保存的模型狀態
  須一致；拒絕 unreviewed template、混片、漏格、狀態不符與覆寫既有輸出。
- [執行前固定計畫](evaluation_plans/phase2_reviewed_export_20261007.json)：綁定五片所有來源、
  工具／測試、既有 FFmpeg／ffprobe、字型與輸出範圍；執行後再次核對。
- 新增12項測試，涵蓋 inclusive 邊界、不可見／錯位區分、插值未認證、缺失、
  major與identity獨立、主體未確認、左右手映射、來源防改與完整衍生資料／時間對齊。
- 原片、原 overlay、新 overlay 全部逐格解碼核對格數／尺寸／FPS，
  新影片均為 H264/yuv420p；全部592格生成時驗證原 overlay 區域像素未修改。
- 實際視覺檢查五片的關鍵畫面：001/002一般格、003重大錯位、004/005中斷及插值。
  這是新增版面／狀態顯示檢查，沒有再替人工新增對位判斷。
- 完整測試與獨立唯讀核對結果保存在同輸出目錄。
  **203 passed／0 failed／0 errors／0 skipped**，包含正式五片真影片E2E，約47秒。
  獨立核對通過全部592格／3,552列、五片影片和22張無損PNG原overlay區域；
  342份不重複綁定／歷史保護來源未變。資料狀態共3,133 observed、63 interpolated、
  356 missing，沒有補點或把missing刪出分母。

可在相同、來源相符的工作目錄用以下方式重建到**新的**結果目錄：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts/export_reviewed_reliability.py --plan docs/evaluation_plans/phase2_reviewed_export_20261007.json --output analysis_results/<new_reviewed_output>
```

計畫綁定目前電腦既有的編碼器與字型；其他電腦應先建立自己的來源相符計畫。
不用安裝新模型，不能改歷史計畫或覆寫已有分析／人工紀錄。

## 剩餘工作

五片 canonical GT 維持5/5 reviewed。此輸出可用，但原自動可靠性警示的漏報／誤警
尚未修好；Phase 2不宣告PASSED。同學005獨立事件補充仍待實際回傳，
不要求HSU重做已保存內容。

[座標可用性／誤差對照](phase2_observation_accuracy_20261007.md)與
[驗收範圍](phase2_acceptance_review_20261007.md)說明剩餘限制。
共用交付資料夾接入仍未開始；Phase 2穩定、輪到該待辦時先停止回報。
沒有進入Phase 3。
