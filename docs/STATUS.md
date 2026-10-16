# 進度摘要

更新：2026-10-16（台灣）。[完整狀態](current_status.md)。

**Phase 1 = PASSED。Phase 2 自動可靠性仍 NOT PASSED。第一步覆核提示已交付；第二步待確認。**

## 最新完成：重大錯位覆核提示

`analyze-pitch` 新增獨立 `major_review_hints.json` 並列入新分析 manifest。
維持原 tracking＋bbox＋肩髖分歧聯集，五球 592 格保存、587 非 seed 格評估，
major TP20/FN1/FP9/TN557。五球新分析的提示數為 2／0／19／5／3。
003 第 104 格仍未提示，保留已知漏報。沒有提示不代表可靠。

僅精確吻合影片、metadata、model、raw、capture 與時間軸才使用封存證據。
其他輸入輸出 not_evaluated／null；證據缺失或損壞輸出 evidence_unavailable。
既有判定、座標、原 gate 與資料都保留。詳見 [第一步文件](phase2_major_review_hints_20261016.md)。

## 驗證與保存

- 完整 suite：**787 passed、0 failed、0 errors、2 skipped**，789項／64.452秒／exit 0。
- 2項skip是Windows符號連結限制；正式五球E2E實際驗證新提示皆有適用證據。
- 18項新增測試；wheel包含SHA吻合的程式及封存證據。
- 歷史374來源中373份SHA維持，唯一核准變動為分析輸出接點；62上游來源維持。
- 正式pose/tracking、selector、原threshold/gate、raw、GT與原五球均保留；8交付候選仍pending。
- 輸出：`analysis_results/phase2_major_review_hints_20261016_01/`。

## 第二步：等待使用者確認

[肘腕品質判斷器計畫](phase2_joint_quality_classifier_plan_20261016.md)已寫定：
沿用canonical逐格標籤，固定小型邏輯迴歸與原模型訊號，整片四訓練／一測試輪流五折。
擬議肘 TP≥17、FP≤1、非003 TP≥10；腕 TP≥27、FP≤1、非003 TP≥23；
各需至少2支非003影片改善。完整保留好點保留率、錯點漏報與未知／缺值負擔。

目前 **AWAITING_USER_CONFIRMATION，訓練0次**。任一關節達標才提該關節覆核提示採用範圍，
仍等使用者核准；兩者都未達標就停止調整這組訊號，記錄需要更好的影像或模型資訊。
未開始Phase3。

---

# 2026-10-15 歷史收尾

更新：2026-10-15（台灣）。詳見 [完整狀態](current_status.md) 與 [最新結果及驗收整理](phase2_expanded_roi_results_20261015.md)。

**Phase 1 = PASSED。Phase 2 評估與本次有限修復已完成；自動可靠性仍 NOT PASSED。**

## 已完成

- 正式 Yamamoto 五球 baseline、592 格品質與追蹤評估、HSU 定性 GT 覆核 5/5。
- 003 的 115 格、12 關節人工座標覆核：1,205 visible、173 not_observable、2 uncertain；已完成 prediction vs GT。
- raw／interpolated／missing、逐關節品質、追蹤警示、major／局部限制與來源可追溯。
- 固定 2× ROI 單次五球實驗完成，592 次推論／0 tracker；中斷恢復重跑新增推論 0。
- contract v2 交付讀取器已完成候選接入；8 球仍 pending、未分析。

## 本輪決定

固定 2× ROI 不採用。五球 selected 550/587，窄框 552/587，全圖 IMAGE 555/587。
004／005 恢復部分 selection，但 003 從窄框 108/114 降到 88/114；同格肘角 MAE
11.0391°→20.4522°（35格），膝角 4.0257°→5.5399°（73格）。缺值與所有退步保留。
已查看五張對照圖、11 個案例；恢復骨架仍可能把手臂連到背景，不能用 coverage 當正確性。

## 測試與保存

- **769 passed、0 failed、0 errors、2 skipped**，共 771 項、58.508 秒、exit 0，包含正式五球 E2E。
- 2 項 skip 是 Windows 符號連結能力；初次沙箱多跳過的 8 項 junction 檢查已補驗。
- 獨立重算 592 格、19,866 映射點、28,416 關節狀態、1,380 人工狀態、920 角度流。
- 374 保護檔案、62 上游來源及原 MoveNet attempts 不變；正式五球、raw、GT、核心與門檻不變。
- 輸出：`analysis_results/phase2_expanded_roi_20261015_01/`。

## 未完成與使用範圍

自動警示仍會漏掉已知錯位，肘腕局部不可靠；不能宣稱自動 reliable 就是正確關節。
可使用人工覆核後的資料與逐格使用限制。原 major hold 保留，不把 missing 當作修好。
只有 003 有精確人工 XY，其餘四片誤差 null；005 uncertain 事件保持有效。

本次交付已收尾，停止追加倍率、模型或小規則實驗。自動可靠性修復仍是未完成工作，
不因測試通過而改標 PASSED，也不把更多標註、零 FN/FP 或新 holdout 加成收尾條件。
未進入 Phase 3。交付候選正式使用仍需人工確認。
