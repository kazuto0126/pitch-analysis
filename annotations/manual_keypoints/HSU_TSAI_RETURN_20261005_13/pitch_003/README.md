# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第十三個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_12`，整體狀態仍是 `in_progress`。

- **165 visible**：新增右腕24、30–32、105–114共14個Tsai原始X/Y。
- **114 not_observable**：新增右腕16–21共6點，X/Y留空。
- **1,101 unreviewed**：其他未確認點保持原樣。

HSU 原話：「16-21位置正確但看不到，其他都看的到且位置正確」。範圍僅為本次呈現的20格右腕。
右腕全115格已覆核：58可見且對位、57不可觀測；右肘93可見／22不可觀測不變。
未推定不可見原因；歷史checkpoint、原XML、canonical HSU與模型輸出保留。
confidence／完整覆核完成時間保持null，未比較座標或訓練。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_15/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_13.json`。
`source_annotations.xml`僅本地保存，由Git忽略。
