# 進度摘要

更新日期：2026-10-08（台灣）。

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
- 自動警示修復與再驗收須另行安排；本輪以實際NOT PASSED結果結束。
- [x] 使用者已另行核准 `D:/project/pitch-video-handoff` 第一版候選讀取器；
  規格只依 `CONTRACT.md` v2，交付唯讀，不依賴另一專案程式碼。
- [ ] 八球人工輸入覆核、正式 metadata 轉換／提升及後續分析另行安排。
  第一版只完成候選接入，不因程式與時間檢查通過就認證素材或 Phase 2 自動可靠性。

完成候選讀取器後停止。沒有開始Phase3或新球分析。
供片需求見 [INPUT_REQUIREMENTS](INPUT_REQUIREMENTS.md)；完整歷史見 [current_status](current_status.md)。
