# 大谷新補片五球：一次分析結果

2026-10-20（台灣）。批次 `20261020T073530Z_6gyr6IC2e0Q`。
**5/5 完成分析、0 執行異常；5 degraded、0 通過既有 pose gate。Phase 2 自動可靠性仍 NOT PASSED。**

## 本輪實際完成

- HSU 已逐球確認七項輸入條件，共35項pass；本輪沒有重做人工關節標註。
- 準備獨立試用輸入 `input/shohei_ohtani/phase2_supplement_20261020_01/`，
  使用 `supplement_001`–`supplement_005`，原候選與舊正式素材不變。
- 五份 `pitch-input-v1` 驗證成功；MP4 複製前後 SHA 相同。season=2026，
  team／pitch_type／session_id=null；其他來源欄位留在原ID對照，不把batch當session或能量anchor當事件。
- 先檢視新來源90張原片取樣，再提出完整動作範圍。HSU於2026-10-20T08:33:11Z
  明確確認「五球範圍都可使用，繼續分析」。這是操作設定，不是逐格GT。
- 固定原圖軀幹ROI `(0.22,0.40,0.46,0.88)`；模型輸入crop `(0.15,0.30,0.60,1.0)`，
  對應 `[192,216,768,720)`、576×504未另行縮放切片。原MP4不裁剪；native與回到原圖的候選分開保存。
- 五球各分析一次，於08:33:57–08:36:03 UTC執行；MediaPipe Full權重、selector gate、
  品質門檻、插值與平滑保持。沒有搜尋crop尺寸、重跑失敗球或新模型試驗。

[固定設定與來源對照](../config/pilots/ohtani_supplement_regions_20261020.json)；
[版本化數字摘要](dataset_selections/ohtani_supplement_analysis_20261020.json)。

## 五球結果

以下球號只指新補片，不是原山本或舊大谷同號球。選中骨架不等於關節正確。

| 補片 | total／選中 | 選中比例 | rejected | 含插值影格 | mean visibility | 最長pose gap | 肘角raw coverage | 原pose gate失敗原因 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| p01 | 335／324 | 96.72% | 11 | 45 | 0.85635 | 9 | 59.10% | 連續缺失 >2格 |
| p02 | 321／275 | 85.67% | 46 | 91 | 0.82723 | 13 | 59.19% | pose <90%、連續缺失 >2格、前導膝角raw <80% |
| p03 | 369／362 | 98.10% | 7 | 61 | 0.85973 | 5 | 75.34% | 連續缺失 >2格、前導膝角raw <80% |
| p04 | 338／323 | 95.56% | 15 | 49 | 0.86038 | 12 | 57.40% | 連續缺失 >2格 |
| p05 | 321／315 | 98.13% | 6 | 67 | 0.86260 | 2 | 63.86% | 前導膝角raw <80% |

合計1,684格、選中1,599格（94.95%）、rejected85格、含既有插值313格；
raw visibility樣本加權平均0.85415。五球均`quality_gate_failed`／品質`degraded`，
自動input quality也均degraded，原因含原pose gate失敗；p02另有pose_invalid_span_requires_review，
p02／p03／p05另有preparation_phase_unverified，p05另有followthrough_unverified。
五球preflight均沒有偵測到切鏡；HSU先前輸入覆核與自動proxy分開保留，沒有互相覆寫。

### 重要關節raw coverage

| 補片 | 右肩 | 右肘 | 右腕 | 左髖 | 左膝 | 左踝 | 前導膝角 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| p01 | 96.72% | 73.13% | 59.70% | 96.72% | 94.33% | 96.12% | 94.33% |
| p02 | 85.67% | 71.96% | 60.12% | 85.67% | 58.57% | 81.62% | 58.26% |
| p03 | 98.10% | 78.05% | 79.95% | 98.10% | 67.48% | 98.10% | 67.48% |
| p04 | 95.56% | 70.41% | 58.28% | 95.56% | 84.02% | 92.31% | 83.73% |
| p05 | 98.13% | 82.24% | 66.36% | 98.13% | 71.34% | 98.13% | 71.34% |

