# 山本四球人工事件與時序比較：本輪範圍

2026-10-24，HSU以「好進行」核准上一則提出的同投手動作時序比較。

- 僅處理已接受的山本001／002／004／005，共477格；003仍為歷史對照。
- 只讀保存的曲線與同一原片的canonical `ground-truth-v1`事件，不重新標註。
- 讀取前核對事件檔SHA、原片SHA／檔名、pitch_id、影格數與0起算時間軸。
- 在原曲線加精確事件線／範圍色帶；不確定候選另用虛線，不提升為精確答案。
- 時距用事件上下界計算：`[max(0, end_min-start_max), end_max-start_min] / 分數FPS`。
  任一端為uncertain／not_observable時留空並附原因，不取中點、不猜事件。
- 逐事件顯示已保存肘／膝模型角的範圍與完整缺值分母，不改原角度或逐點unknown/null。
- 同投手時距表與事件／曲線對照頁是本輪交付；沒有精確出手對齊、跨投手比較或動作品質評分。
- 不把舊模型的人工關節品質區間套用到新骨架；不讀供片能量anchors作事件。
- 共用骨架方式、raw、既有門檻、人工GT、原CSV／PNG及已接受觀看頁保持。
- 新增數值／來源／不確定性測試，跑一次完整suite與純Node測試；產生實際四球輸出，
  更新狀態與結果，commit／push後停止。

人工事件來源設定：`config/analysis_inputs/yamamoto_event_timing_20261024.json`。
輸出：`analysis_results/phase3_yamamoto_event_timing_20261024_01/`。
本輪不改Phase2自動可靠性NOT PASSED或Phase3整體NOT EVALUATED的結論。
