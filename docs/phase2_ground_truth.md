# Phase 2 人工 Ground Truth Review

更新：2026-09-30。沿用 **ground-truth-v1**，以 `review_profile: phase2_full_review`
擴充完整人工覆核欄位，舊版模板仍可讀取。原始／處理後 prediction 均不覆寫。
目前人工覆核 **2/5**：`pitch_001`、`pitch_002` 已由 HSU 標為 `reviewed`，格式／來源驗證通過；
`pitch_003`–`pitch_005` 尚未覆核。下一支為 `pitch_003`，不自動填入人工判斷。
尚未執行 prediction comparison；標註完成與格式有效不代表 Phase 2 通過。
後續工作順序及 Clipper 接入條件記錄於 [current status](current_status.md)。

## 人工覆核紀錄 — HSU（2026-09-28）

`pitch_001` 的 ground truth 由 **HSU 親自觀看影片、overlay 與逐格對照圖，逐項判讀並手動填寫**。
本次覆核涵蓋 0–86 格的主體追蹤、六個重要關節的可靠性／遮擋區間，以及投球事件的影格或範圍。
HSU 也逐次指出漏標、錯位及關節誤連到裁判腳附近等問題，並確認可見與不可見的區別。
無法清楚判斷的部分保留不可觀測狀態或事件範圍。

Codex 協助提供檢查素材、解釋欄位、整理 HSU 已表達的觀察及驗證 JSON 格式；
人工判斷來自 HSU，並非由模型自動產生後直接當作 ground truth。

