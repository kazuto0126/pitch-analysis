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
事件檔須為`reviewed`，或提供下述已完成五事件的覆核紀錄。
輸出須為新的`analysis_results/`目錄，不覆寫既有結果。

## 只完成事件覆核的資料

若GT仍為`in_progress`，每球設定可另提供`event_review_ref`（path／SHA256），
指向既有`manual-event-review-checkpoint-v1`完成紀錄。原事件仍只保存在ground-truth-v1。
讀取器核對五個事件名稱完整且無重複、完成旗標、reviewer、影片ID、有時區的紀錄時間，
並要求紀錄綁定的GT與原片path／SHA完全符合本次輸入；過期或未完成紀錄會拒收。
沒有這份紀錄的`in_progress`資料仍不能使用；完整`reviewed`資料的舊設定保持有效。

此方式只授權讀取五事件，未覆核的其他欄位及`reviewed_at_utc=null`保持。
輸出以`event_review_scope.kind=event_only`與`full_pose_gt_complete=false`明確記錄範圍，
另保留checkpoint的`recorded_at_utc`，不把它當成完整GT完成時間。
明確的uncertain／not_observable也可完成事件覆核，但相關時距仍留空。

大谷五球設定：`config/analysis_inputs/ohtani_event_timing_20261025.json`。

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

事件報告、觀看頁與CSV會區分以下讀值：

| `reading_kind` | 讀值方式 | `sample_span_deg`／`sample_span_scope` |
|---|---|---|
| `single_frame` | 已確認的單格視窗，保留當格角度；時間敏感度未評估 | null／`not_assessable` |
| `multiple_frames` | 多格視窗，至少兩個可計算樣本才列max−min | 全部可算為`complete_window`；有缺值為`calculated_samples_only` |
| `event_unresolved` | 人工不確定或不可觀測，候選影格不參與角度計算 | null／`not_assessable` |

多格只有零或一個可計算樣本時，跨度同樣為null／`not_assessable`。
部分視窗顯示「可計算樣本跨度」，不能當成完整事件範圍；缺失／退化格數與完整分母仍列出。
單格不填0度跨度；多格實際算得0度也只描述模型讀值，不能推定關節可靠。
原事件status、confidence、note、min/max與可用性判定保持。

## 落地到大致出手的模型角度變化

同一輸出另列投球肘與前導膝的端點變化：

```text
delta_model_xy_deg = 出手影格的model_xy_deg − 落地影格的model_xy_deg
```

只使用已確認的人工foot_plant與approximate_release。兩端若是範圍，保留所有
`落地格 <= 出手格`的配對（含同格），並列出排除的倒序配對數；不選中點或合併重複差值。
每個配對保留原格號、兩端角度及計算狀態、分數FPS換算的時距與差值。
摘要的min/max為全部可計算合法配對的差值極值，並非期間角度最大活動範圍。

兩端都能計算才產生差值；任一端缺點或幾何退化則保留空值，不補點或丟棄配對。
`missing_endpoint_pairs`與`degenerate_endpoint_pairs`可重疊；`unavailable_pairs`為聯集，
與`calculated_pairs`合計等於`total_pairs`。至少一個配對可算便保留其差值；全不可算時min/max為null。
人工事件任一未確認時，摘要計數與差值全部null，配對列表空白，候選影格不參與計算。

`delta_direction`的positive／negative／zero／includes_zero只表示模型差值的正負／包含0，
沒有品質門檻或可靠性評級。配對數不是獨立樣本數，範圍也不是統計信賴區間。
不能據此推論人體真實伸屈、角速度、動作好壞或投手整體穩定度；unknown/null保持。

## 輸出

- `event_comparison.json`：逐球事件、時距、事件角度視窗、reviewer與來源／產物SHA。
- `event_timing.csv`：每球四筆時距，包含不可計算的項目與原因。
- `event_angle_readouts.csv`：每球五事件×兩關節共10列，含影格範圍、原人工status／confidence／note、min/max、完整格數與缺值／退化數，以及上述三個新增讀值欄位。null在CSV中為空白；可靠性維持unknown、usable_for_analysis為空白。
- `event_transition_readouts.csv`：每球兩列落地→大致出手的端點變化摘要，含事件界線、合法／倒序配對分母、計算／缺點／退化數量及差值極值。
- `event_transition_pairs.csv`：每個合法配對的兩個關節各一列，包含不可計算的配對；附原格號、分數時距與兩端狀態。
- `report.md`：逐球時序與事件角度讀值表，說明單格、多格及未確認事件。
- `viewer/review_motion_events.html`：影片、原始曲線、事件線／色帶與同投手時距表。
- `viewer/event_viewer_manifest.json`：觀看頁、原播放JS與事件JS的SHA及檢查範圍。

本機可在Chrome或Edge用`Ctrl+O`開啟HTML；須保留專案相對目錄，影片仍使用原overlay。
沒有外部JS或網路資料請求，也不寫人工標註。

逐點可靠性unknown、可用角度／usable_for_analysis=null保持。
此入口只使用舊GT的事件，不把舊模型關節品質判斷套用到新骨架。
沒有精確事件對齊、跨投手比較、評分或3D推論，不改Phase2與Phase3整體驗收狀態。

[山本四球實際結果](phase3_yamamoto_event_timing_20261024.md)。
[大谷五球實際結果](phase3_ohtani_event_timing_20261025.md)。
[正式報告讀值整合與新版輸出](phase3_event_readout_integration_20261026.md)。
[落地→大致出手的模型變化結果](phase3_event_transition_20261026.md)。

## 以前腳落地對齊曲線

若同投手各球的落地皆為人工確認的精確單格，可使用同一設定：

```powershell
pitch-analysis align-native-motion `
  config/analysis_inputs/ohtani_event_timing_20261025.json `
  --output analysis_results/foot_plant_alignment_NEW
```

新增相對時間`(frame_index − foot_plant_frame) / 分數FPS`，保留全部原曲線樣本。
輸出肘／膝疊圖、完整CSV與摘要；出手區間仍為區間。落地若為範圍或不確定則拒絕對齊，
不選中點、不重取樣或改變時間比例。這是新增入口，原事件對照頁及時間語義保持。
[大谷五球落地對齊結果](phase3_ohtani_foot_plant_alignment_20261025.md)。

人工落地為annotated範圍時，可另加`--retain-anchor-ranges`，輸出所有候選平移與每個原始樣本的
時間上下界；不指定單一原點。原精確模式行為保持，uncertain／不可觀測也不會因新旗標取得原點。
見[山本四球範圍比較](phase3_yamamoto_anchor_bounds_20261025.md)。
