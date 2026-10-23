# 原生骨架的逐關節與追蹤描述

`report-native-reliability` 讀取已接受的原生分析資料入口，補上 Phase 2 所需的
相鄰影格連續性與追蹤描述。它適用於目前共同採用的人工初始化人物框＋RTMPose17點流程。

```powershell
pitch-analysis report-native-reliability `
  analysis_results/phase2_native_analysis_input_20261023_01/bundles/supplement_001 `
  --output analysis_results/native_reliability_NEW/supplement_001
```

輸出必須是專案 `analysis_results/` 下的新目錄。來源及接受紀錄先由既有 loader 核對；
本功能不重新推論、重新追蹤、插值、清理座標、執行品質門檻或修改人工 GT。

## 輸出

| 檔案 | 內容 |
|---|---|
| `report.md` | 六個重點關節的中文摘要、最大位移格號與追蹤中斷 |
| `pose_reliability.json` | 17點既有覆蓋率／分數統計、缺值區段、相鄰位移、左右影像順序 |
| `tracking_reliability.json` | 原追蹤狀態／IoU、人物框與雙髖中心連續性、框及軀幹尺度 |
| `frame_diagnostics.jsonl` | 所有影格的測量值、原座標與分數的衍生檢視副本，可定位格號／時間 |

兩份報告均綁定分析入口、metadata、影片、骨架、追蹤、overlay與人工接受紀錄的 SHA。
檔名中的 reliability 表示可靠性評估所需資料；本報告的 `assessment=descriptive_only`，
不宣稱通過自動可靠性驗收。

## 計算定義

- **時間**：第0格為0秒，`timestamp_sec=i/fractional_fps`。速度使用分數FPS，
  不從毫秒四捨五入後的時間差推算。
- **相鄰位移**：第i格比較i−1→i，在原圖像素中計算XY歐式距離。
  速度＝位移×FPS；正規化位移＝位移／前格人物框對角線長。
  沒有跨缺值計算；首格沒有前格，不列入有效或缺值配對分母。
  相鄰統計 `total_count=N−1`，`count` 是可計算配對數，`missing_count` 是不能計算的配對數。
- **缺值區段**：起訖格均包含。`start_sec/end_sec` 為起訖格取樣時刻；
  `duration_sec=frame_count/fps`，代表區段涵蓋的影格期間，與兩端取樣時刻差不同。
- **左右影像順序**：解剖左側x減右側x的符號−1／0／+1。
  只在相鄰兩格都有非零符號時列出改變；相等／missing均保留，不跨越它們推定反轉。
- **人物框**：使用已保存的選中框，量測中心、寬高、面積、對角線及相鄰比例。
  `saved_match_iou`直接使用追蹤紀錄；不重算候選關聯。
- **身體中心／尺度**：雙髖原生座標的中點；軀幹尺度是左肩→右髖、右肩→左髖
  兩條對角線長的平均。所需點缺失就null；尺度分母為0亦為null。
  這些是2D影像投影，人物框尺度與骨架軀幹尺度分開記錄。
- **慣用手**：六個角色由metadata的LEFT／RIGHT對應投球肩／肘／腕，及對側前導髖／膝／踝。
  不根據球員姓名推定。

## 判讀限制

快速揮臂可能產生大位移，正常轉身可能改變左右影像順序；報告沒有將它們自動標為錯點。
多個候選人物及候選編號改變也不代表identity switch。幾何追蹤中斷沿用原紀錄，
自動身分正確性仍為unknown；整片人工接受另外呈現。

`model_observed`表示模型有座標，不表示關節在原片中可見或對位精確。
原生分數可以是任意有限值，保留負值與大於1的值，不當成visibility／正確率。
畫面外座標也不裁切或改成missing。逐點reliability／human_visibility保持unknown，
`usable_for_analysis=null`；沒有新增分類器、分數界線或通過標準。

因此，本功能補齊新後端的資料診斷能力，不會自行將 Phase 2 改為 PASSED。
