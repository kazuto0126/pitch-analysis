# Phase 2：幾何支持警示試驗結果

2026-10-11（台灣）。**新提示實際抓到7格舊漏報，新增誤報0；Phase 2 = NOT PASSED。**

依[事前規則](phase2_movenet_support_plan_20261011.md)，只讀已封存native六槽、CSRT及原raw／capture。
592格全部保存，587非seed格評估；pose／tracker新增呼叫0。人工GT只進比較端。
沒有分數門檻、像素容忍、padding搜尋、時間擴張或GT觸發條件。

## 原screen、新提示及聯集

下表欄位皆為TP／FN／FP；人工major正例21格、負例566格，沒有人工排除。
原screen的TN557與先前592格報告TN562相差五個frame0；TP／FN／FP不變。

| 影片 | 原tracking screen | 新幾何衝突提示 | 原screen＋新提示 | 新提示證據不足 |
|---|---:|---:|---:|---:|
| pitch_001 | 0/0/2 | 0/0/0 | 0/0/2 | 3 |
| pitch_002 | 0/0/0 | 0/0/0 | 0/0/0 | 2 |
| pitch_003 | 0/18/2 | 7/11/0 | 7/11/2 | 0 |
| pitch_004 | 2/0/3 | 0/2/0 | 2/0/3 | 2 |
| pitch_005 | 1/0/2 | 0/1/0 | 1/0/2 | 12 |
| 合計 | 3/18/9 | 7/14/0 | 10/11/9 | 19 |

新提示precision=7／7、recall=7／21（33.33%）、FPR=0／566，
有判斷568／587（96.76%）；19格證據不足含3正例、16負例，全部保留在主要FN／TN分母。
這是本批已知開發資料的計數，零新增FP不是未見資料的保證。
新提示在003／93–95、97–100發出；原重大18格由全部漏掉變成抓到7、仍漏11。
首次提示在93，距87起點6格；沒有把提示回填到87或擴張成整段。

聯集保留全部原screen警示，TP3→10／FN18→11／FP9維持。
它不替代原break提示：004／75–76與005／54的3格中斷仍由原screen抓到。
沒有把native幾何支持叫作關節可靠、沒有將歧義強制選成某一人，沒有修正原raw座標。

## 與既有關節跳點的描述性比較

另列事後診斷，未改任何jump設定或新增policy：

| 提示集合 | TP | FN | FP |
|---|---:|---:|---:|
| 原screen＋原六關節jump端點 | 13 | 8 | 56 |
| 同集合再加新幾何提示 | 16 | 5 | 56 |

剩餘漏報為003／90、92、96、102–103；56個major目標外提示仍保留。
jump提示回答局部跳動，並非已校準major detector；不能以此聯集宣稱自動驗收通過。
原screen＋幾何的11漏報為003／87–92、96、101–104，沒有用診斷聯集掩蓋它。

## 來源修正與測試

最初offline evaluator `_01`誤以為tracking逐格有timestamp_ms，在寫輸出前停止。
實際tracking只有frame_index；`_02`改核對已綁定capture的時間及selection status一致性。
原碼snapshot、失敗log與原計畫保存；producer、規則、GT及量測完全不變，沒有重推論或重產生警示。
新增3個回歸測試覆蓋這個來源契約差異。

最終完整suite **526 passed／0 failed／0 errors／2 skipped**，
528項、117.824秒，含正式五球E2E；兩skip為Windows符號連結限制。
全輪56新增測試包含34項模型比較及22項support producer／evaluator。
374保護來源／62上游引用、正式五球、raw、人工GT5／5及production src不變。
警示592格由另一核對程序逐格重算相符；人工比較逐片重算相符。

## 狀態與接續點

**Phase 2 = NOT PASSED。** 這次有實際提示改善，但未修復剩餘漏報、局部手臂誤連及自動身份證據不足。
MediaPipe維持正式backend，沒有將此試驗接入核心或將MoveNet score當visibility。
下一步聚焦剩餘11格的獨立影像支持與局部關節警示，先定位為何native框仍支持錯誤raw，
再決定規則；不調整本試驗邊界使已知資料通過，也不重做已完成的人工覆核。
交付八球維持candidate／pending；Phase3未開始。

輸出：`analysis_results/phase2_movenet_cohort_20261011_01/support_measurements/`與`support_evaluation/`；
`existing_joint_cue_union_02.json`為另列的描述性聯集，`final_audit.json`保存核對與測試。
原事後聯集`_01`按二元cue索引列覆蓋；`_02`另保留幾何證據不足，TP／FN／FP／TN不變，原檔保存。
