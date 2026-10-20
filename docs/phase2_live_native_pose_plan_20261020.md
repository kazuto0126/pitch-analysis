# 可選 live RTMPose：最小接入方案

2026-10-20。**PROPOSED — 等待本版實作核准。**

## 目的與需要確認的範圍

讓專案能對本地新MP4產生獨立的RTMPose原生17點與overlay，提供另一份可追查的姿態輸出。
這是可運行的替代後端交付，不重開已停止的肘腕分類器、response警示或crop大小搜尋。

先前核准的20261017方案只讀封存592格；當前`NativePoseSource`及schema仍明示
`cached_read_only`。本版需要增加新影片推論能力，所以先提出具體方案。
正式MediaPipe `analyze-pitch`、33點介面、selector、門檻與品質gate保持。

## 固定輸入與執行上限

- 僅新大谷批次 `20261020T073530Z_6gyr6IC2e0Q` 的五球，335／321／369／338／321格，共**1,684格**。
  來源SHA與35項HSU輸入覆核見`config/pilots/ohtani_supplement_regions_20261020.json`。
- 沿用HSU已確認的青框原圖`[192,216,768,720)`，每格先取得該固定原片區域，
  再使用RTMPose原生預處理／affine到192×256模型輸入；記錄合成正逆變換，不以GT或模型分數選框。
  只向此模型提供該操作範圍的像素；padding不擴取框外其他人物像素。
- 沿用本機既有RTMPose-m ONNX與已相容的隔離runtime，不下載新權重、不升級環境：
  `analysis_results/phase2_rtmpose_response_20261016_01/model/end2end.onnx`，
  SHA `5c0a4bf67953e6d2ac43ce15e77dc9d5d354ae18430a47d2c5963a7bc5683e3c`。
- 真實新推論最多**1,684次**，每球每格一次；不重跑MediaPipe推論，直接讀上輪結果作並列參照。
  真實推論不作自動重試；失敗保留frame、原因與已產生資料。相容性用既有seal與無模型單元測試核對。
- 不新增標註；不重新對山本五球推論或校準。舊003人工XY與既有RTMPose改善／髖部退步只引用歷史結果。

固定青框包含動作空間及部分旁人，不能保證模型一定分離人物；這個限制在本版結果中如實回報。

## 實作位置與必要改動

| 位置 | 本版內容 |
| --- | --- |
| 新`src/pitch_analysis/native_pose_estimator.py` | 原生estimator protocol與COCO17 adapter；保留MediaPipe33介面 |
| 新隔離worker／`scripts/run_native_pose_live.py` | 讀本地已覆核MP4與固定設定，呼叫既有ONNX runtime；逐格保存來源、幾何與原生輸出 |
| `native-keypoints-v1.json` manifest | `inference_mode`增加明示的live模式；舊cached mode與舊封存資料仍完全相容 |
| `native_pose.py` | 只補live manifest來源／能力驗證；不放寬座標、topology或缺值語義 |
| `native_pose_io.py`／`native_pose_review.py` | 優先直接沿用；必要時只增加新來源保存／播放相容接點，保留原cached行為 |
| 新必要測試與文件 | 時間、17點、座標正逆轉換、隔離runtime、失敗保存、原流程相容 |

不修改`analysis/pitch.py`、`workflow.py`、`pose_capture.py`、`subject.py`、
`clean_pose.py`、`features.py`或原quality gate；不加`analyze-pitch --backend`正式替換入口。
舊凍結response worker及其評估程式也不修改。新worker可抽取已驗證的數學／預處理，
但必須保留原版本及其結果，不能以修改舊實驗的方式取得新結論。

## 輸出語義

- 原生COCO17，不補成33點；無Z／visibility／presence皆null。
- 保存原生score，沿用原SimCC定義；不把score當成MediaPipe visibility或校準機率。
- 每格原圖pixel XY、來源MP4與decoded BGR SHA、frame index、時間、ROI與正逆affine均可追查。
  第0格0秒，時間取`frame_index / (60000/1001)`，不加container offset。
- `model_observed`只表示模型直接輸出；缺值保持missing，不增加插值，不宣稱遮擋關節被恢復。
- `quality_status=not_calibrated`、`usable_for_analysis=null`保持；不把「有17點」當成可靠或通過原gate。
- 新輸出目錄例如`analysis_results/phase2_ohtani_live_native_20261020_01/`，
  保存五份native JSONL／manifest、五支新overlay、既有MediaPipe結果連結、逐球描述性比較與執行receipt。
  所有素材仍candidate，正式五球／原raw／人工GT不變，交付資料夾唯讀。

## 一次完成與停止規則

1. 先完成可選live入口及必要測試，再對固定五球各執行一次；不切換模型、ROI或參數尋找較好結果。
2. 核對1,684格完整時間軸、原生17點／missing原因與座標來源；實際檢查五支overlay。
3. 報告所有原生缺值、六重要關節score／位置跳動、與MediaPipe位置分歧，
   並列p02第159／245格、p05第251格及原最長缺口。
   位置分歧不當成準確率，不由其他模型分數判定真人可見，不新增任意總分／排名。
4. 五球沒有逐格關節GT，新RTMPose正確率與自動可靠性仍須列「未量測」；
   不移用只針對MediaPipe的canonical可靠／不可靠標籤來計算RTMPose TP／FN／FP。
5. 跑一次完整test suite，確認原MediaPipe與cached介面相容；更新status、獨立commit／push並交付。
6. 完成本版後停止；不追加調參、分類器、score校準、兩模型逐格混點、更多投手或Phase3。

本版驗收是「新影片原生後端能正確運行與保存」。模型在003的已知髖部退步、
Ohtani沒有逐格GT與原品質限制保留。**完成接入不會自動把Phase2改為PASSED。**
正式模型採用與可靠性驗收維持原標準，不降低既有門檻，也不新增零錯誤條件。
