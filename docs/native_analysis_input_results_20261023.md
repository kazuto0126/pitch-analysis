# Phase2：原生骨架分析資料接入與本輪收尾

2026-10-23（台灣）。[操作方式](native_analysis_input.md)、[版本化結果](dataset_selections/native_analysis_input_20261023.json)。

**Native analysis input integration = PASSED。**
**本輪授權交付 = COMPLETE WITH KNOWN LIMITATIONS；Phase2 = NOT PASSED（自動關節可靠性尚未驗證通過）。**

## 完成的接點

新增`prepare-analysis-input`，讀取已保存RTMPose COCO17、同源metadata、人物追蹤及人工overlay接受紀錄。
`load_native_analysis_input`提供後續Python程式可直接使用的完整影格／追蹤／人工接受物件，
每格的`native`保留原座標與原生分數；`tracking`保留原框選擇；`joint_assessments`保留逐點未知。
輸出只新增`native_analysis_input.json`與`usage_summary.json`，原始keypoints仍以SHA引用，不複製或修正座標。
沒有經過舊MediaPipe33點CSV／visibility gate，也沒有補造33點或將原生score當visibility。

## 五球實際消費結果

五球都透過真正CLI建立新bundle，再由下游loader逐格讀取與原始輸出比對。
002讀取已保存的原追蹤和先前接受紀錄；其他四球讀取本次共用流程與後續HSU接受紀錄。

| 影片 | 下游讀取格數 | 原生關節影格 | 原影格／追蹤差異 | 人工reviewer |
|---|---:|---:|---:|---|
| supplement_001 | 335 | 5695 | 0／0 | HSU |
| supplement_002 | 321 | 5457 | 0／0 | HSU |
| supplement_003 | 369 | 6273 | 0／0 | HSU |
| supplement_004 | 338 | 5746 | 0／0 | HSU |
| supplement_005 | 321 | 5457 | 0／0 | HSU |

合計**1684格、28628個原生關節影格**，原始影格內容及人物追蹤差異皆0。
所有關節影格仍保留在分母中；28628個逐點可靠性與人工可見性狀態均為unknown，
`usable_for_analysis=null`，未把整片人工接受擴成逐點可靠或量化100%正確。
這批native沒有插值，若來源有missing或terminal track break，loader同樣保留，測試涵蓋該情況。

## 三項狀態分開

| 項目 | 本輪結論 |
|---|---|
| 影片層人工接受 | 大谷5/5，沿用HSU既有原話與SHA綁定紀錄 |
| 新骨架可由後續程式讀取 | PASSED；新CLI與loader已實際消費全部1684格 |
| 模型有座標／native score | 只表示保存的模型輸出，原值保留 |
| 逐點可見性／遮擋／對位可靠性 | 未由整片接受建立，維持unknown；不猜遮擋原因 |
| 原自動錯點警示／可用性驗收 | 既有未通過結果不改寫；本輪未訓練或採用新判斷器 |
| Phase2整體是否PASSED | NOT PASSED；不由資料接入或測試成功宣告通過 |

原canonical定性GT描述舊MediaPipe輸出，不移用為新RTMPose逐格正確率；
003既有可見XY比較的10.11px僅適用其人工參考，沒有套用到大谷。
沒有新增通過分數、零錯誤條件、新標註或後續小規則試驗。

## 測試與保存

完整suite **1155項：1153 passed／0 failed／0 errors／2 skipped**，
98.953秒。新增14項必要測試：12項來源／時間／追蹤／人工證據／missing／不可變資料語義，
以及2項CLI傳遞／拒收測試。兩項skip為Windows檔案symlink權限。
正式山本五球舊E2E有執行，major提示仍2／0／19／5／3。
初輪沙箱另有8項directory-junction測試跳過，紀錄保留；本報告採用一般Windows權限的verified_suite完整結果。

2068個保護來源SHA不變；原影片、native資料、已接受overlay、raw及人工GT保留。
既有產品檔案僅CLI新增命令，舊selector、pose／tracking／confidence gate／門檻／平滑與插值程式未修改。
本次資料接入的人物偵測／RTMPose推論／追蹤重播／新GT皆0；完整測試另執行既有MediaPipe測試。
無Phase3、角度計算、事件預測或跨投手比較。

本機輸出：`analysis_results/phase2_native_analysis_input_20261023_01/`；五份資料入口位於`bundles/supplement_001..005/`。
這一輪已到限定停止點。下游可讀新資料的接點與使用限制已交付，自動可靠性尚未通過的結論保留。
