# 落地到大致出手：模型角度端點變化

更新：2026-10-26（台灣）。

正式事件報告已能回答同一球在人工落地與出手標記之間，投球肘、前導膝的模型XY角度
各變化多少。沿用原曲線與既有人工事件，沒有重跑骨架或要求重新標註。

變化量定義為「出手角度−落地角度」。人工事件是範圍時，保留所有落地格不晚於出手格的
配對，列出差值極值及完整分母，不選中點。這是端點差，並非期間最大活動範圍、
真實人體伸屈或動作品質分數；配對也不是獨立樣本。

## 大谷五球

| 影片 | 原時距（格） | 肘模型XY變化（度） | 前導膝模型XY變化（度） | 合法事件配對 |
|---|---:|---:|---:|---:|
| supplement_001 | 9–10 | +152.4 至 +157.4 | +27.9 至 +33.4 | 2 |
| supplement_002 | 8 | +150.3 | +4.1 | 1 |
| supplement_003 | 8 | +129.9 | −7.3 | 1 |
| supplement_004 | 5 | +106.4 | +4.0 | 1 |
| supplement_005 | 10–11 | +142.6 至 +144.8 | +38.6 至 +44.7 | 2 |

前導膝002／004的端點差分別約+4.1°／+4.0°；003為−7.3°；001與005的可能差值都為正。
這描述各片兩端的模型讀值，不能解讀為人體動作是否正確或投手整體穩定度。
肘的部分大幅差值包含先前已記錄的落地近0°投影；原值保留，沒有自動當成伸肘幅度或錯點。

[大谷報告](../analysis_results/phase3_event_transition_20261026_01/ohtani/report.md)；
[摘要CSV](../analysis_results/phase3_event_transition_20261026_01/ohtani/event_transition_readouts.csv)；
[全部配對CSV](../analysis_results/phase3_event_transition_20261026_01/ohtani/event_transition_pairs.csv)。

## 山本四支啟用影片

| 影片 | 原時距（格） | 肘模型XY變化（度） | 前導膝模型XY變化（度） | 合法事件配對 |
|---|---:|---:|---:|---:|
| pitch_001 | 4–6 | +60.4 至 +134.3 | +72.1 至 +86.0 | 4 |
| pitch_002 | 1–3 | +1.0 至 +13.6 | +1.2 至 +9.1 | 3 |
| pitch_004 | 4–6 | +76.7 至 +148.2 | +5.1 至 +61.4 | 4 |
| pitch_005 | 3–4 | −100.3 至 −39.6 | +4.8 至 +9.1 | 2 |

001／004保留兩個可能落地格，因此差值界線同時包含起點與終點選擇的影響。
005肘的全部候選端點差為負，其他三球為正；符號描述投影數值，不能判斷實際伸屈方向。
003仍為歷史對照，不恢復正式使用。兩位投手各自呈現，沒有跨投手評分或排名。

[山本報告](../analysis_results/phase3_event_transition_20261026_01/yamamoto/report.md)；
[摘要CSV](../analysis_results/phase3_event_transition_20261026_01/yamamoto/event_transition_readouts.csv)；
[全部配對CSV](../analysis_results/phase3_event_transition_20261026_01/yamamoto/event_transition_pairs.csv)。

## 交付與缺值處理

原`compare-native-motion-events`指令及設定不變；新目錄輸出另附：

- `event_comparison.json`的`event_transition_readouts`：逐球配對、原時距與兩關節摘要。
- `event_transition_readouts.csv`：每球兩列，本次共18列。
- `event_transition_pairs.csv`：每合法事件配對的兩關節各一列，本次20配對、40列。
- `report.md`：新增「落地→大致出手的模型XY變化」表。

本次40列皆可計算，僅代表模型兩端座標齊備。逐點可靠性仍unknown、usable_for_analysis仍null。
一般輸入若缺點或退化，配對保留且差值null；全不可算時極值null。未確認事件不取候選角度，
摘要計數也保持null。缺點與退化配對數可重疊，不可計算數為聯集；原始分母不縮減。
倒序配對另計，不納入差值；同格配對保留0時距。每筆時間按原片分數FPS換算。

## 驗證與狀態

新增11項Python測試，包含手算端點差、完整／倒序配對、分數FPS、缺點／退化、
不確定候選不讀取、深拷貝與兩份CSV／報告來源保持。針對性測試11/11通過。
完整suite：**1262項，1260 passed／0 failed／2 skipped**，包含正式山本五球MediaPipe E2E。
兩項跳過皆為Windows環境不支援檔案符號連結，沒有未修復失敗。
[完整來源與測試紀錄](dataset_selections/phase3_event_transition_20261026.json)。

獨立唯讀核對18摘要、40關節配對、20事件配對全部一致；原九球的90視窗與36時距保持，
四份舊時距／角度CSV逐bytes相同，564份受保護檔案SHA無變更。
JS／播放器未改，本輪未重跑Node；前輪相同JS為11項Node測試通過、事件helper34項斷言通過。
本輪不主張新的瀏覽器互動驗證或人工接受。

根目錄：`analysis_results/phase3_event_transition_20261026_01/`。
pose／tracking核心、門檻、raw、GT與已採用的骨架模式保持；新增模型推論／追蹤／標註皆0。
Phase 1 PASSED；Phase 2原自動可靠性NOT PASSED；Phase 3整體尚未驗收。
本輪完成測試、文件、commit與origin push後停止。
