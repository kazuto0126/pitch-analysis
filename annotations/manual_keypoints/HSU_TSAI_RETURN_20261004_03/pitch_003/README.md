# pitch_003 — HSU 部分人工座標覆核，第三個 checkpoint

狀態為 `in_progress`，沿用 `manual-keypoints-v1`。Tsai 放置原始座標；HSU 覆核可見性與點位。

- **56 visible**：左腕 46–48、左肘 66–72、左肘／左腕 64–65、右肘／右腕 33–53。
- **63 not_observable**：保留前兩版已確認的不可觀測區間，X/Y 留空。
- **1,261 unreviewed**：尚未確認，X/Y 留空。

本次加入右肘／右腕 45–53 共 18 點，全部直接保留 Tsai 原 XML 的 X/Y。點位判斷來自 HSU 本次明確回覆，不沿用舊 AI 對位判斷。
confidence 與完整覆核完成時間保持 null；尚未執行比較、模型分析或訓練。

前兩版 checkpoint、canonical HSU 標註及原始預測保持原樣。
`source_annotations.xml` 為完整原 XML，含帳號資訊，僅在本地保存並由 Git 忽略。
原 ZIP/XML 與原狀態宣告保存在 `analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。

驗證報告：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261004_03.json`。
原始回答：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`。
Phase 2 尚在進行中。
