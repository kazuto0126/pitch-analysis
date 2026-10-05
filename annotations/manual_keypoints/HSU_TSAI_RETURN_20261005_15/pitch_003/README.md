# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第十五個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_14`，整體仍 `in_progress`。

- **181 visible**：新增左肘0–15共16個Tsai原始X/Y。
- **130 not_observable**：前版左腕0–15共16點不可觀測不變。
- **1,069 unreviewed**：其他未確認點保持原樣。

HSU 先確認左肘點位正確，再回答原圖左肘0–15「全部看得見」。
原XML、canonical HSU與模型輸出、舊checkpoint保留；confidence／完整覆核完成時間保持null。
接續16–32左肘／左腕，尚未收到該批人工判斷；未比較座標或訓練。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_17/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_15.json`。
`source_annotations.xml`僅本地保存，由Git忽略。
