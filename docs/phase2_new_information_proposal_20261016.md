# Phase 2：新增模型資訊的單次驗證提案

日期：2026-10-16。**PROPOSED — AWAITING_USER_CONFIRMATION**。

已完成現有資料的只讀核對；以下新模型試驗尚未下載、實作或執行。
依使用者先前「新模型 benchmark 先提出方案」的要求，核准本提案後才開始。
上一輪13特徵分類器維持拒絕與封存，不調整、不重新FIT。
Phase 2自動可靠性仍 **NOT PASSED**；本提案不是通過宣告。

## 一、本次已完成的檢查

核對來源：[本次只讀紀錄](evaluation_plans/phase2_new_information_preflight_20261016_01.json)。
重用上一輪已封存的逐格評估，不重新跑模型或製造人工判讀。

| 原gate通過但人工判為錯點 | 投球肘 | 投球腕 |
|---|---:|---:|
| pitch_001 | 11 | 9 |
| pitch_002 | 0 | 0 |
| pitch_003 | 29 | 12 |
| pitch_004 | 6 | 20 |
| pitch_005 | 26 | 8 |
| 合計 | **72** | **49** |

先前sample-maximum提示在這個集合抓回肘7／腕8，同時提示各1個gate通過的好點。
已拒絕分類器抓回13／16，但額外提示好點9／21；仍漏掉59／33個gate通過錯點。
這些是提示能力的試算，原資料和可用狀態完全沒有改寫。
這批錯點的`min(visibility, presence)`中位數仍達肘0.9002／腕0.9023；
這是描述性量測，不是新的confidence門檻，說明高模型分數仍不足以認證對位。

- 380份目前保護來源及62份上游SHA全部吻合，0變更。
- 本地匯入SQLite維持1 batch／8 pitches／45 events；8筆匯入狀態為`imported`。
  這是匯入紀錄，不能當成正式素材核准；原候選／人工覆核狀態檔的SHA也保持。
- 本機只有`models/pose_landmarker_full.task`，9,398,198 bytes；尚無Heavy。
- 既有`PoseEstimator`及MediaPipe adapter可指定模型路徑；這是介面可行性檢查，
  尚未證明新權重能載入或改善本資料。
- 新pose推論0、tracker推論0、classifier FIT 0、人工新增標註0。

## 二、建議只增加一個資訊來源

**MediaPipe Pose Landmarker Heavy，float16，version 1**，作獨立離線對照。
原Full維持正式後端。Heavy只提供另一組原生預測，評估它與原Full的分歧能否提示原錯點。

官方提供Full／Heavy同一套33點介面，landmarker輸入均為256×256；
Heavy不是更高解析度輸入，也不是透視恢復器。
參考：[官方模型與輸出說明](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)。
官方舊版單人Yoga／Dance／HIIT比較中Heavy優於Full；那不是後方投球／多人重疊的驗證。
參考：[官方評估範圍與數據](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md)。

選擇它的理由是沿用目前runtime與點位定義，減少新backend的轉換工作；
這是成本判斷，沒有保證它比其他模型更適合投球。同模型家族可能共同犯錯，須保留這個限制。
本輪不增加另一模型、分割器、手部模型、超解析度或新影片，不切換RTMPose。

核准後從官方version 1固定網址取得權重，先記錄下載來源與SHA、runtime、程式及全部輸入SHA，
再推論；不使用可變的latest路徑：

`https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task`

## 三、固定量測範圍

1. 原正式五球、全部592格，原尺寸、像素、時間軸，不裁切、放大、遮人或補格。
2. Heavy使用VIDEO模式、`num_poses=4`，detection／presence／tracking維持原0.5設定；
   每片新建既有PitcherSelector，實作與參數不變。只改離線呼叫所用的權重。
3. 保存每格全部原生33點候選、候選數、selector結果與理由，再保存選中結果。
   不用GT挑人、選slot或拼接跨人關節；Heavy選中也不證明身份正確。
4. 只量一次，每格呼叫與失敗留紀錄；不根據結果改模式、ROI或模型版本重試。
   未完整完成則回報未完成／失敗，不能用部分成功結果宣稱有效。
5. 原Full、原MoveNet、所有raw／clean／GT／人工XY與既有重大提示保持不變。
   新輸出放獨立`analysis_results/phase2_heavy_information_<timestamp>/`，不接正式分析。

