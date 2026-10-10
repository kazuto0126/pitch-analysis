# 進度摘要

更新日期：2026-10-10（台灣）。

## 最新：五球裁切漏格與關節損失診斷完成

見 [損失診斷](phase2_roi_loss_diagnosis_20261010.md)與
[完整輸入比較提案](phase2_complete_input_comparison_plan_20261010.md)。
已保存候選重播原selector592格完全一致；587格配對有28新增選取損失、25新增選取、7共同未選。
新四片28損失／6新增選取，淨少22；003新增19。28損失拆為12後端無候選／15原selector拒絕／1歧義。
15拒絕中14格只有5／8主要關節達原0.35、未達原6個要求；005／67肩至踝高度0.1467945低於原0.16。
右肘65損失／15新增可用、右腕75／17、左膝99／28、左踝100／29；這是可用性，不是人工準確率。
002雖174格全selected，右肘仍少15格，原IMAGE肘點都在框內，不能只歸因於手腳出框。
診斷推論0次，完整suite另跑正式五球E2E；**455 passed／0 failed／0 errors／2 skipped**（457項，54.968秒）。
374來源與62上游引用不變；正式核心／GT／五球不改，交付八球仍candidate／pending。
Phase2仍**NOT PASSED**，原FN18未修復。輸出：`analysis_results/phase2_roi_loss_audit_20261010_01/`。
已提出MoveNet MultiPose Lightning v1隔離相容性第一關，需依原「benchmark先提案」指示等核准。
最多1次合成圖、正式影片0次；下載／安裝尚未執行，MediaPipe維持baseline。
本輪至commit／push與乾淨checkpoint停止，不開始Phase3。

## 前次：五球人工起點固定裁切對照完成，設定不採用

見 [五球結果](phase2_assisted_roi_cohort_results_20261010.md)。HSU已確認001／002／004／005第0格的
投手與當時可見肢體範圍，實際「全部正確」另存，保留原草案與空白snapshot；不延伸成全片身份GT。
四片各量測一次477格；003沿用封存追蹤／pose／XY評估，新增呼叫0。完整592格保留，成效587格。
裁切selected552／全圖IMAGE555／原VIDEO584；逐片裁切對IMAGE差為 **-3／0／+19／-7／-12**。
新四片單獨444／473 vs IMAGE466／473，少22格，不能用003改善掩蓋退步。
587次後續tracker update均native success，仍可見伸展手腳在框外；API成功不等於輸入完整或對位正確。
裁切右肘gate且input-supported：001=44／86、002=139／174、003=77／114、004=68／113、005=80／100。
這是可用性而非人工準確率。精確XY只003沿用；其餘四片XY／新warning／identity／event accuracy皆null。
39個事前固定圖完成工程檢查，無新增人工GT；原5/5 GT保持reviewed。
固定窄框裁切未通過五球適用性，不接入正式核心；自動Phase2仍**NOT PASSED**。
下一步先診斷新增缺失與動作範圍，再定保留完整輸入的有限方案，不調padding／gate或自動fallback。

完整suite **442 passed／0 failed／0 errors／2 skipped**（444項，73.972秒，含正式五球E2E）。
374受保護來源與上游封存／答案不變，正式五球與src不改，八顆交付片仍candidate／pending。
輸出：`analysis_results/phase2_assisted_roi_cohort_20261010_01/`。
實際execution為`_02`；`_01`因推論前補強文件SHA檢查而未使用，完整保留，沒有重跑或改設定。
本輪至checkpoint停止；沒有進Phase3。

## 前次：六格裁切失效已分類，五球驗證前置方案已保存

見 [下一關方案](phase2_roi_completeness_fiveclip_plan_20261010.md)。本輪只讀舊輸出、重播原selector，
115格receipt完全一致：63／68／79／81為後端無候選；65只有5／8主要關節達原0.35條件，
80身體高度0.07945低於原0.16，故原selector拒絕。這不是統一的追蹤失敗或遮擋。
44個框外可見點分布26格，以左腕21、右踝11最多；不以人工座標反推新padding。
固定ROI／低confidence／外插／歧義的缺失語意，人工參考僅離線評估，不進producer決策。
五球保留592格；若各片人工起點排除frame0，成效587格。只有003有精確XY與已確認seed；
其他四片的起點框圖已準備並在對話提出確認，四份草案的人工作答仍null，不能冒用舊review。
5/5 canonical GT不用重做；回覆另存，不覆寫原草案。
尚未選新padding／fallback或擴跑四片；人工seed路線僅能稱人工輔助實驗，自動Phase2仍**NOT PASSED**。
本輪推論0／tracker0／新GT0；374來源不變。最近完整測試仍409passed／2skipped，沒有假稱本輪重跑。

