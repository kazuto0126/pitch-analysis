# 共用交付資料夾：第一版候選讀取器

2026-10-08。介面規格唯一來源為交付根目錄的 `CONTRACT.md`，只接受
`contract_version = 2`。不讀供片專案的程式碼、repo 或內部 output。

## 範圍

本版只匯入候選、去重、驗證 SHA-256 與逐格時間、保存來源與人工輸入覆核紀錄。
不呼叫分析、不產生 `pitch-input-v1`、不自動提升正式素材，不取代既有山本五球。
Phase 2 的 `analysis/pitch.py`、`workflow.py`、`pose_capture.py` 與其他核心維持原樣。
Phase 2 自動可靠性仍為 NOT PASSED；候選接入不改變這個結論。

## 如何接收

在本專案的 Python 環境執行：

```powershell
python -B scripts/import_handoff.py import --handoff-root D:/project/pitch-video-handoff --ffprobe C:/path/to/ffprobe.exe
python -B scripts/import_handoff.py status
```

`ffprobe` 必須已安裝；可用 PATH、`FFPROBE_PATH` 或 `--ffprobe` 指定。
不安裝、下載或替換影片工具。標準输出與本地 reports 都保留拒收原因。
有拒收／衝突時退出碼為 1；無法啟動時為 2。

- 只從 `index.jsonl` 找批次；未列入 index 的資料夾和合併觀看影片不匯入。
- index、batch、單球 JSON 各自檢查版本及識別一致性，非 2 拒收。
- 先比對 MP4 的 SHA-256，再複製配對 MP4／原始 JSON；複製後再驗 hash。
- 交付資料夾只讀，不寫入、不改名、不刪除；本地輸出限專案 `data/intake/` 下的獨立目錄。
- SQLite 保存已見 batch／pitch 與匯入事件。重跑不重複匯入、不覆寫人工紀錄。
- 相同原 ID 若 index、batch 或單球檔案改變，記錄衝突且保留舊副本；應由供片端另交新批次。
- 一球失敗只拒收該球；批次不完整時報 partial，不把數量或 pipeline 宣告當成人工通過。
- 中斷後若候選已完成改名而 ledger 未寫入，重新做時間驗證並核對保存證據，才復原登記。

## 時間驗證與記錄

逐檔完整解碼，三條件都必須符合：

1. `constant_frame_rate` 必須是 true。
2. 實際解碼格數必須等於 `frame_count`。
3. 每一格 `abs((PTS - first PTS) - i / Fraction(video.fps)) < 1 ms`。

第三項使用分數 FPS 做精確比較；恰好 1 ms 也拒收。Native PTS 來自 ffprobe
逐格解碼；OpenCV 另完整解碼以確認格數、尺寸，並保存其時間供追查。
解碼錯誤、缺 PTS、非遞增 PTS、格式／尺寸不符皆記錄拒收原因。

`timeline.json` 保存每格 native／normalized PTS、分數預期時間、偏差與最大偏差，
以及 contract 指定的 `timestamps_ms = i / fps_float * 1000`。第 0 格為 0；
`container_start_time_sec` 僅保留證據，絕不平移時間。
`pipeline_anchors_sec` 在 provenance 保存為動作能量參考，沒有轉成啟動、最高抬腿、
落地或出手等人工／生物力學事件。事件欄位保持空白。

## 本地檔案

```text
data/intake/handoff/
  state.sqlite3
  batches/b_<batch_id 的 SHA-256>/
    batch.json              原始批次 JSON
    index_entry.json        此批次的 index 紀錄
    CONTRACT.md             匯入時規格快照
  candidates/h_<pitch_id 的 SHA-256>/
    source/<原 pitch_id>.mp4
    source/<原 pitch_id>.json
    provenance.json
    timeline.json
    review.json
  reports/<run_id>.json
```

內部 ID 使用原 ID 大小寫不變的 UTF-8 SHA-256，避免 Windows 檔名大小寫碰撞，
原 batch／pitch ID 在 provenance、review 與 ledger 完整保留。
大型副本與 ledger 為本地 ignored 資料；程式、測試、對照表與文件進 Git。

`config/handoff_pitchers.json` 是本地明確姓名→投手 ID 對照表。
沒有對照時 `pitcher_id = null` 並記錄 blocker，不用字串猜 ID；
`throws: R/L/unknown` 對應 `RIGHT/LEFT/null`；game 的 unknown 轉 null。
球季照交付的已知年份保留，不能把它當成已知場次／session。
原始 JSON 不修改，來源、操作者排除紀錄與 warnings 一併保存。

## 人工輸入覆核

每球 `review.json` 起始全部為 pending，`history = []`、`latest = null`。
覆核交付的所有 `requires_human_review`，另確認 `preparation_complete`
與 `follow_through_complete`。pipeline 已驗項目仍只是來源宣告，不是人工 GT。
目前八球需人工確認身分、真的有投球、無慢動作／重播、無鏡像、全身入鏡、準備與收尾完整。

觀看本地 `source/` MP4 後，逐項明確提交；以下是命令格式，不是實際判定：

```powershell
python -B scripts/import_handoff.py review <internal_pitch_id> --item pitcher_identity --reviewer <署名> --reviewed-at 2026-10-08T21:30:00+08:00 --conclusion uncertain --note "填入實際觀察與不確定原因"
```

每筆必須有判讀者、含時區時間、結論、非空備註。結論可為 `pass`、`fail`、
`uncertain`、`not_observable`；不強迫看不清的素材通過。
每次提交追加 history、保存 UTC 時間；後提交的紀錄為 latest，原答案不刪除。

- 未填完：pending。
- 任一項 fail：rejected。
- 已填完但有 uncertain／not_observable：requires_review。
- 全部 pass：review_complete，**仍是 candidate**。

這是素材輸入覆核，與既有逐格 pose ground truth 分開保存。
正式 metadata 轉換、素材提升及分析是後續工作，尚未開啟；未知投手 ID／慣用手
也不能因覆核其他項目就被自動補值。

## 本次實測與測試

批次 `20261006T114959Z_Q8Bl2X4VKuw` 八球通過 SHA、完整解碼與逐格時間檢查。
分數 FPS 皆為 `60000/1001`；八球格數依序449、425、395、402、491、401、396、437，
共3,396格；每球最大偏差0.000666667ms。重跑新增0球、跳過8球。
八球皆為 candidate，7項輸入覆核全待填；沒有分析結果或人工判定被自動產生。

完整 suite：**302 passed、0 failed、0 errors、2 skipped**，共304項，
包含既有正式五球的真影片 E2E。新增64項匯入／時間／覆核／路徑測試。
兩項檔案符號連結測試因 Windows 無建立權限跳過；實際目錄 junction 案例通過。
交付所有檔案內容／修改時間、候選副本、374份原有保護來源皆未變。
證據與完整 log 在 `analysis_results/handoff_reader_validation_20261008_01/`。
