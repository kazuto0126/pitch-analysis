# pitch-analysis

接收已整理好的 **單次投球 MP4 + metadata**，分析 MLB 投手的姿勢、動作時序與特徵。
長期目標包括單一投手 motion profile，以及不同投手的完整時序比較。

本次收尾摘要見 [STATUS](docs/STATUS.md)；外部專案供片需求見
[INPUT_REQUIREMENTS](docs/INPUT_REQUIREMENTS.md)。

2026-10-26 最新：[事件角度讀值已接入正式報告](docs/phase3_event_readout_integration_20261026.md)。
原事件比較指令會自動輸出單格／多格／未確認讀值、窗內跨度與缺失／退化數量，另附每球10列CSV。
大谷5球、山本啟用4球已產生新版報告；既有720個視窗欄位與36段時距保持，骨架與GT不改。
完整suite **1249 passed／0 failed／2 skipped**（含正式五球E2E），純Node **11 passed**。

前段：[人工事件範圍與模型角度讀值](docs/phase3_event_angle_readout_20261026.md)。
45筆事件形成90個關節視窗：60個單格敏感度留空、24個多格保留min–max／跨度、6個事件未確認保持空值。
附來源格號、完整CSV與分投手圖表；跨度只描述模型XY讀值，沒有轉成可靠性分數。
本輪無產品／測試碼變更，未重跑suite；最近相同程式碼1241 passed／0 failed／2 skipped。

前段：[可攜式成果包](docs/phase3_portable_review_20261026.md)。
大谷5球、山本啟用4球共2161格的原片／overlay、曲線、人工事件與觀看頁已整理為約32.4 MiB ZIP。
完整解壓後以Chrome／Edge開啟`START_HERE.html`即可使用；原檔與標註保持，沒有新增分析或模型。
包內136檔、79個本機連結已檢查；無產品／測試碼變更，未重跑suite。

前段：[山本四球保留落地範圍的曲線比較](docs/phase3_yamamoto_anchor_bounds_20261025.md)。
001／004的兩個可能原點全部保留，與精確原點的002／005共同查看；四球477列原資料未改。
新增可選`--retain-anchor-ranges`，候選平移不當成新增觀測、不選中點或給機率，原精確模式保持。
[來源與測試紀錄](docs/dataset_selections/phase3_yamamoto_anchor_bounds_20261025.json)。
完整suite **1241 passed／0 failed／2 skipped**，含正式五球E2E。

前段：[山本精確落地對齊與共同觀看入口](docs/phase3_yamamoto_exact_alignment_20261025.md)。
沿用同一套工具完成山本002／005共276格的疊圖與回看頁；001／004保留落地範圍，啟用素材仍為四球。
共同入口可分別開啟山本兩球對齊、山本四球事件與大谷五球對齊頁；沒有跨投手比較。
無產品／測試碼變更，未重跑suite；最近相同程式碼1231 passed／0 failed／2 skipped。

前段：[大谷五球可點選對照頁](docs/phase3_ohtani_alignment_viewer_20261025.md)。
點選落地對齊曲線即可回看該球最近的原片影格，跨球切換等待目標來源載入；原播放器JS保持。
1684格時間映射與3368個肘／膝角度核對完成，曲線保留缺值斷線與人工出手區間。
實際瀏覽器操作尚待確認；本輪沒有新增人工接受紀錄。
完整suite **1231 passed／0 failed／2 skipped**；另新增5項純Node互動邏輯測試通過。

前段：[大谷五球落地對齊曲線](docs/phase3_ohtani_foot_plant_alignment_20261025.md)。
五球皆以人工確認落地格為0秒，投球肘／前導膝各一張疊圖，附落地附近放大與人工出手區間。
新增`align-native-motion`；1684列原欄位逐格比對差異0，只增加分數FPS換算的相對格號與時間。
新入口沿用既有來源校驗，完整保留原樣本、角度、缺值與人工範圍；完整suite **1223 passed／0 failed／2 skipped**。

前段：[大谷五球事件畫面與角度解讀](docs/phase3_ohtani_event_readout_20261025.md)。
25筆事件內的31格全部匯出，原片／既有骨架共62張圖、5張事件對照圖，附肘／膝模型角度表。
保留範圍與逐球差異，說明落地近0°的XY肘角不能當作人體屈曲角；原資料與算法不變。
本輪無產品／測試碼變更，未重跑suite；最近相同程式碼1212 passed／0 failed／2 skipped。

