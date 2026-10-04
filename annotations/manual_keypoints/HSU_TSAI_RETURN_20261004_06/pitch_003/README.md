# pitch_003 — HSU 部分人工座標覆核，第六個 checkpoint

`manual-keypoints-v1`，狀態為 `in_progress`；Tsai 放置原始 X/Y，HSU 覆核原圖可見性與點位。

- **96 visible**：本次另加入右腕 73–78 六點，保留 Tsai 原座標。
- **81 not_observable**：本次另加入右肘 73–78 六點、右肘／右腕 79–82 八點，X/Y 留空。
- **1,203 unreviewed**：尚未確認，X/Y 留空。

HSU 先指出右腕 73–78 可見，再明確確認點位正確，並澄清右肘同段不可見。
不可見的點不補透視座標，未自行推定看不到的原因。
confidence 與完整覆核完成時間保持 null；沒有執行比較、模型分析或訓練。

前五版、canonical HSU 標註與原始預測保留原樣。
`source_annotations.xml` 僅在本地保存並由 Git 忽略。
原始回傳：`analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。
驗證報告：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261004_06.json`。
原始回答：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`。
Phase 2 仍在進行中。
