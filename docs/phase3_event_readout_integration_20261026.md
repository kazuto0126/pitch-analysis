# 事件角度讀值已接入正式報告

更新：2026-10-26（台灣）。

`compare-native-motion-events`現在直接產生事件角度讀值表與`event_angle_readouts.csv`，
觀看頁同步顯示讀值範圍。之後不必另做一次離線整理；原指令與設定檔可沿用。

| 視窗 | 本次數量 | 輸出意義 |
|---|---:|---|
| 單格 | 60 | 保留當格模型角度，時間敏感度未評估；跨度為null |
| 多格 | 24 | 保留min–max與max−min跨度；本次24窗皆完整可計算 |
| 事件未確認 | 6 | 角度、跨度與計數保持null，不取候選影格計算 |

一般輸入若有缺值，多格至少兩個可計算樣本才輸出「可計算樣本跨度」，
並標明視窗不完整；零或一個樣本不估跨度。缺失／退化數量與完整分母都保留。
這些數字描述模型XY變化，不能據此判斷動作優劣、定位準確性或真實3D角度。

## 新版輸出

根目錄：`analysis_results/phase3_event_readout_integration_20261026_01/`。
兩位投手各自出報告，沒有跨投手排名；山本003仍為歷史對照，不恢復使用。

- [大谷五球報告](../analysis_results/phase3_event_readout_integration_20261026_01/ohtani/report.md)：1684格、25事件、50列讀值。
- [大谷觀看頁](../analysis_results/phase3_event_readout_integration_20261026_01/ohtani/viewer/review_motion_events.html)；[CSV](../analysis_results/phase3_event_readout_integration_20261026_01/ohtani/event_angle_readouts.csv)。
- [山本四球報告](../analysis_results/phase3_event_readout_integration_20261026_01/yamamoto/report.md)：477格、20事件、40列讀值。
- [山本觀看頁](../analysis_results/phase3_event_readout_integration_20261026_01/yamamoto/viewer/review_motion_events.html)；[CSV](../analysis_results/phase3_event_readout_integration_20261026_01/yamamoto/event_angle_readouts.csv)。

觀看頁以Chrome／Edge的`Ctrl+O`開啟，保留專案目錄與既有overlay。
本輪沒有新增實際瀏覽器操作驗證或人工頁面接受紀錄。
`analysis_results`為本機產物；GitHub保存程式、測試、文件與來源／測試紀錄，未上傳影片或重打包舊ZIP。

## 變更與驗證

- `analysis/native_motion_events.py`：新增三個視窗描述欄位、Markdown角度表與CSV，舊欄位保持。
- `review_assets/native_motion_events.js`：顯示單格／多格／未確認及缺值範圍；舊payload缺欄位時相容處理，明確null不補算。
- 新增8項Python測試；事件helper保留原18項斷言，新增16項，共34項。
- 完整Python suite：**1251項，1249 passed／0 failed／2 skipped**，包含正式山本五球MediaPipe E2E。
- 兩項跳過皆為Windows環境不支援檔案符號連結；無未修復測試失敗。
- 純Node測試：**11 passed／0 failed／0 skipped**（含事件helper的34項斷言），沒有使用瀏覽器或DOM。
- 實際九球共2161格：舊720個視窗欄位、36段時距保持；兩份時距CSV逐bytes相同。
- 545份受保護來源SHA全部相同；獨立唯讀覆核確認90列與null語義，原片、raw、GT、舊輸出及可攜ZIP保持。

[來源與測試紀錄](dataset_selections/phase3_event_readout_integration_20261026.json)。
[輸出欄位及使用方式](native_motion_events.md)。

本次沒有新骨架推論、追蹤重跑或人工標註；pose／tracking核心、門檻與原播放器不改。
逐點可靠性仍unknown、usable_for_analysis仍null。
Phase 1 PASSED；Phase 2原自動可靠性NOT PASSED；Phase 3描述性交付延續，整體尚未驗收。
本輪在文件、測試、commit與origin push完成後停止。
