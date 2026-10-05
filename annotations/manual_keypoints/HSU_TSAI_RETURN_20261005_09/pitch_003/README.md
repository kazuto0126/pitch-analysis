# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第九個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_08`，狀態仍是 `in_progress`。

- **128 visible**：加入右肘 4–7 四點，保存 Tsai 原始 X/Y。
- **92 not_observable**：沒有新增；座標留空。
- **1,160 unreviewed**：其餘未確認點保持原樣。

HSU 對直接可見且點位正確的合併問題回答「正確」，只限這四格 RIGHT_ELBOW。
歷史 checkpoint、原 XML、canonical HSU 標註及模型輸出不變。
confidence 與完整覆核完成時間保持 null；未比較座標、訓練或進入 Phase 3。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_11/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_09.json`。
`source_annotations.xml` 僅本地保存，由 Git 忽略。
