# 兩位投手的人工事件時距對照

更新：2026-10-26（台灣）。`compare-native-timing`是新增的描述性入口，
從兩份既有單投手事件報告比較四段**已標人工事件時距**。原單投手指令、骨架方法與品質gate保持。

## 使用

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe compare-native-timing `
  analysis_results/phase3_manual_stages_20261026_01/ohtani/event_comparison.json `
  analysis_results/phase3_manual_stages_20261026_01/yamamoto/event_comparison.json `
  --output analysis_results/timing_comparison_NEW
```

依參數順序定義A／B。需要兩位不同投手的報告，輸出必須為專案`analysis_results/`內的新目錄。
讀取器沿用既有來源驗證：核對原request SHA，重新讀取已保存曲線與人工事件，
要求報告的影片、事件／時距及覆核紀錄與原來源一致；篡改或過期報告會拒絕。
原生資料介面只讀既有結果，不執行模型或推定新事件。

## 比較方式

每個區段比較A組每球與B組每球，不先算平均、不丟棄事件不足的配對。
各片使用自己的`Fraction(fps_fraction)`，由原`frame_bounds`換算秒數，不能直接跨FPS比格數。

```text
A秒數範圍 = A格數範圍 / A分數FPS
B秒數範圍 = B格數範圍 / B分數FPS
差值範圍 = [A最短 − B最長, A最長 − B最短]
```

| 關係 | 意義 |
|---|---|
| a_shorter／a_longer | 在所有已記錄的合法選格下，A時距嚴格較短／較長 |
| identical_exact | 兩側都是精確時距，分數秒完全相同 |
| touching | 範圍只在邊界相接，不支持嚴格先後 |
| overlapping | 範圍有其他重疊，不能建立嚴格關係 |
| unavailable | 任一側事件未確認，差值留空，保留原原因 |

判斷使用完整分數，表格的小數僅供閱讀。大谷8格／(60000/1001)與山本4格／30
分別為1001/7500秒與1000/7500秒，皆可能顯示0.133秒，但差值是1/7500秒。
這只代表已記錄界線的算術差異，不表示人體計時精度已到0.133 ms，也不是統計顯著。
影格粒度、人工界線誤差與未知球種／場景仍會影響可解釋性，沒有新增「有意義差異」門檻。
同名事件沿用各片既有人工紀錄，沒有重新校準兩位投手的啟動／收尾判讀標準；結果保持記錄層的對照。

## 輸出

- `timing_comparison.json`：兩側來源、逐球事件界線／FPS、全部配對、分數秒與未知原因。
- `pitch_timings.csv`：每球四段原時距，未定也保留列。
- `timing_pairs.csv`：每球對的關係／差值，附原格數、分數秒、來源影片與GT路徑；空值不填0。
- `report.md`：區段配對數量、逐球時距、全部球對與原片／人工事件連結。

這不是正式`pitcher-comparison-v1`完整動作比較；沒有角度相似度、動作品質分數、姿勢合成或排名。
逐點可靠性unknown、`usable_for_analysis=null`保持，來源素材資格及registry不變。
配對共用影片，不能當成獨立樣本、機率或投手整體快慢的證據。

## 本批大谷五球／山本四球結果

本機[完整對照](../analysis_results/phase3_manual_timing_comparison_20261026_02/report.md)／
[逐球時距](../analysis_results/phase3_manual_timing_comparison_20261026_02/pitch_timings.csv)／
[全部球對](../analysis_results/phase3_manual_timing_comparison_20261026_02/timing_pairs.csv)。

A為大谷5球、B為山本啟用4球，共9球2161格。每段20組，共80組：65可比較、15事件不足。
山本003仍排除；001啟動、005啟動／最高抬腿未確認，不使用候選格補齊。
大谷仍為候選素材，本次對照不把它提升為正式reference。

| 區段 | 可比較／全部 | A較短 | A較長 | 精確相同 | 相接 | 重疊 | 事件不足 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 啟動→最高抬腿 | 10／20 | 10 | 0 | 0 | 0 | 0 | 10 |
| 最高抬腿→落地 | 15／20 | 7 | 6 | 0 | 0 | 2 | 5 |
| 落地→出手 | 20／20 | 3 | 8 | 0 | 0 | 9 | 0 |
| 出手→收尾 | 20／20 | 8 | 11 | 0 | 0 | 1 | 0 |

在本批已確認的啟動／抬腿界線下，大谷五球的這一段時距均短於山本002／004。
其餘區段出現雙向差異及重疊，不能概括成某位投手整個動作一定較快；前段未確認的山本球也不能推廣此結論。
上述數量只描述本批配對，並非正式投手profile比較、優劣或泛化結果。

新增15項測試涵蓋分數FPS、微小分數差、區間關係、未知原因／空值、來源與覆寫拒絕，以及CLI。
完整suite1285項：初跑1275 passed／0 failed／10 skipped；其中八項junction環境案例已單獨補跑全部通過，
按不重複測試計為**1283 passed／0 failed／2 skipped**，含正式山本五球E2E。
剩餘兩項為Windows檔案符號連結能力限制；沒有未修復失敗。重跑既有輸出會拒絕覆寫。
[版本化交付與測試紀錄](dataset_selections/phase3_manual_timing_comparison_20261026.json)；
本機完整／補跑紀錄與合併結果保存在輸出目錄的`verified_suite/`及`validation_summary.json`。
Phase 2自動可靠性與Phase 3整體驗收結論保持。
