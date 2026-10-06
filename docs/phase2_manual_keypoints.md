# Phase 2 人工 2D 關節座標

更新：2026-10-06。本次以 `pitch_003` 建立獨立人工 X/Y 基準，量化既有 AI 骨架位置誤差。讓同學在原片上親自畫出及修正骨架，並逐格記錄是否有足夠影像證據；這比「骨架可靠／不可靠」區間多出可直接比較的座標。

既有 HSU ground truth、`ground-truth-v1` 事件及原始 prediction 各自保留來源。人工座標存成獨立 sidecar，不取代 canonical ground truth。此工作屬 Phase 2 人工資料與評估工具，尚未進入 Phase 3。

## 本次範圍與工具

| 影片 | 指定任務 |
|---|---|
| `pitch_003` | 原始 510 × 628 pixels，全部 115 格（0–114）；左右肩、肘、腕、髖、膝、踝 12 點的人工狀態及可見座標；另填五個事件 |
| `pitch_005` | 查看全部 101 格（0–100），補充五個事件，重點是 onset／peak／release |

建議工具為 [CVAT Online](https://app.cvat.ai/)。官方提供 [圖片任務與 Raw 標籤設定](https://docs.cvat.ai/docs/workspace/tasks-page/)、[骨架逐點編輯及屬性](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/skeletons/) 和 [CVAT image 匯出](https://docs.cvat.ai/docs/dataset_management/formats/format-cvat/)。同學只需帳號、瀏覽器及資料包；實際操作見 [同學標註說明](../review_tools/manual_pose/START_HERE.md)。

資料包：

```text
analysis_results/phase2_yamamoto_20260925_01/manual_pose_package_20261004_01.zip
```

包內包含原始 `pitch_003.mp4`、全部未標註 PNG 的 `raw_frames_pitch_003.zip`／`raw_frames/`、`frame_manifest.json`、`cvat_labels.json`、`pitch_003` 事件空白表，以及 `pitch_005` 事件補充素材。媒體 ZIP 由使用者另行分享，不需同學使用 Git。

資料包已產生，約 80.4 MiB；原圖與來源、模板空白、包內連結及 ZIP 完整性檢查通過。
這裡尚未建立登入後的 CVAT 任務，請同學先交回第 0–4 格的部分匯出檢查，再完成其餘影格。

使用者已授權將資料包放到公開的 GitHub Release，供同學直接下載：

- [下載完整人工骨架標註 ZIP](https://github.com/kazuto0126/pitch-analysis/releases/download/phase2-manual-pose-review-20261004-01/manual_pose_package_20261004_01.zip)
- [Release 頁面與操作摘要](https://github.com/kazuto0126/pitch-analysis/releases/tag/phase2-manual-pose-review-20261004-01)

請選 Assets 中的 `manual_pose_package_20261004_01.zip`；GitHub 自動提供的 Source code ZIP 不含媒體。
資料包 SHA-256：`3b568e9065e0ec712c17bbd4d9ad741d39b1e1c7d5174d874ce6e2de7ffbe80e`。

## 標註基準

同學上傳原始 PNG ZIP，在 Labels → Raw 貼上 `cvat_labels.json`。每格使用一個 `PITCHER_2D` skeleton，選 **Shape**，逐一拖曳關節點及設定各點的 `human_state`、`review_note`。以空白原片開始，不匯入 AI 預測、不用自動標註、Track 或自動內插，讓人工基準保持獨立。

座標基準是原始圖片：左上角為原點，X 向右、Y 向下，單位 pixels。上傳圖片不得裁切、縮放、鏡像或拼接；既有左右對照圖、contact sheet、overlay 不可作為 CVAT 標註圖。CVAT 畫面放大只是檢視。

12 點與 [MediaPipe 官方 PoseLandmark 定義](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmark) 對應如下。LEFT／RIGHT 是**投手自身的解剖側別**，不是畫面側別；右投手的投球側是 RIGHT，前腳側是 LEFT。

| 標籤 | MediaPipe index |
|---|---|
| `LEFT_SHOULDER` / `RIGHT_SHOULDER` | 11 / 12 |
| `LEFT_ELBOW` / `RIGHT_ELBOW` | 13 / 14 |
| `LEFT_WRIST` / `RIGHT_WRIST` | 15 / 16 |
| `LEFT_HIP` / `RIGHT_HIP` | 23 / 24 |
| `LEFT_KNEE` / `RIGHT_KNEE` | 25 / 26 |
| `LEFT_ANKLE` / `RIGHT_ANKLE` | 27 / 28 |

人工點放在關節中心，不能放在衣服外緣、指尖、鞋尖、手套尖或旁人身上。每格都先確認主體及側別，再檢查點的位置。第一版以這 12 個身體關節建立基準，不要求臉部、手指或 3D 座標。

## 可見性、遮擋與未完成

| 每點 `human_state` | 人工含義 | 匯入後 X/Y |
|---|---|---|
| `visible` | 本格有足夠影像證據，已手動確認關節中心 | 保留，可計位置誤差 |
| `uncertain` | 已檢查，但模糊、部分遮擋或重疊使位置無法可信定位 | `null`；不評估位置 |
| `not_observable` | 完全遮擋、畫面外或沒有位置證據 | `null`；不評估位置 |
| `unreviewed` | 尚未檢查；也包含缺少 skeleton／關節標註 | `null`；不當作已檢查的遮擋 |

每格 12 點都需要明確人工判斷。全片完成是 1,380 個點狀態都已檢查，不表示強迫提供 1,380 組座標。不可觀測及不確定是有效結果，必須保留原因；尚未標的點仍是未覆核。

CVAT 初始化 skeleton 可能先放出全部 12 點。不可見點的暫放座標只是工具操作需求，明確設成非 `visible` 後，轉換器丟棄它的 X/Y。不能把暫放、複製、AI 或內插位置當作人工真值；不對完全遮住的部位作透視式補點。

CVAT 原生 `occluded` 只表示遮擋，單靠它不能區分本專案的 `uncertain`、`not_observable` 與 `unreviewed`；仍須填 `human_state` 及 `review_note`。`visible` 點的 `occluded` 與 `outside` 必須都是關閉。`outside` 只用於畫面外；`hidden` 是顯示用途，不是可保存的真值狀態。參見 [官方骨架屬性說明](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/skeletons/#editing-skeletons-on-the-sidebar)。

## 事件判斷與回收

事件仍沿用 `ground-truth-v1`。兩支影片各填自己的空白 `REVIEW_NOTES.md` 或 `ground_truth.json`：

- `preparation_start`（onset）：動作開始的可見時點；片頭已在動作中不強迫填 0。
- `leg_lift`（peak）：**最高抬腿**，不是首次腳離地。
- `approximate_release`（release）：球最後仍在手中／首次在空中的影格；球不清楚時保留範圍或不可判斷。
- `foot_plant`：左腳首次可見接觸地面附近。
- `follow_through_end`：投球後回復穩定／平衡附近；片尾截斷保留不可觀測。

每項回覆確定單格／包含兩端的範圍（`annotated`），或 `uncertain`、`not_observable`，加上原因；尚未檢查保持未覆核。座標標註不會自動填出事件，事件也不以 AI 手腕推定為確定值。

同學完成後，儲存每個 job，再到 Task → Actions → **Export task dataset**，選 **CVAT for images 1.1**、Save images 關閉，交回 ZIP 或其中的 `annotations.xml`。官方路徑見 [匯出說明](https://docs.cvat.ai/docs/dataset_management/export-datasets/#exporting-dataset-from-a-task)。另收兩支事件回覆、原始 manifest、reviewer 真實名稱／代號、實際標註時間及時區、資料包來源、已完成與未完成範圍。

只填事件的 `ground-truth-v1` 仍是 `in_progress`；未檢查的主體追蹤與可靠性欄位保持 `null`，不宣稱 `phase2_full_review` 已完成。人工座標 sidecar 的 `reviewed` 與既有 ground truth 的完整覆核狀態分開驗證。事件回覆可依 [既有回覆匯入流程](phase2_peer_review.md#維護者操作) 另存，不覆寫 HSU 版本。

## 維護者產生資料包

在專案根目錄執行；同學不需跑這些命令。輸出目錄使用新名稱，避免覆寫已交出的包：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\export_manual_pose_package.py input\yoshinobu_yamamoto\phase1_final\pitch_003.mp4 analysis_results\phase2_yamamoto_20260925_01\predictions\yoshinobu_yamamoto\pitch_003\video_metadata.json analysis_results\phase2_yamamoto_20260925_01\manual_pose_package_20261004_01 --supplement-folder analysis_results\phase2_yamamoto_20260925_01\peer_review_package_20261003_01\pitch_005 --event-template-folder analysis_results\phase2_yamamoto_20260925_01\peer_review_package_20261003_01\pitch_003
```

## 維護者匯入人工座標

匯入格式為 `manual-keypoints-v1`。把 CVAT 回覆放入專案內的暫存資料夾。以下的 reviewer 與 UTC 時間請替換成**同學實際資料**，不要由程式生成或沿用範例。

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\import_manual_keypoints.py temp\returned_cvat.zip analysis_results\phase2_yamamoto_20260925_01\manual_pose_package_20261004_01\frame_manifest.json input\yoshinobu_yamamoto\phase1_final\pitch_003.mp4 --review-id CLASSMATE_20261004 --reviewer '<實際同學名稱或代號>' --reviewed-at-utc '<實際完成 UTC 時間，例如 YYYY-MM-DDTHH:MM:SSZ>' --status reviewed
```

只有全部影格與 12 點都已決定為 `visible`／`uncertain`／`not_observable`、且提供實際 reviewer／完成時間時，才能使用 `--status reviewed`。部分回覆使用 `--status in_progress`，省略 `--reviewed-at-utc`；缺少標註保持 `unreviewed`。修正版使用新的 review ID，保留原版。

匯入輸出位置：

```text
annotations/manual_keypoints/CLASSMATE_20261004/pitch_003/manual_keypoints.json
```

工具驗證 CVAT 格式、原始來源／SHA-256、manifest、圖片名稱與尺寸、影格範圍、關節、座標及人工狀態，保留 reviewer 與回覆來源。非 `visible` 座標轉為 `null`；來源或格式驗證通過不等於人工標註正確，分歧仍需人回看處理。

### 本次回傳與部分覆核（2026-10-04）

Tsai 回傳原檔有 115 格、1,380 個點，全部宣告 `visible`。重新提供的 ZIP/XML 與第一次檢查的校驗碼相同；已保存原始回傳，不修改它的座標或狀態。

HSU 逐段覆核後，另存部分參考：
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261004_01/pitch_003/manual_keypoints.json`。
其中 **14 個點確認可見且對位、63 個點確認不可觀測、1,303 個點保持未覆核**。可見點直接保留 Tsai 原始 X/Y，其餘座標為 `null`；標註者與覆核者分開記錄，狀態仍是 `in_progress`，未捏造完成時間或 confidence。

原 ZIP、XML 與未修正的 CVAT 宣告位於
`analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。
原 XML 也保存在部分參考旁；其中含帳號資訊，僅在本地留存並由 Git 忽略。正式影片、115 格原圖及時間軸已重新驗證，canonical HSU 標註與原模型輸出保持原樣。這次尚未執行座標誤差比較；部分參考不代表全片覆核完成。

後續 HSU 確認 33–44 格右肘、右腕均可清楚判讀且點位正確，再確認 45–63 格點位正確，共加入 62 個點。
HSU 接著確認 64–72 格點位，但單獨原圖澄清時表示 70–71 格右肘、右腕皆看不到。
因此只加入 64–69、72 格的 14 個可見點；70–71 的四個點記為不可觀測、X/Y 留空。
再覆核 73–82 格後，HSU 確認右腕 73–78 可見且正確、右肘 73–78 看不到，79–82 兩關節皆看不到。
當時部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261004_07/pitch_003/manual_keypoints.json`：
**96 個可見且對位、84 個不可觀測、1,200 個未覆核**，仍為 `in_progress`。
HSU 再確認右腕 84–86 被遮住、右肘 83–92 可見；前者加入三個不可觀測點，後者點位正確性仍待釐清，仍為未覆核且 X/Y 留空。
前六版保留原樣；已採用座標與保存的原 XML 相同，未複製舊 AI 對位判斷或推估隱藏座標。

2026-10-05，HSU 最後短答「沒有」已另存於
`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_01/pitch_003/ground_truth.json`。
尚不確定是表示沒有偏移，還是否定全部對位；不據此把右肘 83–92 十格判對或判錯。
下次放大對照圖及完整進度見 [人工覆核 checkpoint](phase2_manual_review_checkpoint_20261005.md)。

HSU 接著在同一個 83–92 右肘續看頁上下文明確回覆「位置正確」，解除這十格的點位待釐清。
83–92 澄清後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_01/pitch_003/manual_keypoints.json`：
**106 個可見且對位、84 個不可觀測、1,190 個未覆核**，仍為 `in_progress`。
十個新可見座標直接取自 Tsai 原 XML；前七版與先前補充皆保留，未改 confidence／完成時間。

HSU 再明確確認右肘 93–96「看的到且正確」，新增四個可見且對位的原始座標。
93–96 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_02/pitch_003/manual_keypoints.json`：
**110 個可見且對位、84 個不可觀測、1,186 個未覆核**，仍為 `in_progress`；下一段是右肘 97–100。

HSU 確認 97–100 右肘「都看不到被遮住了」，四點記為不可觀測、X/Y 留空，未推定遮擋來源。
97–100 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_03/pitch_003/manual_keypoints.json`：
**110 個可見且對位、88 個不可觀測、1,182 個未覆核**，仍為 `in_progress`；接續右肘 101–104。

HSU 確認 101–104 右肘「看不到」，四點不可觀測、X/Y 留空；未推定不可見原因。
101–104 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_04/pitch_003/manual_keypoints.json`：
**110 個可見且對位、92 個不可觀測、1,178 個未覆核**，仍為 `in_progress`；接續右肘 105–108。

105–108 右肘點位意見已回答「正確」，原圖關節中心可見性仍待直接確認。
最新補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_06/pitch_003/ground_truth.json`；
本次沒有採用新座標或推定不可見狀態，最新座標 checkpoint 及計數保持不變。

HSU 隨後以「可以」明確確認 105–108 原圖右肘可直接看見，與前次位置正確的回答合併，加入四個 Tsai 原始可見點位。
105–108 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_05/pitch_003/manual_keypoints.json`：
**114 個可見且對位、92 個不可觀測、1,174 個未覆核**，仍為 `in_progress`；接續右肘 109–112。

HSU 確認 109–112 右肘「看的見且正確」，新增四個 Tsai 原始可見點位。
109–112 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_06/pitch_003/manual_keypoints.json`：
**118 個可見且對位、92 個不可觀測、1,170 個未覆核**，仍為 `in_progress`；接續右肘 113–114。

HSU 以「正確可以」確認 113–114 右肘可見且對位，新增兩個 Tsai 原始座標。
113–114 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_07/pitch_003/manual_keypoints.json`：
**120 個可見且對位、92 個不可觀測、1,168 個未覆核**，仍為 `in_progress`。
右肘尚待覆核 0–21、24–32 共31點；其他已完成區段不重複標，先回到 0–3 補齊。

HSU 對 0–3 右肘是否直接可見且對位的合併問題回答「正確」，保存四個 Tsai 原始點位。
0–3 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_08/pitch_003/manual_keypoints.json`：
**124 個可見且對位、92 個不可觀測、1,164 個未覆核**，仍為 `in_progress`；接續右肘 4–7。

HSU 對 4–7 右肘是否直接可見且對位的合併問題回答「正確」，保存四個 Tsai 原始點位。
4–7 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_09/pitch_003/manual_keypoints.json`：
**128 個可見且對位、92 個不可觀測、1,160 個未覆核**，仍為 `in_progress`；接續右肘 8–11。

HSU 確認 8–11 並要求一次給更多格數，保存四個 Tsai 原始可見點位。
8–11 覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_10/pitch_003/manual_keypoints.json`：
**132 個可見且對位、92 個不可觀測、1,156 個未覆核**，仍為 `in_progress`。
下一批一次呈現剩餘右肘 12–21、24–32 共19格；增加批次量不代表未看區段已獲人工確認。

HSU 對最後19格右肘回答「全部都正確」；可見性另有同SHA既有人工紀錄，結合新點位判斷保存19個原始座標。
右肘全片完成後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_11/pitch_003/manual_keypoints.json`：
**151 個可見且對位、92 個不可觀測、1,137 個未覆核**，仍為 `in_progress`。
右肘全115格已覆核（93可見、22不可觀測）；其他關節未完成，下一批改看右腕0–15。

HSU 對右腕0–15回答「位置正確但是看不到」，16點記為不可觀測、X/Y留空。
推估位置意見保留在 notes，不當成可見座標真值；未推定不可見原因。
右腕0–15覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_12/pitch_003/manual_keypoints.json`：
**151 個可見且對位、108 個不可觀測、1,121 個未覆核**，仍為 `in_progress`。
右腕尚待16–21、24、30–32、105–114共20格，下一批一次呈現；右肘與舊紀錄不變。

HSU 對本批剩餘20格回答「16-21位置正確但看不到，其他都看的到且位置正確」。
16–21共6個右腕點不可觀測，X/Y留空；其餘24、30–32、105–114共14點可見且對位，採用Tsai原始X/Y。
「其他」只指本次呈現的右腕格數，不擴及其他關節。未推定不可見原因，推估位置意見保留於notes。
右腕全片完成後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_13/pitch_003/manual_keypoints.json`：
**165 個可見且對位、114 個不可觀測、1,101 個未覆核**，仍為 `in_progress`。
右腕全115格已覆核（58可見、57不可觀測）；右肘93可見／22不可觀測不變，接續左肘／左腕0–15。

HSU 對0–15格左手回答「看不到左腕但是位置正確，左肘位置正確」。
左腕16點不可觀測、X/Y留空；左肘先只保存位置正確的意見，可見性待澄清。
此中間版本為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_14/pitch_003/manual_keypoints.json`，
165可見、130不可觀測、1,085未覆核；不因點位看似正確而自行填入可見性。
HSU 再對同段左肘原圖可見性明確回答「全部看得見」，16點可見且對位，採用Tsai原始座標。
左肘0–15可見性澄清後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_15/pitch_003/manual_keypoints.json`：
**181 個可見且對位、130 個不可觀測、1,069 個未覆核**，仍為 `in_progress`。
左肘25可見／15不可觀測／75未覆核；左腕5可見／35不可觀測／75未覆核。接續16–32格兩關節，尚未收到該批人工判斷。

HSU 對16–32格兩關節回答「全部都被遮住但位置正確」，34點不可觀測、X/Y留空。
推估位置意見保留；遮擋已明確確認，但未指定遮擋來源，不當成可觀測座標真值。
左肘／左腕16–32覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_16/pitch_003/manual_keypoints.json`：
**181 個可見且對位、164 個不可觀測、1,035 個未覆核**，仍為 `in_progress`。
左肘25可見／32不可觀測／58未覆核；左腕5可見／52不可觀測／58未覆核。接續45、49–63兩關節共32點，略過已覆核33–44與46–48。

HSU 對45、49–63格左肘／左腕回答「皆可看到位置正確」，32點可見且對位，保留Tsai原始X/Y。
只轉錄本批兩關節，不擴及未看格數，也不宣稱像素誤差為零。
左肘／左腕45、49–63覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_17/pitch_003/manual_keypoints.json`：
**213 個可見且對位、164 個不可觀測、1,003 個未覆核**，仍為 `in_progress`。
左肘41可見／32不可觀測／42未覆核；左腕21可見／52不可觀測／42未覆核。0–72兩關節已完成；接續73–88共32點，尚未收到該批人工判斷。

HSU 對73–88格回答「85-86左腕看不清之外其他都正確」，再明確確認「其餘全部看得見」。
左肘73–88共16點及左腕73–84、87–88共14點可見且對位，採用Tsai原始X/Y。
85–86左腕2點看不清，保留既有schema的 `uncertain`、X/Y留空；不強迫當成完全不可見或精確答案，未推定原因。
左肘／左腕73–88覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_18/pitch_003/manual_keypoints.json`：
**243 個可見且對位、164 個不可觀測、2 個不確定、971 個未覆核**，仍為 `in_progress`。
左肘57可見／32不可觀測／26未覆核；左腕35可見／52不可觀測／2不確定／26未覆核。接續89–104共32點，尚未收到該批人工判斷。

HSU 在對話直接觀看89–104原圖／Tsai對照，先回答「皆清楚可見」，再確認「全部位置正確」。
本批兩關節32點可見且對位，採用Tsai原始X/Y；85–86左腕既有不確定狀態與空座標不變。
當時部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_19/pitch_003/manual_keypoints.json`：
**275 個可見且對位、164 個不可觀測、2 個不確定、939 個未覆核**，仍為 `in_progress`。
左肘73可見／32不可觀測／10未覆核；左腕51可見／52不可觀測／2不確定／10未覆核。接續最後105–114共20點，尚未收到該批人工判斷。

HSU 對105–114格左肘（青色3號）／左腕（青色5號）「是否都清楚可見且位置正確」的合併問題回答「正確」。
本批20點可見且對位，採用Tsai原始X/Y；85–86左腕仍為 `uncertain`、X/Y留空。
左肘／左腕全片覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_20/pitch_003/manual_keypoints.json`：
**295 個可見且對位、164 個不可觀測、2 個不確定、919 個未覆核**，仍為 `in_progress`。
該次HSU補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_22/pitch_003/ground_truth.json`。
左肘83可見／32不可觀測／0未覆核；左腕61可見／52不可觀測／2不確定／0未覆核。
右肘93可見／22不可觀測、右腕58可見／57不可觀測；四個肘腕關節全115格已逐點覆核，全12關節人工參考仍未完成。
下一批只看雙肩0–15格，共32個未覆核點：青色1號左肩、紅色2號右肩。
對照圖為 `analysis_results/shoulder_review_20261005_01/shoulders_0000_0007.png` 與 `analysis_results/shoulder_review_20261005_01/shoulders_0008_0015.png`。
本次只做annotation schema／來源hash檢查；147 passed／0 failed／1 skipped為先前完整suite紀錄，本批未重跑。


HSU觀看雙肩0–15原圖／Tsai對照，對「清楚可見且位置正確」明確回答「都正確清楚」。
雙肩0–15覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_21/pitch_003/manual_keypoints.json`：
**327 個可見且對位、164 個不可觀測、2 個不確定、887 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_23/pitch_003/ground_truth.json`；只追加notes。
左右肩各新增16個Tsai原始X/Y，16格以後未代判，左腕85–86不確定紀錄不變。
下一批只看雙肩16–31，青色1左肩／紅色2右肩；對照位於 `analysis_results/shoulder_review_20261005_02/`。
本次schema／來源hash驗證通過，未重跑模型或完整suite；沒有啟用子代理。

HSU再觀看直接貼於最終回覆的16–31雙肩對照，對清楚可見且位置正確的合併問題回答「正確」。
雙肩16–31覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_22/pitch_003/manual_keypoints.json`：
**359 個可見且對位、164 個不可觀測、2 個不確定、855 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_24/pitch_003/ground_truth.json`；僅追加人工原話／上下文。
左右肩各32可見／83未覆核，接續32–47，共32個未覆核點；對照位於 `analysis_results/shoulder_review_20261005_03/`。
新增32點採用Tsai原始X/Y，左腕85–86不確定紀錄、歷史及原模型輸出不變；schema／來源檢查通過，沒有啟用子代理。

HSU對32–47格雙肩清楚可見且位置正確的合併問題回答「都正確」，新增32個Tsai原始X/Y。
雙肩32–47覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_23/pitch_003/manual_keypoints.json`：
**391 個可見且對位、164 個不可觀測、2 個不確定、823 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_25/pitch_003/ground_truth.json`；只追加notes。
左右肩各48可見／67未覆核，接續48–63；對照位於 `analysis_results/shoulder_review_20261005_04/`。
schema／來源檢查通過，左腕85–86不確定、原來源／模型／歷史保留；沒有啟用子代理。

HSU對48–63格雙肩清楚可見且位置正確的合併問題回答「正確」，新增32個Tsai原始X/Y。
雙肩48–63覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_24/pitch_003/manual_keypoints.json`：
**423 個可見且對位、164 個不可觀測、2 個不確定、791 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_26/pitch_003/ground_truth.json`；只追加notes。
左右肩各64可見／51未覆核，接續64–79；對照位於 `analysis_results/shoulder_review_20261005_05/`。
schema／來源檢查通過，左腕85–86不確定與原來源／模型／歷史不變，沒有啟用子代理。

HSU在64–79批指出70–78被遮住，另明確澄清「對，是右肩」，其餘點「其他沒問題」。
RIGHT_SHOULDER70–78共9點不可觀測、X/Y留空，未提供遮擋來源或精確隱藏位置；其餘23點採用原Tsai X/Y。
雙肩64–79覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_25/pitch_003/manual_keypoints.json`：
**446 個可見且對位、173 個不可觀測、2 個不確定、759 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_27/pitch_003/ground_truth.json`；只追加原話／澄清上下文。
左肩80可見／35未覆核，右肩71可見／9不可觀測／35未覆核，接續80–95；對照位於 `analysis_results/shoulder_review_20261005_06/`。
schema／來源檢查通過，左腕85–86不確定與原來源／模型／歷史不變，沒有啟用子代理。

HSU對雙肩80–95清楚可見且位置正確的合併問題回答原話「都沒問替」，依上下文理解為「都沒問題」。
只新增本批32個原Tsai X/Y，未代判96格以後或其他關節。
雙肩80–95覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_26/pitch_003/manual_keypoints.json`：
**478 個可見且對位、173 個不可觀測、2 個不確定、727 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_28/pitch_003/ground_truth.json`；只追加原話與問題上下文。
左肩96可見／19未覆核，右肩87可見／9不可觀測／19未覆核；最後一批雙肩96–114共38點，對照位於 `analysis_results/shoulder_review_20261005_07/`。
schema／來源檢查通過；右肩70–78不可觀測、左腕85–86不確定與原來源／模型／歷史不變，沒有啟用子代理。

HSU對雙肩96–114清楚可見且位置正確的合併問題回答「正確」，新增38個原Tsai X/Y。
雙肩96–114覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_27/pitch_003/manual_keypoints.json`：
**516 個可見且對位、173 個不可觀測、2 個不確定、689 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_29/pitch_003/ground_truth.json`；只追加原話與問題上下文。
雙肩115格全片覆核完成：左肩115可見；右肩106可見／9不可觀測（70–78）。
肩、肘、腕六關節均已逐點覆核；髖、膝、踝尚待人工，左腕85–86不確定紀錄保留。
下一批雙髖0–15共32點全為未覆核；對照位於 `analysis_results/hip_review_20261005_01/`，青色7左髖、紅色8右髖。
schema／來源檢查通過，歷史、來源、模型與canonical GT保留；沒有啟用子代理、重跑分析或訓練。

HSU對雙髖0–15看得清楚且標點位置正確的合併問題回答「正確」，新增32個原Tsai X/Y。
雙髖0–15覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_28/pitch_003/manual_keypoints.json`：
**548 個可見且對位、173 個不可觀測、2 個不確定、657 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_30/pitch_003/ground_truth.json`；只追加原話與問題上下文。
左右髖各16可見／99未覆核；下一批雙髖16–31共32點全為未覆核，對照位於 `analysis_results/hip_review_20261005_02/`。
schema／來源檢查通過，來源、canonical GT、prediction、歷史与既有不確定／不可觀測狀態保留。
沒有啟用子代理、修改模型、重跑分析、比較或訓練。

HSU對雙髖16–31看得清楚且位置正確的合併問題回答「可以」，新增32個原Tsai X/Y。
雙髖16–31覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_29/pitch_003/manual_keypoints.json`：
**580 個可見且對位、173 個不可觀測、2 個不確定、625 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_31/pitch_003/ground_truth.json`；只追加原話與問題上下文。
左右髖各32可見／83未覆核；下一批雙髖32–47共32點全為未覆核，對照位於 `analysis_results/hip_review_20261005_03/`。
後續「繼續」只要求接續展示，不當成未看影格的人工標註。schema／來源檢查通過；歷史、模型輸出與canonical GT保留。

HSU對雙髖32–47看得清楚且位置正確的合併問題回答「正確」，新增32個原Tsai X/Y。
雙髖32–47覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_30/pitch_003/manual_keypoints.json`：
**612 個可見且對位、173 個不可觀測、2 個不確定、593 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_32/pitch_003/ground_truth.json`；只追加原話與問題上下文。
左右髖各48可見／67未覆核；下一批雙髖48–63共32點全為未覆核，對照位於 `analysis_results/hip_review_20261005_04/`。
schema／來源檢查通過；原Tsai座標、歷史、模型輸出與canonical GT保留，未修改分析邏輯。

HSU對雙髖48–63看得清楚且位置正確的合併問題回答「可以」，新增32個原Tsai X/Y。
雙髖48–63覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_31/pitch_003/manual_keypoints.json`：
**644 個可見且對位、173 個不可觀測、2 個不確定、561 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_33/pitch_003/ground_truth.json`；只追加原話與問題上下文。
左右髖各64可見／51未覆核；下一批雙髖64–79共32點全為未覆核，對照位於 `analysis_results/hip_review_20261005_05/`。
schema／來源檢查通過；原Tsai座標、歷史、模型輸出與canonical GT保留，未修改分析邏輯。

HSU對雙髖64–79看得清楚且位置正確的合併問題回答「都正確」，新增32個原Tsai X/Y。
雙髖64–79覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_32/pitch_003/manual_keypoints.json`：
**676 個可見且對位、173 個不可觀測、2 個不確定、529 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_34/pitch_003/ground_truth.json`；只追加原話與問題上下文。
左右髖各80可見／35未覆核；下一批雙髖80–95共32點全為未覆核，對照位於 `analysis_results/hip_review_20261005_06/`。
schema／來源檢查通過；原Tsai座標、歷史、模型輸出與canonical GT保留，未修改分析邏輯。

HSU對雙髖80–95看得清楚且位置正確的合併問題回答「正確」，新增32個原Tsai X/Y。
雙髖80–95覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_33/pitch_003/manual_keypoints.json`：
**708 個可見且對位、173 個不可觀測、2 個不確定、497 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_35/pitch_003/ground_truth.json`；只追加原話與問題上下文。
左右髖各96可見／19未覆核；最後一批雙髖96–114共38點全為未覆核，對照位於 `analysis_results/hip_review_20261005_07/`。
schema／來源檢查通過；原Tsai座標、歷史、模型輸出與canonical GT保留，未修改分析邏輯。

HSU對雙髖96–114清楚可見且位置正確的合併問題回答「都正確」，新增38個原Tsai X/Y。
雙髖96–114覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_34/pitch_003/manual_keypoints.json`：
**746 個可見且對位、173 個不可觀測、2 個不確定、459 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_36/pitch_003/ground_truth.json`；只追加原話與問題上下文。
雙髖全115格已逐點覆核，左右髖各115可見且對位；雙肩、雙肘、雙腕及雙髖全片已覆核。
依HSU要求，後續每批同時覆核左右膝踝，避免同一段影格分開重看。
下一批膝踝0–15共64點全為未覆核，對照位於 `analysis_results/leg_review_20261005_01/`。
青色9／11為左膝／左踝，紅色10／12為右膝／右踝；原雙膝助手保留，流程調整沒有新增人工判定。
schema／來源檢查通過；原Tsai座標、歷史、模型輸出與canonical GT保留，未修改分析邏輯。
全片12關節參考仍待膝踝覆核；人工 confidence／完整完成時間維持null，不宣稱像素誤差為零。

HSU對左右膝踝0–15四點清楚可見且位置正確的合併問題回答「正確」，新增64個原Tsai X/Y。
膝踝0–15覆核後的部分參考為 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_35/pitch_003/manual_keypoints.json`：
**810 個可見且對位、173 個不可觀測、2 個不確定、395 個未覆核**，仍為 `in_progress`。
該次補充為 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_37/pitch_003/ground_truth.json`；只追加原話與問題上下文。
雙膝、右踝各16可見／99未覆核；左踝16可見／1不可觀測／98未覆核，左踝65原不可觀測紀錄保留。
下一批左右膝踝16–31共64點全為未覆核，對照位於 `analysis_results/leg_review_20261005_02/`。
schema／來源檢查通過；原Tsai座標、歷史、模型輸出與canonical GT保留，未修改分析邏輯。
人工 confidence／完整完成時間維持null，不宣稱像素誤差為零。

HSU對左右膝踝16–31四點清楚可見且位置正確的合併問題回答「可以」，新增64個原Tsai X/Y。
膝踝16–31覆核後的部分參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_36/pitch_003/manual_keypoints.json`，
**874 可見且對位、173 不可觀測、2 不確定、331 未覆核**，仍為 `in_progress`。
該次補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_38/pitch_003/ground_truth.json`，只追加notes。
雙膝、右踝各32可見／83未覆核；左踝32可見／1不可觀測／82未覆核。
下一批左右膝踝32–47共64個未覆核點，對照位於 `analysis_results/leg_review_20261005_03/`。
schema／來源檢查通過；歷史、canonical GT、prediction與既有不可觀測／不確定點保留，confidence與完整完成時間仍null。

HSU對左右膝踝32–47四點清楚可見且位置正確的合併問題回答「正確」，新增64個原Tsai X/Y。
膝踝32–47覆核後的部分參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_37/pitch_003/manual_keypoints.json`，
**938 可見且對位、173 不可觀測、2 不確定、267 未覆核**，仍為 `in_progress`。
該次補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_39/pitch_003/ground_truth.json`，只追加notes。
雙膝、右踝各48可見／67未覆核；左踝48可見／1不可觀測／66未覆核。
下一批左右膝踝48–63共64個未覆核點，對照位於 `analysis_results/leg_review_20261005_04/`。
schema／來源檢查通過；歷史、canonical GT、prediction與既有不可觀測／不確定點保留，confidence與完整完成時間仍null。

HSU對左右膝踝48–63四點清楚可見且位置正確的合併問題回答「正確」，新增64個原Tsai X/Y。
膝踝48–63覆核後的部分參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_38/pitch_003/manual_keypoints.json`，
**1002 可見且對位、173 不可觀測、2 不確定、203 未覆核**，仍為 `in_progress`。
該次補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_40/pitch_003/ground_truth.json`，只追加notes。
雙膝、右踝各64可見／51未覆核；左踝64可見／1不可觀測／50未覆核。
下一批左右膝踝64–79對照位於 `analysis_results/leg_review_20261005_05/legs_0064_0071.png` 與 `analysis_results/leg_review_20261005_05/legs_0072_0079.png`。共顯示64點，其中63點未覆核；第65格左踝已記為不可觀測、X/Y留空，保留原判定，不再詢問。
schema／來源檢查通過；歷史、canonical GT、prediction與既有不可觀測／不確定點保留，confidence與完整完成時間仍null。

HSU對64–79格膝踝問題回答「都可以」。問題已排除第65格左踝，其餘63點確認清楚可見且對位，採用Tsai原始X/Y。第65格左踝保留不可觀測與null座標。
雙膝、右踝各80可見／35未覆核；左踝79可見／1不可觀測／35未覆核。
膝踝64–79覆核後的部分參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_39/pitch_003/manual_keypoints.json`，
**1065 可見且對位、173 不可觀測、2 不確定、140 未覆核**，仍為 `in_progress`。
該次補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_41/pitch_003/ground_truth.json`，只追加notes。
下一批左右膝踝80–95對照位於 `analysis_results/leg_review_20261005_06/legs_0080_0087.png` 與 `analysis_results/leg_review_20261005_06/legs_0088_0095.png`。四個點一起看，共64個未覆核點。
schema／來源檢查通過；歷史、canonical GT、prediction與既有不可觀測／不確定點保留，confidence與完整完成時間仍null。

HSU對80–95格四個膝踝點清楚可見且位置正確的合併問題回答「正確」，新增64個Tsai原始X/Y。
雙膝、右踝各96可見／19未覆核；左踝95可見／1不可觀測／19未覆核。
膝踝80–95覆核後的部分參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_40/pitch_003/manual_keypoints.json`，
**1129 可見且對位、173 不可觀測、2 不確定、76 未覆核**，仍為 `in_progress`。
該次補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_42/pitch_003/ground_truth.json`，只追加notes。
最後一批左右膝踝96–114對照位於 `analysis_results/leg_review_20261005_07/legs_0096_0105.png` 與 `analysis_results/leg_review_20261005_07/legs_0106_0114.png`。19格四個點一起看，共76個未覆核點；第65格左踝保留既有不可觀測判定。
schema／來源檢查通過；歷史、canonical GT、prediction及既有不可觀測／不確定點保留，confidence與完整完成時間仍null。

HSU對最後96–114格四個膝踝點清楚可見且位置正確的合併問題回答「都正確」，新增76個Tsai原始X/Y。
雙膝、右踝各115可見；左踝114可見／1不可觀測（第65格）。全115格12關節的1,380個點狀態均已逐點覆核，0未覆核。
第41版座標參考（當時逐點覆核完成、正式provenance待補）：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_41/pitch_003/manual_keypoints.json`，
**1205 可見且對位、173 不可觀測、2 不確定、0 未覆核**。
該次補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_43/pitch_003/ground_truth.json`，只追加notes。
逐點影像覆核已完成，包含不可觀測與不確定這些有效結果；85–86左腕保留不確定，不強迫補精確答案。正式完成時間未由人工提供，`reviewed_at_utc`及confidence仍為null，`annotation_status`暫留`in_progress`。下一步補齊完成provenance，再用現有評估器比較原始prediction與可見人工座標，排除175個非可見點並分開報告模型漏點；Phase 2仍IN PROGRESS。
schema／來源檢查通過；歷史、canonical GT、prediction及既有不可觀測／不確定點保留；本次未執行新模型推論、座標比較或訓練。

## 正式座標覆核與比較完成

HSU提供完成時間原話「2026/10/5 10.14」，記為台灣2026-10-05 10:14、UTC `2026-10-05T02:14:00Z`（分鐘精度，00秒為格式填位）。正式座標sidecar已另存為 `reviewed`，confidence保持null，舊版保留。已使用原始prediction完成1,205個可見點的位置誤差比較，排除175個不可觀測／不確定點。詳見 [座標比較報告](phase2_manual_coordinate_comparison_20261005.md)。Phase 2仍IN PROGRESS。

最新正式參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_42/pitch_003/manual_keypoints.json`。
最新時間紀錄補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_44/pitch_003/ground_truth.json`（僅notes更新，事件／其他provenance維持原樣）。

原片510 × 628；投球肘平均誤差27.50px、中位數10.55px、P95 106.19px。87–104格整體偏移平均76.90px；有raw座標及高visibility仍可能錯位。
原有人工非可見政策與評估器保留，同學被遮擋關節的原始推估座標保存在來源ZIP/XML；其價值與限制見比較報告，不把這些點混入可觀測位置誤差。

## 計算 AI 位置誤差

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\evaluate_manual_keypoints.py annotations\manual_keypoints\CLASSMATE_20261004\pitch_003\manual_keypoints.json analysis_results\phase2_yamamoto_20260925_01\predictions\yoshinobu_yamamoto\pitch_003\keypoints.json analysis_results\phase2_yamamoto_20260925_01\manual_keypoints_error_CLASSMATE_20261004.json
```

比較前確認 prediction 的同支來源與相鄰 `video_metadata.json`。模型的 normalized X/Y 轉為原圖 pixels，再以同影格、同解剖關節與人工 `visible` 座標做比較：

```text
pixel_error = sqrt((AI_x - human_x)^2 + (AI_y - human_y)^2)
```

誤差只統計**有人工可見座標且有有效模型座標**的點，逐關節報告。人工可見但 AI 漏點要另列數量與比率；保留人工可見點總數、有效比較數及各人工狀態的數量，避免把 AI 漏點排除後誤認成表現良好。AI confidence／visibility 不是人工可見性；人工非 `visible` 點不以暫放值計算誤差。

已收到同學的座標回傳，但尚未完成全片可見性／點位覆核或實際座標比較，因此目前沒有人工座標誤差報告。評估是後續改善的依據，可用來找易錯關節、動作階段與資料缺口；匯入本身不會讓 MediaPipe 更新權重，不會自動訓練或微調。後續若要學習，需另外決定模型、標註品質、訓練資料與獨立驗證方式。
