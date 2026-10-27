# 兩位投手的完整模型曲線並列回看

更新：2026-10-27（台灣）。此入口把兩組已保存的肘／膝模型XY曲線放在相同秒數與角度顯示刻度，
保留人工落地範圍的每個候選平移，並將SVG中的原始樣本連回自己的影片格號。

## 使用

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe review-native-cohort-curves analysis_results/phase3_native_motion_delivery_20261027_01/ohtani/events/event_comparison.json analysis_results/phase3_native_motion_delivery_20261027_01/yamamoto/events/event_comparison.json --output analysis_results/my_cohort_curve_review
```

需要兩位不同投手的既有事件報告，依參數順序定義A／B。原讀取器會核對各自的request、
曲線、人工事件與來源SHA；輸出須為新的`analysis_results/`子目錄，不覆寫已有結果。
單投手入口保持，這份圖版也不修改原事件或模型輸出。

本機[兩投手並列圖版](../analysis_results/phase3_cohort_curve_review_20261027_01/review/report.html)。

## 如何看圖

每個關節各有一張四面板圖：上排A、下排B；左欄完整來源時間軸，右欄落地前後0.5秒顯示放大。
兩位投手的左欄共用同一完整x範圍，右欄共用−0.5至+0.5秒；兩關節所有面板皆為0–180°。
完整曲線、原格號與缺值保留，沒有跨球平均或時間拉伸。

1. 先按圖例球號辨認各條曲線；虛線是同一球的替代落地原點。
2. 點彩色樣本圓點，在新分頁回看該球原影格／曲線。SVG提示保留球號、原點候選、格號與原讀值。
3. 曲線重疊時可能只能點到上層樣本；請在播放器確認球號，或由下方表格開指定球。
4. 也可直接開SVG、下載PNG，或下載每來源影格一列的CSV。

HTML以`object`嵌入SVG，保留點位連結；PNG是同一資料的靜態圖。送出跳格要求不代表目標格已呈現，
實際格號以原播放器讀值為準。實際瀏覽器播放尚未覆核。

## 人工原點與原始時間

對每個已確認落地候選`o`，只作顯示時間平移：

```text
相對時間 = (frame_index − o) / 原分數FPS
```

精確事件只有一個原點；已確認範圍保留每個整數候選，不取中點。
單格range仍記為bounded，不升成exact。uncertain／不可觀測落地不提供原點、不畫對齊曲線，
但原片、原始座標與CSV影格仍保留。若全部原點未定或時間域只有一點，±0.5秒只作空圖／單點顯示範圍，不是推測事件。

CSV每來源影格只存一列，附相對時間的上下界與精確分數；替代平移不增加來源分母。
例如山本001落地為34–35格，同一第40格的相對時間為1/6至1/5秒；圖中兩條替代平移都指回同一原片40格。

## 本批與產物

大谷5球1684格，60000/1001 FPS；山本啟用4球477格，30/1 FPS。共9球2161個來源影格。
落地原點為7個exact影片、2個bounded影片，共11個候選顯示原點；不是11球或新增觀測。
山本003仍排除，其他未確認事件保持原狀。

| 檔案 | 內容 |
|---|---|
| `report.html` | 兩關節並列圖、原點狀態表與原片入口 |
| `throwing_elbow.svg`／`lead_knee.svg` | 全部合法原點的曲線與可點樣本；每點綁定自己的cohort、球號、原點及原格 |
| 同名`.png` | 同一資料的靜態圖，方便匯出 |
| `cohort_curves.csv` | 原樣本、缺值、原分數FPS與相對時間界線；每來源影格一列 |
| `cohort_curves.json` | 兩組來源、事件原狀、原點、共享圖軸與產物SHA |
| `source_a_###.html`／`source_b_###.html` | 原影格播放器；原播放JS與跳格adapter保持 |

## 解讀範圍

0秒一致只表示各自人工落地候選對齊。模型XY角受攝影投影與定位影響，不能直接當成解剖角度或真正動作差異。
片頭／片尾長短可能來自剪輯，不表示準備或收尾階段長短；階段時距仍讀原人工事件。
替代平移不是額外觀測、機率分布或信賴區間。缺值保持斷線，不補點、不平滑、不依分數刪除樣本。

這是完整曲線的並列回看，沒有相似度、DTW、品質分數、排名或正式reference比較。
逐點可靠性仍unknown、usable_for_analysis仍null，不修改pose／tracking、門檻、raw prediction或人工GT，
也不改變Phase 2自動可靠性與Phase 3整體驗收狀態。

## 驗證

新增10項測試，涵蓋分數時間、exact／全部bounded原點、unknown／單點顯示域、跨投手同名球號、
缺口保留、CSV不倍增、PNG／SVG共享軸、來源／原播放器不變，以及SVG樣本URL與metadata。
完整Python suite1343項：初跑1333 passed／0 failed／10 skipped，八項junction案例補跑全過；
不重複計為**1341 passed／0 failed／2 skipped**，含正式五球E2E。
兩項跳過仍為Windows檔案符號連結能力限制；原JS未更動，未重跑相同Node suite，最近仍23項通過。

實際CSV共2161列唯一來源影格，角度／狀態與來源逐值一致；兩圖各2843個樣本連結（含顯示放大與替代平移），
共5686個均綁定正確側別、球號、候選原點及範圍內原格號。兩張PNG已檢視圖軸／標籤與渲染，未新增姿態真值判讀。
完整時間顯示域為`−14/3`至`7007/1875`秒，兩位投手及兩關節保持一致。
[交付、來源與完整測試紀錄](dataset_selections/phase3_cohort_curve_review_20261027.json)。
