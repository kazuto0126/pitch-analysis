# 可重跑的單投手動作描述

更新：2026-10-27（台灣）。`describe-native-profile`讀取一份已保存的單投手人工事件報告，
自動整理同投手各球的時距關係與肘／膝模型XY端點差，避免為每位投手手寫相同統計。
它不執行新pose／tracking，也不把描述性摘要升為正式reference。

## 執行

在專案根目錄，以已產生的`event_comparison.json`作為輸入，指定未存在的新輸出目錄：

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe describe-native-profile analysis_results/phase3_manual_stages_20261026_01/ohtani/event_comparison.json --output analysis_results/my_ohtani_profile
```

新投手先完成既有[共用骨架流程](standard_skeleton_workflow.md)、
[原生動作曲線](native_motion.md)及[人工事件報告](native_motion_events.md)，再沿用此入口。
只接受同一投手的一份來源綁定報告，不要求指定姓名；一球可產生描述，但沒有跨球比較。
本批實際輸出位於`analysis_results/phase3_native_profiles_20261027_01/`：

| 投手 | 球數／格數 | 同投手時距球對 | 肘／膝區段摘要 |
|---|---:|---:|---:|
| 大谷 | 5／1684 | 40，全部可比 | 40，全部有可算端點 |
| 山本（001、002、004、005） | 4／477 | 24，16可比／8未定 | 32，26有可算端點／6未定 |

[大谷報告](../analysis_results/phase3_native_profiles_20261027_01/ohtani/report.md)／
[山本報告](../analysis_results/phase3_native_profiles_20261027_01/yamamoto/report.md)。
歷史山本003保持排除；山本001啟動不可觀測、005啟動／最高抬腿不確定，均保持原狀。

## 四份輸出

| 檔案 | 內容 |
|---|---|
| `profile.json` | 四段摘要、全部球對、每球端點配對、原事件／FPS與來源SHA、未知原因 |
| `report.md` | 本批時距涵蓋範圍、全部球對、肘／膝方向分組、各球端點差與缺值、來源連結 |
| `timing_relations.csv` | 全部同投手球對的精確分數秒界線、A−B與未定原因 |
| `joint_direction_summary.csv` | 四段×兩關節的正／負／零／含零／未定計數及全部球共同方向 |

報告綁定原request、曲線、人工事件與覆核範圍，並核對保存的四段讀值。
來源SHA不符、報告內容與原來源不一致、缺少四段讀值或輸出已存在時拒絕寫入。
原影片、raw prediction、GT、既有gate與素材資格保持。

## 如何解讀

- 時距使用各球原分數FPS；保留上下界，不取中點。範圍相接、重疊與嚴格較短／較長分開記錄。
- 時距涵蓋範圍只覆蓋本批已確認界線，不是平均、信賴區間或投手整體變異。
- 肘／膝方向沿用未四捨五入的模型端點差；微小負值仍保留，不因顯示成負零而改判。
- 「全部球共同方向」要求每球都有可算端點且方向同為正、負或零；含零或未定會保留，不能據此宣稱整段單調或跨球穩定。
- 有可算端點只代表至少一組合法事件端點具保存讀值；部分配對缺值仍保留。事件未定的配對數為null，已確認但全缺座標則可算數為0。
- 相鄰區段共用事件，各段獨立極值不能相加成單一路徑；球對不是獨立樣本。極小分數秒差也不代表生理事件計時精度。

此處使用`native-descriptive-pitcher-profile-v1`描述性輸出；不是正式`pitcher-profile-v1`，
不產生標準動作、真實3D角度、品質分數、排名或相似度。
逐點可靠性仍`unknown`、`usable_for_analysis`仍null。
Phase 2自動可靠性仍NOT PASSED，Phase 3整體尚未驗收；不新增人工標註或重開模型試驗。
現有可攜02 ZIP仍是前次觀看快照，不包含這個後續CLI與新生成檔案。

## 從摘要直接回看影片證據

`review-native-profile`把保存的摘要接上既有原片／骨架與曲線播放器。
它讀取已產生的`profile.json`，不重跑骨架或更動人工事件：

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe review-native-profile analysis_results/phase3_native_profiles_20261027_01/ohtani/profile.json --output analysis_results/my_ohtani_profile_review
```

開啟新目錄的`review_profile.html`：

1. 選人工事件區段，再選一組已保存的球對。
2. 查看這一段的本批時距涵蓋、肘／膝方向分組，以及當前兩球各自的端點差、可算／全部配對數。
3. 按A或B的事件影格按鈕回看證據。精確事件只有一格；範圍分下界與上界，兩側各自獨立播放。

球對只使用原摘要的單向組合，不加入反向或自比；切換區段保留所選球對。
單球摘要顯示單一播放器與該球時距，不製造跨球比較。
未確認／不可觀測事件沒有定位按鈕，其他已確認事件仍可回看。
影片跳格實際呈現以播放器格號為準；這不是同步對齊或時間拉伸。
完整逐片事件表仍使用原[事件觀看頁](native_motion_events.md)，本入口只顯示當前區段。

本機入口：
[大谷五球](../analysis_results/phase3_native_profile_review_20261027_01/ohtani/review_profile.html)／
[山本四球](../analysis_results/phase3_native_profile_review_20261027_01/yamamoto/review_profile.html)。
各自沿用40／24組原球對，沒有新增推論、GT、品質分數或素材升格。
來源或摘要被改動時拒收；輸出須為新目錄。
原影格播放器與跳格adapter保持；瀏覽器實際播放仍未確認，不新增人工接受紀錄。

## 回看入口驗證

新增8項Python與5項Node測試，涵蓋來源／摘要拒收、原時間軸／腳本保留、canonical球對、
換區段保留球對、未知事件無定位、單球無自比、既有兩投手模式與CLI。
完整Python suite1311項：初跑1301 passed／0 failed／10 skipped，八項junction案例補跑全過；
不重複計為**1309 passed／0 failed／2 skipped**，含正式五球E2E。
兩項跳過仍為Windows檔案符號連結能力限制。Node **23 passed／0 failed**，另含34項既有事件helper斷言。
實際輸出九個來源頁保留2161格、64組原球對及全部72筆關節摘要，未定事件不改寫。
[回看交付與測試紀錄](dataset_selections/phase3_native_profile_review_20261027.json)。

### 摘要產生器驗證（前段）

新增12項測試，涵蓋分數FPS、未知事件、缺座標、微小負值跨零、任意投手ID、單球、
來源SHA／過期摘要拒收、防覆寫及CLI。完整Python suite1303項：初跑1293 passed／0 failed／10 skipped，
八項Windows junction案例已補跑全部通過；合併不重複計數為**1301 passed／0 failed／2 skipped**，
包含正式山本五球E2E。兩項跳過為檔案符號連結能力限制。Node18項及既有34項事件helper斷言通過。
[交付與測試紀錄](dataset_selections/phase3_native_profiles_20261027.json)。
