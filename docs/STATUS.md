# 進度摘要

更新：2026-10-24（台灣）。[完整狀態](current_status.md)；[大谷人工事件覆核](phase3_ohtani_event_review_20261024.md)。

**Phase 1 = PASSED；Native interface integration = PASSED；Phase 2 自動可靠性仍 NOT PASSED。**
**Phase3第一個描述性曲線交付 = COMPLETE；Phase3整體尚未驗收。**

## 最新：大谷001／002／003／005五事件已由HSU確認，進度4/5

005：啟動81–82、最高抬腿96–99、前腳落地124、出手134–135、收尾169。
001：啟動28、最高抬腿59、前腳落地110、出手119–120、收尾160；收尾經連續影格確認。
002：啟動78、最高抬腿95、前腳落地129、出手137、收尾203；概覽收尾候選208依連續格回答修正。
003：啟動105、最高抬腿119、前腳落地156、出手164、收尾208；收尾經連續影格確認。
範圍原樣保留，沒有取中點；概覽中的88／176已依連續影格回答修正，原話與修正歷程保留。
格式、原片來源與事件順序檢查通過；checkpoint只保存事件範圍完成，不宣稱完整pose GT已完成。
GT仍in_progress、reviewed_at_utc=null；未覆核的身份、關節、pose failure等欄位仍null。
004事件未填；最後一支004的338格圖片／29張連續格表已準備好，等待人工回答。
本輪無產品／測試碼變更，未重跑suite或骨架；最近相同程式碼1201 passed／0 failed／2 skipped。
[人工進度與來源](dataset_selections/phase3_ohtani_event_review_progress_20261024.json)。

## 前段：大谷五球空白事件模板與005查看圖片備妥

依「繼續」準備五個事件的人工判讀，先005再001／002／003／004，不重標骨架。
五支原片實際解碼共1684格，建立同一ground-truth-v1的五份空白模板；人工答案全null。
005的321張原片固定裁切、27張連續12格表、每8格概覽與逐格查看頁已完成。
只使用既有已確認觀看裁切，原MP4／骨架／曲線／接受紀錄保持；504份保護檔案SHA不變。
事件完成不同於完整pose GT；其他未覆核欄位保持null，之後再處理限定事件範圍接入。
無產品／測試碼變更、無新模型或人工判斷，未重跑suite；最近同程式碼1201 passed／0 failed／2 skipped。
[模板與判讀流程](phase3_ohtani_event_review_20261024.md)。等待人工回答005，不自行填事件。

## 前段：山本時距圖與逐球解讀完成

依「繼續」將前輪已算好的16筆時距整理成可匯出PNG、中文MD與24筆配對清單。
每種時距各6組配對，合計7筆區間分開、9筆重疊／相接、8筆無法比較；不省略缺值。
最高抬腿→落地：001／002／004三球範圍均重疊；落地→出手：002範圍與001／004分開。
圖中的界線來自人工事件，不是統計信賴區間；沒有品質排名、顯著性推論或整體投手profile。
圖表已實看，標籤與數值可讀；504份資料／來源／程式／測試SHA變更0。
本輪無產品／測試碼變更，未重跑suite；相同程式碼最近1201 passed／0 failed／2 skipped。
兩位投手的骨架方式與九支既有接受紀錄保持，003仍為歷史對照。
下一項資料缺口是大谷五球尚無同類已確認人工事件；本輪不猜測、不建立新GT或新review工具。
輸出：`analysis_results/phase3_yamamoto_timing_readout_20261024_01/timing_intervals.png`。
[解讀摘要](phase3_yamamoto_timing_readout_20261024.md)。本輪commit／push後停止。

## 前段：山本四球人工事件／曲線與時距對照完成

依HSU「好進行」授權，新增`compare-native-motion-events`，只讀保存曲線及同源人工事件。
四球477格、20筆事件逐欄保留；16筆時距13筆可界定、3筆保留空值與原因。
曲線有精確線／範圍色帶／不確定候選虛線，附事件視窗模型角度、完整缺值分母與逐球時距表。
005啟動及最高抬腿仍不確定；001啟動仍不可觀測，不取中點或自動補事件。
003仍排除；大谷與山本既有九支人工接受、骨架方式、原CSV／PNG／觀看頁保持。
新推論、tracking replay、角度重算、新GT皆0；未作精確出手對齊、跨投手比較或評分。
新觀看頁可使用，自動瀏覽器互動未驗證；本輪不追加逐格人工標註或新通過條件。
完整suite **1201 passed／0 failed／0 errors／2 skipped**（1203項、135.796秒，新增19項，含正式五球E2E）。
另5項純Node時間測試與18項事件helper斷言全過；233份保護資料SHA變更0，20筆事件差異0。
輸出：`analysis_results/phase3_yamamoto_event_timing_20261024_01/comparison/viewer/review_motion_events.html`。
[區間公式與使用](native_motion_events.md)、[本輪結果](phase3_yamamoto_event_timing_20261024.md)。
本輪commit／push後停止，不開始下一功能。

## 前段：山本四支曲線／連動頁已獲HSU人工接受4/4

