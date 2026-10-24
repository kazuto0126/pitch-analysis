# Phase3：山本四支啟用影片的2D曲線與連動頁

2026-10-24後續人工確認：HSU回覆「都正確一樣是5表現最好」。
**目前人工整體接受4/4**，pitch_005記為使用者偏好的示範。
原話、reviewer、紀錄時間及頁面／JS／四支曲線與overlay SHA已另存
`annotations/motion_reviews/HSU_20261024/yamamoto_motion_sync_acceptance.json`。
[最新接受狀態](dataset_selections/phase3_yamamoto_motion_acceptance_20261024.json)。
原始交付pending快照保留；本次只保存人工覆核與文件，沒有改骨架、曲線或程式，也未重跑模型／測試。

2026-10-24（台灣）。依使用者「繼續呢」，將既有動作曲線與觀看工具套用到
山本目前啟用的001／002／004／005，直接沿用已接受的原生17點骨架。
003維持歷史診斷對照，不納入本輪，也不恢復正式使用。

## 本輪交付

| 影片 | 完整影格數 | 投球肘可計算角度 | 前導膝可計算角度 | 缺值／退化角度 |
|---|---:|---:|---:|---:|
| pitch_001 | 87 | 87 | 87 | 0／0 |
| pitch_002 | 175 | 175 | 175 | 0／0 |
| pitch_004 | 114 | 114 | 114 | 0／0 |
| pitch_005 | 101 | 101 | 101 | 0／0 |
| 合計 | 477 | 477 | 477 | 0／0 |

四支皆30/1 FPS，保留原圖像素長寬比例，時間為`frame_index / fps_fraction`。
共954個模型XY投影角；各支提供CSV、PNG、來源SHA摘要，另有四支影片共用的連動頁。
模型有座標即可計算角度，不代表關節可見、精確或已通過逐點可靠性驗證。

來源設定：`config/analysis_inputs/yamamoto_active_seeded_20261024.json`。
來源資料入口：`analysis_results/phase2_active_cohort_closeout_20261024_01/bundles/`。
來源骨架接受紀錄：
`annotations/skeleton_reviews/HSU_20261024/yamamoto_active_skeleton_acceptance.json`。

## 開啟與操作

在Chrome或Edge按`Ctrl+O`，選擇：

```text
D:\project\pitch-analysis\analysis_results\phase3_yamamoto_native_motion_20261024_01\viewer\review_motion.html
```

選擇影片後可播放、逐格、輸入格號、拖滑桿或點曲線回看。
藍線為投球肘、橘線為前導膝；觀看速度只影響播放。
保留專案與原overlay的相對目錄位置，單獨複製HTML不會包含影片。
[完整操作與同步定義](native_motion_viewer.md)。

四支原骨架已獲HSU整片接受；新觀看頁交付時待確認，後續亦獲HSU人工整體接受4/4。
大谷連動頁先前的人工接受5/5保留，沒有重跑或改動該結果。

## 實際執行與檢查

- 四支各執行一次既有`describe-native-motion`，再以`review-native-motion`建立觀看頁。
- CLI已核對來源／接受紀錄SHA、完整格號、分數時間、角度狀態與分母；四支全部成功。
- 415份受保護來源、原始資料、人工紀錄、既有結果與產品／測試碼SHA變更0。
- 人物偵測、pose推論、tracking replay、新GT皆0；產品／測試碼變更0。
- 實看四張PNG，標題與座標軸完整可讀；肘角局部突變原樣保留，未平滑、補點或排除。
- 本輪僅既有程式的資料重用與文件更新，未重跑完整suite。同程式碼最近完整結果為
  **1182 passed／0 failed／0 errors／2 skipped**（1184項、130.406秒，含正式五球E2E）；
  另5項純Node時間換算測試全過。兩skip為Windows檔案symlink建立能力不足。

既有測試證據：`analysis_results/phase3_motion_sync_20261024_01/verified_suite/test_results.json`。
瀏覽器工具拒絕file://頁面觀察且禁止繞過，沒有執行自動瀏覽器互動驗證；
`browser_interaction_verified=false`保留。PNG檢查及CLI成功不視為實際播放驗證。

## 限制與狀態

角度是2D模型投影，沒有事件對齊、跨投手比較、評分或真實3D生物力學推論。
`pointwise_reliability=unknown`、`usable_deg`與`usable_for_analysis=null`保持。
被遮住的關節可能仍有模型座標；本輪沒有新增可見性或精度GT。

**本輪曲線／觀看頁生成完成；Phase2自動可靠性仍NOT PASSED；Phase3整體NOT EVALUATED。**

後續人工接受沒有變成逐點精度GT、逐控制項測試日誌或新的通過標準。
005作為偏好示範不構成量化排名，沒有因此調整其他影片、參數或門檻。

輸出根目錄：`analysis_results/phase3_yamamoto_native_motion_20261024_01/`。
[版本化結果與來源SHA](dataset_selections/phase3_yamamoto_native_motion_20261024.json)。
本輪提交與推送後停止，不自動新增功能。
