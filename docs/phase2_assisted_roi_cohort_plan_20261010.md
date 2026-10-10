# Phase 2：人工起點條件下的五球固定設定對照

2026-10-10（台灣）。**事前方案；本文件建立時四片新追蹤／裁切 pose 尚未執行。**
Phase 2 automatic reliability = **NOT PASSED**。本輪接續已確認的起點，量測同一設定的剩餘四片，
不修改正式分析核心、門檻、PitcherSelector、模型、平滑／插值或人工 GT。

## 人工輸入已具備

HSU 對四個第0格黃色框回答「**全部正確**」。問題明確包括主要投手及目前可見頭／手臂／腳未被裁掉，
不要求猜隱藏關節。實際回答另存
`review_tools/subject_initialization/HSU_formal_four_seed_review_20261010_01.json`，
四個 confirmed seed 另存；原未確認草案、空白 questions、圖片及之前003的人工答案保持原樣。
human completion time／confidence 未提供仍 null，recording time 另存。
此回答只確認四個第0格的主體與可見範圍，不證明後續影格身份／框完整或排除所有背景人物。

| 影片 | 原格數 | 第0格起點來源 | 本輪工作 |
|---|---:|---|---|
| pitch_001 | 87 | assistant 視覺草案＋HSU確認 | 新追蹤／裁切各一次 |
| pitch_002 | 175 | assistant 視覺草案＋HSU確認 | 新追蹤／裁切各一次 |
| pitch_003 | 115 | HOG提案＋HSU確認，既有 | 使用原封存追蹤及裁切，零重跑 |
| pitch_004 | 114 | assistant 視覺草案＋HSU確認 | 新追蹤／裁切各一次 |
| pitch_005 | 101 | assistant 視覺草案＋HSU確認 | 新追蹤／裁切各一次 |

全部592格保留，五個初始化格排除成效分母，剩587格。
本輪新來源477格、4次初始化，最多473次後續update及477次pose推論；
terminal/init失敗時呼叫數減少，完整時間列與缺值仍保留。
003的115格／114非起點格沿用，明列為已知development案例。
起點來源不同也分開報告，不作公平的全自動方法排名。

## 唯一輸入策略：沿用已測設定

- 保持本機CSRT的同一27個預設與同一native binary，原native score只作診斷。
  不用score設新cutoff；terminal failure後不resume／reseed／沿用前框。
- 外部裁切padding為0；CSRT內部原生`padding=3.0`是另一個既有參數，不混作外部裁切範圍。
  floor左上、ceil右下與原圖交集，半開slice，原生框及derived bounds分別保存。
- 同一既有MediaPipe full模型、IMAGE、num_poses=4、三個原confidence設定皆0.5、segmentation=false。
  原尺寸BGR裁切複製轉RGB；不外部resize、mirror、mask、修點或插值，不fallback到全圖。
- 先保存全部crop候選33點，再按原公式映射至全圖；visibility／presence不變、外插不clamp。
  z只保留原值及寬度單位換算，不當3D、不作準確性評估。
- 每片fresh原PitcherSelector，逐格包括無候選格都更新一次。原selection拒絕／歧義保持原樣。
- producer只讀原MP4／metadata／technical／該片confirmed seed及模型；
  不開人工回答lineage、canonical review、manual XY或舊pose來決定新輸出。
  003只核對既有封存來源與receipt後引用，不當成新量測。
- 重用既有兩個low-level `measure_frames`，新增隔離cohort wrapper；
  舊003 runner／execution／constants及正式src完全不改。

本輪用不變設定量測可用性與退步，不宣稱已解決003的44個框外參考或6格拒絕。
沒有依人工座標挑padding或額外參數搜尋；新輸入策略／核心接入需另列方案。

## 封存與獨立核對

新工具／測試完成後，固定code、test、模型、native、runtime、source SHA與proposal／execution manifest。
parent先核對374個原受保護實體檔案、四份實際人工確認、003追蹤／crop及五片全圖控制組封存。
每個新追蹤完成先保存receipt，再以其ROI做一次pose；中斷／API或來源錯誤不得寫cohort成功封存。
不覆寫舊003或candidate validation。整體輸出逐片區分new_measurement／reuse_sealed，附原檔ref與hash。

evaluator只在量測封存後讀人工資料。獨立核對全部592原像素／PTS／格數、裁切BGR／RGB、
XY/Z映射、confidence及fresh selector replay，沒有模型／tracker replay。
開始／完成皆重核來源；缺失列與terminal尾段不從固定分母消失。

## 五球報表與限制

逐片及全體保存：

- 來源／成效格數、ROI可用／缺失、候選數、selected／rejected／ambiguous；與原IMAGE／VIDEO分開列。
- 12關節raw存在、原gate通過、input-supported、外插、低confidence／缺值、visibility／presence統計。
- 最長缺失段、相鄰且同時有支持資料的XY跳動統計，不跨missing連線、不新增jump cutoff。
- `full_body_input_verified`除了已確認起點的可見範圍，其餘仍unknown；
  框有效／tracker success／高confidence不能替代所有肢體完整或對位正確。
- 新arm沒有插值。raw、支持範圍、人工可見性分開，不把raw gate輸出說成已證實可見且正確的observed。
- 精確XY只有003既有visible人工參考；直接引用原847點主要配對結果及逐點封存，無重跑。
  其餘四片的像素誤差保持null，不由coverage或兩種輸出一致冒充精度。
- canonical major只描述舊prediction，作分組；新warning TP／FN／FP、identity／event accuracy及passed維持null。
  新輸出主體／重大錯位需另做有限、明確的新視覺覆核，不搬用舊GT成答案或重做5/5全部GT。

固定顯示格（事前選定，兼顧均分位置與原已知失效／出手，不依新結果增刪）：

| 影片 | frame index |
|---|---|
| 001 | 0、21、43、65、86 |
| 002 | 0、43、87、131、174 |
| 003 | 0、38、70、78、87、92、95、101、104、112、114 |
| 004 | 0、28、57、74、75、76、85、113 |
| 005 | 0、25、50、53、54、55、58、59、75、100 |

圖是工程檢查輔助，不自動成為人工GT，也不能證明所有影格身份。全部其他格仍保留在JSON報表。
圖顯示native來源與ROI／原raw，原圖內既有播放符號／游標等畫面保留，不清理或美化輸入。

## 本輪停止點

完成四片新量測、五片離線統計與來源核對，實際檢查固定圖、跑含正式五球E2E的完整suite，
更新狀態文件、commit/push後回報。正式五球／raw／GT、八顆交付candidate／pending維持原狀。
新輸出尚未由人完整覆核、沒有新warning policy，不因可用性改善自動標Phase2 PASSED。
結果若有惡化或terminal failure照實保存；不在本輪調參補救、不開始Phase3。