## 四、只驗證一個新提示訊號

**訊號只有原Full與Heavy選中結果的同名肘／腕2D距離，除以原圖對角線。**
不加入已拒絕的時間特徵、MoveNet分歧或原分類器分數，不訓練新的多特徵分類器。
這是新增權重資訊的一次對照，沒有重新調整上一輪訊號組合。

- Full與Heavy同格同名點皆finite、Heavy由原selector選中才有距離；
  不以Heavy點自己的confidence預先刪除難格，分數只保存作診斷。
- Full缺值，或Heavy無候選、拒選、歧義、點非finite時，距離null、`insufficient_evidence`，沒有錯點提示。
  無新提示不等於可靠，不將Heavy缺值轉成「成功攔錯」，也不因此移除原資料。
- 以整片五折：四片校準、一片測試。各關節的界線固定為
  **四片canonical標為reliable且距離可量測之列的最大距離**；query距離嚴格大於界線才提示。
  不試分位數、margin、窗口或其他界線；訓練無可用可靠配對就明列該fold無法校準。
- 校準只讀四片training GT；query GT、003人工XY不能進producer或校準。
  先封存全部五片提示，才評估；不做五片共同校準或採用模型。
- 保留592格資料；沿用原非seed587格／關節主要分母。frame0保存但不進校準或成效。
  所有證據不足列仍留主要FN／TN分母並另列，禁止靠大量缺值提高表現。

## 五、人工標籤用途與必報數字

Canonical的可靠／不可靠判讀指向**原Full raw-overlay**，只評估新提示能否指出原錯點；
不能把它當成Heavy對錯的標籤。not_observable／uncertain各自保留，不併入二元類別。
003可見人工XY僅輔助比較兩模型的同格／同點誤差、各自coverage及缺值；
不把其他四片補成精確GT，不用XY選人或訂採用線。

各片與合計分開報告：

- TP／FN／FP／TN，以及原gate通過錯點中實際新增提示數、原gate通過好點中額外提示數。
  此處「新增」指相對原gate；另列與現有重大覆核提示的重疊及聯集增量，避免重複算成新抓回錯點。
- 原gate支持總數、無新提示的支持數、人工可靠保留數；遮擋／不確定／證據不足／raw缺值另列。
- 候選、selector歧義／拒選與可量測距離的分母，不以不同coverage的平均誤差冒稱進步。
- 003整片作測試的結果與104格原重大漏報保留；不延伸區間或回填known answer。
- 原score-only、sample-maximum與已拒絕分類器作歷史比較，原21格major hold不改。

## 六、執行前待確認的唯一決策

沿用上一輪兩個基準與主要數字，不降低採用界線。每關節獨立判定：

| 條件 | 肘 | 腕 |
|---|---:|---:|
| 全587格抓到的原錯點TP | ≥17 | ≥27 |
| 全587格誤提示好點FP | ≤1 | ≤1 |
| 排除003的TP | ≥10 | ≥23 |
| 原gate通過錯點被提示數須嚴格高於sample-maximum | >7 | >8 |

並且五fold均可校準、至少兩支非003各自TP高於原兩基準的較高值。
新增的`>7／>8`只確認提示確有改善「原本可用的錯點」，不是新增Phase2整體驗收門檻；
不得把只提示原gate已拒絕的點算成這個目的達成。

- 至少一關節符合：只提出該關節附加「需要覆核」提示的採用範圍，等使用者核准；
  不換正式模型、不改座標、不自動宣告Phase2 PASSED。
- 兩者都不符合：結束本輪，不追加模型、特徵或界線搜尋。
  保持evaluation COMPLETE WITH KNOWN LIMITATIONS、automatic reliability NOT PASSED，記錄資訊仍不足。

以上是單次新資訊試驗的採用提案，不代替原Phase2驗收要求；
未新增零漏報、新投手、重做GT或精確事件等收尾條件。

## 七、本輪核准與停止位置

這次已交付只讀核對與具體提案，停在**新模型試驗尚待確認**。
使用者只需確認是否採用以上「一個Heavy、一次五球、固定最大值提示、固定決策」範圍。
核准後先實作離線量測／校準／評估的必要程式與合成測試，凍結程式、計畫及來源SHA，再執行一次。
正式核心檔不需修改；完整suite與保護來源核對在執行後回報。
不分析交付八顆候選、不新增人工標註、不進Phase3。
