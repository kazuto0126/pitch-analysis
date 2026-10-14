# Phase 2：ROI角度流失清單與有限整合決策

2026-10-15。既有五球窄ROI設定已不採用，003的同格角度均值改善不能推翻五球完整性損失。
本輪只補尚未保存的三點角度轉換／退步明細，結案窄框整合方向並提出一次有限後續實驗。
不再重做既有592格selector分支診斷、不增加warning規則，不跑新模型或tracker。

## 固定資料與分母

承接昨日四流逐格角度與summary、原manual／reviewed view，以及既有五球ROI loss seal。
兩個既有feature×三個baseline（full-frame IMAGE raw、formal VIDEO raw、原processed base）×115格，
保存690列。每組第0格保留但主摘要排除，共684非seed列；實作依target計數，不寫投手專用邏輯。
先重建昨日115格來源／crop／selector與1,368舊逐點列、230角度列及summary完全一致，再產生新audit。

## 新清單

- availability由原numerical_support判定，獨立於人工角度是否可算：both_available、baseline_only、
  crop_only、neither_available。保留全部frame lists，另列人工參考存在／缺值、major、eligible與crop內外分層。
- baseline／crop的所有原unavailable_reasons均保留，報非互斥數量與同時存在組合；不把優先順序分組當因果。
  原gate不改，缺值不當成功或零誤差，不用人工crop內外篩掉困難格。
- 同格有可見三點參考且兩流角度可用時，保存原signed／absolute error與crop-minus-baseline差。
  improve／worsen／numerical tie沿用昨日1e-8 degree，僅判數值相同，不是準確性或驗收門檻。
- 三個成員各保存原人工status／visible XY、兩流XY、pixel error與差值。
  人工hidden／uncertain不猜點；processed的座標來自原processed view，不能拿raw代替。
  單點可見而整個人工角度不可算時，仍可保存該點診斷，不能假裝已有完整角度真值。
- 所有角度退步列完整保存三點變化，不只挑嚴重或有利案例。點位差值原樣保存；
  三點pixel差全負／全正／mixed-or-tied僅描述精確數值符號，不建立pixel準確度門檻。
  角度與點位誤差是不同目標，不因此認證骨架正確。

## 不做的推論

不依GT或事後誤差挑流、點、候選、fallback、padding或新門檻。
reference出框／below gate／未選到等並存條件不是已證明的物理失效原因。
IMAGE與VIDEO有模式差異，不能把對VIDEO的全部增益歸因於裁切。
不把原prediction的定性GT當新ROI的正確性標籤，不重做5/5GT、不外推003的XY精度。

## 保存與停止範圍

固定code／tests／protocol與父來源SHA後，寫新的
`analysis_results/phase2_roi_decision_20261015_01/`；原所有輸出不覆寫。
測試availability與reference獨立、完整分母／seed、非互斥原因、processed原點、遮擋、
角度／pixel方向不一致、輸入不變及來源拒收；另做獨立重算及包含正式五球E2E的完整suite。
374來源／62上游、原推論與八候選狀態保持不變。

本輪交付：角度流失／退步audit、窄ROI不整合決策，以及下一次單一輸入範圍實驗的可review方案。
新實驗只擬定，未核准／未開始，不計預期改善；Phase2仍NOT PASSED，不進Phase3。
