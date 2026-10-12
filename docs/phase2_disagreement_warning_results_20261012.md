# Phase 2：跨片肩髖分歧警示修復結果

2026-10-12（台灣）。本輪已完成警示候選、五球比較、獨立核對與完整測試。
**Phase 2 = NOT PASSED。** 離線警示有實質改善，正式流程仍保留原樣。

## 做了什麼

依[事前固定政策](phase2_disagreement_warning_plan_20261012.md)，新增可重現的離線producer與evaluator。
沿用封存592格／587非seed格，零新pose／tracker推論；producer不讀人工GT或XY。
每支查詢影片只用其他四支finite非seed的同slot四肩髖RMS分歧min，取sample maximum作
**實驗性、資料估計的閾值**。這不是改既有threshold，也不是依本輪GT選門檻。
不挑native slot，不拼跨人骨架，不改座標，不擴張警示前後區間。

四種狀態：`warning`、`candidate_dependent`、`within_reference_range`、`insufficient_evidence`。
within-range不能解讀為可靠；candidate-dependent只保留歧義，不當身份或major確認。
每格、每fold的來源、候選、時間、參考最大值出處與原因皆可追查。

## 真正的警示改善

全部587格保留21個人工major正例、566負例；缺值仍列FN/TN，不縮小分母。

| Screen | TP | FN | FP | TN |
|---|---:|---:|---:|---:|
| 原tracking | 3 | 18 | 9 | 557 |
| 前輪tracking＋bbox | 10 | 11 | 9 | 557 |
| 本輪分歧單獨 | 17 | 4 | 0 | 566 |
| 保留舊警示＋本輪分歧 | **20** | **1** | **9** | **557** |

新增抓回10格：003的**87–92、96、101–103**；沒有新增FP，原9格FP未撤回。
新分歧共警示003／87–103的17格，其中7格與原bbox重複。
新規則缺19格（3正例／16負例），包含原3格骨架中斷；舊tracking仍捕捉該3格。
聯集證據不足15格皆為負例，決策覆蓋率572/587；不把它們宣稱對位可靠。

| 影片 | 非seed格 | 新warning | candidate-dependent | within-range | insufficient | 聯集TP/FN/FP/TN |
|---|---:|---:|---:|---:|---:|---:|
| pitch_001 | 86 | 0 | 5 | 78 | 3 | 0/0/2/84 |
| pitch_002 | 174 | 0 | 11 | 161 | 2 | 0/0/0/174 |
| pitch_003 | 114 | 17 | 59 | 38 | 0 | 17/1/2/94 |
| pitch_004 | 113 | 0 | 5 | 106 | 2 | 2/0/3/108 |
| pitch_005 | 100 | 0 | 13 | 75 | 12 | 1/0/2/97 |
| 合計 | 587 | 17 | 93 | 458 | 19 | 20/1/9/557 |

association及candidate_count=0–6的完整狀態表另存JSON；所有zero counts保留。

## 唯一剩餘major漏報

**pitch_003／104**仍未警示：唯一相容候選的分歧min=max=**0.03128724**，
低於其他四片454個finite參考格的最大值**0.05148073**（001／25）。
該格肩髖RMS跨模型距離25.3114px；raw四肩髖相對既有可見人工XY的平均誤差仍**34.7994px**。
這是「模型比較接近，仍可能對位錯誤」的實例。沒有降低bound、改GT或把87–103延伸到104。
`remaining_miss_diagnosis.json`保留逐點誤差與原量測；對照圖已實際查看，未新增人工答案。

## 限制與Phase 2狀態

五片都已檢視，LOO是**開發驗證，不是未見holdout或跨投手泛化**。
其他四個fold的最大參考皆來自003／93（0.13727026）；已知壞格可能抬高參考界線，
本政策不使用GT清洗它。候選數、畫面尺度及時間相關性亦會影響分歧。
0新增FP只描述這批資料，不能保證未來false-alarm rate。

本輪修復的是離線**異常提示覆蓋**，沒有修復raw坐標或把新warning部署到正式流程。
104漏報、既有9FP、局部肘腕遮擋／誤連、獨立正例與正式接入驗證仍未解決。
原五份GT、observed/interpolated/missing、正式五球、Phase 2核心與全部舊門檻原樣。
八顆交付球仍candidate/pending，沒有分析或提升；沒有Phase3。

## 核對與測試

- 獨立stdlib程序重算592個候選範圍、5fold最大值來源、592逐格狀態／原因、
  587全部confusion／區間及association／候選數分層，**0 mismatch**。
- 374保護來源＋62上游SHA未變；GT5/5 reviewed；src/input/annotations diff空；
  MoveNet原592次attempt未增加；handoff唯讀DB仍1批8球45events，8候選皆pending。
- 新增29項合成回歸，完整suite **619 passed、0 failed、0 errors、2 skipped**，
  621項／66.526秒，含正式五球MediaPipe E2E。兩skip皆Windows建立符號連結權限限制。
- 兩張工程圖實際查看：五球警示timeline、104漏報與001／25參考來源對照。
- evaluator初次在Windows嚴格路徑解析遭sandbox拒絕；使用相同凍結程式與政策重試成功，
  無輸出覆寫或重新量測。完整suite初次審批逾時，允許的一次重試後完成。

## 輸出與重現

`analysis_results/phase2_disagreement_warning_20261012_01/`

- `warnings/pitch_001.json`至`pitch_005.json`與`warning_run.json`
- `evaluation/disagreement_warning_evaluation.json`
- `remaining_miss_diagnosis.json`、`figures/`、`independent_audit.json`
- `full_test_suite.log`、`final_audit.json`

已用的輸出目錄不可覆寫。要重現時，另建execution plan並指定新的output_directory，
保持相同policy與來源SHA；不得改已封存plan。

下一關：釐清104這類較小但仍錯的對位與局部肘腕失效，設計不靠GT改門檻的證據；
正式採用前另外驗證未見資料、歧義／缺值及誤報。**Phase 2 = NOT PASSED。**
