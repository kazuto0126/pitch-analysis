# 原生骨架的分析資料入口

本入口把已保存的 RTMPose 原生17點、逐格人物追蹤及人工 overlay 接受紀錄，
交給後續 Python 流程讀取。它使用既有資料，不執行人物偵測或 pose 推論。

## 使用方法

從專案根目錄執行，例如大谷第001球：

```powershell
pitch-analysis prepare-analysis-input `
  analysis_results/phase2_ohtani_seeded_skeleton_20261023_01/supplement_001/rtmpose/supplement_001 `
  input/shohei_ohtani/phase2_supplement_20261020_01/supplement_001.json `
  --subject-track analysis_results/phase2_ohtani_seeded_skeleton_20261023_01/supplement_001/subject_track.jsonl `
  --human-review annotations/skeleton_reviews/HSU_20261023/ohtani_shared_skeleton_acceptance.json `
  --output analysis_results/native_input_NEW/supplement_001
```

輸出目錄須為專案 `analysis_results/` 下的新位置。輸出包括：

- `native_analysis_input.json`：已核對的來源、metadata、骨架、追蹤、人工接受與使用範圍。
- `usage_summary.json`：座標存在／缺值、原生分數、追蹤狀態及人工接受的摘要。

原 `native_keypoints.jsonl`、人物框、影片、overlay 與 GT 透過來源 SHA 引用保存。
來源或人工紀錄不吻合時拒絕建立輸入，沒有使用呼叫端傳入的 `accepted=true` 取代人工證據。

第002球沿用已接受的續跑結果，使用其原始追蹤與獨立人工採用紀錄。
五球確切來源見 `config/analysis_inputs/ohtani_seeded_20261023.json`；不重跑002。

## 後續程式如何讀取

```python
from pathlib import Path
from pitch_analysis.analysis.native_input import load_native_analysis_input

pitch = load_native_analysis_input(
    Path.cwd(),
    "analysis_results/native_input_NEW/supplement_001",
)
for frame in pitch.iter_frames():
    native = frame.native.to_dict()  # 原生17點、原圖pixels、原分數與原座標狀態
    track = frame.tracking         # 同一格人物框追蹤
    assessment = frame.joint_assessments
```

讀取器核對來源與完整時間軸，提供不可被呼叫端改寫原始 snapshot 的資料物件。
影格順序為0起算，時間沿用 `frame_index / fractional_fps`，追蹤中斷與缺失格保留。

## 三種證據分開使用

| 證據 | 表示什麼 | 不能推導什麼 |
|---|---|---|
| 影片層人工接受 | 指定reviewer已接受這份來源對應的整支overlay | 每個關節、每格都有精確可見真值 |
| `model_observed` | 模型在該格有原生XY座標 | 人體關節一定可見、對位一定正確 |
| 關節可靠性／可見性／可用性未知 | 目前沒有足以設定逐點可信狀態的證據 | 自動改成可靠或自行認定為遮擋 |

模型未提供的Z／visibility／presence保持null，native score不當成visibility或正確率。
本入口不插值、不改座標、不補成33點；也不將原生分數硬套MediaPipe品質門檻。

## 與既有入口及Phase2的關係

`prepare-skeleton`／`extract-skeleton`負責取得原生骨架；本入口負責讀取已保存、已人工接受的結果。
`analyze-pitch`／舊CSV特徵及品質gate保留原有行為，供歷史重現。
本次接入不產生投球角度、事件預測、跨投手比較或真實3D指標。

要查看已保存原生資料的逐關節缺值、相鄰位移與人物框連續性，可接著執行
[`report-native-reliability`](native_reliability.md)。此命令會產生定位格號／時間的描述報告，
並保留本入口的逐點unknown與原生分數語義。

資料入口交付、影片人工接受、自動關節可靠性是三項獨立狀態。
Phase2是否通過仍依既有要求判定，不能由檔案成功讀取或模型有座標自動改為PASSED。
