# Phase 2：RTMPose 原生位置回應單次驗證結果

日期：2026-10-17（台灣）。已按使用者「核准完整單次離線驗證」完成
[固定提案](phase2_rtmpose_response_proposal_20261016.md)。
提案保留核准前原文及 SHA；實際核准、來源和設定記於
[執行凍結](evaluation_plans/phase2_rtmpose_response_execution_20261017_02.json)。

**兩關節都未達事先採用規則，原生回應 deficit 提示不採用。Phase 2 = NOT PASSED。**
這輪已完成並停止。沒有重新選門檻、追加特徵或改用其他模型版本。
既有重大錯位覆核提示仍提供；沒有提示不能當成可靠認證。

## 1. 實際執行與相容性修正

- 固定官方 RTMPose-m Body7、256×192、20230504/e48f03d0，原生 COCO17。
  ONNX SHA：`5c0a4bf67953e6d2ac43ce15e77dc9d5d354ae18430a47d2c5963a7bc5683e3c`。
- 獨立 Python3.12.14／ONNXRuntime1.23.2 CPU／NumPy2.2.6；沒有更動分析或 MoveNet 環境。
  官方模型包與10份 wheel 共84,551,273 bytes；wheel 大小與官方 PyPI SHA 逐份核對。
- 首次 metadata guard 在 `.run()` **之前**停下：ONNX 把兩軸共同的17點維度記成
  `MatMulsimcc_x_dim_1` 符號，舊 guard 誤要求 literal17。當時合成／真人推論均0。
  舊01 manifests及錯誤 log 保留；02 amendment只修 metadata 驗證，不改模型或計算。
- 唯一合成推論實際產生 float32 `[1,17,384]`、`[1,17,512]`，才啟動真人量測。
  實際 tensor contract 沒有放寬；錯點數或 GT 不參與相容性判斷。
- 正式五球592格，每格一次新 RTMPose 呼叫，started/completed journal與完整 SimCC 保存。
  沿既有人工初始化 CSRT 框，沒有新 detector／tracker／ReID；不能稱完全自動身分確認。
- SDK 固定 RGB、padding1.25、bilinear affine、原生未正規化 SimCC、split ratio2；
  不做 flip、augmentation、其他色序或輸入大小試跑。
- 唯一訊號：原 Full 同名點經 affine 後的 nearest-bin 兩軸最大回應差之和。
  四片 canonical reliable 非seed列取最大值，第五片嚴格 `>` 才提示。五折均有效。
  OOF 封存後才讀 query GT 評估；003人工 XY只作輔助，不改主要標籤或校準。

## 2. 五球完整結果

TP＝提示人工錯點、FN＝漏掉錯點、FP＝提示人工好點、TN＝未提示好點。
影格0保存但不列主要成效；不可觀測及不確定另列，不當二元類別。

| 影片 | 全片格數 | 非seed可量測肘／腕 | 肘 TP/FN/FP/TN | 腕 TP/FN/FP/TN |
|---|---:|---|---|---|
| pitch_001 | 87 | 86／81 | 0/12/0/45 | 3/14/1/18 |
| pitch_002 | 175 | 174／174 | 0/0/0/158 | 0/2/0/120 |
| pitch_003 | 115 | 114／113 | 0/36/0/76 | 0/12/0/76 |
| pitch_004 | 114 | 111／111 | 0/8/0/94 | 0/30/0/76 |
| pitch_005 | 101 | 99／99 | 0/28/4/67 | 0/10/0/89 |
| 合計 | **592** | **584／578**（各587分母） | **0/84/4/440** | **3/68/1/379** |

肘原raw缺失3格；腕原raw缺失3格、原 Full 點落在原生 bin 範圍外6格。
證據不足的肘3／腕9格仍留主要 FN／TN分母，沒有裁掉難格提高數字。
肘不可觀測59格、腕136格，不確定皆0；腕另提示1格不可觀測（004/83），
不計 TP或FP。原生解碼有座標及正分數不等於關節可見或可靠。

## 3. 原本被 gate 接受的錯點與保留數

下表為提示負擔試算，原資料及可用判定未被改寫。