前段：[大谷五球事件與曲線對照已交付](docs/phase3_ohtani_event_timing_20261025.md)。
沿用已接受骨架與1684格曲線，25筆人工事件產生20筆時距（14精確／6範圍），附觀看頁、CSV與總覽圖。
新增對已完成事件覆核紀錄的讀取；完整GT仍in_progress，不補填其他欄位、不重跑骨架。
完整測試加8項環境跳過案例補跑，合計 **1212 passed／0 failed／2 skipped**；512份保護檔案未變。
[使用方式](docs/native_motion_events.md)。下一步可直接查看五球事件／曲線對照。

前段：[大谷五球人工事件覆核完成](docs/phase3_ohtani_event_review_20261024.md)。
HSU已完成五球各五事件，事件覆核5/5：共25筆，21筆精確影格、4筆影格範圍，範圍原樣保留。
最後一支004為39／71／124／129／180；概覽啟動40、收尾192已依人工回答修正，其他四球紀錄保留。
格式、來源、影格界限及事件順序檢查完成；完整GT仍為in_progress，未覆核的非事件欄位仍為null。
本輪無產品／測試碼變更，未重跑suite；最近相同程式碼1201 passed／0 failed／2 skipped。
事件接入已於上方最新交付完成，不需再次標這25筆事件。

前段：[山本四球時距圖與解讀摘要](docs/phase3_yamamoto_timing_readout_20261024.md)。
只讀前輪16筆事件時距，新增可匯出PNG與24筆逐球區間關係；保留不能比較的8筆配對。
最高抬腿→落地的三球可用範圍相互重疊；002落地→出手範圍與001／004分開，不作優劣評分。
本輪無產品／測試碼變更，未重跑suite；最近同程式碼結果1201 passed／0 failed／2 skipped。
該輪大谷尚缺已確認人工事件；現已完成，見上方最新紀錄。

前段：[山本四球人工事件與時序對照](docs/phase3_yamamoto_event_timing_20261024.md)。
新增`compare-native-motion-events`，沿用既有曲線與已標事件；477格、20筆事件完整保留。
精確影格用線、範圍用色帶、不確定用虛線；16筆時距13筆可界定、3筆因人工不確定／不可觀測留空。
來源SHA與時間軸綁定，原骨架／曲線／GT及已接受觀看頁保持，新增模型推論與標註皆0。
[使用方式與區間定義](docs/native_motion_events.md)。未做精確出手對齊、跨投手比較或評分。
完整suite **1201 passed／0 failed／2 skipped**，另5項純Node測試及18項事件helper斷言全過。

前段：[山本四支啟用影片的曲線與連動頁](docs/phase3_yamamoto_native_motion_20261024.md)。
沿用現有工具及已接受骨架，001／002／004／005共477格、954個模型2D投影角，003仍為歷史對照。
四支CSV、PNG、來源摘要與連動頁已生成；新推論、tracking replay、GT及產品碼變更皆0。
HSU回覆「都正確一樣是5表現最好」，山本四支觀看頁已獲人工整體接受4/4，005記為偏好示範。
連同大谷五支，九支觀看結果皆已接受；兩位投手的骨架方式保持。
本輪未重跑suite；相同程式碼最近1182 passed／0 failed／2 skipped，另5項Node測試全過。
2D投影、逐點unknown／usable null及Phase2自動可靠性NOT PASSED限制保留，未做跨投手比較。

前段：[大谷影片／曲線連動頁](docs/phase3_motion_sync_20261024.md)。
新增`review-native-motion`，可播放時同步游標與角度，並用逐格、格號、滑桿或點曲線跳轉。
直接讀取五球既有角度與overlay，共1684格，骨架方式與曲線數值保持。
HSU已回覆「都正確尤其是5最完美」，五球觀看頁已獲人工整體接受，005記為示範樣本。
狀態為**HUMAN ACCEPTED（5/5）**；工具自動瀏覽器檢查仍未執行，未新增逐點GT。
[操作方式](docs/native_motion_viewer.md)。同程式碼最近完整Python suite **1182 passed／0 failed／2 skipped**；另5項Node測試全過，本次未重跑。

前段：[Phase3第一步：大谷五球2D投影角度曲線](docs/phase3_ohtani_native_motion_20261024.md)。
依使用者授權，在獨立分支保留現有骨架模式，新增`describe-native-motion`，直接讀取已保存的原生17點。
五球1684格的投球肘／前導膝曲線、CSV、來源JSON及簡單觀看頁已完成，新增模型推論0。
曲線是未校準的模型XY投影，保留缺值與突變；未做事件對齊、評分或跨投手比較。
完整suite **1176 passed／0 failed／2 skipped**。Phase2自動可靠性NOT PASSED紀錄保留。
[使用方式](docs/native_motion.md)。

