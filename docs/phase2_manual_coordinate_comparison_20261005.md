# Phase 2 — pitch_003 人工座標比較

覆核完成：2026-10-05 10:14（台灣 UTC+08:00）；資料整理：2026-10-06。

**人工座標參考 = REVIEWED；Phase 2 = IN PROGRESS。**

## 來源與範圍

Tsai 於2026-10-04手動放置原片的12個身體關節；HSU逐格確認可見性及點位，並提供完成時間原話「2026/10/5 10.14」。
正式時間為 `2026-10-05T02:14:00Z`；原答案精度是分鐘，00秒僅為格式填位。Codex僅轉錄與驗證。

正式參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_42/pitch_003/manual_keypoints.json`。
115格（0–114）、原圖510 × 628；全部1,380個關節影格狀態已覆核：1,205可見且對位、173不可觀測、2不確定、0未覆核。
85–86左腕保留不確定；第65格左踝不可觀測。175個非可見點座標留空、排除位置誤差。confidence保持null，沒有假設人工標點沒有誤差。

比較的是既有 `keypoints.json` 的raw 2D座標；原影片與prediction不覆寫，沒有新模型推論、訓練或演算法修改。

## 十二關節結果

誤差為原始影像pixels；不以這次數值建立新驗收門檻。中位數與P95只計可見人工點，P95表示約95%的這批誤差不高於該值。

| 關節 | 可見人工格 | 有raw座標 | raw漏點 | 平均誤差px | 中位數px | P95 px | 最大px |
|---|---:|---:|---:|---:|---:|---:|---:|
| 左肩 | 115 | 115 | 0 | 23.32 | 10.94 | 108.89 | 145.54 |
| 右肩／投球肩 | 106 | 106 | 0 | 20.74 | 7.47 | 124.66 | 147.37 |
| 左肘 | 83 | 83 | 0 | 36.14 | 15.21 | 132.14 | 150.69 |
| 右肘／投球肘 | 93 | 93 | 0 | 27.50 | 10.55 | 106.19 | 166.56 |
| 左腕 | 61 | 61 | 0 | 44.57 | 21.75 | 136.76 | 252.37 |
| 右腕／投球腕 | 58 | 58 | 0 | 26.66 | 14.39 | 84.57 | 108.07 |
| 左髖／前導髖 | 115 | 115 | 0 | 19.63 | 10.54 | 94.33 | 114.32 |
| 右髖 | 115 | 115 | 0 | 18.10 | 8.00 | 86.09 | 118.73 |
| 左膝／前導膝 | 115 | 115 | 0 | 15.61 | 7.61 | 77.82 | 109.27 |
| 右膝 | 115 | 115 | 0 | 14.36 | 7.57 | 66.37 | 85.19 |
| 左踝／前導踝 | 114 | 114 | 0 | 19.89 | 9.86 | 107.70 | 128.58 |
| 右踝 | 115 | 115 | 0 | 17.48 | 10.16 | 72.44 | 120.41 |

**raw座標存在不代表是可信的observed點。** 此評估器沿用既有raw presence規則，不加入visibility gate；1,205點都有raw座標、raw漏點0，並不表示overlay每格都畫出可信關節。
overlay與processed observed／interpolated／missing另受既有confidence gate影響。MediaPipe官方將visibility定義為可見／遮擋分數，未將它定義為位置正確率。參見[官方Landmark文件](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/components/containers/Landmark)。

## 人工指出的整體偏移

87–104沿用HSU既有重大pose failure區段；下表按可見關節影格計算，不是逐格等權總分，也不建立主觀排名。

| 影格區段 | 可比較關節影格 | 平均px | 中位數px | 最大px |
|---|---:|---:|---:|---:|
| 0–86 | 895 | 11.67 | 8.23 | 108.07 |
| 87–104 | 190 | 76.90 | 78.57 | 166.56 |
| 105–114 | 120 | 14.27 | 9.45 | 252.37 |

87–104的平均誤差76.90px，相較0–86的11.67px，提供與HSU先前整體偏移觀察一致的量化證據。
第95格右肩visibility約0.9996，仍偏離人工點147.37px；第112格左腕visibility約0.9927，偏離252.37px。
因此高visibility或有座標不能單獨作為位置正確的依據。105–114整體平均下降，但左腕仍有大誤差，不宣稱所有關節都恢復。

## 被遮住的人工座標

人工推估遮擋關節可提供姿勢假設或之後有明確政策的輔助資料，但其不確定性需保留；AI與推估座標接近只能表示與人工推估一致。
[COCO官方格式](https://github.com/cocodataset/cocodataset.github.io/blob/master/dataset/format-data.htm)區分「已標註但不可見」與「已標註且可見」，說明遮擋標點可以保存，但可見性需另記。
本專案既有manual-keypoints-v1用於可觀測2D位置驗證，故維持非可見座標null；同學原始1,380組X/Y完整保存在本機原始回傳ZIP/XML，未刪除。
本次未擴充schema、未把遮擋推估混入這份位置誤差基準。若之後要讓分析使用人工推估，需另定用途、來源與不確定性規則，並分別評估。

## 證據檢查與限制

- manual-keypoints-v1 reviewed與來源MP4 SHA驗證通過；reviewer為HSU。
- 與第41版相比，只變更完成狀態／時間及notes，全部frames、XY、可見性、confidence與來源欄位相同。
- 1,205組距離及各關節平均值以獨立計算重核；raw漏點0、排除非可見175點，沒有把漏點算成零誤差。
- 原canonical五支GT、歷史checkpoint、原影片、Tsai來源與原prediction全部hash保持不變。
- 新補充 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_44/pitch_003/ground_truth.json` 僅追加完成時間notes；其自身仍in_progress，不把座標完成時間套給其他覆核。
- 單支單視角、單一人工座標版本；沒有重複標點誤差／獨立reviewer一致性或真實3D驗證。
- 本次不衡量事件偵測精度，baseline也未自動預測五個事件；HSU補充13／46／65／69／99與canonical12／47／66／69／99分開保留。
- 本次只執行資料、來源及計算檢查，未重跑完整test suite；既有147 passed／0 failed／1 skipped是先前紀錄。

## 輸出與後續

本機輸出：`analysis_results/phase2_manual_coordinate_comparison_20261005_01/`。
包含 `manual_keypoints_evaluation.json`、`evaluation_summary.json`、`regional_diagnostics.json`、`evidence_integrity_check.json`。
原始JSON與媒體保持本機；此摘要、正式座標sidecar及人工作業來源納入Git。

下一步聚焦既有警示漏掉的87–104整體偏移及局部腕／肘錯位，先提出可靠性修正與回歸驗證方案。
本次沒有修改pose／tracking演算法或門檻，不自動訓練、不開始Phase 3；同學pitch_005事件補充仍待回傳。
MLB Pitch Clipper正式接入仍待Phase 2穩定且以證據驗收後，再依既定順序執行，不擴增投手。
