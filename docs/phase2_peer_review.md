# Phase 2 同學獨立覆核

**2026-10-04 任務更正：** 使用者需要同學實際手動放置骨架 X/Y，原本這份可靠性紀錄表
不包含座標，無法獨立提供位置誤差基準。本次請改用 [CVAT 人工座標流程](phase2_manual_keypoints.md)
及新的 `manual_pose_package_20261004_01.zip`；本文件保留作可靠性／事件回覆與分 reviewer 匯入的說明。

本流程讓同學在自己的電腦檢查影片、既有骨架及事件，交回獨立人工判斷。沿用 `ground-truth-v1` 與 `review_profile: phase2_full_review`，並將結果另存；既有 HSU 標註與原始 prediction 都保持各自的來源。

## 本次範圍

| 影片 | 任務 | 需回覆的內容 |
|---|---|---|
| `pitch_003` | 完整獨立覆核 | 全部 115 格（0–114）：主體追蹤、六關節全片區間、五事件及整體觀察 |
| `pitch_005` | 事件補充 | 全部 101 格（0–100）的動作脈絡與五事件，至少回覆準備開始、最高抬腿、大致出手；其餘關節與追蹤維持未覆核 |

資料包不提供既有人工答案，也不從模型推測人工標籤。對外只附空白 ground truth 與空白回覆表，讓同學先看原片形成判斷。

這次檢查的是**既有骨架在可見關節上的位置與可靠性、主體追蹤及五個事件時間**。同學不需要重建完整 2D／3D 座標、估計不可見關節或建立新模型。

## 給同學的資料與入口

本次已產生：`analysis_results/phase2_yamamoto_20260925_01/peer_review_package_20261003_01.zip`（約 48 MiB）。
媒體未放進 GitHub；請把這份 ZIP 另行交給同學。

維護者產生一份 ZIP，使用者自行分享給同學。ZIP 完整解壓後，雙擊最外層 `START_HERE.html` 即可開始；所有連結使用相對位置，可以離線開啟。覆核不需要 Git、Python 或專案環境。

每支影片包含：

- `review_all.html`：原片、原始骨架影片與逐格檢查入口。
- 原片 `browser_playback/<pitch-id>.mp4`（內容與正式原片相同），及既有 raw overlay 的瀏覽器相容播放副本 `browser_playback/overlay_browser.mp4`。
- `frames/` 全尺寸逐格原片／骨架對照圖、`contact_sheets/` 縮圖索引與 `frame_index.csv`。
- `ground_truth.json`：綁定該支原片與 SHA-256 的空白表，人工欄位保持 `null`。
- `REVIEW_NOTES.md`：可直接用文字填寫的回覆表，含 reviewer、時間與時區、來源及任務範圍。

資料包最外層另有 `START_HERE.md`、`package_manifest.json` 與 `serve_review.py`。如果瀏覽器阻擋本機檔案，已有 Python 的同學可執行附帶的 `python serve_review.py` 開啟本機頁面；也可用本機播放器看影片並開啟 `frames/` 圖片。

對照圖左側是原片，右側是既有 raw overlay。CSV 與圖下方的 `observed`／`interpolated`／`missing` 是處理後模型狀態，**不是人工真值**；補點與模型 confidence 都不能代替影像證據。

可重用的同學說明與表格在：

- [START_HERE.md](../review_tools/peer_review/START_HERE.md)
- [REVIEW_NOTES_TEMPLATE.md](../review_tools/peer_review/REVIEW_NOTES_TEMPLATE.md)

## 人工判斷要求

同學依序看完整原片、完整 overlay，再從第一格檢查到最後一格；不只檢查模型提示區間。影格從 0 起算，區間兩端都包含；播放器時間僅適合找大致位置。

六關節為投手自己的**右肩、右肘、右腕、左髖、左膝、左踝**，不是畫面左右。完整覆核中，每個關節都要記錄正常與異常的完整影格區間：

