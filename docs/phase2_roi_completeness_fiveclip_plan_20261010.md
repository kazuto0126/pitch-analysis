# Phase 2 下一關：裁切完整性、缺失處理與五球驗證

2026-10-10（台灣）。**本輪完成已保存輸出的故障診斷與後續方案；尚未執行新的影片實驗。**
Phase 2 automatic reliability = **NOT PASSED**。不修改正式核心、selector、confidence gate、模型或 GT。

## 1. 已查清的六格缺失

以既有裁切輸出重播原 PitcherSelector 全 115 格，全部 selection receipt 精確相符。
沒有重跑模型或 tracker。六格都有有效 ROI，來源像素及裁切幾何已由前輪核對。

| 格數 | 已保存的候選 | 實際缺失類型 | 能確認的原因 |
|---|---:|---|---|
| 63 | 0 | 後端無候選 | 模型回傳空集合；不能據此推定遮擋或 tracker 失敗 |
| 65 | 1 | 原 selector 拒絕 | 8 個主要關節中只有 5 個信心 ≥0.35，原規則需要至少 6 個 |
| 68 | 0 | 後端無候選 | 模型回傳空集合，因果原因未知 |
| 79 | 0 | 後端無候選 | 模型回傳空集合，因果原因未知 |
| 80 | 1 | 原 selector 拒絕 | 全圖 normalized 身體高度 0.07945，低於原 0.16 下限 |
| 81 | 0 | 後端無候選 | 模型回傳空集合，因果原因未知 |

65 的主要關節平均信心為 0.64341，髖部連續距離 0.01091、身體高度 0.36309，
這幾項都不是本格拒絕原因；低信心主要包括左膝 0.11835、左踝 0.10342、右踝 0.25994。
80 的平均信心 0.64675、6 個主要關節達原 0.35 條件，髖部距離 0.10916 也未超過原 0.18 限制；
其候選的肩踝高度異常才是實際拒絕原因。不能因肩髖高信心就保留不合理的全身骨架。
上述數字是**既有規則的診斷**，沒有新增、降低或重新校準任何門檻。

另有 **44 個可見人工關節位於裁切外，分布於 26 格**：
左腕 21、右踝 11、左肘 5、右膝 4、左踝 2、右腕 1。
這和無候選／selector 拒絕是不同問題，不能都當作身體遮擋。
65／63／68 沒有可見人工參考出框；79／80／81 各有 4 個可見參考出框。
即使框內參考全在，也不代表模型一定能偵測；出框與失效同時發生也不能證明因果。

逐格原始數字、44 個出框點、原 selector 來源 SHA 保存在
`analysis_results/phase2_roi_completeness_audit_20261010_01/failure_audit.json`。
[版本化診斷摘要](evaluation_plans/phase2_roi_completeness_audit_20261010_01.json)。

## 2. 固定缺失與支持範圍的語意

下一個實驗必須分開保存以下事實，不能用「tracker 成功」替代全部狀態：

| 情況 | 必須保留的狀態與處理 |
|---|---|
| ROI 缺失、空交集、tracker terminal failure | 無可用裁切；不偷偷回退全圖、重 seed 或沿用前框 |
| ROI 存在且原生像素核對成功 | 只證明裁切可取得；`full_body_input_verified` 仍 unknown，除非另有證據 |
| 偵測器正常回傳空集合 | `backend_no_candidate`；不推定是遮擋、不補骨架 |
| selector rejected／ambiguous | 保存原 receipt 與缺值；不按人工誤差挑另一個候選 |
| 單關節低於原 visibility／presence gate | 保留 raw 數值，支持比較不可用；不改成可靠的 observed |
| 預測落在裁切之外 | 保留原外插座標，另標 input support 不足；不 clamp 或假稱直接觀測 |
| 人體完整性／歸屬無法確認 | unknown／unverified；不由框包含、高信心或連續性自動填 true |
| 人工 visible／not_observable／uncertain | 沿用現有 GT，與上述模型狀態分開；hidden XY 不當精確真值 |

人工參考是否在裁切內只可供**離線 evaluator**計算，不能成為 producer 的裁切、選人、
缺失或 warning 決策。也不使用這 44 個人工座標反推 padding，避免把測試答案拿來調輸入。
本輪沒有實作新的完整人體偵測器、warning 或可靠性分類規則。

## 3. 下一次五球實驗前必備的資料

只用既有正式五球，不用八顆交付候選。全部 592 格保存；如仍採每片第 0 格人工起點，
成效分母為 587 格，另外清楚報出被排除的 5 格。003 必須列為已知開發資料。

| 影片 | 原格數 | 已保存、人工確認的起點 ROI | 可見人工 XY 參考 |
|---|---:|---|---|
| pitch_001 | 87 | 尚無 | 無逐關節精確 XY；有完整定性 review |
| pitch_002 | 175 | 尚無 | 無逐關節精確 XY；有完整定性 review |
| pitch_003 | 115 | 有，第 0 格 Q1 | 有 12 關節人工座標與可見性 |
| pitch_004 | 114 | 尚無 | 無逐關節精確 XY；有完整定性 review |
| pitch_005 | 101 | 尚無 | 無逐關節精確 XY；有完整定性 review |

