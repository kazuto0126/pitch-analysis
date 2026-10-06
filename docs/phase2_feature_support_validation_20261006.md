# Phase 2：影像特徵的軀幹支援驗證

日期：2026-10-06。**本次離線驗證完成；Phase 2 = IN PROGRESS。**

## 結論

上一輪量測已發現影像特徵散開；本輪用HSU已覆核的003可見肩、髖座標，
獨立檢查特徵與軀幹幾何的關係。結果確認：**往返誤差小、移動一致、特徵存活，
均不足以保證特徵仍支援投手的軀幹位置。** 尚未得到可採用的foreground驗證方法。

003可比較106／115格；逐格最低FB分位群中1031／1530個特徵格落在可見軀幹四點凸包外。
第86格的55個特徵全在該範圍外，FB最大仍只有.000829px。
此格在canonical紀錄中不是全身major pose failure，證明影像特徵的支援問題
不能直接等同骨架重大錯位。

**四點凸包不是完整身體輪廓。** 在凸包外的點仍可能位於肩部衣物、頭、手臂等投手部位；
凸包內也不構成身分證明。不能把上述比例叫作「背景追蹤錯誤率」，
不能自行新增identity-switch或ground truth。其他四片沒有同等可見人工座標參考，
其定量proxy結果全部保留unavailable／null。

正式MediaPipe、PitcherSelector、pose／tracking演算法、gate與平滑／插值不變。
沒有重跑正式五片pose、補人工遮擋位置、訓練、換模型、調門檻或產生新warning。

## 固定方法與可重現輸出

量測前固定的方案：[phase2_feature_support_20261006.json](evaluation_plans/phase2_feature_support_20261006.json)。
使用上一輪已保存的 `analysis_results/phase2_image_geometry_measurements_20261006_01/`，
不重新取得影片或計算光流。新輸出：
**`analysis_results/phase2_feature_support_20261006_01/`**。

- `feature_validity_measurements.json`：GT-blind的特徵品質、rank與分布量測。
- `evaluation/feature_support_summary.json`：五片摘要與003人工proxy比較。
- `evaluation/feature_support_rows.json`：全部28185個可用特徵格及null。
- `evaluation/frame_support_summary.json`：592格可評／缺少參考原因。
- `evaluation/*_uniform_review.png`：五片各0、1/3、2/3、結尾的四格圖。
- `evaluation/pitch_003_proxy_review.png`：003原圖、可見人工凸包與特徵的對照。
- `agent_visual_inspection.json`：Codex的診斷觀察，明確標記不是human GT。
- `completion_integrity_check.json`及完整test suite log／result。

獨立量測器 `scripts/measure_feature_validity_evidence.py` 只讀固定計畫、原量測及
來源綁定資訊；不讀人工標註內容。它保留原 `numerically_usable` 特徵集合，
不篩點、不重新初始化、不補新座標。連續品質量測為：

1. 保存的FB往返誤差。
2. 每個特徵的移動向量到同cohort componentwise median移動的距離。
3. 目前特徵位置到同cohort median位置的距離。
4. 原seed存活率與同存活cohort的分布面積擴張比。

FB另做每格與每片兩種描述性rank分群。Rank為
`(嚴格較小數＋0.5×同值數)／有值數`，群組為`min(floor(4×rank),3)`。
相同值同群，缺值留null，不為湊等量而拆開ties。
這些是相對分位描述，不是新warning cutoff；每片rank讀取整片，屬離線分析。

另一支 `scripts/evaluate_feature_support_evidence.py` 才讀既有人工資料。
僅當左右肩／髖四點皆visible且凸包非退化時，計算特徵到凸包的signed distance。
邊界距離≥0算inside；未放大範圍、調整容忍度或用raw點替代缺少人工點。
正部outside距離為`max(0, -signed_distance)`，inside值為0；JSON的該距離統計包含所有可評點。
兩端支援需要前、後兩格proxy，缺一端則null，不能改用三點三角形或插值。

## 五支的覆蓋率與品質

「特徵格」指一個特徵在一格的紀錄；同特徵跨格高度相關，不是獨立人工樣本。
下表品質值仍是影像量測，不能當成foreground或pose通過率。

| 影片 | 總格 | 可用特徵格 | 人工proxy可評格 | FB P99 px | 移動離散P95 px | 分布徑向距離P95 px |
|---|---:|---:|---:|---:|---:|---:|
| pitch_001 | 87 | 1898 | 0／87 | 43.528 | 9.630 | 140.871 |
| pitch_002 | 175 | 7824 | 0／175 | 38.121 | 4.168 | 70.448 |
| pitch_003 | 115 | 6783 | 106／115 | 58.500 | 13.153 | 151.344 |
| pitch_004 | 114 | 6320 | 0／114 | 81.433 | 12.773 | 121.335 |
| pitch_005 | 101 | 5360 | 0／101 | 43.448 | 11.315 | 79.768 |

其餘四片的0是沒有人工軀幹座標參考，不是0個正確frame或全部通過。
五片共592格，106格有proxy，486格缺少此參考；未移除原始分母。

## 003完整缺值與支援分母

人工來源為
`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_42/pitch_003/manual_keypoints.json`，
全部既有可見性、XY、confidence／notes及reviewer provenance保持不變。
70–78右肩not_observable，共9格、495個特徵格沒有current proxy。

