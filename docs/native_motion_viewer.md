# 影片與2D曲線連動觀看

這是Phase3第一步曲線交付後的觀看工具。它只讀既有`motion_summary.json`／CSV與原overlay，
不重算角度、不執行骨架推論、不寫人工標註。

```powershell
pitch-analysis review-native-motion `
  analysis_results/phase3_ohtani_native_motion_20261024_01/supplement_001 `
  analysis_results/phase3_ohtani_native_motion_20261024_01/supplement_002 `
  --output analysis_results/native_motion_viewer_NEW
```

可提供同一投手的多支既有輸出。新目錄包括`review_motion.html`、`motion_viewer.js`及
來源／產物SHA的`motion_viewer_manifest.json`。保留原專案目錄的相對位置，即可在本機瀏覽器開啟。
沒有外部JS、網路資料請求、登入或資料上傳。

## 操作

1. 選擇影片。播放器與兩條曲線使用同一支來源。
2. 播放時，游標和肘／膝角度跟隨播放器；影格從0起算。
3. 暫停後可按上一格／下一格，或用←／→。
4. 可拖滑桿、輸入格號按「前往」，或點擊曲線跳到該格。
5. 0.5×／0.25×僅改變觀看速度，原資料與原始FPS不變。

藍色為投球肘，橘色為前導膝。缺點或退化幾何處維持斷線與空值，不補點。
影片載入中或失敗時，逐格控制會停用；仍可改選其他影片。

## 同步語義

支援`requestVideoFrameCallback`時，畫格索引取播放器**實際呈現畫格**的`mediaTime×分數FPS`四捨五入。
來源與overlay先前已驗證為0起算固定FPS；不平移容器起點，也不對齊出手／落地事件。

要求第i格時，以`(i+0.25)/fps`定位到該格的時間區間內並暫停，降低時間邊界四捨五入問題。
UI會區分「要求的目標格」與「目前實際呈現格」，等待回呼後才將兩者視為同步。
不支援畫格回呼時，使用`currentTime×fps`向下取整的**時間估計**，頁面會明示。
實際畫格回呼與fallback估計都不是新的品質或身份判定。

## 邊界與檢查

建頁前核對原生資料接受紀錄、來源、CSV／PNG SHA、完整影格、分數時間、角度狀態與分母。
只接受一位投手，重複pitch_id與來源不符會拒絕；輸出不覆寫既有資料。
畫面中的2D角度仍是模型XY投影，逐點可靠性unknown、usable角度空值。

本輪完成Python來源／CSV檢查及純Node時間換算測試。
瀏覽器工具的安全政策拒絕`file://`頁面觀察，且禁止繞過；因此未做真實瀏覽器／DOM播放驗證。
原交付的`browser_interaction_verified=false`快照保留；測試本身沒有被當作真實播放的證明。

2026-10-24後續：HSU在本機開啟後回覆「都正確尤其是5最完美」，
五球觀看頁已獲人工整體接受，005記為偏好示範。接受紀錄綁定當時頁面／JS／輸出SHA，
保存於`annotations/motion_reviews/HSU_20261024/ohtani_motion_sync_acceptance.json`。
這是人工操作接受，沒有逐控制項量測日誌，也沒有增加逐點GT或改變角度可靠性。

## 目前已產生的觀看頁

| 投手 | 影片 | 來源格數 | 人工觀看頁確認 | 本機HTML |
|---|---|---:|---|---|
| 大谷 | supplement_001–005 | 1684 | HSU已整體接受5/5 | `analysis_results/phase3_motion_sync_20261024_01/viewer/review_motion.html` |
| 山本 | pitch_001／002／004／005 | 477 | HSU已整體接受4/4 | `analysis_results/phase3_yamamoto_native_motion_20261024_01/viewer/review_motion.html` |

在Chrome或Edge按`Ctrl+O`選取對應HTML。山本003維持歷史對照，不在啟用觀看頁中。
兩頁分別只含一位投手，沒有事件對齊或跨投手比較；兩者沿用同一套既有程式與骨架模式。

HSU確認山本「都正確一樣是5表現最好」，pitch_005亦記為偏好示範。
接受證據另存`annotations/motion_reviews/HSU_20261024/yamamoto_motion_sync_acceptance.json`；
原pending／自動瀏覽器未驗證快照保持，沒有因此建立逐點精度或更動原始資料。

## 多球落地對齊曲線的回看

`review-native-motion-alignment`可沿用已完成事件設定，建立可點選的多球對齊圖。
點曲線會選擇該球最近原格；跨球載入後才跳格，仍由本頁相同的播放器確認呈現狀態。
原播放器資產與單球時間軸保持，新功能只加對齊圖和跳格接點。
見[大谷五球可點選對照頁](phase3_ohtani_alignment_viewer_20261025.md)。
