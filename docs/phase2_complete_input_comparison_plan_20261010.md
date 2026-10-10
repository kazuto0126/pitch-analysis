# Phase 2：保留完整輸入的獨立比較提案

2026-10-10（台灣）。**提案，尚未核准或執行新模型。Phase 2 = NOT PASSED。**

## 已完成的證據與待回答問題

[五球損失診斷](phase2_roi_loss_diagnosis_20261010.md)已定位28格新增選取損失與重要關節退步。
002即使174格皆selected，右肘仍少15格可用，且原IMAGE肘點都在裁切框內。
舊003也有10／18原major錯位的raw四肩髖仍落在CSRT框內；主體框正確不保證框內關節正確。
單純框包含、同模型模式切換或固定窄框裁切，現有證據都不足以修復自動可靠性。

待回答：另一個保留全圖、產生不同關節假設的模型，是否提供可核對的關節分歧證據，
並減少已知錯位而不犧牲其他片完整動作？此問題尚無實測答案，不保證新模型更準。

## 提議的單一比較模型

**Google MoveNet MultiPose Lightning，TensorFlow 2版本1**。
使用[官方固定版本頁](https://www.kaggle.com/models/google/movenet/tensorFlow2/multipose-lightning/1?tfhub-redirect=true)，
核准後先保存下載來源、授權、實際檔案大小與逐檔SHA；版本或授權無法確認就停止，不自動換模型。

[官方model card](https://storage.googleapis.com/movenet/MoveNet.MultiPose%20Model%20Card.pdf)描述：
輸入RGB、H/W為32倍數；輸出float32 `[1,6,56]`，每槽17個(y,x,score)關節及box／instance score。
左右肩、肘、腕、髖、膝、踝都有原生點，不需要外部窄框裁切。六槽不是六個已確認的人，也不是identity ID。
官方用途偏向近距離webcam／健身，會預測遮擋關節；轉播投球的小尺度、模糊與自遮擋仍是未驗證風險。
原生score不等於visibility、presence或解剖正確，遮擋預測不能改叫observed。

## 第一關：只做隔離相容性檢查（本次待核准範圍）

1. 將官方版本1模型保存在本專案隔離實驗目錄，保存授權與所有檔案hash；不改正式模型。
2. 使用獨立CPU環境，提議`tensorflow-cpu==2.21.0`，不安裝到`.venv-analysis`。
   [官方套件metadata](https://pypi.org/pypi/tensorflow-cpu/2.21.0/json)有CPython3.12／WindowsAMD64 wheel，
   單wheel **350,945,555 bytes（約351MB）**，另有相依套件；不把這當成整套下載或磁碟需求。
   本機Python3.12.14／AMD64符合wheel標籤，但不等於載入成功；完整相依版本／檔案hash須另封存。
3. 用[本地SavedModel載入API](https://www.tensorflow.org/api_docs/python/tf/saved_model/load)檢查實際signature、
   dtype、輸出shape與原生關節順序。核對固定版本的`serving_default`／`output_0`及int32輸入；不符就記錄並停止。
4. 固定全圖RGB、`resize_with_pad(...,256,256)`、batch1、int32；使用預設bilinear／antialias=false。
   [官方resize文件](https://www.tensorflow.org/api_docs/python/tf/image/resize_with_pad)說明等比例縮放與零填充。
   保存實際縮放尺寸、左右／上下padding與反映射；邊界／角落合成fixture先驗證座標還原。
   保留整個視野但會縮小細節，不能稱為原像素或輸入資訊完全不變。
5. **最多1次合成圖smoke inference，正式影片推論0次**。保存原始輸出、耗時、runtime與錯誤。
   不同dtype／shape、缺signature、非有限輸出或不支援operator即停止，不自動換版本或增加試跑。
6. 回報相容性與實際資源需求後停止；不因相容性通過就宣稱可靠，也不自動接著跑592格。

本輪只讀本機套件／SDK source與官方文件；下載、安裝、新模型推論皆0。
本機MediaPipe測試source明示PoseLandmarker不支援region-of-interest；這是SDK文件／測試檢查，
沒有把它當成已執行ROI影片實測。OpenCV有DNN loader也不證明此SavedModel可直接使用。

## 第二關：相容性確認後另行封存的五球比較（尚未開始）

- 固定同五片592格，每片frame0排除成效，分母587；不增加投手、片段、resize網格或padding搜尋。
- 只量測一次完整原圖；保存六個原生槽、raw score／box、frame index、原PTS、輸入hash及映射。
  CSRT沿用既有封存框，僅當主體association背景；所有競爭與歧義保留，不用GT選人。
- 原生17點使用獨立contract；共享解剖點可離線對照，但不捏造缺少的16個MediaPipe點、Z、visibility或presence，
  不直接塞進正式33點輸出或變更`PoseEstimator`／capture／workflow核心。
- 同時保存框內肢體分歧，不能僅因hip／box在CSRT框內就認定關節正確。
  兩模型score不互轉；一致與分歧先作描述，不設定任意新警示門檻、總分或自動挑贏家。
- producer不讀GT；輸出封存後，003僅用可見人工XY離線比較。其餘四片精確誤差仍null，
  既有定性標籤只描述原prediction，不自動變成新模型的accuracy標籤。
- 分開回報可用／缺值、原始逐關節score、配對座標誤差／不一致、歧義與全片退步；不得只報003改善。
- 任何自動修復／警示policy與新TP／FN／FP評估都需後續獨立方案；本提案不宣稱解決原FN18。

## 決策與邊界

先依使用者原先「新模型benchmark先提出方案」的指示，等待第一關核准。
核准只涵蓋隔離下載／環境／契約與合成圖檢查，不授權切換production backend或直接跑影片比較。
MediaPipe維持baseline；正式五球、raw、GT、threshold、selector、tracking、平滑／插值皆保持原樣。
八顆交付素材保持候選；不開始Phase3、不重做5/5GT，也不把遮擋座標當精確可見真值。
