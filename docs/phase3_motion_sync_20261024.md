# Phase3：大谷影片與曲線連動頁

2026-10-24後續人工確認：HSU在本機開啟後回覆「都正確尤其是5最完美」。
目前狀態為**HUMAN ACCEPTED：5/5**，005記為使用者偏好的示範樣本。
原話、reviewer、時間及頁面／JS／五球來源SHA已另存，
見[人工接受證據](dataset_selections/phase3_motion_sync_acceptance_20261024.json)。
此確認是整體觀看體驗與五球結果的人工接受，不是逐點精度GT或逐控制項測試日誌。
本次無程式碼變更，沒有重跑模型或測試；下文保留原始交付與自動檢查限制。

2026-10-24（台灣）。使用者要求繼續後，本輪將前一輪大谷五球曲線與已接受的overlay連動。
只讀既有角度CSV、來源摘要及影片；共5球1684格，角度重算／骨架推論／tracking replay／GT皆0。
大谷與山本的共用骨架模式保持。

## 使用方式

開啟：`analysis_results/phase3_motion_sync_20261024_01/viewer/review_motion.html`。

- 播放時同步游標、來源格號、秒數與肘／膝角度。
- 暫停後用上一格／下一格、左右鍵、滑桿、格號前往或點曲線跳轉。
- 選擇不同球；0.5×／0.25×只改觀看速度。
- 缺點／退化角度維持空值與斷線，原2D曲線數值不改。

支援畫格回呼時，以實際呈現的mediaTime推回來源格號；要求跳轉的目標格另列，
等待畫面回報後才視為同步。不支援回呼則明示「時間估計」。
沒有投球事件標記、事件對齊、評分或新標註介面。
[完整操作與同步定義](native_motion_viewer.md)。

## 本輪驗證

新增6項Python測試，完整suite：**1182 passed／0 failed／0 errors／2 skipped**，
共1184項，130.406秒；含正式山本五球MediaPipe E2E。
兩skip為Windows檔案symlink能力；既有junction測試已執行。
另5項純Node時間換算測試：**5 passed／0 failed**，涵蓋分數FPS、首尾邊界、
要求時間位於目標格內，以及實際呈現PTS與fallback估計的不同取整方式。

來源／CSV SHA、完整影格及時間、缺值狀態、同投手限制與fresh輸出皆有檢查。
新頁面使用的JS與版本化原始碼SHA一致。
379份原資料、既有曲線圖／CSV／頁面與人工紀錄在完整測試後SHA不變。
既有產品碼只有CLI新增命令，另補package-data讓JS隨安裝保存；舊核心／門檻／raw／GT保持。

## 原交付時的檢查限制與後續人工接受

瀏覽器工具的安全政策拒絕file://頁面觀察，並明確禁止繞過。
本輪沒有改用其他瀏覽器途徑、headless browser或替代介面規避此限制。
交付當時已完成靜態審查與來源／時間邏輯測試，實際操作尚待人工確認，
因此原manifest保留`browser_interaction_verified=false`、原結果保留CODE COMPLETE／UI REVIEW PENDING快照。
後續HSU已完成人工整體接受5/5；工具自動檢查仍未執行，獨立人工接受紀錄補上最新狀態。

本次接受沒有更改頁面、骨架、曲線或參數；005作為示範不形成投手排名或新品質規則。
Phase2原自動可靠性仍NOT PASSED；2D投影與unknown/null限制保持，未宣稱Phase3整體通過。
本輪commit／push後停止，不新增功能。
