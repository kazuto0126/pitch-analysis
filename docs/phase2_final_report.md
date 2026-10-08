# Phase 2 最終評估

**Phase 2 evaluation = COMPLETE**
**Phase 2 = NOT PASSED；automatic reliability = NOT PASSED**

人工 GT 5/5 reviewed。這輪評估已結束；已知重大錯位漏報使自動可靠性未通過。
無新總分、數值通過線、模型、pose／tracking／平滑修改。測試通過不等於可靠性通過。

## 五片摘要

| 影片 | 格數 | 重大失效 | 原警示 TP/FN/FP | +既有跳點 TP/FN/FP | 手肘關節 raw coverage | 角度可用：肘/膝 |
|---|---:|---:|---|---|---:|---|
| pitch_001 | 87 | 0 | 0/0/2 | 0/0/7 | 66.7% | 18/81 |
| pitch_002 | 175 | 0 | 0/0/0 | 0/0/11 | 88.6% | 112/173 |
| pitch_003 | 115 | 18 | 0/18/2 | 10/8/8 | 84.3% | 38/86 |
| pitch_004 | 114 | 2 | 2/0/3 | 2/0/15 | 72.8% | 35/103 |
| pitch_005 | 101 | 1 | 1/0/2 | 1/0/15 | 88.1% | 43/87 |

全部 592 格：原警示 TP3/FN18/FP9；既有跳點診斷聯集 TP13/FN8/FP56。
聯集是診斷對照，沒有成為新 detector；跳點只標相鄰 observed 轉移的當前端點，不擴張成整段錯誤。
身分切換 confirmed 0 格，不能估 sensitivity；track break 3/3 格與人工吻合。

## 這次可使用的成果

- `phase2_final_assessment.json`：來源驗證、逐片六關節 coverage／visibility／gap／jump、比較與判定。
- `release_status.json`：評估完成與自動驗收分開；`accepted=false`，停止在 Phase 3／共用資料夾之前。
- 既有自動提示的新五片影片、逐格 JSON／CSV：沒有讀入人工 GT。無提示仍不代表對位正確。
- 已完成的人工覆核影片／逐關節狀態，以及既有角度側檔保留；可用欄位僅限本批定性覆核的直接觀測 2D 輸入。

## 座標與限制

pitch_003：1205 可見點，同 1174 可用點 raw 均誤差 21.9504px，clean 22.0292px。
97.43% 是保留率，不是準確率；不可觀測／不確定點不作精確座標真值。
其餘片沒有相同人工 XY；事件沒有自動預測可比較；一位投手不代表其他投手泛化。
pitch_005 canonical 啟動／最高抬腿仍為 uncertain；同學的獨立事件補充未回傳，另存待辦，不冒填或重開已完成 GT。

## 測試與停止點

完整測試：240 passed / 0 failed / 0 errors / 0 skipped，含正式五片 E2E。
下一次若要修復自動錯位警示，先指定新工作與驗收方式。共用交付資料夾接入仍未開始，須另行開始指示。
本輪 Phase 2 評估與報告收尾後停止；沒有開始 Phase 3。

## 最終輸出與重現來源

最終評估：`analysis_results/phase2_final_yamamoto_20261008_02/`。
先看 `START_HERE.md`；完整數字在 `phase2_final_assessment.json`，終止狀態在
`release_status.json`，測試紀錄與二次唯讀核對也在同一目錄。

本次五片提示影片／3552列CSV：`analysis_results/phase2_automatic_cues_20261008_01/`。
每片有 `autocue_overlay.mp4`、`automatic_reliability_cues.json`、`cue_index.csv`。
保留原overlay區域與骨架，僅增加中文側欄；五片均H264/yuv420p、原FPS與完整格數。
五片代表畫面已檢查排版；全部592格已解碼核對、33張PNG原區域像素核對相同。
H264重編碼為有損，不能宣稱解碼後逐像素相同。

既有人工覆核視圖：`analysis_results/phase2_reviewed_baseline_20261007_01/`；
既有角度可用欄位：`analysis_results/phase2_reviewed_features_20261007_02/`。
角度可用共手肘246/592、前導膝530/592；原值仍保留，受限的新可用值留空。
原正式 `analyze-pitch` 尚未自動使用人工側檔；這不是自動定位修復或新motion分析。

