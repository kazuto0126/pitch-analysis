# Phase 2：原生17／33點接入第一版

2026-10-18（台灣）。使用者已明確核准「第一版接入實作」，依
[已確認方案](phase2_rtmpose_native_backend_plan_20261017.md)完成。
原方案保留核准前原文與SHA；核准及實際來源另記於execution／result紀錄。

**Native interface integration = PASSED。**
**Phase2 automatic reliability = NOT PASSED。**

本版接入封存資料，不是任意新影片的live RTMPose後端。
正式MediaPipe、PitcherSelector、confidence gate、threshold、插值／平滑、raw及人工GT均保持。

## 1. 已完成的接入

- 共用`NativePoseFrame`／`NativePoseSource`介面及`native-keypoints-v1`，支援原生`mediapipe_33`／`coco_17`。
- 原生資料獨立保存；RTMPose沒有補成33點，Z／visibility／presence保持unsupported／null。
  原始score保留，不正規化、不當visibility或校準機率。
- MediaPipe保留整圖推論與原normalized欄位，新增原圖pixel表示；不把CSRT裁切框當成其模型輸入。
  RTMPose保留實際ROI、人工初始化前提、SDK正逆affine與SimCC來源引用。
- 模型直接輸出標`model_observed`，缺值標`missing`；不提供的關節與missing分開。
  兩後端新增路徑皆`quality_status=not_calibrated`、`usable_for_analysis=null`，沒有套用或改寫舊gate。
- 五支RTMPose H.264／yuv420p overlay已產生；MediaPipe只引用既有overlay，沒有重建或覆寫。
- 來源、模型、逐格像素／時間／ROI／raw CSV與原生結果SHA已核對；變更資料時拒絕接入，不自動重算。

本次接入：**新RTMPose推論0、tracker0、校準0、標註0、模型下載0**。
完整測試照常執行原MediaPipe E2E，與接入的新推論次數分開。

## 2. 五球資料與overlay

每個後端完整保留592格，包含每片第0格及原缺值。
下表為原生資料欄位數，**不是通過品質門檻的關節數**。

| 影片 | 格數 | MediaPipe欄位／其中missing | RTMPose欄位／其中missing | 新overlay |
|---|---:|---|---|---|
| pitch_001 | 87 | 2,871／0 | 1,479／0 | [開啟](../analysis_results/phase2_native_interface_20261018_01/pitch_001/rtmpose/overlay_native.mp4) |
| pitch_002 | 175 | 5,775／0 | 2,975／0 | [開啟](../analysis_results/phase2_native_interface_20261018_01/pitch_002/rtmpose/overlay_native.mp4) |
| pitch_003 | 115 | 3,795／0 | 1,955／0 | [開啟](../analysis_results/phase2_native_interface_20261018_01/pitch_003/rtmpose/overlay_native.mp4) |
| pitch_004 | 114 | 3,762／66 | 1,938／0 | [開啟](../analysis_results/phase2_native_interface_20261018_01/pitch_004/rtmpose/overlay_native.mp4) |
| pitch_005 | 101 | 3,333／33 | 1,717／0 | [開啟](../analysis_results/phase2_native_interface_20261018_01/pitch_005/rtmpose/overlay_native.mp4) |
| 合計 | **592** | **19,536／99** | **10,064／0** | **5支** |

原MediaPipe99個缺值完整保留，沒有補點。RTMPose有11個畫面外座標，保留原值、overlay不把它們clip到邊界。
RTMPose都有座標並不表示人體關節都可見，更不表示100%可靠。
每支新overlay已整片解碼，格數、原尺寸及時間對位均吻合；最大毫秒四捨五入差約0.333334ms，沒有時間平移。

### 實際畫面檢查

根代理實際觀看五張contact sheet，每支抽查6格，共30格；另有全部592格的程式解碼／像素／時間驗證。

| 影片 | 實際觀看frame |
|---|---|
| pitch_001 | 0、17、34、52、69、86 |
| pitch_002 | 0、35、70、104、139、174 |
| pitch_003 | 0、23、46、68、91、114 |
| pitch_004 | 0、23、45、68、90、113 |
| pitch_005 | 0、20、40、60、80、100 |

