# 交付接入逐項回歸核對

日期：2026-10-09（台灣）。交付功能基準 commit：`5431161`；此前 Phase 2 基準：`7f0f9e6`。
完整實際命令、stdout、SQLite與檔案快照在
`analysis_results/handoff_regression_20261009_01/`，先看 `audit_summary.json`。

## 1. 匯入結果

原始匯入 stdout（`analysis_results/handoff_reader_validation_20261008_01/first_import.json`）：

```text
imported_candidates = 8
already_imported = 0
rejected = 0
conflicts = 0
```

批次：`20261006T114959Z_Q8Bl2X4VKuw`；沒有被拒收的 pitch，拒收名單為 `[]`。
現有 SQLite 亦有8筆 imported、0筆 rejected，原ID與內部ID各8個唯一值。
這是候選接收數，未將它解釋成8球已人工通過。

## 2. 兩次重跑與SQLite筆數

實際兩次執行同一命令，exit code皆為0（完整 ffprobe 路徑見 `import_and_sqlite.json`）：

```text
.venv-analysis/Scripts/python.exe -B scripts/import_handoff.py import --ffprobe <已安裝的ffprobe完整路徑>
兩次各自：imported_candidates=0, already_imported=8, rejected=0, conflicts=0
```

唯讀查詢：`SELECT COUNT(*) FROM batches/pitches/events`，以及各表的
`COUNT(DISTINCT original_batch_id/original_pitch_id)`。

| 時點 | batches | pitches | 唯一batch_id | 唯一pitch_id | imported | rejected | events |
|---|---:|---:|---:|---:|---:|---:|---:|
| 重跑前 | 1 | 8 | 1 | 8 | 8 | 0 | 27 |
| 重跑1後 | 1 | 8 | 1 | 8 | 8 | 0 | 36 |
| 重跑2後 | 1 | 8 | 1 | 8 | 8 | 0 | 45 |

每次9筆events是8球skip加1筆批次執行紀錄；沒有增加素材或身份列。
八個candidate目錄共40檔，兩次前後SHA與mtime完全一致。
實際stdout：`import_1.stdout.json`、`import_2.stdout.json`。

## 3. Phase 2 未受影響

### Git差異與例外

開始檢查時 `git status --short`、`git diff --stat`均無輸出；分支為
`codex/handoff-reader-v2...origin/codex/handoff-reader-v2`。
但是 **交付commit並非「只有新增檔案」**：對照 `7f0f9e6..5431161`，12個新增、4個既有文件修改。
修改逐一如下，沒有修改既有Phase 2程式或測試：

| 既有修改檔案 | 原因 |
|---|---|
| README.md | 增加讀取器說明入口，更新「尚未接入」的舊敘述。 |
| docs/INPUT_REQUIREMENTS.md | 一句交付狀態更新：新素材先是候選，正式使用須人工確認；影片需求與門檻不變。 |
| docs/STATUS.md | 記錄核准的候選範圍、實測、測試與尚待人工覆核；Phase 2仍NOT PASSED。 |
| docs/current_status.md | 保存新接入狀態、原Phase 2結果與新的待辦邊界，移除已過時的未接入描述。 |

本次核對另修正兩個交付第一版新增的檔案，並新增5項測試：

- `scripts/import_handoff.py`：人工覆核入口檢查整條本地candidate路徑。
- `src/pitch_analysis/handoff/review.py`：拒絕上層symlink／junction，驗證資料與項目後才建鎖，鎖內再次驗證。
- `tests/test_handoff_review_boundary.py`：真Windows junction與無效證據皆不得碰外部目標。

`git diff 7f0f9e6 -- src/pitch_analysis/analysis/pitch.py src/pitch_analysis/workflow.py src/pitch_analysis/pose_capture.py`
無輸出；原374份保護來源hash也全部相同。這個修正不改pose、tracking、threshold或smoothing。

### 全部測試

實際執行：`.venv-analysis/Scripts/python.exe -B .cache/rerun_full_suite_20261009.py`。
此runner以unittest discover執行全部tests並啟用正式五球E2E，保存原始log及JSON。

```text
tests_run = 309
passed = 307
failed = 0
errors = 0
skipped = 2
pre_handoff_existing_tests: run=240, passed=240
handoff_tests: run=69, passed=67
```

兩項既有檔案symlink案例因Windows無建立權限跳過；目錄junction案例與5項本次新案例實測通過。
完整結果：`full_test_suite.log`、`full_test_suite_result.json`。

### 正式五球重新執行

以正式 `input/yoshinobu_yamamoto/phase1_final` 從頭執行；新輸出根為
`analysis_results/handoff_regression_20261009_01/phase2_fresh/`：

