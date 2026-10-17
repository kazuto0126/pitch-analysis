# 進度摘要

更新：2026-10-17（台灣）。[完整狀態](current_status.md)；[RTMPose單次結果](phase2_rtmpose_response_results_20261017.md)。

**兩步授權工作已完成。Phase 1 = PASSED；Phase 2 自動可靠性仍 NOT PASSED。**

## 最新：RTMPose原生回應單次驗證完成，不採用

已完成使用者核准的隔離相容性、五球592格原生SimCC量測、整片五折及獨立核對。
相容性guard誤拒ONNX符號維度已在推論前修正並另存凍結；實際17點shape仍嚴格驗證。
肘TP/FN/FP **0/84/4**、腕 **3/68/1**；gate通過錯點只抓回0／3，
未達固定採用條件，依規則停止此訊號，不接正式流程或追加調參。

003可見XY同集合：肘平均27.7461→7.3101px，腕26.6556→16.8405px。
這是單片座標的局部改善；自動識別原錯點仍失敗，其他四片精確誤差保持null。
003/104及[可見性來源差異](phase2_visibility_gap_audit_20261016.md)保留，沒有修改人工GT。

最新完整suite：**916 passed、0 failed、0 errors、2 skipped**（918項，54.701秒，含正式五球E2E）。
34項新合成測試；467目前保護來源及62上游SHA不變。
正式MediaPipe／pose／tracking／gate／raw／GT與五球保持；8交付候選仍pending、未分析。
輸出：`analysis_results/phase2_rtmpose_response_20261016_01/`。
**Phase2 evaluation已完成；自動可靠性仍NOT PASSED。** 本輪到此停止，未進Phase3。

## 前輪：Heavy新資訊單次驗證已完成，不採用

使用者要求「繼續修正直到phase2通過」後，已按[固定範圍](phase2_new_information_proposal_20261016.md)
完成五球592格單次MediaPipe Heavy離線量測與整片五折；沒有更換正式模型。
肘TP/FN/FP **2/82/1**、腕 **2/69/1**，皆未達事先規則。
原gate通過錯點只抓回1／2，同時各提示1個好點，少於原sample-maximum的7／8。
003/104仍漏報；新資訊不足以讓Phase2通過，依規則停止本輪，不追加界線或模型搜尋。

該輪完整suite：**882 passed、0 failed、0 errors、2 skipped**（884項，含正式五球E2E）。
436保護來源及62上游SHA維持；原13特徵分類器、raw、GT、core與8顆候選保持。
新輸出：`analysis_results/phase2_heavy_information_20261016_01/`。
歷史提案保留原SHA；核准與實際執行另存manifest，不再待核准。

## 已交付

- 正式五球592格baseline、5/5人工定性覆核、003完整人工XY及品質／追蹤評估。
- 第一步：分析輸出新增重大錯位覆核提示，維持major TP20/FN1/FP9；003/104仍為已知漏報。
- 第二步：固定13特徵＋9missing indicators、L2邏輯迴歸、整片五折一次驗證；10模型均正常收斂，未調參或重FIT。
- 第一階段提示繼續提供；第二步分類器只保存離線結果，不接正式流程。

## 前輪13特徵分類器決策：兩關節皆不採用

肘TP/FN/FP **13/71/13**，腕 **20/51/24**。
肘未達TP≥17／FP≤1，改善也未分布兩支非003；腕未達TP≥27／FP≤1／非003TP≥23。
依核准規則停止調整這組訊號，缺口記為 **需要更好的影像或模型資訊**。

在原gate已通過的點中，新提示抓回肘13／腕16錯點，同時額外提示肘9／腕21好點。
原gate支持中未被新提示標出的數目為453/477、309/350；人工可靠保留376、245。
這是覆核負擔試算，原資料、座標與可用狀態未被修改。

## 前輪13特徵分類器驗證與保存

- **842 passed、0 failed、0 errors、2 skipped**；844項／56.411秒／exit0，含正式五球E2E。
- 55項新增合成測試；2skip為Windows符號連結能力。
- 獨立核對1184特徵列、15392值、10模型、1168有效OOF分數與3522筆screen計數。
- FEATURE讀GT0、APPLY讀人工檔0，每fold FIT只讀另外4片GT。
- 380目前保護來源及62上游SHA維持；原pose/tracking、gate、raw、GT、正式五球與第一步證據保留。
- 8交付候選仍candidate/pending，未分析／升格。
- 前輪輸出：`analysis_results/phase2_joint_quality_classifier_20261016_01/`。

## 尚未通過與停止點

自動提示仍會漏掉已知關節錯位，003/104也仍未修復；無提示不能當成可靠。
依既有Phase2要求維持NOT PASSED，沒有新增零錯誤、更多標註或新資料集的收尾條件。
本次兩步工作及後續核准的單次Heavy試驗均已收尾，沒有降低門檻或冒稱通過。
不再調整這些訊號或追加小規則，未進Phase3。
