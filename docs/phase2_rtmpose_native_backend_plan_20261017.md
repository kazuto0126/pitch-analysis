# Phase 2：原生後端輸出接入與驗收方案

日期：2026-10-17（台灣）。**PROPOSED — AWAITING_IMPLEMENTATION_APPROVAL**。

使用者已確認「允許規劃後端介面改動」，目前授權是規劃，尚未授權實作或正式替換模型。
本文件建議一版有界的接入：共用原生輸出contract、封存結果讀取、獨立overlay與比較報告。
**先接現有資料，不重跑模型；MediaPipe保持正式預設。**

## 1. 本版要解決什麼

把已驗證可讀的RTMPose原生17點，接成專案可辨識、可保存、可覆核的獨立輸出，
保留模型能力與來源差異，讓未來後端不必冒充MediaPipe33點。
本版完成的是「原生資料接入」，不是可對任意新影片執行的正式RTMPose分析後端。

[既有診斷](phase2_rtmpose_coordinate_diagnosis_20261017.md)顯示003投球肘座標有改善，
但major hold以外的髖部退步；原生回應提示亦已拒絕。
介面能接入不能直接解決「錯點仍被當成可用」；本版不以工程完成宣告Phase2通過。

## 2. 現況與最小接入邊界

| 現有位置 | 實際依賴 | 第一版處理 |
|---|---|---|
| `pose_estimator.py` | 33個固定順序點、Z、visibility、presence | 舊`PoseEstimator`／`PoseEstimate`及MediaPipe設定保持；新增原生型別另存模組 |
| `pose_capture.py` | 強制33點、按MediaPipe索引命名並寫原CSV | 保留；原生結果使用另一入口與JSONL |
| `subject.py`／PitcherSelector | MediaPipe索引與visibility／presence | 保留；原生讀取沿用已封存ROI來源，明列人工初始化前提 |
| `clean_pose.py`／`features.py` | 原v/p gate、插值、既有座標正規化 | 保留；原生結果不送入此流程、不沿用缺presence的舊CSV fallback |
| `pose_reliability.py`／`tracking_reliability.py` | 原gate、processed狀態與33點幾何 | 保留；原生只報描述性資料與未校準狀態 |
| `analysis/pitch.py`／`workflow.py`／`cli.py` | 正式analyze-pitch與keypoints-v1 | 保留；不新增`analyze-pitch --backend rtmpose` |
| `analysis/debug.py`及原overlay | MediaPipe連線與v/p畫點條件 | 保留；新增依原生topology繪圖的獨立overlay |

**最小版不必修改上述正式核心檔案。** 使用者允許規劃介面改動，
不代表必須擴大改動範圍。新介面與舊正式介面並存，避免未驗證的score進入舊gate。

## 3. 共用原生contract：名稱與語義先固定

建議新增`NativePoseFrame`／`NativePoseSource`與版本化`native-keypoints-v1`。
`NativePoseSource`是讀取已保存結果的來源介面，不宣稱會重新估計姿態。
第一版支援兩種明示topology：`mediapipe_33`與`coco_17`，各保留自己的原生點集。
未來真正的`NativePoseEstimator`執行介面及live RTMPose adapter另列範圍，不在本版實作。