前段：[啟用九片人工覆核與資料交付已收尾](docs/phase2_active_cohort_closeout_20261024.md)。
HSU已接受山本001／002／004／005的新骨架；四片477格的資料入口與描述報告補齊，未重跑模型。
連同大谷五片，九片2161格皆已人工接受並完成接入。003保持歷史對照。
本輪無產品／測試碼變更；同程式碼最近完整suite1163 passed／0 failed／2 skipped。
人工輔助交付COMPLETE；原自動可靠性驗收仍NOT PASSED，未進Phase3。

前段：[原生逐關節與追蹤連續性報告已完成](docs/native_reliability_results_20261024.md)。
新增`report-native-reliability`，從已接受的資料入口產生17點缺值／相鄰位移、左右影像順序、
人物框及雙髖／軀幹連續性，附完整格號／時間，可直接回看overlay。
大谷五球1684格／28628關節影格報告已生成，原資料差異0、推論0。
完整suite **1163 passed／0 failed／2 skipped**；自動逐點可靠性仍未通過，未進Phase3。
[操作與計算定義](docs/native_reliability.md)。

前段：[原生骨架分析資料入口已完成](docs/native_analysis_input_results_20261023.md)。
新增`prepare-analysis-input`及Python loader，直接讀取已接受RTMPose17點、追蹤與人工紀錄。
大谷五球1684格／28628關節影格已由實際CLI＋loader讀取，原影格／追蹤差異0、模型重跑0。
保留原生座標、分數及missing；影片人工接受與逐點unknown分開，舊33點特徵入口保留相容。
完整suite **1153 passed／0 failed／2 skipped**；**Native analysis input integration = PASSED，Phase2自動可靠性仍NOT PASSED**。
[使用方式](docs/native_analysis_input.md)。本輪已收尾，未進Phase3。

前段：[大谷五球共用骨架已補齊](docs/ohtani_shared_skeleton_rollout_20261023.md)。
沿用HSU已接受的方法，001／003／004／005各處理一次，共1363格，整格missing0、幾何track break0；
002保留已接受321格結果，未重跑。已實看35組比較，005/128舊混合骨架與003/158舊手臂偏移有改善。
HSU已回覆「可以都正確」，連同先前002，五球overlay人工接受完成5/5；原話及來源SHA另存獨立review。
原片與舊結果保留，未改模型／門檻／GT或進Phase3。
本輪僅設定／資料／文件，未重跑suite；同程式碼最新完整suite1139 passed／0 failed／2 skipped。
本機觀看：`analysis_results/phase2_ohtani_seeded_skeleton_20261023_01/review_all.html`。

前段：[共用骨架流程已採用，山本五片已處理](docs/standard_skeleton_rollout_20261023.md)。
HSU完整觀看大谷第2球後確認整體骨架對位，要求山本與後續投手使用同一標準。
**新骨架統一使用人工指定起始投手＋人物框連續追蹤＋RTMPose原生17點**；
正式入口為 `prepare-skeleton` → 人工確認首格框 → `extract-skeleton`，
[使用方法](docs/standard_skeleton_workflow.md)。舊33點特徵／品質流程保留相容。
山本五片各執行一次，87/175/115/114/101格、合計592格；整格missing 0、幾何track break 0。
003仍僅歷史對照。既有003可見人工XY同點平均誤差 22.21→10.11px，
87–104歷史重大錯位段 76.90→10.50px；不是新的遮擋GT或自動可靠性通過證明。
完整suite1139 passed／0 failed／2 skipped。原影片、raw與GT保留；Phase2自動可靠性仍NOT PASSED。
本機觀看：`analysis_results/phase2_yamamoto_seeded_skeleton_20261023_01/review_all.html`。

前段：[人工初始化追蹤的106格續跑完成](docs/phase2_seeded_resume_results_20261023.md)：
只執行第215–320格；前215格逐值不變，合計319新pose＋2格cache＝321格原生座標。
紀錄改為各筆獨立新檔，本次無中斷；0新detector／0追蹤replay，672保護檔案不變。
實看25組對照，完整suite1126 passed／0 failed／2 skipped；正式核心／門檻／GT保持。
座標完整度不代表關節可靠性，未正式採用，Phase2仍NOT PASSED。本輪完成後停止。
本機觀看：`analysis_results/phase2_seeded_resume_native_20261023_01/review_all.html`。