沿用現有`describe-native-motion`及`review-native-motion`，直接讀取已接受的山本骨架。
001／002／004／005共477格、954個可計算2D投影角，CSV、PNG、來源摘要與連動頁皆完成。
003保持歷史對照；大谷五球既有結果保持。兩位投手各自觀看，沒有跨投手比較。
415份受保護來源／結果／程式SHA變更0；新模型、tracking replay、新GT及產品／測試碼變更皆0。
實看四張曲線圖，保留局部突變、unknown及null，沒有新增自動品質判定。
HSU回覆「都正確一樣是5表現最好」，四支新觀看頁已記為人工整體接受4/4，005為偏好示範。
原話、reviewer、時間、頁面／JS／四支輸出與overlay SHA另存獨立人工紀錄，原pending快照保留。
連同大谷5/5，九支觀看結果皆已接受；工具自動瀏覽器檢查未執行，未新增逐點精度GT。
本輪未重跑suite；同程式碼最近結果1182 passed／0 failed／2 skipped，另5項Node測試全過。
輸出：`analysis_results/phase3_yamamoto_native_motion_20261024_01/viewer/review_motion.html`。
[逐球結果與限制](phase3_yamamoto_native_motion_20261024.md)。本輪提交／推送後停止。

## 前段：大谷影片／曲線連動頁獲HSU人工接受5/5

新增`review-native-motion`，只讀大谷五球既有曲線及已接受overlay，共1684格。
可播放連動游標／格號／肘膝角、逐格、格號前往、滑桿及點曲線跳轉。
優先使用實際呈現畫格的mediaTime；fallback明示時間估計，要求目標與實際呈現格分開顯示。
觀看速度只影響播放器，原骨架、CSV、PNG、逐點unknown/null與Phase2 NOT PASSED保持。

來源／CSV與完整時間軸檢查、6項新增Python測試及5項純Node時間測試已完成；
完整Python suite **1182 passed／0 failed／0 errors／2 skipped**（1184項、130.406秒），
含正式五球E2E；另5項Node測試全過。詳細來源見[交付紀錄](phase3_motion_sync_20261024.md)。
379份受保護來源與既有結果不變，新增模型推論／角度重算／GT皆0。
HSU在本機開啟後回覆「都正確尤其是5最完美」，五球已記為人工整體接受，
005作為使用者偏好的示範樣本；沒有因此調參、加總分或替換其他四球。
原話、reviewer、時間及頁面／JS／五球輸出SHA另存
`annotations/motion_reviews/HSU_20261024/ohtani_motion_sync_acceptance.json`。
**HUMAN ACCEPTED（5/5）**；原CODE COMPLETE／UI PENDING保留為交付時快照。
工具自動瀏覽器驗證仍未執行；整體接受未轉成逐點可靠性或精度GT。
本次僅保存覆核與文件，無產品／測試碼變更，未重跑模型或測試。
輸出：`analysis_results/phase3_motion_sync_20261024_01/viewer/review_motion.html`。
[操作與同步定義](native_motion_viewer.md)。本輪commit／push後停止，不開始新功能。

## 前段：依使用者授權完成Phase3第一步，大谷五球2D投影曲線

在確認保留大谷／山本骨架模式後，使用者授權「可以繼續下步驟」。
新分支`codex/phase3-native-motion`，Phase2 checkpoint`48ac5bc`保留。
新增`describe-native-motion`，讀取既有已接受原生資料，輸出投球肘及前導膝的逐格2D夾角。
大谷五球1684格／3368個可計算投影角，CSV、PNG、來源摘要與原overlay觀看頁皆完成。
模型推論／tracking replay／新GT皆0；363份保護檔案在完整測試後SHA不變。

實看五張曲線圖，標籤及座標軸可讀；肘的局部突變保持，沒有平滑、補點或判為動作差異。
model_xy_deg用於描述，逐點可靠性unknown、usable_deg空值；未作事件對齊／偵測或跨投手比較。
完整suite：**1176 passed／0 failed／0 errors／2 skipped**（1178項、99.172秒，新增13項）；
兩skip為Windows檔案symlink能力，正式五球E2E已執行。

**本輪Phase3第一個交付 = COMPLETE；Phase3整體尚未驗收。**
Phase2原自動可靠性仍NOT PASSED；這次有限前進由使用者另行授權，沒有回改舊驗收。
輸出：`analysis_results/phase3_ohtani_native_motion_20261024_01/review_motion.html`。
[欄位與限制](native_motion.md)、[逐球結果](phase3_ohtani_native_motion_20261024.md)。
本輪commit／push後停止，不自動擴充下一功能。

## 前段：山本四片接受完成，啟用九片人工輔助交付收尾

HSU回覆「都正確」，已保存山本001／002／004／005四片的原話、reviewer、時間及來源SHA。
四片477格／8109點的原生資料入口與報告皆由既有CLI建立並經loader逐格核對，差異0、break0。
003保持歷史對照；原rollout pending快照不覆寫，最新狀態以新獨立接受紀錄為準。

連同大谷先前五片，**啟用九片2161格／36737點皆已完成人工整片接受、資料接入與描述報告**。
大谷報告沿用，沒有重跑；323份保護來源／程式／測試SHA不變。
本輪新增模型推論、tracking replay、插值、逐點GT與正式素材替換皆0。

本輪無產品／測試碼修改，不重跑suite；相同程式碼前輪完整結果：
**1163 passed／0 failed／2 skipped**，含正式五球E2E。
**Phase2人工輔助骨架交付 = COMPLETE；原自動可靠性／Phase2總驗收 = NOT PASSED。**
逐點可靠性／可見性仍unknown、usable_for_analysis=null；沒有新分類器、通過線或Phase3。
啟用集合的整片人工覆核已全部完成，本輪commit／push後停止。
[接受紀錄與輸出位置](phase2_active_cohort_closeout_20261024.md)、
[版本化證據](dataset_selections/phase2_active_cohort_closeout_20261024.json)。

