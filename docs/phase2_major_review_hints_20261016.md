# Phase 2 第一步：分析輸出的重大錯位覆核提示

2026-10-16。使用者已核准把已驗證的離線提示作為附加覆核資訊提供。

每次完成 `analyze-pitch`，新增 `major_review_hints.json`，並在新分析的 `analysis.json`
列出該 artifact。原 status、quality gate、座標、raw、confidence、平滑／插值與 overlay 保留。
提示不自動刪資料、擋掉影格、改角度可用性或宣告 identity switch。

## 已採用的提示範圍

保存既有三種提示的聯集：原 tracking screen、前輪 bbox support、跨片肩髖分歧。
這正是封存評估的 additive trial，包含 bbox 才能完整保留 TP20/FN1/FP9 的原比較定義。
來源均使用已封存數值，沒有新 MediaPipe／MoveNet／tracker 推論或 GT 校準。

五球合計 592 格保存，587 非 seed 格評估：major TP20、FN1、FP9、TN557。
逐片非 seed 提示數是 001=2、002=0、003=19、004=5、005=3，共 29 格。
這是在已檢視五片上開發的結果，沒有跨片型或其他投手的可靠性保證。

**003 第 104 格仍為已知漏報。** 它只列在 known_misses／限制紀錄，沒有按已知答案新增提示。
沒有提示不代表可靠；candidate-dependent、insufficient evidence 與 seed 狀態保留於 diagnostics。

## 相同來源才套用

封存證據放在 package 的 `review_evidence/major_review_development_v1.json`，以固定 SHA 驗證。
適用性需同時吻合影片 SHA、pitch/pitcher 與投球側／視角／鏡像／速度／單球 metadata、
原 raw CSV SHA、模型 SHA、capture 語意內容 SHA 及逐格時間。
capture 的輸出路徑不參與 SHA，選取內容、分數與 timeline 仍需完全相同。

因此可隨相同來源的新分析直接附上既有證據；改影片、改模型或改 prediction 都不沿用舊提示。
未知／不匹配輸入輸出 `not_evaluated`，各格 `review_required=null`。
證據檔缺少或損壞輸出 `evidence_unavailable`，不假裝沒有警示，也不因此改變既有分析結果。
本輪 8 顆交付候選維持 pending，未分析／升格，正式五球未被取代。

## 輸出如何閱讀

- `review_required=true`：該格有既有聯集提示，請人工看原影片與 overlay。
- `review_required=false`：這份有限證據未發提示；關節正確性仍未知。
- `review_required=null`：無適用證據，不能作無警示解讀。
- `reasons`、`evidence_state`：提示來源與原因；各分量均保留，不修改原判定。
- `diagnostics`：bbox／分歧狀態、候選 slot 與關聯歧義；沒有替候選挑身份。
- `development_scope`：五球開發分母、原 major 回測與第 104 格漏報。

## 修改範圍與驗證

新增獨立 module、封存證據打包工具、package data 及測試。
`analysis/pitch.py` 僅增加 artifact 接點；正式 pose／tracking、selector、gate、threshold、
raw prediction 及人工 GT 未修改。CLI 不需新增選項。
歷史 374 份來源中，373 份保持原 SHA；唯一允許差異是該分析輸出接點，
原凍結實驗文件與程式均保留。62 份上游來源亦維持。

本輪證據與測試放在 `analysis_results/phase2_major_review_hints_20261016_01/`。
測試結果與來源核對以同目錄的 `delivery_summary.json` 及
`docs/evaluation_plans/phase2_major_review_hints_result_20261016_01.json` 為準。

第一步只正式提供覆核提示；Phase 2 自動可靠性仍依既有驗收要求判定。
第二步 [肘腕品質判斷器計畫](phase2_joint_quality_classifier_plan_20261016.md) 狀態是
AWAITING_USER_CONFIRMATION；本輪不訓練或執行第二步。
