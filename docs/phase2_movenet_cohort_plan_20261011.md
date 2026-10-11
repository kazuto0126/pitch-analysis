# Phase 2：五球全圖 MoveNet 比較計畫

2026-10-11（台灣）。使用者「繼續努力完成phase2」接續相容性結果，授權本輪有限比較。
本計畫在正式影片 MoveNet 推論前封存；MediaPipe 維持正式 baseline。

## 固定輸入與執行

- 沿用正式 `pitch_001` 至 `pitch_005`：87／175／115／114／101 格，共592格。
- 各片第0格仍量測、保留，排除成效分母；有效評估分母固定587。不得排除缺失或歧義。
- 原環境只解碼全部原圖、BGR→RGB，保存原圖尺寸、逐格像素SHA及原始PTS；不裁切或縮放。
  封存RGB bundle後，使用已驗證的獨立CPU環境，不為其安裝OpenCV或其他套件。
- Google MoveNet MultiPose Lightning TF2 v1，沿用相同模型與runtime hashes、
  全圖RGB resize_with_pad 256×256、bilinear、antialias=false、int32、batch1。
- 每格恰好一次推論、總上限592；不增加合成圖warmup、resize搜尋、padding調整或失敗重試。
  每次呼叫前先保存attempt記錄，逐格保存完整輸出；中斷／不符contract時保留partial並停止。
- 保存六槽17點、原生score、box、實際縮放／padding及未截斷的source XY。
  六槽不等於六個人，slot編號不當跨格身份，score不轉換成MediaPipe confidence或可見性。

## 產生端與評估端分離

輸入export計畫、量測execution、離線evaluation分別綁定來源與程式SHA。
產生端只讀影片／metadata／technical／已封存RGB bundle、模型和runtime，不讀GT或追蹤框。
離線評估才讀既有CSRT、原VIDEO／全圖IMAGE輸出與人工GT。
人工標註、raw prediction及舊結果皆不覆寫。

## 事前固定的保守幾何對應

對每一槽，雙肩／雙髖四點都必須有限且位於原圖半開範圍及封存CSRT半開矩形內；
native box還必須為正面積，與CSRT有正交集，才列為幾何候選。

- 0候選：`none`；1候選：`unique_geometric_candidate`；多候選：`ambiguous`。
- 只有唯一候選的座標可作描述性對照。全部槽、候選與不符合的理由均保留。
- box IoU／中心距離／hip midpoint僅作診斷，不以最高score、IoU、slot順序或GT誤差解歧義。
- 唯一幾何候選仍不是已確認投手，沒有新identity accuracy、observed或reliable標籤。
  CSRT起點由人工確認，結果只能描述該條件下的配對，不能稱全自動追蹤已通過。

## 評估與判讀

逐片、逐關節列出對應／歧義／未對應、原生分數分布、框外座標、相鄰跳動及與MediaPipe的座標差異。
MediaPipe既有gate可原樣描述；MoveNet沒有新gate、插值、可用性門檻或總分。
原major標籤只分組原MediaPipe失效區段，不轉成MoveNet的正誤標籤。

只有003的人工可見XY可計算誤差，所有不可觀測／不確定點排除座標誤差並另外列數量。
保留固定可見分母、未對應點及共同配對數，分開回報改善／惡化，不能只報已配對均值。
其餘四片精確XY與新模型解剖準確率保持null；兩模型一致也不能當真值。

每片事前固定工程檢查影格：0、四分之一、二分之一、四分之三、最後一格（整數floor），
另003固定已知問題區22、33、44、65、83、87、95、104、105格。
圖片作工程檢查，不冒稱新增人工GT。

## 驗收邊界與下一步

本輪建立模型差異與缺失證據，不直接替換production或宣稱修復原FN18。
Phase2仍須可由五球GT逐格評估的、產生端不讀GT的錯位警示／棄權規則；不能以程式成功或任意總分通過。
若新模型有幫助，後續先封存該規則及全分母TP／FN／FP／覆蓋評估，才談正式採用。
不改threshold、confidence gate、PitcherSelector、pose／tracking、平滑／插值；不增加投手或進Phase3。
交付八球保持candidate／pending，正式五球保持原樣。