## 前段：原生逐關節與追蹤連續性報告完成

新增`report-native-reliability`，直接讀取已接受的原生資料入口，補齊17點相鄰位移、
缺值區段、左右影像順序，以及人物框／雙髖中心／軀幹尺度連續性。
每球提供中文`report.md`、pose／tracking JSON與完整逐格JSONL，可依格號／時間回看overlay。

大谷五球**1684格／28628關節影格**皆已由實際CLI產生報告；
幾何break0，原XY／狀態／分數／缺值原因差異0，158份保護來源在完整測試後SHA不變。
新增推論、tracking replay、插值及人工標註皆0。
位移只比較相鄰兩格，缺值不跨越；大位移／左右順序改變沒有自動當成錯誤或identity switch。

完整suite：**1163 passed／0 failed／0 errors／2 skipped**（1165項，104.141秒，新增10項）；
兩skip為Windows檔案symlink能力。正式山本五球E2E已執行，major提示仍2／0／19／5／3。
五球人工接受維持5/5，逐點可靠性／可見性unknown、usable_for_analysis=null。
**本輪描述報告 = COMPLETE；Phase2自動可靠性仍NOT PASSED。**
這次補齊資料診斷，沒有新增自動品質分類器或通過標準；本輪commit／push後停止，未進Phase3。
輸出：`analysis_results/phase2_native_reliability_20261024_01/`。
[使用與公式](native_reliability.md)、[逐球結果](native_reliability_results_20261024.md)、
[版本化證據](dataset_selections/native_reliability_20261024.json)。

## 前段：原生骨架接入完成

新增`prepare-analysis-input`與`load_native_analysis_input`，後續程式可讀取已保存的RTMPose17點、
同源人物追蹤、metadata及人工overlay接受證據。輸出為reference-only manifest＋使用摘要，來源SHA綁定。
大谷五球皆由實際CLI建立bundle、再由loader逐格讀取：**1684格／28628關節影格，原影格／追蹤差異0**。
002保留原結果；新人物偵測、pose、tracking replay及GT皆0。

五球影片人工接受仍為5/5；逐點可靠性與可見性均unknown，usable_for_analysis=null，
原model_observed／missing及不支援的visibility／presence／Z保留原樣。完整分母保留，沒有靠移除資料提高分數。
本輪**Native analysis input integration = PASSED**。

完整測試：**1153 passed／0 failed／2 skipped**（1155項，98.953秒，14項新增必要測試）；
正式山本五球舊E2E有執行，major提示仍2／0／19／5／3。初輪沙箱額外8項junction skip已由一般權限重跑補齊。
2068個保護來源SHA不變，既有產品檔案僅CLI新增命令；模型、selector、pose／tracking核心、
confidence gate、門檻、平滑／插值、raw及人工GT保持。

**本輪授權交付 = COMPLETE WITH KNOWN LIMITATIONS；Phase2 = NOT PASSED（自動關節可靠性未驗證通過）。**
這次接入與整片人工接受並未建立逐點正確率，也沒有新增驗收分數、標註或小規則試驗。
本輪完成後停止，未進Phase3。使用者若要繼續，應依已保留限制另行決定工作範圍。
輸出：`analysis_results/phase2_native_analysis_input_20261023_01/`，五球入口在`bundles/`。
[使用方式](native_analysis_input.md)、[結果／收尾判定](native_analysis_input_results_20261023.md)、
[版本化證據](dataset_selections/native_analysis_input_20261023.json)。

## 前段：大谷五球共用骨架已補齊

依HSU「後續投手沿用」授權，已將同批大谷001／003／004／005套用已採用流程。
HSU確認起始框001＝1號、003＝1號、004＝1號、005＝2號；四片各跑一次，
335／369／338／321格共1363格。4次首格＋1359次其餘人物偵測、1363次pose，
整格missing0、幾何track break0；002沿用已接受321格結果，本輪0次重跑。
對話中斷期間模型已全部完成，恢復後僅補輸出及檢查，沒有重複推論。

已實看12張比較圖、35組原片／舊／新骨架：005第128格舊骨架混到打者、
003第158格舊手臂伸向背景的問題有可見改善，取樣骨架留在投手附近。
完整五球overlay及原片已整理在`analysis_results/phase2_ohtani_seeded_skeleton_20261023_01/review_all.html`。
2052個保護來源SHA不變，2722份新worker binary核對；原GT、山本素材與所有舊結果保留。

本輪只新增設定／4份人工seed／文件，沒有修改產品碼或測試，未重跑完整suite；
相同程式碼最新完整測試仍為1139 passed／0 failed／2 skipped（前輪結果）。
HSU隨後回覆「可以都正確」，001／003／004／005已記為影片層人工接受；
加上先前002，**大谷五球overlay人工接受完成5/5，共1684格**。
原話、reviewer、紀錄時間及四份來源／overlay／原生座標SHA保存於
`annotations/skeleton_reviews/HSU_20261023/ohtani_shared_skeleton_acceptance.json`。
執行時的rollout JSON保留pending歷史快照，最新人工狀態以此獨立review紀錄為準。
這是整片目視接受，沒有新增逐點XY／可見性GT或校準分數。
**Phase2自動可靠性仍NOT PASSED**，未進Phase3。
[結果](ohtani_shared_skeleton_rollout_20261023.md)、[版本化證據](dataset_selections/ohtani_shared_skeleton_rollout_20261023.json)。