| 必要資訊 | 規則 |
|---|---|
| backend／topology／schema | 名稱、版本、模型SHA、原生索引／解剖名稱及連線明確保存 |
| 原圖座標 | 共用比較空間為原圖pixel XY；保留原始座標表達與變換來源。原MediaPipe normalized XY×原寬／高；不clip超出原圖的預測 |
| frame／時間 | 完整保存每格frame_index、第0格及來源timestamp_ms／timebase；不刪漏格、不平移原時間軸、不修改pose_capture時間計算 |
| ROI／幾何 | RTMPose保留實際ROI來源SHA、人工初始化前提及正逆affine；原Full MediaPipe標`full_frame`，ROI／affine為null／not_applicable，不把CSRT框當其推論輸入。兩者保存原圖尺寸／像素來源SHA；不重新追蹤或用GT選框 |
| score | RTMPose原值及`min(max(Sx),max(Sy))`語義保留；不假定為0–1校準機率、不映射成visibility／presence |
| 能力描述 | RTMPose的Z／visibility／presence為unsupported，值保持null；不填0或1，不補成33點 |
| 座標狀態 | `model_observed`表示模型直接輸出，`missing`表示該原生點此格無有效座標；`interpolated`保留契約概念，但本版補點次數固定0 |
| 人工可見性 | 不放入prediction作模型事實。模型在遮擋處輸出XY不等於人工看得見；人工visible／not_observable／uncertain只在評估側讀取 |
| 自動可用性 | `quality_status = not_calibrated`、`usable_for_analysis = null`。原生座標存在不能自動產生reliable或通過舊quality gate |
| 不支援的關節 | heel／foot index／手指等屬topology未提供；與「提供此點但某格missing」分開，不混用分母 |
| 非finite／解碼失敗 | 保留原原因及二進位來源；JSON使用null，嚴格拒絕NaN／Infinity，不靜默改為0或補點 |

原MediaPipe sidecar可保留自己的v/p／relative Z，不能反向用它們為RTMPose補欄位。
原raw、clean與keypoints-v1內容完全保留，新contract另用檔名，不經舊CSV相容路徑。

共同十二關節只按解剖名稱對應，禁止依影像左右翻轉或GT挑點：

| 部位（左／右） | MediaPipe index | COCO index |
|---|---|---|
| 肩 | 11／12 | 5／6 |
| 肘 | 13／14 | 7／8 |
| 腕 | 15／16 | 9／10 |
| 髖 | 23／24 | 11／12 |
| 膝 | 25／26 | 13／14 |
| 踝 | 27／28 | 15／16 |

## 4. 建議實作檔案與工作順序

下列皆為**計畫路徑，尚未建立程式**。

| 檔案 | 內容 |
|---|---|
| `src/pitch_analysis/native_pose.py` | 原生型別、來源protocol、topology、能力描述、名稱／狀態驗證 |
| `src/pitch_analysis/native_pose_io.py` | native JSONL／manifest讀寫、SHA與完整frame驗證；只寫新輸出目錄 |
| `src/pitch_analysis/native_pose_sources.py` | 封存MediaPipe33與RTMPose17結果的唯讀adapter；不import或啟動推論runtime |
| `src/pitch_analysis/native_pose_review.py` | 原生連線overlay與描述性coverage／缺值統計；不套用舊confidence gate |
| `src/pitch_analysis/contracts/schemas/native-keypoints-v1.json` | 新prediction schema；不是第二套人工GT schema |
| `scripts/export_native_pose_review.py` | 明確選用的獨立入口，讀已封存五球、輸出兩種原生結果與比較 |
| `tests/test_native_pose_*.py` | 原生contract、來源／frame binding、能力／缺值、topology、overlay及舊gate隔離 |
| 新使用文件與status更新 | 啟用方式、前提、工程驗收及仍未通過的可靠性狀態 |

工作分三段，一次完成這個確認範圍：

1. contract／來源adapter與必要測試。
2. 讀既有592格，產生兩後端各自的原生資料、五支RTMPose overlay及003十二關節比較；MediaPipe引用原overlay。
3. 完整測試、來源保護核對、文件、獨立checkpoint commit／push，回報並停止。

實作時以新`codex/phase2-native-pose-interface`分支從目前已保存checkpoint開始。
不改已凍結的RTMPose response量測／校準／評估腳本，也不重開Heavy或分類器。

## 5. 固定輸入、輸出與執行上限

輸入只有原正式五球及既有封存資料：

- `phase2_rtmpose_response_execution_20261017_02.json`與完成結果／SHA作來源綁定。
- RTMPose現有592格的native keypoints、SimCC來源引用及SDK geometry，不重新解碼取代封存座標。
- 原MediaPipe33 raw／capture／metadata，保留原selection資訊；新增pixel表示不覆寫原值。
- 003既有人工XY：1,205 visible／173 not_observable／2 uncertain，全115格保存。
- 其他四片canonical只描述原Full可靠性，**不得用來計算RTMPose正確／錯誤率**。

