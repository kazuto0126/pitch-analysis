# 大谷五球：可點選的落地對齊曲線

2026-10-25（台灣）。沿用五球已接受的骨架、25筆人工事件與1684格曲線。

## 開啟與操作

在Chrome／Edge用Ctrl+O開啟：

`D:/project/pitch-analysis/analysis_results/phase3_ohtani_alignment_viewer_20261025_01/viewer/review_alignment.html`

1. 點任一球的肘／膝曲線，播放器切到該球並定位最近的原片影格。
2. 曲線重疊時，先用「supplement_00N 落地」按鈕選球，再點圖中空白處定位。
3. 「曲線範圍」可切換落地前後0.5秒與完整原片；顯示範圍不改變資料。
4. 黑色虛線為人工落地0秒，游標依目前影片影格移動；出手標記跟隨所選球，範圍保留色帶。
5. 可展開「目前影片的原片影格曲線」查看原圖；逐格、格號、滑桿及觀看速度沿用既有播放器。

跨球切換時，等待載入來源與目標影片一致後才跳格。播放器仍明示要求影格與實際呈現影格，
不支援畫格回呼時標示為時間估計；曲線頁亦保留這項區分。
點選超出某球原片範圍的時間不會被默默夾到首格或末格。

## 接入

```powershell
pitch-analysis review-native-motion-alignment `
  config/analysis_inputs/ohtani_event_timing_20261025.json `
  --output analysis_results/alignment_viewer_NEW
```

輸出新HTML、原播放器JS、新增曲線互動JS與來源manifest；不覆寫先前頁面或分析結果。
原`native_motion_viewer.js`逐bytes保持，只新增對齊圖、來源影格映射與跳格協調。
原片時間與格號不改，圖上時間仍為`(frame_index − foot_plant_frame) / 分數FPS`。
所有來源校驗沿用既有事件讀取器，落地必須是人工精確單格。

## 資料與測試

五球1684列原始時間／角度／狀態完整保留；缺值斷線，出手範圍不選中點。
全部來源格的時間往返映射已核對，曲線沒有重取樣、平滑、插值、評分或角度重算。
模型、追蹤、門檻、人工GT與既有骨架方式保持；逐點可靠性unknown、usable_for_analysis=null。
新增Python封裝與來源測試、純Node時間映射及跳格狀態測試。
完整Python suite共1233項：**1231 passed／0 failed／0 errors／2 skipped**，含正式五球E2E。
兩項跳過仍為環境不支援檔案符號連結；新增Node5項、原播放器5項及事件helper18項斷言通過。
521份保護檔案SHA保持不變。
完整結果與產物SHA見[交付紀錄](dataset_selections/phase3_ohtani_alignment_viewer_20261025.json)。

本輪未執行瀏覽器／DOM自動操作，實際播放與點曲線互動仍待使用者開啟確認。
數值／封裝測試不作為真實瀏覽器互動通過的證明；沒有新增人工接受紀錄或改變Phase整體狀態。

交付後commit／push並停止。