## 前次：固定追蹤框裁切 pose 對照完成

見 [結果](phase2_tracked_roi_pose_results_20261010.md)。新增隔離量測／離線比較與28項回歸。
003原115格只跑一次，沿用已封存CSRT框、同一full模型／設定／原selector，沒有重跑tracker或改正式核心。
排除人工起點第0格，1195個可見人工點中1151框內／44框外；全部缺值與不可觀測／不確定保留。
相同847個支持配對點：全圖IMAGE均誤差19.1565→裁切9.0031px，478改善／369惡化。
原major18共同113點：80.4089→10.8965px；其他96共同734點：9.7266→8.7116px。
改善集中原嚴重漂移；不是每點皆變好，不把原major標籤當成新結果全對證明。
裁切仍6格拒絕、64個可見點無輸出、95個低於gate；原major可見投球肘87–96仍低於既有gate。
九張固定圖實際檢查，肩髖漂移改善但局部／框外肢體仍有問題；沒有新增人工GT。
只是一片已知資料、人工初始化條件下的候選證據，尚未正式接入或驗證五球警示；Phase2仍**NOT PASSED**。
下一關為輸入完整性／缺失棄權與五球驗證設計，未降低門檻、直接擴跑或開始Phase3。

完整suite **409 passed／0 failed／0 errors／2 skipped**（411項，含正式五球E2E，63.469秒）。
兩項Windows file-symlink限制；374保護來源與上游封存／人工答案不變，交付八球仍candidate／pending。
輸出：`analysis_results/phase2_tracked_roi_pose_20261010_01/`，逐點JSON／九張圖／完整來源核對可追查。

## 前次：人工起點主體延續試驗及十個新框覆核完成

見 [本輪結果](phase2_subject_assignment_results_20261010.md)。新增隔離CSRT量測／離線比對及35項回歸。
只跑003一次，採前次HSU確認的第0格框與27個預設；producer只讀影片／metadata／technical／Q1輸入。
完整115格保存，初始化1次、後續update114次全native成功；第0格排除成效分母。
1195個可見人工點有1151框內／44框外；四肩髖proxy105／105在框內，另9格缺參考。
固定10個新框由HSU回覆「全部都是投手」，另外保存；extent／confidence／完成時間未提供皆null。
只支持人工初始化後的有限主體延續，未證明114格身份／骨架全對或自動選人可靠。
18格原重大錯位有10格連錯誤raw四肩髖仍在框內，原FN18未修復；Phase2仍**NOT PASSED**。
未採用新warning或改正式核心；下一步須處理框內錯位證據及歧義，再定592格回歸方案。

完整suite **381 passed／0 failed／0 errors／2 skipped**（383項，含正式五球E2E）。
兩項Windowsfile-symlink限制；原374來源、前次九題與HOG封存保持hash。
輸出：`analysis_results/phase2_subject_assignment_20261010_01/`，包含新圖、獨立核對與人工覆核assessment。
原5/5 GT保持COMPLETE；交付八球仍candidate／pending，沒有進Phase3。

## 前次：人體候選試驗及九個框的人工歸屬已完成

見 [本輪實測結果](phase2_person_support_results_20261009.md)。新增隔離量測／比較工具及26項回歸，
003完整115格產生177個人體候選框／114格有框；完整重播115格的框／原分數multiset差異0。
API回傳順序另有8格不同，原始順序與各次框編號完整保存，不當跨格track ID。
106格可用四肩髖人工proxy、9格缺值；93格有框包含四點，僅描述幾何關係。
18格原重大失效全部有框，其中7格連錯誤raw四肩髖點也被包含；有框不代表骨架正確。

固定抽樣9題已由HSU完成，獨立紀錄於
`review_tools/person_support/HSU_pitch003_20261009_01.json`：**6投手／3其他人，其中2個投手局部框**。
保留「投/局/局/他/投/投/他/投/他」及另筆「兩個都是投手的局部」補充；待確認0題。
其餘7個框的範圍未提供，不當成完整全身；原空白snapshot／量測／5/5 GT保持原樣。
人工完成時間與confidence未提供，保持null；記錄時間另存。不自動指定投手、不建立warning cutoff。
原FN18仍待修復，Phase2 automatic reliability **NOT PASSED**，identity accuracy／IoU／新警示數null。
CLI入口及多框順序核對修正均保留舊plan／結果／source快照；偵測設定不變、不放寬數值容差。
這9題已完成，不重覆要求覆核；另168框未標註。86／105／112格抽樣同時有投手與其他人框，
本輪不採用為獨立投手對位警示、不擴跑其他四片。後續須先另定主體指定／歧義處理與592格
驗證方案，不能依這9題調參後宣稱準確率。人體歸屬不是骨架正確性或連續身份驗證。

