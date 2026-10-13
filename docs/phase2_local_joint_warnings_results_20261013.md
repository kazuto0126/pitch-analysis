# Phase 2：六關節局部提示的實測結果

2026-10-13（台灣）。使用者在前輪收尾後要求繼續，本輪已完成局部提示producer、evaluator、
五球評估與來源核對。**規則不足以作一般關節可靠性分類器，不採用正式流程；Phase 2 = NOT PASSED。**
前輪結案及全部封存結果保持原樣，本輪為新的有限修復試驗。

## 實際新增能力

依[事前固定政策](phase2_local_joint_warnings_plan_20261013.md)，逐一輸出投球肩／肘／腕、
前導髖／膝／踝的極端位置分歧提示。各關節以其他四片同一解剖點的finite非seed min距離
最大值作實驗性參考，查詢整片與所有frame0皆不參與自己的校準。
GT與人工XY不進producer，不用GT清洗校準，不選slot、不拼骨架、不改原門檻或座標。

每格保存`warning / candidate_dependent / within_reference_range / insufficient_evidence`、
原model state、全部相容slot、時間與原因；原observed/interpolated/missing保持原樣。
完整保存592×6＝3,552列，成效為587×6＝3,522非seed列，再按各關節排除人工不可觀測／不確定。
模型缺值留在FN/TN分母；原jump獨立比較，局部提示不提升為major或identity-switch。

## 新提示單獨的結果

| 關節 | 人工正例／負例 | 人工排除 | TP | FN | FP | TN |
|---|---:|---:|---:|---:|---:|---:|
| 投球肩 | 21/566 | 0 | 8 | 13 | 0 | 566 |
| 投球肘 | 84/444 | 59 | 1 | 83 | 0 | 444 |
| 投球腕 | 71/380 | 136 | 5 | 66 | 0 | 380 |
| 前導髖 | 4/582 | 1 | 0 | 4 | 15 | 567 |
| 前導膝 | 8/577 | 2 | 0 | 8 | 2 | 575 |
| 前導踝 | 5/579 | 3 | 0 | 5 | 2 | 577 |

正例是canonical raw-overlay `unreliable`，負例是`reliable`；不是逐點像素誤差分類。
新提示落在人工排除格的數量全為0；原jump／局部聯集仍有肘3筆not_observable提示，另列負擔。
每關節19筆insufficient全部保留，並按人工類別記數；within-reference不能當作可靠。

新提示位置：

- 001投球肘50；腕49–51、53–54。
- 003投球肩93–100；前導髖87–100、103；膝95–96；踝99–100。
- 002／004／005新提示皆0，不代表片內關節都正確。

## 與原jump比較

| 關節 | 原jump TP/FN/FP | 原jump＋新局部提示 TP/FN/FP |
|---|---|---|
| 投球肩 | 5/16/5 | 12/9/5 |
| 投球肘 | 6/78/16 | 7/77/16 |
| 投球腕 | 4/67/10 | 9/62/10 |
| 前導髖 | 1/3/5 | 1/3/17 |
| 前導膝 | 1/7/13 | 1/7/15 |
| 前導踝 | 1/4/22 | 1/4/23 |

新訊號對少量手臂／肩點有增量，但肘腕漏報仍多，不能以「新提示沒有手臂FP」掩蓋低涵蓋。
各角色分開列示，沒有建立總分或主觀排名；完整逐片、association、候選數0–6與
model-state×人工標籤×evidence-state交叉表均在JSON。

## 19筆FP與人工座標的語意差異

全部19筆局部FP均在003的confirmed major區段，且有可見人工XY：

| 角色 | 筆數 | raw對可見人工XY平均距離 |
|---|---:|---:|
| 前導髖 | 15 | 84.4042px |
| 前導膝 | 2 | 105.8170px |
| 前導踝 | 2 | 128.1816px |

這些點的canonical逐關節定性標籤為`reliable`，同格卻有整體major使用限制，
raw與已覆核可見人工座標也有大距離。已輸出全部19筆對照與三個工程圖案例，
沒有選較好的案例改主要分數、推定新的pixel容忍線、修改GT或把FP轉成TP。
定性對位、整格使用限制與連續座標誤差是不同參考；下一步需明確核對其評估用途。
既有人工使用側檔已限制全部21個major格的兩種角度，沒有因此把第104格變成可用。

## 為什麼不採用

事前已指出的結構問題在實測出現：其他片的最大壞點會抬高校準界線，
只有含整組極端值的影片容易超界，不能泛化成一般肘腕可靠性分類。
不依本輪結果清洗reference、調低bound、換百分位或增加針對104的小規則。
位置分歧也不能單獨確認哪個模型錯、是否遮擋或投手身份。

原major離線聯集仍TP20/FN1/FP9/TN557，正式流程仍原樣；本輪沒有修好104或任何raw坐標。
八顆交付球仍candidate/pending，未分析／提升；不進Phase3。

## 核對、測試與輸出

- 獨立重算21,312組同名距離、30fold、3,552保存狀態／3,522成效列，confusion、
  人工排除提示負擔及完整分層全一致；最大浮點差1.14e−13px，非準確性容忍門檻。
- 374保護來源／62上游SHA、GT5/5、正式五球、raw與核心不變；MoveNet原592次attempt未增加。
- 新增29項合成回歸（producer15、evaluator14）。完整suite **648 passed、0 failed、
  0 errors、2 skipped**，650項／58.123秒，包含正式五球MediaPipe E2E。
  兩skip是Windows建立符號連結權限限制；試驗零推論，E2E測試另外執行。
- 兩張工程圖已實際檢視：六關節完整screen比較、人工參考scope對照；沒有新增人工判斷。

輸出：`analysis_results/phase2_local_joint_warnings_20261013_01/`。
包含`warnings/`、`evaluation/local_joint_warning_evaluation.json`、
`post_seal_scope_comparison.json`、`figures/`、獨立audit及完整test log。
來源／政策以新的execution／evaluation／result seal綁定，前輪封存不覆寫。

下一步應先釐清局部定性GT與已覆核XY的評估目標，再決定校準方式；
本sample-max政策不再調參，**Phase 2仍NOT PASSED**。
