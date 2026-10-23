# Phase3第一步：大谷五球2D投影動作曲線

2026-10-24（台灣）。使用者確認保留現有骨架模式後，授權繼續最小Phase3。
獨立分支`codex/phase3-native-motion`，Phase2 checkpoint`48ac5bc`保持可恢復。
共用人工初始化投手＋人物框連續追蹤＋RTMPose原生17點設定保持。

新增`describe-native-motion`，直接讀取已接受的原生資料入口。
五球各由實際CLI產生CSV、PNG及來源綁定JSON，共**1684格／3368個可計算2D投影角**。
沒有新增人物偵測／pose／tracking replay／GT，也沒有重建或改寫既有骨架。

| 影片 | 完整格數 | 肘可計算格 | 膝可計算格 | 缺點肘/膝 | 退化幾何肘/膝 |
|---|---:|---:|---:|---:|---:|
| supplement_001 | 335 | 335 | 335 | 0/0 | 0/0 |
| supplement_002 | 321 | 321 | 321 | 0/0 | 0/0 |
| supplement_003 | 369 | 369 | 369 | 0/0 | 0/0 |
| supplement_004 | 338 | 338 | 338 | 0/0 | 0/0 |
| supplement_005 | 321 | 321 | 321 | 0/0 | 0/0 |

「可計算」表示模型三點座標足以計算2D夾角；不是人體可見率、精確率或品質通過率。
逐點可靠性仍unknown；usable角度欄位／usable_for_analysis保持空值。
五支已人工接受的overlay維持原樣；山本現有骨架、003歷史排除及原正式素材不變。

## 看結果

`analysis_results/phase3_ohtani_native_motion_20261024_01/review_motion.html`

每球都有原overlay播放器、肘／膝曲線圖與CSV下載連結；影片與圖沒有播放連動。
`supplement_001..005/`內：`motion_curves.csv`、`motion_curves.png`、`motion_summary.json`。
CSV含來源格號與分數FPS秒數；未以出手或落地對齊。

已實看五張1400×840曲線圖，標籤、座標軸與限制說明可讀。
肘曲線部分區段有明顯突變，原樣保留；目前沒有逐點證據區分投影／定位誤差與真實動作變化。
未用平滑、插值、分數界線或移除困難格改善外觀，也未自動判定動作好壞。
[欄位、公式與限制](native_motion.md)、[凍結範圍](phase3_native_motion_scope_20261024.md)、
[版本化結果](dataset_selections/phase3_ohtani_native_motion_20261024.json)。

## 測試與交付判定

新增13項必要測試；完整suite：**1176 passed／0 failed／0 errors／2 skipped**，
共1178項，99.172秒，包含正式山本五球MediaPipe E2E。
兩項skip為Windows檔案symlink能力，既有junction測試已執行。
本輪產品與測試均無真實RTMPose／人物偵測呼叫；舊E2E沿用MediaPipe檢查。
363份受保護來源、骨架、人工紀錄及既有程式／測試在完整測試後SHA不變；
既有產品碼僅CLI增加獨立命令，舊核心／門檻／平滑／raw／GT保持。

**Phase3第一個描述性曲線交付 = COMPLETE**。
Phase2原自動可靠性仍NOT PASSED；這次是使用者接受限制後的有限前進，沒有回改Phase2判定。
本輪未建立完整投手profile、跨投手比較、事件偵測、3D或臨床解讀；未宣稱Phase3整體通過。
交付、commit／push後停止，不擴跑其他投手或自動開始下一功能。
