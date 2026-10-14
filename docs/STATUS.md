# 進度摘要

更新：2026-10-15（台灣）。詳見 [完整狀態](current_status.md)。

**Phase 1 = PASSED。Phase 2 evaluation = COMPLETE WITH KNOWN LIMITATIONS；Phase 2 自動可靠性 = NOT PASSED。**
未進入 Phase 3，正式五球、raw、人工GT、既有核心與門檻原樣。

## 已完成

- 山本由伸正式五支單球的 Phase 1 E2E；五球592格 Phase 2 baseline、人工定性覆核5/5。
- Tsai標點／HSU覆核的003完整115格12關節：1,205可見XY、173不可觀測、2不確定；遮擋不猜點。
- [角度來源診斷](phase2_angle_reference_gaps_results_20261014.md)：原MP4、封存RGB、人工PNG與XML115格一致，時間差0ms；50肘／106膝共同格三點誤差分解完成。
- [封存ROI比較](phase2_saved_roi_angles_results_20261014.md)：無新推論，115保存／114非seed格，四流同格與缺值評估完成。VIDEO raw→ROI肘41格MAE23.8410°→11.2361°、膝95格7.2015°→4.6703°。
- [交付讀取器](handoff_reader.md) contract v2、SHA／解碼／時間／去重／本地覆核已完成；8球仍候選pending、未分析。

## 最新：窄ROI整合方向已結案

- [角度轉換結果](phase2_roi_decision_results_20261015.md)：690保存／684非seed列，availability與人工參考可算性分開，原缺值／理由／三點差值完整保留。
- 與同模式IMAGE比，有人工參考的肘4格新流失、3格新增有值；膝3／18。7個流失格人工點皆在框內，selected仍低gate；不能把流失都說成被裁掉。
- 肘46／55／61、膝50／94／111的三點pixel誤差全下降，角度誤差仍增加；單一角度不認證骨架對位。
- [整合決策](phase2_roi_integration_decision_20261015.md)：目前固定窄ROI不接production；五球可用性損失與單片角度增益一起納入。
- 下一次2×中心擴框、同MediaPipe的單次五球方案已寫，最多592pose／0tracker，尚未執行；本輪0新推論。

## 最新驗證與保存

- 完整測試：**751 passed、0 failed、0 errors、2 skipped**（753項／54.578秒），包含正式五球E2E。
- 兩skip：Windows無法建立符號連結；本輪新增13項角度轉換工具測試。
- 原ROI的115格像素／映射／selector與1,368逐點列重建一致；新690列轉換／缺值／三點誤差與分層另做獨立重算。
- 374保護來源、62上游、原592次MoveNet attempt、正式五球／raw／GT／core均維持。
- 最新輸出：`analysis_results/phase2_roi_decision_20261015_01/`；昨日比較：`analysis_results/phase2_saved_roi_angles_20261014_01/`。

## 未完成與已知問題

- 自動可靠性尚未通過：既有局部肘腕錯位、003/104 major漏報、遮擋及原警示FP仍保留；離線試驗未正式採用。
- ROI的角度平均增益不是全面改善：肘18／41、膝40／95共同格變差，中位數增加；膝改善集中原major段。
- ROI有人工參考且有值的肘41/51、膝98/113，少於VIDEO raw的49/51、103/113；缺值不能算修好。
- 69肘ROI仍差62.5092°，105肘below gate保持null；原major／feature限制不解除。
- ROI依賴人工初始化，003數字不外推其他四球或投手；人工XY數值不確定性、事件偵測誤差尚未量化。005獨立peer事件補充仍分開pending，canonical uncertain有效。

## 下一步與邊界

現有固定窄ROI不採用，不重跑同設定或繼續調小規則。下一次有限輸入範圍實驗只有提案，未開始；正式整合仍需人工初始化、crop／missing、原gate、來源隔離與同格證據。
目前不改正式pose／tracking核心、不重標GT、不新增通過線，不再調已否證的比例小規則。
交付接入已完成候選範圍；正式使用外部素材須人工確認，不能取代現有五球。禁止自動進Phase3。
