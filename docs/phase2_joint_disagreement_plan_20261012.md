# Phase 2：同名關節模型分歧的效度檢查

2026-10-12（台灣）。只用封存五球592格，零新pose／tracker推論。
上一輪閉凸包重疊新增0警示，仍漏11格；本輪檢查同名關節分歧能否區別人工可靠性。

## 固定的量測與資料邊界

- Producer只讀封存native六slots、CSRT、原raw／capture與原pose reliability狀態。
  GT、人工XY、事件與含GT結果不進producer；保持正式五球、raw、GT及核心原樣。
- 全12關節直接同名配對，原source像素Euclidean distance及source影像對角線比例皆保存。
  有限但框外的點保留距離並記錄in_source；不因不符合預期而剔除。
- 幾何association沿用前輪全部相容slots。各slot逐點保存，另存所有相容候選的min／max；
  min是多候選下的分歧下界，max會受低分假slot影響，兩者均不是身份選取或可靠度分數。
- 四肩髖RMS先在同一slot計算，再取候選range；不平移擬合、不用各點最小值拼骨架。
  不同slot編號不代表跨格身份。分數只記錄、不作cutoff。
- 原raw有限性依既有helper；原observed／interpolated／missing逐格照存，不新增可用性gate。
  無raw／無候選保持距離null；不把missing填0或無限大，不改任何插值或顯示門檻。
- 不產生新二元警示、通過判定、身份選擇或矯正座標。所有numeric cutoff保持null。

## 封存後評估

- 保存五片全部592格，每片frame0只作初始化參考，成效587格。
- 六focus joints逐片／合計列人工reliable／unreliable／not_observable／uncertain完整分母，
  與原model state交叉統計；不可觀測人工點不作XY真值。
- Min及max兩端都報，方向固定為「分歧大更可能unreliable」，不看結果後反轉。
  Conditional AUROC只用有數值且人工可判定子集；同表列全人工分母、逐類缺值與數值可用率。
  單類AUROC=null，沒數值不移出完整人工分母；不冒充threshold-based TP/FN/FP或已修好。
- Unique／ambiguous／none及candidate_count分層，避免候選多令min自然變小的偏差被掩蓋。
- Major用同slot torso RMS range作描述性rank檢查。所有major漂移正例集中003，
  其他兩片正例是中斷；五片均已知開發資料，不宣稱holdout泛化或逐格獨立抽樣信賴區間。
- 003全12可見人工XY另比較原raw真實2D誤差與模型分歧的Spearman（ties平均rank），
  按joint與合計列配對數、raw缺值／量測缺值。保留兩模型接近卻一起錯的證據；
  不選最好slot或新增誤差門檻、不可見推估不混入精確XY。

## 完成條件

合成測試與介面審查後凍結code／protocol／source SHA；全592格一次離線量測，後跑GT評估。
報六關節的區辨性、原狀態與缺值表，以證據決定分歧是否值得另提新警示，不直接採用模型。
完整suite包含正式五球E2E，374保護來源／62上游引用／八候選狀態核對；更新狀態、commit、push。
Phase2仍NOT PASSED，直到原有驗收問題以證據解決；不進Phase3，不重做已完成人工覆核。
