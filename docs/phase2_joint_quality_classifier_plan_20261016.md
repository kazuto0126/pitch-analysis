# Phase 2：投球肘與手腕品質判斷器的單次驗證計畫

日期：2026-10-16（台灣）。狀態：**AWAITING_USER_CONFIRMATION**。

本文件提出待確認的實驗規格與數字。尚未訓練、套用分類器或查看分類器結果，
也尚未建立執行凍結 SHA。第一步的重大錯位覆核提示完成回報後，先請使用者確認本計畫；
確認後才實作、測試並封存程式、資料清單與執行 manifest，再執行一次五折驗證。

目標是減少「原本仍被當成可用的錯誤肘／腕點」。只產生附加的「需要人工覆核」提示，
不修改正式 pose／tracking、PitcherSelector、既有 gate／threshold、平滑／插值、raw prediction
或人工 GT，不新增標註，不進入 Phase 3。這是已檢視五球的開發驗證，不是未見投手的泛化證明。

## 1. 標籤、完整分母與來源

只使用正式 Yamamoto 五球：001／002／003／004／005，原始影格數為
87／175／115／114／101，合計 592。沿用先前實驗的 frame 0 初始化排除，保存全部 592 格，
成效分母為 587 格／關節，兩關節合計 1,174 列。frame 0 的原模型值可作 frame 1 的時間特徵前文，
frame 0 的人工標籤不參與訓練或成效計數。

Canonical 人工來源只有：

`analysis_results/phase2_yamamoto_20260925_01/ground_truth/pitch_00N/ground_truth.json`

標籤採 `labels.throwing_elbow_reliability` 與 `labels.throwing_wrist_reliability`，
沿用區間兩端包含、frame index 從 0 開始的定義：

- `unreliable`：分類正例 1，表示原 raw-overlay 關節不可靠。
- `reliable`：分類負例 0，表示原 raw-overlay 定性對位可核對。
- `not_observable` 與 `uncertain`：分開保存及報告；不進入二元訓練或 TP／FN／FP／TN。
  它們不是好點或錯點，提示落在這些格也不算抓到錯點。
- 不以 major、processed state 或 XY 誤差重寫上述標籤；major 格和其他既有使用限制完整保留。

目前已封存的非 seed 分母：

| 關節 | unreliable | reliable | not_observable | uncertain |
|---|---:|---:|---:|---:|
| 投球肘 | 84 | 444 | 59 | 0 |
| 投球腕 | 71 | 380 | 136 | 0 |