前段：[人工初始化追蹤的部分結果已保存](docs/phase2_seeded_native_track_results_20261021.md)：
HSU指定1號框；321格保存框關聯完成，0新detector，213新pose＋193／194兩格重用。
Windows執行紀錄替換錯誤使pose在214格後停止；後106格未執行，保留missing，未補跑。
22組對照中準備段舊手臂線回到投手附近；完整推論未完成，不正式採用，Phase2仍NOT PASSED。
完整suite1115 passed／0 failed／2 skipped，615保護檔案不變。
本機觀看：`analysis_results/phase2_seeded_track_native_20261021_01/review_all.html`。本輪停止。

前段：[單球人物框修正已完成，政策不採用](docs/phase2_person_box_native_results_20261021.md)：
第2球321次人物偵測、2次pose；319格多框歧義導致missing，不能視為可靠性改善。
完整suite1091 passed／0 failed／2 skipped，正式核心／門檻／raw／GT保持；Phase2仍NOT PASSED。
本輪依核准方案停止，不追加規則或擴跑。本機觀看：`analysis_results/phase2_person_box_native_20261021_01/review_all.html`。

前段：[可選 live RTMPose 入口已交付](docs/phase2_live_native_pose_results_20261021.md)：
五球1684格各推論一次，提供原生17點與五支完整overlay；正式MediaPipe／核心／門檻保持。
部分舊錯例回到投手附近，但第2球準備段、第5球第128格仍有混合骨架，尚未校準或正式採用。
完整suite1055 passed／0 failed／2 skipped；**Phase2自動可靠性仍NOT PASSED**。
[使用方式](docs/phase2_live_native_pose_usage.md)；本機觀看入口：`analysis_results/phase2_ohtani_live_native_20261020_01/review_all.html`。

前段：[新大谷補片五球分析完成](docs/phase2_ohtani_supplement_results_20261020.md)：
人工輸入覆核5/5與新來源操作框已確認，五球各跑一次；選中1599/1684，肘角raw coverage皆≥50%。
仍因長缺口／前導膝角不足而5 degraded，另保留p02／p05混合骨架錯例；Phase2仍NOT PASSED。
原片與overlay觀看入口：`analysis_results/phase2_ohtani_supplement_20261020_01/review_all.html`。

前段：[剩餘缺失復原處理已記錄](docs/phase2_ohtani_remaining_limits_20261020.md)：
003／004主因右腕低visibility，未找到資料鏈bug；004／005的23格補偵測只找回5格，長gap未縮短，未接入正式流程。
保留原門檻與degraded結果，後續需較可觀測素材或明確核准新的模型資訊範圍；未進Phase3。

前段：[大谷五球固定裁切試用已完成](docs/phase2_ohtani_crop_cohort_20261019.md)：
001–004各跑一次、005沿用，五球選中1448→1842/1873，missing425→31；001／002通過原pose gate。
003／004肘角coverage、005收尾缺口仍保留，Phase2自動可靠性未通過；本輪未改產品碼或重跑suite。

前段：[大谷第5球輸入裁切有實際改善](docs/phase2_ohtani_p05_crop_20261019.md)：
選中215→338/353格，missing138→15；原錯人畫面回到投手，但13格收尾缺口仍使原gate未通過。
可選`input_crop`保存native及原圖座標，預設流程不變；完整suite1016 passed／0 failed／2 skipped。

前段：[可選投手範圍修正已交付](docs/phase2_pitcher_lock_results_20261019.md)，
部分錯人例子已排除或改選投手，但仍有混合手臂及更多missing，五球仍degraded。
完整測試999 passed／0 failed／2 skipped（1001項）；未指定範圍時保持原預設。

前段：[大谷翔平五球初次小量試用](docs/phase2_ohtani_pilot_results_20261019.md)：五球均 degraded，0 執行異常。
山本 `pitch_003` 退出後續試用集合，原影片、人工標註與五球歷史評估保留。
人工輸入覆核5/5完成；實際overlay抽樣發現第2球部分追到打者、第5球多處追到裁判／打者。
已保存完整結果與錯例；Phase 2 原自動可靠性未通過的結論保持，尚未進 Phase 3。

