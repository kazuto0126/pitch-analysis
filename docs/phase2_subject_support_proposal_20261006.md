# Phase 2：獨立核對特徵歸屬與主體範圍的下一步

日期：2026-10-06。狀態：**接續人工答案8／8；候選mask實驗已嘗試，SDK讀取失敗，證據不足。**
Phase 2 = IN PROGRESS。

## 恢復 Phase 2 後的八題確認

使用者已要求繼續 Phase 2。原八題回答與對照保持原樣；其中五個位置的可見歸屬
值得再核對，不由 Codex 根據圖片自行改答案。新增三個固定影像位置，以補足參考。
產生問題時全部未覆核，沒有預填答案；現在已收到全部真人回答。

- 新資料：`analysis_results/phase2_membership_supplement_20261006_01/`。
- [固定題目與來源](evaluation_plans/phase2_membership_supplement_20261006.json)。
- 86格1–4保留原題位置；5、6為新增位置。95格新1號對應舊3號；2號為新增位置。
- 每題單獨放大，圈的中心保留原像素，上方全景原圖沒有畫記號。
- 本人重新確認已另存版本與來源；86／3由本人補充為P（投手腿部）。
- 原T／P／O／?含義沿用。頭頸、手臂與腿屬P；只有可見胸背腰的軀幹／衣物屬T。

這是已知診斷案例的定向核對，不是隨機／獨立測試集。新增位置不是關節，也不是
既有追蹤特徵；之後僅供evaluator抽取同位置mask值，不能成為模型／selector的提示。
本輪八題為3T、1P、4O；合併最新明確答案共11個不同位置（3T、2P、6O）。
原答案與初次轉錄保持原樣，確認版本見
[HSU紀錄](../review_tools/feature_membership/HSU_pitch003_membership_supplement_20261006_02.json)。
後續獨立mask實驗因SDK原生讀取錯誤無可用數值；完整紀錄見
[實驗報告](phase2_subject_mask_pilot_20261006.md)。沒有變更threshold、演算法或原人工GT。

## 原先八點試看與人工回覆（歷史紀錄）

已完成的003十二關節、五支定性GT及事件都沿用。
本次只新增「影像特徵的圓圈中心是否落在可見投手上」這個人工問題。
先用003第86、95兩格、各四個既有特徵，避免立即要求大量描輪廓。

試看資料：`analysis_results/phase2_feature_membership_pilot_20261006_02/`。
第一版`_01`因86格標號重疊，保留為未覆核草稿；`_02`新增四個獨立放大格。
選點、坐標、原始圖片與產生題目當時的八個unreviewed狀態相同。
兩版manifest與空白notes保持原樣；最新真人回答另存，不覆寫產生時的紀錄。

- `pitch_003_frame_0086_review.png`、`pitch_003_frame_0095_review.png`：原圖／圈號與放大格。
- `raw_frames/`：原始510×628 PNG，未畫標記、未縮放原圖。
- `query_manifest.json`：來源SHA、frame／timestamp、特徵ID、問題坐標及未覆核狀態。
- `REVIEW_NOTES.md`：產生當時的空白答案清單。
- [HSU人工回覆](../review_tools/feature_membership/HSU_pitch003_20261006_01.json)：原話、八個明確答案及來源SHA。
- `evaluation_01/human_membership_comparison.json`：收到真人答案後的離線對照。
- [操作說明](../review_tools/feature_membership/START_HERE.md)。

圈號1–4不是肩肘腕等解剖關節；不拖動、不重標位置，只判讀原圖中圈中心的可見歸屬：

| 代碼 | 人工判斷 |
|---|---|
| T | 可見投手軀幹／軀幹衣物，胸、背、腰等 |
| P | 可見投手其他部位或所戴物品，頭、手臂、腿、手套等 |
| O | 其他人或背景，可在notes補充打者／捕手／裁判／草地 |
| ? | 模糊、遮擋、跨邊界或無法分辨；保持不確定 |

查看放大格的圓圈**中心**，而不是圈線覆蓋的整個範圍。
若像素呈現旁人的可見表面，應依本格實際畫面判斷；不能推測背後隱藏的投手位置。
不把這個問題與「某個關節應該在這裡」或原有關節visible／not_observable混為一談。
T與P都屬可見投手，但只有T直接提供軀幹特徵的支援；手部動作可與軀幹不同。

## 試看題目的獨立性與保存

題目選點只讀原保存影像特徵與FB rank；每個非空rank群選一個排序中位代表。
沒有參考人工坐標、GT可靠性、人工答案或新segmentation結果。
86／95為已知診斷案例的固定試看格，不是警示觸發規則或獨立holdout。
圖中不顯示FB數值、人工proxy範圍、AI骨架或候選mask，減少先看模型判定的影響。

現有`ground-truth-v1`保存事件／可靠性區間；`manual-keypoints-v1`固定十二個解剖關節。
兩者沒有任意image-feature membership或polygon／mask欄位。
此階段`query_manifest`只是來源綁定的問題cache，沒有另建pose或事件GT schema，
也不將普通特徵偽裝成關節。人工回覆先另存為review notes，保留實際reviewer、
原話、時間來源與不確定性；收到回覆後再處理窄範圍的對照資料，原兩份GT保持不變。

產生題目時八個問題全部unreviewed；現在只依HSU明確回覆轉錄，沒有自動答案。
沿用本次人工覆核的HSU署名；未提供confidence、細分部位與新的完成時間，均保持null。
既有HSU代填授權只用於轉錄人實際提供的觀察，不能補猜其餘問題。
試看格式可用後，再決定是否擴至五片24格、每格至多四點、上限96個問題。
這是後續工作量的上限提案，本次未交出96題或要求重標整部影片。

