# pitch_003 — HSU 部分人工座標覆核，2026-10-05 第十一個 checkpoint

承接 `HSU_TSAI_RETURN_20261005_10`，整體狀態仍是 `in_progress`。

- **151 visible**：加入右肘 12–21、24–32 共19點，保存 Tsai 原始 X/Y。
- **92 not_observable**：沒有新增；座標留空。
- **1,137 unreviewed**：其他關節尚未確認點保持原樣。

HSU 對整批可見/點位確認提示回答「全部都正確」。點位判斷針對 Tsai；原片可見性亦有同SHA既有HSU紀錄，詳細依據另存補充notes。
右肘全115格狀態已確認：93 visible、22 not_observable、0 unreviewed。
其他關節仍有未覆核，不能因此把整支 manual reference 設成 reviewed 或 Phase 2 通過。
歷史 checkpoint、原 XML、canonical HSU 標註及模型輸出不變。
confidence 與完整覆核完成時間保持 null；未比較座標、訓練或進入 Phase 3。
原話：`annotations/phase2_peer_reviews/HSU_TSAI_RETURN_20261005_13/pitch_003/ground_truth.json`。
驗證：`analysis_results/manual_pose_return_check_20261004_01/manual_keypoints_HSU_checkpoint_check_20261005_11.json`。
`source_annotations.xml` 僅本地保存，由 Git 忽略。
