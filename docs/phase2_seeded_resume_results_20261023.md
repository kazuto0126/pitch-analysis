# 人工初始化追蹤：106格續跑完成

2026-10-23（台灣）。[本次範圍](phase2_seeded_resume_20261023.md)、
[版本化數字／SHA](dataset_selections/ohtani_seeded_resume_results_20261023.json)、
[前次中斷紀錄](phase2_seeded_native_track_results_20261021.md)。

**本次續跑 = COMPLETED；321格原生座標已齊；未正式採用；Phase 2 自動可靠性仍 NOT PASSED。**

使用者在前次中斷結果後要求「繼續」。已完成同一球尚未執行的106格，
維持原初始化框、固定關聯結果、模型及319次新pose總額度。

## 實際完成內容

| 項目 | 結果 |
|---|---:|
| 影片 | 大谷`supplement_002`，321格 |
| 原尺寸／FPS | 1280×720／60000/1001 |
| 原樣保留的前段 | 第0–214格，共215格，逐值0變更 |
| 本次新pose | 第215–320格，106嘗試／106完成 |
| 新detector／新追蹤replay | 0／0 |
| 兩段合計新pose | 213＋106＝319次 |
| 另列原人物框pose重用 | 193、194格，共2格 |
| 合併後有原生座標 | 321／321格 |
| 未執行／整格missing | 0／0 |
| 本次失敗／模型重試／warmup | 0／0／0 |

本次執行17秒左右，完整時間見receipt；原321格框關聯沒有重跑。
續跑前核對舊213次started/completed逐一配對、binary SHA、partial及完整source refs，
沒有結果不明的已嘗試呼叫。執行時逐格核對原像素與分數FPS時間，
前215格只重新計算零推論的取樣幾何及213份舊input SHA；沒有重新推論。

投球肩／肘／腕、前導髖／膝／踝的座標可用影格數各由215增至321，
最長整格missing由106降至0；新增106格全是前次I/O中斷後未執行的尾段。
**這些數字描述座標完整度，不是關節準確率、人工可見性或正式gate的raw coverage。**

## 執行紀錄修復與保存

本次另建續跑設定／claim／worker／journal／輸出，原claim、running receipt、
暫存receipt、partial、binary及先前overlay全部保留。
不是刪claim重跑舊入口，也沒有把原失敗紀錄改寫為成功。

新增`native_progress_log.py`：每筆事件獨立序號JSON，exclusive create、flush/fsync；
不替換已有snapshot、不使用固定.tmp。讀取者開著舊進度檔仍可寫下一筆。
錯誤紀錄若也失敗，保留最初例外。本次108筆紀錄（開始＋106格＋完成）完整，
最後只建立一次`run_receipt.json`，沒有再遇前次WinError5。
前次Windows鎖定根因仍未確認；本修復移除了新段對同一進度檔反覆replace的路徑。

## 實際overlay抽查

已看7張contact sheet、25組原片／舊固定crop／合併結果，
包括原20固定格、193／194、續跑交界214／215／216。

- 0／19／38／56／75格保留先前改善：手臂線位於投手／手套附近，未延伸到打者。
- 214／215／216格均有投手附近骨架，抽樣未見續跑交界空白或整副骨架跳到打者。
- 原未執行的226／245／264／282／301／320格現在已有投手附近骨架。
- 其餘動作段抽樣仍鎖在投手附近；局部關節精度及遮擋可見性沒有新增人工真值可量測。

這是代理抽樣，不是逐格人工GT；框連續或骨架齊全不能證明每個肘／腕都可靠。
尤其遮擋關節仍是模型估計。保持`not_calibrated`、`accuracy=null`、
`identity_switch_confirmed=null`、`usable_for_analysis=null`。

完整H264 overlay實際解碼321格，原始像素SHA與時間皆逐格核對，
時間最大差約9.095e-13ms，第0格0秒，沒有container起點平移或插值。

## 測試與保存結果

新增11項無模型測試；完整suite **1128 run／1126 passed／0 failed／0 errors／2 skipped**，
含載入耗時82.719秒。兩項skip為Windows檔案symlink權限；junction測試實際執行。
正式山本五球MediaPipe E2E完成，major提示仍2／0／19／5／3。
完整suite沒有呼叫真實detector或RTMPose；本次106次真實推論另由worker證據核對。

672個保護檔案SHA全部不變；包括正式素材／GT／raw／權重與前次中斷全部輸出。
前215格prediction逐值0變更、逐格來源配對0錯誤，106份binary及journal完整核對。
既有程式與凍結方案未改；新增兩個獨立模組、CLI、設定與測試。
正式MediaPipe、PitcherSelector、分析核心、門檻、插值／平滑、raw及人工GT均保持。

## 輸出與停止狀態

本機輸出：`analysis_results/phase2_seeded_resume_native_20261023_01/`。
先開`review_all.html`；完整overlay位於`rtmpose/supplement_002/overlay_native.mp4`。
大型影片、模型及binary留本機；Git保存程式、設定、精簡結果及文件。

本輪已完整補完同一球，不再因前次寫入錯誤缺106格。
尚未把本次輔助追蹤當成正式自動可靠性結果，也沒有改變既有驗收門檻；
**Phase 2仍NOT PASSED**。完成commit／push後停止，不擴跑其他球、不增加人工標註或進Phase3。
