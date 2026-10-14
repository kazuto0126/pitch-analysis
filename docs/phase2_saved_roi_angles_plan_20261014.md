# Phase 2：已封存ROI輸出的可見人工角度比較

2026-10-14。來源核對與三點分解已完成，接著量化先前已執行的tracked-ROI實驗
是否改善既有2D角度。只讀封存預測，0新pose／tracker推論；原正式VIDEO pipeline不改。

## 事前固定資料與用途

- 003全115格人工座標與既有features，原IMAGE、tracked-ROI IMAGE及正式VIDEO封存輸出。
  第0格是人工seed，逐格仍保存，但主要成效分母排除它，保留114格。
- 兩項原feature：throwing_elbow_angle與lead_knee_angle。讀取原左右角色映射，
  人工三點皆visible、finite且非退化才有2D角度參考；遮擋不補座標。
- 此ROI由人工初始化，不宣稱全自動身分追蹤；僅003有這份完整人工XY，不外推其他投手或四片。
- 不改threshold／confidence gate／PitcherSelector／pose／tracking／插值／平滑／GT／major限制。
  不訓練或推論新模型、不自動採用ROI、不產生新事件或binary可靠性分類，不進Phase3。

## 四條既有輸出與數值支援

保留crop、full-image、formal-video raw三條封存原始點，及原formal-video processed base四流。
三條raw流的主要角度需原selection=selected、三點皆finite且在原圖內、三點皆過原confidence gate；
crop的預測點另需落在原crop範圍。這只叫數值支援，不等同正確對位或可靠骨架。
未過gate的有限點仍可保存ungated角度供診斷，不能拿來增加主要支援率或通過數。
原processed base只讀先前已驗證features.csv，不重建清理或混入新的平滑。

**人工參考是否在crop內另列分層，不用它篩掉主要比較的困難格。**
原crop外可見人工點依然保留，預測存在且符合原數值支援時仍計誤差；
缺值／rejected／越界／below gate等原因逐格報出，不把沒有數值當零誤差。

## 比較與完整分母

主要：crop對full-image raw；另一個固定比較是crop對formal-video raw。
次要：crop對既有formal processed base。所有差異僅在同格兩流與人工參考皆可算時配對，
報共同frame indices、前後MAE／median／P95／RMSE／signed bias／max及誤差減少／增加／數值相同格數。
1e-8 degree只判數值tie，不是準確度或Phase2通過門檻。

另報每流完整115保存／114非seed格、人工可算與不可算、人工存在但預測缺值、
預測存在但人工缺值、原major與原eligible／crop內外分層；不同分母的均值不能解讀成同格改善。
第69、105格是已封存診斷中的事前指定案例，不用新結果挑排名或只報成功格。
不以角度接近解解除major限制，亦不宣稱真實3D或無誤差人工真值。

## 來源與驗證

先固定protocol／code／tests、原ROI與IMAGE量測／評估、原角度父輸出SHA，再產生
`analysis_results/phase2_saved_roi_angles_20261014_01/`。
核對measurement frame index／source hash／timestamp／crop映射與原selector保存結果，
重建舊逐點comparison確認原gate／原可見性／座標取用一致；不能呼叫舊writer或estimator推論。
每條角度用原圖pixel比例計算，所有來源保護維持；新增結果由獨立公式和原點重算。

合成測試覆蓋三點角度、遮擋與缺值、crop外參考保留、gate／越界、不等分母與同格配對、
seed分母、原hold保留、輸入不變與binding拒收，並跑包含正式五球E2E的完整suite。
結果只決定既有實驗是否值得下一個具體修復評估，不自動改正式流程或Phase2狀態。
