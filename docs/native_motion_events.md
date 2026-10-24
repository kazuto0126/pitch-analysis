# 同投手人工事件與2D曲線對照

此入口讀取已保存的動作曲線，以及**同一原片已完成覆核的人工事件**，
在原曲線上加事件標記，並列出每球的事件時距。
人工事件沿用`ground-truth-v1`，沒有新建標註格式或修改原標註。

```powershell
pitch-analysis compare-native-motion-events `
  config/analysis_inputs/yamamoto_event_timing_20261024.json `
  --output analysis_results/event_comparison_NEW
```

設定列出一位投手的影片ID、既有動作輸出目錄，以及人工事件檔的path／SHA256。
所有輸入須位於本專案內；原片SHA／檔名、影片ID、完整格數與0起算時間軸必須一致。
事件檔須為`reviewed`；輸出須為新的`analysis_results/`目錄，不覆寫既有結果。

## 圖上如何呈現

| 人工事件 | 曲線標記 | 時距／事件視窗角度 |
|---|---|---|
| annotated＋精確格 | 實線 | 計算 |
| annotated＋格數範圍 | 色帶與兩端界線 | 保留上下界 |
| uncertain＋候選範圍 | 虛線／虛線色帶，標示候選 | 留空，不使用候選計算 |
| uncertain但無候選 | 只在事件表列出 | 留空 |
| not_observable／not_visible | 只在事件表列出 | 留空 |

單格範圍仍保留range，單格uncertain候選仍不視為精確判斷。
事件表保留原confidence與note；null信心不推算成分數。
播放器、逐格、格號與曲線跳轉沿用既有程式，原骨架與曲線座標不改。

## 時距與角度的意義

每球列出：啟動→最高抬腿、最高抬腿→落地、落地→出手、出手→收尾。
兩事件範圍為`[a0,a1]`與`[b0,b1]`時，時距上下界為：

```text
格數：[max(0, b0 - a1), b1 - a0]
秒數：格數 / 分數FPS
```

採用事件的時間先後順序；若範圍重疊，可能的最小時距為0。
任一端不確定或不可觀測，時距留空並說明原因。沒有取中點作精確出手，也沒有推測事件。
結果JSON另保留分數秒數，表格的小數只是顯示格式。

已確認事件範圍內的肘／膝角列出模型XY最小／最大值、計算格數、缺值格數與退化格數。
完整視窗分母保留，不補點、不平滑、不依模型分數刪除樣本；不可計算時角度仍空值。
這些是模型2D投影的視窗描述，不是人體角度真值、校準精度或動作品質分數。

## 輸出

- `event_comparison.json`：逐球事件、時距、事件角度視窗、reviewer與來源／產物SHA。
- `event_timing.csv`：每球四筆時距，包含不可計算的項目與原因。
- `report.md`：可閱讀的逐球時序摘要。
- `viewer/review_motion_events.html`：影片、原始曲線、事件線／色帶與同投手時距表。
- `viewer/event_viewer_manifest.json`：觀看頁、原播放JS與事件JS的SHA及檢查範圍。

本機可在Chrome或Edge用`Ctrl+O`開啟HTML；須保留專案相對目錄，影片仍使用原overlay。
沒有外部JS或網路資料請求，也不寫人工標註。

逐點可靠性unknown、可用角度／usable_for_analysis=null保持。
此入口只使用舊GT的事件，不把舊模型關節品質判斷套用到新骨架。
沒有精確事件對齊、跨投手比較、評分或3D推論，不改Phase2與Phase3整體驗收狀態。

[山本四球實際結果](phase3_yamamoto_event_timing_20261024.md)。
