# Phase 2：既有五支影片的影像／幾何量測實驗

日期：2026-10-06。狀態：**離線量測與人工參考比較完成；Phase 2 = IN PROGRESS。**

## 本次完成與結論

使用正式五支 Yamamoto MP4、既有 raw predictions、HSU 的五份定性 GT，
以及 Tsai 標點／HSU 覆核的 pitch_003 可見座標參考，共量測592格。
沒有重跑五支影片的 pose inference、修改正式 tracking／pose／confidence gate、
改寫人工標註或產生新 warning。沒有訓練或更換模型。

逐格影像移動與 raw 骨架中心的差異，在003的87–104重大錯位區段提供可研究的線索。
但影像特徵會漂到投手外，正常動作也有差異，局部手臂證據的區分能力跨片不一致。
**目前不能把這項實驗加入正式可靠性 gate，也不能因此宣告 Phase 2 通過。**

## 資料與輸出

- 原片：`input/yoshinobu_yamamoto/phase1_final/pitch_001..005.mp4`。
- 保存的模型資料：`analysis_results/phase2_yamamoto_20260925_01/predictions/yoshinobu_yamamoto/`。
- 定性 GT：同一 baseline 的 `ground_truth/pitch_001..005/ground_truth.json`。
- 可見人工座標：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_42/pitch_003/manual_keypoints.json`。
- 新量測根目錄：`analysis_results/phase2_image_geometry_measurements_20261006_01/`。
- 最終比較：上述根目錄的 **`evaluation_02/`**。

每支的 `image_pose_measurements.json` 保存逐格影像特徵、raw 2D幾何與缺少證據原因。
`measurement_run.json` 保存固定參數、程式hash與runtime版本。
最終比較包含 `evaluation_summary.json`、`per_frame_evaluation.json`、
`visible_coordinate_evidence.json`、來源完整性檢查、五張timeline及003特徵分布圖。
原有 `overlay.mp4` 保持不變。

初次 `evaluation/` 的 pooled key 誤用 `_px` 命名，實際數值已除以影像高度。
修正 evaluator 的單位命名後另建 `evaluation_02/`；原版保留。
量測、所有數值、逐格比較及人工座標誤差完全相同，沒有覆寫第一次結果。
各片與 pooled 的 `_image_height` 值都是影像高度比例；圖及逐格 `_px` 值才是pixel。

## 方法與限制

獨立量測器 `scripts/measure_image_pose_evidence.py` 只讀 MP4、input manifest、
video metadata、raw keypoints、selector capture及clean gate設定。
它不讀人工 GT、manual X/Y或已知問題frame。人工資料只由另一支
`scripts/evaluate_image_pose_evidence.py` 在量測完成後讀取。

1. 以最早通過原有四個軀幹端點 gate 的影格建立raw肩／髖多邊形初始區域。
   該區域與特徵是否確實屬於投手**尚未驗證**。
2. 在區域內擷取 Shi–Tomasi 影像特徵，以雙向 KLT 光流逐格延續。
   原始特徵只建一次，不重新初始化，不用人工答案選取新位置。
3. 保存每個特徵的前後向status、位置、FB往返誤差、存活數及分布面積。
   成功status＋有限且位於畫面內的座標只表示數值可計算；沒有設定FB誤差篩選門檻。
4. 相鄰移動使用同一批存活點的前一格／這一格差異。
   累積移動使用同一批存活點的原始seed／這一格差異，沒有累加成員不斷變動的median。
5. raw四點中心移動與影像移動相減，產生step／cumulative差異。
   raw缺少或未通過原gate時留null；影像特徵仍存活不代表raw比較有資料。
6. 另在前一格raw關節位置做相鄰patch探測；每一對frame獨立計算，
   不等於重新初始化軀幹追蹤。起點可能已在打者或背景，不能當成人工關節位置。
7. 保存raw投影上臂／前臂長度、方向與跨格角度差；另保留端點是否通過原gate。
   這是2D投影，轉身、縮短投影與遮擋均會改變數值，不能當成真實骨長或3D生物力學。

參數在人工比較之前固定：最大80特徵、corner quality .01、間距4px、block7；
LK window21×21、max level3、30 iterations、epsilon .01、min eigenvalue .0001；
至少3個非共線點才能算影像移動。這些是實驗解算設定，不是新pose或warning gate。
`warning_thresholds = null`；沒有選cutoff、依GT調參、擬合分類器或產生新判定。
量測runtime：OpenCV5.0.0、NumPy2.5.3。

## 五支影像證據品質

五支皆在frame0建立seed。下表的「可計算」**不是可靠foreground或有效pose比例**。
FB統計涵蓋保存的可計FB特徵探測；大誤差沒有被刪除。
分布擴張為當前／相同存活cohort之seed凸包面積比。

| 影片 | 總格 | 光流數值可計算格 | seed／結尾存活點 | FB P99 px | FB最大 px | 最大分布擴張 |
|---|---:|---:|---:|---:|---:|---:|
| pitch_001 | 87 | 86 | 23／21 | 43.528 | 156.545 | 12.850倍 |
| pitch_002 | 175 | 174 | 51／19 | 38.121 | 267.159 | 8.912倍 |
| pitch_003 | 115 | 114 | 62／55 | 58.500 | 365.897 | 20.161倍 |
| pitch_004 | 114 | 113 | 59／48 | 81.433 | 250.769 | 9.294倍 |
| pitch_005 | 101 | 100 | 59／46 | 43.448 | 333.547 | 3.600倍 |

實際檢視003的0、38、95、112原圖特徵分布，95／112有點散落到投手外。
其中部分FB誤差很小，表示來回能追到同一塊影像，仍不證明影像屬於投手。
003在114個轉換均保有數值支援，不能解讀成114個轉換都追對主體。
002沒有人工全身重大錯位，仍有特徵大量流失與累積差異，不能只看差異是否變大。

## 全身重大錯位比較

固定人工分母：21正例／571負例。正例為003的87–104共18格、004的75–76共2格，
005的54共1格。影像不足／raw缺少不能移除原始人工分母。

| 證據 | 有值正／負 | 缺值正／負 | 正例median（高度比例） | 負例median | 條件排序AUC |
|---|---:|---:|---:|---:|---:|
| 相鄰step差異 | 18／564 | 3／7 | .020659 | .002598 | .928684 |
| seed→current累積差異 | 18／566 | 3／5 | .084699 | .066293 | .705830 |

AUC只問「有量測值的正例是否傾向比較大」，不是召回率、精確率、通過率或新增總分。
沒有warning cutoff，因此沒有新warning TP／FP／FN或誤警率。
**18個有值正例全部來自003同一區段**；五支均為已知開發／回歸資料，沒有獨立holdout。
004／005的3個骨架缺失正例保持缺值；由既有track-break結果另外評估，不能當成新證據抓到。

003片內：step AUC .924190、正／負median .020659／.002499；
cumulative AUC .763889、正／負median .084699／.055854。
003的正常負例累積差異最大 .122892，與錯位正例重疊；
001正常負例累積差異最大 .228366，超過003所有正例。
因此累積偏移不能直接等同錯位，step線索也需先處理影像前景品質與正常快速動作。

step缺值：各片frame0、004的75–77、005的54–55。
cumulative缺值：各片frame0、004的75–76、005的54。
恢復後cumulative仍與原seed比較，沒有重設起點。逐格輸出另外列raw缺少、原gate不足、
selector未選取與影像移動缺少等原因；null不作為零差異或可靠證據。

## 六關節與手臂幾何

下表是local patch差異的條件AUC。括號為「有量測的不可靠正例／所有人工不可靠正例」；
沒有可量測正例時留空。各片完整可靠負例數、缺值與not_observable排除數保存在JSON。

| 關節 | 001 | 002 | 003 | 004 | 005 |
|---|---|---|---|---|---|
| 投球肩 | —（0／0） | —（0／0） | .859（18／18） | —（0／2） | —（0／1） |
| 投球肘 | .636（12／12） | —（0／0） | .674（36／36） | .582（5／8） | .412（27／28） |
| 投球腕 | .461（17／17） | .546（2／2） | .633（12／12） | .541（26／30） | .618（9／10） |
| 前導髖 | —（0／0） | —（0／0） | .870（2／2） | —（0／2） | —（0／0） |
| 前導膝 | .953（1／1） | —（0／0） | .736（3／3） | .981（1／3） | .768（1／1） |
| 前導踝 | —（0／0） | —（0／0） | .815（2／2） | —（0／2） | .979（1／1） |

肘／腕差異未在各片呈現一致可靠區分；少量腿部正例的高AUC也不足以決定規則。
不把canonical不可觀測區間強迫當成可靠或錯誤座標。

| raw 2D幾何的條件AUC | 001 | 002 | 003 | 004 | 005 |
|---|---:|---:|---:|---:|---:|
| 上臂投影長度 vs 投球肘不可靠 | .375 | — | .434 | .767 | .688 |
| 上臂跨格角度變化 | .596 | — | .633 | .606 | .390 |
| 前臂投影長度 vs 投球腕不可靠 | .477 | .054 | .677 | .443 | .432 |
| 前臂跨格角度變化 | .303 | .404 | .361 | .479 | .649 |

所有列均固定「較大為正例」方向，沒有依每支結果翻轉判定。
可見投影縮短、正常高速揮臂及已有錯位起點均可能干擾；不能直接轉成骨長／角度門檻。

## 可見人工座標案例

1205個visible點逐點重算，173個not_observable及2個uncertain不參與座標誤差。
1205個raw點皆存在；median9.715px、P95 102.634px、最大252.367px，與原參考比較一致。

| 003 frame／關節 | raw座標誤差 px | local patch差異 px | patch FB往返誤差 px |
|---|---:|---:|---:|
| 38／右肘 | 90.775 | 52.029 | .022 |
| 38／右腕 | 108.067 | 104.566 | .018 |
| 93／右肘 | 166.563 | 84.951 | .088 |
| 95／右肩 | 147.370 | 19.463 | .030 |
| 112／左腕 | 252.367 | 178.699 | .120 |

大座標誤差並不保證patch差異同樣大；低FB也不表示raw點位正確。
112左腕沿用額外可見座標案例，不新增canonical六關節GT。
人工被遮擋部位原始推測仍可保留作獨立來源紀錄，沒有當成可見真值或拿來訓練。
本次不量測事件誤差，因baseline沒有自動事件預測。

## 測試、稽核與保存

新增11項合成／保存資料測試：已知影像平移、stationary image對raw跳位、
相同存活cohort、空間不足null、角度wrap、低confidence／缺點、禁止覆寫、
不讀人工GT、不改raw、保留缺值正例分母、AUC ties／無正例，以及raw缺少理由。
完整suite：**159 discovered，158 passed／0 failed／0 errors／1 skipped**。
略過項為要求設定 `PITCH_ANALYSIS_REAL_BASELINE_DIR` 的真實MP4 E2E；本次未重新推論正式五支。

第一次沙盒執行90 passed、68環境errors、1 skipped，均為Windows strict realpath權限拒絕。
以相同測試／validator在沙盒外重跑成功，沒有修改或略過失敗測試。
兩次log及result JSON都留在新量測根目錄；暫存限定在專案`.cache/`。

295份受保護source／GT／raw outputs／影片hash不變，42個比較來源hash相符。
獨立唯讀稽核重算分母、缺值、所有major／joint／geometry AUC及1205座標，結果均一致。
producer／parameters／最終evaluator hash已保存；warning數值門檻仍null。
來源XML的私人帳戶資料、原片及大型generated artifacts不上傳；腳本、測試、報告與狀態納入Git。

## 下一步

先提出一個有界的影像證據有效性實驗：分開評估FB誤差、空間分布與主體前景支援，
保留abstention，對正常動作及已知錯位同時驗證。需先固定候選方法與評估方式，
另開新輸出，不在這次資料上事後選cutoff並直接加入production。
只有可靠證據成立後，才決定additive warning或其他修正；HSU無須重做已完成的003覆核。

Phase 2仍在進行中，peer pitch_005事件補充待回傳。維持原本Clipper交接順序：
Phase 2穩定並經證據驗收後，再做少量single-pitch MP4＋pitch-input-v1 JSON交接；
不合併專案、複製取得／剪輯邏輯或自行進入Phase 3。
