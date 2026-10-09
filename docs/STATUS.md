# 進度摘要

更新日期：2026-10-09（台灣）。

## 下一個方案已具體化，尚未執行

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
