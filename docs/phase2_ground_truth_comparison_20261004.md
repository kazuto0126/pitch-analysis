# Phase 2 人工紀錄與 reliability 警示比較

日期：2026-10-04。HSU 已完成五支 Yamamoto 影片的定性覆核，共 **592 格**。
本次讀取已保存的 ground truth、pose reliability 與 tracking reliability，
沒有重新執行五支影片的 pose 推論。

主要發現：骨架完全消失的 3 格能由現有 selection 狀態找出；
`pitch_003` 87–104 格仍有骨架卻明顯錯位，整體 tracking screen 沒有抓到。
關節跳動提示能指出其中部分影格，但同時會提示人工認為正常的動作。
目前的 coverage、observed 狀態與連續性警示，仍不足以證明位置可信。

**Phase 2 = IN PROGRESS**。這份診斷比較不宣告 Phase 2 通過；
人工座標與事件精度仍待有對應資料後量測。

## 正式輸出與來源

- 最終 JSON：`analysis_results/phase2_gt_comparison_20261004_01/ground_truth_comparison_verified.json`。
- 來源 baseline：`analysis_results/phase2_yamamoto_20260925_01/`。
- 五份人工紀錄：baseline 下 `ground_truth/pitch_00N/ground_truth.json`，reviewer 均為 HSU。
- 最終 JSON SHA-256：`02d082f4772f062ae5bbc3e9747274bae85b5d97e51564d1b75012f70b458181`。
- 原片、人工紀錄、原始與處理後 prediction、overlay、reliability JSON 等 **126 份檔案**，比較前後 SHA-256 一致。
- 比較只寫入新檔案；原 baseline、人工標籤、原始輸出沒有覆寫。

## 如何讀取結果

人工 reliability 標籤是對原片與 **raw overlay** 的判讀；
`observed / interpolated / missing` 是處理後資料的可用性狀態。
兩者交叉對照能指出需要檢查的落差，不能直接當成處理後座標的定位誤差。

- `observed`：有通過既有 gate 的直接模型觀測，不保證位置正確。
- `interpolated`：現有 cleaner 補點，不代表人工看得到或座標正確。
- `missing`：處理後缺點；raw overlay 仍可能畫出模型點或線。
- 人工 `uncertain / not_observable`：在關節 jump screening 的分母中排除，另外列出。
- 未確認遮擋原因的 `not_observable`，不會改成「已確認身體遮擋」。

人工標註仍是定性紀錄。例如 `pitch_001` 47–54 格的逐關節標籤記錄誤連裁判腳，
整體 throwing-arm 遮擋紀錄也涵蓋該段。此次忠實對照現存逐關節標籤，
保留兩種紀錄；這不能推出被遮住關節的真實位置。後續人工座標 workflow
將「可見且定位」「不確定」「不可觀測」分開，避免把這類誤連判斷當成透視座標。

## 五支影片的實際差異

表中的「整體提示」指 selection rejection 或現有 per-frame tracking warning。
「仍為 observed」只表示人工標籤與模型可用性狀態的交叉格數。

| 影片 | 總影格 | 人工重大 pose failure | 整體提示涵蓋／漏掉 | 人工 track break／模型吻合 | 肘：人工不可靠但仍 observed | 腕：人工不可靠但仍 observed |
|---|---:|---:|---:|---:|---:|---:|
| pitch_001 | 87 | 0 | 0／0 | 0／0 | 11／12 | 9／17 |
| pitch_002 | 175 | 0 | 0／0 | 0／0 | 0／0 | 0／2 |
| pitch_003 | 115 | 18 | 0／18 | 0／0 | 29／36 | 12／12 |
| pitch_004 | 114 | 2 | 2／0 | 2／2 | 6／8 | 20／30 |
| pitch_005 | 101 | 1 | 1／0 | 1／1 | 26／28 | 8／10 |

- `pitch_001`：沒有整體換人或重大失效；局部手肘／手腕誤連與漏標仍存在。
  人工不可靠而模型仍 observed 的肘區段為 36–37、47–54、58；腕為 20、47–54。
- `pitch_002`：人工確認主體及大部分可見關節對位；手腕 18–19 格漏標在處理後也非 observed。
  不可觀測區段仍有 4 格肘、2 格腕被模型列 observed，不能拿來當真實可見性證據。
- `pitch_003`：87–104 格重大錯位沒有整體 tracking warning；當時整體 tracking flag 仍是 reliable。
  右肩該 18 格全為 observed。肘有 29 格、腕有 12 格落在人工不可靠而模型仍 observed 的交叉格。
- `pitch_004`：75–76 格全身骨架消失與模型 track break 完全吻合。
  27–32 格肘標歪仍全為 observed；腕的交叉區段為 14–19、21–32、78–79。
- `pitch_005`：54 格全身骨架缺失與模型 track break 完全吻合。
  肘 6–23、29–33、58、74–75 格仍為 observed；腕為 24–28、58、74–75。

