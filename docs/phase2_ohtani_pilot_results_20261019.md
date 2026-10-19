# 大谷翔平五球試用結果

2026-10-19（台灣）。**本批試用已完成；5 球皆 degraded，0 球可依既有 gate 當正式 reference。**

五球原影片由 HSU 在對話觀看後確認全部七項輸入需求（共 35 項）；原第 1 球答「都對」，第 2–5 球答「2-5」「都正確」。紀錄保存於各候選 review.json，含署名、UTC時間、結論與備註。這是素材輸入覆核，並非骨架對位 GT。

每球使用目前正式 MediaPipe Full 流程一次。5 球均完成 input contract／MP4／input quality、pose/keypoint、metrics 與 overlay 輸出；執行異常 0，品質 success 0／degraded 5／failed 0。原始來源、人工 GT、核心、gate 與門檻均未修改。

最關鍵的新發現：**第 2、5 球抽樣可見追到打者／裁判。** 高 pose 比例或高 visibility 不能當成投手骨架正確；第 5 球肘角coverage雖達 78.19%，仍不能使用錯人的軌跡。這批證據指出問題會在新素材上重現，不能藉排除山本 pitch_003 宣稱可靠性已通過。

## 每球品質摘要

| 大谷球號 | 總格數 | 選中 pose 格數 | 比例 | 拒絕格 | 含插值格 | 平均 visibility | 最長 pose gap | 結果 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| p01 | 362 | 333 | 91.99% | 29 | 120 | 0.826 | 5 格 | degraded |
| p02 | 326 | 300 | 92.02% | 26 | 167 | 0.801 | 6 格 | degraded |
| p03 | 422 | 397 | 94.08% | 25 | 68 | 0.803 | 6 格 | degraded |
| p04 | 410 | 345 | 84.15% | 65 | 120 | 0.803 | 11 格 | degraded |
| p05 | 353 | 302 | 85.55% | 51 | 134 | 0.862 | 7 格 | degraded |

「選中 pose」是舊流程欄位名稱，未代表每格確實追到投手。插值格可和選中格重疊，不能相加當總格數。最長缺口約 0.08–0.18 秒；既有 gate 仍以超過 2 格為失敗條件，未調整。

## 關節與角度 coverage

| 大谷球號 | 右肘直接觀測 | 右腕直接觀測 | 左膝直接觀測 | 肘角 raw | 前導膝角 raw |
|---|---:|---:|---:|---:|---:|
| p01 | 79.83% | 59.39% | 80.39% | 59.12% | 79.56% |
| p02 | 66.26% | 57.36% | 76.69% | 56.44% | 71.47% |
| p03 | 77.73% | 36.49% | 91.47% | 36.49% | 91.23% |
| p04 | 79.27% | 39.27% | 78.05% | 38.78% | 77.80% |
| p05 | 82.15% | 78.47% | 74.50% | 78.19% | 74.50% |

關節直接觀測是通過既有 gate 的原始座標比例；肘角 raw 需要肩／肘／腕三點同時可量測，不能代稱單一肘點coverage。被遮擋、missing 與插值仍分開保存。全六個重點關節的 raw prediction coverage、直接觀測、visibility、missing span、插值與跳點，保存在 evaluation_summary.json 與每球 reliability JSON。

## 未通過既有 gate 的原因

- **p01**：more than 2 consecutive frames have no source pose；lead_knee_angle raw coverage below 80%。
- **p02**：more than 2 consecutive frames have no source pose；lead_knee_angle raw coverage below 80%。
- **p03**：more than 2 consecutive frames have no source pose；throwing_elbow_angle raw coverage below 50%。
- **p04**：pose detection below 90% of segment timeline；more than 2 consecutive frames have no source pose；lead_knee_angle raw coverage below 80%；throwing_elbow_angle raw coverage below 50%。
- **p05**：pose detection below 90% of segment timeline；more than 2 consecutive frames have no source pose；lead_knee_angle raw coverage below 80%。

