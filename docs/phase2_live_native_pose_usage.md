# 可選RTMPose新影片入口

這個入口讀取本地已覆核MP4，輸出RTMPose原生17點與獨立overlay。
正式`analyze-pitch`仍使用原MediaPipe流程；新結果不會自動變成正式分析資料。

## 本次已核准執行

來源是大谷補片批次`20261020T073530Z_6gyr6IC2e0Q`，五球共1,684格。
設定與來源SHA在`config/pilots/ohtani_live_native_20261020.json`。
本次固定執行已完成；以下是已執行入口的紀錄，無須重跑。
[交付結果與已知錯例](phase2_live_native_pose_results_20261021.md)記錄實際影像檢查及停止狀態。

執行入口：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts/run_native_pose_live.py `
  config/pilots/ohtani_live_native_20261020.json `
  analysis_results/phase2_ohtani_live_native_20261020_01
```

相同輸出目錄已存在時會拒絕執行，不自動覆寫或續跑。
本輪授權是每格一次；失敗的呼叫也會保留紀錄，不能自動換輸出路徑重試。

新來源須先經既有交付匯入、七項人工輸入覆核、來源綁定的完整動作範圍確認，
並建立另行核准的設定；本入口不搜尋、下載或剪輯影片，也不讀供片端程式碼。

## 會產生什麼

- `run_receipt.json`：實作授權、執行狀態、嘗試／完成次數與失敗原因。
- `worker/worker_calls.jsonl`：每次真實推論前後的紀錄，對應input／output SHA與原生binary位置。
- `worker/worker_outputs.bin`：完整SimCC原始float32輸出，含模型非finite值，供追查。
- `supplement_00N.partial.jsonl`：逐格保存journal；完整狀態以receipt及正式native dataset為準。
- `rtmpose/supplement_00N/native_pose_manifest.json`：來源、模型、隔離runtime、原圖尺寸、時間、操作範圍。
- `rtmpose/supplement_00N/native_keypoints.jsonl`：完整零起算時間軸、原圖pixel XY、原生score及缺值原因。
- 同目錄的`native_pose_summary.json`、`overlay_native.mp4`、`overlay_validation.json`。

本次交付另包含`review_all.html`及`comparison_summary.json`，提供原片／舊MediaPipe／新RTMPose並列觀看與描述性比較。
這些報告只讀已保存結果，不增加推論。

## 解讀限制

- `model_observed`表示模型直接輸出此座標；不表示人眼看見，也不保證對位正確。
- 原生score是SimCC軸最大回應的較小值，未校準；不沿用MediaPipe的0.5 visibility／presence gate。
- 沒有Z／visibility／presence的能力，保持null；不補成33點、不補腳跟／手指，也不插值長遮擋段。
- `quality_status=not_calibrated`、`usable_for_analysis=null`保持。
  坐標數量、與MediaPipe接近或看起來連續，都不能直接變成準確率或Phase2通過。
- 兩模型位置分歧只提供覆核線索。這五球沒有逐格關節XY真值，新模型正確率仍未量測。
- 關節在遮擋處即使有座標，也保留模型估計的身分；人工visible／not_observable／uncertain不被改寫。

## 資料與環境邊界

推論前先核對全部來源SHA、input metadata、七項人工覆核、操作範圍、全解碼格數及逐格時間。
第0格=0秒，按分數FPS計算時間，不以container start平移。
先取得已確認的原圖crop，再做模型要求的affine／padding；padding不讀框外像素。
正逆矩陣與crop原點均保存，輸出XY回到原圖，不把框外預測截到邊界。

影像處理留在`.venv-analysis`；模型透過現有隔離`.venv-rtmpose-response-20261016`執行。
兩個runtime不混用NumPy套件、不自動安裝或下載模型。握手不執行合成推論。
每個真實模型呼叫都有上限與journal；逾時、解碼或協定錯誤會停止並保存原因，不自動重試。

正式MediaPipe、原selector／gate、raw／GT、已完成的封存實驗及正式素材均保持。
本次接入計畫與停止規則見`phase2_live_native_pose_plan_20261020.md`。
