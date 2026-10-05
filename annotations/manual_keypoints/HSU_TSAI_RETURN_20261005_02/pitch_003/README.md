# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第二個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_01`，狀態仍是 `in_progress`。

- **110 visible**：加入右肘 93–96 四點；HSU 回答「看的到且正確」，保存 Tsai 原始 X/Y。
- **84 not_observable**：本次沒有新增；座標留空。
- **1,186 unreviewed**：其餘未確認點保持原樣。

只處理本次四格 RIGHT_ELBOW，未修改右腕或擴及 97–100。
歷史 checkpoint、原始 XML、canonical HSU 標註與模型輸出保持不變。
confidence 與完整覆核完成時間保持 null；未做座標比較、模型訓練或 Phase 3。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_03/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_02.json`。
`source_annotations.xml` 僅本地保存，由 Git 忽略。
