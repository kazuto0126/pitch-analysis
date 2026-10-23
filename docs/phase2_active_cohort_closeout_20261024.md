# Phase 2 啟用骨架人工覆核與資料交付收尾

更新：2026-10-24（台灣）。

HSU在四支山本新overlay的明確覆核要求後回覆「都正確」。本次接受範圍為
`pitch_001／002／004／005`；`003`仍是歷史對照，未恢復啟用。
原話、reviewer、紀錄時間，以及四片各自影片／overlay／manifest／原生座標SHA另存：

`annotations/skeleton_reviews/HSU_20261024/yamamoto_active_skeleton_acceptance.json`

這是整片投手跟隨與整體關節對位的人工接受。原逐點人工GT保持，不自動增加精確XY、
可見性或逐點可靠性標籤。舊rollout的pending是執行時快照；最新狀態以獨立接受紀錄為準。

## 已完成的啟用集合

| 投手／影片 | 影格 | 新骨架人工接受 | 本輪處理 |
|---|---:|---|---|
| 山本 pitch_001 | 87 | HSU接受 | 原生資料入口＋描述報告 |
| 山本 pitch_002 | 175 | HSU接受 | 原生資料入口＋描述報告 |
| 山本 pitch_004 | 114 | HSU接受 | 原生資料入口＋描述報告 |
| 山本 pitch_005 | 101 | HSU接受 | 原生資料入口＋描述報告 |
| 大谷 supplement_001 | 335 | 先前HSU接受 | 沿用原入口／報告 |
| 大谷 supplement_002 | 321 | 先前HSU接受 | 沿用原入口／報告 |
| 大谷 supplement_003 | 369 | 先前HSU接受 | 沿用原入口／報告 |
| 大谷 supplement_004 | 338 | 先前HSU接受 | 沿用原入口／報告 |
| 大谷 supplement_005 | 321 | 先前HSU接受 | 沿用原入口／報告 |

合計 **9支／2161格／36737個原生17點關節影格**。大谷仍維持候選素材身分，
人工骨架接受不自動升格／替換正式素材。Phase1原正式檔案及五球歷史紀錄保持。

山本四片477格／8109點已各用既有實際CLI建立bundle與report，再經Python loader逐格讀取。
原影格／追蹤／報告XY、狀態、分數及缺值原因差異皆0；四片幾何track break0。
大谷五片1684格原報告SHA核對相同，沒有重跑。
新人物偵測／pose推論／tracking replay／插值／逐點GT皆0。

本輪保護323份既有來源、人工紀錄、正式素材、程式與測試，SHA差異0。
只新增人工接受、來源設定、保存資料輸出與收尾文件，產品碼／測試碼均未修改。

## 輸出與測試

山本四片新入口與報告：`analysis_results/phase2_active_cohort_closeout_20261024_01/`。

- `bundles/pitch_001／002／004／005/`：原生資料入口，來源與接受證據SHA綁定。
- `reports/pitch_001／002／004／005/`：中文`report.md`、pose／tracking JSON、逐格JSONL。
- `closeout_results.json`：四片實際接入與兩投手合計狀態。

設定：`config/analysis_inputs/yamamoto_active_seeded_20261024.json`。
[版本化結果](dataset_selections/phase2_active_cohort_closeout_20261024.json)。
大谷入口沿用`analysis_results/phase2_native_analysis_input_20261023_01/bundles/`，
報告沿用`analysis_results/phase2_native_reliability_20261024_01/`。

本輪實際驗證：山本4支CLI資料接入＋4支CLI報告、完整477格loader／原始資料核對；全部完成。
產品與測試碼未變，**沒有重跑完整suite**。
相同程式碼前輪完整suite：**1163 passed／0 failed／0 errors／2 skipped**（1165項），
兩項為Windows檔案symlink能力，包含正式山本五球MediaPipe E2E。
完整測試來源與SHA在版本化結果的`full_suite`欄位。

## 最終驗收決策與停止點

| 項目 | 判定 |
|---|---|
| 共用人工初始化＋人物框追蹤＋RTMPose17點方法 | 已採用 |
| 目前啟用九片的整片人工接受 | COMPLETE：山本4/4，大谷5/5 |
| 啟用集合的原生資料接入 | PASSED |
| 啟用集合的逐關節／追蹤描述報告 | COMPLETE |
| Phase2人工輔助骨架交付 | COMPLETE |
| 原本自動可靠性驗收／Phase2總狀態 | NOT PASSED |

剩餘限制是自動逐點品質判斷：模型有座標／分數，仍不能自動證實該點可見且正確。
現有逐點reliability／human_visibility保持unknown、usable_for_analysis=null；
既有失敗的自動錯點判斷試驗保持封存。整片接受不能取代它們的量化採用要求。

本輪沒有增加精確率、零錯誤、新標註或新素材數量等收尾條件，也沒有調低舊門檻。
啟用集合的整片人工覆核已全部完成；這一項沒有剩餘影片需要重看或重標。
本輪在此停止。後續若要改變Phase2驗收範圍或開發自動品質判斷，需由使用者另行決定；
目前沒有新實驗排程，未進Phase3。
