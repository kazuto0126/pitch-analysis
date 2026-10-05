# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第十二個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_11`，整體狀態仍是 `in_progress`。

- **151 visible**：沒有新增可見點。
- **108 not_observable**：新增右腕 0–15 共16點，X/Y 留空。
- **1,121 unreviewed**：其餘未確認點保持原樣。

HSU 回答「位置正確但是看不到」，保存推估位置意見，但不可觀測點不作為可見座標真值。
未推定不可見原因或改右肘；右腕尚待16–21、24、30–32、105–114共20格。
歷史 checkpoint、原 XML、canonical HSU 標註與原模型輸出不變。
confidence 與完整覆核完成時間保持 null；未比較座標、訓練或進入 Phase 3。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_14/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_12.json`。
`source_annotations.xml` 僅本地保存，由 Git 忽略。
