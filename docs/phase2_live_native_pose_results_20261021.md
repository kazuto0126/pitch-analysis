# 可選 live RTMPose 入口：實作與五球交付結果

收尾日期：2026-10-21（台灣）。實際單次推論於 2026-10-20 13:18:46–13:21:01 UTC 完成。

**Live native engineering integration = PASSED。Phase 2 自動可靠性 = NOT PASSED。**

HSU 已核准[固定範圍方案](phase2_live_native_pose_plan_20261020.md)，本輪已完成該範圍。
新入口能處理新 MP4，並保存可追查的原生座標與 overlay；新模型仍有跨人骨架，沒有取代正式模型。
[使用說明](phase2_live_native_pose_usage.md)、[版本化結果](dataset_selections/ohtani_live_native_results_20261021.json)。

## 實際交付

- 獨立入口 `scripts/run_native_pose_live.py`，正式 `analyze-pitch` 預設仍為 MediaPipe。
- 沿用既有 RTMPose-m ONNX 權重、已確認的完整動作 crop，以及隔離 runtime；沒有下載或替換權重。
- 原生 COCO17 輸出原圖 pixel XY／原生 score；Z、visibility、presence 保持 null。不補成 33 點、不插值。
- 全部來源在推論前核對 SHA、人工輸入覆核、格數及分數 FPS 時間軸。
- 每格一次呼叫；失敗停止、保存逐格 journal，不自動重試或覆寫輸出。握手沒有合成推論。
- 保存全部原生 SimCC binary、來源／實作雜湊、正逆座標轉換，以及五支完整 H264 overlay。

來源：大谷補片批次 `20261020T073530Z_6gyr6IC2e0Q`，1280×720、60000/1001 FPS。
固定原圖 crop 為 `[192,216,768,720)`；本輪沒有倍率或範圍搜尋。

| 影片 | 完成格數／真實呼叫 | 舊 MediaPipe 選中格數（保持） | 舊最長 pose gap（保持） | 新肘／腕座標數 |
|---|---:|---:|---:|---:|
| supplement_001 | 335 / 335 | 324 | 9 | 335 / 335 |
| supplement_002 | 321 / 321 | 275 | 13 | 321 / 321 |
| supplement_003 | 369 / 369 | 362 | 5 | 369 / 369 |
| supplement_004 | 338 / 338 | 323 | 12 | 338 / 338 |
| supplement_005 | 321 / 321 | 315 | 2 | 321 / 321 |
| 合計 | **1684 / 1684** | **1599** | — | **1684 / 1684** |

實際嘗試／完成各 1,684 次，執行失敗 0。Worker journal 共 3,368 列，
attempt 1–1684 各一組 started／completed，沒有重試；1,684 份 binary payload SHA 全部吻合，共 102,602,752 bytes。
五支 overlay 全解碼共 1,684 格，原圖尺寸／FPS 不變，最大時間差 `9.095e-13 ms`。
摘要、overlay 及比較檔的 `new_inference_calls=0` 只指報告／繪圖本身；整輪真實呼叫以 `run_receipt.json` 為準。

**新肘／腕每格都有座標，不能解讀為 100% 可靠 coverage。**
原生 score 未校準，也未套用 MediaPipe 0.5 visibility／presence gate，兩者的可用格數不能直接比較。
六個重要關節的 score 分布、逐格跳動、同格模型分歧保存在 `comparison_summary.json`；
例如第4球肘最大相鄰位移 332.04 px、第5球肩 248.56 px，這些僅為描述，不是新增門檻或可靠性判定。

## 實際影像抽查

Codex 已看完每球 18 張 overlay 取樣，共 90 張，以及 9 組原片／舊 MediaPipe／新 RTMPose 對照；
共 13 張 contact sheet。這是代理的影像抽樣檢查，不是逐格人工 GT，也不是全片關節準確率評估。

| 影片 | 抽查觀察與限制 |
|---|---|
| 001 | 抽樣主要骨架靠近投手；舊缺失第138格有新骨架接近投手輪廓。遮擋處局部對位仍未人工確認。 |
| 002 | 舊錯例第159／245格新骨架較接近投手；但新模型第0／19／38／56／75格混接投手下身與打者附近上身／頭部，第188格也有上方點偏移。不能宣稱主體穩定。 |
| 003 | 抽樣主要骨架靠近投手；舊缺失第185格有新骨架。局部關節未有新人工真值。 |
| 004 | 抽樣主要骨架靠近投手；第149格有新骨架，但前傾段上身／手臂仍近似且有較大跳動。 |
| 005 | 舊混合例第251格新骨架較接近投手；**新模型第128格仍有嚴重混合／錯位**。其他部分手臂對位尚未確認。 |

部分既有錯例有可見改善，同時存在新錯例，不能宣稱新後端整體優於舊模型。
五球只有人工輸入條件覆核，沒有新逐格 XY／可見性 GT；accuracy 與 confirmed identity switch 保持未量測。
遮擋處的座標仍是模型估計，沒有改寫人工不可觀測／不確定標記。

## 測試與資料保存

完整測試：**1057 run，1055 passed，0 failed，0 errors，2 skipped**，64.453 秒；比前版新增 39 項。
正式山本五球真實 MediaPipe E2E 已啟用，major review hints 仍為 **2／0／19／5／3**。
測試未呼叫真實 RTMPose；真實模型只在上述固定五球執行。

兩項 skipped 都因 Windows 無檔案 symbolic-link 建立權限：dangling snapshot file link、
candidate source symlink。Junction 相關測試在最終完整執行中實際通過。
測試證據：`analysis_results/phase2_live_native_preparation_20261020_01/test_results_unrestricted.json`
及 `full_suite_unrestricted.log`。

來源、正式素材、舊輸出、權重、raw／GT 與正式核心等 **475 個保護檔案 SHA 全部不變**。
本輪沒有修改 `analysis/pitch.py`、`workflow.py`、`pose_capture.py`、`subject.py`、
`clean_pose.py`、`features.py`、`config.py`，也沒有改既有 gate、門檻、平滑或插值。
交付資料夾沒有寫入；五球仍為 candidate，未替換山本正式五球，新增人工標註 0。

## 新增／修改檔案

- 新增 `native_pose_estimator.py`、`native_pose_transport.py`、`native_pose_live.py`：原生推論、隔離通訊及固定來源執行。
- 新增 `scripts/native_pose_onnx_worker.py`、`scripts/run_native_pose_live.py`：隔離 worker 與可選入口。
- 擴充 `native_pose.py`、native contract schema、`native_pose_review.py`：保留 cached 模式，增加 live 來源／時間契約及 overlay。
- 新增 live 設定、39 項測試及使用／結果文件；更新 README、STATUS、current_status。

## 輸出與停止狀態

本機完整輸出：`analysis_results/phase2_ohtani_live_native_20261020_01/`。
先開 `review_all.html` 並列觀看三種影片，或各球 `rtmpose/supplement_00N/overlay_native.mp4`。
`visual_review/inspection.json` 保存抽查範圍與限制，`preservation_check.json` 保存呼叫／SHA 核對。
大型影片與 binary 留在本機忽略的 analysis_results；Git 保存實作、設定及精簡結果證據。

本輪核准的實作與一次性執行已完成並停止。新結果維持 `not_calibrated`、`usable_for_analysis=null`；
舊五球分析仍 5 degraded，**Phase 2 = NOT PASSED**。
沒有自行開始新推論、校準、正式模型替換或 Phase 3。
