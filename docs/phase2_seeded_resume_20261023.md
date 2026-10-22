# 2026-10-23：接續未執行106格

使用者在上次中斷結果回報後要求「繼續」。本次只完成同一球尚未執行的部分，
不改先前凍結政策或擴大原319次新pose額度。第0格仍沿用HSU指定的1號框。

## 固定範圍

- 讀取已保存的321格`subject_track.jsonl`，本次追蹤replay／detector皆0。
- 完全保留舊輸出、claim、兩份過時receipt、partial、journal、binary與舊程式。
- journal213對started/completed、binary及partial215格全部相符，沒有不確定的已嘗試呼叫才可續行。
- 0–214格215份prediction逐值原樣帶入；包括193／194兩格舊cache。
- 僅215–320共106格各執行一次；沿用相同框、crop、RTMPose、runtime、像素及分數時間軸。
  合計213＋106＝原額度319次新pose；既有cache2另列。
- 新段獨立設定／claim／worker／journal／輸出。claim排除重複續跑；不清除或借用舊claim。
- 逐事件另存不可變序號JSON，exclusive create、flush/fsync，不替換舊snapshot或使用固定.tmp。
  錯誤記錄若也失敗，保留最初例外，不讓FileExistsError蓋掉原因。不自動重試模型。
- 新結果仍原生17點、not_calibrated、usable_for_analysis=null；不改正式核心、gate、門檻、raw或人工GT。

新增必要測試後跑一次完整suite（含正式山本五球相容檢查），再執行本次106格一次。
核對前215份prediction不變、106新呼叫、321完整分母與全部來源保存；
重產完整overlay，檢查原20個固定對照格、193／194與續跑交界214／215／216。
結果記於獨立結果文件，不修改已綁SHA的舊方案／本執行前範圍文件。

本次完成後commit／push並停止；不自動正式採用、不宣告Phase2通過、不擴跑其他球或進Phase3。
