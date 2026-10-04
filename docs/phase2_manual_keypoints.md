# Phase 2 人工 2D 關節座標

更新：2026-10-04。本次以 `pitch_003` 建立獨立人工 X/Y 基準，量化既有 AI 骨架位置誤差。讓同學在原片上親自畫出及修正骨架，並逐格記錄是否有足夠影像證據；這比「骨架可靠／不可靠」區間多出可直接比較的座標。

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

## 計算 AI 位置誤差

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\evaluate_manual_keypoints.py annotations\manual_keypoints\CLASSMATE_20261004\pitch_003\manual_keypoints.json analysis_results\phase2_yamamoto_20260925_01\predictions\yoshinobu_yamamoto\pitch_003\keypoints.json analysis_results\phase2_yamamoto_20260925_01\manual_keypoints_error_CLASSMATE_20261004.json
```

比較前確認 prediction 的同支來源與相鄰 `video_metadata.json`。模型的 normalized X/Y 轉為原圖 pixels，再以同影格、同解剖關節與人工 `visible` 座標做比較：

```text
pixel_error = sqrt((AI_x - human_x)^2 + (AI_y - human_y)^2)
```

誤差只統計**有人工可見座標且有有效模型座標**的點，逐關節報告。人工可見但 AI 漏點要另列數量與比率；保留人工可見點總數、有效比較數及各人工狀態的數量，避免把 AI 漏點排除後誤認成表現良好。AI confidence／visibility 不是人工可見性；人工非 `visible` 點不以暫放值計算誤差。

收到同學真實座標前沒有人工誤差報告。評估是後續改善的依據，可用來找易錯關節、動作階段與資料缺口；匯入本身不會讓 MediaPipe 更新權重，不會自動訓練或微調。後續若要學習，需另外決定模型、標註品質、訓練資料與獨立驗證方式。
