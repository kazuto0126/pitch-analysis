# Phase 2：11個人工位置的同模型遮罩比較

日期：2026-10-06。**點級讀取完成；主體歸屬可靠性仍不足。Phase 2 = IN PROGRESS。**

## 結果

使用同一MediaPipe1.0.1與模型、原始影片尺寸、VIDEO模式、原信心設定及
未改動的PitcherSelector，在新隔離run依序處理`pitch_003`全部115格。
公開`Image[row,column]`成功取得11／11個固定位置的數值；沒有重試故障的
`numpy_view()`，沒有裁剪、縮放、換模型或換依賴。

| 最新人工分類 | 位置數／可用數 | 最小值 | 中位數 | 最大值 |
|---|---:|---:|---:|---:|
| T：可見投手軀幹／衣物 | 3／3 | 1 | 1 | 1 |
| P：投手其他可見部位 | 2／2 | 1 | 1 | 1 |
| O：其他人／背景 | 6／6 | 0.0000000177417 | 0.642770467 | 1 |

五個投手點都是1，但一個O也是1，另一個O約0.999875。
**單靠此mask的點值，無法用單調門檻完全區分這11個人工位置。**
本次沒有選cutoff、生成warning、計算分類accuracy或修改任何驗收門檻。
這是局部的反例，不推算全片錯誤率，也不宣稱整張mask完全無用。
person mask與pose出自同模型，不能當成獨立的投手身份真值。

## 每個位置

以下數值是原始圖像位置的mask值，不是關節visibility、位置誤差或動作分數。
格數從0開始。新題號指接續覆核圖；舊題號指原先八點覆核圖。
重複位置以最新明確回答作對照，舊回答及其比較結果保留。

| Frame／題號 | 最新人工 | mask值 |
|---|---|---:|
| 86／新1（舊1） | O | 0.555323278 |
| 86／新2（舊2） | O | 0.730217657 |
| 86／新3（舊3；本人澄清腿部P） | P | 1 |
| 86／新4（舊4） | O | 0.091486674 |
| 86／新5（新增） | T | 1 |
| 86／新6（新增） | T | 1 |
| 95／舊1 | O | 0.0000000177417 |
| 95／舊2 | O | 0.999874791 |
| 95／新1（舊3） | O | 1 |
| 95／舊4 | P | 1 |
| 95／新2（新增） | T | 1 |

圖表：`analysis_results/phase2_subject_mask_pilot_20261006_03/evaluation_01/point_mask_values.png`。
其列順序按frame／影像x坐標排列，不是候選排名。

## 來源與量測隔離

- [固定量測計畫](evaluation_plans/phase2_subject_mask_points_20261006.json)包含素材、模型、
  SDK Python source、相容性probe及空白問題快照的SHA；沒有預期人工答案。
- Producer只讀兩份產生時的空白問題快照，按原始frame／float x,y去重為11點；
  不使用真人答案建立ROI、選mask、改pose或移動查詢位置。
- Candidate與mask使用同次SDK result的ordinal，數量／尺寸／格式或主體對應不明時保持missing。
- 每點保留四個合法原生像素的值與雙線性權重，總共44筆receipt。
  權重只用於mask點取樣，不改關節插值或平滑。
- 實際HSU回答由離線evaluator接入，保留16個問題別名、版本鏈及五個重複位置的來源。
  沒有自動填人工GT，也沒有用模型輸出去改你的判讀。
- 完整人體輪廓及整張mask未讀取；accuracy／AUC／IoU保持null。
  accuracy沒有既定分類cutoff，IoU沒有完整mask與輪廓參考；不對兩格定向樣本報驗收AUC。

## 核對與測試

- 115格選取trace、3,795筆raw關節、18,975個數值與原baseline完全一致，最大差異0。
  這只證明輸出一致，共同錯誤可能仍然存在。
- 兩張新保存原圖與先前覆核原圖的pixel完全一致。
- 335個來源／計畫SHA核對通過；295份保護檔案、44份既有來源、5份原人工比較來源均未變。
- 獨立唯讀稽核重算11個位置／16個別名、44個native receipt、權重及baseline數值，結果一致。
  這是程式／資料稽核，不是新增人工判斷。
- 完整suite：**176 passed、0 failed、0 errors、0 skipped**，包含五支正式影片E2E。
  新增5項測試檢查公開讀取邊界、零值、非法機率及candidate／尺寸錯配。

正式`src/`、模型／依賴、confidence gate、threshold、PitcherSelector、pose、
關節平滑／插值、五份GT和既有預測全部保持原樣。

## 檔案與後續範圍

輸出：`analysis_results/phase2_subject_mask_pilot_20261006_03/`。

- `mask_measurements.json`：獨立量測、全部115格候選trace、11點與44筆pixel receipt。
- `frame_0086_raw.png`、`frame_0095_raw.png`：新run原圖，未加模型或人工標記。
- `evaluation_01/human_mask_comparison.json`：真人版本鏈、逐點對照、類別描述統計及baseline核對。
- `evaluation_01/evidence_integrity_check.json`、`point_mask_values.png`：完整性核對與靜態圖表。
- `full_test_suite.log`、`full_test_suite_result.json`：完整測試紀錄。

歷史`_01`讀取中止、`_02`全部missing及單格相容性probe都保留。
實驗程式為`scripts/measure_subject_mask_points.py`、`scripts/compare_subject_mask_points.py`；
歷史producer／evaluator不改，沒有將實驗接到正式pipeline。

下一步先依既有人工參考，提出如何補充「主體是否仍屬投手」的影像證據與驗證範圍；
不能直接把本次mask高值當成身份正確，也不能調cutoff掩蓋這個同值反例。
暫不加新模型、新投手或新GUI。Phase 2尚未穩定，交付資料夾接入待辦尚未到達。
到達該待辦時依使用者要求先停止回報；Phase 3未開始。