本版上限：**新模型推論0、重新校準0、新標註0、新tracker0、模型下載0**。
既有完整測試可照常重跑原MediaPipe E2E，與原生接入的新推論次數分開記錄。
不讀取或分析8顆交付候選、不修改共用交付資料夾。

新輸出例如：`analysis_results/phase2_native_interface_<timestamp>/`。
每球依backend分目錄保存原生manifest／`native_keypoints.jsonl`／`native_pose_summary.json`；
RTMPose另產生`overlay_native.mp4`，共**五支新overlay**。MediaPipe只保存原overlay的路徑／SHA引用，
不重建或覆寫它。兩後端資料分開，總目錄保存`backend_comparison.json`與`integration_summary.json`。
人工GT只引用原檔與SHA，不建立新模板或重寫人工內容。

## 6. 驗收A：介面接入是否完成

以下是工程／資料保真驗收，不是新的模型準確度門檻。

1. **舊流程維持。** 完整既有suite＋新增必要測試；正式五球E2E結果與原重大提示2／0／19／5／3維持。
   原core、threshold、gate、raw、GT及前輪凍結程式／結果SHA不變。
2. **資料完整。** 五球87／175／115／114／101格，總592；不刪第0格、缺值或困難區段。
   每球逐格frame／pixel／timebase／ROI／模型SHA可追查；變更或不符時明確拒絕，不自動重算。
3. **原生語義正確。** RTMPose17點名稱／順序／連線與封存值保持，無padding33、fake v/p/Z、score clipping／normalization或舊gate套用。
4. **座標可重現。** 新表示回到原圖XY後與封存座標逐點吻合；若序列化引入差異，必須列出數值與原因，不用它宣稱新準確度改善。
5. **缺值與能力分開。** unsupported、missing、model_observed、未校準、人工可見性可分辨；本版interpolated數為0。
6. **覆核輸出可用。** 五支RTMPose新overlay能解碼、frame／時間對齊、按COCO連線畫點；圖上明示原生模型估計及未校準，
   不因畫出骨架便顯示可靠通過。實際檢查繪圖／對齊，不新增人工GT。
7. **比較保留退步。** 003十二關節同格可見集合、原major hold內外、mean／median／P95／max、逐格更近／更遠及缺值均報告；
   重現既有肘27.7461→7.3101px及髖部非major退步9.1535→13.3563、7.4754→11.7197px。
   其他四片精確XY誤差保持null，不產生任意總分或排名。

任一項失敗先修相容性／保存問題；不得為此調整模型、信號或原門檻。
修不好的記錄原因，`native interface integration = NOT PASSED`。

## 7. 驗收B：Phase2自動可靠性是否通過

**本版接入完成也不會自動讓Phase2 PASSED。**

- 原回應提示仍不採用；003/104及原Full gate接受的肘72／腕49人工錯點仍是既有問題。
- RTMPose在003的部分定位改善及髖部退步皆保留；不能用單片平均降低或畫面有骨架代替驗收。
- 新原生score沒有經過品質校準，不能借用0.5的舊v/p gate；原生可用性未定不是大量拒點後提高成績。
  本版不報原生新TP／FN／FP成效，也不影響原正式資料的可用數。
- CSRT框有人工初始化前提，輸出穩定不等於新的自動身分證明；五片沒有identity-switch陽性也不假造敏感度。

若工程驗收A全部成立，只標記`native interface integration = PASSED`，
**Phase2 automatic reliability維持NOT PASSED**。
後續若要讓RTMPose座標成為正式分析來源，必須先另行確認新的後端品質／使用判斷範圍與凍結驗收方式。
本方案不新增零錯誤條件、不要求更多標註，也不承諾僅改介面即可修好錯點接受問題。

## 8. 核准與停止點

這次僅交付方案，沒有實作、推論或測試重跑。
使用者確認本文件後，才開始第4–6節的有界接入工作。
完成A後回報、commit／push並停止；不自行開始live後端、正式模型替換、score gate校準、
逐格兩模型混合、新提示規則、其他模型搜尋或Phase3。
