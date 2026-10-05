# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第二十二個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_21`，整體仍 `in_progress`。

- **359 visible**：新增左右肩16–31共32個Tsai原始X/Y。
- **164 not_observable**、**2 uncertain**：保持原樣，X/Y留空。
- **855 unreviewed**：其他未確認點保持原樣。

HSU對本批合併問題回答「正確」；左右肩各32可見／83未覆核。接續32–47。
Tsai於2026-10-04人工放置座標，HSU親自覆核，Codex僅轉錄與驗證，沒有子代理。
85–86左腕不確定、原模型輸出、canonical GT、原XML與舊checkpoint保留。
confidence／完整完成時間保持null；source_annotations.xml只本地保存，由Git忽略。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_24/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_22.json`。