### 本輪實質變更

- 新增 `scripts/export_existing_reliability_cues.py`：從既有模型輸出逐格核對／顯示原跳動端點。
  不接受GT輸入，區分已量測無提示、跳動提示、未量測；身分與對位均不冒稱已驗證。
- 新增 `scripts/finalize_phase2_evaluation.py`：重新核對來源、重算已存在的人工比較與資料可用性，
  建立有限且可讀取的最終結論。`--require-passed` 在自動驗收未成立時回傳非零；一般評估完成不代表可發布。
- 新增25項測試（提示14、收尾11）；最終完整suite為240項、含五片正式MP4 E2E，約42秒。
- 新增兩份最終來源計畫與提示來源計畫，更新README／STATUS／current_status。
  MediaPipe與既有 `PoseEstimator` abstraction 保留；沒有更換後端、修改confidence gate或分析邏輯。

### 來源保護與版本

最終來源計畫：`docs/evaluation_plans/phase2_final_evaluation_20261008_02.json`。
SHA256：`31d2d5814acb3c1121fb73a1be4e0b37ae47115e367ca73a204a20d20e34497f`。
提示計畫：`docs/evaluation_plans/phase2_automatic_cues_20261008.json`。
SHA256：`33e90c9cf978358c02a0fd79b77b8cd688ab5e112e2a0d385e07a5dbe07ab2a5`。

二次唯讀核對：374份不重複來源／程式／測試／媒體檔案hash相符；原tracked演算法與人工標註未修改。
592格／3552個提示CSV列／92個保存的關節端點（59個不同frame）皆與原模型資料一致。
初版 `_01` 及其精確runner／tests snapshot保留；`_02`只修正相同實體檔案被不同路徑重複計數，
並記錄最終240項測試。原初始baseline中pending GT摘要保持歷史快照，不用它當現在完成狀態。

程式、測試、來源計畫與這份報告進Git；影片／大型衍生JSON留在本機既有ignored analysis_results，
可依綁定來源再產生，不把候選結果或人工資料混成raw prediction。

## 原Phase 2問題的最終回答

| 問題 | 本批結果與限制 |
|---|---|
| 追的是正確投手嗎？ | HSU五片覆核確認主體仍在投手；003有整體錯位。模型連續性不能獨立證明正確對位。 |
| 哪些關節可信？ | 六個重點關節全592格有人工定性判讀、資料狀態與限制；003另有12關節可見座標誤差。 |
| 遮擋怎麼處理？ | 保留not_observable／uncertain，不以透視猜點當精確可見真值，也不把missing直接等同遮擋。 |
| observed／interpolated／missing？ | 全部保留、可逐格讀取；observed是模型門檻通過，不是位置正確。 |
| track-break／identity-switch？ | confirmed break3格吻合；confirmed switch0，沒有陽性可以估偵測敏感度。 |
| throwing elbow可信嗎？ | 人工不可靠84格中72格仍是observed；不可觀測59格中20格仍是observed。raw coverage不是精確度。 |
| 是否完成事件評估？ | 原人工事件exact／range／uncertain完整保存；沒有自動事件預測，沒有宣稱事件準確率。 |
| 自動可靠性通過嗎？ | **NOT PASSED**。003的87–104格原整體提示全部漏掉；加入既有跳點的診斷聯集仍漏8格且有56格目標外提示。 |

## 停止位置

本輪Phase2評估已收尾，不保留無限IN PROGRESS；自動可靠性不改成PASSED。
同學005獨立事件補充仍待回傳，但不使canonical 5/5覆核變未完成。
若另行開始修復自動錯位，須以已量測的失效與新的明確驗收方式安排工作。

- [ ] Phase2可靠性穩定後，才評估共用交付資料夾 `D:/project/pitch-video-handoff` 接入。
  以該資料夾的 `CONTRACT.md` 為準；交付資料夾只讀、不依賴供片專案程式碼。
  **依使用者要求：輪到此待辦時先停止回報，收到新的開始指示才實作。**

本輪未讀該交付資料夾、未做接入、未新增投手、未開始Phase3。
