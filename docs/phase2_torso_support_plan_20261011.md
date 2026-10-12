# Phase 2：封存資料的軀幹範圍衝突試驗

2026-10-11；僅離線 sidecar，正式模型、threshold、selector、raw、GT、五球保持原樣。

## 已知機制與範圍

上一輪完整人體框警示已新增003的7格，但仍漏87–92、96、101–104。
唯讀診斷：漏報11格的44個可見肩髖點，原raw平均誤差60.145px，平均visibility0.9973；
正常96格的375個可見肩髖點誤差9.188px，visibility0.9975。
錯誤肩髖仍可能落在完整人體框的頭／胸／腿範圍；96亦有低分歧義骨架抵銷框衝突。
不能靠高confidence、最近骨架或GT挑slot判正確。

只用已封存592格原raw、MoveNet六slots、CSRT、capture；不重跑模型或tracker。
保留五球全部592格，每片人工初始化frame0不列成效，主分母587格。
GT與可見人工XY只供封存量測之後的評估，producer不讀取。

## 事前固定規則

1. 沿用既有幾何candidate條件，所有六slots與多候選全部保留；沒有score／IoU cutoff或勝者。
2. 既有bbox衝突警示全部保留。其餘frame以原raw四個肩髖點建立凸包，
   與各相容native slot自己的四肩髖凸包比較；不組合不同slot的點。
3. 閉集合相交、包含或碰邊／角都算重疊，不加padding、面積比例門檻或浮點epsilon。
   任何一個有效相容軀幹凸包重疊，即不新增警示；不等於對位或身份已證實。
4. 所有相容凸包均非退化且全部不相交才新增「模型間軀幹範圍衝突」。
5. 原raw缺值／非有限、無相容candidate、raw凸包少於三頂點，保持證據不足。
   若沒有重疊但任一相容native凸包退化，也保持證據不足，不能丟掉歧義者強行警示。
6. 記錄所有slots凸包／面積／逐肩髖殘差／中心差／肩髖垂直差；連續診斷值不作cutoff。
   不宣稱native凸包是人物segmentation、可見軀幹或3D解剖真值。

## 評估與停止條件

先測合成幾何／狀態／來源不可變更，再封存code／protocol／來源SHA與producer、evaluator計畫。
producer只讀native／CSRT／raw／capture四種資料角色；零推論；輸出全五球後再跑既有通用評估器。
比較原screen、上一輪bbox聯集、本輪累加聯集；列出各片TP/FN/FP/TN及棄權，棄權不移出主要分母。
原major共有21非seed正例、566負例；沒有把缺乏警示解讀成關節可靠。
若新增FP或仍漏報，完整報告，不依看過的GT調整規則後重跑。
工程圖僅驗證幾何／來源／警示語意，不代替人工GT。
完整suite含正式五球E2E，檢查374保護來源／62上游引用／八交付candidate未變。
Phase2不能因本試驗程式成功或部分提示改善而通過；完成commit、push與乾淨checkpoint後停止，不進Phase3。