完整suite **346 passed／0 failed／0 errors／2 skipped**（348項，含正式五片E2E）；
兩項為Windows file-symlink建立限制，junction案例通過。原374個受保護來源hash不變。
輸出：`analysis_results/phase2_person_support_20261009_03/`，有獨立audit、完整receipt與九圖總覽。
正式五球、人工GT與分析核心保持原樣；交付八球仍candidate／pending，沒有進Phase3。
本次只存人工回答及文件，沒有重新推論或重跑suite；最新完整測試仍為上述346 passed／2 skipped。

## 能力核對與方案歷史（當時尚未執行，已由上節接續）

[獨立人體候選範圍方案](phase2_person_support_proposal_20261009.md)：
先限定003完整115格，以本機已有HOG/personSVM做有界可行性檢查。
能力probe確認3781係數／64×128視窗，綁定係數與runtime；**影片推論0次、下載／安裝0次**。
目前只有文件／proposal manifest，沒有新增runner、改核心或假稱取得新準確率。
人體框可能是打者；不能自動稱為投手定位。先保存所有候選與缺值，
若確有可核對候選，才提出最多12個框的獨立歸屬問題；不冒填GT、不重做原5/5人工覆核。
原374來源保持原hash，Phase2仍NOT PASSED；最新完整程式測試仍320 passed／2 skipped。
本輪僅文件與能力核對，未重跑測試／影片，未進Phase3。

## 最新：Phase 2模式對照checkpoint

見 [模式對照結果](phase2_pose_mode_results_20261009.md)。新增隔離量測／比較工具及13項測試，
同模型IMAGE／VIDEO完整592格實測；沒有改正式核心、門檻、selector、GT或原始輸出。
IMAGE selected560／原589格；560格共92,400數值逐項相同，另29格選取狀態變化。
003重大錯位18格中14格仍同樣錯位、4格ambiguous；相同918個gate可見點均誤差皆20.157145px。
缺少更多預測不是精度改善，本方向不採用，沒有新警示policy或新TP／FN／FP。
原FN18仍在，自動Phase2 **NOT PASSED**；原baseline評估與5/5人工覆核維持COMPLETE。

完整測試 **320 passed／0 failed／0 errors／2 skipped**（322項，含正式五片E2E）；
兩項Windowsfile-symlink建立權限skip，junction回歸通過。374份原保護來源hash未變。
輸出：`analysis_results/phase2_pose_mode_countercheck_20261009_01/`，含獨立核對及三張案例圖。
下一步需要獨立可核對的投手影像對位證據；不同模型benchmark先另列有界方案。
交付八球仍candidate／pending，不分析、不提升，不進Phase3。

## 2026-10-09 回歸核對與主線恢復

見 [逐項核對](handoff_regression_20261009.md)。兩次重跑各0新增／8跳過／0拒收；
SQLite批次1、素材8保持固定，events27→36→45僅為執行紀錄。
修正交付覆核入口的中間junction保護缺口，新增5項回歸測試；完整suite
307 passed／0 failed／0 errors／2 skipped，原有240項全部通過。
正式五球592格重新跑完整流程：10份reliability逐欄位0差異、35份預測檔逐byte相同。
原374份保護來源、交付21檔、候選40檔未變，9份registry無八球ID。
八球仍candidate／pending，不分析、不提升。
已回主線整理 [Phase 2修復案例](phase2_reliability_repair_20261009.md)，FN18仍待修復；
Phase 2 NOT PASSED不變，沒有開始Phase 3。

**Phase 1 = PASSED。**
**Phase 2 evaluation = COMPLETE；Phase 2 = NOT PASSED（自動可靠性未通過）。**

Phase 2 評估與收尾已結束；不再把已完成的人工工作記為IN PROGRESS。
原模型／門檻／pose／tracking／平滑／插值不變，沒有開始Phase3。
最終完整報告見 [Phase 2 final report](phase2_final_report.md)。

## 使用者另核准的交付候選接入（2026-10-08）

- 第一版 [交付讀取器](handoff_reader.md)：只依交付 `CONTRACT.md` v2 和 index 找批次。
  SHA 比對、候選複製、原 ID／本地 ID 與投手 ID 對照、unknown→null、SQLite 去重及拒收原因紀錄已完成。
- 每檔完整解碼，CFR=true、實際格數相等、分數 FPS 逐格 native PTS 偏差嚴格 <1 ms 才接收。
  contract 的第0格時間與 container start 分開保存，motion anchors 不轉成人工事件。
