# Phase 2：HOG 人體候選範圍試驗結果

實測：2026-10-09；覆核紀錄收尾更新：2026-10-10（台灣）。
**隔離量測、幾何核對及九個抽樣框的人工歸屬覆核已完成。**
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
| 新框歸屬覆核題／人工答案 | 9／9；另存人工紀錄，原空白snapshot保持不變 |

四點containment不是全身框IoU或骨架正確率。**7格重大失效仍能讓錯誤raw肩髖點落在
某個人體框裡，因此不能直接用「有框支持骨架」當可靠性通過條件。**
沒有替人體框指定投手；原raw與人工XY的框內／框外關係全部保留，不挑最佳框冒充自動選對。
173個不可觀測及2個不確定點不使用隱藏XY補值。

已直接檢視九張候選圖；範圍大小不一，有的只框住局部身體，畫面也有打者／捕手等其他人。
這項工具端影像檢查只確認review圖可讀；HSU之後提供的實際答案分開保存如下。

## 九個框歸屬覆核已完成

固定抽樣0／38／86／95／105／112格，每格最多兩個最高raw SVM框，同分依x/y/w/h。
實際產生九題，其餘168個框保持未覆核；不重做原5/5 canonical GT或逐關節人工標註。

| 題目 | 原frame／本次框編號 | HSU原回答 | 確認歸屬 | 明確範圍補充 |
|---|---|---|---|---|
| Q1 | 0／0 | 投 | 投手 | 未提供 |
| Q2 | 38／0 | 局 | 投手，依另筆補充確認 | 局部 |
| Q3 | 86／1 | 局 | 投手，依另筆補充確認 | 局部 |
| Q4 | 86／0 | 他 | 其他人 | 未提供 |
| Q5 | 95／0 | 投 | 投手 | 未提供 |
| Q6 | 105／0 | 投 | 投手 | 未提供 |
| Q7 | 105／1 | 他 | 其他人 | 未提供 |
| Q8 | 112／0 | 投 | 投手 | 未提供 |
| Q9 | 112／2 | 他 | 其他人 | 未提供 |

人工只需判黃色框主要支持「投手／其他人／多人難以分開／不確定」，可附局部或截斷備註。
不可因框碰到一個投手點就當整框正確，也不用猜被遮住的關節。
HSU原話：`投/局/局/他/投/投/他/投/他`。Q2／Q3最初只記「局部」、歸屬null；
經另題確認，HSU明確補充「兩個都是投手的局部」。原話及補充分開保留，不倒改原token。
合計**6個投手框（其中2個明確局部）、3個其他人框，歸屬待確認0題**。
其餘7個框的完整／局部範圍未另詢問，保持未提供，不將「投」推成完整全身框。

獨立人工紀錄：
[`review_tools/person_support/HSU_pitch003_20261009_01.json`](../review_tools/person_support/HSU_pitch003_20261009_01.json)。
綁定原query manifest／影片／量測／evaluation／execution／總覽圖及每張圖的SHA，
逐題保留框座標、原分數與run-local index。reviewer使用本對話既有代號HSU；
記錄時間另存，人工未提供的新覆核完成UTC時間／confidence保持null，不挪用舊時間。
原空白generation snapshot及sealed evaluation仍保留當時0答案的原樣，人工覆核另存。

第86、105、112格的已覆核框同時有投手與其他人候選；這支持「須分辨主體」的限制，
沒有產生自動框選規則。其他人框屬person候選，不能直接計為person detector的false positive。
六個投手框也不代表關節對位正確、完整身體範圍或連續身份已驗證。

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
- `ownership_review_20261010_01/`：本次人工回覆的來源／逐題映射核對，不重跑影片。

完整suite **348項：346 passed／0 failed／0 errors／2 skipped**，包含正式五支影片的
真實`analyze-pitch` E2E。兩項skip為本機Windows無法建立file symlink的案例；
directory-junction保護回歸通過，沒有把skip當作pass。新增26項全部通過。
原374份受保護實體來源在執行前、比較後與獨立核對均保持原SHA；測試後再核對保存在
`after_test_integrity_check.json`。五球原素材、raw、人工GT與原正式結果不變。

## 決定與下一步

九題抽樣框已有獨立人工歸屬，但其餘168框、完整可見人體範圍及跨格主體指定尚未驗證；
pitcher identity accuracy、box IoU、新warning policy／TP／FN／FP都保持null。
原TP3／FN18／FP9／TN562與Phase 2 NOT PASSED不變，不部署至正式核心。

**本輪不採用HOG框作獨立投手對位警示，也不擴跑另外四片。**
六個投手歸屬提供局部證據，但同時存在其他人與局部框，尚無自動選投手／歧義處理／錯位規則，
且七個已知錯位格的raw四肩髖仍在某個框內。此次覆核不能直接讓原FN18通過。
這九題已完成，不再要求重覆判同一組。後續若沿此方向，須先另定有界的主體指定與五片592格
評估設計，將本組作開發案例並分開驗證；不依這九題調參、裁切或發明事後準確率。
本次只保存人工紀錄／更新文件，沒有新增推論或重跑完整suite；最新完整結果仍為上述346／0／2。
交付八球維持candidate／pending，不分析、不提升，不進Phase3。