```text
python -B scripts/run_real_baseline.py <正式五球> --output-root <fresh>/predictions
python -B scripts/run_phase2_reliability.py <正式五球> <fresh>
python -B scripts/evaluate_phase2_ground_truth.py <正式五球> <fresh> <fresh>/ground_truth_comparison.json
exit codes: 0, 0, 0
reviewed_count=5, pitch_count=5
```

原runner會生成blank GT及歷史pending摘要。本次保留blank模板，再逐byte複製既有HSU canonical GT
到新輸出供比較；未新增判讀，原GT與raw未改，沒有把pending歷史摘要當成現在的完成狀態。

| 正式pitch | 總格數 | valid pose ratio | pose可靠度（新／舊） | tracking（新／舊） | track break |
|---|---:|---:|---|---|---|
| pitch_001 | 87 | 1.0 | unreliable／相同 | reliable／相同 | 無 |
| pitch_002 | 175 | 1.0 | unreliable／相同 | reliable／相同 | 無 |
| pitch_003 | 115 | 1.0 | unreliable／相同 | reliable／相同 | 無 |
| pitch_004 | 114 | 0.9824561403508771 | unreliable／相同 | partially_reliable／相同 | 75–76 |
| pitch_005 | 101 | 0.9900990099009901 | unreliable／相同 | partially_reliable／相同 | 54 |

共592格；全部identity-switch warning仍false、confirmed仍null。
10份pose／tracking JSON逐欄位0差異，五球35份CSV／capture／keypoint／品質／metrics檔案逐byte相同。
只排除不同輸出路徑；沒有用寬鬆數值容差掩蓋差異。
原人工比較aggregate及逐pitch結果也0差異：重大失效TP3/FN18/FP9、jump診斷TP13/FN8/FP56。
這表示讀取器沒有造成回歸；**Phase 2 automatic reliability仍NOT PASSED**。

完整命令與stdout：`formal_commands.json`；比較：`formal_phase2_comparison.json`。

## 4. 八球候選狀態

共同batch前綴：`20261006T114959Z_Q8Bl2X4VKuw`。

| pitch_id尾碼 | 素材狀態 | 輸入人工覆核 | 人工history筆數 | 分析artifact數 | 正式五球清單內 |
|---|---|---|---:|---:|---|
| _p01 | candidate | pending | 0 | 0 | 否 |
| _p02 | candidate | pending | 0 | 0 | 否 |
| _p03 | candidate | pending | 0 | 0 | 否 |
| _p04 | candidate | pending | 0 | 0 | 否 |
| _p05 | candidate | pending | 0 | 0 | 否 |
| _p06 | candidate | pending | 0 | 0 | 否 |
| _p07 | candidate | pending | 0 | 0 | 否 |
| _p08 | candidate | pending | 0 | 0 | 否 |

每球只有source MP4／原JSON／provenance／timeline／review共5檔。
正式MP4仍5個、pitch_id仍pitch_001–005；新球影片hash亦未出現在正式集合。
另檢查本地9份registry JSON，八球原ID與內部ID的匹配數為0。
完整檔案／ID清單：`candidate_status.json`、`registry_candidate_check.json`。

## 5. 交付唯讀

原程式碼核對發現覆核入口的中間目錄junction可能把鎖定檔導向交付資料夾；本次已修正。
5項新測試確認拒絕時不呼叫recorder／lock，外部假目標的檔案列表、內容及mtime不變。
真交付資料夾前後21個檔案的SHA及mtime完全相同。

| 操作 | 程式位置與受限目的地 |
|---|---|
| 讀取交付 | reader.py `_source_file`、`read_bytes`、hash；timing.py OpenCV／ffprobe只讀取影片。 |
| 複製MP4／JSON | reader.py 239–240；目的地為本專案 `.staging` 的source。 |
| 寫證據、批次快照、SQLite、reports | reader.py `_local_path` 限定 `data/intake/`，且與handoff互不包含。 |
| 改名／清除暫存 | reader.py 251、254–259；僅本地staging→candidate或已核對的staging子目錄。 |
| 人工覆核鎖／原子替換 | review.py 214–240、255–269；整條本地candidate路徑與證據先驗證，無外部連結。 |

沒有以handoff為目的地的write、rename或delete操作；contract.py沒有檔案寫入。
source快照：`source_before.json`、`source_after_all_checks.json`。

## 回主線

已依原路線回到Phase 2的自動錯位警示缺口，整理既有五球592格的修復case index：
TP3/FN18/FP9/TN562；FN18全部為003的87–104格。
位置：`analysis_results/phase2_repair_start_20261009_01/case_index.json`。
具體接續範圍見 [Phase 2 repair checkpoint](phase2_reliability_repair_20261009.md)。
不讓八球待覆核候選進分析，不開始Phase 3，不改模型／門檻或人工GT。
