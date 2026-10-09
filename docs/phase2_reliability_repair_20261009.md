# Phase 2 主線恢復：自動錯位警示修復起點

2026-10-09（台灣）。前置 [handoff回歸核對](handoff_regression_20261009.md) 完成：
原240項測試全通過、正式五球592格重跑結果0差異、交付／正式／人工來源未變。
**Phase 2 automatic reliability仍NOT PASSED。**

## 本次已完成的下一步

以新重跑、已確認相同的五球結果建立獨立case index，不建立新detector。

`analysis_results/phase2_repair_start_20261009_01/case_index.json`

- 全592格保留原tracking screen、選取狀態、warnings、中心與尺度，對照原人工major標記。
- 21格confirmed重大失效：TP3、FN18；9格目標外提示、562格TN。
- FN18全部為003的87–104格；這段skeleton仍持續selected，整體tracking被列reliable。
- 五份canonical GT、五份pose與五份tracking各自綁定SHA，15個來源；沒有新增人工答案。
- 原事件的exact／range／uncertain完整保留；遮擋點不當精確真值。
- 這是已知baseline修復案例，不是未見投手的獨立泛化測試集。

## 接續工作與驗證方式

1. 聚焦有骨架卻對位錯誤的主體證據，先讓離線候選方法能區分003已知錯位與其餘正常動作。
   沿用五球MediaPipe及原raw，不重新要求HSU標完的區間再做一次，不把coverage當正確性。
2. 以同一592格、confirmed／uncertain／not_observable的既有規則，逐片列TP／FN／FP與原模型
   比較；不能只報「某段有一次警示」、降低門檻或透過標記frame號達標。
3. 若證據仍會跟到打者／背景，保留未解決結果；不以KLT往返誤差、小衣物patch或同模型mask
   當成已確認投手。既有失敗方向見原subject-support及diagnosis文件。
4. 在方法有可核對證據與明確驗收方式之前，維持獨立評估，不部署進正式分析核心；沒有發明新的
   總分或自動通過線。事件detector、3D、跨投手profile與新pose模型均不在此步。

這一步先完成來源一致的修復案例整理；沒有假稱已修好FN18或Phase 2已通過。
八球handoff input review仍7項pending，正式轉換／提升與分析尚未安排。
