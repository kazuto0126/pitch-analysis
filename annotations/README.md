# 人工標註與覆核進度

更新：2026-10-05。人工判斷來自 HSU／Tsai；工具只轉錄已提供的答案及驗證格式／來源。

## 目前應使用的部分參考

- 人工座標：`manual_keypoints/HSU_TSAI_RETURN_20261004_07/pitch_003/manual_keypoints.json`。
- 最新 HSU 補充：`phase2_peer_reviews/HSU_TSAI_RETURN_20261005_01/pitch_003/ground_truth.json`。
- 原始 HSU 五支定性紀錄：`analysis_results/phase2_yamamoto_20260925_01/ground_truth/pitch_00N/ground_truth.json`。

部分座標共有 **96 visible、84 not_observable、1,200 unreviewed**；仍為 `in_progress`。
Tsai 放置原始 X/Y；HSU 逐段確認影像可見性及點位。只有確認可見且對位的點保留原始 X/Y。
其他狀態座標留空，沒有用透視、插值或模型補成 ground truth。
右肘 83–92 可見已確認，但最後短答「沒有」的含義待釐清，不能自行判全部對或錯。

## 保存與接續

舊 checkpoint 不刪除、不覆寫。補充事件與 canonical 的差異分開記錄，不自動合併。
完成時間與 confidence 未提供時保持 null。完整人工覆核前不宣稱 Phase 2 通過。

原 ZIP/XML 與完整對照圖保存在本機 `analysis_results/manual_pose_return_check_20261004_01/`。
XML 含帳號資訊，僅本地保存並由 Git 忽略；沒有將其加入 GitHub。

下次檢查入口與保存說明見 `docs/phase2_manual_review_checkpoint_20261005.md`。
