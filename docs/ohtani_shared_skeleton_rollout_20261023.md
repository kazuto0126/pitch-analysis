# 大谷五球共用骨架流程交付

2026-10-23（台灣）。[共用流程](standard_skeleton_workflow.md)、[版本化結果](dataset_selections/ohtani_shared_skeleton_rollout_20261023.json)。

## 交付後人工確認

HSU在觀看請求後回覆「可以都正確」，本輪001／003／004／005已記錄為整片目視接受。
加上先前已接受002，**五球overlay人工接受完成5/5，共1684格**。
獨立紀錄：`annotations/skeleton_reviews/HSU_20261023/ohtani_shared_skeleton_acceptance.json`，
包含原話、reviewer、紀錄時間及對應來源／overlay／原生manifest／座標SHA。
原執行JSON的pending狀態保留為當時快照，最新人工狀態以追加review為準。
這不是新的逐點XY、遮擋可見性標籤或量化100%正確率；不改寫raw及canonical GT。

HSU已接受第002球的人工初始化人物追蹤＋RTMPose結果，並要求後續投手沿用。
本輪處理同批001／003／004／005；四球首格候選已展示，HSU確認001＝1號、003＝1號、004＝1號、005＝2號。
原話「四球框號都正確，繼續」及來源SHA保存於`config/subject_seeds/ohtani_20261023/`。
005最高分框是捕手，本輪使用人工確認的2號投手框。

## 實際結果

| 影片 | 完整影格 | 本輪新pose | 整格missing | 幾何track break |
|---|---:|---:|---:|---|
| supplement_001 | 335 | 335 | 0 | 無 |
| supplement_002 | 321 | 0（沿用） | 0 | 沿用已接受結果 |
| supplement_003 | 369 | 369 | 0 | 無 |
| supplement_004 | 338 | 338 | 0 | 無 |
| supplement_005 | 321 | 321 | 0 | 無 |

四球共1363格，首格detector4次＋其餘1359次，新pose1363次。
全片框關聯皆連續，整格missing0。加上原已接受002，共1684格。
002引用已保存321格結果，本輪detector／pose皆0，來源及輸出SHA不變。
原推論在對話中斷期間已全部完成，本次恢復只補匯出與檢查，沒有重跑模型。

來源為`20261020T073530Z_6gyr6IC2e0Q`批次，FPS分數60000/1001、1280×720；
沿用已完成的人工輸入覆核，素材仍為候選。每片完整原圖作為detector canvas；
舊固定scene-crop輸出保留，沒有因本輪改寫舊設定。
既有模型、固定關聯、score0.7及原NMS保持，未調參、人工修座標或自動重試。

## 影像檢查

已實看12張比較圖，共35組原片／舊固定crop RTMPose／新seeded RTMPose。
005第128格舊骨架伸到打者的問題，在新取樣中回到投手；003第158格舊手臂伸向背景的問題亦有改善。
001取樣239／286格抬手處及004第144格手套側對位有可見差異；完整觀察與格數另列cohort summary。
四球取樣未見整個骨架追到其他人；這是代理抽樣，不能代替HSU全片人工接受。
第003球185為先前問題樣本，第005球128為舊混合骨架樣本，沒有當成出手等事件標註。

比較圖使用這批既有人工確認的觀看範圍裁切，保持比例；這只是觀看裁切，未改推論輸入。
新overlay皆實際完整解碼並核對來源像素／時間；五球可由`review_all.html`一起觀看。
原片另有逐byte相同的觀看副本，避免HTTP根目錄以外的原片連結失效。

## 保存、測試與限制

2052個保護來源SHA不變，2722份新worker binary輸出與journal核對。
原影片、舊prediction、人工GT、已接受002及山本新舊結果保留，沒有取代正式素材。
山本003仍僅歷史對照；四球後續人工接受已完成，見本文件上方追加紀錄。

本輪沒有修改產品碼或測試，故未重跑完整suite。
相同產品碼最新完整suite為**1139 passed／0 failed／0 errors／2 skipped**；兩項skip是Windows symlink權限。
該數字明確屬前輪結果；本輪完成資料完整性、全部影格解碼、時間／像素與影像抽樣檢查。

原生17點score未校準，無Z／visibility／presence則留null。
有座標、框連續不等於每個關節精確，遮擋關節也不因模型給點就成為可見真值。
沒有新人工GT、新模型、事件猜測或Phase3。
**共用骨架方法已採用；Phase2自動可靠性仍NOT PASSED。**

輸出：`analysis_results/phase2_ohtani_seeded_skeleton_20261023_01/`；先開`review_all.html`。
