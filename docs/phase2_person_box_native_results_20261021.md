# 單球人物框修正結果：完成，不採用本次選人政策

2026-10-21（台灣）。[核准方案](phase2_person_box_native_plan_20261021.md)、
[使用方式](phase2_person_box_native_usage.md)、[版本化結果](dataset_selections/ohtani_person_box_results_20261021.json)。

**本次固定選人政策 = NOT ADOPTED；Phase 2 自動可靠性 = NOT PASSED。**

已完成核准的實作、一次性執行、影像抽查及完整測試。
人物偵測器在抽查中能分別框出投手與打者，但兩個人物框的中心都可能落在原操作ROI內，
本輪「唯一合格框才跑pose」因此造成大量missing。這不是可用的可靠性改善，不接入正式流程。

## 實際執行與可用性損失

只處理 `supplement_002`，來源批次 `20261020T073530Z_6gyr6IC2e0Q`。
321格完整保留，1280×720、60000/1001 FPS，第0格0秒。
實際執行時間2026-10-21 05:19:25–05:24:40 UTC；沒有重跑舊MediaPipe或上輪五球RTMPose。

| 項目 | 實際結果 |
|---|---:|
| Detector嘗試／完成 | 321 / 321 |
| Pose嘗試／完成 | 2 / 2 |
| 唯一框／執行pose | 第193、194格，共2格（0.6231%） |
| 多框歧義 | 319格（99.3769%），每格恰好2個合格框 |
| 無合格框 | 0格 |
| 新增missing | 0–192格、195–320格，共319格 |
| 最長missing span | 193格；另一段126格 |
| 執行失敗／重試／warmup | 0 / 0 / 0 |

舊RTMPose在321格都有座標；新政策只剩2格，**失去319格，不能算作錯點修正**。
投球肩／肘／腕與前導髖／膝／踝各自都是321→2格有座標，新增319格missing。
這是模型座標可用數，不是人工可靠率，也沒有將新結果套入原MediaPipe gate。
逐格清單與六關節比較保存在本機`comparison_summary.json`。

原生17點未執行時全為missing、score=null、input_mode=not_run，ROI與affine=null；
沒有用最高分猜人、沿用前格人物框、舊骨架fallback或虛構座標。
僅193／194格呼叫原RTMPose，姿態分數仍未校準，usable_for_analysis=null。

## 模型來源與固定設定

只從核准OpenMMLab URL下載一個YOLOX-m HumanArt archive，HTTP200，94,223,081 bytes。
Archive SHA：`a000224fd8ba283202bc62d4a5fcdfe353adb9f468777dbac1ea2ada2093adde`。
ONNX SHA：`3dea6513388889f0fff4b77bf7a26013600321b9eb9ceb0e9a400a82572f5f23`。
既有隔離環境相容，沒有安裝／升級套件、換鏡像或換模型。

ONNX graph實際NMS為score約0.01、IoU約0.65，與pipeline.json相符；
detail.json列的0.05／0.5沒有用來覆蓋graph。保留原生NMS，不做第二次NMS，最後固定score≥0.7。
label0=person由上游80類COCO定義核對。此處是新detector設定，原正式confidence／quality gate保持。
SHA、graph常數、metadata與授權來源紀錄在
`analysis_results/phase2_person_box_preparation_20261021_01/`，模型留在本機，未重散布。

## 實際影像檢查

已看完6張contact sheet，共22組原片／舊RTMPose／新結果：
原訂20格，加上唯一執行pose的193、194格。這是Codex代理抽樣，不是新增人工GT。

- 第0／19／38／56／75格，人物框可分別包圍投手與打者，但兩框都符合框中心ROI條件，故missing。
- 第113／132／151／159／169／188格到收尾的抽樣，也保留兩個合格框，沒有產生新骨架。
- 第193、194格的新骨架靠近投手輪廓，局部關節準確率沒有人工真值可量測。
- 第201／207／226／245／264／282／301／320格仍多框歧義。
- 原準備段錯位變成missing，不表示已可靠重建或穩定追蹤；identity switch確認保持null。

觀看圖中的琥珀框只是合格候選框，沒有替人工作身分標註。
全片321格overlay已編碼並完整解碼，原尺寸／FPS保持，最大時間差約`9.095e-13 ms`。
沒有選中bbox超出動作crop的格；這不能作為全片手腳完整／正確的證明。

## 測試與保存

新增36項無模型測試；完整suite **1093 run、1091 passed、0 failed、0 errors、2 skipped**，
總耗時83.812秒。正式山本五球MediaPipe E2E已啟用，major提示仍 **2／0／19／5／3**。
兩項skip為Windows檔案symlink權限；junction測試實際執行。完整測試沒有呼叫真實detector或RTMPose。

541個保護檔案SHA全部不變，涵蓋原素材、GT、raw、舊輸出與權重；同格像素／時間對照0錯誤。
核准native幾何／contract的5個既有程式檔另記修改前SHA，未將允許的程式變更混成資料異動。
321份detector binary加2份pose binary全部核對SHA；journal連號且無超額呼叫。
一次性claim已保留，換新輸出路徑仍拒絕重跑。

正式MediaPipe、PitcherSelector、分析核心、confidence／quality門檻、插值／平滑均未修改。
正式五球、其他候選、raw與人工GT不變；新增人工標註0、素材提升0、Phase3工作0。

## 檔案與停止決定

新增獨立detector worker／transport、框選擇與單球producer／CLI／設定；
native estimator增加可選當格bbox，native contract增加嚴格not_run語義與cached envelope檢查；
native overlay增加框狀態。未提供bbox的舊行為保持，完整suite已驗證。

本機輸出：`analysis_results/phase2_person_box_native_20261021_01/`。
先看`review_all.html`，另有逐格人物框、原生JSONL／binary、完整overlay、比較與保存核對。
大型結果與權重不加入Git；Git保存實作、設定、精簡結果與文件。

依核准方案：本輪完成後停止，**不採用這個選人政策為可靠性修正**。
不調整ROI／分數、添加小規則、換模型、擴跑其他四球或自行進Phase3。
Phase 2維持NOT PASSED；沒有新增零錯誤或更多人工標註的驗收條件。
