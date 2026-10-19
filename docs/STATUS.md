# 進度摘要

更新：2026-10-19（台灣）。[完整狀態](current_status.md)；[目前工作：第二位投手試用](phase2_next_dataset_20261019.md)。

**Phase 1 = PASSED；Native interface integration = PASSED；Phase 2 自動可靠性仍 NOT PASSED。**

## 最新：排除 pitch_003，開始大谷翔平五球試用

使用者已選定大谷翔平的一批五球。後續山本工作集合只含 `001`、`002`、`004`、`005`，
四對工作副本已建立於 `input/yoshinobu_yamamoto/phase2_active_20261019/`。
`003` 原影片與全部人工／模型證據保留，退出新試用集合；原五球評估分母與 NOT PASSED 結論不變。

本次只處理交付索引中的 `20261010T110737Z_RObvkuHpkSo`，先匯入候選、完成人工輸入覆核，
再用現有 MediaPipe 流程試跑通過覆核的球，交付每球結果與限制後停止。
不重開已結束的警示試驗，不新增逐格 GT，不進 Phase 3。
當前進度與停止條件見[本批工作紀錄](phase2_next_dataset_20261019.md)。

大谷五球已成功匯入、0 拒收，重跑新增 0／跳過 5；目前全數候選且人工輸入覆核 pending。
1,873 格通過既有時間檢查；尚未分析或升格。已備妥五球原影片觀看頁。
本輪 handoff 測試 **73 passed、0 failed、2 skipped**（75 項，含新增 6 項）。
本批輸出：`analysis_results/phase2_ohtani_intake_20261019_01/`，先看 `START_HERE.md`。

## 前段：原生17／33點接入第一版完成

使用者核准「第一版接入實作」後，已在`codex/phase2-native-pose-interface`完成獨立原生contract、
封存來源adapter、資料保存、五支RTMPose overlay及003十二關節比較；每後端完整592格。
沒有padding33或fake visibility／presence／Z，原生score保留；新路徑未校準、不套用原gate。
原MediaPipe99個missing欄位完整保留；新RTMPose推論／tracker／校準／標註皆0。
五支overlay已全解碼驗證，並實際檢查每片6個sample frame的繪圖／對齊，不新增人工GT。

45項新測試；完整suite **961 passed、0 failed、0 errors、2 skipped**（963項，76.699秒，含正式五球E2E）。
原重大提示維持2／0／19／5／3；467保護來源與62上游SHA不變。
獨立核對29,600個原生欄位、592份SimCC及003的1,380人工列，座標／score最大差異0。
原core、正式MediaPipe預設、門檻、raw與GT維持；8顆候選未分析或升格。
輸出：`analysis_results/phase2_native_interface_20261018_01/`。

工程接入PASSED，不代表原錯點接受問題已修好；Phase2自動可靠性仍NOT PASSED。
已依核准範圍收尾，不開始live RTMPose、正式模型替換、gate校準或Phase3。

## 前段：原生後端介面方案（後續已核准並實作）

使用者確認「允許規劃後端介面改動」後，已完成接入與驗收方案；這是規劃授權，尚未實作。
建議第一版只接已封存五球的MediaPipe33／RTMPose17資料，新增原生contract、來源adapter、
獨立overlay與比較報告。正式MediaPipe、33點舊流程、selector、gate及人工GT保持。
新模型推論／校準／標註皆0；不padding33或把native score當visibility／presence。
介面接入驗收與Phase2自動可靠性分開；本版完成也不會自動讓Phase2 PASSED。
最小版不需修改既有正式核心；live RTMPose及正式模型替換不在第一版範圍。
本次只修改文件，未重跑測試；最近完整suite仍916 passed／0 failed／2 skipped。
等待使用者確認方案後才實作，未進Phase3。

## 前段：十二關節與漏報原因核對完成

只讀既有輸出完成003全部115格×12關節的對照，沒有重開已拒絕訊號或再跑RTMPose。
十二關節全片平均XY誤差均下降，但左髖67/114格、右髖72/114格退步。
原major hold以外，左髖平均9.1535→13.3563px、右髖7.4754→11.7197px；不能宣稱全面改善。
肘84個漏報中81個有可量測訊號，腕68個中59個有訊號；主要不是都缺座標或都被遮擋。
十個既定界線的訓練來源已追查，沒有重校準、刪可靠列或改用分位數。

1,380列／十二關節統計獨立重算一致；1,205可見／173不可觀測／2不確定維持。
該輪完整suite為**916 passed、0 failed、0 errors、2 skipped**（918項，60.560秒，含正式五球E2E）。
原trial決策、正式core／gate／raw／GT及8顆pending候選保持；Phase2仍NOT PASSED，未進Phase3。
輸出：`analysis_results/phase2_rtmpose_coordinate_diagnosis_20261017_01/`。
若下一段要使用原生17點座標，需先確認新的後端／contract工作範圍，不能偽裝成現行33點輸出。

## 前段：RTMPose原生回應單次驗證完成，不採用

已完成使用者核准的隔離相容性、五球592格原生SimCC量測、整片五折及獨立核對。
相容性guard誤拒ONNX符號維度已在推論前修正並另存凍結；實際17點shape仍嚴格驗證。
肘TP/FN/FP **0/84/4**、腕 **3/68/1**；gate通過錯點只抓回0／3，
未達固定採用條件，依規則停止此訊號，不接正式流程或追加調參。

003可見XY同集合：肘平均27.7461→7.3101px，腕26.6556→16.8405px。
這是單片座標的局部改善；自動識別原錯點仍失敗，其他四片精確誤差保持null。
003/104及[可見性來源差異](phase2_visibility_gap_audit_20261016.md)保留，沒有修改人工GT。

該輪完整suite：**916 passed、0 failed、0 errors、2 skipped**（918項，54.701秒，含正式五球E2E）。
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
