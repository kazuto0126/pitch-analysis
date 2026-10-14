# Phase 2：既有2D角度對可見人工座標的數值評估

2026-10-14。肢體鏈比例提示未帶來新增TP，該規則不採用。接著補足既有手肘／前導膝角度
目前只有人工輸入可用性、尚無數值誤差的缺口；不是Phase 3動作分析或新增事件偵測。

## 固定範圍

- 只用已完整覆核的003人工12關節座標，保留115格（包含第0格，這不是校準試驗）。
  其他四片本次不評估角度誤差，不套用003數字。
- 兩個既有feature：throwing_elbow_angle（肩肘腕）、lead_knee_angle（髖膝踝）。
- 三點都人工visible、有限且兩條向量非零時才有人工2D角度參考；unknown／遮擋／退化保持null。
  被遮擋位置的推測不使用，不補點，不改原人工schema或raw prediction。
- 所有角度在來源pixel平面計算，保留width/height，使用原既有joint_angle定義。
  無3D、物理骨長、準確release、真實生物力學或人工pixel零誤差宣稱。

## 比較與分母

比較原raw有限座標所算角度、原processed未平滑base、已存在feature interpolation及smoothed四條流。
後三者只讀原features.csv，不重建分析或改平滑／插值。
先用原source-bound view和原feature exporter重建檔案一致性；base角度也與原processed pixel座標核對。
原始model observed/interpolated/missing、feature provenance、舊人工可用性及major限制皆保留。

每條流報全115格、人工參考可算格、參考存在而prediction缺值、prediction存在但無人工參考，
以及共同可比格的MAE／median／P95／RMSE／signed bias／最大絕對誤差（degree）。
共同可比格的誤差不代替完整分母。raw→base與base→smoothed只比較同格都有數值與人工參考的配對，
另列增加／減少／數值相同的誤差格數；1e-8 degree只判浮點相等，不是準確性門檻或Phase 2通過線。
按原三點model state、舊reviewed feature status、整格major限制分層，不依結果剔除困難格。

沒有新的binary correctness／warning、分類器、pose模型訓練、事件格數或候選素材分析。
量測relative-to-manual-reference error；人工標點自身不確定性尚未量化。
不能因內部角度接近就推定整個骨架對位或subject正確，亦不解除原major／joint使用限制。

## 執行與保護

固定policy／code／tests／來源SHA後才計算；新輸出
`analysis_results/phase2_manual_angle_assessment_20261014_01/`，不覆寫任何舊檔。
測試已知角度、退化、遮擋座標不可使用、長寬比、missing分母、共同配對與輸入不變；
全115格另以atan2(cross,dot)獨立重算，檢查source保護與正式五球完整suite。
本評估不改threshold／confidence gate／PitcherSelector／pose／tracking／平滑／插值，
八交付球仍candidate/pending，不進Phase3。無新數值驗收門檻，Phase2狀態不因單片誤差數字自動變PASSED。
