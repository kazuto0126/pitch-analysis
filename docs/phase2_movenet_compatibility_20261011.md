# Phase 2：MoveNet 隔離相容性檢查

2026-10-11（台灣）。**隔離相容性第一關完成；Phase 2 = NOT PASSED。**

## 實際執行與結果

- 使用者「繼續」承接原先第一關提案；只授權隔離下載、安裝、contract 與合成圖檢查。
- Google MoveNet MultiPose Lightning TF2 v1，TensorFlow CPU 2.21.0、Python 3.12.14。
- 狀態：`compatible_synthetic_only`。合成圖推論嘗試 **1** 次；MoveNet 正式影片推論 **0** 次。
- 實際 signature：`input`：int32 `[1, None, None, 3]`；`output_0`：float32 `[1, 6, 56]`。
- SavedModel 載入 9.683582 秒；唯一一次首次推論與結果取回 1.083051 秒。這不是暖機後影片吞吐量。
- 保留全部六槽、每槽17個原生 `(y,x,score)`、box/instance score，以及未裁切的 source XY。
  合成圖沒有人，模型的六槽不能稱為六位偵測到的人。沒有新增身份、可見性、可靠性或解剖準確率判定。

## 全圖縮放與座標還原

固定全圖 RGB、bilinear resize_with_pad 256×256、antialias=false、batch1、int32。
實際完成6個非推論 fixture，每個保留四個彩色角落並核對9個邊界／中點。
已完成 fixture 的 padding 從實際 runtime 的全1遮罩量得，沒有猜測奇數尺寸的 rounding。

| 原圖 W×H | 縮放 W×H | padding 左/上/右/下 | 最大代數往返誤差 px |
| --- | --- | --- | --- |
| 1280×720 | 256×144 | 0/56/0/56 | 0 |
| 720×1280 | 144×256 | 56/0/56/0 | 0 |
| 1281×719 | 256×143 | 0/56/0/57 | 0 |
| 319×257 | 256×206 | 0/24/0/26 | 0 |
| 256×256 | 256×256 | 0/0/0/0 | 0 |
| 257×127 | 256×126 | 0/64/0/66 | 0 |

XY 明確採連續 pixel-edge `[0,width] × [0,height]`，不截斷框外座標。
已完成的往返檢查僅支持記錄的幾何逆轉換；不證明人體關節中心準確，縮小到256也會損失細節。

## 來源、授權與實際資源

- 固定官方 TFHub v1 handle 重新導向同版 Kaggle TF2 v1；archive **18,612,451 bytes**，
  SHA256 `f01b9e5e8c3bc31f82e9ca7fa4a2876f25d7a54b65c83da5df2eca3e1632cec8`；解開三個 SavedModel 檔各自綁定 SHA。
  這是本地完整性雜湊，官方沒有提供可核對的 archive 簽章／checksum。
- Apache-2.0 由[官方該模型版本文件](https://raw.githubusercontent.com/tensorflow/tfhub.dev/master/assets/docs/google/models/movenet/multipose/lightning/1.md)確認；
  已保存文件與授權全文並綁 SHA。該 master URL 可變，沒有宣稱它是 commit-pinned。
- **32** 個 runtime wheels 共 **405,678,583 bytes**，逐檔符合官方 PyPI SHA，
  以離線、require-hashes、no-deps、no-compile 安裝；另保留標準 ensurepip bootstrap pip 的來源與 SHA。
- 獨立環境 `.venv-movenet-compat-20261010/`，**33** 個 distributions（含 bootstrap pip），
  `pip check`：`No broken requirements found.`；不使用 system site-packages。
- 安裝清單 **17,302** 檔／**1,631,747,390 bytes**，
  **16,858** 個 RECORD SHA 核對；Python executable 和安裝檔在 gate 前後重新核對。
  這是 distributions 清單的實際檔案大小，不是整個環境／保留 partial downloads 的磁碟總占用。
- 10/10 初次 pip／大 range 下載未完成，未安裝；中斷紀錄與 partial 保留。
  自動核准服務用量限制恢復後，10/11 用1MiB ranges完成，已完成的檔案先驗 SHA 再重用。

## 回歸與保護範圍

完整 suite：**470 passed／0 failed／0 errors／2 skipped**，
472 項、69.675 秒，含正式五球的既有 MediaPipe E2E；15項新相容性／完整性回歸。
兩項跳過為 Windows file-symlink 限制；先前470項 suite log另存，未覆寫。

374份保護來源與62筆上游引用前後一致，差異0；正式五球、raw、5/5 reviewed GT、production src 未改。
原分析環境30個套件的名稱／版本／位置及3個 dependency files不變；未建立原環境全套件bytes的 before 快照，
因此不宣稱已逐bytes驗證該環境所有套件。八顆交付片維持 candidate／pending，未分析或升格。

## 停止點與下一步

MediaPipe 保持 baseline；沒有33點轉換、confidence互轉、新警示門檻、selector或插值／平滑修改。
原重大錯位 FN18 仍未修復，**Phase 2 = NOT PASSED**。相容性不代表可靠性提升。
本輪在相容性結果、commit／push 與乾淨 checkpoint 停止；不自動開始592格比較或 Phase3。
若要進行完整五球的模型比較，先另行封存只量測一次、保留原生17點、producer不讀GT的計畫。

輸出：`analysis_results/movenet_compatibility_20261010_01/`；本次 gate：`analysis_results/movenet_compatibility_20261010_01/gate_20261011_01/`。
[凍結 execution](evaluation_plans/phase2_movenet_compatibility_execution_20261011_01.json)；
[結果封存](evaluation_plans/phase2_movenet_compatibility_result_20261011_01.json)。
模型、wheels、環境與逐槽原始輸出保留本地 ignored 路徑，不把大型 runtime 放進 Git。
