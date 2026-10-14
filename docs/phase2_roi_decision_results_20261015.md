# Phase 2：角度流失清單與窄ROI整合決策

2026-10-15。依[固定方案](phase2_roi_decision_plan_20261015.md)，完成003角度層級的可用性轉換與退步對照，
承接已有五球loss診斷；沒有重跑592格selector trace或新增模型推論。
**現有窄ROI不接正式流程；[下一次2×輸入範圍實驗](phase2_roi_integration_decision_20261015.md)僅提出方案，尚未開始。**

## 完整分母與可用性

115格×2個既有feature×3個baseline＝690列全部保存；各組第0格保存而排除主摘要，非seed共684列。
availability依原numerical_support判斷，與人工角度是否存在分開。下表每列完整114格，缺值不當零誤差或成功。

| feature／baseline對crop | 皆有數值 | baseline有、crop無 | crop有、baseline無 | 皆無數值 |
|---|---:|---:|---:|---:|
| 肘 IMAGE | 39 | 12 | 4 | 59 |
| 肘 VIDEO raw | 42 | 19 | 1 | 52 |
| 肘 processed base | 42 | 24 | 1 | 47 |
| 膝 IMAGE | 80 | 3 | 18 | 13 |
| 膝 VIDEO raw | 95 | 8 | 3 | 8 |
| 膝 processed base | 97 | 8 | 1 | 8 |

有完整可見人工三點參考的子集：肘51格、膝113格，仍保存不可比較的各類缺值：

| feature／baseline對crop | 皆有值且可比較 | 新流失 | 新增有值 | 皆無值 |
|---|---:|---:|---:|---:|
| 肘 IMAGE | 38 | 4 | 3 | 6 |
| 肘 VIDEO raw | 41 | 8 | 0 | 2 |
| 肘 processed base | 41 | 9 | 0 | 1 |
| 膝 IMAGE | 80 | 3 | 18 | 12 |
| 膝 VIDEO raw | 95 | 8 | 3 | 7 |
| 膝 processed base | 97 | 8 | 1 | 7 |

有數值不代表位置正確；沒有人工角度參考的格仍保留，但不宣稱新的準確或不準確。
IMAGE為同模式主要對照，VIDEO／processed另列；模式差異使對VIDEO的全部增益無法直接歸因於裁切。

## 可見參考存在時的新流失已逐格定位

| 同模式IMAGE對照 | 新流失frame | 原crop的實際狀態 |
|---|---|---|
| 肘 | 31、32 | RIGHT_WRIST低於原gate |
| 肘 | 105、107 | RIGHT_ELBOW低於原gate |
| 膝 | 27、28、29 | LEFT_KNEE低於原gate |

這7格皆仍有selected crop姿態、人工三點皆在crop內。這是並存條件，不能把所有流失說成肢體被裁掉，
也不能保證擴框會改善；模型輸入內容與相對人物尺度改變的因果仍未隔離。

對VIDEO raw，肘新增缺值8格：31、32、63、66、67、68、105、107；其中63／68未selected，
31／32／66／67腕低gate，105／107肘低gate。膝8格：27、28、29、63、79、80、81、83；
27–29膝低gate，63／79–81未selected，83踝低gate。原因完整保存，不放寬gate或補點。
processed肘另含65，新增缺值9格；processed膝同8格。三流完整gain／loss清單均存JSON。

原reason是非互斥標籤：未selected時可能同列缺肩／肘／腕與missing angle。
`prediction_outside_or_missing_crop`包含缺失點，不能把其數量當實際被裁掉的關節數。
它們不是多個獨立失效，也不證明物理遮擋或tracker失敗。

## 角度退步與三點位置誤差需要分開看

VIDEO raw對crop的肘18個角度退步格中，3格三點pixel誤差全下降、2格全上升、13格混合／相同。
膝40個退步格為3／11／26。原IMAGE對照的肘18格為3／2／13，膝35格為3／10／22。
每列固定三點原值與差值完整保存，沒有挑點、合成總分、oracle選流或新增準確度門檻。

三點更接近既有人工座標但角度差增加的格：肘46／55／61，膝50／94／111。
例如94膝（原major限制保留）：

| 相對人工參考 | VIDEO raw | crop |
|---|---:|---:|
| lead hip pixel誤差 | 93.6782px | 22.8815px |
| lead knee pixel誤差 | 98.1983px | 26.4454px |
| lead ankle pixel誤差 | 114.0659px | 5.2689px |
| 膝角度絕對差 | 13.4958° | 18.5804° |

角度與逐點位置有不同的數值目標，不能單靠角度接近就認證整個骨架對位。
這裡只量測相對既有人工2D座標，不改其status／XY，不將人工參考當無誤差3D真值。

## 本輪決定與驗證

- 結案現有固定窄框設定：不正式採用。五片selected552／IMAGE555／VIDEO584、其他四片相對IMAGE少22格，
  與003角度均值增益一起納入[整合決策](phase2_roi_integration_decision_20261015.md)，不再只靠單片改善推進整合。
- 新增13項測試；完整suite **751 passed、0 failed、0 errors、2 skipped**（753項／54.578秒），
  包含正式五球E2E；兩skip是Windows符號連結建立限制。
- 昨日230角度列／summary及1,368原逐點列重建一致；本輪690列、全部缺值／原因／三點距離與分層另做獨立重算。
  獨立核對690保存／684非seed列、2,070組點位誤差與690個原processed點；角度最大差5.997e-12°，
  分母／frame lists／理由與全部摘要無差異。沒有呼叫本auditor數值函式取得核對值。
- 374保護來源／62上游、正式五球、raw、GT、模型與門檻原樣；原592次MoveNet attempt未增。
  八球仍candidate/pending、未分析；本輪0新pose／tracker推論、0座標校正、0正式採用。
- 已實際檢查全115格可用性矩陣與全部角度退步點位分布圖；這是工程檢查，沒有新增人工GT。

**Phase 2 evaluation已完成並保留限制；自動可靠性仍NOT PASSED。未進Phase3。**
下一方案固定同一MediaPipe、saved浮點框中心2×寬高、五球最多592次pose／0tracker，
保留同模式控制、完整缺值與一次決策後停止；此提案尚未執行，不以預期結果宣稱進步。
輸出：`analysis_results/phase2_roi_decision_20261015_01/`。
