# Phase 2 — pitch_003 錯位診斷

日期：2026-10-06（台灣）。**診斷完成；Phase 2 = IN PROGRESS。**

本次只讀取既有原片、HSU覆核的人工座標、raw／processed骨架、追蹤紀錄與overlay，沒有重新執行推論、修改演算法、調整門檻、改寫人工ground truth或開始Phase 3。

## 已確認的結果

1. **錯位已出現在模型輸出的raw座標。** 87–104格不是插值、平滑或overlay繪圖造成的偏移。
2. **現有tracking警示漏掉這段持續錯位。** 它檢查骨架自身的中心、尺度與相鄰影格變化，沒有獨立確認點是否仍對齊影像中的投手。
3. **observed只代表通過資料門檻。** 很高的visibility／presence仍可伴隨明顯位置錯誤。
4. **有整體位移，也有局部形狀錯誤。** 單純把全身平移回來，仍不能修正所有關節。
5. **打者影響尚未證明。** 圖中有骨架連向背景打者附近，但目前證據不能確認MediaPipe內部為何產生這些錯位，也不能據此宣稱整個主體identity switch。

## 來源與座標對齊

- 原片：`input/yoshinobu_yamamoto/phase1_final/pitch_003.mp4`，115格、30fps、510 × 628。
- MP4 SHA256：`5c08dba98504d998536dfd0f0fab598760400612c9049445a68120e68fdf024c`。
- 人工參考：`annotations/manual_keypoints/HSU_TSAI_RETURN_20261005_42/pitch_003/manual_keypoints.json`。
- 人工參考SHA256：`a970354b14f728d38af97336d6872900625c956e7a105f75ab9cdcff0aa77735`。
- Tsai放置原始X/Y，HSU逐點覆核；1,205可見點計算位置誤差，173不可觀測與2不確定點排除。沒有把遮擋推估當成精確位置真值。
- 模型來源：`analysis_results/phase2_yamamoto_20260925_01/predictions/yoshinobu_yamamoto/pitch_003/`。
- 可靠性來源：同一baseline的 `reliability/pitch_003/`。

全部115格原圖PNG雜湊與人工manifest一致；重新解碼原MP4逐格比對PNG像素完全相同。人工／模型frame index與timestamp一致。這排除了本次比較用了另一版影片、不同尺寸或錯誤影格對齊的問題。

## 錯位最早出現在哪裡

應用程式把**已整理的510 × 628整張影格**送進MediaPipe；這不是未剪輯的原始轉播畫面。
[pose_capture.py](../src/pitch_analysis/pose_capture.py)第49–54行與[pose_estimator.py](../src/pitch_analysis/pose_estimator.py)第68–73行沒有應用程式層的ROI裁切或座標位移。
[PitcherSelector](../src/pitch_analysis/subject.py)第42–60行的ROI是在推論後篩選骨架，不能阻止模型在影像中把局部關節放到其他人附近。

115格皆回傳一個pose，`candidate_count=1`、`selected_index=0`、`status=selected`。
candidate_count是模型回傳數，不是通過篩選的數目；index也不是持續的身分識別碼。
87–104的selector score平均1.110450、mean confidence平均0.900786。score是加總的幾何啟發式分數，不是機率；其mean confidence計算雙肩、雙髖、雙膝、雙踝，**不包含肘與腕**。

序列化檢查確認：

- `keypoints.json`與`pose_raw.csv`的全部3,795列raw X/Y/Z、visibility及presence一致。
- `processed_keypoints.jsonl`的X/Y與`pose_clean.csv`全部3,795列一致。
- 全部3,255個quality-valid列的clean X/Y與raw完全相同。
- saved clean設定為visibility ≥ 0.5、presence ≥ 0.5、最多補2格；設定未改。

### 87–104格的同點比較

| 比較範圍 | 可比較關節影格 | 平均2D誤差px |
|---|---:|---:|
| 全部人工可見點：raw | 190 | 76.90 |
| 其中processed為observed的點：raw | 178 | 74.76 |
| 相同usable點：raw | 189 | 76.53 |
| 相同usable點：clean | 189 | 76.89 |
| 相同usable點：visualization median | 189 | 76.32 |

同一usable集合的三個階段都保留大誤差；不把不同樣本數的平均值拿來宣稱改善。
190個可見點中，178 observed、11 interpolated、1 missing。
因此這段主要問題是**錯誤raw位置被保留為可用資料**，不是短gap插值產生全部錯位。
visualization median是三格中位數欄位，不是新的模型輸出，也不代表修復遮擋關節。

### overlay與processed必須區分

既有 `overlay.mp4` 畫raw座標，顯示條件是 `min(visibility, presence) >= 0.35`，見
[analysis/debug.py](../src/pitch_analysis/analysis/debug.py)第152–165行。
processed的observed／interpolated／missing來自另一組既有clean門檻；`x_smoothed/y_smoothed`沒有驅動目前這支overlay。
已直接解碼既有overlay第38、95、112格，確認畫出的錯位與raw位置相符；沒有重新產生或覆寫overlay。

診斷四欄圖另畫12個人工對應關節：原圖／可見人工點／raw AI／processed clean。
raw橘點達到overlay顯示條件，灰色空心點未達；processed綠點observed、紫點interpolated、missing不畫。
這些圖是診斷圖，不冒充既有33-landmark overlay或新增人工判定。

## 為何追蹤沒有警告

[tracking_reliability.py](../src/pitch_analysis/tracking_reliability.py)以raw雙髖中心與肩至踝的投影高度，檢查ROI、相鄰位移、尺度比與中心加速度。
在87–104，每項最大值仍低於既有警告界線：