| 狀態 | 人工證據 |
|---|---|
| `reliable` | 原片可見，骨架合理對位 |
| `unreliable` | 原片可見，但骨架錯位或漏點 |
| `uncertain` | 看過仍無法決定 |
| `not_observable` | 沒有足夠的位置證據，包含完全遮住或在畫面外 |

不可見時不補座標，不用透視或想像判定真實位置。自然遮擋不一定是換人；單個關節誤連旁人也不能直接判為整副骨架 identity switch。未確認的遮擋原因、視角或旁人影響保留為推測。

事件定義為準備開始、**最高抬腿**、左腳落地、大致出手及收尾回復穩定。最高抬腿不是首次腳離地；片頭已在動作中不能強迫把準備開始填 0；出手可用最後在手中／首次在空中的範圍，球看不清楚時保留不確定或不可觀測。

事件可填確定單格、確定範圍、`uncertain` 或 `not_observable`，每項都保留人工依據。`confidence` 是人工信心，可為 `null`，不強迫填數字。

## 回收、轉錄與保存

同學可交回每支填好的 `REVIEW_NOTES.md`，或同格式 `ground_truth.json`；不需要重傳媒體。回覆至少含 reviewer 名稱／代號、影片與資料包來源、實際檢查時間及時區、任務範圍與尚未完成內容。

使用者收到後可把檔案上傳回這段對話，或放進專案的暫存、忽略追蹤資料夾，再讓 Codex 協助整理。轉錄只能使用同學已說明的判斷，保留實際 reviewer 與轉錄來源；缺少的區段或事件保持未覆核，不代填為正常。

- 完整覆核才可標 `annotation_status: reviewed`：主體及各類異常已回覆、六關節全片區間無缺口、五事件皆有判斷，並有實際完成的 `reviewed_at_utc`。
- `pitch_005` 事件補充維持 `annotation_status: in_progress` 與 `reviewed_at_utc: null`；沒有覆核的關節與追蹤欄仍為 `null`。即使五事件已回答，也不宣稱全片完整覆核完成。
- 不確定或不可觀測是有效的人工結果。已看完全片且未見某類異常才可用 `[]`；`null` 代表尚未覆核。

維護者驗證 schema、影格範圍與完整性、來源檔名／SHA-256／實際影格數後，匯入：

```text
annotations/phase2_peer_reviews/<review-id>/<pitch-id>/ground_truth.json
```

匯入檔保留同學 JSON 的內容；不覆寫 HSU ground truth 或模型輸出。不自動平均、合併或裁定分歧；有差異時由人一起回看片段，再決定是否需要補充或修正。格式與來源驗證通過也不代表標籤正確或 Phase 2 已通過。

## 維護者操作

以下從專案根目錄執行；同學不需要執行這些指令。

產生本次資料包與同名 ZIP（輸出目錄使用新名稱）：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\export_peer_review_package.py analysis_results\phase2_yamamoto_20260925_01 input\yoshinobu_yamamoto\phase1_final analysis_results\phase2_yamamoto_20260925_01\peer_review_package_20261003_01 --full-review pitch_003 --events-supplement pitch_005 --review-assets-root analysis_results\phase2_yamamoto_20260925_01\review_helper_20260926_01 --producer-commit a02f1900d4b3eb77214cbf12bdfc37eb98fa1153
```

先把同學文字回覆忠實整理成 JSON，再匯入已驗證的回覆。`<returned-json>` 替換為實際檔案；review ID 由維護者指定並保持唯一。每支影片分別執行：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\import_peer_ground_truth.py '<returned-json>' input\yoshinobu_yamamoto\phase1_final\pitch_003.mp4 --review-id CLASSMATE_20261003
```

`pitch_005` 使用相同 review ID，來源改為 `pitch_005.mp4`。匯入工具只接受符合來源與格式的 JSON，不會自行解析文字表、修改 reviewer／日期、補齊人工答案或做 prediction comparison。既有目的地不覆寫；若之後交回修正版，使用新的 review ID 保留前一版。

程式、文件與人工標註 checkpoint 可由維護者依專案流程保存；媒體 ZIP 由使用者另行分享，無需讓同學操作 Git 或直接推送專案。
