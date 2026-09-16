# Pitch Analysis 開發現況

更新日期：2026-09-16

## 目前可用成果

- 原始素材庫包含 5 位投手、13 支影片：Blake Snell、Shohei Ohtani、Tarik Skubal、Yoshinobu Yamamoto、Yu Darvish。
- 目前 canonical release 是 `data/pitcher_database/releases/v0.5/`；manifest 將 registry、scaler、驗證結果與重建紀錄綁定在同一版本。
- 嚴格 registry 目前收錄 5 位投手、12 次投球：Snell 5、Skubal 2、Ohtani 2、Darvish 2、Yamamoto 1。
- 切段品質 gate 與人工覆核後的 event-window gate 使用相同門檻。後者安全取回 2 球只在投球窗外品質不佳的素材；仍有 4 球因投球窗內覆蓋率不足而排除。
- 左投與右投分開建立 reference scaler，也只會與相同慣用手的投手比較。
- query 不再自行做 Min-Max；正規化只由 reference 資料擬合。
- 比較流程使用人工事件分期、每期重採樣與品質感知 DTW，可處理不同長度的動作。
- visibility、presence、原始偵測、短缺口插值與每項特徵覆蓋率都有獨立紀錄。
- 2-D 橫向座標已依影片寬高比校正；肩線與髖線角度使用 180 度週期處理。
- 長影片可輸出多個「動作候選窗」，但仍須人工確認，不能直接當成投球事件。

## 現在的測試影片

`test_pitch.mp4` 是右投。新版 Tasks API 資料共有 255 個有效影片時間軸 frame，其中 253 個有姿態偵測；兩個缺失 frame 都只有 1 frame 長，已依規則做短缺口補值。

整支影片含兩次投球與中間等待，因此全片投球手肘原始覆蓋率只有 37.65%。真正參與比較的第二球 160–225 幀內，手肘原始覆蓋率是 65.15%；跨步與加速期皆為 100%，隨揮期則只有 19.05%。比較器會在隨揮期排除不可靠的手肘特徵，但保留另外四項可靠特徵。

以原始比例影格目視確認後，這支影片屬於直式 `side_oblique_mobile`，不是 reference library 的 `rear_centerfield_broadcast`。因此目前正式的 camera-gated 結果是 `no_compatible_references`，不輸出投手排名。

先前跨視角得到的 Darvish 第一、Ohtani 第二已撤回為無效探索結果。若要得到有效排名，使用者影片必須改用投手丘正後方、與資料庫相容的鏡頭重新錄製。

## 資料庫內部留一投球驗證

每次保留一球作為未知 query，並只使用其餘 reference 重新擬合 scaler，避免測試球洩漏到正規化資料：

- 右投：5 球中 4 球可計分且第一名正確；Yamamoto 目前只有 1 球，留一後沒有同投手候選，因此列為 unscored。validation coverage 80%，已計分折的 Top-1 accuracy 100%、MRR 1.0。
- 左投：7 折中 7 折第一名正確，Top-1 accuracy 100%，MRR 1.0。
- 修正前 Darvish 2013 那球曾因手肘低覆蓋而連帶排除整個動作階段；改為只排除該低覆蓋特徵、保留其餘可靠特徵後辨識正確。
- Snell 有一折雖然第一名正確，但與 Skubal 距離非常接近，不能把 100% 解讀成已經具有泛化能力。

目前不依這些小樣本結果調整特徵權重，以避免對現有素材過度擬合。它們會作為後續增加 reference 後的固定比較基線。

## 八個工作面的狀態

| 工作面 | 狀態 | 尚需完成 |
|---|---|---|
| 素材收件與命名 | 已建立 | 新素材仍需記錄來源、賽季、慣用手與鏡頭 |
| 姿態品質控管 | 切段與 event-window gate 已建立 | 改善手肘遮擋與低覆蓋影片的處理 |
| 生物力學特徵 | 已校正第一版 | 2-D 指標不可解讀為真實 3-D 角度或距離 |
| smoothing | 已建立 | 以更多不同幀率影片驗證秒數參數 |
| 投球切段 | 候選功能完成 | 用更多長影片量測誤報與漏報 |
| 投球事件與分期 | 人工審核流程完成 | 自動事件只能做候選，尚不可取代人工標註 |
| temporal alignment / DTW | 已建立並完成 leakage-free 留一驗證 | 增加資料後再校準特徵權重 |
| 投手排名 | camera gate 與 provenance 檢查完成 | 每位投手至少 5 個人工確認且鏡頭相容的 reference |

## 下一個驗收門檻

1. 每位投手至少 5 次完整、人工確認、同類後方鏡頭的投球。
2. 每段 pose 偵測率至少 90%，核心特徵原始覆蓋率至少 80%，投球手肘至少 50%。
3. 明確確認影片沒有水平鏡像，並記錄投手全身是否完整入鏡。
4. 以留一投球測試確認同一投手能穩定排在前列，再調整特徵權重。
5. 左右投持續分開驗證；單一 reference 的投手不計入可計分折 accuracy。

目前所有排名都應標示為 `provisional`，直到以上門檻完成。
