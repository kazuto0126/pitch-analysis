# 可攜式投球動作成果包

2026-10-26（台灣）。將既有成果整理為可離線觀看的資料夾與ZIP，沒有新增模型、分析或人工標註。

## 下載與開啟

ZIP：`analysis_results/phase3_portable_review_20261026_01/pitch_motion_review_20261026_01.zip`

大小33,976,990 bytes，約32.4 MiB。**請先完整解壓縮**，保留資料夾結構，
再以Chrome／Edge開啟`pitch_motion_review_20261026_01/START_HERE.html`。
只需瀏覽器，無須安裝Python、專案程式或模型。

本機未壓縮入口：

`analysis_results/phase3_portable_review_20261026_01/pitch_motion_review_20261026_01/START_HERE.html`

## 包含的成果

9支影片、2161格：大谷5支1684格，山本啟用4支477格。山本003維持歷史對照，不納入。
兩位投手分別查看，沒有跨投手分數或排名。
大谷五球仍維持候選素材身分；打包不會提升素材身分或取代山本正式素材。

- 9支原始MP4、9支既有overlay及對應metadata，保留原檔名與內容。
- 已保存的原生keypoints、native manifest、subject track、骨架接受紀錄。
- 9份原曲線CSV／PNG、原人工GT；大谷5份事件完成checkpoint一併保留。
- 大谷五球對齊頁／事件頁，山本兩球精確對齊頁／四球事件頁，共4份觀看頁副本。
- 大谷對齊圖、山本四球落地範圍圖，以及大谷5張事件原片／骨架對照圖。
- `README.md`及`bundle_manifest.json`，記錄包內位置、來源path／SHA與副本種類。

原GT、CSV與raw prediction逐bytes複製。JSON內的原專案路徑保留作證據，
可透過manifest找到包內相同SHA的副本；此包是成果觀看／資料查核副本，不包含推論環境或模型權重。

## 頁面與標註範圍

觀看頁只改副本中的`clips[].overlay_url`，指向包內相同MP4；原JS逐bytes保持。
頁面內原時間、角度、事件與來源資訊均保留。包裝不產生新頁人工接受紀錄。

大谷GT仍為in_progress，只完成五事件，其他未覆核欄位保持原值。
山本舊GT雖為reviewed，其舊關節品質標記不能套用到新骨架；本包使用其既有事件。
山本001／004落地範圍及005其他uncertain候選不變。

## 檢查與保存

136個檔案；79個HTML／影片本機連結都指向包內有效檔案。來源SHA、包內副本、ZIP CRC、
ZIP路徑與唯一性檢查完成，沒有改動原始成果。
獨立唯讀核對亦通過：135份manifest列出的檔案、133份來源SHA、ZIP內136檔全部相符，
四頁只修改16個overlay_url，6份JS保持；沒有危險路徑、重複檔或漏檔。
無產品／測試碼變更，未重跑完整suite；相同程式碼最近1241 passed／0 failed／2 skipped。
本輪未做瀏覽器／DOM操作，新包實際播放及人工接受尚未確認。

[交付紀錄與ZIP SHA](dataset_selections/phase3_portable_review_20261026.json)。
ZIP保存在本機；Git提交保存設定與交付說明，沒有將ZIP自動上傳GitHub release。
Phase2自動可靠性仍NOT PASSED，Phase3整體NOT EVALUATED。
