# Phase 2：人物框引導原生 pose 的單球修正方案

2026-10-21。**PROPOSED — 等待新模型／native 接點範圍核准，尚未實作或推論。**

## 本輪先完成的檢查

上一版 live 入口已交付，commit `3be4f93402280cf00407a3dacdcd9c13b86554c0`。
本輪只讀程式、已保存結果與上游文件，沒有重跑五球或追加標註。

`native_pose_estimator.prepare_rtmpose_input` 目前把固定 `[192,216,768,720)`
完整動作 crop 當成單人 bbox，再做原生 affine。這個範圍包含部分打者，
沒有在 pose 前先辨識「哪個人物框屬於投手」。
第2球準備段混接投手下身／打者上身與這個限制相符，但尚未證明人物框一定能修好。
舊 `PitcherSelector` 是33點的 pose 後選擇器，不能直接套在 COCO17 上。

上游 Body 實作則先偵測人物框，再將 bboxes 傳給 RTMPose：
[作者的 Body pipeline](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/solution/body.py)。
這裡提出的是補上這個接點，不是再比較更多 pose 模型。

## 建議核准的固定範圍

只跑 `supplement_002` 全部 **321格**，含準備到收尾，不因錯例裁掉任何片段。

- MP4：`input/shohei_ohtani/phase2_supplement_20261020_01/supplement_002.mp4`
- SHA：`b1586bdde9383e3b247bcc7d7974a3f15b0fed173848926d5217f261b87bab8e`
- FPS：`60000/1001`；第0格0秒。現有HSU輸入覆核與操作範圍保留。
- 偵測仍只看HSU已確認的完整動作crop；不擴大取樣範圍。
- 新增 **一個 YOLOX-m HumanArt 人物偵測器，640×640、CPU ONNX**。
  原RTMPose-m權重、192×256輸入、隔離環境與原生17點語義保持。
- 最多 **321次 detector + 321次 pose**；只對唯一選中的人物框跑pose，缺框或歧義不跑pose。
  沒有warmup／合成真實推論、自動重試或第二套模型。

### 新模型來源與固定前處理

只允許此上游Body balanced設定列出的OpenMMLab ONNX archive：

`https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_m_8xb8-300e_humanart-c2c7a14a.zip`

[官方MMPose模型清單](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose)
列有同名YOLOX-m；[Body設定](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/solution/body.py)
提供該ONNX URL與640×640尺寸。這不是已下載／已驗證可用的承諾。

核准後先取得archive，記錄URL／下載時間／archive及ONNX SHA／模型metadata／授權資訊，
固定到單次執行設定，再接觸影片推論。只讀模型metadata做相容檢查，不做warmup。
若來源不可取得、授權不合適、輸出語義無法確認或既有runtime不相容，停止回報；
不自行換鏡像／模型、匯出權重或升級環境。

沿用上游YOLOX的BGR resize／114 padding／座標還原方式；
固定最終detector score下限0.7；若輸出尚未做NMS，固定NMS IoU0.45，不用這支影片或GT調整。
[上游前後處理參考](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/object_detection/yolox.py)。
若archive已內建NMS，沿用並封存其設定，不再做第二次NMS，最後仍以0.7篩選。
必須能確認其內建score下限不高於0.7且NMS設定明確，核對後在接觸影片前封存；
否則停止，不能猜測或改動匯出圖。這些相容分支只依模型metadata決定，不能依影片結果選擇。
以上是新detector的操作設定，不修改原MediaPipe confidence／quality gate。

## 單一人物選擇政策

1. 保存全部模型實際輸出的raw tensor／人物框／分數，以及本地去除原因；只考慮person。
   若模型內建NMS，內部已被抑制的候選不可取得，必須明列，不能聲稱保存了它們。
2. 人物框中心需落在已確認的原圖操作ROI `[0.22,0.40,0.46,0.88]`。
   這是新native框選擇條件，**不等於**原selector的四個軀幹關節都在ROI內。
3. 合格框恰好一個才執行pose；0個記 `no_subject_box`，多個記 `ambiguous_subject_boxes`。
   不以最高分猜一個，不回退舊混合骨架，也不用前格框補長缺失。
4. person bbox決定原生center／scale及固定1.25 padding；取樣畫布仍只有已核准的動作crop。
   人物框周邊的padding可以讀取這個crop內的像素，只有超出動作crop才填黑，
   不額外把人物框外背景遮黑。原bbox不截到邊界，另存超出crop及取樣padding情形；
   非finite／非正面積／無有效畫布交集就missing，不把被裁掉的肢體當作完整可見。
5. 原生17點及模型score保持；遮擋座標仍是模型估計，不是人工可見或可信標籤。

這個保守政策可能漏掉真正投手或仍留下混合框；必須一起報告，不能靠大量missing宣稱準確。
本輪不新增追蹤總分、ReID、時序平滑或遮擋點補值。

## 需要改動的位置

| 位置 | 核准後的有限改動 |
|---|---|
| 新獨立detector adapter／worker | 單一模型輸入輸出、候選框、固定後處理、呼叫上限及journal |
| native estimator可選接點 | 接收當格人物框，保存原圖bbox／crop／affine；舊固定crop呼叫保持相容 |
| 新獨立producer／設定 | 保存321格完整時間軸及missing原因，不改已封存的上輪執行設定或結果 |
| native contract必要處 | 優先沿用逐格geometry與model_selection；若有必要新增明示模式，只擴充native驗證 |
| 測試／結果文件 | 座標還原、0／1／多框、歧義不推論、無回退、時間／SHA與舊介面相容 |

不修改 `analysis/pitch.py`、`workflow.py`、`pose_capture.py`、`subject.py`、
`clean_pose.py`、`features.py`、正式MediaPipe、任何既有門檻、raw或人工GT。
不重新開啟HOG／CSRT／失敗警示分類器，不搜尋靜態crop倍率，不新增標註或投手。

## 一次交付及停止規則

1. 實作與無模型測試完成後，321格每格至多一次detector與一次pose，失敗即保存停止。
2. 分別列出detector框數、唯一選中、無框、歧義、pose執行／缺失數及最長missing span。
   分母固定321格；原本已有座標的格若變missing須明列，不能當成修復。
3. 檢查固定第 `0,19,38,56,75,94,113,132,151,159,169,188,201,207,226,245,264,282,301,320`
   格的原片／舊RTMPose／新結果，並抽查偵測缺失／歧義／裁肢格。
   若仍有錯人／混合／裁肢直接列出；不自動生成人工GT或聲稱逐格正確率。
4. 交付完整overlay、321格逐格人物框、原生輸出／缺值原因及舊結果並列觀看。
5. 完整suite一次；原正式五球相容、來源保存、獨立commit／push後回報並停止。

即使接點有效，也只代表此單球的有限修正結果。沒有自動擴到另外四球、
正式採用、score校準或Phase2通過；不進Phase3。若未改善，不追加小規則或替代模型搜尋。

## 本次等待的確認

是否核准上述**一個人物偵測模型的取得與接入、native人物框接點、單球321格一次執行**？
需要先確認，是因為使用者先前要求新模型benchmark先提方案，
且上一輪核准的1,684次上限已完整使用。本文件不把「繼續」解讀為可無限追加模型推論。