單關節raw coverage是通過原confidence／presence gate的直接模型點比例。
**肘角raw coverage**另要求肩、肘、腕同格共同可用；本次五球都超過原50%條件，
仍不能由數量推論XY準確、人工可見或整片合格。前導膝角要求髖、膝、踝三點共同可用。
含插值影格可與選中影格重疊，不能把兩者相加當成總有效格數。

## Overlay實際檢查

已實查每球18張均勻overlay取樣，共90張；針對警示與可疑錯位另外檢查6組原片／overlay對照，
其中4格不在原90格內。這是agent影像檢查，沒有新增或修改HSU／Tsai人工GT。

- **p01**：選中抽樣主體在投手附近；138格無骨架，與134–142格的9格缺口一致。
- **p02**：收尾多處無骨架；159格上身向打者偏移，245格也有跨人／上身錯位。
  159格原scale警示保留，不能說成已穩定鎖定投手。
- **p03**：選中抽樣主體在投手附近；180–181、183–187格缺口與前導膝coverage不足保留。
- **p04**：159格無骨架；143–154格12格缺口保留，其他選中抽樣仍在投手附近。
- **p05**：245格手臂連線伸向捕手區；251格明顯混合捕手附近上身與投手附近下身，
  252格回到投手附近。251–252的原scale／center／motion警示保留。

五球tracking皆`partially_reliable`。p02、p05的`identity_switch_warning=true`；
其他三球false。五球`identity_switch_confirmed=null`保持，agent檢查不代填人工確認。
新來源的山本major覆核提示皆`not_evaluated`，沒有套用原五片的開發準確數字。
沒有警示不代表可靠，也沒有從抽樣宣告全片各關節正確。

## 保存與本輪檢查

- 五球candidate狀態與35項人工輸入紀錄保持；沒有提升／替換正式素材。
- 本輪305個保護檔案SHA不變，包含來源、模型、人工標註、原正式／舊試用輸入與固定設定。
- 逐格候選側檔1,684格、2,719副native候選；選中raw共52,767點（1,599×33）。
  時間索引、原圖transform與選中／raw點數一致；這是保存檢查，不是準確率量測。
- 五支原圖1280×720 overlay均產生；五份H264觀看副本全解碼1,684格、保留60000/1001 FPS。
- 本輪沒有產品或測試程式變更，**未重跑完整test suite**。同版產品最近完整紀錄仍為
  `e236878`：1018 run／1016 passed／0 failed／2 skipped，82.720秒，含山本正式五球E2E。
  兩項skip是Windows file-symlink建立限制；不把這個舊測試紀錄寫成本輪新跑結果。

## 輸出與下一步

`analysis_results/phase2_ohtani_supplement_20261020_01/`：

- `review_all.html`、`viewing/`：五球原片與可播放overlay。
- `predictions/shohei_ohtani/supplement_001..005/`：分析、raw／clean、所有native／mapped候選、metrics及原overlay。
- `reliability/`：逐關節pose reliability、tracking reliability與逐球summary。
- `evaluation_summary.json`：全批數字、ID對照、定義與限制。
- `visual_review/inspection.json`、contact sheets、`flag_context_1.jpg`／`flag_context_2.jpg`：實查紀錄與錯例。
- `run_receipt.json`、`preservation_check.json`、`export_manifest.json`：一次執行、來源保存及播放驗證。

**較少重疊的新補片仍沒有解除追蹤缺口與混合骨架問題。這批候選不提升正式素材，Phase 2仍NOT PASSED。**
本輪固定素材試用已完成，停止追加相同素材／裁切搜尋。下一步需處理混合骨架與可見關節漏偵測的模型／選取限制；
涉及正式核心或新模型採用時，仍依既有範圍先提出具體方案。沒有啟動新模型或Phase3。
