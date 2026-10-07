# Phase 2：讓已覆核的關節資料決定既有角度能否使用

日期：2026-10-07。**Phase 2 = IN PROGRESS。**

## 實際完成的改進

上一個 checkpoint 已能看每格人工／模型關節狀態。本次新增
`scripts/export_reviewed_feature_quality.py`，將它們接到 baseline 已保存的兩種2D角度：

- `throwing_elbow_angle`：投球肩、投球肘、投球腕。
- `lead_knee_angle`：前導髖、前導膝、前導踝。

輸出每片的 `reviewed_features.csv`、`reviewed_feature_quality.json`、
`feature_use_timeline.png`。CSV保留完整原值，另有`eligible_value`：
原值有限、為直接觀測，三個組成關節都有原人工定性可靠證據，且沒有整格覆核限制時
才保留；其他情況留空，逐格附原因。

這讓後續使用者可以明確避開本批影片已知問題的數值，
而不是只看feature coverage就當成角度正確。
這是**覆核後的資料使用檢視**，不修改正式`analyze-pitch`或原`features.csv`／`metrics.json`。
正式流程尚未自動消費這份側檔。沒有重新推論、增加動作特徵、比較投手或開始Phase 3。

## 五片結果

每個feature仍以整支影片格數為分母；有原值不等於符合人工覆核使用條件。

| 影片 | 總格數 | 手肘原值／可保留 | 手肘原值暫不採用 | 前導膝原值／可保留 | 前導膝原值暫不採用 |
|---|---:|---:|---:|---:|---:|
| pitch_001 | 87 | 45／18 | 27 | 84／81 | 3 |
| pitch_002 | 175 | 119／112 | 7 | 175／173 | 2 |
| pitch_003 | 115 | 66／38 | 28 | 106／86 | 20 |
| pitch_004 | 114 | 61／35 | 26 | 111／103 | 8 |
| pitch_005 | 101 | 75／43 | 32 | 90／87 | 3 |
| 合計 | 592 | 366／246 | 120 | 566／530 | 36 |

「原值」包含原流程允許的座標插值，因此與原metrics的raw-observed數目不同。
原metrics的raw-observed合計為手肘350、膝548；其中104、18個原始觀測值
不符合這次的覆核使用條件，另外16、18個有原值的座標插值點不被認證。
保留／暫不採用各種原因會重疊，完整原因計數不應相加成格數。

`pitch_003`的87–104格兩種角度全數保留原值或原缺失狀態，
新`eligible_value`皆留空；這是沿用已確認重大失效的保守整格限制。
**沒有把個別關節原有的人工reliable改成unreliable**，也沒有聲稱每個點都错。

246／592、530／592是本批已覆核輸入的保留覆蓋率，
**不是角度準確率、新的通過分數、影片排名或新的confidence threshold**。
原Phase1 gate仍維持，不用此側檔重新宣布Phase1失敗或降低門檻。

## 怎麼看、怎麼用

最終輸出：`analysis_results/phase2_reviewed_features_20261007_02/`。
先開同目錄`START_HERE.md`，看各片時間軸圖。

- 綠色：組成點有人工定性對位證據，原feature為直接觀測，可依覆核保留。
- 紅色：整格重大失效／中斷等覆核限制；原各關節判讀仍分開保留。
- 橙色：至少一個所需關節人工不可靠。
- 黃色：至少一個所需關節無法核對／不確定；不推定位置必錯或遮擋原因。
- 紫色：原有座標插值未經人工座標覆核。
- 灰色：沒有原base角度值。

圖用一個主類別顯示；JSON保存全部原因，不會因顏色優先順序丟掉其他限制。

CSV的`*_original_base`保留原值；`*_eligible_value`只供符合覆核條件的資料使用。
空白要保持空白，**不要當0、不要跨缺口補值、不要擅自重做平滑或軌跡重採樣**。
JSON另外保存原feature interpolation／smoothed數值與flag，明確標為未認證。
当前格的可靠關節不能驗證平滑所使用的相鄰格；這次只保留unsmoothed base欄位。
不重算子集min／max／median或提供新的生物力學解讀。

## 可追查與驗證

- [最終執行計畫](evaluation_plans/phase2_reviewed_features_20261007_02.json)
  綁定程式／測試、既有feature／geometry／GT程式、五片CSV／原metrics／quality／review側檔及字型。
- 使用前完整重建原review側檔，與canonical GT、raw／processed、handedness、原影片SHA及時間對齊。
  不接受被手改的derived view、混片、漏格、矛盾的saved state或feature旗標。
- 已保存的base角度以原width／height投影座標獨立重核，
  absolute1e-8／relative1e-10僅為浮點序列化容差，**不是位置準確性或角度驗收門檻**。
  原metrics的raw數目與coverage逐項與CSV一致；沒有拿人工點重建模型角度。
- 五片共592格／1,184個feature列完整保存；新可用值不是補點或raw prediction修改。
- 初次`_01`輸出保留；最終版本補足整格`uncertain`與`not_observable`的原因區分，
  原人工frame evidence也直接保存在側檔。初版程式／測試逐位元保存在
  `_01/implementation_snapshot/`，未覆寫舊輸出；本批保留數目沒有變。
- 新增12項測試：三點相依、局部與整格限制、不可見與錯點區分、插值不可繼承認證、
  缺失／零值、相鄰平滑未認證、原始投影比例、來源矛盾、全格分母與CSV空值。
- 已實際檢查五張時間軸圖的版面／文字與範圍。測試、獨立核對紀錄在最終輸出目錄。
- 完整測試：**215 passed／0 failed／0 errors／0 skipped**，含五片真影片E2E，約43秒。
  獨立覆核通過全部592格／1,184列、原值／旗標／空值、全部時間軸色塊與逐項摘要；
  349份不重複綁定／歷史保護來源未變。408個暫不採用的可用欄位、252個原缺失值
  皆維持空白；沒有把缺失變成0。

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts/export_reviewed_feature_quality.py --plan docs/evaluation_plans/phase2_reviewed_features_20261007_02.json --output analysis_results/<new_feature_review_output>
```

## Phase 2仍未通過的部分

原自動錯位警示沒有被本工具改好。已知003持續偏移仍存在漏報，
未見影片沒有這批人工覆核，不能宣稱自動給出同等可靠性。
保留原5/5 reviewed GT、005獨立事件補充待辦與所有原始預測。
骨架演算法、PitcherSelector、既有threshold／gate、模型、平滑／插值均未改。

共用交付資料夾仍未接入；Phase2穩定、輪到該待辦時先停止回報，等待使用者開始指示。