## 前段：共用骨架標準採用，山本五片完成

HSU在新結果交付後再次確認這是目前最成功的方法，授權後續投手沿用。
後續新骨架固定使用本共用流程，每片確認初始投手；確認原話與來源另存獨立方法授權紀錄。

HSU已完整觀看大谷`supplement_002`的321格新overlay，確認沒有追到其他人、關節整體對位正確，
並授權山本與後續投手沿用。新骨架共同入口已提供：`prepare-skeleton`準備首格編號框，
人工選定投手後，以`extract-skeleton`連續追蹤人物框並輸出RTMPose原生17點。
首格不重複偵測，失去唯一連結後保留missing；固定政策及模型保持，不按投手姓名調參。

HSU確認山本001首格2號、其餘1號；五片各跑一次，影格數87/175/115/114/101，合計592格。
首格detector5次＋其餘587次，pose 592次；
整格missing 0、幾何track break 0。003仍是歷史對照，啟用素材維持001／002／004／005。
已檢查五片新舊骨架比較圖，完整新overlay可由下方入口觀看；山本新結果的全片人工覆核仍待進行。
既有003的1,205個可見人工XY同點平均誤差 22.21→10.11px；
87–104歷史重大錯位段 76.90→10.50px，逐關節差異與缺值另列，沒有新增GT或新驗收門檻。

完整suite **1139 passed／0 failed／0 errors／2 skipped**（1141項，98.391秒）。
正式山本五球舊E2E提示仍2／0／19／5／3；727個保護來源SHA不變。
Git另保存5份HSU初始投手選擇，原始seed不改寫。
新入口保留17點原生score，沒有Z／visibility／presence則為null；不能冒充舊33點特徵／gate資料。
舊核心、門檻、raw、人工GT及Phase1素材保持；未做Phase3。

**骨架方法 = ADOPTED；Phase2自動可靠性仍NOT PASSED。**
已完成共用骨架接入及本次五片輸出；仍待山本新overlay的人工檢查，以及新模型可靠性／原生特徵的後續工作。
採用一支人工接受的結果與共同方法，不等於所有未來關節已量化通過。
本機：`analysis_results/phase2_yamamoto_seeded_skeleton_20261023_01/review_all.html`。
[結果](standard_skeleton_rollout_20261023.md)、[操作流程](standard_skeleton_workflow.md)、
[版本化證據](dataset_selections/standard_skeleton_rollout_20261023.json)。本輪commit／push後停止。

## 前段：106格續跑完成，原生座標321／321

使用者續行後，已完成同一球第215–320格106次pose；前215份prediction逐值不變。
兩段合計319次新pose＋193／194兩格cache＝321格，整格missing106→0。
沿用已保存321格框關聯，本次0detector／0tracking replay，原claim與中斷輸出全保留。
新增不可變逐事件進度檔，108筆均完成，不覆寫舊snapshot；本次無I/O中斷或模型重試。

實看25組原片／舊／新對照，準備段舊手臂混入打者的改善保留，續跑交界／尾段骨架在投手附近。
這是代理抽樣，沒有新人工GT；局部精度及遮擋肘／腕仍未校準，不能以有座標宣告可靠。
完整suite **1126 passed／0 failed／0 errors／2 skipped**（1128項，82.719秒，新增11項）。
正式山本五球E2E提示仍2／0／19／5／3；672保護檔案SHA不變、106份新binary核對。
**本次補完 = COMPLETED；尚未正式採用，Phase2自動可靠性仍NOT PASSED。**
輸出：`analysis_results/phase2_seeded_resume_native_20261023_01/`，先開`review_all.html`。
[結果與保存證據](phase2_seeded_resume_results_20261023.md)、[版本化數字](dataset_selections/ohtani_seeded_resume_results_20261023.json)。
本輪完成commit／push後停止，不擴跑其他球、加新標註、改既有驗收或進Phase3。

## 前段：人工初始化追蹤部分結果已保存，I/O中斷後停止

HSU已核准[單球方案](phase2_seeded_native_track_plan_20261021.md)，指定第0格1號框。
新增獨立native關聯／cache／producer與CLI；321格關聯只跑一次，1seeded＋320linked、無幾何break。
0新detector、213新pose、193／194完整幾何相同重用，共215格骨架；剩餘106格未執行。
Windows在214格後替換執行紀錄失敗，錯誤處理又遇暫存檔存在，依方案不重試。
保留原receipt／tmp、partial／binary／journal／claim；另存中斷說明，不改原紀錄為成功。
匯出完整321格overlay，215–320標missing（執行中斷，並非追蹤／遮擋結論）。

實看22組原片／舊／新對照，準備段舊手臂線回到投手附近；未新增GT或宣稱全片可靠。
完整suite **1115 passed／0 failed／0 errors／2 skipped**（1117項，81.922秒，新增24項）。
正式山本五球E2E提示仍2／0／19／5／3；615保護檔案、8中斷原artifact SHA不變，213份binary核對。
完整推論未完成，**本輪未正式採用，Phase2仍NOT PASSED**；既有核心／門檻／raw／GT保持。
輸出：`analysis_results/phase2_seeded_track_native_20261021_01/`，先開`review_all.html`。
[結果與已知問題](phase2_seeded_native_track_results_20261021.md)、[版本化數字](dataset_selections/ohtani_seeded_track_results_20261021.json)。
本輪保存並停止；沒有claim reset、補跑剩餘106格、政策調整、擴跑或Phase3。

