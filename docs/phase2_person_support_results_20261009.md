# Phase 2：HOG 人體候選範圍試驗結果

2026-10-09（台灣）。**已完成隔離量測與幾何核對；人體框歸屬尚待人工確認。**
**Phase 2 automatic reliability = NOT PASSED。原 FN18 未修復。**

## 已完成的實質工作

- 新增 `scripts/measure_person_support.py`，只讀正式003原片、metadata及影片技術紀錄；
  不讀pose／人工答案，不裁切、外部resize、鏡像或指定投手框。
- 新增 `scripts/evaluate_person_support.py`，量測封存後才讀既有raw／人工參考。
  完整重播115格，逐格核對原像素SHA、小數PTS及每個候選的原始框／SVM值。
- 保存全部API框、分數、原始順序與run-local index；沒有框的格數也保留。
  SVM值不是已校準機率，框編號不是跨格或跨次追蹤ID。
- 新增26項測試，包含native BGR／固定參數、空框、半開區間、遮擋缺值、人工重覆紀錄、
  空白覆核題、CLI入口，以及多框順序變動／重覆框數／分數差異的核對。

## 固定設定與來源

依 [原核准方案](phase2_person_support_proposal_20261009.md)，只跑003完整115格、510×628原圖。
OpenCV5.0.0／NumPy2.5.3／Python3.12.14，本機default people SVM（3781係數）。
設定固定為hitThreshold0、winStride(0,0)、padding(0,0)、scale1.05、groupThreshold2、
useMeanshiftGrouping=false；係數、native binding、HOG各屬性及runtime皆綁SHA／值。
沒有試參數網格、下載、安裝、換pose模型或改正式selector／gate／平滑／插值。

最新執行凍結：
`docs/evaluation_plans/phase2_person_support_execution_20261009_03.json`。
本輪工具／測試／execution JSON固定LF，避免Windows Git自動換行轉換改變凍結SHA；
該設定只適用本輪新增檔案。

## 數字結果

| 項目 | 實測 |
|---|---:|
| 完整量測／獨立完整重播 | 115／115格 |
| API回傳人體候選框 | 177個 |
| 有框／無框 | 114／1格 |
| 重播框座標／原始SVM值差異 | 0；逐格比較完整multiset，保留重覆數 |
| 重播僅API順序不同 | 8格：40、41、52、53、68、92、93、101 |
| 既有人工visible／not_observable／uncertain關節 | 1205／173／2 |
| 四個肩髖點皆visible的proxy／缺proxy | 106／9格 |
| 有框包含四個可見人工肩髖點 | 93／106格；僅幾何對照 |
| 既有confirmed major pose failure有框 | 18／18格 |
| 重大失效格有框包含四個人工肩髖點 | 17／18格 |
| 重大失效格有框亦包含四個原raw肩髖點 | 7／18格 |
| 既有人工歸屬位置去重後 | 11個：T3／P2／O6 |
| 新框歸屬覆核題／人工答案 | 9／0 |

四點containment不是全身框IoU或骨架正確率。**7格重大失效仍能讓錯誤raw肩髖點落在
某個人體框裡，因此不能直接用「有框支持骨架」當可靠性通過條件。**
沒有替人體框指定投手；原raw與人工XY的框內／框外關係全部保留，不挑最佳框冒充自動選對。
173個不可觀測及2個不確定點不使用隱藏XY補值。

已直接檢視九張候選圖；範圍大小不一，有的只框住局部身體，畫面也有打者／捕手等其他人。
這項影像檢查只確認review圖可讀，不代替HSU的框歸屬答案，也不填任何ground truth。

## 人工覆核只新增九個框歸屬問題

固定抽樣0／38／86／95／105／112格，每格最多兩個最高raw SVM框，同分依x/y/w/h。
實際產生九題，其餘168個框保持未覆核；不重做原5/5 canonical GT或逐關節人工標註。

| 題目 | 原frame／本次框編號 |
|---|---|
| Q1 | 0／0 |
| Q2 | 38／0 |
| Q3、Q4 | 86／1、86／0 |
| Q5 | 95／0 |
| Q6、Q7 | 105／0、105／1 |
| Q8、Q9 | 112／0、112／2 |

人工只需判黃色框主要支持「投手／其他人／多人難以分開／不確定」，可附局部或截斷備註。
不可因框碰到一個投手點就當整框正確，也不用猜被遮住的關節。
reviewer、UTC時間、結論、原話與備註均保持null；空白generation snapshot不冒充已覆核。
後續若有實際答覆，另存來源綁定的人工紀錄，不覆寫raw或既有GT。

## 執行修正歷史（完整保留）

1. `_01`：115格／177框已封存，evaluator CLI的plan參數名稱不符，尚未進入比較即失敗。
   修正CLI並新增入口回歸測試。原凍結程式與結果保存在該輸出的`frozen_code/`。
2. `_02`：相同producer／偵測設定再次封存115格／177框。原「順序亦須完全相同」重播
   fail-fast；API順序不穩定。兩次完整封存的逐格框／分數multiset完全相同，只有
   33、36、50、53、68、78、79、81格順序不同，像素／PTS差異0。
3. `_03`：**觀察到上述現象後才修正比較方式**，並再次先凍結程式／測試再量測。
   原API順序全部保留，重播以完全相同框／原分數multiset核對，重覆數不能丟棄；
   另報順序差異。沒有新增數值容差、改框、排序producer輸出或調偵測參數。
   `_02`快照、失敗原因、前版plan／seal的SHA鏈均保留。

共三次完整量測各115格；最後一次另有115格完整重播。第二版中途失敗的重播格數未記錄，
不宣稱確切總推論次數。此比較修正沒有被描述為最初事前規則。

## 檔案與驗證

正式本輪輸出：`analysis_results/phase2_person_support_20261009_03/`。

- `person_measurements.json`：GT blind完整原始框／score／像素／時間receipt。
- `evaluation/person_support_evaluation.json`：全部框、完整重播、人工幾何對照、缺值與限制。
- `evaluation/ownership_questions.json`、9張PNG、`ownership_contact_sheet.png`：空白新題目。
- `source_integrity_before.json`、`evaluation/source_integrity_check.json`：原374實體來源SHA。
- `independent_audit.json`：獨立核對。
- `full_test_suite.log`、`full_test_suite_result.json`：完整suite與正式五片E2E紀錄。

完整suite **348項：346 passed／0 failed／0 errors／2 skipped**，包含正式五支影片的
真實`analyze-pitch` E2E。兩項skip為本機Windows無法建立file symlink的案例；
directory-junction保護回歸通過，沒有把skip當作pass。新增26項全部通過。
原374份受保護實體來源在執行前、比較後與獨立核對均保持原SHA；測試後再核對保存在
`after_test_integrity_check.json`。五球原素材、raw、人工GT與原正式結果不變。

## 決定與下一步

目前只有獨立的person候選證據，尚無人工整框歸屬或完整可見人體範圍GT；
pitcher identity accuracy、box IoU、新warning policy／TP／FN／FP都保持null。
原TP3／FN18／FP9／TN562與Phase 2 NOT PASSED不變，不部署至正式核心。

先完成這九個框歸屬的最小獨立確認。若只能支持「附近有人」、局部框或其他人，
停止此候選，不調參或裁切使它通過；若確有投手歸屬，才另定五片592格評估與warning規則。
交付八球維持candidate／pending，不分析、不提升，不進Phase3。
