# Phase 2：人工起點條件的五球固定裁切對照結果

2026-10-10（台灣）。**Phase 2 automatic reliability = NOT PASSED。此設定不接入正式流程。**

本輪完成四片新量測、五片離線對照；003引用已封存追蹤／pose及XY評估，沒有重新推論。
四片起點的HSU實際回覆「全部正確」另存，不覆寫草案、空白問題或原GT。
回答只證明第0格投手與當時可見肢體範圍，未證明全片身份或隱藏關節。

## 設定與封存

- 事前方案：`docs/phase2_assisted_roi_cohort_plan_20261010.md`。
- 實際執行：`docs/evaluation_plans/phase2_assisted_roi_cohort_execution_20261010_02.json`。
- `_01`保留為未使用封存：在任何推論前，evaluator補上方案文件SHA檢查，因此以`_02`重新封存程式hash；來源／量測設定完全相同，沒有覆寫或重跑。
- 沿用原CSRT27預設、外部padding0、full模型IMAGE／原confidence／fresh原selector；不修點、插值、fallback或依GT調參。
- 新四片477格、初始化4次、update473次、pose477次；003沿用115格，新增呼叫全部0。
- 全來源592格；各片第0格排除成效分母，合計587格。下表全部使用非起點格。

## 主體框與選取可用性

| 影片 | 格數／成效分母 | 裁切 selected／rejected／ambiguous | 全圖IMAGE selected | 原VIDEO selected | 裁切對IMAGE差 |
|---|---:|---:|---:|---:|---:|
| pitch_001 | 87／86 | 81／4／1 | 84 | 86 | -3 |
| pitch_002 | 175／174 | 174／0／0 | 174 | 174 | +0 |
| pitch_003 | 115／114 | 108／6／0 | 89 | 114 | +19 |
| pitch_004 | 114／113 | 102／11／0 | 109 | 111 | -7 |
| pitch_005 | 101／100 | 87／13／0 | 99 | 99 | -12 |
| 合計 | 592／587 | 552／34／1 | 555 | 584 | -3 |

**新四片單獨比較：裁切444／473、IMAGE466／473，少22格；003增加19格，不能用總量掩蓋其他片退步。**
587次後續tracker update均native success、全部587格有有效ROI；這只代表API／幾何條件，不能證明框包含伸展肢體或骨架正確。
裁切未選取35格中：16格後端無候選、18格有候選但原selector拒絕、1格歧義；保留原reason，不自行猜成遮擋。

| 影片 | 裁切未選取frame（含歧義） |
|---|---|
| pitch_001 | 33, 42, 44, 45, 53 |
| pitch_002 | 無 |
| pitch_003 | 63, 65, 68, 79, 80, 81 |
| pitch_004 | 64, 72, 75, 77, 78, 79, 80, 81, 84, 85, 86 |
| pitch_005 | 67, 68, 69, 70, 71, 72, 73, 74, 75, 77, 78, 79, 80 |

## 投球肘與重要關節

此處raw存在＝原selector選出的raw點存在；gate沿用既有min_visibility／min_presence。
input-supported＝預測XY落在真正送入後端的像素範圍內；它不是可見性／解剖位置正確GT。
外插raw保留但不算supported；低confidence不提高、缺值不補。以下百分比不可當人工準確率或Phase1新驗收。

| 影片 | 投球肘raw存在 | 裁切投球肘gate且supported | 全圖IMAGE gate且supported | 原VIDEO gate且supported | 裁切最長不具supported gate的連續段 |
|---|---:|---:|---:|---:|---|
| pitch_001 | 81／86 | 44／86（51.2%） | 55／86 | 57／86 | 62–82（21格） |
| pitch_002 | 174／174 | 139／174（79.9%） | 154／174 | 154／174 | 74–85（12格） |
| pitch_003 | 108／114 | 77／114（67.5%） | 81／114 | 96／114 | 84–105（22格） |
| pitch_004 | 102／113 | 68／113（60.2%） | 80／113 | 82／113 | 84–113（30格） |
| pitch_005 | 87／100 | 80／100（80.0%） | 88／100 | 88／100 | 61–75（15格） |

六個重要關節：下表為各片裁切「gate且input-supported」格數；分母同前。

