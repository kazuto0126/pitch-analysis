# 單球人物框引導原生RTMPose

此入口是獨立、未校準的候選分析；正式MediaPipe及品質gate不變。
本輪依[核准方案](phase2_person_box_native_plan_20261021.md)只處理大谷補片第2球321格。
本次固定執行已完成，選人政策不採用；[結果與停止決定](phase2_person_box_native_results_20261021.md)。

## 固定流程

1. 核對來源SHA、既有人工作業覆核、crop／ROI、格數與分數FPS時間。
2. YOLOX-m只看已核准的動作crop，保留模型實際輸出的dets／labels及binary。
3. 沿用模型內建NMS（graph實際score約0.01、IoU約0.65），不做第二次NMS。
4. 最後固定score≥0.7、class0=person、人物框中心在已確認的操作ROI內。
5. 合格框唯一才呼叫既有RTMPose；0框或多框分別記no_subject_box／ambiguous_subject_boxes。
6. 人物框決定固定1.25 padding的affine；取樣僅來自核准動作crop，crop外填黑。
   原bbox／原圖XY不截斷，不額外遮黑人物框周圍crop內的動作空間。

人物框中心條件與舊selector的四個軀幹點條件不同；不可聲稱它是原selector，
也不能把高偵測分數或唯一框當作真人身分真值。

## 執行入口與一次性限制

設定：`config/pilots/ohtani_person_box_20261021.json`。
獨立入口：`scripts/run_native_person_box.py <config> <new_analysis_results_directory>`。

每格最多一個detector呼叫、一個pose呼叫；兩者各有321次上限。
有歧義時pose不執行，不以最高分、前格人物框或舊骨架回退。
握手／相容性檢查不執行模型warmup；真實呼叫失敗不重試。

設定中的once_only_claim_path會在正式開始前獨占建立。
已執行後即使改用另一個新輸出目錄也會拒絕重跑；不要刪除claim、改名或改路徑來重試。
模型／來源／實作SHA在設定中固定；既有資料與上輪輸出不覆寫。

## 結果語義

- 有執行pose：原生COCO17／原圖pixelXY／原生score，仍not_calibrated。
- 未執行pose：17點全missing、native_score=null、input_mode=not_run；
  ROI與affine保持null，不虛構未曾執行的幾何。
- `pose_not_run`與原因明確保存，cached manifest不能包裝這種未執行影格。
- 沒有Z／visibility／presence的能力，保持null；不padding33、不插值或混用兩模型座標。
- 不可觀測／不確定的人工GT不變；系統沒有新增人工判讀。
- 失去舊版有座標的格屬於可用性損失，不能以missing宣稱改正。

## 輸出

- `run_receipt.json`：執行、實作核准、兩模型呼叫與失敗原因。
- `detector_worker/`及`pose_worker/`：各自started／completed journal與全部原生binary。
- `person_boxes.jsonl`：完整321格、全部模型輸出列、本地篩選原因及歧義。
  模型內建NMS之前被抑制的候選無法取得；模型輸出列也可能包含padding，不是實際人數。
- `native.partial.jsonl`：逐格原生紀錄，執行失敗仍保留已完成部分。
- `rtmpose/supplement_002/`：完整native dataset、逐關節摘要及overlay。
- `person_box_summary.json`：無框／歧義／選中及bbox邊界情形。
- `comparison_summary.json`：同一原圖同一影格的新舊座標可用數與新增missing清單，不是準確率。
- `review_all.html`與`visual_review/`：原片／舊RTMPose／新結果並列。琥珀框為歧義候選，非人工身分標註。

模型權重與大型影片留在本機analysis_results，沒有上傳或重散布權重。
取得來源、模型metadata／graph常數、軟體及資料集條款紀錄位於
`analysis_results/phase2_person_box_preparation_20261021_01/`。
