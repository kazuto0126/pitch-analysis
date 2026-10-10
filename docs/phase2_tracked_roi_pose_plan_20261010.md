# Phase 2：封存投手框的裁切 pose 對照方案

2026-10-10（台灣）。建立本方案時尚未執行裁切pose；事前凍結後只跑003一次。
**正式核心與門檻不變；Phase 2 automatic reliability = NOT PASSED。**

## 問題與既有證據

前次CSRT人工起點試驗有115格receipt、114次後續更新成功，HSU十個固定新框皆回覆投手。
105格可用人工四肩髖皆在框內，但原18格重大錯位仍有10格錯誤raw四肩髖也在框內：
87–92、101–104。框內不等於關節對位；不把框包含當成新可靠性警示。

本次測試**輸入裁切的敏感性**：同一模型、相同信心設定、相同selector，
改用已封存CSRT框的影像區域。裁切同時改變上下文、人物相對輸入尺度及邊界，
不能把差異單獨歸因為移除打者。先前全圖IMAGE、同模型mask、固定衣物與KLT試驗均不是此arm。
本次不是新pose後端、3D、人工修點或正式演算法更新。

## 固定輸入與邊界

- 只用正式003原115格、510×628、原像素／PTS；不重跑CSRT、不挑框、不重新seed。
- producer只讀原MP4、metadata、technical、封存CSRT measurements與現有full模型。
  不開raw pose、人工XY、canonical GT、十題回答或比較結果；上游ROI含人工起點，
  因此僅能稱人工初始化條件下的試驗，不能稱端到端完全無人工資訊。
- parent preflight核對上游來源鏈、實際人工回覆、原374個受保護檔案；evaluator在新pose封存後
  才讀人工參考與舊全圖IMAGE／VIDEO。人工GT與所有舊prediction保持原樣。
- runtime、native binding、model SHA、原selector與capture/backend程式SHA及新工具／測試在execution
  manifest固定；不放入尚未存在程式的假SHA。只一組設定、一次forward，無參數搜尋。

## 裁切及座標契約

1. 對每格原生矩形取`floor(x,y)`、`ceil(x+w,y+h)`，與影像範圍交集成半開slice。
   原生框不改；derived crop邊界另存。沒有ROI／空交集保持缺值，不補前框或回退全圖。
2. 實際slice原BGR、複製為contiguous陣列、轉RGB。無padding、外部resize、mirror、mask或旋轉。
   不把ImageProcessingOptions的ROI欄位當成此PoseLandmarker支援；直接傳新裁切image給IMAGE.detect。
3. 使用既有`pose_landmarker_full.task`，num_poses=4、三個confidence設定皆0.5，segmentation=false。
   使用IMAGE，主要對照既有全圖IMAGE；原正式VIDEO只作次要對照，避免將mode差異混為裁切效果。
4. 全部候選33點先保存crop normalized原值，再映射至全圖：
   `x=(x0+u*crop_width)/510`、`y=(y0+v*crop_height)/628`。
   visibility／presence不改、不clamp外推點；全圖mapped候選才交原PitcherSelector，一個fresh實例。
   每格包括無ROI格皆更新selector一次；禁止依人工誤差選候選或跨arm沿用index。
5. 原crop z保留；若另存全圖width-relative z，僅`z_crop*crop_width/510`，不平移深度、
   不當校準3D、不納入本次精度或selector決策。
   [官方輸出契約](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python)
   說明XY依輸入寬高normalized、z約同x尺度；本次只比較原像素XY。
6. API例外、非finite／33點格式不符、來源像素／時間錯誤中止完整封存，不製造空成功結果。
   正常空pose保存原rejected／ambiguous與缺值；不插值、平滑、修座標或變更confidence gate。

## 事前分母、支持範圍與比較

第0格是上游人工初始化的一部分，保留receipt與selector history，排除成效分子／分母。
固定114格、1368人工關節紀錄：1195 visible、171 not_observable、2 uncertain。
1151個visible在封存ROI內、44在外；18格原major有190visible（189內／1外），
其餘96格有1005visible（962內／43外）。不可觀測／不確定XY不當精確真值。

44個ROI外可見點留在總分母與逐點表。即使模型外插出座標，也不把沒有輸入像素的估計宣稱
為可靠直接觀測；raw gate與input support分開。新點超出crop normalized半開[0,1)同樣另列外插，
保留原值，不透過clamp變成有效點。缺選取、低於既有gate、ROI缺失、外插與框外參考分別列出。

主要配對CROP與舊全圖IMAGE，次要配對CROP與正式VIDEO：同一visible reference、
reference在crop內、兩邊通過既有gate且新預測在crop輸入內，才作supported paired XY誤差比較。
逐點報原／新誤差及差值；依joint、原major18、其他96及原10格框內錯位分組，
完整列common count、mean／median／p90與變好／變差／相同，不只挑有利關節。
另報全部1195點各arm availability與條件誤差，清楚標出選取集合不同不可直接相減。
共同集合縮小或缺預測本身不是精度改善，不發明總分、PCK cutoff或數字通過線。

canonical major只是**舊prediction**的已知case group，不能當作新CROP正確性標籤。
本次沒有新warning policy、TP／FN／FP、identity accuracy或自動事件；這些欄位保持null。
同模型兩輸入的一致性也不能獨立證明正確。

## 執行後停止條件

先完成工具／來源與必要測試，再凍結；完整結果保存後不追加padding、改gate、挑候選或換模型。
若有幾何改善，僅記為已知003、人工起點條件下的候選證據，同時保留所有惡化與缺失；
不直接修復raw、更新正式核心、擴跑其餘四片或宣告Phase2通過。
若未改善，記錄負結果並停止此設定，不能靠多輪試參救回。
少量固定示例圖用於檢查輸出與顯示：38、70、78、87、92、95、101、104、112。
圖只顯示模型輸出與已存在可見人工點，不新增人工答案或重開5/5 GT。

輸出使用新的`analysis_results/phase2_tracked_roi_pose_20261010_01/`，不覆寫前次試驗。
完成後跑完整suite（含正式五球E2E）、核對原374與上游封存SHA、更新狀態文件並commit/push。
八個交付素材仍candidate／pending，不分析或提升，不進Phase3。
