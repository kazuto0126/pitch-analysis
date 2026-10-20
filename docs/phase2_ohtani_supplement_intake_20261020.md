# 大谷補片：五球候選匯入完成

2026-10-20。使用者指定批次 `20261020T073530Z_6gyr6IC2e0Q`，只匯入該索引批次。
介面依共用交付根目錄 `CONTRACT.md` v2；未讀取供片端程式碼或內部 output。

## 實際匯入結果

- 成功 **5**、拒收 **0**、衝突 **0**；第一次退出碼 0。
- 重跑新增 **0**、跳過 **5**，拒收／衝突 0，退出碼 0。
- SQLite：匯入前 **2批／13球／57事件**；首次後 **3批／18球／63事件**；
  重跑後 **3批／18球／69事件**。增加的是匯入稽核事件，批次／球數沒有重複。
- 五個新 MP4 的 SHA 均與供片 JSON 相符，沒有與既有候選的 MP4 SHA 重複。

| 本次觀看別名 | 原 pitch_id 尾碼 | 完整解碼格數 | 最大逐格 PTS 偏差 | 匯入當時本地狀態 |
| --- | --- | ---: | ---: | --- |
| supplement_p01 | `_p01` | 335 | 0.000666667 ms | candidate／pending |
| supplement_p02 | `_p02` | 321 | 0.000666667 ms | candidate／pending |
| supplement_p03 | `_p03` | 369 | 0.000666667 ms | candidate／pending |
| supplement_p04 | `_p04` | 338 | 0.000666667 ms | candidate／pending |
| supplement_p05 | `_p05` | 321 | 0.000666667 ms | candidate／pending |

五球共 **1,684格**，均1280×720、H.264／yuv420p、CFR、分數FPS **60000/1001**。
實際解碼格數等於交付格數；每格以分數 FPS 比較 `(PTS - first PTS)`，均嚴格小於1ms。
第0格仍為0秒，不以container start偏移；motion-energy anchors沒有轉成生物力學事件。

## 候選與人工覆核

匯入時五球全部保持candidate，輸入人工覆核0/5、35項待確認。
後續HSU觀看本對話補片p01–p05原片與以下清單後，逐球回覆通過，
五球共35項已轉錄pass，目前**輸入人工覆核5/5完成，沒有待確認項目**：

1. pitcher_identity：畫面投手是大谷翔平。
2. pitch_delivery_visible：投手確實完成投球。
3. not_replay_or_slow_motion：正常速度，沒有重播／慢動作。
4. not_mirrored：未水平鏡像。
5. full_body_in_frame：全身與動作空間完整入鏡。
6. preparation_complete：準備與啟動完整。
7. follow_through_complete：完整收尾至恢復平衡。

p01的`review.json`已保存HSU、2026-10-20T08:12:17Z、pass及原回答轉錄備註，
相同schema快照在`annotations/input_reviews/shohei_ohtani/20261020T073530Z_6gyr6IC2e0Q/p01.json`。
p02另保存HSU、2026-10-20T08:14:57Z、七項pass及「正確」原回答備註，快照在同資料夾`p02.json`。
p03另保存HSU、2026-10-20T08:17:08Z、七項pass及「正確」原回答備註，快照在同資料夾`p03.json`。
p04另保存HSU、2026-10-20T08:19:47Z、七項pass及「正確」原回答備註，快照在同資料夾`p04.json`。
p05另保存HSU、2026-10-20T08:22:42Z、七項pass及「正確」原回答備註，快照在同資料夾`p05.json`。
每球均依該球的人工回答保存，沒有將已看影片的回答套用到其他影片。
這是影片輸入覆核，不是逐格關節GT；候選身分保留。

**分析執行0、正式提升0、舊素材替換0。** 沒有轉成正式`pitch-input-v1`、執行`analyze-pitch`、
pose、metrics或overlay。原大谷001／002、其他舊球與山本正式素材保留。

## 來源資訊與排除紀錄

- 新來源video ID `6gyr6IC2e0Q`，不同於舊批次的`RObvkuHpkSo`。
- JSON保留season=2026／high、RIGHT；team／opponent／game_id／pitch_type原unknown在本地為null。
- 「2026-04-08對藍鳥」另保存為使用者提供背景，不擅自補寫供片JSON未提供的日期／對手欄位。
- `excluded_by_operator`共9筆：**6顆完整但左打重疊較多**；其餘3筆分別缺收尾、缺準備、
  沒有實際投球。這9筆僅保存來源紀錄，沒有匯入額外影片或要求補交。
- warnings為空、quality_warning=false是供片資料，不能當成分析品質或人工輸入已通過。

## 保存、輸出與下一步

- 共用交付14個檔案的SHA／大小／mtime前後不變；交付區無寫入、改名或刪除。
- 13份既有候選review及20個舊正式／試用MP4與JSON，共33個保護檔案SHA不變。
- 本地候選：`data/intake/handoff/candidates/h_<原pitch_id SHA256>/`。
- 原ID→本地ID、來源與review完整路徑見
  [版本化匯入紀錄](dataset_selections/ohtani_supplement_20261020.json)。
- 本次輸出：`analysis_results/phase2_ohtani_supplement_intake_20261020_01/`。
  `review_all.html`提供五支本地原片及覆核清單，僅供觀看，不提交判定。
  `intake_summary.json`、`intake_receipt.json`、兩次CLI log、`metadata_audit.json`保留實際證據。

五球的輸入人工覆核已完成，維持候選。本文件記錄的匯入／覆核階段沒有執行分析；
其後HSU確認新來源操作框，已另完成一次五球分析，見[新補片分析結果](phase2_ohtani_supplement_results_20261020.md)。
Phase2自動可靠性狀態仍NOT PASSED，未進Phase3。

本輪未修改產品／測試程式，因此未重跑完整suite；實際完成的是SHA、全解碼、分數時間與去重的匯入檢查。
