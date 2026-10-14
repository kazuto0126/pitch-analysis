# 進度摘要

更新：2026-10-14（台灣）。詳見 [完整狀態](current_status.md)。

**Phase 1 = PASSED。Phase 2 evaluation = COMPLETE WITH KNOWN LIMITATIONS；Phase 2 自動可靠性 = NOT PASSED。**
未進入 Phase 3，正式五球、raw、人工GT、既有核心與門檻原樣。

## 已完成

- 山本由伸正式五支單球的 Phase 1 E2E；五球592格 Phase 2 baseline、人工定性覆核5/5。
- Tsai標點／HSU覆核的003完整115格12關節：1,205可見XY、173不可觀測、2不確定；遮擋不猜點。
- [角度來源診斷](phase2_angle_reference_gaps_results_20261014.md)：原MP4、封存RGB、人工PNG與XML115格一致，時間差0ms；50肘／106膝共同格三點誤差分解完成。
- [最新封存ROI比較](phase2_saved_roi_angles_results_20261014.md)：無新推論，115保存／114非seed格，四流同格與缺值評估完成。VIDEO raw→ROI肘41格MAE23.8410°→11.2361°、膝95格7.2015°→4.6703°。
- [交付讀取器](handoff_reader.md) contract v2、SHA／解碼／時間／去重／本地覆核已完成；8球仍候選pending、未分析。

## 最新驗證與保存

- 完整測試：**738 passed、0 failed、0 errors、2 skipped**（740項／72.758秒），包含正式五球E2E。
- 兩skip：Windows無法建立符號連結；新ROI評估15項測試、同輪來源診斷16項。
- 原ROI的115格像素／映射／selector與1,368逐點列重建一致；新四流角度另做獨立重算。
- 374保護來源、62上游、原592次MoveNet attempt、正式五球／raw／GT／core均維持。
- 最新輸出：`analysis_results/phase2_saved_roi_angles_20261014_01/`；前一診斷：`analysis_results/phase2_angle_reference_gaps_20261014_01/`。

## 未完成與已知問題

- 自動可靠性尚未通過：既有局部肘腕錯位、003/104 major漏報、遮擋及原警示FP仍保留；離線試驗未正式採用。
- ROI的角度平均增益不是全面改善：肘18／41、膝40／95共同格變差，中位數增加；膝改善集中原major段。
- ROI有人工參考且有值的肘41/51、膝98/113，少於VIDEO raw的49/51、103/113；缺值不能算修好。
- 69肘ROI仍差62.5092°，105肘below gate保持null；原major／feature限制不解除。
- ROI依賴人工初始化，003數字不外推其他四球或投手；人工XY數值不確定性、事件偵測誤差尚未量化。005獨立peer事件補充仍分開pending，canonical uncertain有效。

## 下一步與邊界

保留ROI為有證據的修復方向；後續整合需列明人工初始化、crop邊界／missing、原gate、來源隔離與同格評估。
目前不改正式pose／tracking核心、不重標GT、不新增通過線，不再調已否證的比例小規則。
交付接入已完成候選範圍；正式使用外部素材須人工確認，不能取代現有五球。禁止自動進Phase3。