003 可見人工 XY 來源為
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_42/pitch_003/manual_keypoints.json`。
只在最後輔助核對可見 XY 的連續誤差與提示分布，不作標籤、特徵、調參、像素正確線或採用條件。
定性 raw 判讀與可見 XY 覆核的範圍／語意差異保留，不把其中一套改成另一套。
其他四片精確座標誤差保持 null，不補人工真值。

## 2. 特徵：先產生並封存，完全不讀人工標籤

重用原 raw／capture、原 clean gate 設定、既有 MoveNet 六 slot、已保存的 CSRT 與
`analysis_results/phase2_joint_disagreement_20261012_01/measurements/pitch_00N.json`。
不重新執行 pose／tracker；不使用這次 ROI 擴框的結果，也不挑最有利模型或候選。
原 native 幾何候選關聯已使用人工確認的初始化框，這項既有前提須記錄；
「特徵讀取不含 GT」不能宣稱整個流程沒有人工資料。

每個關節使用相同、事前固定的 13 欄，不加入 pitch ID、frame index、事件、人工遮擋、major GT、
review disposition 或人工 XY：

| 欄位 | 固定定義 |
|---|---|
| 1–2 | 原 MediaPipe raw visibility、presence，不改分數或 cutoff |
| 3 | raw XY 是否落在原圖半開範圍的 0／1 訊號；框外有限點仍保留 |
| 4 | 與前一格 raw XY 的位移大小／原圖對角線／實際時間差（每秒） |
| 5 | 前後兩段速度向量之差的大小／兩段中點時間差（每秒平方）；只用目前與前兩格 |
| 6–8 | 同名 MediaPipe／MoveNet 關節在所有相容候選中的對角線比例距離 min、max、max−min |
| 9–10 | 所有相容候選的原生 MoveNet 同名關節分數 min、max，不設新 score gate |
| 11 | 相容候選數，0–6 |
| 12–13 | 無候選、候選歧義的 0／1 訊號 |

位移先用原圖 W／H 還原像素，再除影像對角線。時間用已核對的原 capture timeline，
不以不同影片的 frame index 當同一時間尺度。不跨缺值格補速度，不插值、不拿後一格作前文。
缺少連續前格、無相容候選或不能計算的連續特徵保留 null；
所有相容 slots 仍完整保存，不選 winner、不拼跨人關節、不假定 slot 編號跨格身份穩定。

原 raw 不存在／非有限時輸出 `insufficient_evidence`、probability=null；
不因沒點就宣稱抓到位置錯誤，不用全空特徵製造可靠度。這類列仍留在完整評估分母：
人工 unreliable 而無提示計 FN，人工 reliable 而無提示計 TN，並另列 abstain，
不能將 TN 或無提示解讀成可用點。可訓練的 raw 存在列若個別特徵缺值，
採訓練片中位數補特徵並加入固定缺值指示欄；這只補分類器輸入，完全不補關節座標。

## 3. 模型與固定參數

分別建立一個肘模型和一個腕模型，採小型 L2 邏輯迴歸。環境只讀檢查結果：
NumPy 2.5.3 可用，scikit-learn 與 SciPy 均未安裝。計畫使用既有 NumPy 實作，
不安裝套件。以下是**本次事前宣告的固定設定**，不冒稱既有套件的預設行為：

- `C=1.0`、L2、無 class weight／重抽樣／資料增強、包含不正則化截距。
- 目標：`sum(logaddexp(0, z_i) − y_i*z_i) + ||w||²/(2*C)`；每列權重皆 1。
- 固定 deterministic Newton solver；係數和截距皆從 0 初始化，最多 100 次。
  梯度無限範數 ≤ 1e-4 才視為收斂；固定回溯步長從 1 開始，每次減半，
  最多 25 次，Armijo 係數 1e-4。這是數值求解，不挑分類成績最好的迭代。
- 固定 `p(unreliable) >= 0.5` 才發覆核提示。不依測試片改閾值，不校準測試機率。
- 第 1–2、4–10 欄的中位數、平均與標準差只從該 fold 的四支訓練片估計；
  先補特徵缺值，再估平均／標準差。這 9 欄各有一個固定缺值指示，因此模型固定 22 欄。
  全缺值欄填 0 並保留缺值指示，零標準差以 1 作分母。
  第 3、12–13 欄及缺值指示保持 0／1；第 11 欄固定除以 6，不從測試片估縮放值。
- 只以該 fold 訓練片中人工可判定且 raw 存在的列 FIT；
  訓練排除理由與數量完整保存，不能拿同樣條件縮小測試分母。
- 若訓練只剩單一類、數值非有限、Hessian 無法求解或不收斂，該 fold 明列失敗／無法判斷，
  不更換模型、solver、C、class weight、迭代數或提示界線來補救成績。

本輪沒有搜尋超參數或門檻，因此沒有內層挑選。若使用者要改這些設定，必須在執行前重新確認本計畫；
執行結果公開後停止調整這組訊號。

## 4. 整片五折、資料隔離與一次執行

固定五個 outer folds，依序將 001、002、003、004、005 各自整片作測試，其餘四片整片訓練。
不得隨機拆 frame，不得讓同片相鄰影格出現在同一 fold 的訓練與測試兩邊。
每個測試格只由未用過該片標籤的模型產生一次 out-of-fold 提示；不做全五片重訓的採用模型。

資料流程拆成四個可核對階段：

1. **FEATURE**：只讀模型／原時間／既有候選量測，輸出全部 592 格的特徵及原始缺值理由。
   程式與來源明列允許讀取清單，不能開 GT、review view、manual XY 或含 GT 的評估結果。
2. **FIT**：每 fold 只開四片 training GT，核對來源 SHA／完整區間，保存標籤列、
   imputation／scaling 參數、權重、截距、收斂資訊。query GT 不可被 FIT 讀取。
3. **APPLY**：只讀該 fold 的封存數值模型與 query 特徵；不開 training／query GT、review view 或 XY，
   不呼叫 FIT verifier、重新 FIT 或改 preprocessing。先封存全部五片提示與 SHA。
4. **EVALUATE**：全部提示封存後才讀各 query 的 canonical GT，計算固定報告／決策。
   003 XY 最後作輔助核對，不能回饋 FIT 或 APPLY。

測試須證明 query GT 變更不影響自身模型／提示、preprocessing 只使用 training、APPLY 不讀人工檔、
完整時間與分母一致、單類／缺值／不收斂處理、probability 與提示可重算、模型不修改任何輸入。
先用合成資料驗證程式，再封存 code／tests／本計畫／runtime／來源 manifest SHA，才開始一次實際驗證。
不把五片五折稱為五次探索，亦不在看到各 fold 成績後改設定再跑。

## 5. 固定比較基準與已核對數字

三種方法逐格使用同一 canonical 標籤、同一 587 格分母：新分類器、score-only、前次 sample-maximum。
score-only 使用各片原 `pose_clean.clean.json` 的 visibility／presence gate（五片均為 0.5／0.5）：
有限 raw 任一分數低於原 gate 就提示；沒有有限 raw 就 abstain，不自動算 TP。
這只是比較既有分數訊號，不改正式 gate。下表為 2026-10-16 的只讀核對，未跑分類器：

| 影片 | score-only 肘 TP/FN/FP | sample-max 肘 TP/FN/FP | score-only 腕 TP/FN/FP | sample-max 腕 TP/FN/FP |
|---|---|---|---|---|
| 001 | 1/11/1 | 6/6/1 | 8/9/1 | 8/9/1 |
| 002 | 0/0/8 | 0/0/0 | 2/0/9 | 0/2/0 |
| 003 | 7/29/11 | 2/34/0 | 0/12/38 | 0/12/0 |
| 004 | 0/8/29 | 0/8/0 | 8/22/40 | 0/30/0 |
| 005 | 1/27/10 | 0/28/0 | 1/9/26 | 0/10/0 |
| 合計 | **9/75/59** | **8/76/1** | **19/52/114** | **8/63/1** |
| 排除 003 合計 | **2/46/48** | **6/42/1** | **19/40/76** | **8/51/1** |

score-only TN 為肘 385、腕 266；sample-max TN 為肘 443、腕 379。
原 finite raw 缺值肘／腕各 3 格，分別是 004／75–76、005／54，
缺值沒有從上述 FN 分母移除。sample-max 原始結果見
[前輪實測](phase2_supervised_joint_reference_results_20261013.md)。

目前原 raw gate 通過數：

| 影片 | 肘 gate 通過／其中人工 reliable | 腕 gate 通過／其中人工 reliable |
|---|---:|---:|
| 001 | 57/44 | 44/18 |
| 002 | 154/150 | 113/111 |
| 003 | 96/65 | 62/38 |
| 004 | 82/65 | 59/36 |
| 005 | 88/61 | 72/63 |
| 合計 | **477/385** | **350/266** |

通過原 gate 的人工錯點仍有肘 72、腕 49；通過 gate 不等於正確。
新 classifier、原 score-only、sample-max 是獨立 screens，不能把其中的 FP 直接當成正式流程總誤擋。
正式 gate 保留，因此另報原 gate 與新提示的聯集；不能聲稱 standalone FP 降低等同原 gate 被修復。

## 6. 必交報告與「保留可用」的實際含義

每支影片及五片合計，肘／腕各自並列三種方法的 TP、FN、FP、TN、提示數、
人工可靠／不可靠／不可觀測／不確定分母、raw 缺值、特徵缺值、abstain／不收斂數。
不可觀測、不確定與缺值的提示負擔另列，不因移除這些列而提高成績。

保留數須同時列出：

- 原 raw gate 通過、原 observed／interpolated／missing，以及原既有 frame 使用限制。
- 在相同原 raw gate 通過集合中，各 screen 發提示與未發提示的數目；
  其中人工可靠保留、人工錯點仍未提示、人工不可判定各有幾格。
- 新提示真正抓到多少「原 gate 已通過」錯點、額外提示多少原 gate 通過的好點，
  以及只提示本來就被 gate 擋掉的點有多少。有效增量和重複提示不能混為一項改進。
- 原 gate＋新提示聯集的可用支持數與原使用限制。這是覆核負擔／可能使用支持的試算；
  第一步與本實驗皆為附加提示，實際 raw、座標、gate、既有判定與可用狀態不被改寫。

「未提示」只表示未觸發這個 screen，不能命名為已驗證可靠。
不允許把 `insufficient_evidence`、空輸出或全部拒絕當成抓錯成功；
若新增 abstain，保持主要 FN／TN 分母，並在保留數中顯示其代價。
不以 AUC、整體平均 accuracy 或單一總分取代上述數字。

003 held-out 必須有獨立段落：只用 001／002／004／005 訓練，列其 TP/FN/FP、缺值與保留數、
既有 major 區間及第 104 格脈絡、可見 XY 輔助誤差，並將非 003 四片改善另算。
定性 GT、可見 XY、major frame 使用限制不得互換；局部提示不能宣稱已修復 major 漏報或身份追蹤。

## 7. 待確認的一次性決策規則

肘、腕**各自**判定，五折合併的 out-of-fold 計數必須符合以下全部條件，才能提出該關節的覆核提示採用建議。
至少一個關節達標即可提出那個關節；另一關節未達標就不提出採用，不以它阻擋合格關節。
完整五折可計算輸出是比較成立的前提；finite raw 的 query 不得為了減少誤報而主動 abstain。
若任一 fold 無法完成，記為該關節本次驗證無效／不可採用，不能只用其他 folds 的成績宣稱達標。

| 規則 | 投球肘 | 投球腕 |
|---|---:|---:|
| 誤擋好點不高於兩個基準：FP ≤ min(score-only FP, sample-max FP) | **FP ≤ 1** | **FP ≤ 1** |
| 錯點抓取明顯增加：TP ≥ max(兩基準 TP)＋8 | **TP ≥ 17**（FN ≤ 67） | **TP ≥ 27**（FN ≤ 44） |
| 排除 003 後仍增加：TP ≥ max(兩基準非003 TP)＋4 | **非003 TP ≥ 10** | **非003 TP ≥ 23** |
| 改善分布 | 至少 **2 支非003影片**，各自 TP > 該片兩基準 TP 的較大值 | 同左 |

這些是本次候選提示的採用比較數字，須使用者確認；不是 Phase 2 新增的零錯誤收尾條件，
也不降低或替換原 acceptance criteria。原 gate 通過錯點的有效增量、保留支持與未知負擔必須完整報告，
供使用者判斷採用範圍，不另加第三套事後必過線。

執行後只作一次決策：

- 至少一關節達標：明列通過關節、五球開發資料限制、額外模型資訊的依賴及已知漏報，
  提出僅作「需要人工覆核」提示的範圍，**等待使用者核准採用**；不自行接入正式判定。
- 兩關節皆未達標：停止調整這組訊號，記錄「需要更好的影像或模型資訊」，
  不加小規則、不改 C／solver／特徵／門檻、不換模型重試，也不要求再標註才允許收尾。
- 任一結果都按原 Phase 2 驗收要求回報實際狀態，不以程式成功、更多提示或局部達標直接宣布 Phase 2 PASSED。

## 交付與停止點

使用新的獨立 `analysis_results/phase2_joint_quality_classifier_<timestamp>/`，
保存 features／fold models／out-of-fold hints／evaluation、來源與程式 SHA、五折讀取隔離核對、
測試紀錄及一次性決策。正式五球、raw、canonical GT、人工 XY 和封存研究原樣保留。
零新增 pose／tracker 推論；完整測試中的正式五球 E2E 另列。

完成報告、完整 suite、文件、commit 與 working tree 核對後停止。
本計畫目前僅供確認，不執行第二步，不開始其他功能。