| 量 | 區段最大值 | 發生格 | 既有警告條件 |
|---|---:|---:|---:|
| 中心相鄰位移／身體投影高度 | 0.207212 | 87 | > 0.45 |
| 相鄰尺度比 | 1.275982 | 89 | > 1.6 |
| 中心加速度／身體投影高度 | 0.214419 | 98 | > 0.45 |

中心仍在寬ROI內，selector沒有中斷。因此saved tracking結果仍是`reliable`、warning_events為空；HSU既有18格重大錯位全未被tracking警示涵蓋。
這裡報告原本規則與數值，**沒有降低或改動界線**。

現有六個重要關節的jump候選，在該段的current-frame聯集是：
`87, 88, 89, 91, 93, 95, 97, 99, 101, 104`，只包含10/18格。
候選記錄的是相鄰pair的後一格；本報告沒有擴展區間、把前一格也計入，或把它變成新偵測器。
既有pose報告雖因手腕長missing span等原因將整片標為`unreliable`，仍未提供87–104持續全身錯位的定位警示。

## 整體偏移與局部誤差

| 區段 | 可見關節影格 | raw平均px |
|---|---:|---:|
| 0–86 | 895 | 11.67 |
| 87–104 | 190 | 76.90 |
| 105–114 | 120 | 14.27 |

逐格取人工可見肩、髖的「raw減人工」X/Y中位數，用來描述軀幹位移。
87–104的區段中位數為X **−26.68px**、Y **−62.97px**，即偏左、偏上。
若僅在診斷計算中扣除每格的此位移，仍有平均 **50.95px** 殘餘誤差，支持局部骨架形狀亦不正確。
這是使用GT的事後分解，不能直接當成正式預測修正；原prediction完全未動。

| 格／關節 | raw誤差px | visibility | presence | processed |
|---|---:|---:|---:|---|
| 38 右肘 | 90.78 | 0.9823 | 0.9930 | observed |
| 38 右腕 | 108.07 | 0.9517 | 0.9672 | observed |
| 93 右肘 | 166.56 | 0.6764 | 0.9951 | observed |
| 95 右肩 | 147.37 | 0.9996 | 0.9986 | observed |
| 112 左腕 | 252.37 | 0.9927 | 0.9890 | observed |

第22格右肘人工不可觀測，AI仍有raw座標且processed為observed，不能用人工推估去量測其位置錯誤。
第26格右腕人工不可觀測，AI有raw座標但未通過clean與overlay gate；這也說明raw有點、overlay有畫、processed可用是三件不同的事。
105格後全身平均誤差下降，但112左腕仍明顯錯位，不能宣稱所有關節已恢復。

## 原因的確定程度

**已證實：** raw模型層已有錯位；應用程式沒有新增ROI座標轉換誤差；高分錯點會通過現有gate；tracking只看自身幾何連續性，漏掉持續影像對位錯誤。

**仍是假說：** 背景人物重疊、遮擋、MediaPipe內部tracking／檢測不穩定可能有關。
未保存模型內部detector rectangle、tracking state、segmentation或完整多pose輸出，沒有改變輸入的對照實驗，不能把某個假說寫成確定原因。
人工定性GT未確認整個主體identity switch；局部關節連到打者附近，也不等同於整條skeleton切換成打者。

## 後續建議：先設計警示與回歸檢查

建議下一個小範圍工作優先評估：

1. **持續全身錯位警示：** 既有中心／尺度連續性之外，需要獨立的投手影像對位證據；多格累積位移只能當候選線索，不能單獨證明抓錯人。
2. **局部手臂可靠性警示：** 結合關節跳動、肢段幾何與影像可見性；避免把正常投球伸展或自然遮擋一律判錯。
3. **先定回歸評估：** 保存87–104全身錯位、38／93右臂與112左腕作已知案例，同時用現有其餘4片的人工可靠區段檢查誤警。
   分別回報重大failure召回、額外警示、可見關節位置誤差與遮擋狀態，不建立任意加權總分。
4. 本片已被仔細檢查，是開發／診斷資料，不能冒充未看過的測試集。泛化仍需獨立素材或其他現有影片的獨立座標覆核。

這些是待評估方案，本次尚未實作新警示、修改PitcherSelector、換模型、訓練或加入Yamamoto專用規則。
目前HSU不需要重標這115格；`pitch_005`同學的獨立事件補充仍待回傳。
MLB Pitch Clipper正式輸入接入維持在Phase 2穩定且以證據驗收後，再做少量MP4＋metadata交接測試。

## 輸出、驗證與保存

新本機輸出：`analysis_results/phase2_pitch003_diagnostics_20261006_01/`。

- `diagnostic_summary.json`：階段／區段數值、既有設定及限制。
- `per_frame_diagnostics.json`：人工軀幹位移與既有selection、tracking量。
- `per_joint_diagnostics.json`／`.csv`：1,380筆可見性、raw／clean／median位置與誤差。
- `frames/`：13格四欄圖、38／95／112人工對raw圖、既有overlay的3格截圖。
- `error_timeline.png`：誤差、軀幹位移與可見關節誤差圖；陰影87–104來自原人工GT，不是新threshold。
- `index.html`：可離線開啟的圖集；沒有新增完整GUI。
- `build_diagnostics.py`：本機離線診斷產生器；只讀既有資料。
- `evidence_integrity_check.json`：316份受保護檔案雜湊、115格像素對齊、序列化與數值核對。

資料與計算檢查通過；原片、raw／processed prediction、overlay、人工JSON、canonical GT、歷史checkpoint及演算法來源未改。
輸出圖已目視檢查，圖中的原圖panel亦逐像素驗證未變。
本次只更新診斷文件，不重跑完整test suite；**147 passed／0 failed／1 skipped是之前的歷史結果**。
媒體與本機generated output維持ignored；診斷摘要與狀態文件納入Git，不發佈含私人帳號資料的XML。
