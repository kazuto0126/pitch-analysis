# Phase 2：以人工可信觀測校準關節分歧參考

2026-10-13。使用者先前要求人工標註後可供判斷標準學習，並在局部試驗後持續指示修復。
本輪明示採用**supervised calibration**，只校準新的離線可靠性提示，不訓練pose模型、
不改正式核心／selector／原門檻／confidence gate／插值／平滑、raw或任何人工GT。
前輪GT-blind研究的政策與封存維持原樣；本輪不能再把整個流程稱為GT-blind。

## 為何改校準資料

前輪把其他片所有finite資料當參考，已知壞點可抬高sample maximum，肘腕涵蓋不足。
本輪只用已存在、來源核對的人工覆核使用側檔，選取既有
`use_disposition.status == reviewed_raw_observation`作可信參考。
它表示原raw定性可靠、原processed直接觀測且沒有confirmed整格使用限制，
不是精確pixel真值、native模型正確性或新人工標註。
沿用既有disposition語意：不擅自加入新uncertain整格排除、不重新定義人工可靠區間。

## 三階段與資料隔離

### 1. FIT：明示讀取人工training evidence

- 五個leave-one-clip-out folds；每個query的六關節，只用**其他四片**同一解剖landmark。
- 排除所有frame0。query影片的任何人工判讀都不能改變自己的參考界線。
- 先用原`derive_clip`及全部來源SHA重建覆核view並比對，不能信任可手改的衍生檔。
- 只保留既有`reviewed_raw_observation`列，再取finite同名raw/native候選min分歧。
- 固定取sample maximum作**資料估計的實驗性閾值**；不選百分位或另外手定數值，不改既有門檻。
- 每fold保存training GT／view來源、完整reference非seed分母、各種既有use disposition排除數、
  eligible／finite／missing數、全部保留列與並列最大值來源。
- 沒有finite可信參考時bound=null，不用0或其他影片query資料補上。
- FIT明確保存非空`human_training_inputs`；003人工精確XY不作本輪training來源。

### 2. APPLY：只讀封存數值參考與模型量測

APPLY讀數值artifact及原關節量測，**不讀任何GT／review view檔案**，也不呼叫會讀它們的FIT verifier。
training來源只複製provenance，不在application端dereference。
每query只取自己的fold bound，不使用其他fold因query資料估出的界線。

保留同一數值決策：min > bound才warning；min <= bound < max為candidate_dependent；
max <= bound為within_reference_range但不代表可靠；query缺值／無參考為insufficient。
全部相容候選保留，不挑slot、不拼跨人關節，不把原processed missing直接變成位置錯誤。
原observed／interpolated／missing與時間完整保存，不加寬warning區間，不生成major警示。
收據必須記`supervised_calibration_used=true`、artifact SHA及training來源；application不讀GT不等於整個方法無人工資料。

### 3. EVALUATE：封存提示後才讀query標籤

各關節仍以原canonical raw-overlay unreliable為正例、reliable為負例，
uncertain／not_observable依關節排除，缺值保留FN/TN，遮擋時的提示負擔另外報告。
完整592×6＝3,552保存列／587×6＝3,522非seed成效列，不以校準參考資格縮小query評估分母。
逐片逐關節並列舊GT-blind與新supervised結果、原jump／局部聯集、model-state分層。
前輪19筆定性FP與major／可見XY的語意差異保持，不自動改GT、轉TP或套新pixel容忍線。
major screen、精確XY連續誤差與局部定性目標分開；不得把局部提示提升成major修復。

## 驗證與限制

新增測試須證明：改query影片的人工view不影響自身fold bound、training源確實排除query、
seed不校準、無可信參考保持null、衍生view或source矛盾拒絕、APPLY不讀GT、全部候選保留。
實際FIT前固定policy／code／tests與來源；FIT封存後再綁APPLY artifact SHA，APPLY封存後才評估。

五片都已檢視，這是**有監督的開發cross-validation**，不是未見holdout、跨投手泛化或錯誤率保證。
原人工定性、model與native皆可能有誤；模型共同錯誤、低分候選、native參考壞點及畫面尺度影響仍在。
sample maximum不是一般分類器的通過線；本輪結果不能直接宣布Phase2PASSED或正式發布。
試驗零新pose／tracker推論；完整測試另外執行正式五球MediaPipe E2E。

輸出新目錄`analysis_results/phase2_supervised_joint_reference_20261013_01/`，分calibration／warnings／evaluation。
完成後獨立重算來源、folds與評估、完整suite、更新文件、commit/push；八球仍candidate/pending，不進Phase3。