| 非seed合計 | 肘 | 腕 |
|---|---:|---:|
| 原gate支持 | 477 | 350 |
| 其中人工錯點 | 72 | 49 |
| 新訊號抓回錯點 | **0** | **3** |
| 額外提示好點 | 4 | 1 |
| 新提示後仍無提示的原支持 | 473 | 345 |
| 其中人工可靠保留 | 381 | 265 |
| 其中仍未提示的人工錯點 | **72** | **46** |
| 其中不可觀測 | 20 | 34 |

相對既有29格重大覆核提示，肘增4格（全是好點）、腕增5格（3錯／1好／1不可觀測），
兩關節重疊皆0。這是關節提示增量，不能算成新的 major TP。
原 sample-maximum 對 gate通過錯點抓回7／8，本輪0／3未達改善要求。

## 4. 執行前凍結規則的決策

| 條件 | 肘：實際／要求 | 腕：實際／要求 |
|---|---|---|
| 五fold有效 | 5/5，符合 | 5/5，符合 |
| TP | 0／≥17，不符合 | 3／≥27，不符合 |
| FP | 4／≤1，不符合 | 1／≤1，符合 |
| 非003 TP | 0／≥10，不符合 | 3／≥23，不符合 |
| 非003至少兩片各優於原兩基準 | 0／≥2，不符合 | 0／≥2，不符合 |
| gate通過錯點提示 | 0／>7，不符合 | 3／>8，不符合 |

**不提出採用，不接正式流程。** 原 score-only、sample-maximum、分類器比較均保存在 JSON。
這是新提示的採用規則，不是新增的 Phase2整體「零錯誤」或更多標註要求。
003作測試時肘／腕皆無提示；104格肘 deficit0.43684247低於四片最大值2.22743955，
仍是已知漏報。腕該格 canonical不可觀測，deficit0.02080244低於1.51717933；
不把它當人工可靠點。原人工 major hold及可見性來源差異保持。

## 5. 003可見 XY的輔助結果

只比較非seed、人工可見、兩模型皆有 finite座標的相同集合；遮擋不補透視位置。

| 關節 | 共同可比格 | Full平均誤差px | RTMPose平均誤差px | Full P95px | RTMPose P95px |
|---|---:|---:|---:|---:|---:|
| 投球肘 | 92 | 27.7461 | **7.3101** | 106.5538 | 14.9167 |
| 投球腕 | 58 | 26.6556 | **16.8405** | 84.5741 | 73.4950 |

這是實際座標改善的證據，但只適用003既有可見點、且使用既有人工初始化主體框。
腕最大誤差108.0667→127.9342px，仍有嚴重錯點。其他四片精確誤差保持null。
「新座標局部更準」與「能自動識別原 Full 錯點」是兩個問題；
本輪後者失敗，不據此更換正式模型、宣稱五片準確或讓 Phase2通過。

## 6. 保存、驗證與停止點

輸出：`analysis_results/phase2_rtmpose_response_20261016_01/`（沿用開始日16的目錄）。
包含舊guard失敗紀錄、amendment、SDK／runtime receipts、GT盲輸入、592原生輸出、
十個校準／五份OOF、完整逐格評估及獨立核對。
[版本化結果摘要](evaluation_plans/phase2_rtmpose_response_result_20261017_01.json)保存決策及來源SHA。
另完成[漏報可見性核對](phase2_visibility_gap_audit_20261016.md)，沒有改GT解決來源差異。

本輪34項新合成測試，覆蓋原生shape、symbolic metadata、nearest bin、缺值、
GT隔離、四片校準、strict equality及未知分母。
完整suite **918項：916 passed、0 failed、0 errors、2 skipped**，54.701秒、exit0。
兩skip為Windows file symbolic link能力；junction測試實際執行。
正式五球E2E重大提示仍為2／0／19／5／3；467保護來源及62上游SHA不變。
獨立審核重算10,064個原生點、1,184筆deficit及OOF、十個四片最大值，差異0；
每fold只讀其他四片GT，APPLY人工輸入0。592 started／592 completed，沒有重複呼叫。
核對紀錄另存於[版本化audit](evaluation_plans/phase2_rtmpose_response_audit_20261017_01.json)。

Phase1仍PASSED；Phase2 evaluation COMPLETE WITH KNOWN LIMITATIONS，
**Phase2 automatic reliability NOT PASSED**。原核心、gate、selector、raw、人工GT及正式五球保持。
依本輪核准規則停止調整此訊號；不擴大模型搜尋、不新增標註、不分析8顆交付候選、不進Phase3。