## 最新：人物框單球修正完成，政策不採用

HSU已核准[單球方案](phase2_person_box_native_plan_20261021.md)，新人物偵測模型與既有RTMPose接點已完成。
第2球321格只跑一次：detector321次，pose2次（193／194格），319格因兩框都合格而missing。
原native有座標321格→2格，最長missing193格；這不是可靠性改善，**本政策NOT ADOPTED**。
實看22組原片／舊／新對照：人物框分別包圍投手與打者，但框中心條件仍無法排除打者。
不調整ROI／分數或追加小規則；Phase2仍NOT PASSED，沒有新GT、正式提升或擴跑。

新增36項無模型測試；完整suite **1091 passed／0 failed／0 errors／2 skipped**（1093項，83.812秒）。
正式山本五球E2E提示仍2／0／19／5／3；541個保護檔案SHA不變，323份binary payload吻合。
正式核心／selector／gate保持；native僅增加當格bbox、嚴格not_run與overlay狀態。
輸出：`analysis_results/phase2_person_box_native_20261021_01/`，先看`review_all.html`。
[結果／停止決定](phase2_person_box_native_results_20261021.md)、[使用說明](phase2_person_box_native_usage.md)。
本輪已完成並停止，不換模型、重跑、擴大素材或進Phase3。

## 前段：可選 live RTMPose 入口與五球一次性交付完成

HSU已核准並完成新MP4入口；沿用既有權重／隔離環境、已確認的固定crop。
五球335／321／369／338／321格各推論一次，共1684次，0執行失敗；
輸出原生17點、完整SimCC、逐格journal及五支H264 overlay。正式MediaPipe預設與核心／門檻保持。

實看90張overlay取樣與9組原片／舊／新對照：部分舊錯例回到投手附近，
但新後端第2球準備段、第5球第128格仍混合／錯位；座標齊全不代表可靠。
新結果未校準、accuracy未量測、usable_for_analysis=null；五球仍候選，沒有新人工GT。
**工程接入完成，Phase2自動可靠性仍NOT PASSED。**

完整suite **1055 passed／0 failed／0 errors／2 skipped**（1057項，新增39項，64.453秒）；
正式山本五球E2E提示仍2／0／19／5／3，475保護檔案SHA不變。
輸出：`analysis_results/phase2_ohtani_live_native_20261020_01/`，先看`review_all.html`。
[結果／停止狀態](phase2_live_native_pose_results_20261021.md)、[使用方式](phase2_live_native_pose_usage.md)。
本輪已完成並停止，沒有自行開始新推論、校準、正式模型替換或Phase3。

## 前段：原因分解完成，提出可選live後端方案

只讀新補片已保存資料：85個未選中格皆無eligible候選；14格沒有模型候選，
其餘71格有輸出但被原ROI／投影尺度／confidence拒絕，不能統稱完全漏偵測。
p02第159／245、p05第251格也沒有其他eligible骨架可直接換上。
前導膝起始低visibility段p02／p03／p05分別81／107／82格，不能由模型分數斷言真人被遮住。

[原因分解](phase2_ohtani_supplement_diagnosis_20261020.md)；
[可選live RTMPose最小實作方案](phase2_live_native_pose_plan_20261020.md)在該checkpoint備妥，後續已核准並完成，見上節。
原因分解當時的RTMPose介面僅讀封存；該checkpoint未改程式或推論，沒有重跑suite或進Phase3。
方案限定現有權重／隔離環境、新補片1684格各一次、原生17點與五支overlay，正式核心及門檻保持。

## 前段：大谷新補片5球分析完成，仍有追蹤與前導膝限制

HSU已確認新來源五球軀幹框與完整動作crop，五球各跑一次，0執行異常。
合計選中1599/1684格（94.95%）；最長gap9／13／5／12／2格，
肘角raw coverage59.10／59.19／75.34／57.40／63.86%，全部超過原50%條件。
仍5 degraded、0通過原pose gate：p01／p04因長缺口，p02另有pose<90%與前導膝角不足，
p03／p05前導膝角raw也<80%；門檻保持。

實查五球90張overlay取樣與6組警示原片對照；p02第159／245格有錯位／混合，
p05第251格混合捕手附近上身與投手下身，原警示保留，不宣稱追蹤已可靠。
五球仍candidate，沒有新人工逐格GT、正式提升／替換或Phase3。
305個保護檔案SHA不變；五支H264 overlay全解碼1684格。

輸出：`analysis_results/phase2_ohtani_supplement_20261020_01/`，先看`review_all.html`。
[逐球結果](phase2_ohtani_supplement_results_20261020.md)、[版本化數字](dataset_selections/ohtani_supplement_analysis_20261020.json)。
本輪無產品／測試程式變更，未重跑suite；最近同版紀錄1016 passed／0 failed／2 skipped。
固定素材試用完成，Phase2自動可靠性仍NOT PASSED；下一步應針對混合骨架與關節漏偵測提出有限修正方案。

