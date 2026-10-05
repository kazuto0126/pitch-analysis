# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第一個 checkpoint

`manual-keypoints-v1`，狀態仍是 `in_progress`；承接 `HSU_TSAI_RETURN_20261004_07`。

- **106 visible**：HSU 確認右肘 83–92 共十點可見且位置正確，加入 Tsai 原始 X/Y。
- **84 not_observable**：沒有新增不可觀測點；座標留空。
- **1,190 unreviewed**：其他未確認點仍不自動採用。

原始回答「位置正確」，範圍是續看頁中的右肘 83–92。
此前「沒有」的原話仍保留；這次明確澄清已解除該十格的點位待確認事項。
不把整體點位正確的目視評語當成像素誤差為零。

Tsai 原 XML 與過去七版皆保留原樣；`source_annotations.xml` 只在本地保存並由 Git 忽略。
confidence 與完整覆核完成時間保持 null；未比較模型、訓練或進入 Phase 3。
人工原話及事件補充：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_02/pitch_003/ground_truth.json`。
驗證報告：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_01.json`。
