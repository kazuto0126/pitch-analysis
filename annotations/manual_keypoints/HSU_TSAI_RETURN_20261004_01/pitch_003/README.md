# pitch_003 — HSU 部分覆核的人工座標

Tsai 在 CVAT 放置原始座標，使用者提供標註日期 2026-10-04。
HSU 覆核原圖與人工骨架，Codex 僅依其明確回答保存狀態及座標。

`manual_keypoints.json` 沿用 `manual-keypoints-v1`，狀態為 `in_progress`：

- 14 `visible`：左腕 46–48、左肘 66–72，以及左肘／左腕 64–65。
- 63 `not_observable`：右肘 22–23；右腕 22–23、25–29、83、87–104；左踝 65；左肘／左腕 33–44；左肘 46–48；左腕 66–72。
- 1,303 `unreviewed`：尚未由 HSU 逐點確認，不表示 Tsai 沒標或標錯。

只有可見且經確認的 14 點保留 Tsai 的原始 X/Y；其他點的 X/Y 是 null。
目視對位正確不代表測得像素誤差為零，也沒有據此更新模型。
confidence 與完整覆核完成時間均未提供，保持 null。

原始 ZIP、XML 與原狀態宣告保存在：
`analysis_results/manual_pose_return_check_20261004_01/original_return_preserved_20261004_01/`。
完整原 XML 也留在本資料夾的 `source_annotations.xml`；含帳號資訊，由 Git 忽略，僅在本地保存。
ZIP/XML 校驗碼、正式影片來源、115 格解碼圖片及時間軸均重新核對。

HSU 事件與可見性補充另存於：
`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261004_02/pitch_003/ground_truth.json`。
既有 canonical HSU ground truth 與模型輸出保持原樣。
尚未進行座標誤差比較；Phase 2 仍在進行中。
