# 人工初始化追蹤：部分結果保存，執行中斷後停止

2026-10-21（台灣）。[已核准且執行前凍結的方案](phase2_seeded_native_track_plan_20261021.md)、
[版本化數字與SHA](dataset_selections/ohtani_seeded_track_results_20261021.json)。

**完整推論 = 未完成；本輪不正式採用；Phase 2 自動可靠性 = NOT PASSED。**

HSU核准並指定第0格1號框（saved output_index0）。新增獨立的初始化設定、
相鄰框關聯、嚴格cache重用及native producer／CLI，正式MediaPipe、PitcherSelector、
核心、gate、門檻、raw與人工GT均保持。原未選定seed的提案另留歷史紀錄。

## 單次執行的實際結果

僅處理大谷`supplement_002`：321格、1280×720、60000/1001FPS，第0格0秒。
沿用舊eligible人物框，政策固定為相鄰框彼此唯一最大正IoU，失敗即永久中斷；
沒有新detector、模型下載、套件安裝、調ROI／分數、fallback或重抓主體。

| 項目 | 實際結果 |
|---|---:|
| 保存框關聯replay | 1次 |
| Seeded／linked | 1／320格 |
| 幾何track break | 0格 |
| 新detector呼叫 | 0 |
| 新pose嘗試／完成 | 213／213（上限319） |
| 完整幾何相同而重用 | 193、194格，共2格 |
| 已保存骨架 | 215／321格（66.98%） |
| 因執行中斷未跑pose | 215–320格，共106格 |
| 重跑／重試／warmup | 0／0／0 |

新推論範圍是0–192及195–214格。193／194的來源、model、frame、時間、像素SHA、
原bbox與完整affine／SDK幾何全部吻合，landmarks及geometry原樣重用，沒有再推論。
全部321格的候選矩陣、所選框及來源時間線均已保存。

### 中斷原因與已保存的證據

第214格的prediction已寫入`native.partial.jsonl`後，Windows拒絕將
`run_receipt.json.tmp`替換為`run_receipt.json`（PermissionError／WinError5）。
錯誤處理再次要建立同名暫存檔，又因該檔仍存在而得到FileExistsError，程序停止。
可能涉及同時讀取的Windows檔案鎖；**根因未確認**，不能宣稱是模型或關聯失敗。

保留原`run_receipt.json`、`.tmp`、215格partial、213份binary和journal、
321格subject_track及once-only claim，沒有刪除claim或改輸出位置重跑。
原receipt仍是214格／212次新pose的過時running快照；以另存的
`interrupted_run_receipt.json`與實際journal／partial核對215格／213次。
沒有把原receipt改寫成成功，也沒有修改凍結程式。

只從保存資料匯出完整321格native JSONL／overlay；後106格為`not_run`、
`missing`、score=null、affine=null，原因`execution_interrupted_no_retry`。
保留人物框表示關聯已完成，並不表示那些格已執行pose。匯出新增推論／replay皆0。

依核准方案「失敗停止、不自動重試」，本次不補跑剩餘106格，也不繼續調整政策。

## 座標可用性比較

| 關節 | 舊固定crop RTMPose | 舊唯一框政策 | 本次部分結果 |
|---|---:|---:|---:|
| 投球肩 | 321 | 2 | 215 |
| 投球肘 | 321 | 2 | 215 |
| 投球腕 | 321 | 2 | 215 |
| 前導髖 | 321 | 2 | 215 |
| 前導膝 | 321 | 2 | 215 |
| 前導踝 | 321 | 2 | 215 |

數字是有模型座標的影格數，**不是正確率、人工可見性或既有gate的raw coverage**。
相較舊唯一框政策多213格座標；相較舊固定crop少106格，全因本次I/O中斷未執行。
最長missing106格，不能歸因追蹤丟失，也不能當成遮擋結論。

## 實際影像抽查

已看6張contact sheet，共22組原片／舊固定crop／本次結果：
固定20格加193／194格；本次無track break，不需要新增中斷附近抽樣。

- 0／19／38／56／75格，舊固定crop手臂線延伸到打者附近；新骨架回到投手與手套附近。
- 94／113／132／151／159／169／188／201／207格，抽樣所選框持續包圍投手。
  遮擋關節的位置與局部精度仍未量測，不能由線條齊全宣稱可靠。
- 193／194格呈現同一份已執行人物框pose，重用未改座標或幾何。
- 226／245／264／282／301／320格只有所選框、沒有骨架，符合未執行狀態。

抽樣未見整副骨架移到打者；這是代理檢查，沒有新增人工GT，不能延伸為全片身分真值。
`identity_switch_confirmed=null`、`accuracy=null`、`quality_status=not_calibrated`、
`usable_for_analysis=null`保持。

完整H264 overlay實際解碼321格，逐格來源像素SHA及時間皆核對；
最大時間差約9.095e-13ms。檔案後段缺骨架已有明確標示，沒有剪掉來縮小分母。

## 測試、保存與停止狀態

新增24項無模型測試，完整suite **1117 run／1115 passed／0 failed／0 errors／2 skipped**，
81.922秒。兩項skip為Windows檔案symlink權限，junction測試實際執行。
正式山本五球MediaPipe E2E啟用；major提示仍2／0／19／5／3。
測試沒有呼叫真實detector或RTMPose；實際執行的I/O錯誤另列為已知問題，沒有用測試全綠掩蓋。

615個保護檔案SHA全部不變；8個中斷原始artifact也保持。
213份新pose binary SHA及journal連號全部核對；來源逐格配對0錯誤，凍結設定／程式SHA不變。
未新增人工標註、素材提升、其他球推論、門檻修改或Phase3工作。

本機輸出：`analysis_results/phase2_seeded_track_native_20261021_01/`。
先開`review_all.html`；`START_HERE.md`說明中斷、逐格狀態與證據位置。
Git保存新增模組／CLI、設定、24項測試、精簡結果與文件；影片／權重／完整binary留本機。

**本輪已保存到可停下的狀態；尚未完成全片pose，不作正式採用或Phase2通過判定。**
