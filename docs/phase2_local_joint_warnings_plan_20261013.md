# Phase 2：六關節局部分歧提示

2026-10-13。使用者在前輪收尾後指示「繼續」，本輪續做局部關節可靠性修復。
只新增離線局部提示，保留前輪結案與所有封存結果。正式核心、原門檻／gate、selector、pose、
tracking、插值／平滑、raw、人工GT與五球保持原樣；零新pose／tracker推論，不進Phase3。

## 凍結前確定的範圍

對投球肩／肘／腕、前導髖／膝／踝逐一產生極端位置分歧screen。
沿用封存同名raw/native關節距離與所有相容候選，單位為原影像對角線比例。
映射必須跨五片一致；逐fold只校準其他四片同一解剖landmark的全部finite非seed min距離。
frame0完整保存，但不進校準／警示成效。每個關節分開取sample maximum作**實驗性資料估計閾值**。
不使用GT刪壞格、不依投手名稱或事件／frame區間觸發，不調低原有門檻。

- query min嚴格大於reference maximum：`warning`，全部相容同名候選均超出參考。
- min <= reference < max：`candidate_dependent`，不選slot、不發局部二元warning。
- max <= reference：`within_reference_range`，**不代表可靠或正確**。
- query無距離／無相容候選，或reference全缺：`insufficient_evidence`，缺值不填0。
- 原processed observed／interpolated／missing只作獨立context，不改標、不把missing視為位置錯誤。

六關節提示不提升為major／identity-switch警示，也不擴張前後影格；不以它宣稱修好003／104。
各fold保存完整校準分母、finite／missing、相容候選分布與全部並列最大值來源。

## 必須揭露的結構限制

其他影片sample maximum會讓**只有含整組極端分歧的影片可能超界**；其餘片的較小錯點可能
被壞校準格遮住。因此這是極端分歧提示，不是一般reliable／unreliable分類器。
候選相依或模型彼此接近仍可能一起錯；native score不裁掉假候選。
五片皆已檢視，這是開發驗證，沒有未見資料、跨投手或false-alarm機率保證。

## 評估

Producer不讀GT／人工XY。封存提示後，evaluator才讀canonical六關節raw-overlay標籤：
unreliable正例、reliable負例、uncertain／not_observable按該關節排除。
每關節完整587非seed格都保存，六關節合計3,522列；模型缺值留在人工可判定FN/TN分母。
另報warning落在人工排除格的數量，避免隱藏遮擋提示負擔。

逐片、逐關節列TP/FN/FP/TN、recall、precision、完整缺值／候選相依數與model-state交叉表。
原jump端點僅作獨立局部component／context，不把自然快速動作直接當錯誤。
局部結果與major結果分開，不把新增局部TP算成major修復或Phase2通過。
不因本輪結果改分位數、清洗校準或改閾值。若效果不足，記錄不採用。

輸出使用新目錄`analysis_results/phase2_local_joint_warnings_20261013_01/`。
完成後獨立核對、完整suite含正式五球E2E、更新狀態、commit/push；八顆交付球保持candidate/pending。
