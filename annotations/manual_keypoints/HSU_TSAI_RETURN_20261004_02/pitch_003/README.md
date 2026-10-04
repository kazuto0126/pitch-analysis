# pitch_003 — HSU 部分人工座標覆核，第二個 checkpoint

沿用 `manual-keypoints-v1`，狀態為 `in_progress`。Tsai 人工放置原座標，HSU 觀看原圖及人工骨架後提供可見性與點位判斷。

- **38 visible**：左腕 46–48、左肘 66–72、左肘／左腕 64–65，以及右肘／右腕 33–44。
- **63 not_observable**：沿用前一版已明確確認的不可觀測區間，X/Y 留空。
- **1,279 unreviewed**：尚未確認，X/Y 留空；不表示 Tsai 漏標或標錯。

新增 24 個可見點全部保留 Tsai 原 XML 的 X/Y，未推估或修改座標。
confidence 與完整覆核完成時間保持 null。沒有執行 prediction comparison、pose 分析或訓練。

第一版位於 `annotations/manual_keypoints/HSU_TSAI_RETURN_20261004_01/pitch_003/`，保留原樣。
本資料夾的 `source_annotations.xml` 是相同原 XML，含帳號資訊，僅在本地保存並由 Git 忽略。
原 ZIP、XML、未修正 CVAT 狀態宣告保存在 `analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。

本次校驗報告：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261004_02.json`。
HSU 的原始回答與事件另存於 `annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`。
canonical HSU 標註、第一版參考與原始預測保持原樣；Phase 2 尚未通過。
