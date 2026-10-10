# Phase 2：固定追蹤框裁切 pose 對照結果

2026-10-10（台灣）。**Phase 2 evaluation = COMPLETE；automatic reliability = NOT PASSED。**
本次是已知 `pitch_003`、人工初始化追蹤框條件下的改善證據，尚未接入正式流程。
原五球、GT、raw、confidence gate、PitcherSelector、pose／tracking／smoothing／interpolation 核心保持不變。

## 完成的工作

- 新增隔離裁切量測與離線逐點比較工具，以及 28 項回歸測試。
- [事前方案](phase2_tracked_roi_pose_plan_20261010.md)與
  [固定設定](evaluation_plans/phase2_tracked_roi_pose_execution_20261010_01.json)先封存，再跑一次。
- 同一個既有 MediaPipe full 模型，以 IMAGE 模式處理原 115 格；115 次推論，沒有重跑 CSRT。
  不 resize、padding、mirror、修點或插值。所有候選先還原全圖座標，再交原 selector。
- 115 格原像素／PTS、實際裁切 BGR／RGB 像素、座標還原及 selector 均獨立核對。
  主要對照是既有全圖 IMAGE；正式 VIDEO 作次要對照，沒有重跑兩組舊輸出。
- 第 0 格保留但排除成效：114 格、1368 個人工關節紀錄，1195 visible、171 not_observable、2 uncertain。
  非可見座標沒有當作精確真值，也沒有補填新人工答案。

## 相同可見點的誤差比較

只有人工參考在裁切內、新預測也在輸入範圍內，且兩組皆通過既有 visibility／presence 0.5 gate，
才進入配對。下表每列兩組使用完全相同的點；不同列分母不同，不可混作同一集合。
單位為原圖像素，沒有新 PCK cutoff、總分或通過門檻。

| 與全圖 IMAGE 配對的區段 | 共同點數 | 全圖均誤差 | 裁切均誤差 | 改善／惡化／相同 |
|---|---:|---:|---:|---:|
| 全部 114 格 | 847 | 19.1565 | 9.0031 | 478／369／0 |
| 原重大錯位 18 格 | 113 | 80.4089 | 10.8965 | 110／3／0 |
| 其餘 96 格 | 734 | 9.7266 | 8.7116 | 368／366／0 |
| 原錯誤軀幹仍在框內的 10 格 | 49 | 45.5494 | 8.9299 | 46／3／0 |

全體配對 median：8.4121 → 7.5479；p90：63.7613 → 16.9849。
與正式 VIDEO 的次要共同集合為 1002 點，均誤差 20.7130 → 9.6994，578 改善／424 惡化。
原重大錯位 18 格均有新骨架選取，但其 GT 是對**舊 prediction**的標記；不能直接稱新重大錯位已全部修復。
改善主要集中於原嚴重偏移區段，其餘區段改善／惡化數接近，不能說每點皆變好。

### 各關節（主要 IMAGE 配對）

| 關節 | 人工可見數 | 裁切 raw gate 數 | 共同支持點 | 全圖均誤差 | 裁切均誤差 | 改善／惡化 |
|---|---:|---:|---:|---:|---:|---:|
| 左肩 | 114 | 108 | 89 | 23.0545 | 11.2923 | 51／38 |
| 右肩（throwing） | 105 | 99 | 89 | 19.9400 | 7.7627 | 48／41 |
| 左肘 | 82 | 70 | 48 | 28.3854 | 8.1440 | 39／9 |
| 右肘（throwing） | 92 | 73 | 67 | 16.1017 | 10.0519 | 44／23 |
| 左腕 | 61 | 31 | 11 | 39.8289 | 12.5077 | 8／3 |
| 右腕（throwing） | 58 | 43 | 40 | 19.5852 | 10.5340 | 26／14 |
| 左髖（lead） | 114 | 108 | 89 | 21.0650 | 11.0179 | 43／46 |
| 右髖 | 114 | 108 | 89 | 19.4134 | 8.5730 | 46／43 |
| 左膝（lead） | 114 | 99 | 80 | 17.0833 | 7.8585 | 36／44 |
| 右膝 | 114 | 95 | 80 | 10.7272 | 6.7661 | 43／37 |
| 左踝（lead） | 113 | 106 | 85 | 19.7910 | 8.8207 | 44／41 |
| 右踝 | 114 | 96 | 80 | 15.3315 | 8.0386 | 50／30 |

raw gate 數只表示可見人工點上有通過既有 gate 的預測，不是全影片 coverage、正確率或 observed 宣告。
所有關節的完整 median／p90／差值及缺值均在 JSON；沒有只挑投球肘或有利結果。

