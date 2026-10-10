# Phase 2：人工起點主體延續試驗結果

2026-10-10（台灣）。**有限的人工初始化追蹤可行性有支持；Phase 2 automatic reliability = NOT PASSED。**
原FN18尚未修復，沒有採用新warning policy或改動正式核心。

## 本次完成

依[事前方案](phase2_subject_assignment_proposal_20261010.md)及
[凍結設定](evaluation_plans/phase2_subject_assignment_execution_20261010_01.json)，
新增隔離CSRT量測、離線比對與35項回歸測試。只執行003一次、一個已由HSU確認的起始框、
本機27個預設，不重新seed、不調參、不換tracker。正式五片／raw／人工GT保持原樣。
proposal內的「未執行／346 passed」描述建立當時狀態，後續實測與最新測試以本文件為準。

起始框沿用前次HOG Q1 `[85,165,217,435]`，另存只含Q1的初始化輸入。
這是模型提議、人工確認歸屬的框；完整／局部範圍未提供，不當成手繪全身GT。
producer只讀MP4、metadata、technical及該初始化輸入；完整九題、manual XY及canonical GT
僅在parent preflight／封存後evaluator使用。這不是完全無人工輸入的自動選投手試驗。

## 實際數字

| 項目 | 結果 |
|---|---:|
| 原始receipt／獨立像素與PTS核對 | 115／115格 |
| 初始化／後續native update | 1／114次 |
| 後續native成功／terminal break | 114／0格 |
| 成效分母 | 114格；第0格排除 |
| 可見人工XY在框內／框外／tracker缺失 | 1151／44／0，共1195點 |
| 不可觀測／不確定XY，排除幾何比較 | 171／2點 |
| 四肩髖proxy在框內／框外／tracker缺失 | 105／0／0格 |
| 四肩髖proxy缺參考 | 9格（70–78） |
| 原重大錯位的人工proxy在框內 | 18／18格 |
| 原重大錯位的**錯誤raw**四肩髖仍在框內 | 10／18格 |
| 固定新框人工覆核 | 10投手／0其他／0混合／0不確定 |

所有114筆native tracking score都是`-1.0`；只保存API原值，未當作confidence或新增cutoff。
沒有重新執行tracker來宣稱精確可重現；獨立核對的是115格來源像素／時間與完整receipt。

### 各關節可見人工點與框的幾何關係

| 關節 | 框內 | 框外 | tracker缺失 |
|---|---:|---:|---:|
| 左肩 | 114 | 0 | 0 |
| 右肩 | 105 | 0 | 0 |
| 左肘 | 77 | 5 | 0 |
| 右肘 | 92 | 0 | 0 |
| 左腕 | 40 | 21 | 0 |
| 右腕 | 57 | 1 | 0 |
| 左髖 | 114 | 0 | 0 |
| 右髖 | 114 | 0 | 0 |
| 左膝 | 114 | 0 | 0 |
| 右膝 | 110 | 4 | 0 |
| 左踝 | 111 | 2 | 0 |
| 右踝 | 103 | 11 | 0 |

上表是**人工可見座標是否位於追蹤框**，不是模型關節準確率、raw coverage或新的可靠性分級。
框外的手／腿也可能屬於投手；框內仍可能有背景或他人。

## 人工來源與限制

固定frames38、70、78、86、87、95、104、105、112、114皆有新圖。
HSU實際回覆：**「全部都是投手」**。保存於
`review_tools/seeded_subject/HSU_pitch003_csrt_20261010_01.json`，逐題綁定新框、原像素與圖SHA。
十題的extent／confidence／人工完成時間皆未提供，保持null，記錄時間另外保存。
原空白question snapshot、measurement、evaluation及前次九題紀錄保持原樣；後續人工結論另存。

十個固定樣本支持本次人工初始化後的有限主體延續可行性；不能證明114格身份全部正確、
沒有identity switch、關節位置正確或自動初始化可靠。全部資料都是已看過的development案例。
原HOG排除seed後為92／105格有某框包含四人工點；本次為105／105。
兩者輸入資訊不同（本次有人工起點），不能當成公平的全自動準確率排名。
尤其10／18格錯誤raw仍被框包含，**框內／外不足以修復全部FN18**。
identity accuracy／box IoU／新警示TP、FN、FP維持null。

下一步須先定義能處理「錯骨架仍在投手框內」的對位證據與歧義政策，再訂原592格回歸方案；
此設定不直接接入正式warning、擴跑其他四片或重做5/5人工GT。

## 測試與來源保護

完整suite **383 run／381 passed／0 failed／0 errors／2 skipped**（64.412秒），包含正式五球真實E2E。
兩項skip為Windows file-symlink建立限制；directory-junction案例仍通過。
新增21項producer、14項evaluator測試涵蓋一次初始化、terminal棄權、缺值分母、來源封存、
固定抽樣與禁止搬用舊答案。

首次沙箱suite遇到TEMP存取拒絕，原log保留；正常權限未指定正式素材的一次suite有3項skip，
最終已明確指定正式五球重跑，僅剩上述2項。第一次evaluator的沙箱路徑解析也被拒，
在產生評估前中止；原程式／封存設定不變，正常權限重跑成功，沒有重跑tracker。
原374個受保護實體來源、前次HOG封存與九題review hash不變。

輸出：`analysis_results/phase2_subject_assignment_20261010_01/`。
能力／preflight／三次suite歷史log：`analysis_results/phase2_subject_assignment_proposal_20261010_01/`。
結果與來源摘要：[result manifest](evaluation_plans/phase2_subject_assignment_result_20261010_01.json)。
八個交付素材維持candidate／pending，未分析或提升。沒有進入Phase 3。