本輪核對 `review_tools/subject_initialization/`，只有003的既有 seed。
因此不能直接把 003 runner 換檔名擴跑四片，也不把舊 GT「投手正確」當成已批准新的初始化框。
本輪已準備另外四片的第0格及待覆核黃框，讓 HSU 只確認新的投手框；
保存 rectangle、原像素 SHA、實際回答、判讀者與來源，未提供的 confidence／完成時間仍 null。
不要求重新標五片骨架或重做 5/5 canonical GT。

四份草案位於 `review_tools/subject_initialization/`：

- `proposed_HSU_pitch_001_visual_20261010_01.json`
- `proposed_HSU_pitch_002_visual_20261010_01.json`
- `proposed_HSU_pitch_004_visual_20261010_01.json`
- `proposed_HSU_pitch_005_visual_20261010_01.json`

框是 assistant 看原第0格提出的可見範圍草案，
不是新 detector 的輸出，也沒有自動寫成人工答案；四份 `human_conclusion`／extent／reviewer／時間皆 null。
原圖解碼像素與既有全圖 IMAGE 第0格 SHA 相符，顯示圖加黃框與英文識別，不更動原PNG。
兩張雙圖總覽及空白 questions 保存於
`analysis_results/phase2_roi_completeness_audit_20261010_01/seed_review/`，本對話已提出獨立確認問題。
回覆前禁止拿草案啟動追蹤或分析；回覆到來另存來源與 confirmed seed，不覆寫這批未確認快照。
背景可能仍有其他人的像素，人工問題只確認主要投手與目前可見肢體範圍，不宣稱裁切可隔離所有他人。
003來自HOG提案／其他四片是視覺草案的起點來源差異也須報告，不能稱公平的全自動方法比較。

這只能驗證**人工初始化後**的追蹤／裁切；自動初始化與全自動可靠性仍是分開的未解決項目。
若改為自動產生並直接採用 seed，須另定主體指定／歧義政策與獨立驗證，不能省略這個條件。

## 4. 五球比較的執行界線

1. 起點資料就緒後，先固定每片 ROI 來源、追蹤預設、裁切設定、同一 full 模型與 IMAGE options、
   原 selector／gate、軟體／native／來源 SHA，以及 terminal 缺失處理，再執行；不得一片一套設定。
2. 本輪沒有選定新的 padding、改追蹤框或加全圖 fallback。若要試新的輸入範圍，先另列一個有界設定，
   明示與前輪不同且不以 manual XY 調參；不能沿用前輪 execution manifest 冒稱相同實驗。
3. 原五片全圖 IMAGE／VIDEO 都已保存，優先重用已封存控制組。003既有裁切也不重跑充當新證據；
   相同設定可重用；新設定則需另存新 arm，不能覆寫舊輸出。
4. 每片及全體列出完整來源格數、ROI 可用／缺失、候選數、selected／rejected／ambiguous、
   每關節 raw gate、輸入支持、外插、缺失長度與既有 observed／interpolated／missing 的原語意。
   新 arm 不插值或平滑救回；保留壞結果及固定分母。
5. 精確 XY 誤差只可在有 visible 人工座標的003報告，仍用相同點集合配對。
   其餘四片的像素誤差保持 null，不套用003均誤差，也不把新舊骨架一致當準確。
6. 舊 major labels 描述舊 prediction，只作案例分組。新輸出重大錯位／identity switch 需要另外、
   明確且有限範圍的人工覆核；不得直接搬用舊標籤計算新 warning TP／FN／FP。
7. 原漏報18格、004的75–76、005的54、各片出手與遮擋附近列為固定檢查範圍；
   也報其他全部影格的可用性，避免只看已知錯誤片段。代表圖不能取代全片身份驗證。
8. 結果先停在候選改善證據。正式接入需另列必要改動，保持原五球／raw／GT 不變，
   跑完整 suite 與來源核對，再按既有 Phase2目標評估；不發明數字通過線或自動標 PASSED。

## 5. 目前可停止的狀態

- 六格缺失已精確分類；115 個原 selector receipt 相符，374 個受保護來源 hash 未變。
- 本輪新模型推論 0、tracker update 0、人工 GT 修改 0、正式程式變更 0；四份新框草案均待人工確認。
- 僅新增診斷／方案文件，未重跑完整 suite；最近完整結果仍為 **409 passed／0 failed／2 skipped**，
  411項，包含正式五球 E2E。不能把沿用的測試紀錄說成本輪新跑。
- 新五球實驗尚未開始：四個起點框確認待回覆，輸入策略待固定，之後才一次執行已封存設定。
- 八顆交付影片仍候選／pending，沒有新的交付匯入、分析或正式替換；不開始 Phase3。
