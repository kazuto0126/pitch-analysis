# Phase 2：資料可用性與座標準確性的對照

日期：2026-10-07（台灣）。**既有 baseline 評估已補齊；Phase 2 = IN PROGRESS。**

本次重新整理已保存的 `pitch_003` 座標診斷，回答「現有 gate／短 gap 插值後，
保留多少可見點？相同點位的誤差是否改善？」。
沒有重跑影片／模型、修改 pose／tracking、調 gate／threshold、改插值或填人工 GT。
這是既有量測的分組與重核，不是新的模型準確率或新警示。

## 固定的參考集合

- 115 格 × 12 關節，共 1,380 筆人工狀態。
- 1,205 筆 `visible` 可比較 2D 座標。
- 173 筆 `not_observable`、2 筆 `uncertain` 保留，但不推估座標或量測其位置誤差。
- 保存的 raw／clean 都用 `x × 510、y × 628` 回到原圖像素。
  內部 `x_height` scaling 不適用於這些保存欄位；也不使用 visualization median。
- `observed / interpolated / missing` 完全沿用既有狀態，不代表人工看見／確認對位。
- 逐筆座標、時間、狀態與距離和原 manual／raw／processed／reliability／diagnostics 相符。
  不裁切超出影像的模型座標、不補點、不新增像素通過門檻。

## 全片結果

| 既有 processed 狀態 | 可見人工點 | 相同點 raw 平均誤差 | clean 平均誤差 | 說明 |
|---|---:|---:|---:|---|
| observed | 1,150 | 21.16 px | 21.16 px | raw 與 clean 全部相同；最大誤差仍 252.37 px |
| interpolated | 24 | 59.68 px | 63.54 px | 11 點降低、13 點增加；平均差 +3.86 px |
| missing | 31 | 32.09 px | 不可量測 | 沒有 clean 座標；誤差留 null，不能算成 0 |

相同 **1,174 個可用點**（observed＋interpolated）的平均誤差：

- raw：**21.9504 px**。
- clean：**22.0292 px**。
- 保留率：1,174／1,205＝**97.43%**；這是可用點保留率，**不是準確率**。

全 1,205 個可見點的 raw 平均誤差為 22.2113 px。
不能拿它和只剩 1,174 點的 clean 平均值相比，就宣稱定位改善。
被丟掉的 31 點仍在固定人工分母內；表格及 JSON 分開保留缺失與誤差。

這批資料顯示 gate 保留了很多仍有位置偏差的點；插值也沒有一致降低誤差。
這不代表所有插值都有害，不修改原策略，也不據此增加或降低門檻。
可見人工點的插值比較更不能證明恢復了被遮住的關節。

## 六個重要關節

下列分母只計該關節可見的人工參考，和整支 115 格的 raw coverage 分母不同。

| 關節 | 可見人工点 | observed／interpolated／missing | observed 平均／P95 誤差 | 插值點 raw → clean 平均 |
|---|---:|---:|---:|---:|
| 右肩／throwing shoulder | 106 | 106／0／0 | 20.74／124.66 px | 無可比較插值點 |
| 右肘／throwing elbow | 93 | 87／4／2 | 23.79／87.16 px | 76.19 → 108.36 px（4 點） |
| 右腕／throwing wrist | 58 | 49／1／8 | 23.02／88.05 px | 29.79 → 34.70 px（1 點） |
| 左髖／lead hip | 115 | 115／0／0 | 19.63／94.33 px | 無可比較插值點 |
| 左膝／lead knee | 115 | 104／2／9 | 15.59／93.83 px | 3.94 → 4.39 px（2 點） |
| 左踝／lead ankle | 114 | 111／3／0 | 20.02／109.17 px | 15.25 → 11.68 px（3 點） |

完整十二關節與原人工 major-failure 區段／其他格的分組皆在 JSON。
87–104 原有比較（190 可見、178 observed、11 interpolated、1 missing）也重核相符。
不把各關節加成任意總分或排名；樣本很少的插值平均不當成可泛化策略。

## 保存、驗證與範圍

- [固定評估計畫](evaluation_plans/phase2_observation_accuracy_20261007.json)。
- 原診斷：`analysis_results/phase2_pitch003_diagnostics_20261006_01/per_joint_diagnostics.json`。
- 新輸出：`analysis_results/phase2_observation_accuracy_20261007_01/`。
  - `observation_accuracy.json`：全片、十二關節、major／其他格、固定分母與同點比較。
  - `evidence_integrity_check.json`：九份綁定來源與既有保護清單核對。
  - `full_test_suite.log`、`full_test_suite_result.json`：完整測試紀錄。
- 獨立唯讀覆核確認全部 1,380 筆與 15 個報告群組可重算，344 份不重複來源檔案未變。
- 此項評估沒有新人工答覆；仍只有 `pitch_003` 有同等完整、可見的人工 X/Y。
  其他四片有定性 GT，不能套用003的像素誤差當成它們的準確率。
- 未核定像素容忍門檻，`accuracy_pass_rate` 與 `pixel_acceptance_threshold` 保持 null。
- 此評估checkpoint完整測試191 passed／0 failed／0 errors／0 skipped。
  後續新增[五片覆核視圖](phase2_reviewed_reliability_20261007.md)後，最新完整測試為
  203 passed／0 failed／0 errors／0 skipped，紀錄另存於新的覆核輸出目錄。

Phase 2 的完整能力與剩餘範圍見[驗收對照](phase2_acceptance_review_20261007.md)。
共用資料夾接入仍未開始；輪到該待辦時先停止回報。沒有進入 Phase 3。
