# 大谷五球人工事件與曲線對照

2026-10-25（台灣）。HSU完成25筆事件後授權「繼續」，本輪將已保存事件接入既有同投手比較。

## 已交付

五球共1684格、25筆人工事件（21精確格／4範圍），產生20筆時距：14精確值、6上下界、0不可計算。
所有時間均依60000/1001 FPS，從原片第0格起算；範圍不取中點。
肘／膝曲線、overlay及播放器沿用已接受結果，沒有新增推論、追蹤或人工標註。

- 對照頁：`analysis_results/phase3_ohtani_event_timing_20261025_01/comparison/viewer/review_motion_events.html`
- 逐球摘要：`analysis_results/phase3_ohtani_event_timing_20261025_01/comparison/report.md`
- 資料：同目錄的`event_comparison.json`與`event_timing.csv`
- 可匯出總覽：`analysis_results/phase3_ohtani_event_timing_20261025_01/timing_intervals.png`
- 設定：`config/analysis_inputs/ohtani_event_timing_20261025.json`
- [版本化結果與來源](dataset_selections/phase3_ohtani_event_timing_20261025.json)

在Chrome或Edge按Ctrl+O，開啟上方對照頁的完整本機路徑，切換001–005即可查看原overlay、
肘／膝曲線、事件線／範圍色帶與時距表。既有逐格、播放和曲線跳轉程式保持。
本輪已檢查產物資料及靜態圖；未執行自動瀏覽器互動，也尚未記錄此新頁的人工操作確認。

## 五球時距（秒）

| 球 | 啟動→最高抬腿 | 最高抬腿→落地 | 落地→出手 | 出手→收尾 |
|---|---:|---:|---:|---:|
| 001 | 0.517 | 0.851 | 0.150–0.167 | 0.667–0.684 |
| 002 | 0.284 | 0.567 | 0.133 | 1.101 |
| 003 | 0.234 | 0.617 | 0.133 | 0.734 |
| 004 | 0.534 | 0.884 | 0.083 | 0.851 |
| 005 | 0.234–0.300 | 0.417–0.467 | 0.167–0.184 | 0.567–0.584 |

表格取三位小數供閱讀；JSON保留分數秒數及原影格上下界。
例如002與003的落地→出手均為8格；001為9–10格，005為10–11格，在10格相接。
這些是本批人工事件界線下的節奏差異，不推論優劣、球速、統計顯著性或投手整體穩定度。

## 接入範圍與資料保護

原入口只接受整份`reviewed`GT；新增可選的`event_review_ref`，讀取已存在的五事件完成紀錄。
核對reviewer、五事件範圍、影片ID、時間、GT及MP4的path／SHA，資料不符即拒收。
輸出明確記為`event_only`，GT仍`in_progress`，完成時間與其他未覆核欄位仍null。
沒有修改GT schema／validator、pose／tracking核心、門檻、平滑、插值或人工答案。
完整reviewed的山本入口仍相容，山本003仍僅供歷史對照。

512份受保護來源／程式／資料SHA無變更；本輪只修改事件比較讀取器，新增11項測試與設定／文件。
大谷素材仍是候選；逐點可靠性unknown、usable_for_analysis=null保持。
Phase2自動可靠性仍NOT PASSED，Phase3整體NOT EVALUATED；本次交付不改其結論。

## 測試

- 完整Python suite：1214項，1204 passed／0 failed／0 errors／10 skipped，含正式五球E2E。
- 其中8項Windows目錄junction案例因sandbox限制跳過，另行只補跑這8項：8 passed、0 skipped。
- 合併不重複測試結果：**1212 passed／0 failed／0 errors／2 skipped**。
- 剩餘2項因Windows環境不支援檔案符號連結而跳過，原因保存於完整suite紀錄。
- Node：原播放器5項測試、事件helper18項斷言全過；沒有瀏覽器／DOM驗證。
- 記錄：`analysis_results/phase3_ohtani_event_timing_20261025_01/verified_suite/`。

下一步先使用此頁檢視已確認事件與曲線的對應。本輪交付與commit／push後停止，不擴增投手或功能。