專案不負責影片搜尋、YouTube、下載、yt-dlp、來源管理、從長影片建立素材或指定球員 ReID。
這些能力由獨立 preprocessing 專案負責。本機 MP4 probe / validation / working-copy
standardization 屬於分析輸入品質控制，仍保留在本專案。

## Phase 0 已完成的入口

`analyze-pitch <mp4> <metadata.json>` 驗證整支影片，沿用現有 MediaPipe、confidence gate、
clean pose、2D feature 與 quality gate，輸出待人工覆核的單球結果。
Phase 0 沒有新增自動事件偵測、投手追蹤、profile 或 overlay；既有 phase、DTW、normalization、
registry 與 validation 演算法保留。現在的結果仍是 2D 投影分析，不能解讀為真實 3D biomechanical loading。

## Phase 1.1：單球 input quality gate

目前 `analyze-pitch` 僅接受 `rear_centerfield_broadcast`。它會在多人體姿態中以
畫面位置、身體尺度與時間連續性保守選取投手，並輸出逐幀原始／處理後 keypoints、
品質摘要、2D 投手手腕軌跡、`overlay.mp4` 與獨立人工檢查表。這不是球員身分 ReID；
視角與完整投球仍須目視核對。2026-09-24 完成正式五支山本由伸素材的 Phase 1
finalization，五支均通過現有 clip-level acceptance 條件；正式狀態與輸出見
[Current status](docs/current_status.md)。先前失敗素材的歷史紀錄見
[Phase 1 baseline](docs/phase1_baseline.md)。

## Phase 2：投手追蹤與姿態可靠度