## 缺失與退步仍完整保留

- 114 格的選取：裁切 108 selected／6 rejected；全圖 IMAGE 89 selected／20 rejected／5 ambiguous；正式 VIDEO 114 selected。
- 裁切 rejected：63、65、68、79、80、81。63／68／79／81 後端沒有候選；65／80 有一候選但原 selector 拒絕。
  不回退全圖、不補前格或改 selector 救回。
- 1195 可見點中，裁切 1131 有 selected raw、1036 通過 gate，64 無點、95 低於 gate。
  全圖 IMAGE 是 937 有點／908 gate；VIDEO 是 1195 有點／1140 gate。
  三組條件均值使用不同集合，只分開保存，不能直接相減宣稱改善。
- 1151 可見人工點在裁切內、44 在外（原 major 189／1，其他 962／43）。框外點仍留在分母。
  1036 個 gate 點中有 20 個參考在裁切外；另有 14 個新預測在裁切外，兩者有重疊。
  共同輸入支持且 gate 的點只有 1016，不把外插當成直接觀測。
- 原 major 的可見右肘 87–96 雖有預測，皆未通過原 gate；本次不降低門檻，不能把較接近座標當可靠輸出。
- 左腕配對只有 11 點，裁切使可見的左腕／伸出框外的肢體失去輸入支持；仍是明確限制。

## 九張固定圖的檢查

實際查看 38、70、78、87、92、95、101、104、112 的 source／全圖 IMAGE／裁切 IMAGE 三欄圖。
綠圈只畫已存在的 visible 人工參考，紫色為 selected raw，黃框為既有 ROI。
圖會顯示低 confidence raw 線，**不代表每條紫線皆通過 gate 或已由人確認**；缺選取維持空白。

- 38：原手部延伸到打者附近的線明顯改善，但關節仍不是零誤差。
- 70／78：舊 IMAGE 沒選取，新輸出有軀幹；78 的伸出腿仍有裁切邊界限制。
- 87／92／95：舊軀幹偏上，新肩髖接近既有可見人工點，與逐點誤差改善一致。
- 101／104／112：舊 IMAGE 未選取，新輸出有骨架；局部肩髖及手部仍可偏移，並非全點正確。

這是工程視覺核對，不是 HSU 新 ground truth。沒有自動修改人類答案、occlusion 或原重大失效標籤。
完整圖片和逐點表位於 `analysis_results/phase2_tracked_roi_pose_20261010_01/evaluation/`。

## 結論與下一個關卡

本設定保留為候選方向：**同模型在正確主體範圍輸入下可減少已知嚴重錯位**。
裁切同時改變上下文、尺度及邊界，不能單獨證明原因就是打者，也不是公平的無人工初始化 benchmark。
仍只有已看過的 003，還有框外肢體、6 格拒絕及投球肘低 confidence，沒有五球 warning 回歸。
因此不接入正式 pipeline、不直接擴跑其他四片、不宣稱原 FN18 已修復。
新 warning policy／TP／FN／FP、identity accuracy、event accuracy 及新 passed 判斷皆 null。

下一步先明定輸入完整性、ROI 缺失／歧義的棄權方式和五球比較設計，保留原 confidence gate；
需要任何核心改動或新模型先另列方案。既有 5/5 人工 review 已完成，不重新要求完整標註。
Phase 2 仍 **NOT PASSED**；交付八球仍 candidate／pending，沒有開始 Phase 3。

## 測試與封存

完整 suite：**411 run／409 passed／0 failures／0 errors／2 skipped，63.469 秒**，
包含正式五球真實 E2E。兩項 skip 為 Windows file-symlink 建立限制；junction 回歸仍通過。
新增 14 項 producer／14 項 evaluator 測試涵蓋裁切映射、原 selector、來源像素與時間、
缺值保留、可見性、外插、既有 gate、相同集合配對及錯誤 receipt 拒絕。

374 個受保護實體來源及本輪上游 CSRT／人工回覆／舊模式對照封存 SHA 不變。
原模型 native warning 已保留於 measurement.log，無 exception；不以成功執行取代精度驗收。
本輪 output 與大圖依既有規則保存在本地 analysis_results；Git 保存工具、測試、方案與結果摘要／來源 hash。

- 輸出：`analysis_results/phase2_tracked_roi_pose_20261010_01/`
- 測試／前置核對：`analysis_results/phase2_tracked_roi_pose_proposal_20261010_01/`
- [結果 manifest](evaluation_plans/phase2_tracked_roi_pose_result_20261010_01.json)
