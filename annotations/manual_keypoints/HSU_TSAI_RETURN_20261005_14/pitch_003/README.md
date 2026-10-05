# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第十四個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_13`，整體仍 `in_progress`。

- **165 visible**：未新增可見座標。
- **130 not_observable**：新增左腕0–15共16點，X/Y留空。
- **1,085 unreviewed**：其他未確認點保持原樣。

HSU 原話：「看不到左腕但是位置正確，左肘位置正確」。左肘0–15位置正確，但可見性尚待澄清，仍unreviewed、X/Y null。
推估不可見位置意見不當成可見真值；未推定不可見原因。
舊checkpoint、原XML、canonical HSU與模型輸出保留；confidence／完整覆核完成時間保持null。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_16/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_14.json`。
`source_annotations.xml`僅本地保存，由Git忽略。
