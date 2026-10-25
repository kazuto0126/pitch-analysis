# 大谷五球：落地對齊的肘／膝曲線

2026-10-25（台灣）。HSU核准「五球以前腳落地為0秒，曲線疊合並保留出手範圍」後完成。

## 結果與觀看方式

使用已接受的五球骨架、1684格原曲線與25筆人工事件。兩張圖各包含：

1. 完整原片時間範圍的五球疊合曲線。
2. 落地前後各0.5秒的放大圖，使用同一批原始樣本。
3. 五球人工出手相對落地的位置，影格範圍保持為區間。

輸出：`analysis_results/phase3_ohtani_foot_plant_alignment_20261025_01/alignment/`。

- `throwing_elbow_aligned.png`：投球肘模型XY角度疊圖。
- `lead_knee_aligned.png`：前導膝模型XY角度疊圖。
- `aligned_curves.csv`：保留全部原片影格、時間、角度、狀態與空可用性欄位，新增相對格號／時間。
- `alignment_summary.json`：來源、人工事件、落地格號、平移後事件範圍及產物SHA。
- `report.md`：圖片與逐球對照表。

## 時間基準

```text
relative_frame_index = 原片 frame_index − 人工 foot_plant.frame_index
relative_timestamp = relative_frame_index / 分數 FPS
```

五球皆為60000/1001 FPS，落地格號001–005依序為110、129、156、124、124。
第0格的原片時間仍為0；只有新增的顯示時間可為負值。落地樣本的相對時間精確等於0。
CSV另保留分數秒數，計算不採用浮點FPS或兩個浮點時間相減。

| 球 | 落地原片格 | 保留格數 | 出手相對落地格數 | 出手相對秒數 |
|---|---:|---:|---:|---:|
| 001 | 110 | 335 | 9–10 | 0.150150–0.166833 |
| 002 | 129 | 321 | 8 | 0.133467 |
| 003 | 156 | 369 | 8 | 0.133467 |
| 004 | 124 | 338 | 5 | 0.083417 |
| 005 | 124 | 321 | 10–11 | 0.166833–0.183517 |

## 可解讀的差異

五球現在共用「落地」基準，可直接看各球在落地前後的模型曲線及人工出手位置。
002／003出手位置相同；001／005的人工出手區間在落地後10格相接。沒有選取區間中點。
前導膝曲線保留早段不同的姿勢變化；肘部在落地附近及之後的快速變動全部呈現，未自動認定為真實動作或錯點。
落地附近接近0°的肘XY角仍須按影像平面向量解讀，不能當作人體真實屈曲角。

## 接入與邊界

```powershell
pitch-analysis align-native-motion `
  config/analysis_inputs/ohtani_event_timing_20261025.json `
  --output analysis_results/foot_plant_alignment_NEW
```

沿用既有事件設定與來源校驗。完整reviewed GT和已有五事件完成紀錄的event-only GT均可使用。
落地必須為人工annotated的精確單格；範圍即使只有一格也不自選為精確錨點。
來源改動、跨投手、重複ID、格數不符、時間軸不符或已有輸出目錄皆拒收。
只平移時間，沒有重取樣、時間拉伸、補點、平滑、角度重算、品質篩選或跨球平均。
原骨架方式、GT、播放器、門檻及逐點unknown／usable_for_analysis=null保持。
本輪不改Phase2自動可靠性NOT PASSED及Phase3整體NOT EVALUATED的結論。

新增11項測試；完整suite共1225項，**1223 passed／0 failed／0 errors／2 skipped**，含正式五球E2E。
兩項跳過為Windows環境不支援檔案符號連結。513份受保護檔案SHA未變；1684列原欄位差異0。
完整測試與來源保護結果見[交付紀錄](dataset_selections/phase3_ohtani_foot_plant_alignment_20261025.json)。
本輪交付、commit／push後停止。
