# Phase 2：人工確認起點的主體延續驗證方案

2026-10-10（台灣）。**本文件建立時是方案與輸入準備，尚未初始化／執行影片追蹤。**
**Phase 2 automatic reliability = NOT PASSED；原FN18未修復。**

## 要回答的問題

給定一個已由HSU確認主要歸屬投手的起始框，獨立影像tracker能否在後續動作中維持
可核對的投手範圍？本輪候選限定本機既有OpenCV CSRT，一支003、一個起點、一組預設。
它是**人工確認模型提議框後初始化**，不是全自動選投手、人工手繪全身框或新pose模型。

先前KLT的來源歸屬不足，9×9固定衣物matching來源亦未確認、競爭候選接近；
本方案改用已確認主體的較大起始範圍及CSRT自身外觀更新，仍可能納入背景或逐格漂移。
CSRT只能回傳追蹤候選，`update=true`不等於投手身份正確；單一候選本身也無法排除多人體歧義。
[OpenCV CSRT API](https://docs.opencv.org/5.0/extra_modules/classcv_1_1TrackerCSRT.html)與
[Tracker API](https://docs.opencv.org/4.13.0/d0/d0a/classcv_1_1Tracker.html)說明其已知框初始化及
update回傳；實際函式／參數以本機5.0 binding probe為準，不由其他文件版本猜預設。

## 起始輸入與驗證資料分開

起點沿用剛完成覆核的Q1：003第0格、時間0、原矩形`[85,165,217,435]`。
HSU原回答「投」，只確認主要歸屬投手，**完整／局部範圍未提供**；不縮框、補全身或補遮擋點。

另存擬用輸入：
`review_tools/subject_initialization/proposed_HSU_pitch003_csrt_20261010_01.json`。
只抽Q1的原始框、影片／frame pixel SHA、時間及「投」原話；來源鏈連回既有九題紀錄。
原九題紀錄、原generation snapshot、量測、人工XY與canonical GT均不修改。

| 角色 | 可讀來源 | 禁止用途 |
|---|---|---|
| producer | 原MP4、metadata、technical、只含Q1的初始化輸入 | 不讀完整九題、pose、manual XY、canonical GT、T/P/O或evaluator結果 |
| parent preflight | 核對完整來源鏈，確認抽出的Q1與原回答一致 | 不把後續人工答案塞入seed或設定 |
| evaluator | 封存後接既有raw、人工參考及新tracker圖的獨立覆核 | 不回填producer、挑新seed或調設定 |

frame0屬初始化輸入，僅做來源／像素／初始化receipt核對，**排除所有成效分子與分母**。
既有Q2–Q9是原HOG矩形的開發證據，不直接當新CSRT矩形的歸屬答案。
本批003及其餘四片已有人工覆核，皆為development/regression，不稱holdout或未見資料。

## 一次有界執行的規則

1. 只用003原115格、510×628 BGR、原小數PTS與原像素；不作外部crop／resize／mirror。
   CSRT內部原有ROI／外觀更新照固定預設，不另加mask或背景遮除。
2. 一個CSRT實例，第0格初始化一次。全部27個實際預設與runtime／native SHA已核對，
   包含內部psr_threshold；不調參、不試其他tracker、不重新seed、不HOG reassociation。
   正式confidence gate、PitcherSelector、pose／tracking／平滑／插值維持原樣。
3. 先完成producer／evaluator／必要測試，含合成圖的API相容性檢查，再凍結execution manifest。
   本輪manifest是proposal，沒有替尚未存在的runner填假SHA，也不假稱已執行。
4. 保存115筆來源frame紀錄；frame0為初始化，1–114為後續狀態分母。
   原生框、布林回傳、截斷狀態、像素SHA／PTS與缺值原因分開保存。
   `init`原生回傳None不能當成布林失敗。本機有`getTrackingScore`，保存update後的原生
   finite score作診斷，不當校準confidence、不另設cutoff；讀值例外／非finite留null及原因，
   不把score缺值當追蹤失敗。校準confidence保持null。
5. 第一次`update=false`、非有限／非正尺寸、完全無影像交集或原生例外，停止這條追蹤並棄權。
   這是本試驗的保守停止政策，不把API的false宣稱為確認identity switch或投手離開畫面。
   失敗格的native回傳框可留作診斷，但可用候選框=null；後面不再update或重新初始化。
   **後續原影片仍解碼並保留115格完整receipt**，狀態為not_attempted_after_terminal_break。
   若初始化例外，frame0保存init_failed，其餘114格為not_attempted_after_initialization_failure。
   解碼、來源pixel／PTS核對失敗屬run integrity failure，立即拒絕封存完整成功結果，不能補造格數。
6. 部分出框保留原座標及truncated狀態，不偷偷clamp／round／補前框；只能描述可見部分。
   有限、正尺寸且有影像交集只是幾何可用，不是身份／人體範圍通過。
7. 原生update成功仍標subject_candidate_unverified，不能自動產生reliable或identity判定。
   「原生缺失」「幾何不可用」「歸屬未覆核／不確定／混合」是不同狀態。

## 事前固定分母與缺值

| 封存後評估項目 | 分母 |
|---|---:|
| 原始frame receipt，含seed | 115 |
| 成效／後續狀態，frames1–114 | 114；實際update呼叫最多114次，提前棄權不刪分母 |
| 12關節人工紀錄，排除frame0 | 1368 |
| visible XY，可作幾何對照 | 1195 |
| not_observable／uncertain，排除XY幾何 | 171／2 |
| 四肩髖皆visible的proxy／缺proxy | 105／9；缺值格70–78 |
| confirmed major failure／其餘非seed格 | 18／96；major仍87–104 |
| 既有T/P/O位置 | 11：T3／P2／O6 |

1195個visible點分成框內／框外／tracker不可用；105個完整proxy亦作同樣分割，另列9格缺參考。
使用原像素的半開矩形幾何，不用人體凸包冒充完整bbox GT；不報box IoU。
原HOG對照也排除seed：92／105有某框包含四人工點；major仍17／18人工點、7／18錯誤raw點
可落在某個框裡。這些是幾何背景，不能轉成新警示TP／FN／FP或主體準確率。
缺失輸出留在固定分母，不能因先停止就刪掉後段失敗、提高條件百分比。

## 最少人工確認與歧義處理

有候選圖才產生最多10題，固定frames`38,70,78,86,87,95,104,105,112,114`，每格一個原生框。
抽樣槽位分母固定10，分別列有題／缺候選；有題數不是完整十格通過數。
無候選就保留無題／缺值，不改抽樣、不補其他成功格；不重做已完成canonical GT。
題目只問該框主要屬投手／其他人／多人難分／不確定，局部／截斷另註，不猜隱藏關節。
保存實際原話、reviewer、時間與備註；未提供時間／confidence留null。
同格原HOG框的答案不能按重疊或最近距離搬過來，未問的tracker框保持unreviewed。

任一固定覆核為其他人／多人難分，記錄觀察失敗；固定十格任一缺候選／未回答／不確定，
記錄證據不足，均不調參救回。即使十題皆為投手，也只支持有限的人工初始化延續可行性，
不能證明114格全對、無identity switch、關節準確或已修好FN18。

## 執行前與本輪停止點

本機能力probe：OpenCV5.0.0、TrackerCSRT存在，27個參數綁定；**初始化0、update0、解碼0、下載0**。
輸出：`analysis_results/phase2_subject_assignment_proposal_20261010_01/`。
原374保護來源保持SHA，另綁本輪九題回覆與HOG封存來源。
此proposal不含尚未取得的實測結果。接續實作時先依本方案完成工具／測試並另存凍結manifest，
只跑003；不自動延伸五片、改核心或加入新模型。後續結果另存，不回改此事前方案。
Phase 2仍NOT PASSED；八個handoff素材仍candidate／pending，不分析、不提升，不進Phase3。
最新完整suite仍346 passed／0 failed／0 errors／2 skipped，本輪未重跑測試或影片。
