# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第二十一個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_20`，整體仍 `in_progress`。

- **327 visible**：新增左右肩0–15共32個Tsai原始X/Y。
- **164 not_observable**、**2 uncertain**：保持原樣，X/Y留空。
- **887 unreviewed**：尚未經人工確認的點保持原樣。

HSU親自看圖回答「都正確清楚」；左右肩各16可見／99未覆核，接續16–31。
85–86左腕不確定紀錄、原模型輸出、canonical HSU紀錄、舊checkpoint與原XML保留。
Tsai於2026-10-04手動放置原座標，HSU確認可見性及位置；Codex只轉錄與驗證。
confidence／完整覆核完成時間保持null。`source_annotations.xml`只本地保存且由Git忽略。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_23/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_21.json`。
