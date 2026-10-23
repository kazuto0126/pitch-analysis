# 共用骨架標準：先確認投手，再追蹤人物框與估計骨架

2026-10-23。HSU完整觀看大谷`supplement_002`新overlay後，確認沒有追到其他人、
關節整體對位正確，並指示山本及後續投手都使用同一方法。
本流程因此採用為**新骨架輸出的共同入口**；原評估資料與人工GT保留。

HSU在山本新結果交付後再次確認：「我覺得這種模型是目前下來最成功的，
你可以繼續沿用之後的投手部分」。後續投手的新骨架沿用本流程，逐片確認初始投手；
方法沿用的授權另存`annotations/skeleton_reviews/HSU_20261023/future_pitcher_method_endorsement.json`。

2026-10-24保留方式確認：HSU再次要求保留大谷翔平與山本由伸目前的骨架模式。
後續沿用本文件的人工指定初始投手＋人物框連續追蹤＋RTMPose原生17點，
固定權重、預處理與關聯設定由`config/seeded_skeleton_runtime.json`綁SHA保存。
已接受的九片骨架透過既有原生資料入口直接使用；後續動作分析不需要更換骨架方法或重新推論。
新影片仍逐片確認初始投手；若未來要更換此共用方法，須先說明差異並取得使用者確認。
本次保留決定沒有授權開始Phase3，也沒有將整片接受轉為自動逐點可靠性通過。

後續HSU已另行回覆「可以繼續下步驟」，授權保留本骨架方法下的最小Phase3動作曲線。
`describe-native-motion`直接讀取已保存的原生資料入口；沒有更換權重或重跑骨架。
本次有限曲線交付的範圍見[Phase3第一步](phase3_ohtani_native_motion_20261024.md)。

## 固定流程

1. 接收已剪好的單球MP4與`pitch-input-v1` metadata，核對來源及分數FPS時間軸。
2. 同一YOLOX人物模型在首格產生編號候選，人工指定投手。新影片不可沿用別片框號或像素範圍。
3. 保存其餘各格所有候選；首格偵測直接重用，無須再跑一次。
4. 使用原固定「相鄰框彼此唯一最大正IoU」關聯。中斷後保留missing，不猜人或自動重抓。
5. 僅在成功連結的人物框內估計RTMPose原生17點，保存原圖座標、取樣幾何、來源與原生分數。
6. 輸出完整時間軸、人物框軌跡、骨架JSONL與overlay；逐事件另存不可變進度檔。

不因投手姓名調參，不拼接不同人的關節，不以插值製造被遮住部位的精確座標。
偵測score仍0.7、原NMS不變；關聯政策、RTMPose權重與預處理均沿用已確認方法。
山本來源已裁成窄畫面，使用各片完整來源作取樣canvas；不複製大谷的絕對crop／ROI。

## 正式使用入口

先準備首格候選，`--fps-fraction`使用交付／技術紀錄中的確切分數：

```powershell
pitch-analysis prepare-skeleton input/pitch.mp4 input/pitch.json --fps-fraction 60000/1001 --output analysis_results/new_source_prepared
```

檢視`seed_candidates.png`，把操作人指定的框號保存成來源綁定的`native-subject-seed-v1`。
該檔記錄reviewer、UTC時間、原回答、source/frame0 SHA、output_index及bbox；不是自動猜選。

```powershell
pitch-analysis extract-skeleton analysis_results/new_source_prepared/preparation.json seed.json --output analysis_results/new_skeleton
```

模型與隔離環境由`config/seeded_skeleton_runtime.json`綁SHA，不下載或安裝新模型。
每片偵測總額度N格（含已準備首格1次），pose最多N次；失敗不自動重試，完整保留claim與partial。
較長來源仍遵守既有detector每session上限321；拆成獨立證據段，總呼叫數不增加。

## 與既有分析的界線

新骨架使用原生COCO17；沒有提供的Z／visibility／presence保持null。
模型分數不冒充MediaPipe visibility，也不補造33點。
`analyze-pitch`／`extract-pose`仍保留原MediaPipe33特徵與gate相容流程，供歷史重現；
**新骨架處理走本文件的共同入口**，不把17點直接送入不相容的舊CSV／角度gate。
後續原生17點動作指標須依可用關節與資料語義接入，不能靠放寬舊門檻完成。

HSU對這支大谷的整體影像確認另存
`annotations/skeleton_reviews/HSU_20261023/ohtani_supplement_002.json`。
這是該結果的人工接受與方法採用，不是所有未來影片都已被人工逐點驗證。
Native分數仍未校準；原始GT、Phase1素材及Phase2歷史失效紀錄不覆寫。

## 山本遷移範圍

HSU已確認001首格2號，002／003／004／005首格1號，各片獨立保存操作設定。
本次五片各處理一次，共592格；001／002／004／005屬目前啟用素材。
003列歷史對照，保留原排除決策，不因重建骨架自動恢復為啟用素材。
只重建骨架並檢查輸出；不重標人工GT、不重新挑模型／調參或進Phase3。

## 大谷同批套用結果

001／003／004／005已使用HSU確認的首格框1／1／1／2各處理一次，共1363格；
002沿用原已接受結果，沒有重跑。新舊比較、完整五球overlay與保存紀錄見
[大谷五球交付](ohtani_shared_skeleton_rollout_20261023.md)。
HSU隨後確認「可以都正確」，加上002，五球overlay人工接受已完成。
方法採用與逐片人工接受分開保存；接受紀錄見
`annotations/skeleton_reviews/HSU_20261023/ohtani_shared_skeleton_acceptance.json`。

## 已保存骨架的後續資料入口

已取得人工overlay接受的來源，可用`prepare-analysis-input`建立資料輸入，
以`load_native_analysis_input`讀取原生影格、同源追蹤與人工接受證據。
大谷五球已實際完成1684格接入，原資料差異0、推論0。
詳見[使用方式](native_analysis_input.md)及[本輪結果／Phase2收尾判定](native_analysis_input_results_20261023.md)。

已建立的原生資料入口可再執行`report-native-reliability`，輸出逐關節缺值區段、
相鄰位移格號及人物框／雙髖／軀幹連續性描述。沒有新模型或品質門檻；
詳見[計算定義與使用方式](native_reliability.md)。

山本啟用001／002／004／005亦已獲HSU整片接受，原生入口／報告已完成。
四片接入設定為`config/analysis_inputs/yamamoto_active_seeded_20261024.json`；
003維持歷史對照。兩投手啟用九片的最新狀態見[本輪收尾](phase2_active_cohort_closeout_20261024.md)。
