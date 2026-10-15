# 固定 2× ROI 五球實驗

2026-10-15。依使用者「繼續」執行上一份整合決策中的單次方案。

以封存 CSRT 浮點 xywh 中心擴成寬高各 2 倍，再 floor/ceil 與原圖相交。
MediaPipe Full、IMAGE、4 poses、原 confidence、fresh 原 PitcherSelector 每片一次。
不重跑 tracker，不 resize/pad/mirror/fallback，不調門檻，不讀人工點來選框。
正式五球 592 格保存、587 非 seed 格評估，最多 592 次 detect、0 tracker。

新增隔離 IMAGE adapter 遵守既有 PoseEstimator 的 estimate → PoseEstimate contract；
正式 VIDEO adapter 與核心均不改。每次呼叫前 fsync started journal，結果與 completed 分別 fsync。
重啟可重建 selector 但不重算已存影格；started 而無結果時拒絕自動重試。
OS lock 防止同時執行。來源、模型、runtime、程式與評估規則在推論前固定 SHA。

producer 只讀宣告的影片、metadata、technical、封存 tracker、code/model/native；
GT 與對照組只由量測完成後的 evaluator 讀取。原資料均保留。

逐片比較 expanded / narrow / full-frame IMAGE / 原 VIDEO 的 selection、12 關節 raw、
原 gate、input support、visibility/presence、缺值跨度、相鄰位移與完整流失/新增格清單。
六重要關節依正式 metadata 的 throwing/lead side 解讀。
只有 003 有精確人工 XY：保留所有 visible 參考與原 major/eligibility 分層，
以各對照共同格比較 pixel 與肘/膝角度；人工點在 crop 外不移出主要分母。
其餘四片精確誤差 null。原定性 GT 只作原 prediction 的背景，不認證新預測。

一次固定倍率後作採用/拒絕決定並停止，不追加倍率搜尋或新模型，不自動接正式流程。
不創建新的數值通過線或任意排名。Phase 2 尚未通過的既有限制持續有效。