這些是可追查差異，沒有建立總分或候選排名。

## 追蹤、重大失效與跳動提示

HSU 判斷五支皆持續選到投手，沒有 confirmed identity switch；模型也沒有 switch warning。
本資料沒有陽性 identity-switch 案例，因此 sensitivity／recall 維持 null。
這只能說目前五支未見警示與人工換人紀錄不一致，無法證明換人偵測能力。

| 指定比較目標／提示來源 | 人工陽性格 | 提示涵蓋 TP | 未提示 FN | 目標外提示 FP | 人工陽性涵蓋率 |
|---|---:|---:|---:|---:|---:|
| Track break／selection rejection | 3 | 3 | 0 | 0 | 3／3 |
| Major pose failure／整體 tracking screen | 21 | 3 | 18 | 9 | 3／21 = 14.3% |
| Major pose failure／上述 screen 加六關節 jump 端點 | 21 | 13 | 8 | 56 | 13／21 = 61.9% |

最後一列只是現有提示的診斷聯集，沒有加入新的 detector 或改動 baseline flag。
它提升影格涵蓋率，同時增加 **56 格目標外提示**，不能只引用提升的涵蓋率。
其 exact-frame precision 為 13／69 = 18.8%；整體 tracking screen 為 3／12 = 25.0%。

整體 tracking screen 的 9 格目標外提示為：001 的 35–36、003 的 65 與 73、
004 的 65–67、005 的 53 與 62；全是 `raw_body_scale_unavailable`。
它們可提示幾何資訊不足，但並非人工 major pose failure；這裡的 FP 只相對該指定目標。

`pitch_003` 的 jump 端點聯集涵蓋 87–89、91、93、95、97、99、101、104，共 10／18 格，
仍未涵蓋 90、92、94、96、98、100、102–103。
Warning 可能只落在異常開始或轉換邊界；報告另列每段有無任一提示，不擅自擴張提示影格。

## 六關節交叉對照

每個關節各有 592 格；下列「人工不可觀測但 observed」不算模型定位錯誤，
因為沒有可確認的人工位置證據。

| 關節 | 人工可靠 | 人工不可靠 | 人工不可觀測 | 不可靠且 observed | 不可觀測且 observed |
|---|---:|---:|---:|---:|---:|
| Throwing shoulder | 571 | 21 | 0 | 18 | 0 |
| Throwing elbow | 449 | 84 | 59 | 72 | 20 |
| Throwing wrist | 384 | 71 | 137 | 49 | 36 |
| Lead hip | 587 | 4 | 1 | 2 | 0 |
| Lead knee | 582 | 8 | 2 | 2 | 0 |
| Lead ankle | 584 | 5 | 3 | 3 | 0 |

六關節此次沒有人工 `uncertain` 格；不確定性仍存在於事件。
完整 4 × 3 cross-tab、joint jump 端點吻合、逐影片 clip-level flag 及影格範圍均保存在 JSON。
84 格人工不可靠的 elbow 中，72 格仍 observed；71 格不可靠的 wrist 中，49 格仍 observed。
因此直接觀測 coverage 不能單獨衡量 raw overlay 是否抓對位置。

## 事件與尚不能衡量的項目

所有五支事件保留原始 status、exact frame、frame range、confidence 與 reviewer note。
`pitch_005` 準備開始候選 0、最高抬腿候選 33 仍為 uncertain；落腳 55、出手 58–59、收尾 83。
其他影片的範圍也沒有改成單一影格。

- Event timing error：未量測，baseline 沒有對應的自動事件估計。
- X/Y 定位誤差：未量測，同學人工座標尚未回傳。
- 遮擋原因準確率：未量測，baseline 沒有遮擋原因 detector。
- 跨 reviewer 一致性與其他投手泛化：未量測。

## 驗證及下一步

完整 test suite：**147 passed、0 failed、1 skipped**（148 discovered）。
Skipped 是需明確啟用的正式影片 E2E，因此未重新分析正式五支影片；
既有 synthetic-video MediaPipe 測試有執行。
Log：`analysis_results/phase2_gt_comparison_20261004_01/test_suite.log`。

新增測試涵蓋未知標籤排除、警示端點／異常區間區別、六關節 cross-tab、
事件範圍與 uncertainty 保留、來源 hash／投手 ID／時序一致，以及拒絕覆寫輸出。
獨立從原始五份 GT 與 reliability JSON 重算的各項格數與最終結果一致。

接著先驗證同學的 0–4 格 CVAT pilot，再收完整 `pitch_003` 座標與兩支事件補充。
根據本報告與人工座標證據，再討論如何改進「有骨架但穩定錯位」與局部誤連的提示。
本次只擴充比較與驗證功能，pose／tracking 演算法、threshold、gate、smoothing／interpolation 均未修改。
Phase 3 與 Clipper 正式接入仍依現有順序另行進行。