| 影片 | 右肩 | 右肘 | 右腕 | 左髖 | 左膝 | 左踝 |
|---|---:|---:|---:|---:|---:|---:|
| pitch_001 | 81 | 44 | 31 | 81 | 63 | 61 |
| pitch_002 | 174 | 139 | 96 | 174 | 158 | 158 |
| pitch_003 | 108 | 77 | 45 | 108 | 99 | 106 |
| pitch_004 | 102 | 68 | 48 | 102 | 67 | 74 |
| pitch_005 | 87 | 80 | 58 | 87 | 65 | 69 |

逐片12關節完整raw／gate／外插、visibility／presence的count/mean/median/p90/max、最長缺失、
相鄰支持格的像素jump統計都在`evaluation/assisted_roi_cohort_evaluation.json`；不跨missing連線、不設新jump門檻。

## 精確座標與人工真值界線

- 精確XY僅003有獨立可見人工參考，直接引用原封存summary，evaluation_rerun=false。
- 003相同847個supported配對：全圖IMAGE均誤差19.1565px→裁切9.0031px，478改善／369惡化；原major18共同113點80.4089→10.8965px。
- 003仍有44個可見參考在框外、6格拒絕；投球肘87–96仍低於既有gate。
- 其餘四片XY誤差保持null，不能由confidence／選取格數／兩種輸出一致推導準確率。
- 原major標籤只描述原prediction，用於分組；新warning TP/FN/FP、identity/event accuracy及passed=null。
- 原5/5 canonical GT保持reviewed，隱藏關節不當精確真值；本輪沒有新增人工GT。

## 固定圖工程檢查

事前固定39格，全數輸出source／裁切raw／全圖IMAGE對照；另有15張contact sheets。
由助手作工程檢查，**不是HSU新增人工答案**，每圖human_review_answer仍null。
004可見：57格伸展的手臂／腳超出窄框；74–76、85格抬起的腿超出框；75裁切與IMAGE皆沒有selected；85裁切缺失。
005可見：50格伸展手臂、58格抬高手臂、75格腳與抬起腿超出框；54格裁切有輸出但IMAGE缺失；75裁切缺失。
框追到軀幹與輸入肢體完整是不同條件；這些圖支持輸入範圍問題，但不能單憑抽樣推斷所有拒絕的因果。

001的21格前伸手臂與抬起腳超出框；兩種輸出仍有肢體位置差異。
002的131格手套手與前導腳超出框，雖全片selected不減，肘／腕與腿gate支持量仍下降。
003沿用圖中38、87、92、95格的手臂／軀幹錯位有局部改善，70、78、101、104、112格裁切仍有輸出而IMAGE沒有；
78、87格伸展腿可超框、112格手臂可超框。這些圖不解除原44個框外參考或投球肘低gate限制。
完整工程觀察見completion audit的visual_inspection；沒有把圖中遮擋點猜成可見真值。

## 測試、來源與停止點

- 新增33項隔離工具測試。完整suite444項：**442 passed、0 failures、0 errors、2 skipped**，73.972秒。
- 包含正式五球real E2E。兩項skip為Windows file-symlink建立限制；junction測試通過。
- 592格source／crop像素、PTS、XY/Z/confidence映射及原selector receipts皆獨立核對；evaluator推論0次。
- 374個受保護實體檔案及上游sealed artifacts／人工答案hash不變；正式src、threshold、selector、pose／tracking、smoothing／interpolation不變。
- 八顆交付素材仍candidate／pending；沒有新輸入分析、正式替換或Phase3。
- 輸出：`analysis_results/phase2_assisted_roi_cohort_20261010_01/`。
- 測試／preflight：`analysis_results/phase2_assisted_cohort_proposal_20261010_01/`。

**結論：保留003的有限改善證據；固定窄框裁切未通過五球適用性檢查，不採用為正式修復。**
下一步先用已封存輸出區分新增漏點與範圍缺失，再提出保留完整動作輸入／背景干擾取捨的有限方案；
不依GT調padding、不自動fallback、不降低gate，也不要求重做已完成的5/5GT。
本輪至文件、commit/push及乾淨checkpoint停止。