正式五支山本由伸單球作為第一個 baseline dataset。Phase 2 在獨立分支上新增
逐關節 observed／interpolated／missing 狀態、關節覆蓋率與跳動檢查，以及
投手骨架的 ROI、中心、尺度、動作連續性和 track-break 警示。原有 MediaPipe
推論經共用 `PoseEstimator` 介面執行，未更換模型或修改選取門檻。
HSU 已完成五支影片的逐格定性覆核，並完成與既有可靠性警示的
[比較報告](docs/phase2_ground_truth_comparison_20261004.md)。比較顯示骨架缺失能被抓到，
仍有重大錯位及局部誤連未被可靠提示。已收到 Tsai 的手動 X/Y 回傳，
HSU 已完成 `pitch_003` 全115格12關節覆核，並提供2026-10-05 10:14（台灣）完成時間。
[座標比較報告](docs/phase2_manual_coordinate_comparison_20261005.md)已量測1,205個可見人工點的raw 2D誤差；173個不可觀測點與2個不確定點排除。
87–104格整體偏移的平均誤差為76.90px，高visibility仍可能錯位；事件偵測誤差尚未量測。
[錯位診斷](docs/phase2_pitch003_diagnosis_20261006.md)確認誤差已存在於raw模型輸出，
現有tracking連續性警示漏掉該18格；插值與平滑未修正這段偏移。
診斷包含人工／raw／processed對照圖，未改演算法或門檻。
[警示設計與驗證清單](docs/phase2_warning_design_20261006.md)已固定五支592格及14個已知案例，
[離線影像／幾何實驗](docs/phase2_image_geometry_experiment_20261006.md)已完成五支量測及人工參考比較。
逐格移動差異提供錯位線索，但影像特徵會漂離投手、手臂證據跨片不一致；尚未實作新警示。
[特徵支援驗證](docs/phase2_feature_support_validation_20261006.md)進一步以003人工肩／髖座標核對，
低往返誤差仍無法保證特徵留在可見軀幹；該範圍也不等於完整身體輪廓或身分真值。
[八點人工特徵覆核與下一步方案](docs/phase2_subject_support_proposal_20261006.md)已完成局部對照：
HSU確認003兩格中6點屬其他人／背景、2點屬投手其他部位；小往返誤差仍不保證抓對投手。
Phase 2 baseline與本次有限修復已收尾：**evaluation = COMPLETE WITH KNOWN LIMITATIONS；自動可靠性 = NOT PASSED**。
前次結果見 [Phase 2收尾](docs/phase2_closeout_20261013.md)：五球人工覆核／可用性已重核，
離線警示聯集major TP20/FN1/FP9，尚未正式採用；完整測試619 passed、2 skipped。
原正式流程與局部肘腕限制仍保留；沒有開始Phase3。
使用者隨後要求繼續，[六關節局部警示試驗](docs/phase2_local_joint_warnings_results_20261013.md)
已完成並維持不採用：肘腕涵蓋不足，局部定性GT與可見人工XY的評估用途需分開；完整測試648 passed、2 skipped。
[人工參考校準](docs/phase2_supervised_joint_reference_results_20261013.md)完成五球交叉驗證，
肘 TP/FN/FP 為8/76/1、腕8/63/1；有有限增益，漏報仍多、未正式採用，Phase 2仍NOT PASSED。
完整測試669 passed、0 failed、2 skipped，包含正式五球E2E；正式核心、raw與GT保持原樣。
最新[人工座標角度評估](docs/phase2_manual_angle_assessment_results_20261014.md)補上003的數值誤差：
processed肘50可比格MAE25.0452°、膝106格MAE7.1532°，遮擋不補角度；其他四球未套用這些數字。
定性eligible不代表數值準確；[肢體鏈幾何試驗](docs/phase2_chain_reliability_results_20261014.md)0新增TP、不採用。
續行的[角度差異診斷](docs/phase2_angle_reference_gaps_results_20261014.md)確認003全115格原影片／封存影像／人工圖與XML來源一致，
並保存50肘／106膝共同可比格的三點誤差分解、ray方向與局部敏感度。69／105格腕位移約47／91px已存在於raw；
沒有修改座標、人工GT、門檻或正式核心。
最新[封存ROI角度比較](docs/phase2_saved_roi_angles_results_20261014.md)以同格比較取得局部增益：
VIDEO raw→ROI肘41共同格MAE23.8410°→11.2361°、膝95格7.2015°→4.6703°，同時保留18／40格變差與coverage損失。
ROI需人工初始化，未正式採用。
最新[ROI角度轉換與整合決策](docs/phase2_roi_decision_results_20261015.md)保存690列完整缺值／退步清單，
確認7個同模式有人工參考的新流失皆仍在crop內且低於原gate；角度與逐點誤差亦可能不同方向。
現有固定窄ROI正式不採用；[2×輸入範圍實測](docs/phase2_expanded_roi_results_20261015.md)已完成五球592格，亦不採用。
擴框 selected 550/587（窄框552、全圖IMAGE555）；003共同格肘／膝角度誤差比窄框增加，恢復coverage不代表修正錯位。
Phase 2約定的評估與本次有限修復已交付，停止追加倍率／小規則實驗；自動可靠性仍NOT PASSED，保留已知限制。
2026-10-16 已依授權提供[重大錯位覆核提示](docs/phase2_major_review_hints_20261016.md)：
`analyze-pitch` 新增 `major_review_hints.json`，五球非seed提示2/0/19/5/3，維持major TP20/FN1/FP9。
只適用SHA吻合的封存來源／預測；其他輸入明列未評估，沒有提示不代表可靠，003/104漏報保留。
[肘腕判斷器單次結果](docs/phase2_joint_quality_classifier_results_20261016.md)已完成核准的整片五折：
肘TP/FN/FP為13/71/13、腕20/51/24，兩者皆未達事先規則，不採用，停止調整這組訊號。
兩步授權工作已交付；剩餘缺口記為需要更好的影像或模型資訊，Phase2自動可靠性仍NOT PASSED。
該輪完整測試842 passed、0 failed、2 skipped（844項，含正式五球E2E）；未進Phase3，原核心、門檻與GT維持。
使用者隨後核准的[單次Heavy新資訊試驗](docs/phase2_heavy_information_results_20261016.md)已完成：
肘TP/FN/FP為2/82/1、腕2/69/1，原gate通過錯點只抓回1／2，兩者皆不採用。
正式Full維持，沒有降低門檻、改座標或重訓原分類器；依固定規則停止本輪，Phase2仍NOT PASSED。
該輪完整測試882 passed、0 failed、2 skipped（884項）；新模型對照並不等於自動可靠性通過。
2026-10-17完成使用者核准的[RTMPose原生回應單次試驗](docs/phase2_rtmpose_response_results_20261017.md)：
五球592格與整片五折，肘TP/FN/FP為0/84/4、腕3/68/1，皆未達固定採用規則，停止此訊號。
003可見XY平均誤差有所下降，但自動識別原錯點仍不足；沒有更換正式MediaPipe或修改GT／門檻。
該輪完整測試916 passed、0 failed、2 skipped（918項，含正式五球E2E）；Phase2仍NOT PASSED，未進Phase3。
後續[封存座標診斷](docs/phase2_rtmpose_coordinate_diagnosis_20261017.md)完成003全部十二關節／1,380列：
全片平均均改善，但左右髖多數格退步，major hold外平均誤差也增加；不能直接換正式後端。
原回應訊號維持不採用，沒有新增RTMPose推論、重校準或修改GT；該輪完整suite916 passed、2 skipped。
使用者已核准並完成[原生後端輸出接入第一版](docs/phase2_rtmpose_native_interface_results_20261018.md)：
兩後端各完整592格、原生17／33點、五支新RTMPose overlay及獨立比較，原core／gate／raw／GT保持。
**Native interface integration = PASSED；Phase2自動可靠性仍NOT PASSED**。這是cached接入，不是live模型替換。
最新完整suite **961 passed、0 failed、2 skipped**（963項，含正式五球E2E）；新RTMPose推論／校準／標註0，未進Phase3。
使用者另核准的 [交付資料夾候選讀取器](docs/handoff_reader.md) 已接入 contract v2：
驗 hash、完整解碼、分數 FPS 逐格時間與去重，保存本地待人工覆核候選。
它不自動分析、轉換正式 metadata 或取代山本正式五球，也不改 Phase 2 核心。
詳見 [Phase 2 reliability](docs/phase2_reliability.md) 與
[manual ground truth](docs/phase2_ground_truth.md)。