## 前段：大谷新補片5球匯入與人工輸入覆核完成

只處理指定批次`20261020T073530Z_6gyr6IC2e0Q`：成功5、拒收0、衝突0；重跑新增0／跳過5。
五球1280×720、60000/1001 FPS，完整解碼335／321／369／338／321格，共1684格；
逐格分數時間最大偏差每球0.000666667ms。SQLite2批13球→3批18球，重跑球數不變。
五球均candidate；HSU已在本對話逐球確認補片p01–p05的七項輸入條件，
五球共35項已轉錄pass，輸入覆核**5/5完成**。這是輸入覆核，不是逐格關節GT；尚未執行分析或提升／替換正式素材。
交付區14檔SHA／mtime及33個既有review／input SHA不變；來源排除紀錄6顆重疊較多、3顆不完整／無投球保留。

輸出：`analysis_results/phase2_ohtani_supplement_intake_20261020_01/`，
`review_all.html`提供五球原片與清單。下一步設定這批來源的投手範圍，再沿用現有模型與門檻各分析一次；本輪尚未開始。
本輪無產品碼變更，不重跑完整suite、不自動分析；Phase2自動可靠性仍NOT PASSED。

## 前段：23格缺失復原未解決主要限制，未接入正式流程

使用者要求繼續修正後，完成003／004資料鏈查核及004／005共23個原missing格的同模型獨立重新偵測。
003／004肘角缺失中，97.19%／95.40%涉及右腕低visibility；時間、側別、座標與原gate計算沒有發現bug。
23格重新偵測的原selector重播僅多找回5格，最長gap仍3／13，沒有解除原失敗原因。
因此不接入正式capture、不改正式數字、不追加crop／門檻搜尋；來源raw與GT保留。
正式結果仍001／002 pose gate通過，003／004／005 degraded，Phase2自動可靠性仍NOT PASSED。

輸出：`analysis_results/phase2_ohtani_recovery_20261020_01/`；
[處理結果與停止決定](phase2_ohtani_remaining_limits_20261020.md)、[同投手替代素材需求](phase2_ohtani_replacement_input_needs_20261020.md)。
本輪無產品／測試碼變更，未重跑suite；同版最近結果1016 passed／0 failed／2 skipped。
使用者已明確選定「先補較清楚的大谷素材」。本次目標新增至少3顆不同完整投球，依
[明確供片需求](phase2_ohtani_replacement_input_needs_20261020.md)及contract v2交付。
當時索引只有已分析的5球批次；其後新交付的5球候選匯入與人工輸入覆核狀態見上節。
001／002與全部歷史結果保留；可選live後端不在本次路線，未開始新模型或Phase3。

## 前段：大谷五球固定範圍試用完成，兩球通過 pose gate

001–004各推論一次、005沿用前次，產品程式／模型／門檻與GT不變。
相較全畫面＋軀幹限制，五球選中1448→1842/1873，missing425→31；
最長gap依序1／1／1／3／13，肘角raw coverage59.12／62.58／41.00／41.71／59.49%。
001、002品質success但仍needs_event_review；003／004肘角不足，004另有3格gap，005保留13格收尾缺口。
001自動input quality仍因followthrough_unverified而degraded，002為accepted，未自動升格素材。

實際檢查57格前後overlay（114張），原錯人／missing例子有改善；局部關節準確度仍有限，未新增人工GT。
新四片overlay全解碼，504保護檔案SHA不變；五球觀看入口在
`analysis_results/phase2_ohtani_crop_cohort_20261019_01/before_after.html`。
本輪只改設定／結果文件，**未重跑完整suite**；同版程式最近紀錄仍1016 passed／0 failed／2 skipped。
已完成本輪固定試用；Phase2自動可靠性仍NOT PASSED，未進Phase3，不追加裁切大小搜尋。

## 前段：大谷第5球有實際主體改善

使用者同意單球完整動作範圍輸入。新增可選 `input_crop`，保存 crop-native 候選及轉回原圖的座標；
未指定時維持舊流程。模型、selector、gate／門檻與人工GT保持。
同一球僅跑一次：位置限制版215/353→裁切版338/353（95.75%），missing138→15，最長gap54→13；
肘角raw coverage36.83%→59.49%。固定14格實際對照，原裁判／打者例子回到投手，仍有局部關節限制。
196–208格缺失未補，依原gate仍degraded；沒有宣告Phase2通過。

新增17項測試；完整suite **1016 passed、0 failed、0 errors、2 skipped**（1018項，82.720秒）。
正式山本五球E2E提示仍2／0／19／5／3，160個保護來源／標註／舊輸出SHA不變。
輸出：`analysis_results/phase2_ohtani_p05_crop_20261019_01/`，包含可直接看的 `before_after.html`。
本輪停在單球交付；下一步才是其餘四球的固定範圍試用，不做倍率搜尋或Phase3。

## 前段：可選投手範圍修正已交付，部分錯人改善

使用者已核准有限selector／capture修改並確認五球橘框。新增可選`subject_roi`：
左右肩／髖原點必須在操作範圍內，手腳可伸出；無匹配候選就missing。無設定時維持原預設。
模型仍看原完整畫面，既有信心與品質門檻、插值／平滑不變；所有模型候選另存逐格側檔。

