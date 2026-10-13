# Phase 2 收尾：已交付能力與自動可靠性限制

日期：2026-10-13（台灣）。

**Phase 2 baseline／人工覆核／評估／本次授權的有限修復工作 = COMPLETE WITH KNOWN LIMITATIONS。**

**Phase 2 automatic reliability = NOT PASSED；Phase 2 = NOT PASSED；accepted = false。**

本次將已完成成果整理成可停止、可追查的交付點。自動可靠性發布維持阻擋，
沒有宣告 Phase 2 穩定或通過；Phase 3 未開始。

## 一、目前可以使用什麼

- Yoshinobu Yamamoto 正式五球仍為 `pitch_001` 至 `pitch_005`，共 **592 格**。
- HSU 的五份 canonical GT 均已完整覆核：**5/5 reviewed**，六個重點關節共 **3,552 個逐格判讀**。
- `pitch_003` 的十二關節人工座標覆核涵蓋全部 115 格，共 1,380 個參考位置：
  **1,205 visible、173 not_observable、2 uncertain**。只有可見座標可作精確 2D 比較。
- 原始／處理後 prediction、人工判讀、人工座標、離線新模型量測與實驗警示分開保存。
  原 `observed / interpolated / missing`、raw 座標及正式分析結果沒有被人工資料覆寫。
- 已覆核的逐格狀態、中文檢視影片及資料使用側檔可供本批 baseline 的人工覆核後使用。
  既有手肘角度可保留 **246/592 格**，前導膝角度 **530/592 格**；這是使用條件下的保留率，
  不是角度準確率或新的通過分數。正式 `analyze-pitch` 尚未自動使用這些人工側檔。

3,552筆原模型狀態為 **3,133 observed／63 interpolated／356 missing**。
人工覆核後的使用限制仍逐筆保存；全部21格major失效的兩種角度均不採用，
包含離線自動警示仍漏掉的第104格。這是既有人工使用側檔的結果，不能算成自動警示已修好。

詳見 [人工 GT 流程](phase2_ground_truth.md)、
[003 可見座標比較](phase2_manual_coordinate_comparison_20261005.md)、
[覆核後可靠性檢視](phase2_reviewed_reliability_20261007.md)及
[既有角度使用條件](phase2_reviewed_features_20261007.md)。

## 二、原 Phase 2 要求逐項對照

| 原要求 | 已完成的交付 | 使用範圍與剩餘限制 |
|---|---|---|
| 人工 Ground Truth schema 與流程 | 沿用 `ground-truth-v1`，支援 exact frame、frame range、uncertain、not_observable、confidence／reviewer note；五片均 reviewed | 人工資料獨立保存。005 啟動與最高抬腿仍可合法保持 uncertain |
| Pose／keypoint 品質評估 | 五片逐關節 raw coverage、visibility、missing span、interpolation、jump、左右／投球側診斷與人工比較；六個 focus joints 分開報告 | coverage、模型分數與 observed 狀態都不能單獨證明關節對位 |
| 主體追蹤可靠性 | 原 ROI／中心／尺度／動作連續性與中斷警示已評估；人工確認五片主體仍在投手，3 格 track break 與人工吻合 | 003 的 skeleton 可持續被選中而整體錯位；連續追蹤不等於定位正確。五片無 confirmed identity switch，敏感度無法量測 |
| 明確 reliability flags 與原因 | 原每片／每關節 provisional flags、逐格模型狀態、人工覆核狀態及原因均可追查 | 自動 flags 尚有錯判；原旗標沒有改標成已驗證可靠。人工覆核後可用性只適用本批已檢查資料 |
| 遮擋與缺值 | observed、interpolated、missing 與人工可見性分開；不可見／不確定的人工精確 XY 保持空值 | 不製造被遮住關節的精確透視真值，不把所有 missing 都歸因於遮擋，也不跨長缺口補出假軌跡 |
| 評估輸出與 overlay | `pose_reliability.json`、`tracking_reliability.json`、`ground_truth.json`、`evaluation_summary.json` 與原 overlay／覆核視圖已提供 | 新實驗輸出使用獨立 sidecar，沒有替換 raw prediction 或正式結果 |
| 使用正式五球建立 baseline | 五片全 592 格完成 baseline 與完整人工定性覆核；003 另有十二關節可見座標參考 | 其餘四片沒有同等精確人工 XY；不把003誤差套用到其他影片或投手 |
| 模型策略與 abstraction | MediaPipe 保留正式 baseline，既有 `PoseEstimator` abstraction 保留；MoveNet 在隔離環境作已核准的有界比較 | MoveNet 原生17點與全部候選保留，沒有假造其他點、visibility 或 Z；未替換正式後端，未切換 RTMPose |
| 可量化驗收 | 原警示、人工標籤、可用性、座標誤差、歧義與缺值均可比較；新增離線分歧警示已有完整五片結果 | 自動對位與局部肘腕仍有已知失效，`accepted=false`；執行成功與測試全綠不等於可靠性通過 |
| 排除的功能 | 維持一位投手、五球的 Phase 2 範圍 | 未開始 Phase 3、跨投手比較、完整 profile、自動五事件判定、真實3D biomechanics 或影片取得功能 |
| 開發與來源保護 | 在獨立 branch／checkpoint 開發，保存凍結規則、來源 SHA、獨立核對及測試紀錄 | 正式五球、canonical GT、raw、核心模型／selector／gate／原門檻／平滑與插值保持原樣 |