目前 HSU 已完成 5/5 逐格定性覆核。`pitch_005` 除已記錄的問題外，
HSU 另確認其餘右肩／肘／腕及左髖／膝／踝皆可見且大致對位；
準備啟動與最高抬腿事件仍標為 uncertain。另提供可離線分享的
[同學獨立覆核流程](docs/phase2_peer_review.md)：`pitch_003` 完整覆核、
`pitch_005` 事件補充。回覆沿用相同 ground truth 格式，按 reviewer 分開保存。

2026-10-04 確認同學任務改為 [手動骨架座標標註](docs/phase2_manual_keypoints.md)：
用 CVAT 在 `pitch_003` 原始逐格圖上標 12 個身體關節，另補 `pitch_003`／`pitch_005`
事件。人工 X/Y 與可見性另存，可量化既有 AI 的逐關節位置誤差；不自動更新模型。
同學可直接下載 [GitHub 人工骨架標註 ZIP](https://github.com/kazuto0126/pitch-analysis/releases/download/phase2-manual-pose-review-20261004-01/manual_pose_package_20261004_01.zip)，
解壓後閱讀 `START_HERE.md`；不需要 clone 專案。

目前已確認的人工座標、遮擋狀態與下一次覆核入口見
[2026-10-05 人工覆核 checkpoint](docs/phase2_manual_review_checkpoint_20261005.md)。

`validate-input-quality <mp4> <metadata.json>` 先做影片層的保守檢查；
`analyze-pitch` 會在姿態推論前執行同樣 preflight。明顯切鏡標記 `rejected`，
不執行後續 pose；其他素材執行原有 pipeline 後，將主體遺失、疑似 identity switch、
準備／follow-through 完整性與現有 pose quality gate 更新至 `input_quality.json`。
`accepted` 仍需人工確認視角、投手身分及是否為正常速度單球；`degraded` 不可
直接納入 reference。規則、證據限制與人工檢查項目見
[Input Quality Gate](docs/phase1_1_input_quality.md)。

## 安裝（Windows x64 / Python 3.12）

從專案根目錄執行：

```powershell
.\scripts\setup.ps1
```

預設用 `py -3.12` 建立 `.venv-analysis`。若沒有 Python launcher，指定可用的 Python 3.12：

```powershell
.\scripts\setup.ps1 -PythonExe "C:\path\to\Python312\python.exe"
```

腳本安裝 `requirements-lock.txt` 的全部固定版本，再以 editable mode 安裝本專案。
不需要手動設定 PYTHONPATH，也不需要啟用環境。舊 `.venv` 保留作歷史資料，不再作執行入口。
只安裝 `opencv-contrib-python`，避免兩個套件同時提供 cv2。FFmpeg 由 imageio-ffmpeg 提供。

## 輸入與使用

```text
input/
  shohei_ohtani/
    pitch_001.mp4
    pitch_001.json
  yoshinobu_yamamoto/
    pitch_001.mp4
    pitch_001.json
```

複製 [metadata 範例](examples/pitch_001.json) 到 MP4 旁，再填寫真實投手與影片資訊。
每支檔案應是一個正常速度、未鏡像、連續鏡頭、全身入鏡的投球。
這些內容宣告仍需人工確認；驗證器不會辨識球員身分或計算影片內投球次數。

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe validate-pitch input/shohei_ohtani/pitch_001.mp4 input/shohei_ohtani/pitch_001.json
.\.venv-analysis\Scripts\pitch-analysis.exe validate-input-quality input/shohei_ohtani/pitch_001.mp4 input/shohei_ohtani/pitch_001.json --output analysis_results/input_quality_review.json
.\.venv-analysis\Scripts\pitch-analysis.exe analyze-pitch input/shohei_ohtani/pitch_001.mp4 input/shohei_ohtani/pitch_001.json
```

可加 `--output-root PATH` 選擇新輸出位置，或 `--model PATH` 指定本機 Pose Landmarker 模型。
預設模型為專案根目錄下 `models/pose_landmarker_full.task`。
`--standardize` 可建立 H.264/yuv420p 工作副本，保留原始 FPS、解析度與 frame count。
不會降為固定 30 FPS、不會切段、不會修改原始 MP4。Phase 0 接受 CFR；不支援 VFR、
帶 rotation metadata 或非正方形像素的影片。完整規則見 [contracts](docs/phase0_contracts.md)。

```text
analysis_results/<pitcher_id>/<pitch_id>/
  analysis.json             # 執行狀態、版本、hash、輸出索引
  input_manifest.json       # 原始 input metadata 快照
  video_metadata.json       # 整支 decode/probe/時間軸
  input_quality_preflight.json # pose 前的影片品質判定
  input_quality.json        # 最終 input 品質；明顯切鏡時與 preflight 相同
  keypoints.json            # 每幀位置、confidence、presence
  metrics.json              # 既有 2D 特徵摘要與原始 coverage
  phases.json               # Phase 0 待覆核事件快照，沒有偽造事件
  events.json               # 現有流程的人工標註入口
  pose_raw.csv
  pose_raw.capture.json
  pose_clean.csv
  pose_clean.clean.json
  features.csv
  features.quality.json
  metadata.json             # 舊分析流程 metadata，與 input metadata 不同
```

若 preflight 已拒絕，保留 input manifest、video metadata、品質報告與
`analysis.json`，不執行 pose、不產生 keypoints/overlay。無 pose 時保留 raw capture、
keypoints、metrics 與失敗狀態，不建立事件檔。
輸出目錄存在時拒絕覆寫。品質不足會回報 `quality_gate_failed`；不會自動成為 reference。

## 事件覆核與既有分析 handoff

人工檢查姿態與五個事件，在 `events.json` 填入從 0 開始的 clip frame index，
確認後設 `review_status=human_reviewed`，再執行：

```powershell
.\.venv-analysis\Scripts\pitch-analysis.exe revalidate-segment analysis_results/shohei_ohtani/pitch_001
.\.venv-analysis\Scripts\pitch-analysis.exe build-registry analysis_results analysis_results/registry.json
```

以上保留事件順序、原始 coverage、event-window quality gate 與 registry 設計。
`phases.json` 等新契約檔是首次 preparation 快照；舊 revalidate 指令不會更新這些快照，
實際核准狀態由 events.json 與 registry 決定。詳見 [契約與限制](docs/phase0_contracts.md)。

## 現有資料與 legacy

目前 canonical library 是 `data/pitcher_database/releases/v0.6/`，包含 5 位投手、12 個
provisional references。左投/右投 scaler、camera gate、phase DTW 及留一驗證仍可使用。
舊 v0.5 release 保留，但不是目前的使用範例。小樣本驗證不是跨影片泛化能力的證明。

preprocessing 完整保存於 `integration/opencode-preprocessing` 的 `4a65c32`，
尚未合併到新的 `codex/analysis-phase-0`。舊單用途 scripts 和長影片收件命令已列入
[deprecated 清單](docs/legacy.md)，檔案仍保留。既有 Git 已追蹤的環境、模型和素材仍未清除。

## 測試

```powershell
.\.venv-analysis\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv-analysis\Scripts\python.exe -m pip check
```

自動測試使用本機合成 MP4 與確定性的 pose fixture，不依賴網路下載。
實際 MediaPipe 推論另由本機 smoke test 驗證，測試報告見 [Phase 0 狀態](docs/phase0_status.md)。

## 接續開發

Phase 0 已封存，Phase 1 已通過五支正式單球的 clip-level 驗收。Phase 2
目前聚焦於同五支影片的追蹤與關節可靠度，等待獨立人工標註來衡量實際
準確性；尚不擴充多投手或跨投手比較。
