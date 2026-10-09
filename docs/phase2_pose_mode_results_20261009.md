# Phase 2：IMAGE／VIDEO 對照結果

2026-10-09（台灣）。**Phase 2 automatic reliability = NOT PASSED。**

## 本輪實際完成

以原正式五片的全部592格，完成一次獨立的同模型模式對照與既有人工資料比較。
新增兩支實驗程式與13項測試；沒有改正式pose、tracking、PitcherSelector、
confidence gate、插值／平滑、人工GT、影片或原預測。

- [事前方案](phase2_pose_mode_plan_20261009.md)。
- [事前固定execution清單](evaluation_plans/phase2_pose_mode_countercheck_20261009.json)：
  34份量測來源、6份僅evaluator可讀人工來源、374份原始保護來源與runtime／程式SHA。
- 原 `pose_landmarker_full.task`、MediaPipe 1.0.1、4 poses與三項0.5設定相同。
  原完整影格直接轉RGB；IMAGE用`detect(image)`，原VIDEO結果唯讀。
- 每片使用原PitcherSelector的新instance；不以人工資料選候選、不跨模式配candidate index。
- 所有原格、33個關節、未選到、低gate、原始小數PTS及capture整數時間完整保留。
  新點只是experimental raw，不冒稱observed、正確或正式結果。

## 五片結果

| 影片 | 總格數 | 原VIDEO selected | IMAGE selected | IMAGE rejected | IMAGE ambiguous |
|---|---:|---:|---:|---:|---:|
| pitch_001 | 87 | 87 | 85 | 1 | 1 |
| pitch_002 | 175 | 175 | 175 | 0 | 0 |
| pitch_003 | 115 | 115 | 90 | 20 | 5 |
| pitch_004 | 114 | 112 | 110 | 2 | 2 |
| pitch_005 | 101 | 100 | 100 | 1 | 0 |
| 合計 | 592 | 589 | 560 | 24 | 8 |

**560格新選到的骨架與原骨架完全相同**：33個關節的X/Y/Z/visibility/presence，
共92,400個數值逐項相等；最大像素座標差0。獨立CSV／JSON／math計算亦得到相同結果，
不是比較函式把同一個變數用兩次。

候選與選取確實有變化：29格從selected變為rejected或ambiguous；
另外有8個可與原raw比較、但不同的IMAGE候選，沒有因人工答案而替換選取結果。
原baseline只保存selected VIDEO，拒選格無完整候選可比，這部分保持不可量測。

### 原重大錯位仍存在

003的87–104共18格：IMAGE仍selected **14格**，101–104共**4格ambiguous**。
14格的座標保留相同錯位。另20格rejected在63–81、83；
非major區段共21格未選到，不能把未選到全部算成抓到重大錯誤。

全五片21個confirmed major frame中，14 selected／4 ambiguous／3 rejected。
只在可量測子集的軀幹差異全部為0，條件rank AUC為0.5；
另外7個重大格與25個非major格沒有此量測，不從分母中消失。
這不是新warning policy，也沒有新的TP／FN／FP；原baseline仍TP3／FN18／FP9／TN562。

## 003人工座標比較

人工原有1380點：**1205 visible、173 not_observable、2 uncertain**，後兩類不計精確位置誤差。

| 比較集合 | 點數 | VIDEO mean error px | IMAGE mean error px |
|---|---:|---:|---:|
| 相同finite可見點 | 947 | 21.254704 | 21.254704 |
| 相同既有gate通過可見點 | 918 | 20.157145 | 20.157145 |
| major區段相同finite可見點 | 150 | 81.062266 | 81.062266 |
| major區段相同gate通過可見點 | 138 | 78.665650 | 78.665650 |

共同gate集合改善0點／變差0點／相同918點。
原VIDEO有1205個finite可見點，新IMAGE只剩947，另258個可見參考沒有新選取座標。
不能拿VIDEO全1205點的22.211292px，與IMAGE剩947點的21.254704px比較後宣稱提升。
完整median／P95／max、12關節與每點列保存在comparison.json；六個角色也逐片列分母與缺值。
其餘四片只有原VIDEO定性覆核，沒有XY可判定新IMAGE座標準確率，不能自動沿用原標籤。

第95格右肩是直接反例：兩個模式皆預測(167.4432,104.7554)px，
既有可見人工點為(260.56,218.98)px，兩者誤差皆**147.370310px**。
新增95／101／112格四欄圖：原圖、原VIDEO、新IMAGE、原有可見人工點。
101／112的IMAGE為ambiguous，圖中不擅選另一條骨架、不補遮擋點。
這些是量測後的案例說明圖，不作訓練或新GT。

## 結論與停止位置

這次提供了可重現的模式敏感性對照；**未改善已選骨架的定位，未採用為自動警示或正式backend**。
API設定確實是IMAGE enum1／VIDEO enum2，Python wrapper傳給native建立函式，並呼叫不同入口；
未驗證native內部的時間狀態，不能宣稱已證明某個tracking機制造成錯位。
結果只適用這個SDK／模型／設定與已知development五片，不是泛化驗收。

不再於此實驗追加crop、改gate或挑較好的候選。修復仍需要能核對投手影像對位、
且不與原模型共享相同錯點的證據。若評估不同模型或新的主體定位方法，
先另列小範圍方案、來源與驗證方式；本輪沒有選用／安裝／替換新模型。
原baseline評估與canonical5/5人工工作仍COMPLETE；自動可靠性仍NOT PASSED，
不要求HSU重標已完成區段。交付八球保持candidate／pending，不分析、不取代正式素材，不進Phase3。

## 輸出與驗證

輸出：`analysis_results/phase2_pose_mode_countercheck_20261009_01/`

- `measurement_run.json`、五份`pitch_00*.json`：GT-blind量測與所有候選。
- `evaluation_01/comparison.json`：全592格背景、逐關節對照及003全部1380列。
- `evaluation_01/evidence_integrity_check.json`：592格原像素、selection／差異重算與來源未變。
- `read_only_audit.json`：獨立92,400數值、人工誤差、SDK入口及374個保護來源核對。
- `examples/`：95、101、112三張圖與SHA清單；原圖區域沒有resize。
- `full_test_suite.log`、`full_test_suite_result.json`：完整測試紀錄。

實際執行：

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts/measure_pose_mode_countercheck.py docs/evaluation_plans/phase2_pose_mode_countercheck_20261009.json analysis_results/phase2_pose_mode_countercheck_20261009_01
.\.venv-analysis\Scripts\python.exe -B scripts/evaluate_pose_mode_countercheck.py docs/evaluation_plans/phase2_pose_mode_countercheck_20261009.json analysis_results/phase2_pose_mode_countercheck_20261009_01 analysis_results/phase2_pose_mode_countercheck_20261009_01/evaluation_01
```

Windows執行使用repo內獨立TEMP／TMP，完整suite啟用正式五片E2E。
測試：**322 run、320 passed、0 failed、0 errors、2 skipped**，約108秒。
兩項skip為Windows無法建立檔案symbolic link；目錄junction安全回歸測試通過。
新增13項覆蓋：像素尺度、原gate、缺值、候選序號、未完整軀幹、來源綁定、
時間對齊、不可觀測排除、相同分母、uncertain排除及篡改receipt拒絕。
原374個physical sources、正式五球、raw、GT與核心保持原hash。
大檔輸出維持本機ignored；程式、測試、固定計畫與此報告進Git。