## 第一個候選方向：現有MediaPipe的附加person mask

現行模型為`models/pose_landmarker_full.task`，不更換weights或backend。
本機MediaPipe1.0.1的options有`output_segmentation_masks`，result有`segmentation_masks`。
官方說明此選項預設false，能輸出所偵測pose的segmentation mask。
參考：[MediaPipe官方Python指南](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python#configuration_options)。

本機正式`MediaPipePoseEstimator`只回傳landmarks，保存的baseline沒有person mask。
歷史baseline沒有保存mask。本輪隔離推論已有mask物件，但無法可靠取出數值；
**目前仍沒有可直接比較的mask值**。
模型SHA：`5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1`。
先前方案只核對SDK欄位；這次隔離實驗執行同模型、原信心設定與selector，
讀取float32 mask的`numpy_view()`原生中止。安全報告將全部11點保留missing。

這是同一pose模型的附加輸出，錯誤可能相關；「person mask」也不能自行證明其屬於投手。
若之後進行實驗，使用獨立shadow runner與新目錄，不修改正式wrapper或原33-landmark contract。
先固定模式、既有confidence設定、candidate／mask對應及主體選取trace，
再保留每個mask在固定查詢點的連續數值與missing原因。
新run與原selection不同時不能直接沿用舊candidate index；對應不明保持證據不足。
人工答案只交給evaluator，不拿來選mask、建立ROI或移動預測。

目前尚未選mask cutoff、產生warning、決定保留哪些點、做模型benchmark或訓練。
沒有採用GrabCut、SAM2、RTMPose、ReID或新增投手。

## 需要驗證的問題與停止條件

1. 固定點是否在可見投手上？T／P與O分開，?按人工不確定保留。
2. 候選mask是否錯把打者、捕手等人的點也收進來？保留各種人工類別與每題數值。
3. 模型缺少pose／mask或candidate對應不清時，報missing／insufficient evidence；
   不移除原始八題及全部已完成人工判斷的分母。
4. 點仍在投手頭、手、腿上不等於支援軀幹中心；T與P另列。
5. person membership不衡量關節中心誤差，不能宣稱修好了被遮住的肘腕。
6. 兩格八點只驗證試看與局部點歸屬；不能算整張mask IoU、全片正確追蹤或Phase 2通過。

原八點與接續八點真人回覆均已收到；SDK讀取失敗使mask數值全部不可用。
若第一個候選在多人場景不能綁定投手，先記錄限制，再提出下一個有界方案；
不自行大規模替換模型或調正式gate。

## 原八點人工對照結果（保留當時回答，最新重核對見上方）

HSU原話：`86:1=o,2=o,3=o,4=p;95:1=o,2=o,3=o,4=p`。
只將代碼轉成大寫；不補猜O是打者、裁判或哪一塊背景，也不補猜P的細分部位。

| Frame／題 | 人工 | FB error（px） | 格內FB rank群 | 軀幹proxy |
|---|---|---:|---:|---|
| 86／1 | O | 0.00004316 | 0 | outside |
| 86／2 | O | 0.00009651 | 1 | outside |
| 86／3 | O | 0.00016434 | 2 | outside |
| 86／4 | P | 0.00030518 | 3 | outside |
| 95／1 | O | 0.00447819 | 0 | outside |
| 95／2 | O | 0.17807970 | 1 | outside |
| 95／3 | O | 0.46383844 | 2 | outside |
| 95／4 | P | 1.59733298 | 3 | outside |

合計：6個O、2個P、0個T、0個不確定。八點全數匹配來源frame／feature ID／坐標。
這8點的最低格內FB群代表都是O；小往返誤差不能保證特徵落在投手身上。
兩個P也在軀幹proxy外，進一步確認proxy外不能直接判成非投手。

每群只取一個代表，群0–3為格內相對rank，不是新的絕對threshold；
86格群3的FB仍只有0.00030518px。不選新cutoff或依這八題篩掉特徵。
6／8只描述這八個選定問題，不能當成全片錯誤率、骨架identity switch或mask準確率。
沒有T正例，不能衡量軀幹mask覆蓋；若擴充，需另外取得人工確認的T與其他場景參考。
兩個P正例同樣不足以建立完整身體mask的驗收結果。

## 原八點驗證紀錄（歷史）

八個query與原保存feature ID／坐標、FB分群選點一致；兩張原圖與MP4解碼pixel完全一致。
原圖及顯示圖hash、來源SHA與generator code hash保存於manifest。
實際檢視`_02`顯示圖：每題另有放大格，可分辨86格靠近的1／2／4號位置。
源資料、五份GT、人工十二關節參考、正式src與歷史結果不變。
完整suite仍為166 passed／0 failed／1 skipped；這次重跑紀錄存於試看輸出。
其中1 skipped為需指定`PITCH_ANALYSIS_REAL_BASELINE_DIR`的選用真影片交接測試。
人工對照後重新核對295份保護檔案、44份既有來源，皆未變；
紀錄在`evaluation_01/review_integrity_check.json`。

原定下一步已嘗試；新的3個軀幹正例已由真人確認，但mask讀取問題仍待解決。
下一步先提出不改正式環境的SDK相容性核對方案，不能以程序不再中止當作mask驗證通過。
peer005事件補充仍待回傳；Phase 2尚未通過。
Clipper少量single-pitch MP4＋metadata交接維持在Phase 2穩定且經證據驗收之後。
