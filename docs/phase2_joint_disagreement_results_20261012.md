# Phase 2：同名關節分歧的效度檢查結果

2026-10-12（台灣）。**評估完成；Phase 2 = NOT PASSED。**

本輪實作並測量[事前固定的關節分歧方案](phase2_joint_disagreement_plan_20261012.md)。
沿用封存五球592格／587非seed格，零新pose／tracker推論；未改核心、門檻、GT或正式素材。
新增12關節逐slot距離、六focus joint人工可靠性比較、原model state交叉統計及缺值報表。
本輪沒有產生新二元警示或改座標；原警示聯集仍TP10／FN11／FP9，11格漏報尚未修復。

## 重要進展

同名肩髖的位置差，比「凸包是否碰到」有更明確的重大錯位訊號。
四肩髖同slot RMS分歧下界，在有量測的568格上conditional AUROC=**0.997576**；
上界為0.793232，所有歧義slots仍保留，不看GT選身份或拼各關節最小值。
AUROC是固定方向的排序區辨性，**不是99.76%正確率**，也沒有選定任何警示門檻。

完整人工major分母仍587＝21正例＋566負例；有數值568＝18正例＋550負例。
缺19＝3正例＋16負例，全部保留在完整可用性分母；沒有把中斷正例從資料刪除。
所有有數值的major正例都來自003同一段已知漂移，不能據此宣稱跨片泛化或Phase2通過。

| 影片 | 非seed格 | 人工major正例／負例 | 有值正例／負例 | 缺值 | torso min/max conditional AUROC |
|---|---:|---:|---:|---:|---:|
| pitch_001 | 86 | 0/86 | 0/83 | 3 | null/null |
| pitch_002 | 174 | 0/174 | 0/172 | 2 | null/null |
| pitch_003 | 114 | 18/96 | 18/96 | 0 | 0.998843/0.678241 |
| pitch_004 | 113 | 2/111 | 0/111 | 2 | null/null |
| pitch_005 | 100 | 1/99 | 0/88 | 12 | null/null |
| 合計 | 587 | 21/566 | 18/550 | 19 | 0.997576/0.793232 |

單類或沒有可配正例保持null，不把原break的缺值補成大距離。
框外但finite座標保留量測，原native score僅記錄，不作新cutoff。

## 六個重要關節

單位統一為原影像對角線比例，min／max均為全部相容native候選的分歧端點，非可靠度分數。
人工不可觀測／不確定按關節排除；模型缺值留在完整人工可靠／不可靠分母。
下表正例＝人工unreliable；負例＝人工reliable。

| 關節 | 完整正例／負例 | 有值正例／負例 | 人工排除 | min AUROC | max AUROC |
|---|---:|---:|---:|---:|---:|
| 投球肩 | 21/566 | 18/550 | 0 | 0.945657 | 0.892222 |
| 投球肘 | 84/444 | 78/434 | 59 | 0.793277 | 0.671777 |
| 投球腕 | 71/380 | 65/372 | 136 | 0.828164 | 0.697146 |
| 前導髖 | 4/582 | 2/566 | 1 | 0.944346 | 0.849823 |
| 前導膝 | 8/577 | 6/561 | 2 | 0.971777 | 0.745989 |
| 前導踝 | 5/579 | 3/563 | 3 | 0.986975 | 0.701599 |

前導腿有值正例僅2／6／3個，數字高不能視為穩定驗證。完整逐片、unique／ambiguous／none、
candidate_count=0–6分層都保留於JSON，沒有只呈現較好的端點。

局部手臂沒有跨片一致的效果：

| 影片 | 投球肘 min AUROC（有值正例／負例） | 投球腕 min AUROC（有值正例／負例） |
|---|---:|---:|
| pitch_001 | 0.875000（12/44） | 0.882353（17/18） |
| pitch_002 | null（0/156） | 0.341667（2/120） |
| pitch_003 | 0.802632（36/76） | 0.763158（12/76） |
| pitch_004 | 0.872340（6/94） | 0.689380（28/76） |
| pitch_005 | 0.570964（24/64） | 0.845528（6/82） |

原observed不代表對位：人工不可靠投球肘84格中72 observed／6 interpolated／6 missing；
不可靠投球腕71格中49 observed／3 interpolated／19 missing。
人工不可觀測投球肘59格中仍20 observed，腕136格中35 observed／4 interpolated。
這是原數值gate的狀態，不是可見性真值；本輪僅交叉列出，沒有改原分類。
人工reliable也可能與processed missing並存，因GT覆核的是raw overlay、clean的gate不同，不能混為同一目標。

## 人工可見XY效度與失效例

僅003有完整人工XY；排除frame0後1,195可見點全部可配，171不可觀測＋2不確定不打位置誤差分數。
原raw人工誤差與模型分歧的Spearman：min=**0.592146**、max=**0.110261**。
每個關節的相關性與配對數另存；這是描述性關聯，沒有改善原raw誤差或建立真實3D判定。

事前固定案例，例如003／38右肘raw誤差90.775px、分歧82.133–109.180px；
95右肩誤差147.370px、分歧140.845–149.899px；112左腕誤差252.367px、分歧246.229px。
這些可提供覆核線索，但不能只列有效案例。

封存後診斷也確認失效：003／100左腕raw誤差**151.056px**，兩候選分歧範圍卻是
**3.563–150.781px**；91左肘raw誤差99.728px，候選分歧9.572–103.031px。
某候選與原模型接近，仍可能同樣偏離人工位置；不能用min小就判可靠，
也不能用max大就宣稱投手身份錯誤。這兩例是描述性失效說明，沒有反向調規則或新增數值cutoff。

## 核對、圖與測試

- 獨立程序使用stdlib，未import producer／evaluator／statistics，重算42,624對距離
  （42,408 finite／216 missing）、3,552同slot torso RMS與7,104原model states。
- 全五球／六關節／association／candidate-count分層、pairwise AUROC、可見XY Spearman與完整分母一致。
  最大距離差1.14e−13px，屬浮點計算次序差，不是座標容忍門檻。
- 三張圖已實際檢視：五球torso timeline、六關節區辨性及003可見XY散點；沒有新增人工GT。
- 新增39項測試（producer11、evaluator15、statistics13）。離線試驗零推論；測試另執行既有MediaPipe E2E。
  完整suite **590 passed、0 failed、
  0 errors、2 skipped**，592項、58.844秒，包含正式五球MediaPipe E2E；兩skip為Windows符號連結限制。
- 374保護來源／62上游SHA、正式五球、raw、GT5/5與src不變；既有MoveNet量測嘗試仍592筆，未增加。
- 本地交付DB唯讀核對1批／8球／8 imported；八球全部candidate／pending，未分析或取代正式素材。

## 接續決定

保留同slot肩髖分歧作下一個major警示候選；不採用「範圍重疊即可靠」或「min小即可靠」。
局部肘腕需各自處理可見性、原model state與候選歧義，不能由major的高AUROC推成全部關節可信。
下輪先固定警示政策與校準／驗證的分離方法；若缺獨立正例，明確只作開發驗證，
不可拿這批高AUROC直接決定production門檻或宣布驗收。原break警示保留，正式核心不改。
**11格漏報未修復，Phase 2 = NOT PASSED；不進Phase3。**

輸出：`analysis_results/phase2_joint_disagreement_20261012_01/`；
`measurements/`、`evaluation/`、`figures/`、`visible_manual_pairs.json`、`fixed_case_diagnostics.json`、
`independent_audit.json`、`full_test_suite.log`保留完整依據。
