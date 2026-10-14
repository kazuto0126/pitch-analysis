# Phase 2：原骨架肢體鏈相對伸長提示

2026-10-14。使用者要求持續改善。前輪人工校準的跨模型距離仍受參考模型位置品質影響；
本輪固定一個不依賴另一模型位置的幾何假設，新的獨立 sidecar，不改正式核心或既有門檻。
舊上臂／前臂投影長度實驗保持原樣；本輪新增整條鏈的同格軀幹比例、明示人工參考與可重現提示。

## 唯一事前假設

兩條鏈：投球肩—肘—腕 `arm_chain`、前導髖—膝—踝 `lead_leg_chain`。
`S` 是投球肩、`H` 是前導髖，均已有六個 focus 角色中的人工資料。
所有距離先轉成來源影像 pixel，保留像素長寬比例：

`R = (distance(p0,p1) + distance(p1,p2)) / distance(S,H)`。

只測**相對過度伸長**。自然投影縮短可接近零，因此不設下界，不以變短判錯或判遮擋。
分母或必要點缺失／非有限、分母為零時保留 null 與原因；極小正分母不 clamp、不加 epsilon。
原 raw 有有限點但 processed 是 missing／interpolated 時仍可保存幾何診斷，原狀態不改。

## FIT 與 APPLY

- FIT 明示 supervised，只用其他四片所有非 seed 格。
- arm 的 unique 依賴角色是肩、肘、腕、前導髖；leg 是髖、膝、踝、投球肩。
  每個依賴角色皆須符合既有 `reviewed_raw_observation`，不可只要求被測角色正確。
- 使用原 source-bound 覆核 view 的同一資格定義與來源重建，frame 0 不進校準或成效。
- `U = max(finite eligible R)`，保存完整 retained rows、資格／缺值／排除計數及所有最大值來源。
  沒有 finite 可信參考時 U=null。query 整片的人工標籤不參與自己的 U。
- APPLY 只讀封存數值 artifact 與已封存 raw 量測，不讀 GT／view，不重新 FIT。
  原先量測檔雖含另一模型欄位，本政策的特徵／資格／決策只能讀 raw 點／原狀態／時間與 metadata。
  親代來源契約驗證仍會核對舊檔 native 欄位與 SHA；它們不供應本輪特徵或警示決策。
- `R > U` 才發 `chain_relative_stretch_warning`；其餘為 within-reference 或 insufficient。
  `within_reference_range` 不表示可靠。無 slot 選取、座標修正、時間加寬或新推論。

## 警示 scope 與評估目標

提示只屬於整條鏈：**不能知道哪一端錯**，不廣播成三個 joint warnings，不提升為 major／identity switch。
整個骨架共同平移或縮放可讓比值完全不變，本輪不能宣稱修好 003／104。
raw 軀幹 anchor 自己也可能錯或被投影縮短，因此沒有獨立對位或身分保證。

固定每條鏈的主要人工目標：三個 member 任一 `unreliable` 即 positive；三個全 reliable 為 negative；
沒有已知 unreliable 而有 uncertain／not_observable 時按該鏈排除。positive 的其他 member
即使不可觀測也不取消已知錯誤。判斷 unknown 的順序固定為 uncertain 優先、其後 not_observable。
anchor 的 query 人工狀態只供另外分層，不能拿來事後排除 FP 或縮小主要分母。

完整保存 592×2＝1,184 chain 列，成效先保留 587×2＝1,174 非 seed 列，再按上述人工 scope 排除。
原六個角色 3,522 個非 seed 人工／model 狀態也完整核對，但不把 chain cue 冒充六關節分類改善。
missing／insufficient 保留在主要 FN/TN；unknown 提示負擔另列。
在同一 chain 目標下對照原 jump 的 member 聯集、前輪 supervised joint 提示的 member 聯集、
本輪 chain 提示，以及原 jump＋前輪提示＋本輪提示；scope 的聚合規則保持一致。
這些對照是 chain review cues，不能替代逐關節或 major 既有計數。

## 測試與決定

先凍結 code／tests／policy／來源，FIT 封存後綁定 APPLY 數值 artifact，再封存提示才評估。
測試須包含：pixel aspect、剛體平移／uniform scale 不變、自然縮短、零／缺／極小分母、
完整依賴點資格、query GT 隔離、seed 排除、無參考、來源變更、APPLY 不讀人標與不推論，
chain mixed known-error／unknown 目標和完整 missing 分母。
五片皆已檢視，屬開發交叉驗證，不作未見資料泛化或真正骨長／3D 宣稱。
不新增任意 Phase 2 通過線，不以程式成功等同驗收；零 FN／零 FP 也不是原先核定門檻。
若效果不足，記錄原因，不事後換比值、加下界或挑最好 cutoff。

輸出新目錄 `analysis_results/phase2_chain_reliability_20261014_01/`。
正式五球／raw／GT／confidence gate／PitcherSelector／pose／tracking／插值／平滑保留；
八球仍候選、待人工確認、未分析。跑完整 suite、獨立核對、更新文件並 commit/push，不進 Phase 3。
