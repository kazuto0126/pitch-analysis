# Phase 1.1 — Input Quality Gate

此 gate 沿用 `pitch-input-v1`，沒有搜尋、下載、剪輯、修復或球員 ReID。它針對已整理好的
`rear_centerfield_broadcast` 單球 MP4 提供保守 triage，不能以演算法的 `accepted`
取代人工驗片。既有 pose confidence threshold、phase、DTW 和 reference 規則不變。

## 兩層判斷

1. `validate-pitch` 仍檢查 metadata、CFR、完整解碼與 30 秒長度。`validate-input-quality`
   在其後逐幀低解析度掃描相鄰畫面差異與 HSV 分布。明顯硬切鏡直接 `rejected`；
   較弱的候選切鏡或長段近似重複畫面 `degraded`。這一步不呼叫 MediaPipe。
2. `analyze-pitch` 在正式 pose 前執行同樣 preflight。未拒絕者沿用原分析流程，
   再用已產生的逐幀投手選取／原始 keypoints 更新品質報告：選取比例、最長
   pose-invalid span、跨遺失區段的髖中心跳動、投球前段與尾段的 2D 膝高線索、
   以及原有 pose/feature quality gate。這些是可疑訊號，不是事件 ground truth。

`accepted`：沒有觸發目前可觀測的品質警訊，且原有 pose/feature gate 通過。
仍須人工確認真正投手、相機視角、完整單球及速度。

`degraded`：有不確定或不完整的訊號（例如準備階段缺失、較弱切鏡、
原有 pose gate 未過）；不可直接進 reference。

`rejected`：明顯硬切鏡、長時間 pose 無效、選取比例過低，或跨遺失區段
出現大幅髖中心跳動；保留證據，不自動修復或降低門檻。

`input_quality_preflight.json` 記錄 pose 前判定，`input_quality.json` 記錄最新判定。
`analysis.json.status` 對 pose 已執行的影片保留原有 `no_pose`、`quality_gate_failed`、
`needs_event_review` 語意，另由 `input_quality.json.status` 表示 input eligibility。
preflight 直接拒絕時 `analysis.json.status=input_rejected`，不應期待 keypoints/overlay。
新結果的 registry eligibility 也會檢查 `input_quality.json.status=accepted`；
既有無該報告的 legacy reference 暫維持舊審查規則。

## 不能自動證明的事項

- 無語意相機分類器。即使沒有硬切鏡，也不能確認每幀都是真正 rear-centerfield；
  低對比 dissolve 或相近畫面的切鏡也可能漏檢。
- 重複影格只能提示 freeze/replay，不能確認影片正常速度；原生高 FPS 慢動作
  也可能沒有重複幀。需檢查球速、動作速度與轉播標記。
- 髖中心跳動只能提示可能換人或鏡頭改變，不能證實選取了哪位球員。
- 2D 膝高只能提示準備或後續動作可能不完整，不能精確定位 release、
  maximum external rotation 或 follow-through 結束事件。
- 數值閾值是非校準的通用 heuristic，`confidence.level` 不是機率。
  後續需用多投手、不同場次的人工標註影片評估 false positive / false negative。

人工 review 請保留逐支 overlay 檢查，尤其是疑似切鏡前後、投手與跑者／捕手
的選取、起始準備階段、release 後的尾段、慢動作／重播、水平鏡像與視角。

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe validate-input-quality input\yoshinobu_yamamoto\pitch_002.mp4 input\yoshinobu_yamamoto\pitch_002.json --output analysis_results\pitch_002_preflight.json
.\.venv-analysis\Scripts\pitch-analysis.exe analyze-pitch input\yoshinobu_yamamoto\pitch_002.mp4 input\yoshinobu_yamamoto\pitch_002.json --output-root analysis_results\phase1_1
```

每次分析請使用新的 output root；不覆寫舊 Phase 1 證據。
