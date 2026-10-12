# Phase 2：跨片肩髖分歧警示試驗

2026-10-12。只新增離線警示sidecar，不改正式核心、既有threshold、confidence gate、
PitcherSelector、pose/tracking、smoothing/interpolation、正式素材或人工GT。不推論新模型。

## 事前固定政策

沿用封存五球592格、同slot四肩髖RMS／原影像對角線分歧。成效分母587非seed格。
每支查詢影片以**其他四支**所有finite非seed格的分歧min校準；使用sample maximum作
**資料估計的實驗性閾值**。沒有固定pixel cutoff、百分位選擇或人工GT校準；不修改既有門檻。
不依GT刪掉壞校準格，可能使其他fold參考範圍過寬；保留最大值來源與完整校準分母。
frame0保留，但每個fold的校準與警示成效都排除。自己的任何格均不進自己的校準。

- `min > reference_max`：`warning`，全部相容整副肩髖候選都超出跨片參考。
- `min <= reference_max < max`：`candidate_dependent`，保留候選歧義，不發major二元警示。
- `max <= reference_max`：`within_reference_range`，**不能判為可靠**。
- 查詢無finite四肩髖／沒有相容候選，或其他影片沒有finite校準值：`insufficient_evidence`。
  保留missing，不填0或無限大。NaN/inf、半缺範圍、不一致slot與timeline直接拒絕。

每格保留min/max、所有相容slot編號、association、時間戳、明確原因；不選最可信slot，
不把不同人的關節拼成骨架，不把高native score當身份，不把警示前後影格一起回填。
本試驗只針對軀幹分歧警示，不能代替肘腕可見性、人體關節位置或identity-switch真值。

## 評估與限制

Producer只讀已封存的關節分歧量測與來源收據，**不讀GT或人工XY**。
輸出封存後，獨立evaluator才讀既有canonical GT，逐片列四種screen：原tracking、原加bbox、
新分歧、原加bbox加新分歧。保留舊警示，另外報新增TP／FP、剩餘FN與缺值分母。
候選相依影格不刪掉；missing仍在主要FN/TN分母。全五球、association、候選數均列明。

五片已看過且僅003有可量測重大漂移，因此leave-one-clip-out只是**開發驗證**，
不是未見holdout、跨投手泛化、conformal錯誤率保證或正式驗收。參考範圍對候選數、鏡頭尺度
與校準污染敏感；影格彼此相關，不能把大量逐格樣本當作獨立影片樣本。
不得依本輪結果調低bound、改分位數、清洗校準資料或宣布座標修復。

新輸出：`analysis_results/phase2_disagreement_warning_20261012_01/`。
執行前SHA綁定政策、程式、測試、全部五球量測；完成後獨立重算及完整suite含正式五球E2E。
Phase 2通過與否另依實際可靠性證據判定；本離線試驗無production adoption，不進Phase3。
