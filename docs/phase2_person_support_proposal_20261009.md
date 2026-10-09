# Phase 2：獨立人體候選範圍的有界試驗方案

2026-10-09（台灣）。**proposal only；未執行影片偵測。Phase 2 automatic reliability仍NOT PASSED。**

## 本輪決定

下一個候選是已安裝OpenCV的HOG＋內建person SVM，只先檢查003完整115格的可行性。
這套影像描述／分類器與目前MediaPipe不同，不讀其骨架來提出搜尋範圍。
它尚未被選為修復方案，也不是新增pose backend；正式MediaPipe保持原樣。

本機能力核對：OpenCV5.0.0、64×128視窗、3781個float32係數、detector size有效。
係數依little-endian float32的SHA256：
`cb2198952eaa5bc7e43d950b9f2aa1966528063c7295c7262133e7fa0d3d564c`。
沒有下載、安裝、推論、重算pose或修改任何人工答案。
[OpenCV官方HOG說明](https://docs.opencv.org/4.13.0/d5/d33/structcv_1_1HOGDescriptor.html)
確認其person classifier與多尺度矩形輸出語意；該文件版本為4.13，
本方案實際runtime與屬性以本機5.0 probe為準，不混用版本或假定所有預設完全相同。

## 為什麼只能先作可行性試驗

**人體框只支持「這附近可能有人」，尚不支持「這是投手」。**
打者／捕手也可能被偵測；錯誤骨架落到打者身上時，也可能獲得人體框支持。
框包住模型點不等於模型點對位，沒框不等於沒投手或pose failure。
彎身、快速投球、遮擋與不同比例可能使這個人像偵測器失效，是待量測風險，不能先宣稱效果。

CSRT API亦存在，但它需要已知目標起始框。本次不選CSRT：
以疑似錯誤pose作seed會保留原歸屬問題；把evaluator人工XY當seed會混用輸入與驗證。
若日後試人工初始化追蹤，須另定input annotation、不可觀測處理及排除初始化格的評估方式。

## 事前固定的量測範圍

1. 只用正式003原片、metadata與原影片技術紀錄；完整115格、510×628原像素／原小數PTS。
   不裁切、外部resize、鏡像、遮掉背景人、使用pose ROI或人工座標。
2. 一組設定，使用本機內建default people coefficients：
   `hitThreshold=0, winStride=(0,0), padding=(0,0), scale=1.05, groupThreshold=2.0,
   useMeanshiftGrouping=false`。本機HOG屬性逐項綁定；執行前核對binding接受此設定。
   這是獨立候選偵測器的固定設定，正式confidence gate／tracking threshold不改。
   不試參數網格、不用GT挑值，沒有新的warning cutoff。
3. 保存全部API回傳框與原始SVM分數、原始框順序、有效性、時間與decoded-pixel SHA。
   API內部已grouping，不宣稱取得全部sliding-window proposals。
   SVM分數不轉成已校準機率；無框保留空list，不補框。
4. **不選投手框、不加跨格tracking、不用離原骨架最近的框指定投手。**
   多框與背景人都保留；不因人工答案改框、排序、重跑或縮小搜尋。
5. producer／evaluator／測試及runtime須先實作、核對並凍結新的execution manifest，再跑影片。
   本輪JSON為proposal manifest，沒有尚不存在的runner hash，也不假稱已完成execution freeze。

## 量測封存後才可比較

| 已有人工參考 | 可以核對 | 不能推出 |
|---|---|---|
| 003的1205 visible XY | 可見關節對原raw的位置誤差、每個候選框與可見點的幾何關係 | 框的全身IoU、整框身份、看不到的關節 |
| 四肩／髖皆visible的106格proxy | 逐框包含哪些可見軀幹點；另9格缺proxy | 完整人體輪廓；GT挑出的框是自動選對 |
| 既有11個T/P/O像素中心 | 原位置在每個候選框內／外的描述性對照 | 整框投手／其他人歸屬；背景分割真值 |
| 原major／逐關節可靠性 | 原VIDEO錯誤與量測可用性的背景 | 新人體偵測準確率、新警示TP/FN/FP |

evaluator可讀原raw及以上既有人工來源，producer不可讀。
不依人工框選「最佳候選」後報為自動準確率；所有115格、每個回傳框與缺值完整保留。
不把原資料改名成未見過的holdout，不重做已完成的5/5 canonical覆核。

## 若有候選框，最少還缺什麼

- **主體歸屬：** 候選框主要圈住投手／其他人／多人難以分開／不確定，
  必須有原圖上的獨立人工答案。既有關節XY及T/P/O中心不能自動補這個答案。
- **若要報IoU／框位置誤差：** 另需可見投手範圍參考，保留遮擋、截斷與不確定；
  目前沒有這種GT，本試驗不要求先重標整片，也不報IoU。
- **若要報跨格身份穩定：** 先定義可核對的投手指定與歧義／中斷處理，
  一般person框與SVM分數不足以建立身份或證明沒有switch。

未產生候選圖前不請HSU憑空判框。若量測能提出可核對候選，才建立最多12個框的人工題目：
使用既有診斷格0／38／86／95／105／112，各取最多兩個最高原始SVM分數框，
同分按x/y/w/h固定排序。這是已知案例的evaluator抽樣，不是producer觸發規則或泛化樣本；
其餘框保持未覆核，不因未問就判錯或判對。保存原話、reviewer、時間與uncertain。

## 停止與延伸條件

- 沒有框、框反覆落到其他人、或主體歸屬無法核對：保存不可用／歧義，停止這個候選，
  不用改參數、裁切或改挑frame把它調到通過。
- 若只能知道「某個人」而仍不能指定投手：不能叫作投手影像對位證據，亦不進正式warning。
- 若有可核對的投手歸屬，才另定相同方法在五片592格的評估與warning policy；
  在此之前不產生新TP/FN/FP或任意總分／通過線。
- 不因提出方案或API可用就標Phase2 PASSED。原FN18及原驗收結果保持不變。

原374個保護來源／正式五球／GT／raw保持原樣。交付八球仍candidate／pending，
不作此試驗、不提升、不取代正式素材；不進Phase3。
