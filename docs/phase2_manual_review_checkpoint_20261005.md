# Phase 2 人工覆核 checkpoint — 2026-10-05

## 已完成的保存

Tsai 在 2026-10-04 人工放置 `pitch_003` 的 115 格、12 關節，共 1,380 組原始 X/Y。
HSU 親自觀看原圖與人工骨架，逐段確認可見性及點位；Codex 依明確回答轉錄，未代替人工判斷。
原始 CVAT 全點 `visible` 宣告原樣保存，不把推估隱藏位置直接當成可觀測真值。

最新部分座標：[manual_keypoints.json](../annotations/manual_keypoints/HSU_TSAI_RETURN_20261004_07/pitch_003/manual_keypoints.json)。
最新補充：[ground_truth.json](../annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_01/pitch_003/ground_truth.json)。
七份舊座標 checkpoint、原 HSU canonical 紀錄、原影片與模型 prediction 均保留。

目前 **96 visible、84 not_observable、1,200 unreviewed**，狀態為 `in_progress`。
只有確認可見且對位的 96 組座標保留 Tsai 原始 X/Y；其餘座標為 `null`。
人工 confidence 與完整覆核完成時間未提供，均保持 `null`。

| 關節 | 可見且對位 | 不可觀測 | 未完成覆核 |
|---|---:|---:|---:|
| LEFT_SHOULDER | 0 | 0 | 115 |
| RIGHT_SHOULDER | 0 | 0 | 115 |
| LEFT_ELBOW | 9 | 15 | 91 |
| RIGHT_ELBOW | 38 | 14 | 63 |
| LEFT_WRIST | 5 | 19 | 91 |
| RIGHT_WRIST | 44 | 35 | 36 |
| LEFT_HIP | 0 | 0 | 115 |
| RIGHT_HIP | 0 | 0 | 115 |
| LEFT_KNEE | 0 | 0 | 115 |
| RIGHT_KNEE | 0 | 0 | 115 |
| LEFT_ANKLE | 0 | 1 | 114 |
| RIGHT_ANKLE | 0 | 0 | 115 |

這是逐點座標覆核進度，不是先前五支定性 GT 的完成比例。
雙肩、雙髖及腿部等尚未逐點核對；不能沿用「舊 AI 標得正確」就判定 Tsai 的點也正確。

## 待釐清的最後回答

83–92 格右肘已由 HSU 明確確認可見，但點位仍未完成確認。
HSU 接著回覆「沒有，我現在要睡了你先把能自行處理的部分處理好token用完也行」。
「沒有」可能表示沒有偏移，或是否定全部對位；只保存原話，不能據此把十格全部判對或判錯。
右腕 84–86 遮擋已保存，加上原先 83 與 87–104 不可觀測區段，不需要重複詢問。

## 下次從這裡續看

離線助手：
`analysis_results/manual_pose_return_check_20261004_01/autonomous_cleanup_20261005_01/review_resume/review_resume.html`。
旁邊有 `START_HERE.md`、十張逐格放大對照、兩張 contact sheet 與空白備註。
兩側是原圖／Tsai 人工標註，檢查右肘紅色 4 號；所有圖均標示位置尚待人工確認。
直接開 HTML 即可；圖片使用相對路徑，不依賴之前的本機 HTTP 服務。

1. 先釐清上面的「沒有」是沒有偏移，或有哪些格偏移。
2. 若有偏移，列格數；只有人提供修正座標或明確確認正確點時，才能採用該 X/Y。
3. 再檢查右肘 93–114、其餘尚未確認的手臂區段，然後雙肩、髖、膝、踝。
4. 被遮住或關節中心無法觀察時，不補透視座標；不確定可保留 `uncertain`。
5. 完整人工覆核後，先驗證 JSON／來源，再比較原始 prediction 與可見人工座標；人工不可觀測與 AI 漏點分開計數。

仍待同學 `pitch_005` 事件補充及實際完成 provenance；不擅自給 uncertain 事件精確答案。
HSU 對 `pitch_003` 的補充事件 13／46／65／69／99 保留於獨立檔，沒有覆蓋 canonical 的 12／47／66／69／99。

## 驗證結果

- 七份人工座標 checkpoint 及三份 HSU 補充 GT schema／來源驗證通過。
- 所有保留 X/Y 與原始 Tsai XML 相同；非 `visible` 座標為空白。
- 126 項正式 baseline／影片 hash、232 次歷史保護檔 hash 核對一致。
- 十張續看圖及原來源 hash 不變；離線頁 43 個相對連結存在。
- 完整 test suite：**147 passed、0 failed、1 skipped**（148 tests）。
- Skipped 是需明確啟用的正式影片 E2E；本次不重跑正式五支分析。既有合成影片 MediaPipe 測試有執行。
- 第一輪因受限環境暫存權限阻擋；保留該 log，改用正常暫存存取後完整 suite 通過，未改程式來通過測試。

本機報告根：`analysis_results/manual_pose_return_check_20261004_01/autonomous_cleanup_20261005_01/`。
包含 `agent_annotation_integrity_audit.json`、`manual_review_progress.json`、`manual_review_state_matrix.csv`、
`answer_transcription_check.json`、`test_suite_verified.log` 與 `test_suite_verified_summary.json`。

## 現在的範圍

**Phase 2 = IN PROGRESS**。已完成的定性 comparison 不等於精確座標準確率；完整座標比較尚未執行。
本次保存人工紀錄、接續助手與驗證結果，沒有模型學習、演算法修改或 Phase 3 工作。
MLB Pitch Clipper 的正式接入依 [current status](current_status.md#deferred-mlb-pitch-clipper-handoff) 順序：
先完成 Phase 2 人工證據與驗收，再做後續動作分析，之後才接收外部單球 MP4＋metadata；不複製其取得／剪輯邏輯。
原 XML 含帳號資訊，只在本地保存並由 Git 忽略；影片、原回傳 ZIP 與對照圖片仍是本機產出。
