# 已保存原生骨架的2D動作曲線

此入口是Phase3的第一步，將人工接受的原生17點資料轉成可查看的逐格角度曲線。
大谷／山本的共用骨架方式保留，入口只讀已保存的資料，不執行人物偵測或pose推論。

```powershell
pitch-analysis describe-native-motion `
  analysis_results/phase2_native_analysis_input_20261023_01/bundles/supplement_001 `
  --output analysis_results/native_motion_NEW/supplement_001
```

輸出須為本專案`analysis_results/`中的新目錄；已存在目錄不覆寫。
來源改動或人工接受證據不吻合時，由既有原生資料loader拒絕處理。

## 如何看數值

| 曲線 | 原生三點 | 定義 |
|---|---|---|
| 投球肘 | 投球側肩／肘／腕 | 以肘為頂點的原圖XY夾角 |
| 前導膝 | 非投球側髖／膝／踝 | 以膝為頂點的原圖XY夾角 |

慣用手使用metadata的LEFT／RIGHT，不依球員姓名推定。原圖像素保留圖片長寬比例。
角度範圍0–180度；這是影像平面中兩條線段的夾角，並非人體真實3D屈曲角。
缺少任一點時留空；零長線段為退化幾何，亦留空。兩者分開計數。

## 輸出

- `motion_curves.csv`：完整逐格格號、秒數、兩個模型投影角、計算狀態與空的可用角度欄位。
- `motion_curves.png`：上下兩張曲線，藍色投球肘、橘色前導膝。
- `motion_summary.json`：原生資料入口／來源／人工接受SHA、角色對應、完整分母及產物SHA。

CSV關鍵欄位：

| 欄位 | 意義 |
|---|---|
| `frame_index` | 0起算的來源格號 |
| `timestamp_sec` | 格號／分數FPS，第0格=0秒 |
| `*_model_xy_deg` | 模型三點座標可計算的2D投影角；缺值／退化則空 |
| `*_coordinate_status` | calculated_from_model_xy／missing_coordinates／degenerate_geometry |
| `*_usable_deg` | 維持空值，尚未建立逐點可靠性，不自動當成品質通過角度 |
| `pointwise_reliability` | unknown |

每球以影片第0格為起點，沒有依投球啟動、落地或出手對齊；未讀取供片動作能量anchors。
資料與圖都不平滑、不補點、不重取樣。圖中只連接相鄰可計算點，missing保留斷線。

## 使用限制

整片骨架已人工接受，仍不等於每個點的可見性／精確度已量測。
被遮住的關節也可能有模型座標，快速運動、影像投影或定位誤差都可能影響曲線。
局部突變原樣保留；本輪沒有證據將它自動認作真實動作變化或錯點。

因此`model_xy_deg`用於描述、回看片段與後續研究；`usable_deg`／原輸入的usable_for_analysis
維持null，沒有新品質門檻、評分、臨床解讀、完整profile或跨投手比較。
Phase2自動可靠性NOT PASSED的歷史與限制保持；本入口不宣告Phase3整體通過。

既有輸出亦可用[`review-native-motion`](native_motion_viewer.md)建立影片／曲線連動頁，
以逐格、格號或點曲線回看片段。這是觀看工具，原CSV／PNG與角度計算保持。
大谷五球連動頁已獲HSU人工整體接受；山本啟用四球也已產生同套曲線與新觀看頁，操作確認待完成。
見[大谷交付](phase3_motion_sync_20261024.md)與[山本交付](phase3_yamamoto_native_motion_20261024.md)。
工具自動瀏覽器互動驗證未執行，沒有因此新增可靠性判定或人工GT。
