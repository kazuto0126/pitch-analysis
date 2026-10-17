# Phase 2：RTMPose原生位置回應的單次離線提案

2026-10-16。**PROPOSED — AWAITING_USER_CONFIRMATION**。
沒有下載、安裝、執行RTMPose或變更正式模型。
依使用者原先「新模型benchmark先提出方案」的要求，確認本文件後才執行。
Heavy與13特徵分類器維持封存，不調整失敗組合。

## 1. 為什麼需要不同資訊

[可見性核對](phase2_visibility_gap_audit_20261016.md)確認，原gate通過且Heavy仍漏報的點中，
至少58肘／27腕有原reason明示可見且無已知XY衝突；不能全部歸為自然遮擋。
003另有8格可見性來源差異，原記錄及主要評估分母保持，不用改標籤改善成績。

下一個問題是：**原MediaPipe標點的位置，是否得到另一個模型的影像位置回應支持？**
本輪提議讀RTMPose的原生SimCC兩軸回應，保留完整向量；
它比只保存最大值位置多一組資訊，但仍是模型回應，不是真實可見性或身分證明。
官方提供ONNX CPU推論及SimCC輸出範例：
[官方部署指南](https://github.com/open-mmlab/mmpose/blob/main/docs/en/user_guides/how_to_deploy.md)、
[原生回應與解碼範例](https://github.com/open-mmlab/mmpose/blob/main/projects/rtmpose/examples/onnxruntime/main.py)。

## 2. 一個模型、一套環境

- 固定 **RTMPose-m Body7，256×192，20230504/e48f03d0，原生COCO17點**。
  官方[model zoo](https://github.com/open-mmlab/mmpose/blob/main/projects/rtmpose/README.md)有該版本ONNX SDK。
- 固定官方archive：
  `https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-m_simcc-body7_pt-body7_420e-256x192-e48f03d0_20230504.zip`
- 新獨立Python3.12／ONNXRuntime CPU環境，無system site-packages；不改分析或MoveNet環境。
  只使用官方wheel、不從source build；下載總上限250MB，不安裝Torch／MMCV／完整MMPose訓練工具。
- 原生17點與一種原生score保留，不補成33點、不偽造visibility／presence／Z。
  不接正式PoseEstimator、不替換MediaPipe、不修改原selector。
- 本機分析環境沒有ONNXRuntime／RTMPose；CPU相容性尚未確認。
  相容性關只做一次合成輸入推論與座標contract檢查，無真人GT。
  若模型shape／SDK metadata／runtime不符就停止回報，不另換版本或backend。
- 下載後先保存權重、SDK設定、授權與runtime版本／SHA；先跑必要合成測試並凍結來源，才做真實五球。
  不依結果挑模型版本、輸入大小或色序；也不宣稱COCO性能適用後方投球。

## 3. 沿用已核對的主體框，不新增追蹤器

使用既有五片封存CSRT的`usable_rectangle_xywh`，592/592格均存在。
001／002／004／005來自`phase2_assisted_roi_cohort_20261010_01`，003來自`phase2_subject_assignment_20261010_01`；
確切path／SHA在execution再綁定。起點曾由人工確認，這項人為初始化前提必須明列，不能稱全自動。
不重跑CSRT、不讀人工關節／事件挑框，不增加detector、ReID或候選解歧義規則。

沿官方top-down流程使用固定bbox padding1.25、調整至192:256比例、零旋轉、bilinear affine、
保存正逆矩陣；這是新模型的輸入轉換，不修改原片或先前ROI實驗。
以SDK與對應training config核對RGB／mean／std、float32 NCHW、SimCC split ratio2。
若官方範例與SDK色序描述有差異，先依模型SDK及training contract核對，未解決就停，
不跑兩種色序後挑成績。原圖像素／frame／timestamp的來源SHA仍逐格核對。

## 4. 只驗證一個新訊號

固定關節對應：右肘COCO index8、右腕index10，依原metadata右投；六個重要關節與全部17點都保存作診斷。
每格只有一個既有主體框、一次RTMPose呼叫，合計上限592；不flip、不augmentation、不加warmup真人推論。

主訊號是原Full點在RTMPose兩軸原生向量中，距離最大回應的差值：

`deficit = (max(Sx) - Sx[jx]) + (max(Sy) - Sy[jy])`

原Full source XY經已保存affine映到模型座標；`jx=floor(2*x+0.5)`、`jy=floor(2*y+0.5)`。
Full點缺失、向量非finite或bin超出原生向量範圍時，deficit=null／insufficient_evidence。
不clip邊界、不插值原關節、不補遮擋點、不因原生score較低移除難格。
完整SimCC向量、原生argmax／score、Full取樣bin、affine與deficit都保存。
Deficit不是校準機率；低差值、兩模型同意或沒有提示都不能認證可靠。

只用四片canonical reliable且deficit可量測的非seed列取最大值，
測試片deficit嚴格大於該最大值才提示。整片五折，不用query GT校準。
不加入距離、entropy、時間特徵或分類器；不試其他界線、溫度、窗口或組合。
沒有training reliable配對就明列fold失敗，不換方法。

## 5. 一次完整評估與固定決策

全部592格保存，主要分母587格／關節。五份OOF封存後才讀query canonical GT及003XY。
Canonical只判原Full的可靠／不可靠，不當RTMPose正誤GT；not_observable／uncertain另列。
所有模型缺值／證據不足仍留FN／TN主要分母，原major hold與重大覆核提示保留。
003可見性來源差異另列，不能改標籤、刪格或降低門檻。

每片、合計、排除003及003作測試分開報：TP／FN／FP／TN、gate通過錯點新增提示、
好點額外提示、支持／人工可靠保留、未知／缺值／框外bin、與原重大提示重疊和聯集增量。
003 XY只報相同配對點的連續誤差與coverage，其他四片精確誤差null。

| 採用條件（每關節獨立） | 肘 | 腕 |
|---|---:|---:|
| TP | ≥17 | ≥27 |
| FP | ≤1 | ≤1 |
| 非003 TP | ≥10 | ≥23 |
| gate通過錯點提示數 | >7 | >8 |

另須五fold有效，至少兩支非003各自TP高於原score-only與sample-maximum的較高值。
基準及數字沿用前輪，不因Heavy失敗降低要求。
至少一項符合就提出該關節附加覆核提示的採用範圍，等核准；不自動換模型或宣布整體Phase2通過。
兩者均未達就封存本輪、停止調整這個資訊來源，不追加小規則或模型大小搜尋。
這是新提示的採用規則，不新增Phase2整體的零錯誤／新投手／更多GT驗收條件。

## 6. 確認的完整範圍與停止點

核准後一次完成：隔離相容性關→固定五球量測→整片五折→獨立核對與完整suite→文件／commit／push。
相容性通過後不再拆成多輪pilot；失敗或成效不符即按上文停止。
新輸出獨立保存，不覆寫Heavy／MoveNet／原Full或人工資料。
不新增人工標註，不分析8顆交付候選，不進Phase3。
目前只完成資料核對及本提案，尚未實作或執行新模型試驗。