| 比較 | 完整分母 | 有參考／值 | 缺少 |
|---|---:|---:|---:|
| current proxy影格 | 115 | 106 | 9 |
| 相鄰pair proxy轉換 | 114 | 104 | 10 |
| current proxy特徵格 | 6783 | 6288 | 495 |
| pair proxy特徵格（含seed紀錄） | 6783 | 6171 | 612 |
| pair proxy特徵格（只計轉換） | 6721 | 6171 | 550 |
| 有proxy的FB／移動品質值 | 6288 | 6226 | 62個seed無前一格 |

Pair缺少包含70–79轉換；當前79已恢復人工proxy，但前一格沒有。
含seed列另加62個無前一格紀錄，不能當成track break或feature failure。
6288個current可評特徵格為inside2012、outside4276（68.00%在proxy外）。
有效pair6171筆為兩端inside1873、僅前一端134、僅當前79、兩端皆outside4085。

| 003 frame | inside／可用點 | FB median px | 解讀限制 |
|---|---:|---:|---|
| 0 | 60／62 | 無值 | 初始支援；兩個outside最大距離2.389px，不是完整seed身分真值 |
| 38 | 5／62 | .051961 | 正常major負例；凸包狹窄，衣物側面可在proxy外 |
| 70–78 | unavailable | 另存量測 | 右肩被遮擋，不補人工位置 |
| 86 | 0／55 | .000116 | major負例；低FB仍不支援人工軀幹 |
| 95 | 0／55 | .324492 | 已知major正例；不能單憑proxy推導identity switch |
| 114 | 5／55 | .000246 | major負例；seed存活55／62仍無法保證軀幹支援 |

## 低FB分群與連續品質的比較

| 最低FB相對群 | 可評特徵格 | 涵蓋格數 | inside | outside | outside比例 |
|---|---:|---:|---:|---:|---:|
| 每格rank的最低群 | 1530 | 105 | 499 | 1031 | 67.39% |
| 整片rank的最低群 | 1523 | 57 | 623 | 900 | 59.09% |

兩種群組的時間條件與涵蓋格數不同，不能把59.09%對67.39%當成改善幅度。
資料仍保留全部群組，不以最低群替代完整分母，也不選出一個門檻給production。

僅為描述性比較的「較大值是否傾向proxy outside」條件rank AUC：

| 候選品質 | outside／inside完整數 | 有值outside／inside | 條件AUC |
|---|---:|---:|---:|
| FB往返誤差 | 4276／2012 | 4274／1952 | .686611 |
| 同cohort移動離散 | 4276／2012 | 4274／1952 | .665907 |
| 到cohort中心的徑向距離 | 4276／2012 | 4276／2012 | .534170 |

這是known-development且有時間／特徵相關性的proxy比較，
不是foreground分類準確率、警示recall、獨立驗收、總分或投手排名。
不根據結果改方向或擬合組合規則。

003的major正例18格有990特徵格、983在proxy外；
major區間之外有5298特徵格、3293在proxy外。
後者包含88個有proxy的frame；另外9個major負例frame缺proxy。
所以proxy outside既不能等同骨架major failure，也不能自動指認某個關節錯誤。

## 實際看圖的診斷觀察

已實看五張uniform contact sheet及003人工proxy對照，這些是Codex診斷觀察，
與HSU／Tsai的人工GT分開保存：

- 001結尾86有點靠近打者鞋部；仍有部分點在投手附近。
- 002早期多在背部衣物，174有最低FB群的點落在背景MLB標誌附近。
- 003的38有點在衣物側面但proxy外；86、95、114有特徵散到投手輪廓外。
- 004後段有點散到草地、打者／捕手附近；76的骨架缺失不表示影像特徵本身正確。
- 005後段有點朝頭、手臂與打者腿部區域散開；沒有人工輪廓可量化整片前景準確率。

上述抽樣觀察不能冒充整片逐格foreground GT，也沒有改五片canonical紀錄。
綠線是四點凸包；藍點是每格最低FB分位群，粉色為其他點；seed無FB群。

## 驗證與保存

新增8項有意義測試：ties／missing rank、缺點不補三角proxy、已知signed distance與邊界、
pair兩端缺值、低FB且一致移動仍可在proxy外、AUC ties／缺值分母、
禁止覆寫，以及不讀human檔案／不改保存來源。
完整suite：**167 discovered，166 passed／0 failed／0 errors／1 skipped**。
Skip為要求明確提供真實MP4資料集的opt-in E2E；本次不重跑正式五片pose。
沿用先前已證實必要的沙盒外Windows執行環境，原validator沒有修改。

295個受保護檔案、前次42個比較來源與本輪44個來源hash皆不變。
固定計畫、參數及producer／evaluator hash相符。
獨立唯讀稽核逐片重算所有rank／ties／移動／分布、feature集合、proxy缺值、signed distance、
pair分類及條件AUC，皆一致；獨立邊段距離與OpenCV浮點距離差最多.0000153px，分類一致。

本次Git保存兩支獨立實驗腳本、8項測試、計畫、報告與狀態文件；
原片與大型量測仍依原規則留在本機。沒有Phase 3或Clipper整合。

## 接下來

影像證據有效性仍是尚未解決的問題。本輪結果不支持以低FB／存活率確認軀幹支援；
正式方法需要能獨立確認主體範圍、適當拒答，並評估正常快速動作與遮擋。
下一個候選方法應先固定有界實驗及獨立身體範圍參考需求，
與原raw／人工GT分開保存，再量化比較。尚未選threshold或核准production警示。

HSU不需重標已完成的003關節；peer005事件補充仍待回傳。
維持Phase 2穩定且以證據驗收後，才做Clipper少量single-pitch MP4＋metadata交接。
