# 山本四球：人工事件與動作時序交付

2026-10-24（台灣）。依HSU「好進行」授權，處理目前啟用的001／002／004／005，
共477格；003保持歷史對照。大谷五球與兩位投手已接受的骨架方式、觀看頁均保持。

## 本輪新增

新增`compare-native-motion-events`，直接讀取既有肘／膝曲線及同源canonical人工事件。
曲線上以實線、範圍色帶、不確定虛線分別呈現；每球附事件表及事件角度視窗，
另外列出四球的事件時距。不修改原曲線、不選事件中點、不產生新標註。

20筆人工事件逐欄保留：17筆annotated、2筆uncertain、1筆not_observable。
16筆時距中13筆可界定、3筆留空；所有477格曲線仍保留，沒有移除資料。

## 逐球時距（秒）

| 影片 | 啟動→最高抬腿 | 最高抬腿→落地 | 落地→出手 | 出手→收尾 |
|---|---:|---:|---:|---:|
| pitch_001 | 不可觀測 | 0.533–0.767 | 0.133–0.200 | 0.600–0.667 |
| pitch_002 | 1.467 | 0.733 | 0.033–0.100 | 0.833–0.900 |
| pitch_004 | 1.333 | 0.700–0.733 | 0.133–0.200 | 0.600–0.633 |
| pitch_005 | 不確定 | 不確定 | 0.100–0.133 | 0.800–0.833 |

以上由既有人工作記錄與30/1 FPS換算，小數顯示至三位；JSON保留完整數值與分數秒數。
001的啟動在片頭不可觀測；005的啟動0、最高抬腿33仍是候選，沒有提升成精確答案。
四球的落地→出手時間界線不同；這只描述現有人工標記下的時序，不判動作好壞或推論原因。
相近／重疊的範圍也不視為相同動作的證明。

## 開啟

在Chrome或Edge按`Ctrl+O`，選擇：

```text
D:\project\pitch-analysis\analysis_results\phase3_yamamoto_event_timing_20261024_01\comparison\viewer\review_motion_events.html
```

先選影片，播放或逐格查看原骨架／兩條曲線與事件標記，頁面下方有逐球時距表。
005仍為HSU偏好的示範；新頁操作尚待確認，原觀看頁接受紀錄不被覆寫。
[指令、圖例與區間計算](native_motion_events.md)。

## 資料與限制

使用`config/analysis_inputs/yamamoto_event_timing_20261024.json`列明的四份人工事件檔SHA，
並驗證原片SHA、檔名、影片ID、格數與0起算。只讀事件，沒有把舊模型的關節品質標籤搬到新骨架。
新增人物偵測、pose推論、tracking replay、角度重算、新GT均0。
唯一修改的既有產品檔為CLI新增命令；曲線入口、播放同步JS、模型／selector／門檻與raw／GT保持。

事件視窗角度仍是未校準的模型XY投影，保留完整缺值分母；逐點unknown與usable null保持。
原片時間軸不平移，沒有精確出手對齊、跨投手比較或評分。
自動瀏覽器互動驗證未執行，保留`browser_interaction_verified=false`；沒有繞過file://工具限制。

## 測試與來源保持

完整Python suite：**1201 passed／0 failed／0 errors／2 skipped**，共1203項、135.796秒。
本輪新增19項，涵蓋區間手算、分數FPS、不確定性、缺值分母、來源拒收、原資料不變、
CLI、播放器資源保持、嵌入JSON與人工備註跳脫。正式五球MediaPipe E2E也已執行。
兩skip仍為Windows檔案symlink建立能力；其餘既有路徑測試已執行。
另5項既有純Node時間測試與18項事件圖示／文字helper斷言全過，不含瀏覽器或DOM。

233份受保護的來源、raw、人工紀錄與既有輸出SHA變更0；
新頁中的20筆事件逐欄對照原人工紀錄，差異0。
原播放同步JS逐位元組沿用，事件裝飾為獨立新JS。
唯一完整suite本輪執行一次，完成後未追加測試或模型試驗。

證據：`analysis_results/phase3_yamamoto_event_timing_20261024_01/verified_suite/test_results.json`。
[版本化交付紀錄與來源SHA](dataset_selections/phase3_yamamoto_event_timing_20261024.json)。

**本輪事件／時序交付完成；Phase2自動可靠性仍NOT PASSED；Phase3整體NOT EVALUATED。**
輸出：`analysis_results/phase3_yamamoto_event_timing_20261024_01/comparison/`。
本輪完成測試、提交與推送後停止，不新增下一功能。
