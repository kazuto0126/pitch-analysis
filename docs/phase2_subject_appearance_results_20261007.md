# Phase 2：固定衣物外觀量測結果

日期：2026-10-07（台灣）。**Phase 2 = IN PROGRESS。**

## 本輪做到哪裡

依[追加影像證據方案](phase2_subject_appearance_plan_20261006.md)，
只對正式 `pitch_003` 做隔離量測；沒有改正式 pose、PitcherSelector、
confidence gate、threshold、插值／平滑或人工 ground truth。

- 全 115 格保留；兩個來源候選在原有 gate 最早合格的第 0 格提出。
- 兩塊固定 9×9 灰階圖像；來源矩形為 `[191,262,9,9]` 和 `[191,303,9,9]`。
- 來源四角均在 raw 軀幹凸包內，數值可用；不更換來源、不更新 template。
- 每格搜尋整張原圖，保存前三個完整不重疊候選、原始相似值、同分數量、
  競爭分差與 score-map hash；不把最佳位置當成投手身份。
- 230 筆 patch/frame 量測皆有數值，完整重算逐格候選及 hash 相符。
- 人工資料只在量測保存後由 evaluator 讀取；producer 僅開啟六份已綁定的影片／模型記錄。
- 106 格有四肩／髖皆可見的人工幾何 proxy；70–78 的 9 格缺人工右肩，
  不補點、不刪除。可用量測與可用人工參考分母分開報告。

來源 patch 的**整塊歸屬尚未由 reviewer 確認**；raw gate、人工關節位置或凸包
不能取代這項確認。人工點仍為 1,205 visible／173 not_observable／2 uncertain，未修改。

## 描述性結果

下表只問「最高相似候選中心是否在人工四點軀幹凸包內」，
**不是投手身份準確率，也不是關節位置誤差**。
衣物 patch 中心不是解剖關節；凸包外也不一定是別人或背景。

| 量測 | patch 1 | patch 2 |
|---|---:|---:|
| 原始影格分母／數值可用 | 115／115 | 115／115 |
| 人工 proxy 可用／缺少 | 106／9 | 106／9 |
| 最佳中心在 proxy 內／外 | 33／73 | 30／76 |
| 已確認重大錯位 87–104：內／外 | 1／17 | 0／18 |
| 其餘格有 proxy 的 88 格：內／外 | 32／56 | 30／58 |
| 全片最高相似值中位數 | 0.929187 | 0.945092 |
| 全片第一／第二候選分差中位數 | 0.011388 | 0.013164 |

「其餘格」指沒有已確認 major failure 的 97 格，其中 88 格有 proxy；
不代表其餘關節全部準確。87–104 是 evaluator 在量測後才接入的人工背景，
不參與來源、搜尋或調參。

高相似值與接近的競爭候選普遍存在，無重大錯位參考的區段也常有最佳位置落到 proxy 外。
因此這次**無法建立可信的衣物主體追蹤或警示 policy**。
沒有挑相似值／位移／margin 門檻，沒有生成 identity 或 warning 判定，
沒有把「115 格有數值」寫成「115 格追對投手」。

## 本候選的停止位置

本輪有界量測與描述性比較完成，方向記為**證據不足、未採用**。
最多兩塊來源 patch 的原圖與放大圖已保存，尚無新人工答案；僅確認來源歸屬
也不能證明後面 115 格的匹配都正確。不為此擴大人工重標，也未延伸跑 001／002。
accuracy、warning recall、identity-switch sensitivity 均保持 null，沒有陽性 identity-switch 參考。

若繼續此方向，需先提供足以核對來源及後續匹配歸屬的證據與固定評估方案；
不能用現有中心 T/P/O 擴成整塊 patch 真值、把 score 逐格正規化為 confidence，
或依已知錯位區段調參。本輪不選新模型、不自動開始其他功能。

## 執行與來源保護

