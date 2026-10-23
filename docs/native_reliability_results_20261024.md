# 原生骨架 Phase 2 描述報告交付

更新：2026-10-24（台灣）。

本輪補齊已採用RTMPose17點流程的相鄰關節位移、左右影像順序、人物框及雙髖／軀幹連續性。
`report-native-reliability`直接讀取上一輪已接受的analysis bundle，五球已各由實際CLI產生報告。
新增的是定位可疑變化所需的量測資料；沒有新分類器、警示界線或改寫逐點可用狀態。

| 影片 | 影格 | 六重點關節缺座標 | 幾何break | 肘最大相鄰位移px（格） | 腕最大相鄰位移px（格） |
|---|---:|---:|---:|---:|---:|
| supplement_001 | 335 | 0 | 0 | 38.902（122） | 58.378（115） |
| supplement_002 | 321 | 0 | 0 | 49.486（140） | 123.072（140） |
| supplement_003 | 369 | 0 | 0 | 84.933（156） | 76.541（159） |
| supplement_004 | 338 | 0 | 0 | 35.795（132） | 71.166（131） |
| supplement_005 | 321 | 0 | 0 | 45.808（137） | 75.925（129） |

合計 **1684格／28628關節影格**，全部保留。五球17點模型座標均存在；
這是座標存在率，不是人體可見率、精確率或品質gate通過率。
逐格XY／coordinate_state／native_score／missing_reason與原資料差異 **0**。
新增人物偵測、pose推論、tracking replay、插值與人工標註皆 **0**。

格號為0起算；第i格位移比較i−1→i。首格沒有前格，未列入缺值配對；
五球各有334／320／368／337／320組相鄰配對，合計1679組。
時間使用分數FPS60000/1001。缺值不跨格計算；左右相等／缺值不推定反轉。
快速揮臂也會產生大位移，本表未把最大值當錯誤；候選框編號改變亦未當identity switch。
IoU直接取自既有追蹤紀錄，沒有重新做關聯。

## 可使用的輸出

根目錄：`analysis_results/phase2_native_reliability_20261024_01/`。
每支`supplement_001..005/`皆有：

- `report.md`：六重點關節、最大位移格號與中斷摘要。
- `pose_reliability.json`：17點覆蓋率／分數統計、缺值區段、相鄰位移與左右順序。
- `tracking_reliability.json`：既有連接／框、雙髖中心、框與軀幹尺度摘要。
- `frame_diagnostics.jsonl`：完整逐格原生座標／分數檢視副本及測量，原raw檔維持不變。

報告綁定上一輪bundle、影片、metadata、raw、track、overlay與人工接受證據SHA。
158份既有來源／人工紀錄／正式山本素材在生成報告及完整測試後SHA皆不變。
[操作與公式](native_reliability.md)、[版本化結果](dataset_selections/native_reliability_20261024.json)。

## 測試與本輪停止點

完整suite：**1163 passed／0 failed／0 errors／2 skipped**，
共1165項，104.141秒；新增10項必要測試。
兩項skip為Windows檔案symlink能力；其餘既有junction測試正常執行。
正式山本五球MediaPipe E2E有執行。新native報告與測試均無RTMPose／人物偵測模型呼叫。

影片人工接受仍 **5/5**；逐點可靠性與可見性仍 **unknown**、`usable_for_analysis=null`。
本輪 **原生連續性描述交付 = COMPLETE**。**Phase 2 自動可靠性仍 NOT PASSED**。
完整資料診斷不會校準原生模型分數；既有人工接受亦不會自動成為逐點GT。
本次資料入口與報告已備妥，後續自動品質判斷仍需另外決定範圍，不再自行追加小規則。

本輪完成後停止；未進Phase3、未替換正式素材或改動模型／核心／門檻／raw／人工GT。
