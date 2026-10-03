# 同學手動骨架標註：從這裡開始

請使用 [CVAT Online](https://app.cvat.ai/) 在原始圖片上親自放置、拖曳及修正關節點。這份工作會產生**可見關節的人工 X/Y 座標**，之後可量化 AI 骨架偏差。請先依原片獨立標註；包內的骨架定義只是 12 點模板，不含 AI 預測或其他人的答案。

## 這次要做的內容

| 影片 | 任務 |
|---|---|
| `pitch_003` | 全部 115 格，影格 **0–114**；每格逐一檢查左右肩、肘、腕、髖、膝、踝共 12 點，記錄座標及人工狀態；另填動作事件 |
| `pitch_005` | 只補充動作事件，尤其準備開始、最高抬腿與大致出手；查看全部 101 格，影格 **0–100** |

## 1. 解壓縮並確認檔案

把收到的 `manual_pose_package_20261004_01.zip` 完整解壓縮，保留資料夾位置。先開啟最外層 `START_HERE.html`，再看 `pitch_003.mp4` 的完整動作。

| 檔案 | 用途 |
|---|---|
| `pitch_003.mp4` | 原始影片，用來看動作及前後脈絡 |
| `raw_frames_pitch_003.zip` | **只把這個圖片 ZIP 上傳到 CVAT**，內含 115 張未畫骨架的原始 PNG |
| `raw_frames/` | 同一批原始 PNG，可在自己的電腦逐張開啟 |
| `cvat_labels.json` | 在 CVAT 的 **Raw** 標籤頁貼上的完整骨架設定 |
| `frame_manifest.json` | 圖片檔名、原始影格、尺寸及來源的對照；交回時保留這份檔案 |
| `pitch_003/REVIEW_NOTES.md`、`pitch_003/ground_truth.json` | `pitch_003` 事件的文字回覆表／空白 JSON 表 |
| `pitch_005/` | 事件補充的原片、逐格入口、文字回覆表及空白 JSON 表 |

`pitch_003` 原始大小是 **510 × 628 pixels**，圖片 `pitch_003_frame_0000.png` 對應影格 0，最後一張 `pitch_003_frame_0114.png` 對應影格 114。以檔名及 manifest 為準，避免把播放器秒數當作影格。

請保留原始圖片：不裁切、不縮放、不鏡像、不改檔名。CVAT 裡放大畫面方便看點可以；上傳前修改圖片會改變座標基準。`pitch_005/frames/` 的左右對照圖、縮圖及 overlay 只作事件檢查，**不能上傳為座標標註圖片**。

## 2. 在 CVAT 建立空白圖片任務

1. 開啟 [CVAT Online](https://app.cvat.ai/)，登入自己的帳號。
2. 到 **Tasks → ＋ → Create new task**。Name 可填 `pitch_003_manual_你的代號`，Project 留空。
3. 在 Labels 的 **Raw** 頁籤，貼上 `cvat_labels.json` 的**全部文字**，按 **Done**。設定應包含 `PITCHER_2D` 及 12 個關節子標籤。
4. 在 **Select files → My computer** 選取 `raw_frames_pitch_003.zip`。這是圖片任務，請使用提供的 PNG，不另上傳影片讓 CVAT 重新取格。
5. 在 Advanced configuration 中，Sorting method 選 **Lexicographical**（檔名已補零）；Image quality 可設 **100**。不要設定影格抽樣、跳格或翻轉。
6. 按 **Submit & Open**。在任務的 **Jobs** 區點入 job，確認第一／最後檔名及全部 115 格。如果分成數個 job，每個都要完成。

介面路徑依 [CVAT 官方任務建立說明](https://docs.cvat.ai/docs/workspace/tasks-page/#how-to-create-and-configure-an-annotation-task) 整理。這次使用提供的 Raw 設定，不使用 **From model**、**Automatic Annotation** 或 **AI Tools**。

## 3. 每一格親自建立並修正骨架

1. 在影格 0，選 **Draw new skeleton**，Label 選 `PITCHER_2D`，模式一定選 **Shape**。
2. 在投手身上畫出骨架模板，再逐一拖曳可見的關節點到正確位置。先辨認投手，再修正單點；骨架框的位置本身不算完成標註。
3. 在右側 **Objects** 展開該 skeleton 的關節清單，逐點確認英文標籤、位置及下面的 `human_state`。每格只保留投手的一副骨架。
4. 點的位置確認後才將 `human_state` 改為 `visible`，並確認該點的 **Occluded／Outside 都未勾選**。看過但無法定位的點依下一節填 `uncertain` 或 `not_observable`，並填 `review_note`。
5. 12 點都處理完後按 **Save**。切到下一格，再建立 Shape 並逐點檢查；每隔數格儲存一次，中途離開前再儲存。
6. 依序完成到影格 114，最後回看有重疊、模糊、出手附近及左右容易混淆的格。

**Shape** 是這次逐格標註的模式。請不要用 **Track**，也不要讓追蹤、複製後未檢查的點或自動內插代替人工判斷。操作方式可參考 [CVAT 官方骨架說明](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/skeletons/#annotation-with-skeletons)。

**先做小批次確認：** 先完成影格 0–4，依第 7 節匯出一次交回，讓維護者確認點名稱、座標及 `human_state` 都有正確匯出，再繼續其餘影格。這次部分回覆會保存為 `in_progress`，不當作全片完成。這可避免標完全部才發現設定或回傳格式不符。

建立骨架時，CVAT 可能先把整個 12 點模板放在圖片上，包括不可見的點。這些只是**操作上的暫放位置**，不表示你知道真實位置。預設 `unreviewed` 不會進入誤差評估；不可見點要明確改狀態並註明原因，匯入後會丟棄它的 X/Y。不要為了讓骨架好看，把遮住的點猜出來或設成 `visible`。

## 4. 左右與關節中心怎麼放

**LEFT／RIGHT 是投手自己的左右，與畫面左右不同。** 這支是右投手；右腕是投球手腕，左腕是手套側手腕。轉身後也不交換標籤。每次拖點時對照右側標籤名稱，不只靠點或線的顏色。

| 關節標籤 | 放點依據 |
|---|---|
| `LEFT_SHOULDER`、`RIGHT_SHOULDER` | 肩與上臂連接的關節中心；不要放在袖口或衣服最外緣 |
| `LEFT_ELBOW`、`RIGHT_ELBOW` | 上臂與前臂的肘關節中心；不要放在衣服鼓起的邊界 |
| `LEFT_WRIST`、`RIGHT_WRIST` | 前臂與手掌連接的腕關節中心；不是指尖、球的位置或手套尖端 |
| `LEFT_HIP`、`RIGHT_HIP` | 骨盆與大腿連接的髖關節中心；不要直接以褲子的外緣當作關節 |
| `LEFT_KNEE`、`RIGHT_KNEE` | 大腿與小腿連接的膝關節中心；依影像可辨認的轉折與位置判斷 |
| `LEFT_ANKLE`、`RIGHT_ANKLE` | 小腿與腳連接的踝關節中心；不是鞋尖、鞋底或地面接觸點 |

可用前後格協助辨認部位，但本格座標必須有本格影像證據。衣物下若仍能合理定位關節中心可以標；位置無法辨認就保留不確定。不要把旁人的手腳、裁判或打者標到投手身上。這次不需標臉、手指或其他 21 個 MediaPipe 點。

## 5. 遮擋與不確定怎麼處理

每一格的每一點都要有 `human_state`。狀態是「你能否從影像定位關節」，不是「AI 有沒有畫出點」。

| `human_state` | 何時用 | X/Y 會怎麼處理 |
|---|---|---|
| `visible` | 本格有足夠證據，你已親自確認及修正關節中心 | 保留，才能用於 AI 位置誤差 |
| `uncertain` | 已檢查，但模糊、部分遮擋或重疊使位置無法可信地定位 | 丟棄，不計位置誤差；寫原因 |
| `not_observable` | 完全遮住、在畫面外，或完全沒有位置證據 | 丟棄，不猜座標；寫原因 |
| `unreviewed` | 尚未逐點檢查，或該格未做標註 | 丟棄，表示未完成；不能當成遮擋 |

例如右腕藏在手套裡且看不到腕中心，就標 `not_observable`，`review_note` 寫「右腕被手套完全遮住」。只看到模糊邊界而無法放點則標 `uncertain`，寫「動態模糊，腕中心無法確認」。**不要做透視式補點，也不要用 AI 的位置當作人工真值。**

CVAT 的原生開關也要正確使用：

- **Occluded**：關節在畫面內，被身體或其他物體遮擋而無法可信定位時可以標示；另填 `uncertain` 或 `not_observable` 及原因。只勾 Occluded 不足以表示本次人工判斷。`visible` 點須取消勾選 Occluded。
- **Outside**：只在關節確實在畫面外時使用；同時設 `not_observable`，註明「畫面外」。畫面內被擋住不使用 Outside。
- **Hidden**：只讓你暫時看不到畫面上的點，屬於介面顯示功能，不能當作已儲存的人工狀態。

以上開關的含義見 [CVAT 官方骨架屬性說明](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/skeletons/#editing-skeletons-on-the-sidebar)。未標的影格會保留未覆核，不能因沒有點就當作全部不可見。

完成全部 **115 × 12 = 1,380 個人工狀態判斷**才可表示 `pitch_003` 座標標註完成。確實檢查後的 `uncertain`／`not_observable` 是有效結果；不必強迫每格都有 12 個可信座標。

## 6. 另填動作事件

`pitch_003` 填 `pitch_003/REVIEW_NOTES.md`，`pitch_005` 填 `pitch_005/REVIEW_NOTES.md`。你也可填各自空白 `ground_truth.json` 的事件欄位，沿用 `ground-truth-v1`；未檢查的其他欄位保留 `null`。

兩支都先看完整原片，再逐格看事件附近，尤其下列三項：

| 事件 | 判斷規則 |
|---|---|
| 準備開始 `preparation_start`（onset） | 本次投球動作開始的可見時點；片頭已在動作中就說明起點在片外或無法判斷，不強迫填 0 |
| 最高抬腿 `leg_lift`（peak） | 左腿抬到最高的位置；維持數格可填範圍，不是第一次腳離地 |
| 大致出手 `approximate_release`（release） | 優先找球最後仍在手中／首次已在空中的影格；看不清球就保留範圍、不確定或不可觀測 |
| 前腳落地 `foot_plant` | 左腳首次可見接觸地面附近；不從骨架猜受力時間 |
| 收尾結束 `follow_through_end` | 投球後回復穩定／平衡附近；片尾截斷就說明無法觀測 |

每項填**確定單格或範圍**（`annotated`），或 `uncertain`／`not_observable`，都加上理由。尚未看的事件保持空白並註明未完成。範圍兩端都包含，確定單格與範圍只選一種；不確定的候選範圍不能寫成確定答案。人工 `confidence` 可為 `null`。

文字表若仍有舊的「六關節可靠性／主體追蹤」區塊，這次沒有做的項目請註明未覆核。只交事件的 `ground_truth.json` 保持 `annotation_status: in_progress`、`reviewed_at_utc: null`；事件有回覆不代表整份 `phase2_full_review` 已完成。CVAT 座標的完成狀態由維護者另外記錄。

## 7. 儲存、匯出與交回

1. 在每個 job 按 **Save**，確認最後的修改已儲存。
2. 回任務頁，選 **Actions → Export task dataset**。
3. Format 選 **CVAT for images 1.1**，**Save images 關閉**，輸出檔名可填 `pitch_003_manual_你的代號.zip`，按 **OK** 並下載。不要改用影片、COCO 或 YOLO 格式。
4. ZIP 裡應有 `annotations.xml`。可交整個 ZIP，或只交裡面的 `annotations.xml`；不要只交截圖或畫好骨架的 PNG。

步驟見 [CVAT 官方匯出說明](https://docs.cvat.ai/docs/dataset_management/export-datasets/#exporting-dataset-from-a-task)；[CVAT image 格式](https://docs.cvat.ai/docs/dataset_management/formats/format-cvat/) 可保留 skeleton 及屬性。

請一起交回：

- CVAT 匯出的 ZIP／`annotations.xml`。
- `pitch_003` 與 `pitch_005` 填好的事件 `REVIEW_NOTES.md`，或空白表填好後的 `ground_truth.json`。
- 原封不動的 `frame_manifest.json`。
- 你的名稱／代號、資料包名稱、實際標註日期與時間及時區（例如 `Asia/Taipei`），以及完成範圍、未完成影格或待討論的點。記錄實際時間，不直接沿用範例日期。

把檔案交給提供資料的同學即可。維護者會確認來源及影格、保留你的獨立版本，再計算可見關節的 AI 誤差。這些人工資料可支持之後改善方法或另做模型訓練；**匯入不會讓 MediaPipe 自動學習，也不會自動開始微調**。
