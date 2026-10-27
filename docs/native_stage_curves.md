# 人工區段內的模型讀值範圍

更新：2026-10-27（台灣）。這個入口讀取已保存的曲線，列出每段內的肘／膝模型XY極值、
所有並列極值格號、完整分母與缺值，再連回既有原影格播放器。
它描述區段中間的保存樣本，不偵測新事件、不修改原曲線或人工GT。

## 使用

已有事件報告時，只產生這份附加分析：

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe describe-native-stage-curves analysis_results/phase3_native_motion_delivery_20261027_01/ohtani/events/event_comparison.json --output analysis_results/my_stage_curves
```

未來建立新的完整交付時，可選擇一起加入：

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe build-native-motion-report config/analysis_inputs/ohtani_event_timing_20261025.json --output analysis_results/my_full_delivery --include-stage-curves
```

整合指令預設仍為原三步；加入旗標後，在review之後建立`stage_curves/`，
並從`START_HERE.html`連到新讀值報告。既有交付不覆寫。
本次九球只用獨立入口讀取既有事件報告，沒有重做三份原交付；可選整合以小型四產生器端到端測試驗證。

本機報告：[大谷五球](../analysis_results/phase3_stage_curves_20261027_01/ohtani/report.html)／
[山本四球](../analysis_results/phase3_stage_curves_20261027_01/yamamoto/report.html)。
展開球號與區段，再展開最小／最大模型角的「原格號」即可回看片段；全部並列格都保留。

## 事件範圍如何處理

令起點候選為S、終點候選為E，只使用已確認人工事件，保留所有`s∈S、e∈E、s≤e`的配對。
每個區間`[s,e]`都包含首尾，影格分母為`e−s+1`。

| 窗口 | 定義 | 意義 |
|---|---|---|
| 可能影格 | 所有合法區間的聯集 | 至少一組合法事件選格會包含 |
| 共同影格 | 所有合法區間的交集 | 每組合法選格都包含；不表示關節可靠 |
| 逐區間讀值 | 每組合法配對各自計算 | 保留選格敏感度，不選中點、不合併相同結果 |

聯集／交集都從排除倒序後的合法配對計算。交集可以是空集合；若已確認事件完全沒有合法配對則拒收。
相鄰段共用事件，不能把各段獨立極值相加成單一路徑；不同關節的極值也未必出現在同一格。

## 空值、分母與跨度

| 情況 | 輸出 |
|---|---|
| 人工uncertain／不可觀測，即使有單格候選 | 不使用候選；分母、極值與格號列表皆null |
| 事件已確認，但共同影格為空 | `empty_intersection`；分母0、極值null、格號列表空 |
| 有區間但缺座標／退化 | 完整分母保留，兩類分開計數；可算樣本才參與極值 |
| 只有一個可算樣本 | min=max，跨度null |
| 至少兩個可算樣本 | 跨度=max−min；真實算得0則保留0 |

跨度為`complete_window`或`calculated_samples_only`；少於兩個可算樣本為`not_assessable`。
原始未四捨五入數值決定極值與全部並列格，時間使用`frame_index / fractional_fps`，第0格是0秒。
不補點、不平滑，不用模型分數刪除樣本。缺口兩側可形成樣本範圍，但不能推論缺口內的軌跡。

## 本批資料與一個可回看的例子

大谷20段皆已確認；山本16段中13段已確認、3段事件未定。
山本001啟動、005啟動／最高抬腿保持原狀，003仍排除。

大谷001啟動28格至最高抬腿59格內，投球肘模型角最小為76.568971°（32格）、
最大為102.270107°（45格），兩者都出現在區段中間。
這讓讀者可以回看端點之外的保存讀值；不能單靠極值判定真實轉折或模型錯位。

## 產物與限制

- `stage_curves.json`：全部區段、事件原標註、合法配對、兩種窗口及逐區間完整數值與來源SHA。
- `stage_windows.csv`：每球四段×兩關節×兩窗口，包含未知與空交集。
- `stage_intervals.csv`：每組合法區間、每關節一列，保留所有配對與極值格號／分數時間。
- `report.html`及`source_###.html`：讀值與原片／曲線回看；原播放器與跳格adapter逐bytes沿用。

來源、人工事件報告及原四段端點讀值須一致；輸出只能是新`analysis_results/`子目錄。
這些是模型XY樣本範圍，不是真實人體活動幅度、3D角度、角速度、品質分數或新事件標註。
逐點可靠性仍unknown、usable_for_analysis仍null，沒有模型／門檻修改或reference提升。
瀏覽器實際播放尚未覆核；Phase 2自動可靠性及Phase 3整體驗收狀態保持。

## 驗證

新增11項區段曲線與4項可選串接測試，涵蓋區間含首尾、內部極值／並列格號、合法配對裁切、
空交集與未知的區別、缺值分母、單點null／真0跨度、來源／播放器保留，以及真實四產生器小型端到端串接。
完整Python suite1333項：初跑1323 passed／0 failed／10 skipped，八項junction案例補跑全過；
不重複計為**1331 passed／0 failed／2 skipped**，含正式五球E2E。
兩項跳過仍為Windows檔案符號連結能力限制。JS未改，未重跑相同Node suite，最近仍為23項通過。

實際九球保留2161格、36段／72筆關節摘要，輸出144筆窗口與154筆合法區間關節讀值。
報告600個本地連結均存在，其中585個極值影格連結均在對應原片範圍內；這是靜態資料檢查，非瀏覽器播放驗收。
[交付、來源與完整測試紀錄](dataset_selections/phase3_stage_curves_20261027.json)。
