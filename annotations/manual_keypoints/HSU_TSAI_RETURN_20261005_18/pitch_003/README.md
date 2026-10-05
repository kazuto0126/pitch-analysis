# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第十八個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_17`，整體仍 `in_progress`。

- **243 visible**：新增本批左肘16點、左腕14點，共30個Tsai原始X/Y。
- **164 not_observable**：既有不可觀測點不變。
- **2 uncertain**：85–86左腕看不清，X/Y留空，未指定原因。
- **971 unreviewed**：其他未確認點保持原樣。

HSU 先表示85–86左腕看不清、其他位置正確，再明確確認其餘全部看得見。
左肘57可見／32不可觀測／26未覆核；左腕35可見／52不可觀測／2不確定／26未覆核。
接續89–104左肘／左腕；本批僅73–88，不擴大人工判斷範圍。
原XML、canonical HSU與模型輸出、舊checkpoint保留；confidence／完整覆核完成時間保持null。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_20/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_18.json`。
`source_annotations.xml`僅本地保存，由Git忽略。