文字`cached RTMPose / COCO17 / NOT CALIBRATED`、frame與timestamp可讀；原生連線與原圖對齊，
沒有使用MediaPipe手指／foot-index連線。原模型的遮擋估計與不自然位置保持，沒有人工修點。
這是繪圖／對齊檢查，**不是新增人工GT，也不宣稱逐格人工判讀了所有關節可靠性**。

## 3. 比較沒有掩蓋退步

003原人工資料1,380列仍為1,205 visible／173 not_observable／2 uncertain；不可觀測與不確定不計精確誤差。
新增輸出重現同格、同關節、可見集合的既有結果：

| 關節／範圍 | 可比格 | Full平均誤差px | RTMPose平均誤差px |
|---|---:|---:|---:|
| 投球肘，全片非seed | 92 | 27.7461 | 7.3101 |
| 投球腕，全片非seed | 58 | 26.6556 | 16.8405 |
| 左髖，原major hold以外 | 96 | **9.1535** | **13.3563** |
| 右髖，原major hold以外 | 96 | **7.4754** | **11.7197** |

十二關節、major區段內外、mean／median／P95／max及逐格更近／更遠均保留在`backend_comparison.json`。
其他四片精確XY誤差保持null；原Full的定性GT不當RTMPose正誤標籤，不產生新模型TP／FN／FP。
沒有任意總分、排名、依GT逐格選模型或混合座標。

## 4. 驗收與來源保護

- 45項新增測試全數通過，涵蓋contract、IO、來源鏈、unsupported／missing、低分點保留、拓樸、
  exclusive寫入、SHA／路徑／時間錯誤拒絕、實際H.264編解碼與可見XY比較。
- 完整suite **963項：961 passed、0 failed、0 errors、2 skipped**，76.699秒、exit0。
  兩skip為Windows file symbolic link能力；junction測試實際執行。
- 正式五球E2E重大提示仍2／0／19／5／3；原正式流程與既有門檻未改。
- 獨立重算19,536個MediaPipe原生欄位、10,064個RTMPose原生欄位與592份SimCC，
  原CSV→pixel、RTMPose複製、argmax／分數／逆affine的最大差異均**0**。
- 003全部1,380逐點列與十二關節三分組摘要獨立核對，重現前輪診斷。
- 646個唯一prediction來源SHA、736份audit讀取來源前後核對；467個保護來源及62個上游引用保持。
- 正式模型／selector／clean／feature／reliability／workflow／CLI及舊contracts registry未修改。
  8顆交付候選未送入本次接入或分析，仍未升格。

最終驗收以`integration_acceptance.json`及[版本化結果](evaluation_plans/phase2_rtmpose_native_interface_result_20261018_01.json)為準；
`integration_summary.json`保留匯出完成、等待獨立audit的階段快照，不覆寫其來源紀錄。

## 5. 使用方式與輸出

本次輸出：`analysis_results/phase2_native_interface_20261018_01/`。

```text
pitch_001..pitch_005/
  mediapipe/  native_pose_manifest.json / native_keypoints.jsonl / native_pose_summary.json
  rtmpose/    上述三檔 + overlay_native.mp4 / overlay_validation.json
backend_comparison.json
native_export_seal.json
integration_summary.json       # 匯出階段快照
integration_acceptance.json    # 最終工程驗收
independent_audit.json
visual_review/                 # contact sheets與實際抽查紀錄
full_suite.log
```

需要已封存的原影片、模型及cache來源，單純clone程式碼不會取得這些本地大型資料。
此入口不接受任意新MP4，不會下載或執行RTMPose。
若要重現，指定全新輸出目錄；既有目錄會拒絕，不覆寫：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts/export_native_pose_review.py `
  docs/evaluation_plans/phase2_rtmpose_response_execution_20261017_02.json `
  docs/evaluation_plans/phase2_rtmpose_response_result_20261017_01.json `
  analysis_results/phase2_native_interface_NEW
```

新檔為四個`native_pose*.py`模組、一份schema、一個獨立export入口、五個測試檔；
`.gitattributes`僅增加新檔LF規則。未新增正式CLI backend選項或推論依賴。

## 6. 停止位置

接入工程已通過，但原生score仍未校準，原提示訊號仍拒絕，003/104及原Full錯點接受問題仍保留。
**Phase2 automatic reliability = NOT PASSED**；沒有降低驗收、重開失敗訊號或將介面成功當成模型採用。
依核准範圍完成此版後停止，不開始live後端、正式模型替換、score gate校準、新標註或Phase3。
