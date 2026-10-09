# Phase 2：同模型 IMAGE／VIDEO 對照

2026-10-09。實驗只回答**輸出對 running mode 是否敏感**，不替換正式分析。

## 固定範圍

- 原正式五片、全部592格。保留原尺寸、原始像素與原時間軸；不裁切、放大或遮掉打者。
- 原 `pose_landmarker_full.task`、4個pose上限、三項0.5設定保持相同。
- 對照端使用已安裝MediaPipe的IMAGE `detect(image)`；原VIDEO結果保持原樣。
  不新增模型、下載、重新訓練或RTMPose。
- 每片另建原有PitcherSelector，不改實作或參數。它仍有時間狀態；
  因此不能把此實驗解讀為完全無狀態pipeline，或證明VIDEO某個內部機制造成錯位。
- 先保存每格所有33點候選，再保存原selector自行選取的結果；
  不把兩個模式的candidate index當成身份配對、不因拒選而改取人工答案最接近的候選。
- 原clean gate的visibility／presence只決定差異是否可量測，不代表點位正確。
  無候選、拒選、模糊選取與gate未通過都保留；沒有補點、平滑或座標修正。

## 量測與比較分開

`measure_pose_mode_countercheck.py`只讀原片、metadata、原raw/capture、clean設定與影片驗證紀錄。
完整原像素SHA、原小數PTS、capture整數毫秒、所有候選、selection及逐關節像素距離另存。
軀幹描述值為雙肩／雙髖四個距離的中位數，四點皆可量測才產生；缺點不補、不改分母。
相同模型的兩種模式即使一致，也不能證明抓對投手。

實作、runtime、模型、來源與參數先綁定在execution JSON；量測封存後，
`evaluate_pose_mode_countercheck.py`才讀五份已完成canonical GT及003的人工XY。
evaluator重算所有selection／差異，並逐格重新解碼核對原圖像素；不重新推論來挑較好的結果。

## 事前決定的報告

1. 每片及全部592格的候選數、selected／rejected／ambiguous、差異可量測分母與缺值原因。
2. 差異在原confirmed重大失效與其餘區段的分布、條件rank AUC；不確定標記獨立保留。
   這是已看過的development素材，不是holdout；AUC不是新警示召回率。
3. 六個重要關節逐片對照原overlay的人工reliable／unreliable，
   uncertain／not_observable不轉成錯誤或正常。原定性答案不是新IMAGE結果的準確性標籤。
4. 003全部1380個人工點、其中1205 visible：兩個模式各自可量測數、
   相同可量測集合與相同既有gate集合的mean／median／P95／max誤差；
   173 not_observable和2 uncertain不計位置誤差。
5. 003重大失效區段與其餘區段分開，12關節分開；
   不拿因缺點而不同的樣本平均宣稱改進、不推測不可見關節位置。

## 本轮停止條件與採用邊界

只跑這一個事前固定的模式對照，不根據結果追加裁切、調gate或挑frame。
執行失敗的部分輸出不能當完整實驗；保留失敗原因後只修資料／程式錯誤。
本輪不建立分類cutoff、不產生新警示、不將新座標送回正式分析。
原TP3／FN18／FP9／TN562保持原baseline數字；沒有新policy就沒有新TP／FN／FP。
即使003有改善，仍須核對是否能為錯位警示提供足夠證據，不能直接標Phase 2 PASSED。

原五球、人工GT、raw與核心來源SHA持續保護。交付八球保持candidate／pending；
不跑它們的分析，不進Phase 3。
