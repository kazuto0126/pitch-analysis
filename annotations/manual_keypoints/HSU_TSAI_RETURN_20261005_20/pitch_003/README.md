# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第二十個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_19`，整體仍 `in_progress`。

- **295 visible**：新增左肘／左腕105–114共20個Tsai原始X/Y。
- **164 not_observable**：既有不可觀測點不變。
- **2 uncertain**：85–86左腕看不清，X/Y留空。
- **919 unreviewed**：其他未確認點保持原樣。

HSU對本批清楚可見且位置正確的合併問題回答「正確」。
左肘83可見／32不可觀測；左腕61可見／52不可觀測／2不確定。
四個肘／腕關節各115格已完成逐點覆核；接續雙肩0–15，雙肩所有點仍未覆核。
Tsai於2026-10-04人工放置原座標，HSU親自確認可見性及點位；Codex僅轉錄與驗證。
原XML、canonical HSU與模型輸出、舊checkpoint保留；confidence／完整覆核完成時間保持null。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_22/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_20.json`。
`source_annotations.xml`僅本地保存，由Git忽略。