- 實測批次 `20261006T114959Z_Q8Bl2X4VKuw` 八球／3,396格全部通過匯入檢查；
  最大時間偏差0.000667ms。重跑新增0球、跳過8球，副本與交付資料保持不變。
- 本地 `data/intake/handoff/` 八球皆 candidate／review pending；沒有代填人工判定、沒有自動分析。
  每項人工提交須有判讀者、含時區時間、結論、備註；保留原答案與歷史。
- Phase 2 核心、五球正式素材、raw／GT與原輸出 hash 未變；沒有將 Phase 2 改標 PASSED。
- 實測證據：`analysis_results/handoff_reader_validation_20261008_01/`。
- 本次完整測試 **302 passed、0 failed、0 errors、2 skipped**（共304項，含正式五球E2E）。
  新增64項；兩項檔案符號連結案例因Windows建立權限跳過，實際目錄連結案例通過。

## 已完成

- 正式山本由伸5片Phase1素材保持原樣，superseded舊素材與Phase1stable commit保留。
- HSU canonical GT **5/5 reviewed**；六關節全592格人工定性判讀與exact／range／uncertain事件有來源。
- Tsai標註、HSU覆核003全115格／12關節；1205可見座標、173不可觀測、2不確定分開評估。
- 原警示對照、pose／tracking品質、可見座標與資料處理效果評估完成。
- 五片中文人工覆核影片、逐格reliability側檔與既有角度可用性側檔完成。
  肘角度246/592、膝角度530/592有本批定性覆核直接觀測輸入；原值保留，受限可用欄位留空。
- 本輪新增五片**既有自動提示**影片、JSON／CSV；沒有讀入人工GT。
  全592格／3552列、92個保存跳動端點完整核對；無提示仍不代表對位正確。
- 最終評估重算既有來源比較，建立 `phase2_final_assessment.json` 與 `release_status.json`，
  評估完成與自動驗收分開、`accepted=false`，沒有新增任意總分或通過線。

## Phase 2 最終測試與核對

**240 passed、0 failed、0 errors、0 skipped**，含正式五片真影片E2E，約42秒。
本輪新增25項測試（提示14、收尾11），沒有待修失敗。
二次唯讀核對：374份不重複來源hash未變；五片影片完整解碼與33張PNG原區域核對通過。
中文提示面板已看五片代表畫面；H264是有損重編碼，不宣稱解碼後像素完全相同。

最終輸出：`analysis_results/phase2_final_yamamoto_20261008_02/`，先看 `START_HERE.md`。
新提示影片：`analysis_results/phase2_automatic_cues_20261008_01/`。
程式／測試／計畫／報告進Git；大型影片與衍生分析留在本機ignored目錄。

## 已知問題與未通過原因

- 人工重大失效21格，原整體提示TP3／FN18／FP9，漏掉003的87–104全部18格。
  加既有跳點的診斷聯集TP13／FN8／FP56，沒有變成新detector。
- 高visibility／raw coverage／observed不等於正確。投球肘人工不可靠84格中72格仍observed。
- 003相同1174可用點raw均誤差21.9504px、clean22.0292px；97.43%是保留率，不是精確度。
  不可觀測位置不作精確真值，插值沒有認證可以恢復看不到的關節。
- 只有一位投手；沒有identity-switch陽性、其他片精確人工XY或自動事件預測可估準確率。
- 早期KLT／mask／小衣物patch方向有歸屬反例，未採用；原實驗和SDK限制保留紀錄。
- 原 `analyze-pitch` 未自動使用人工覆核側檔；新視圖不是自動定位修復。

## 仍待外部補充與後續待辦

- 同學 `pitch_005` 獨立事件補充未回傳；canonical啟動／最高抬腿uncertain合法保留。
  不冒填、不要求重做已完成canonical覆核，也不把這份補充當目前GT完成的必要條件。
- 使用者已核准回主線修復；本輪模式對照已完成且不採用，下一個方法需先固定證據與驗證方案。
  原baseline的NOT PASSED結論沒有改標。
- [x] 使用者已另行核准 `D:/project/pitch-video-handoff` 第一版候選讀取器；
  規格只依 `CONTRACT.md` v2，交付唯讀，不依賴另一專案程式碼。
- [ ] 八球人工輸入覆核、正式 metadata 轉換／提升及後續分析另行安排。
  第一版只完成候選接入，不因程式與時間檢查通過就認證素材或 Phase 2 自動可靠性。

候選讀取器已收尾；後續使用者另核准的Phase2修復checkpoint見本文最上方。
沒有開始Phase3或新球分析。
供片需求見 [INPUT_REQUIREMENTS](INPUT_REQUIREMENTS.md)；完整歷史見 [current_status](current_status.md)。
