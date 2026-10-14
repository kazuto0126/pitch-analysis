# Phase 2：ROI整合決策與下一次有限實驗提案

2026-10-15。**現有固定窄ROI：不接入正式流程。Phase2自動可靠性：NOT PASSED。**
五球GT覆核與baseline評估已完成，不將unknown事件、其餘四片缺精確XY或新零FN／零FP要求
另設為通過門檻。現有raw與人工使用限制持續有效。

## 1. 現有設定的決定

| 證據 | 實際限制 |
|---|---|
| 五球587非seed格，crop selected552／IMAGE555／VIDEO584 | 新四片相對IMAGE少22格；003多19格不能抵銷其他片損失 |
| 003肘41同格MAE23.8410°→11.2361° | 18格變差；有參考且有值41/51，少於VIDEO raw49/51 |
| 003膝95同格MAE7.2015°→4.6703° | 40格變差；有參考且有值98/113，少於VIDEO raw103/113 |
| 膝原major18格MAE24.2432°→10.6508° | 其餘77共同格3.2177°→3.2723°，增益集中在已知重大錯位段 |
| ROI由人工seed初始化 | seed正確與tracker API成功不證明全片身份或關節正確 |
| 精確人工XY僅003 | 不外推另外四片或新投手，不拿原prediction的GT認證新ROI |

保留既有實驗工具與封存資料，不重跑同一窄框設定，不自動fallback、不解除major限制。
昨日的單片均值改善是發現修復方向的證據，不是正式ROI整合授權或Phase2通過。

## 2. 下一個單一假說：擴大輸入範圍的代價

**提案，尚未執行。** 同一MediaPipe baseline、同一IMAGE模式，僅把已封存的CSRT浮點
`usable_rectangle_xywh=(x,y,w,h)`以原中心將width／height各擴成2倍：
邊界為`(x-w/2,y-h/2,x+3w/2,y+3h/2)`，左上floor、右下ceil後與原圖取交集。
不從已整數化窄crop bounds擴張。無效／缺失矩形保持無可用輸入，不沿用前框。
沒有外部resize、padding、mirror。
此設定是固定一次的輸入範圍假說，不以人工XY反推大小、不作多倍率搜尋，已看過的五球明列為開發資料。

待回答：比窄框保留更多來源影像，能否減少可用性損失，同時保留003已有座標／角度增益？
擴大也可能重新帶入打者／捕手背景、造成新錯位；沒有預設一定改善。
2倍範圍也不保證完整人體，邊界clipping與未知可見性照報，不能標full_body_verified=true。

### 固定輸入／預算／輸出

- 只用原正式五球，592格全部保存、587非seed評估；八交付候選不分析。
- 使用已有逐格CSRT rectangle及人工seed provenance，不重跑tracker、不重seed。
- 同一原MediaPipe模型／runtime／num_poses／confidence，fresh原PitcherSelector每片一次；
  不修改正式VIDEO baseline或既有core。控制組為已有full-frame IMAGE與窄ROI IMAGE；VIDEO只作次要比較。
- 最多592次新pose呼叫、0次tracker呼叫；無自動重試。推論前固定來源／程式／模型SHA與契約。
  每次attempt與結果逐格保存；中斷時先檢查journal，不覆寫或重算已完成影格。
- 新raw座標、selection receipts、source/crop pixel SHA、actual crop bounds與映射、
  below-gate／crop外／missing狀態獨立保存；不假裝新點是可靠observed，不補被遮擋的真值。
- producer不讀人工XY或review labels；量測seal後才由獨立evaluator讀GT。

### 固定比較與停止條件

五片逐一報selected/rejected/ambiguous、六重要關節raw/gate/input-support、完整流失／恢復清單。
003另報全部可見XY與既有肘／膝的strict same-frame誤差、reference/prediction缺值；
人工在crop外只作分層，不篩掉primary困難格。其他四片精確誤差保持null。
原major／局部labels只作原prediction的背景分組，不自動成為新ROI accuracy GT。

只完成這一次固定arm、來源稽核、完整分母／同格比較與採用／拒絕決策就停止。
結果不好不連續換倍率、換模型、調gate或按GT挑fallback；結果好也不自動替換production。
沒有任意總分、排名、角度通過線、零FN／零FP或額外holdout強制門檻。
如需對新骨架作人工正確性確認，另保存具體新review紀錄；不重做原五份GT。

## 3. 真正需要變更的檔案範圍

若此後核准該實驗，擬新增：

| 檔案 | 唯一責任 |
|---|---|
| `scripts/measure_expanded_roi_pose.py` | 只讀source／saved ROI，固定2×輸入、原模型／selector、逐次attempt與raw seal；不讀GT |
| `scripts/evaluate_expanded_roi_pose.py` | 量測seal後核對像素／mapping／來源，五片可用性與003可見XY／角度同格比較 |
| `tests/test_expanded_roi_pose.py` | 浮點矩形擴張／clipping／來源拒收／預算與journal，不呼叫真影片模型 |
| `tests/test_expanded_roi_pose_evaluation.py` | 缺值／GT隔離／crop外參考／同格分母與未核准採用狀態 |
| 新proposal／execution／result manifest與結果文件 | 綁來源、code、模型／runtime、592呼叫上限與一次性決策 |

重用現有PoseEstimator介面、crop mapping及原selector；不重寫模型或tracker，不改舊實驗producer。
`analysis/pitch.py`、`workflow.py`、`pose_capture.py`、`subject.py`、原gate／平滑／插值不需修改。
原raw、GT、正式五球與交付讀取器不需修改；不接正式workflow、不新增外部下載依賴。

新的execution plan需固定這些檔案SHA與輸出contract，不能用這份提案自稱已執行或已整合。
本輪只交付來源診斷／整合決策／這份可review範圍，沒有開始新推論或Phase3。

參考：[五球ROI結果](phase2_assisted_roi_cohort_results_20261010.md)、
[五球loss診斷](phase2_roi_loss_diagnosis_20261010.md)、
[同格角度比較](phase2_saved_roi_angles_results_20261014.md)。
