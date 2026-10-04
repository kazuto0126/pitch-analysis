# pitch_003 — HSU 部分人工座標覆核，第五個 checkpoint

`manual-keypoints-v1`，狀態為 `in_progress`。Tsai 放置原始 X/Y，HSU 覆核原圖可見性與點位。

- **90 visible**：左腕 46–48、左肘 66–72、左肘／左腕 64–65、右肘／右腕 33–69 與 72。
- **67 not_observable**：前版 63 點，加上本次 HSU 確認看不到的右肘／右腕 70–71 四點；X/Y 留空。
- **1,223 unreviewed**：尚未確認，X/Y 留空。

HSU 先確認右肘／右腕 64–72 的位置意見，接著在單獨原圖覆核表示 70–71 兩關節看不到。
不可觀測的四點不採用推估座標；其他 14 個新增可見点直接保留 Tsai 原 X/Y。
未自行推定看不到的原因。confidence 與完整覆核完成時間保持 null。

前四版、canonical HSU 標註與原始預測保留原樣。沒有執行比較、pose 分析或訓練。
`source_annotations.xml` 是完整原 XML，僅在本地保存並由 Git 忽略。
原始回傳：`analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。
驗證報告：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261004_05.json`。
原始回答：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`。
Phase 2 尚在進行中。