p01 自動 input quality 另列 followthrough_unverified；HSU 已確認原影片收尾完整，兩份證據均保留，未以人工答案覆寫自動輸出。五球 input quality 均 degraded。

## Overlay 實際檢查

五支 overlay 均完整解碼，格數與來源一致（共 1,873 格）。Codex 實際看過每片 14 格 source／raw-overlay 比較圖，另有每片首／中／尾全畫面構圖，非逐格人工 GT。頁面與裁切僅供看圖，模型輸入始終為原始 1280×720 全畫面。

| 大谷球號 | 抽樣觀察 |
|---|---|
| p01 | 抽樣中有骨架的畫面主要落在投手；f143、165、197附近可見骨架缺失，收尾仍有追蹤缺口。沒有以抽樣推定全片正確。 |
| p02 | f177、266可見骨架落在打者；f238、325有投手與打者肢體混合／不合理跨人連線。前段部分投手骨架合理，後段不能當成持續鎖定投手。 |
| p03 | 抽樣中有骨架的畫面主要在投手；準備段f111、115有缺失，投球後段仍有局部手臂／手腕品質限制，肘角raw coverage只有36.49%。 |
| p04 | f93、109、260、335、409可見骨架缺失；f223上身關節未貼合投手，f297手臂有朝打者方向的不合理連線。 |
| p05 | f0、32、96骨架落在裁判附近；f64、128、160、192、320、352落在打者。f224有跨人／混合連線；存在大範圍追錯人的問題。 |

既有 tracking 五球均 partially_reliable，identity-switch warning 依序 false／true／false／true／true；這些是連續性警示，不是已由人工逐格確認的切換事件。identity_switch_confirmed 保持 null。
新投手不在舊五球 source-bound 重大錯位提示的有效範圍；五球 major_review_hints 都是 not_evaluated，不能把空提示記成零錯點。沒有新增人工 GT、誤差總分、排名或事件預測。

## 來源、輸出與版本

- 批次：`20261010T110737Z_RObvkuHpkSo`；原 `p01`–`p05` 對應本地 `shohei_ohtani/pitch_001`–`005`。此處大谷 `pitch_003` 與已退出後續集合的山本 `pitch_003` 是不同素材。
- 五份人工輸入覆核原樣快照已保存於 `annotations/input_reviews/shohei_ohtani/20261010T110737Z_RObvkuHpkSo/p01.json`–`p05.json` 並納入 Git，沿用 `handoff-input-review-v1`，保留 HSU、UTC 時間、七項結論與備註。這不是新的逐格 pose GT。
- 輸入：`input/shohei_ohtani/phase2_pilot_20261019_01/`；每球 metadata 以人工確認及來源聲明生成，原交付 JSON 保留。球季／場次／球種未知仍為 null。
- 輸出：`analysis_results/phase2_ohtani_pilot_20261019_01/`，先看 `START_HERE.md`。`source_mapping.json` 保存原 ID／本地 ID／影片SHA／人工覆核來源；`evaluation_summary.json`、`reliability/`、`visual_review/` 與原分析輸出完整保存。
- 本輪只新增素材與報告，無產品程式碼修改，沒有重跑全 suite。上一讀取器 checkpoint 的聚焦測試為 73 passed／0 failed／2 skipped；最近完整 suite 的歷史紀錄為 961 passed／0 failed／2 skipped，皆不冒稱是本輪重跑。
- `Phase 1 = PASSED`；原生封存介面接入 PASSED；歷史 `Phase 2 automatic reliability = NOT PASSED`。本批完成不更動這些結論。

## 本批停止位置

已交付五球實跑結果、逐關節診斷與可重現的 overlay 例子；依本批工作計畫到此停止。
後續優先工作可直接針對投手主體選取／跨人骨架問題，使用本批錯例處理；現有界線不包含修改正式 selector／pose 核心，開始修復前需明確確認那項範圍。無須先增加投手或重開已結束的警示實驗。未進 Phase 3。