大谷五球各重跑一次：0執行異常、5 degraded。原第2球177／266格錯人改missing；第5球多個抽樣改選投手，
但2／5仍有框內軀幹搭配跨人手臂。選中格數1677→1448，missing196→425；不可把減少數量當準確率改善。
完整suite **999 passed、0 failed、0 errors、2 skipped**（1001項，新增32項，含正式五球E2E），89.641秒。
原山本major提示仍2／0／19／5／3。候選保存核對0錯誤：1873格、2801副候選／92433點，47784選中raw點逐值相等。

輸出：`analysis_results/phase2_ohtani_subject_lock_20261019_01/`；先看`START_HERE.md`。
本輪已完成並停止，未改成全自動辨識或正式reference；Phase2自動可靠性仍NOT PASSED。
詳細數字、實際overlay抽樣與使用方式見[結果報告](phase2_pitcher_lock_results_20261019.md)。

## 前段：大谷翔平五球試用完成，五球 degraded

使用者已選定大谷翔平的一批五球。後續山本工作集合只含 `001`、`002`、`004`、`005`，
四對工作副本已建立於 `input/yoshinobu_yamamoto/phase2_active_20261019/`。
`003` 原影片與全部人工／模型證據保留，退出新試用集合；原五球評估分母與 NOT PASSED 結論不變。

本次只處理交付索引中的 `20261010T110737Z_RObvkuHpkSo`。HSU 已確認五球所有七項輸入需求（35項），
既有 MediaPipe 流程各跑一次，五球均完成輸出、0 執行異常；依原品質 gate 全為 degraded。
不重開已結束的警示試驗，不新增逐格 GT，不進 Phase 3。
當前進度與停止條件見[本批工作紀錄](phase2_next_dataset_20261019.md)。

大谷五球已成功匯入、0 拒收，重跑新增 0／跳過 5；人工輸入覆核 5/5 完成，未升為正式 reference。
1,873 格已完成分析與 overlay 全解碼；實際檢查每球 14 格 source／overlay 圖（共70格）。
有效 pose 比例依序 91.99／92.02／94.08／84.15／85.55%；肘角raw coverage 59.12／56.44／36.49／38.78／78.19%。
**重要限制：第2球部分抽樣轉到打者，第5球多處骨架落在裁判／打者；高coverage不能當成抓對投手。**
五球均有超過2格pose gap，另有膝角coverage不足／肘角coverage不足；詳見結果報告。
已交付本批結果後停止；下一個具體問題是主體選取／跨人骨架，尚未修改正式核心或開始新的修復試驗。
本輪 handoff 測試 **73 passed、0 failed、2 skipped**（75 項，含新增 6 項）。
上述為匯入 checkpoint 測試；本次只準備素材並實跑，無產品程式變更，未重跑全suite。
分析輸出：`analysis_results/phase2_ohtani_pilot_20261019_01/`，先看 `START_HERE.md`。
候選與人工輸入覆核紀錄仍在 `analysis_results/phase2_ohtani_intake_20261019_01/` 與各候選 `review.json`。

## 前段：原生17／33點接入第一版完成

使用者核准「第一版接入實作」後，已在`codex/phase2-native-pose-interface`完成獨立原生contract、
封存來源adapter、資料保存、五支RTMPose overlay及003十二關節比較；每後端完整592格。
沒有padding33或fake visibility／presence／Z，原生score保留；新路徑未校準、不套用原gate。
原MediaPipe99個missing欄位完整保留；新RTMPose推論／tracker／校準／標註皆0。
五支overlay已全解碼驗證，並實際檢查每片6個sample frame的繪圖／對齊，不新增人工GT。

45項新測試；完整suite **961 passed、0 failed、0 errors、2 skipped**（963項，76.699秒，含正式五球E2E）。
原重大提示維持2／0／19／5／3；467保護來源與62上游SHA不變。
獨立核對29,600個原生欄位、592份SimCC及003的1,380人工列，座標／score最大差異0。
原core、正式MediaPipe預設、門檻、raw與GT維持；8顆候選未分析或升格。
輸出：`analysis_results/phase2_native_interface_20261018_01/`。

工程接入PASSED，不代表原錯點接受問題已修好；Phase2自動可靠性仍NOT PASSED。
已依核准範圍收尾，不開始live RTMPose、正式模型替換、gate校準或Phase3。

## 前段：原生後端介面方案（後續已核准並實作）

使用者確認「允許規劃後端介面改動」後，已完成接入與驗收方案；這是規劃授權，尚未實作。
建議第一版只接已封存五球的MediaPipe33／RTMPose17資料，新增原生contract、來源adapter、
獨立overlay與比較報告。正式MediaPipe、33點舊流程、selector、gate及人工GT保持。
新模型推論／校準／標註皆0；不padding33或把native score當visibility／presence。
介面接入驗收與Phase2自動可靠性分開；本版完成也不會自動讓Phase2 PASSED。
最小版不需修改既有正式核心；live RTMPose及正式模型替換不在第一版範圍。
本次只修改文件，未重跑測試；最近完整suite仍916 passed／0 failed／2 skipped。
等待使用者確認方案後才實作，未進Phase3。

## 前段：十二關節與漏報原因核對完成

只讀既有輸出完成003全部115格×12關節的對照，沒有重開已拒絕訊號或再跑RTMPose。
十二關節全片平均XY誤差均下降，但左髖67/114格、右髖72/114格退步。
原major hold以外，左髖平均9.1535→13.3563px、右髖7.4754→11.7197px；不能宣稱全面改善。
肘84個漏報中81個有可量測訊號，腕68個中59個有訊號；主要不是都缺座標或都被遮擋。
十個既定界線的訓練來源已追查，沒有重校準、刪可靠列或改用分位數。

