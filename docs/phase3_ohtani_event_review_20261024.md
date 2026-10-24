# 大谷五球：只確認投球事件

2026-10-24（台灣）。依「繼續」準備人工事件覆核，順序005→001→002→003→004。
沿用已接受的原片／骨架／曲線，這次不重標骨架，不自動推測事件。

## 最新人工進度：001／005五事件完成，2/5

| 事件 | 001確認影格 | 005確認影格 |
|---|---|---|
| 啟動開始 | 28 | 81–82 |
| 最高抬腿 | 59 | 96–99 |
| 前腳落地 | 110 | 124 |
| 大致出手 | 119–120 | 134–135 |
| 收尾結束 | 160 | 169 |

這些是HSU看過原片連續影格後的回答；概覽候選88／176已依後續回答修正，保留原話與歷程。
001概覽啟動候選32改為28；收尾160經連續影格確認，確認原文「對]」保留於checkpoint。
格式、來源與時間順序檢查通過；範圍不取中點、confidence不猜填。
001／005仍為in_progress、完成時間null，其他人工欄位未填；這是五事件完成，不是完整pose GT完成。
獨立workflow checkpoint只綁定事件範圍、reviewer與目前GT SHA，事件值仍保存在同一ground-truth-v1。
[最新進度與來源](dataset_selections/phase3_ohtani_event_review_progress_20261024.json)。

下一支002已提供321格圖片、27張連續格表與三張概覽，位於同一helper目錄的`supplement_002/`。
其餘002／003／004的GT事件仍全null；不替人工填判斷。

## 先看005

原片固定觀看裁切：先前已確認的`[192,216,768,720]`，僅方便放大，未改動MP4。
完整原片仍可從圖表頁連結開啟；已接受的骨架播放器也保持原樣。

- 逐格圖片頁：`analysis_results/phase3_ohtani_event_review_20261024_01/supplement_005/review_frames.html`。
- 概覽分成000–120、128–248、256–320三張，每8格取一張，只用來定位。
- 精確判斷改看`contact_sheets/`的連續12格，或`frames/`內單格原尺寸圖片。
- 321格全部保留，格號0–320；FPS為60000/1001，時間=格號／分數FPS，第0格=0秒。
- 可直接在對話提供格號／範圍與備註，由Codex照你的原話轉錄。

## 只需要確認五件事

| 事件 | 判讀方式 |
|---|---|
| 啟動開始 | 站定後開始連續投球動作的邊界；片頭已開始則保留不可觀測／不確定 |
| 最高抬腿 | 左膝的最高位置；停留一段時可標範圍 |
| 前腳落地 | 左腳第一次接觸地面的邊界 |
| 大致出手 | 球最後在手與首次離手之間；可跨兩格以上，不強迫單一答案 |
| 收尾結束 | 完整follow-through後恢復平衡的邊界 |

看不清時保留uncertain或not_observable，不能以模型標點／曲線峰值／供片能量anchors替代人工判斷。
概覽每8格的圖片不是精確事件答案；先找區段，再看連續格。
啟動界線沿用你先前採用的開始抬前導左腳；先由你找大致區段，再以連續影格確認。

## 五份實際模板

共同目錄：`annotations/event_reviews/HSU_20261024/shohei_ohtani/`。

| 影片 | 模板 | 完整影格數 |
|---|---|---:|
| supplement_001 | supplement_001/ground_truth.json | 335 |
| supplement_002 | supplement_002/ground_truth.json | 321 |
| supplement_003 | supplement_003/ground_truth.json | 369 |
| supplement_004 | supplement_004/ground_truth.json | 338 |
| supplement_005 | supplement_005/ground_truth.json | 321 |

五份均沿用ground-truth-v1，來源SHA／檔名／格數已綁定；準備時全為unreviewed，
所有人工欄位、reviewer與完成時間皆null。後續005進度見上方最新checkpoint。
第一筆人工回答後改為in_progress，填實際reviewer；尚未完成整份GT時，完成時間仍null。

**五個事件完成不等於完整pose GT完成。** 未覆核的身份、identity switch、pose failure、
逐關節可靠性欄位保持null，不以空陣列假稱「沒有問題」，也不沿用整片骨架接受來補填。
目前事件比較入口要求整份reviewed；事件收集完成後，再處理限定事件覆核範圍的接入。
本輪不修改schema／validator或產品碼，不為讓資料通過而假填其他欄位。

## 準備結果與限制

五支原片實際解碼335／321／369／338／321格，共1684格，與既有來源一致。
005提供321張固定裁切、27張連續影格表；後續已補001的335張／28張格表及002的321張／27張格表，003–004僅模板。
504份既有資料／程式／測試檔SHA保持；新模型、tracking replay、新人工判斷皆0。
本輪只有資料與文件，未重跑suite；相同程式碼最近1201 passed／0 failed／2 skipped。
圖檔已檢查格號與文字可讀；未執行自動瀏覽器互動驗證。

[來源與準備紀錄](dataset_selections/phase3_ohtani_event_review_20261024.json)。
Phase2自動可靠性仍NOT PASSED；Phase3整體NOT EVALUATED。
下一步等待人工對002的事件回答，不自行標註或開始下一功能。