初次 preflight 把整數毫秒 raw CSV 與小數毫秒影片 PTS 作嚴格相等核對，
因此在建立量測輸出前停止。已保存當時程式及原因。
修正為同 frame index 的 CSV 時間必須等於原 capture 整數時間，
capture 必須等於原影片 PTS 四捨五入值；結果仍保留影片原始小數 timestamp。
這是來源對齊檢查，沒有改原 CSV、capture 或分析參數。

- [初次固定計畫](evaluation_plans/phase2_subject_appearance_execution_20261007.json)：保留 preflight 歷史。
- [成功執行前重新固定的計畫](evaluation_plans/phase2_subject_appearance_execution_20261007_02.json)：
  綁定 runtime、兩支實驗程式、測試與來源；量測後未改程式。
- 實驗：`analysis_results/phase2_subject_appearance_20261007_01/`。
- 原 preflight：`analysis_results/phase2_subject_appearance_20261007_00_preflight/`。
- 保護清單 295／44／5／335 份 hash 分別核對通過；六份量測來源、九份 evaluator-only
  來源、原圖／patch hash 及全部逐格量測 receipt 也核對通過。
- 獨立唯讀覆核亦確認全部230筆量測可重算、350份不重複來源檔案保持原樣。
- 既有 GT、人工回覆、raw prediction、過去結果、模型與正式程式保持原樣。

主要輸出：

- `appearance_measurements.json`：來源像素、逐格相似候選與可用性。
- `evaluation_01/appearance_comparison.json`：人工幾何背景、完整分母與限制。
- `evaluation_01/evidence_integrity_check.json`：來源未變與逐格重算核對。
- `source_frame_raw.png`、`source_frame_patch_context.png`、`source_patch_1/2*.png`：來源候選的原始影像證據。
- `full_test_suite.log`、`full_test_suite_result.json`：完整測試紀錄。

最新完整測試：**185 passed、0 failed、0 errors、0 skipped**，包括正式五支影片 E2E；
共約53.66秒。新增9項測試覆蓋來源邊界／退化、最早gate不fallback、常數分母、
同分競爭、原始時間對齊、圖片保存失敗、receipt竄改及人工參考缺失。
最初單項測試的系統暫存權限錯誤已以記憶體CSV fixture排除，完整測試在專案獨立暫存完成。

## Phase 2 剩餘工作與時間估計

已完成的是 baseline、五片定性人工覆核、003 可見座標比較與多個有界診斷。
**尚未完成的是可信警示驗收**；現有連續性警示仍漏掉 003 的重大錯位。

1. 找到有可核對主體證據的警示方案，分開「錯位」「看不見」「證據不足」。
   本輪固定小 patch 量測不足以完成此步；不能承諾下一個候選就有效。
2. 固定警示決策後，對五片全部 592 格量測漏報、正常動作誤警、
   決策／棄權覆蓋率、track break 與逐關節範圍；經人工參考核對，保留缺值分母。
   已知素材是 development/regression，沒有新增 holdout 或 identity-switch 正例可宣稱泛化。
3. 補完 `pitch_005` 啟動與最高抬腿的獨立人工事件覆核；不確定可保留範圍，
   不強迫精確 frame，也不宣稱目前已建立自動事件準確率。
4. 依實際證據記錄 Phase 2 驗收結論、跑完整測試、整理文件與 checkpoint。
   警示驗收尺度需明確記錄；不自行把「3段各有至少一次warning」當成完整逐格通過。

規劃估計：若下一個主體證據方案可驗證且人工回覆順利，預留約 **2–4 個工作回合**
完成方案、五片對照與收尾；以每天能進行一段覆核／開發計，約 **2–4 個工作日**。
這是安排工作的粗估，不是完成期限；若新證據仍無法區分投手與其他人，需追加迭代，
不能用降低標準或程式執行成功替代驗收。單次完整測試先前約 42–171 秒，
主要剩餘時間來自證據與人工確認，不是跑測試。

Phase 2 穩定、輪到 `D:/project/pitch-video-handoff` 接入待辦時，
**先停止回報，等待使用者新的開始指示**；本輪沒有讀取該交付資料夾、沒有進 Phase 3。
