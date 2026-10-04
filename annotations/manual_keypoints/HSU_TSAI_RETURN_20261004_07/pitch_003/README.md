# pitch_003 — HSU 部分人工座標覆核，第七個 checkpoint

`manual-keypoints-v1`，狀態為 `in_progress`；Tsai 放置原始 X/Y，HSU 覆核原圖可見性與點位。

- **96 visible**：本次沒有新增可見且對位的點。
- **84 not_observable**：本次加入右腕 84–86 三點；HSU 確認被遮住，X/Y 留空。
- **1,200 unreviewed**：包含右肘 83–92；HSU 已確認可見，但點位正確性仍待確認。

HSU 原始回答：「右腕都被遮住右肘皆可看到」。只保存這次明示的可見性，未把可見等同點位正確。
confidence 與完整覆核完成時間保持 null；沒有執行比較、模型分析或訓練。

前六版、canonical HSU 標註與原始預測保留原樣。
`source_annotations.xml` 僅在本地保存並由 Git 忽略。
原始回傳：`analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。
驗證報告：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261004_07.json`。
原始回答：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`。
Phase 2 仍在進行中。