1,380列／十二關節統計獨立重算一致；1,205可見／173不可觀測／2不確定維持。
該輪完整suite為**916 passed、0 failed、0 errors、2 skipped**（918項，60.560秒，含正式五球E2E）。
原trial決策、正式core／gate／raw／GT及8顆pending候選保持；Phase2仍NOT PASSED，未進Phase3。
輸出：`analysis_results/phase2_rtmpose_coordinate_diagnosis_20261017_01/`。
若下一段要使用原生17點座標，需先確認新的後端／contract工作範圍，不能偽裝成現行33點輸出。

## 前段：RTMPose原生回應單次驗證完成，不採用

已完成使用者核准的隔離相容性、五球592格原生SimCC量測、整片五折及獨立核對。
相容性guard誤拒ONNX符號維度已在推論前修正並另存凍結；實際17點shape仍嚴格驗證。
肘TP/FN/FP **0/84/4**、腕 **3/68/1**；gate通過錯點只抓回0／3，
未達固定採用條件，依規則停止此訊號，不接正式流程或追加調參。

003可見XY同集合：肘平均27.7461→7.3101px，腕26.6556→16.8405px。
這是單片座標的局部改善；自動識別原錯點仍失敗，其他四片精確誤差保持null。
003/104及[可見性來源差異](phase2_visibility_gap_audit_20261016.md)保留，沒有修改人工GT。

該輪完整suite：**916 passed、0 failed、0 errors、2 skipped**（918項，54.701秒，含正式五球E2E）。
34項新合成測試；467目前保護來源及62上游SHA不變。
正式MediaPipe／pose／tracking／gate／raw／GT與五球保持；8交付候選仍pending、未分析。
輸出：`analysis_results/phase2_rtmpose_response_20261016_01/`。
**Phase2 evaluation已完成；自動可靠性仍NOT PASSED。** 本輪到此停止，未進Phase3。

## 前輪：Heavy新資訊單次驗證已完成，不採用

使用者要求「繼續修正直到phase2通過」後，已按[固定範圍](phase2_new_information_proposal_20261016.md)
完成五球592格單次MediaPipe Heavy離線量測與整片五折；沒有更換正式模型。
肘TP/FN/FP **2/82/1**、腕 **2/69/1**，皆未達事先規則。
原gate通過錯點只抓回1／2，同時各提示1個好點，少於原sample-maximum的7／8。
003/104仍漏報；新資訊不足以讓Phase2通過，依規則停止本輪，不追加界線或模型搜尋。

該輪完整suite：**882 passed、0 failed、0 errors、2 skipped**（884項，含正式五球E2E）。
436保護來源及62上游SHA維持；原13特徵分類器、raw、GT、core與8顆候選保持。
新輸出：`analysis_results/phase2_heavy_information_20261016_01/`。
歷史提案保留原SHA；核准與實際執行另存manifest，不再待核准。

## 已交付

- 正式五球592格baseline、5/5人工定性覆核、003完整人工XY及品質／追蹤評估。
- 第一步：分析輸出新增重大錯位覆核提示，維持major TP20/FN1/FP9；003/104仍為已知漏報。
- 第二步：固定13特徵＋9missing indicators、L2邏輯迴歸、整片五折一次驗證；10模型均正常收斂，未調參或重FIT。
- 第一階段提示繼續提供；第二步分類器只保存離線結果，不接正式流程。

## 前輪13特徵分類器決策：兩關節皆不採用

肘TP/FN/FP **13/71/13**，腕 **20/51/24**。
肘未達TP≥17／FP≤1，改善也未分布兩支非003；腕未達TP≥27／FP≤1／非003TP≥23。
依核准規則停止調整這組訊號，缺口記為 **需要更好的影像或模型資訊**。

在原gate已通過的點中，新提示抓回肘13／腕16錯點，同時額外提示肘9／腕21好點。
原gate支持中未被新提示標出的數目為453/477、309/350；人工可靠保留376、245。
這是覆核負擔試算，原資料、座標與可用狀態未被修改。

## 前輪13特徵分類器驗證與保存

- **842 passed、0 failed、0 errors、2 skipped**；844項／56.411秒／exit0，含正式五球E2E。
- 55項新增合成測試；2skip為Windows符號連結能力。
- 獨立核對1184特徵列、15392值、10模型、1168有效OOF分數與3522筆screen計數。
- FEATURE讀GT0、APPLY讀人工檔0，每fold FIT只讀另外4片GT。
- 380目前保護來源及62上游SHA維持；原pose/tracking、gate、raw、GT、正式五球與第一步證據保留。
- 8交付候選仍candidate/pending，未分析／升格。
- 前輪輸出：`analysis_results/phase2_joint_quality_classifier_20261016_01/`。

## 尚未通過與停止點

自動提示仍會漏掉已知關節錯位，003/104也仍未修復；無提示不能當成可靠。
依既有Phase2要求維持NOT PASSED，沒有新增零錯誤、更多標註或新資料集的收尾條件。
本次兩步工作及後續核准的單次Heavy試驗均已收尾，沒有降低門檻或冒稱通過。
不再調整這些訊號或追加小規則，未進Phase3。
