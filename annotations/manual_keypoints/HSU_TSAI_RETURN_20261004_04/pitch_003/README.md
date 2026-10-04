# pitch_003 — HSU 部分人工座標覆核，第四個 checkpoint

`manual-keypoints-v1`，狀態為 `in_progress`。Tsai 放置原座標，HSU 覆核原圖與人工點位。

- **76 visible**：左腕 46–48、左肘 66–72、左肘／左腕 64–65、右肘／右腕 33–63。
- **63 not_observable**：沿用已明確確認的不可觀測區間，X/Y 留空。
- **1,241 unreviewed**：尚未确认，X/Y 留空。

本次加入右肘／右腕 54–63 的 20 點，全部保留 Tsai 原 XML 的 X/Y。
前三版 checkpoint、canonical HSU 標註及原始預測保持原樣。
confidence 與完整覆核完成時間保持 null；未執行比較、模型分析或訓練。

`source_annotations.xml` 為完整原 XML，僅在本地保存並由 Git 忽略。
原始回傳位於 `analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。
驗證報告：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261004_04.json`。
原始回答：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`。
Phase 2 仍在進行中。