- Reviewer：`HSU`；方法：`manual_video_review`。
- JSON 記錄的完成時間：`2026-09-27T16:01:04Z`（臺灣時間 2026-09-28 00:01:04）。
- 人工標註檔：[pitch_001/ground_truth.json](../analysis_results/phase2_yamamoto_20260925_01/ground_truth/pitch_001/ground_truth.json)。
- 首次保存此標註的 checkpoint：[`f48fc0c`](https://github.com/kazuto0126/pitch-analysis/commit/f48fc0cb0353c18835691f13a2670051d76b4141)。
- 本紀錄涵蓋已完成的 `pitch_001`，當時整體進度為 **1/5**；其餘四支仍待人工覆核。

## 人工覆核紀錄 — HSU（2026-09-30）

HSU 親自檢查 `pitch_002` 原片、overlay 與 0–174 格的對照圖，逐段提供判斷，
並手動填寫同一份 [pitch_002/ground_truth.json](../analysis_results/phase2_yamamoto_20260925_01/ground_truth/pitch_002/ground_truth.json)。
Codex 協助解釋欄位、依 HSU 的回答提供填寫片段與行號，並做只讀格式／來源驗證。

- 主體全程在投手身上，未見 identity switch、明顯 track break 或整體姿勢錯亂。
- 右肩、左髖、左膝與左腳踝全片標記正確。
- 右手肘 140–141、144–155、166–167 格無法清楚觀察，其餘區間確認標記正確。
- 右手腕 18–19 格可見但漏標；72–92 格藏在手套內；144–174 格被身體遮住。
- 事件：準備開始 74、最高抬腿 118、落腳 140、出手範圍 141–143、收尾結束 168。
- 完成時間：`2026-09-30T12:47:32Z`（臺灣時間 2026-09-30 20:47:32）。
- `annotation_status = reviewed`；完整關節區間、事件順序、schema 與原片 SHA-256 驗證通過。

人工不可觀測區間保留原判斷；未自行填入 confidence 數值或修改 prediction。
目前進度 **2/5**，尚未執行 prediction comparison，Phase 2 仍未通過驗收。

## 從哪裡開始

本次入口：`analysis_results/phase2_yamamoto_20260925_01/review_helper_20260926_01/START_HERE.md`。
Baseline root：`analysis_results/phase2_yamamoto_20260925_01/`。

| 影片 | 唯一待填 ground truth（相對於 baseline root） | Frame index |
|---|---|---|
| pitch_001 | ground_truth/pitch_001/ground_truth.json | 0–86 |
| pitch_002 | ground_truth/pitch_002/ground_truth.json | 0–174 |
| pitch_003 | ground_truth/pitch_003/ground_truth.json | 0–114 |
| pitch_004 | ground_truth/pitch_004/ground_truth.json | 0–113 |
| pitch_005 | ground_truth/pitch_005/ground_truth.json | 0–100 |

這五份既有 `ground_truth.json` 是唯一人工標註來源，也納入 Git 保存覆核進度；
不另外建立第二套可編輯標註。影片、overlay、逐格圖片和其他分析輸出仍只保存在本機。
還原或換機時，先用每份 JSON 的影片 SHA-256 核對來源，勿把另一支影片套到既有標註。

正式原片：`input/yoshinobu_yamamoto/phase1_final/pitch_00N.mp4`。
Overlay：baseline root 下 `predictions/yoshinobu_yamamoto/pitch_00N/overlay.mp4`。

每支 helper 有 `review_checklist.md`、全尺寸逐影格 `frames/frame_XXXX.jpg`、
每頁 12 frames 的 `contact_sheets/`，以及 `frame_index.csv`。
全部 592 個影格皆匯出，沒有用模型挑選事件關鍵影格。
對照圖左邊是原片、右邊是既有 raw overlay，下方是六關節的處理後模型狀態。
全尺寸圖保留原始影像尺寸；contact sheet 只適合定位，關節判讀請開全尺寸圖。

Frame index 從 **0** 開始，區間兩端皆包含。時間為剪輯內時間，非轉播絕對時間。
CSV 保留 metadata 的毫秒數，圖片顯示至三位小數秒。
播放器暫停時間不足以精確對應影格，標註請以對照圖的 frame index 為準。

## 逐支檢查流程

依序 pitch_001 → 002 → 003 → 004 → 005，每支分四輪：

1. **先看完整原片**：確認投手位置、身體側別、可見性與投球動作。
   先形成視覺判斷再看模型，減少模型位置影響人工判斷。
2. **完整播放 overlay**：主要 skeleton 是否一直屬於投手；是否換人、消失／重現、
   大部分身體點錯位。看前後影格區分快速動作與追蹤跳動。
3. **逐影格檢查六關節**：contact sheet 定位後開啟全尺寸圖，配合前後影格，
   合併判斷相同的連續區間。每個關節都覆蓋全片，不能只標異常。
   throwing／lead side 是身體解剖側別，不是畫面左右；每支清單有 metadata 對應。
4. **填事件與不確定性**：清楚才填 exact frame；只能定位一段就填 range；
   無法確定用 uncertain；無影像證據用 not_observable。最後只做格式／來源驗證，
   等全部人工完成才執行 prediction comparison。

請看完整影片，不要只看模型警示區間。無警示也可能追錯人。

## 必須由你填寫的欄位

`source_video`、SHA-256、frame count、schema/profile 和 provenance 的 method/guidelines_version
已綁定來源，不需修改。開始時改 `annotation_status` 為 `in_progress`，填
`provenance.reviewer`；完成前 `reviewed_at_utc` 保持 null。

| 人工判斷 | labels 欄位 | 填法 |
|---|---|---|
| skeleton 是否為正確投手 | pitcher_correctly_selected + pitcher_selection_review | 可判斷時 true/false；不確定時布林為 null，在 review 物件寫 uncertain/not_observable |
| identity switch | identity_switch_intervals | 換到其他人的區間及原因 |
| 明顯 track break | track_break_intervals | 骨架追蹤中斷區間；與換人分開 |
| throwing shoulder | throwing_shoulder_reliability | 全片分段 |
| throwing elbow | throwing_elbow_reliability | 全片分段 |
| throwing wrist | throwing_wrist_reliability | 全片分段 |
| lead hip | lead_hip_reliability | 全片分段 |
| lead knee | lead_knee_reliability | 全片分段 |
| lead ankle | lead_ankle_reliability | 全片分段 |
| major pose failure | major_pose_failure_intervals | 骨架大幅錯位、缺失、不可用區間 |
| throwing arm 遮擋 | throwing_arm_occlusion_intervals | 因遮擋無法核對的區間；note 指明肩／肘／腕 |
| 準備開始 | events.preparation_start | 若真正開始在片外，不強迫填 0 |
| 最高抬腿 | events.leg_lift | maximum/peak；若有平台可填範圍 |
| 前腳落地 | events.foot_plant | 首次可見接觸附近，不推斷受力開始 |
| 大致出手 | events.approximate_release | 球被遮住可 uncertain/not_observable |
| 收尾結束 | events.follow_through_end | 動作完成／回復穩定附近；片尾截斷則不可觀測 |

`pitcher_correctly_selected = true` 表示有選 skeleton 時都屬於投手；沒骨架本身不等同
identity switch。曾選到其他人即 false，並說明區間。

### 空白、無異常、不確定

- `null`：尚未檢查，不能當成沒有問題。
- `[]`：已檢查全片且確認沒有該類異常，只適用 switch/break/failure/occlusion 區間欄。
- `uncertain`：看過但模糊、重疊或邊界不清，仍無法可靠決定。
- `not_observable`：沒有足夠影像證據，例如完全遮擋、事件在片外。
- `confidence`：人工信心，0–1 或 null；不強迫量化，與模型 confidence 無關。
- `note` / `reason`：記錄判斷依據；不可靠、不確定、不可觀測及事件範圍必須有說明。

以下 JSON **僅為語法範例，數字不是這五支影片的答案**。

### 主體判斷

```json
"pitcher_correctly_selected": null,
"pitcher_selection_review": {
  "status": "uncertain", "confidence": null,
  "note": "填寫無法確認的原因與影格"
}
```

可確定時用 `status: annotated`，布林欄填 true 或 false。

### 異常區間

```json
[
  {"start_frame": 20, "end_frame": 24, "status": "confirmed",
   "reason": "人工觀察到的問題", "confidence": 0.8, "note": "補充依據"},
  {"start_frame": 25, "end_frame": 27, "status": "uncertain",
   "reason": "邊界不明", "confidence": null}
]
```

switch/break/failure/occlusion 都用此格式，status 是 confirmed/uncertain/not_observable。
同一欄位區間排序且不重疊，不同欄位可重疊。不能排除問題時列 uncertain/not_observable，
不要省略而視為正常；單一影格用 start_frame = end_frame。

### 六關節 reliability

每個關節從 frame 0 到最後一格連續覆蓋，狀態分為：

- `reliable`：原片可辨識關節，預測位置與可見位置合理相符。
- `unreliable`：影像足以顯示模型錯位或缺失，無法信任座標。
- `uncertain`：影像／預測曖昧，無法確定是否合理。
- `not_observable`：原片沒有位置證據，不宣稱模型一定錯或一定對。

```json
[
  {"start_frame": 0, "end_frame": 9, "status": "reliable",
   "reason": "可辨識且骨架合理對位", "confidence": 0.8},
  {"start_frame": 10, "end_frame": 19, "status": "not_observable",
   "reason": "關節被身體遮住", "confidence": null}
]
```

上例僅示意 20-frame 影片，不可直接套用正式影片。
reviewed 可保留 uncertain/not_observable；填完不代表全部可靠。

### 事件：exact / range / uncertain / not observable

每個 event 填其中一種物件：

```json
{"status": "annotated", "frame_index": 42, "confidence": 0.9, "note": "單格清楚"}
```

```json
{"status": "annotated", "frame_index": null,
 "frame_range": {"start_frame": 40, "end_frame": 44},
 "confidence": 0.6, "note": "確定在此區間，無法定位到單格"}
```

```json
{"status": "uncertain", "frame_index": null,
 "frame_range": {"start_frame": 40, "end_frame": 46},
 "confidence": null, "note": "可能在此區間，影像不足以確認"}
```

```json
{"status": "not_observable", "frame_index": null,
 "confidence": null, "note": "說明遮擋或片外原因"}
```

uncertain 可不提供 range；舊 `not_visible` 仍接受，意義同 not_observable。
exact 與 range 不得同時填；not_observable 不假填範圍。
範圍可重疊，只要存在合理時間先後順序，驗證器不逼你拆成精確單格。

## Overlay 與圖片能／不能判讀什麼

可以判讀骨架是否在投手身上、是否跳到其他人、明顯中斷／錯位、可見關節的 2D 對位，
以及可見的落腳與事件附近。單張圖不足以確認換人，必須看連續影格；速度需搭配原片播放。

不能可靠推出完全遮住的肘／腕真實座標、球不清楚時精確出手影格、片外事件、真實 3D 角度／力學、
僅憑骨架確認真實球員身分，或證明來源原生速度。證據不足就保留 uncertain/not_observable。

**兩種模型資料不可混淆**：原 overlay 畫 raw landmarks，使用視覺化門檻；
CSV／圖下方 observed/interpolated/missing 是處理後 keypoint 狀態。
因此 missing 關節仍可能在 raw overlay 有線或點。observed 只代表通過既有 gate，
不代表真實可見或位置正確；interpolated 是補點，不是人工觀測證據。

## 完成與只驗證格式

全片完成後設定 `annotation_status: reviewed`，`provenance.reviewed_at_utc` 填實際完成 UTC
時間（Z 或 +00:00），不要複製預填時間。驗證檢查六關節完整區間、事件順序、SHA-256、reviewer
及狀態一致性；不證明答案正確，也不代表 Phase 2 通過。

每支替換 pitch ID，從專案根目錄執行：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\validate_ground_truth_review.py analysis_results\phase2_yamamoto_20260925_01\ground_truth\pitch_001\ground_truth.json input\yoshinobu_yamamoto\phase1_final\pitch_001.mp4
```

只讀取／驗證，不執行模型或 prediction comparison。
也可把人工判斷用影格區間與備註交回，再依據你的答案整理 JSON，不補猜缺少部分。

**本次停止於人工覆核準備。** 舊比較程式只處理兩關節和確定異常，目前對 full-review profile
明確停止，避免忽略新欄位或把 uncertain 當成確定標籤。人工覆核完成後，才擴充比較讀取，
保留六關節、track break、遮擋、事件範圍與不確定區間，產生獨立 comparison report。
本 baseline 沒有自動事件預測或人工 X/Y 座標，事件時間誤差與座標誤差仍不能量測。

## 重建檢查素材（開發／追溯）

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts\prepare_ground_truth_review.py input\yoshinobu_yamamoto\phase1_final analysis_results\phase2_yamamoto_20260925_01 analysis_results\phase2_yamamoto_20260925_01\review_helper_NEW
```

輸出目錄必須全新，五模板仍須 unreviewed；進行中／已完成標註會拒絕。
腳本核對來源雜湊、frame index、timestamp、模型狀態與完整解碼，再備份並只補 null 欄位。
`template_backups/` 是擴充前原始空白檔案，不是第二套待填標註。
`preparation_manifest.json` 保留來源雜湊、模板擴充前後雜湊與數量。
