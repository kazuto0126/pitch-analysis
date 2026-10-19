# 投手範圍鎖定修正：交付結果

2026-10-19（台灣）。**可選主體約束與候選紀錄已完成；錯人例子部分改善，五球仍 degraded，Phase 2 自動可靠性仍 NOT PASSED。**

使用者核准最小修正，並確認五球橘框皆可使用。設定為原畫面 normalized `(0.10, 0.33, 0.43, 0.92)`：左右肩／髖四個模型點都必須在框內；手腳可伸出。設定是操作輸入，不是自動辨識投手或新增逐格GT。

## 已交付的行為

- 指定範圍時，PitcherSelector先排除軀幹不在範圍的候選；沒有符合者就保留missing／rejected。未指定設定時維持原排序、選取閾值與預設行為。
- 模型仍看完整原影片，不裁切、不放大、不換模型；MediaPipe、原品質gate、信心門檻、插值／平滑保持。
- 可選逐格候選側檔保留所有33點原始輸出、visibility／presence、決策與排除理由；當格候選index不當作跨格身分。
- `subject_roi`、`record_candidates`由既有分析／workflow傳至capture；analysis provenance有選填設定與模式欄位，舊input metadata／原契約必填要求保持。
- 薄入口 `scripts/run_pitcher_lock_pilot.py`先驗證整批操作確認與來源SHA，再各跑一次；原五球試用與山本歷史輸出沒有覆寫。

## 五球結果與資料保留

| 大谷球號 | 原選中 | 鎖定後選中／總格數 | 鎖定後比例 | 最長gap：原→新 | 肘角raw：原→新 | 結果 |
|---|---:|---:|---:|---|---|---|
| p01 | 333 | 332/362 | 91.71% | 5→9格 | 59.12%→58.84% | degraded |
| p02 | 300 | 170/326 | 52.15% | 6→49格 | 56.44%→27.61% | degraded |
| p03 | 397 | 397/422 | 94.08% | 6→6格 | 36.49%→36.49% | degraded |
| p04 | 345 | 334/410 | 81.46% | 11→15格 | 38.78%→37.56% | degraded |
| p05 | 302 | 215/353 | 60.91% | 7→54格 | 78.19%→36.83% | degraded |

**總選中格數 1,677→1,448，淨少229格；missing 196→425格。** 其中251個舊selected變missing，22個舊missing變selected；不能把251格全部算成抓到錯點。未新增逐格正確性GT，也不以大量拒絕資料當成通過。
425個未選影格中：86格模型沒有候選、263格沒有任一候選的四個軀幹點同時落入指定範圍、76格有範圍內候選但仍被既有信心／連續性／模糊判定拒絕。這是操作與模型輸出分類，不是人工錯點標籤。
p02與p05最大缺口分別49／54格（約0.82／0.90秒）；後續需要更完整的正確投手候選。現有位置約束本身不會恢復模型沒有給的關節。
肘角raw是肩／肘／腕三點同時可量測的比例，不是單一手肘位置準確率。六個重要關節的raw／observed／interpolated／missing、visibility與gap保存在每球reliability JSON。

## Overlay實際檢查

五支原生overlay全部完整解碼，合計1,873格，格數與來源一致；實際檢查與原試用相同的每片14格source／new-overlay圖（70格），另有每片首／中／尾全畫面。這是agent抽樣檢查，沒有替使用者填新的骨架GT。

| 大谷球號 | 原錯例與目前觀察 |
|---|---|
| p01 | 抽樣與原本接近，投球段missing仍存在；最長gap由5增為9格。 |
| p02 | f177、266、325原錯人／混合骨架現在被拒絕；f238仍有跨人手臂連線，並非所有關節已修好。 |
| p03 | 抽樣與原本相同，保留397格；手腕與肘角coverage問題仍在。 |
| p04 | f297原跨人連線改成missing；f223上身局部錯位仍保留，最長gap15格。 |
| p05 | f0裁判骨架改為missing；f32、64、96、128、160改選投手骨架，f320打者骨架被拒絕；f192、224、352仍可見混合手臂連線。 |

因此這次有實質的有限改善：範圍外整副錯人可被排除，也能在模型已有投手候選時改選投手；但軀幹留在範圍內的混合手臂仍可通過。沒有宣稱全片無identity switch或所有關節可靠。

## 測試與原值保存

- 完整suite一次：**1001 run、999 passed、0 failed、0 errors、2 skipped**，89.641秒、exit0；新增32項測試。
- 正式山本五球E2E回歸有執行，原major提示仍為2／0／19／5／3。兩個skip是原有Windows file-symlink能力限制；junction案例有執行。
- 一次只讀候選／raw核對：1,873逐格紀錄、2,801副候選、92,433原始點；選中47,784點與各自來源候選逐值完全相等。425個未選frame未寫入raw，5,792個肩／髖範圍檢查全符合，0錯誤。
- 來源影片／模型／操作設定SHA符合；核對讀取的32份來源與產物前後未變。這是保存／接入正確性，不是模型準確率。

## 使用與輸出

操作設定：[已確認設定](../config/pilots/ohtani_subject_region_20261019.json)。各球SHA、HSU署名、含時區確認時間與備註均保留。

```powershell
.\.venv-analysis\Scripts\python.exe -B scripts/run_pitcher_lock_pilot.py input/shohei_ohtani/phase2_pilot_20261019_01 config/pilots/ohtani_subject_region_20261019.json analysis_results/NEW_subject_lock_output
```

以上只供未來重現；本次五球已各跑一次，不需再執行。入口拒絕覆寫既有輸出。

- 本次輸出：`analysis_results/phase2_ohtani_subject_lock_20261019_01/`，先看 `START_HERE.md`。
- 新分析：`run/predictions/shohei_ohtani/pitch_001`–`005`；每球有 `pose_raw.candidates.jsonl` 與原分析產物。
- 全批統計：`evaluation_summary.json`；逐關節／追蹤：`reliability/`；實際檢查：`visual_review/inspection.json`；原值核對：`trace_preservation_audit.json`。
- `full_suite.log`、`pilot_run.log`、`run/source_mapping.json`保留測試、執行與設定來源；原MediaPipe的raw座標沒有被人工修正。
- 已備妥新舊並列觀看頁與10份H.264／yuv420p播放副本，原overlay保留。副本完整解碼共3,746格、尺寸與各自來源格數一致；保留來源overlay的59.94 FPS，沒有補格、變速或裁切。細節在`view_manifest.json`。

## 決策與停止點

此版作為**明確操作範圍下的可選保護**交付，沒有把它改成全自動投手身分辨識或正式reference通過。五球仍degraded，原Phase2 automatic reliability維持NOT PASSED。
已依核准方案完成一次五球試跑、原錯例檢查與完整測試，commit／push後停止。本輪不再更換ROI範圍或調參來追求通過。若後續要補足候選缺失或混合手臂，需要另定新資訊／處理範圍；未增加投手或進Phase3。
