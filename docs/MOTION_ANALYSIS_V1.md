# 投球動作描述第一版

更新：2026-10-27（台灣）。本文件集中目前可用成果、解讀方式與下一步；詳細開發紀錄見
[current_status](current_status.md)，計算定義見[人工事件與曲線對照](native_motion_events.md)。

## 目前交付與專案目標

專案接收已整理的單球MP4與metadata，目標是單一投手motion profile及後續投手間完整時序比較。
目前已完成本文件所列的**描述性第一版交付**：既有骨架、影片／曲線回看、人工事件時距及兩關節投影讀值。
它支援查看同一投手各球的差異，尚未交付完整profile、跨投手動作相似度或動作品質評分。
後續已新增[人工事件時距對照](native_timing_comparison.md)，僅比較原事件界線下的分數秒時距。
亦已接上[雙側回看入口](native_timing_comparison.md#直接從差值回看兩側影片)，可從差值選兩球並定位到人工事件原格號。
另提供可重跑的[單投手摘要入口](native_descriptive_profile.md)，讓相同時距關係與肘／膝端點方向可由原事件報告自動產生，沿用於後續投手。
亦可查看[人工區段內的模型讀值範圍](native_stage_curves.md)，列出所有合法事件選格下的內部極值、原格號與缺值分母，連回原片查核。
兩位投手的[完整模型曲線並列圖版](native_cohort_curves.md)使用共用落地相對秒數刻度，保留全部人工原點與原格回看；這是顯示對照，尚未計算動作相似度。

狀態各自保留：Phase 1 PASSED；原生資料介面接入PASSED；Phase 2自動可靠性NOT PASSED；
本批描述性交付COMPLETE；Phase 3整體尚未驗收。此整理不改寫原驗收標準。

## 從這裡開始使用

| 目的 | 現有入口 | 內容與版本 |
|---|---|---|
| 並列回看兩位投手完整模型曲線 | [同刻度圖版](native_cohort_curves.md) | 原分數FPS、全部人工落地原點、缺口與原格連結；沒有平均或時間拉伸 |
| 查看人工區段內的模型極值 | [區段內模型讀值](native_stage_curves.md) | 可能／共同影格與全部合法區間、肘／膝原格號、缺值分母；未知事件不使用候選 |
| 一個指令建立單投手交付 | [build-native-motion-report](native_descriptive_profile.md#建議入口一個指令整合三步) | 讀取既有曲線＋人工事件設定，串接事件報告、單投手摘要、回看頁與START_HERE；未加入新推論 |
| 自動整理單投手動作描述 | [describe-native-profile](native_descriptive_profile.md) | 大谷5／山本4：64組同投手時距配對（56可比／8未定），72筆肘／膝摘要（66有可算端點／6未定）；保留全部事件選格 |
| 從單投手摘要回看證據 | [review-native-profile](native_descriptive_profile.md#從摘要直接回看影片證據) | 選原區段／球對，查看時距與肘／膝讀值後，用已確認事件界線定位各自原片；單球不補自比 |
| 看大谷五球最新數字 | [完整報告](../analysis_results/phase3_manual_stages_20261026_01/ohtani/report.md)／[四段CSV](../analysis_results/phase3_manual_stages_20261026_01/ohtani/manual_stage_readouts.csv) | 最新四段時距、肘／膝模型XY端點差、人工事件與來源 |
| 看山本四球最新數字 | [完整報告](../analysis_results/phase3_manual_stages_20261026_01/yamamoto/report.md)／[四段CSV](../analysis_results/phase3_manual_stages_20261026_01/yamamoto/manual_stage_readouts.csv) | 最新四段讀值；001／005未確認事件保留空值 |
| 回看片段與事件 | [大谷觀看頁](../analysis_results/phase3_manual_stages_20261026_01/ohtani/viewer/review_motion_events.html)／[山本觀看頁](../analysis_results/phase3_manual_stages_20261026_01/yamamoto/viewer/review_motion_events.html) | 原影片／骨架、曲線及事件對照；四段端點差完整表在上列報告／CSV |
| 從時距對照回看兩側影片 | [雙側回看頁](../analysis_results/phase3_manual_timing_viewer_20261026_01/review_timing.html) | 既有80組差值與事件界線定位；原FPS獨立播放，瀏覽器實際播放尚未覆核 |
| 在另一台電腦看完整最新描述性成果 | [可攜02包](phase3_portable_review_20261026.md)／[本機START_HERE](../analysis_results/phase3_portable_review_20261026_02/pitch_motion_review_20261026_02/START_HERE.html) | 九球、兩份草案、最新四段與時距資料、雙側回看頁；舊01快照保留 |

先看逐球時距，再開觀看頁回到該事件格與原曲線。需要檢查數字時，報告列有原事件格號，
每段的合法影格配對另存同目錄`manual_stage_pairs.csv`；不要把事件範圍自行縮成中點。

`analysis_results/`是本機產物，不隨GitHub原始碼下載。分享既有ZIP時先完整解壓縮、保留結構，
以Chrome／Edge開啟START_HERE；後續可攜02包已整合最新結果，但不新增人工播放接受紀錄，舊01包保持原樣。

## 目前資料與結果

| 資料 | 啟用影片 | 影格與FPS | 素材身分 |
|---|---|---|---|
| 大谷翔平 | supplement_001–005 | 1684格；60000/1001 FPS | 已獲整片骨架接受的候選素材，未轉為正式reference |
| 山本由伸 | pitch_001、002、004、005 | 477格；30/1 FPS | 分析啟用四球；003仍為歷史對照，Phase 1正式五球及舊結果保留 |

九球共2161格。九份既有曲線摘要顯示肘與前導膝各2161格皆可計算，缺點／退化格均為0；
這只表示模型座標可形成角度，逐點可靠性仍為unknown、`usable_for_analysis=null`。
九球共45筆人工事件、36段時距；33段可描述，三段因事件未確認而留空。
72筆關節端點差摘要中66筆可計算、六筆未定。缺值不是0，也不是已判定模型標錯。

### 能直接描述：人工落地到大致出手的時距

| 投手 | 影片 | 秒數範圍 |
|---|---|---:|
| 大谷 | supplement_001 | 0.150–0.167 |
| 大谷 | supplement_002 | 0.133 |
| 大谷 | supplement_003 | 0.133 |
| 大谷 | supplement_004 | 0.083 |
| 大谷 | supplement_005 | 0.167–0.184 |
| 山本 | pitch_001 | 0.133–0.200 |
| 山本 | pitch_002 | 0.033–0.100 |
| 山本 | pitch_004 | 0.133–0.200 |
| 山本 | pitch_005 | 0.100–0.133 |

在已記錄的人工事件範圍下，大谷004此時距短於其餘四球；002與003時距相同，並不表示兩球整個動作相同。
山本002此時距範圍與001／004分開；005與002及001／004的範圍各有接觸邊界，不能據此確定先後差異。
這些是本批人工紀錄的時序描述，不是投球表現排名，也不是投手整體穩定度或泛化結論。
30 FPS的一格約33.3 ms、60000/1001 FPS的一格約16.7 ms，保留各片原始精度。

### 需要保留的不確定性

- 山本001片頭左腳已抬起，啟動不可觀測；005啟動及最高抬腿仍uncertain，因此相關三段保持未定。
- 山本005出手第58／59格的肘模型投影角為133.9°／73.2°，相鄰格相差60.7°；不能選一格代表唯一精確出手角。
- 大谷005最高抬腿→落地的前導膝端點差為−9.6°至+8.5°，正負隨合法選格而變；不能斷言一定增加或減少。
- 曲線尖峰可能涉及快速運動、遮擋、投影或定位誤差，現有證據無法單靠曲線分辨原因；整片人工接受不等於逐點精確度已量測。
- 端點差不是期間最大活動幅度，也不是人體真實3D伸屈。相鄰段共用事件，各段獨立上下界不能直接相加成一條一致動作。

## 第一版在這裡收束

| 本版交付項目 | 現況 |
|---|---|
| 保留使用者已接受的共用骨架方式與九球結果 | 完成；[固定骨架流程](standard_skeleton_workflow.md) |
| 同投手逐球回看片段、曲線及已標人工事件 | 既有觀看頁與來源已保存；整片接受範圍不提升為逐點GT |
| 原事件格／範圍、分數FPS時距、模型讀值與未知狀態可追查 | 完成；最新兩份報告、CSV與來源紀錄已存在 |
| 清楚說明目前能描述與不能推論的內容 | 本文件與原計算定義共同提供 |

本版收束不要求把uncertain強迫改成精確事件，也不追加逐格標註、新模型或零錯誤條件。
現有相同讀值不再拆成新的報表交付。第一版收束時的產品程式完整suite為2026-10-26的
**1268 passed／0 failed／2 skipped**，含正式山本五球E2E；兩項跳過為Windows檔案符號連結能力不足。
[原測試與來源紀錄](dataset_selections/phase3_manual_stages_20261026.json)。本次只整理文件，不重跑模型或相同suite。
後續時距對照／雙側回看入口的最新測試為1289 passed／0 failed／2 skipped，
另Node18項及34項既有事件helper斷言通過，見[時距對照交付](native_timing_comparison.md)。

## 已交付的下一工作單位：單一投手motion profile草案

[大谷五球動作特徵草案](profiles/shohei_ohtani_descriptive_v1.md)與
[山本四球動作特徵草案](profiles/yoshinobu_yamamoto_descriptive_v1.md)已各自使用現有資料回答：

**同一投手各球的哪些階段差異，在所有合法人工事件影格選擇下仍成立；哪些差異會隨選格改變？**

草案集中四段時距與兩關節曲線的共同端點變化、逐球例外，附球號、事件格／範圍及原片回看入口；
依「本批可描述」「受選格影響」「資料不足」說明結論。大谷001／004前段時距較長、005抬腿到落地較短，
在既有事件範圍下成立；其005與002的部分時距重疊、膝模型差值跨0等情況保持不確定。
山本002落地→出手短於001／004，但最高抬腿→落地的三球已確認範圍互相重疊，
005早段候選不參與計算；001膝跨0與005肘的逐球例外亦保留。
以上達成本工作單位的文件交付條件，不把模型投影當成人體角度真值。

本批兩份單投手草案的描述工作已完成。後續的[時距對照入口](native_timing_comparison.md)
可重跑兩位投手四段時距的球對關係，不使用未校準投影角產生相似度、分數或排名。
既有骨架方式、原資料／GT與門檻保持，沒有重新推論或重開Phase 2試驗。
這不是正式`pitcher-profile-v1`契約輸出，也不提升素材資格或Phase整體狀態。

上述單投手統計現可用[describe-native-profile](native_descriptive_profile.md)由保存報告重跑，
不必為下一位投手重寫統計；原兩份人工整理草案保留。此輪完整Python suite為
1301 passed／0 failed／2 skipped（含八項junction補跑及正式五球E2E），Node18項通過。

後續[摘要回看入口](native_descriptive_profile.md#從摘要直接回看影片證據)已把原球對、端點差與
事件影格接到兩側播放器；完整Python suite1309 passed／0 failed／2 skipped、Node23項通過。

現已提供[單一交付指令](native_descriptive_profile.md#建議入口一個指令整合三步)，把原三步串成
同一份START_HERE交付；摘要與原資料一致，最新完整Python suite1316 passed／0 failed／2 skipped。

後續[區段內模型讀值](native_stage_curves.md)已補上中間極值與原格回看，保留合法選格、完整分母及未定事件。
此輪完整Python suite1331 passed／0 failed／2 skipped；原JS保持，未重跑相同Node suite。

後續[完整曲線並列圖版](native_cohort_curves.md)保留9球2161來源格與11個人工顯示原點，
提供兩關節共享尺度／原格連結。此輪完整Python suite1341 passed／0 failed／2 skipped；未增加相似度或品質分數。
