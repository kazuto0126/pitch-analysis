# 山本四球：保留落地範圍的曲線比較

2026-10-25（台灣）。在原精確對齊入口新增可選範圍模式，將001／004納入同投手比較。

## 已交付

四球477個來源影格，各自在CSV中保留一列。001／004各顯示兩個可能時間平移，002／005各一個；
合計六條替代路徑來自四球，沒有新增觀測、選中點、分配機率或改人工標註。

本機入口：`analysis_results/phase3_yamamoto_anchor_bounds_20261025_01/index.html`。
入口包含兩張曲線圖、資料下載及原影片觀看頁連結；原精確兩球互動頁保持。

| 球 | 人工落地 | 原點狀態 | 保留原點 | 來源格數 | 出手相對落地格數 |
|---|---|---|---|---:|---|
| 001 | 34–35 | bounded | 34、35 | 87 | 4–6 |
| 002 | 140 | exact | 140 | 175 | 1–3 |
| 004 | 65–66 | bounded | 65、66 | 114 | 4–6 |
| 005 | 55 | exact | 55 | 101 | 3–4 |

圖上虛線是同一原曲線的替代平移；實線是精確原點。放大圖只改顯示範圍，沒有更動樣本。
001／004的原點差一格，即1/30秒；這項時間不確定性保留在CSV每列的上下界。

## 計算方式

原點候選為annotated範圍`[a_min,a_max]`內的全部整數影格。對來源第i格：

```text
相對影格範圍 = [i − a_max, i − a_min]
相對秒數範圍 = 相對影格範圍 / 分數FPS
```

CSV保留原格號、原時間、模型角度、缺值狀態及空可用性欄位，另加相對界線與分數秒數。
各個候選平移只用於圖像呈現，未將同一影格複製成多筆分析資料。
出手時距沿用既有人工事件的上下界算法；005啟動與最高抬腿候選仍為uncertain。
若落地本身為uncertain／not_observable，範圍模式也保持unavailable，全部來源列仍保留、相對時間留空。

```powershell
pitch-analysis align-native-motion `
  config/analysis_inputs/yamamoto_event_timing_20261024.json `
  --retain-anchor-ranges `
  --output analysis_results/anchor_bounds_NEW
```

未加旗標時，原精確模式仍拒收範圍；單格range也不自動改為exact。
本輪未修改精確對齊頁、原播放器、骨架、門檻、GT、平滑或插值。

## 產物與驗證

輸出在`analysis_results/phase3_yamamoto_anchor_bounds_20261025_01/comparison/`：

- `bounded_curves.csv`：477列原始資料與相對時間上下界。
- `anchor_bounds_summary.json`：四球來源、候選原點與事件狀態。
- `throwing_elbow_bounds.png`／`lead_knee_bounds.png`：全部候選平移曲線與人工出手範圍。
- `report.md`：可閱讀摘要。

477列原CSV欄位逐格差異0、無重複來源列；每列分數時間上下界均已核對。兩張圖已實際檢查。
539份保護檔案SHA未變；新增10項測試，完整結果見[來源與測試紀錄](dataset_selections/phase3_yamamoto_anchor_bounds_20261025.json)。
完整suite共1243項：**1241 passed／0 failed／0 errors／2 skipped**，含正式五球E2E；
兩項跳過仍是環境不支援檔案符號連結。
啟用素材仍為001／002／004／005，003仍是歷史對照。

候選曲線不是信賴區間、機率分布或動作品質分數。數值仍為模型2D投影，逐點unknown／usable=null保持。
Phase2自動可靠性與Phase3整體結論保持；完成本輪輸出、測試、commit／push後停止。
