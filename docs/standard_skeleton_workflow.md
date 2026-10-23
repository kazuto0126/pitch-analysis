# 共用骨架標準：先確認投手，再追蹤人物框與估計骨架

2026-10-23。HSU完整觀看大谷`supplement_002`新overlay後，確認沒有追到其他人、
關節整體對位正確，並指示山本及後續投手都使用同一方法。
本流程因此採用為**新骨架輸出的共同入口**；原評估資料與人工GT保留。

HSU在山本新結果交付後再次確認：「我覺得這種模型是目前下來最成功的，
你可以繼續沿用之後的投手部分」。後續投手的新骨架沿用本流程，逐片確認初始投手；
方法沿用的授權另存`annotations/skeleton_reviews/HSU_20261023/future_pitcher_method_endorsement.json`。

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
