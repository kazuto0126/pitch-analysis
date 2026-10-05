# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第十七個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_16`，整體仍 `in_progress`。

- **213 visible**：新增左肘／左腕45、49–63共32個Tsai原始X/Y。
- **164 not_observable**：既有不可觀測點不變。
- **1,003 unreviewed**：其他未確認點保持原樣。

HSU 原話：「皆可看到位置正確」。僅轉錄本批兩關節可見且對位；沒有推估或修改座標。
左肘41可見／32不可觀測／42未覆核；左腕21可見／52不可觀測／42未覆核。
接續73–88左肘／左腕；64–72已覆核，略過。
原XML、canonical HSU與模型輸出、舊checkpoint保留；confidence／完整覆核完成時間保持null。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_19/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_17.json`。
`source_annotations.xml`僅本地保存，由Git忽略。
