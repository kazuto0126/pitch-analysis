# 進度摘要

更新：2026-10-20（台灣）。[完整狀態](current_status.md)；[最新剩餘問題處理](phase2_ohtani_remaining_limits_20261020.md)。

**Phase 1 = PASSED；Native interface integration = PASSED；Phase 2 自動可靠性仍 NOT PASSED。**

## 最新：23格缺失復原未解決主要限制，未接入正式流程

使用者要求繼續修正後，完成003／004資料鏈查核及004／005共23個原missing格的同模型獨立重新偵測。
003／004肘角缺失中，97.19%／95.40%涉及右腕低visibility；時間、側別、座標與原gate計算沒有發現bug。
23格重新偵測的原selector重播僅多找回5格，最長gap仍3／13，沒有解除原失敗原因。
因此不接入正式capture、不改正式數字、不追加crop／門檻搜尋；來源raw與GT保留。
正式結果仍001／002 pose gate通過，003／004／005 degraded，Phase2自動可靠性仍NOT PASSED。

輸出：`analysis_results/phase2_ohtani_recovery_20261020_01/`；
[處理結果與停止決定](phase2_ohtani_remaining_limits_20261020.md)、[同投手替代素材需求](phase2_ohtani_replacement_input_needs_20261020.md)。
本輪無產品／測試碼變更，未重跑suite；同版最近結果1016 passed／0 failed／2 skipped。
使用者已明確選定「先補較清楚的大谷素材」。本次目標新增至少3顆不同完整投球，依
[明確供片需求](phase2_ohtani_replacement_input_needs_20261020.md)及contract v2交付。
最新索引仍只有已分析的5球批次，尚無新大谷批次；待新批次公布後，再候選匯入、人工輸入覆核、各跑一次。
001／002與全部歷史結果保留；可選live後端不在本次路線，未開始新模型或Phase3。

## 前段：大谷五球固定範圍試用完成，兩球通過 pose gate

001–004各推論一次、005沿用前次，產品程式／模型／門檻與GT不變。
相較全畫面＋軀幹限制，五球選中1448→1842/1873，missing425→31；
最長gap依序1／1／1／3／13，肘角raw coverage59.12／62.58／41.00／41.71／59.49%。
001、002品質success但仍needs_event_review；003／004肘角不足，004另有3格gap，005保留13格收尾缺口。
001自動input quality仍因followthrough_unverified而degraded，002為accepted，未自動升格素材。

實際檢查57格前後overlay（114張），原錯人／missing例子有改善；局部關節準確度仍有限，未新增人工GT。
新四片overlay全解碼，504保護檔案SHA不變；五球觀看入口在
`analysis_results/phase2_ohtani_crop_cohort_20261019_01/before_after.html`。
本輪只改設定／結果文件，**未重跑完整suite**；同版程式最近紀錄仍1016 passed／0 failed／2 skipped。
已完成本輪固定試用；Phase2自動可靠性仍NOT PASSED，未進Phase3，不追加裁切大小搜尋。

## 前段：大谷第5球有實際主體改善

使用者同意單球完整動作範圍輸入。新增可選 `input_crop`，保存 crop-native 候選及轉回原圖的座標；
未指定時維持舊流程。模型、selector、gate／門檻與人工GT保持。
同一球僅跑一次：位置限制版215/353→裁切版338/353（95.75%），missing138→15，最長gap54→13；
肘角raw coverage36.83%→59.49%。固定14格實際對照，原裁判／打者例子回到投手，仍有局部關節限制。
196–208格缺失未補，依原gate仍degraded；沒有宣告Phase2通過。

新增17項測試；完整suite **1016 passed、0 failed、0 errors、2 skipped**（1018項，82.720秒）。
正式山本五球E2E提示仍2／0／19／5／3，160個保護來源／標註／舊輸出SHA不變。
輸出：`analysis_results/phase2_ohtani_p05_crop_20261019_01/`，包含可直接看的 `before_after.html`。
本輪停在單球交付；下一步才是其餘四球的固定範圍試用，不做倍率搜尋或Phase3。

## 前段：可選投手範圍修正已交付，部分錯人改善

使用者已核准有限selector／capture修改並確認五球橘框。新增可選`subject_roi`：
左右肩／髖原點必須在操作範圍內，手腳可伸出；無匹配候選就missing。無設定時維持原預設。
模型仍看原完整畫面，既有信心與品質門檻、插值／平滑不變；所有模型候選另存逐格側檔。

大谷五球各重跑一次：0執行異常、5 degraded。原第2球177／266格錯人改missing；第5球多個抽樣改選投手，
但2／5仍有框內軀幹搭配跨人手臂。選中格數1677→1448，missing196→425；不可把減少數量當準確率改善。
完整suite **999 passed、0 failed、0 errors、2 skipped**（1001項，新增32項，含正式五球E2E），89.641秒。
原山本major提示仍2／0／19／5／3。候選保存核對0錯誤：1873格、2801副候選／92433點，47784選中raw點逐值相等。

輸出：`analysis_results/phase2_ohtani_subject_lock_20261019_01/`；先看`START_HERE.md`。
本輪已完成並停止，未改成全自動辨識或正式reference；Phase2自動可靠性仍NOT PASSED。
詳細數字、實際overlay抽樣與使用方式見[結果報告](phase2_pitcher_lock_results_20261019.md)。

## 前段：大谷翔平五球試用完成，五球 degraded

使用者已選定大谷翔平的一批五球。後續山本工作集合只含 `001`、`002`、`004`、`005`，
四對工作副本已建立於 `input/yoshinobu_yamamoto/phase2_active_20261019/`。
`003` 原影片與全部人工／模型證據保留，退出新試用集合；原五球評估分母與 NOT PASSED 結論不變。

本次只處理交付索引中的 `20261010T110737Z_RObvkuHpkSo`。HSU 已確認五球所有七項輸入需求（35項），
既有 MediaPipe 流程各跑一次，五球均完成輸出、0 執行異常；依原品質 gate 全為 degraded。
不重開已結束的警示試驗，不新增逐格 GT，不進 Phase 3。
當前進度與停止條件見[本批工作紀錄](phase2_next_dataset_20261019.md)。

大谷五球已成功匯入、0 拒收，重跑新增 0／跳過 5；人工輸入覆核 5/5 完成，未升為正式 reference。
1,873 格已完成分析與 overlay 全解碼；實際檢查每球 14 格 source／overlay 圖（共70格）。
有效 pose 比例依序 91.99／92.02／94.08／84.15／85.55%；肘角raw coverage 59.12／56.44／36.49／38.78／78.19%。
**重要限制：第2球部分抽樣轉到打者，第5球多處骨架落在裁判／打者；高coverage不能當成抓對投手。**
五球均有超過2格pose gap，另有膝角coverage不足／肘角coverage不足；詳見結果報告。
已交付本批結果後停止；下一個具體問題是主體選取／跨人骨架，尚未修改正式核心或開始新的修復試驗。
本輪 handoff 測試 **73 passed、0 failed、2 skipped**（75 項，含新增 6 項）。
上述為匯入 checkpoint 測試；本次只準備素材並實跑，無產品程式變更，未重跑全suite。
分析輸出：`analysis_results/phase2_ohtani_pilot_20261019_01/`，先看 `START_HERE.md`。
候選與人工輸入覆核紀錄仍在 `analysis_results/phase2_ohtani_intake_20261019_01/` 與各候選 `review.json`。

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