## 三、實質改善與分母

原正式流程的警示尚未由新實驗取代。下面區分正式 baseline 與離線開發結果：

| 評估範圍與方法 | 影格分母 | TP | FN | FP | TN |
|---|---:|---:|---:|---:|---:|
| 原正式 tracking screen，全片 | 592 | 3 | 18 | 9 | 562 |
| 同一原 screen，排除各片初始化第0格 | 587 | 3 | 18 | 9 | 557 |
| 前輪原 screen＋bbox sidecar | 587 | 10 | 11 | 9 | 557 |
| 最新離線試驗：保留舊警示＋跨片肩髖分歧 | 587 | **20** | **1** | **9** | **557** |

以上均以原 raw 的人工 confirmed major failure 為指定目標。
587 格含 21 正例、566 負例；每片第0格保留資料，但不列人工初始化後的成效。
證據不足仍保留於主要人工分母，沒有靠移除困難影格提高結果。

最新實驗新增抓回003的 **87–92、96、101–103**，共10格；未增加相對 major 目標的FP。
原有9格FP完整保留；它們是 major 目標外提示，不表示每個提示都沒有局部診斷價值。
新sidecar另列93格 `candidate_dependent`、19格 `insufficient_evidence`，沒有把它們稱為可靠。

最新政策只用其他四片的 finite 非seed量測作實驗性參考，查詢片不參與自己的校準；
producer 不讀GT、不選native slot、不拼跨人關節、不改座標、不加寬警示區段。
這是已檢視五片的開發 LOO，沒有泛化或 false-alarm 機率保證。
詳見 [本輪警示結果](phase2_disagreement_warning_results_20261012.md)及
[事前固定政策](phase2_disagreement_warning_plan_20261012.md)。

## 四、發布仍阻擋的具體原因

1. **003／104仍為major漏報。** 模型分歧較小仍可能一起對位錯誤；沒有降低參考界線或延伸87–103以回填它。
2. **局部手肘、手腕錯位／誤連與遮擋仍存在。** 人工不可靠的投球肘84格中，原模型有72格仍列observed。
   throwing elbow raw coverage達標不能證明每個保留點準確。
3. **自動身份與對位保證不足。** 五片沒有identity-switch陽性案例；幾何唯一候選、模型一致與連續性均不能直接作身份真值。
4. **新警示尚未正式採用。** 正式流程仍保留原screen；本輪改善屬獨立離線異常提示覆蓋，沒有修復raw座標。

收尾不新增總分、零FN規定、漏報／誤警容忍通過線或其他任意驗收門檻。
原Phase 2要求先完成五片baseline；未見影片只限制泛化及正式採用的宣稱，
這份文件沒有把新增資料集列成臨時必做條件。上述已知限制如實保留，Phase 2不改標PASSED。

## 五、交付資料夾與人工待辦

共用交付資料夾讀取器已由使用者另行核准並完成，
候選匯入／去重／SHA／時間一致性／本地人工覆核記錄與回歸核對均有獨立紀錄，
見 [handoff回歸結果](handoff_regression_20261009.md)。供片資料夾保持唯讀，沒有依賴供片專案程式碼。

本地8顆交付球仍是 **candidate／pending**，沒有送去分析、升格或取代正式五球。
歷史文件「交付接入尚未開始、輪到時先停」描述當時狀態；後續明確核准的第一版讀取器已完成。
這不代表Phase 2已穩定，也沒有啟動候選球的自動分析。

同學的005獨立事件補充仍為另一項待回傳工作；canonical五片覆核保持完成，
原005啟動／最高抬腿uncertain及其他exact／range事件原樣保存。
不冒填同學判斷、實際覆核時間或出手事件，也不要求重做已完成標註。

## 六、測試、重現與停止點

本次重跑完整suite：**621項，619 passed、0 failed、0 errors、2 skipped，68.712秒**，
含正式五球MediaPipe E2E；兩項skip是Windows建立符號連結權限限制。
五片覆核／角度／既有提示與歷史封存逐項重建一致；最新警示比較也完整重現。
獨立核對重數3,552筆關節狀態、1,184筆角度使用條件及兩組major confusion，0 mismatch。

本次收尾證據目錄：`analysis_results/phase2_closeout_20261013_01/`。
收尾核對範圍包含正式五球E2E、既有封存警示／評估結果、374份保護來源、62份上游引用、
人工GT／raw／核心程式與8顆候選狀態。MoveNet的592次封存量測不重新執行。
已有的大型影片與衍生JSON仍在本機既有ignored輸出目錄；程式、測試、計畫與文件由Git保存。

本次工作以重現核對、完整測試、文件與commit／push為有限停止點。
**授權範圍的成果已交付並保留已知限制，自動可靠性發布維持阻擋。**
後續若再修復，應先根據現有證據指定具體工作與驗收範圍；
本次不繼續追加小規則、不改已封存政策、不開始Phase 3。

原 [2026-10-08最終評估](phase2_final_report.md)保留歷史結果與停止狀態；
本文件補充其後已核准的有限修復及交付讀取器進度，沒有覆寫原實驗或人工紀錄。

新輸出入口為`START_HERE.md`；`phase2_closeout.json`提供完整五球狀態、使用限制、
正式592格與離線587格比較；`release_status.json`明確保留`automatic_accepted=false`。
測試與獨立核對結果一併封存，來源計畫見
[本次收尾計畫](evaluation_plans/phase2_closeout_20261013_01.json)。
