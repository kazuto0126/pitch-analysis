"""One entry for existing descriptive writers, without new pose or event labels."""
from __future__ import annotations

from html import escape
from pathlib import Path

from .native_descriptive_profile import write_descriptive_profile
from .native_motion_events import TIMING_PAIRS, load_event_clips, write_event_comparison
from .native_motion_transition import ROLES
from .native_profile_viewer import write_profile_viewer
from .native_stage_curves import write_stage_curves
from ..native_pose_io import BoundReader, reference, write_json


def _entry(pitcher_id: str, summary: dict, stage_curve_summary: dict | None = None) -> str:
    html = f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(pitcher_id)}：投球動作描述</title>
<style>body{{font:18px system-ui;line-height:1.8;max-width:900px;margin:35px auto;padding:0 20px;color:#203147;background:#f3f6fa}}
section{{background:white;border-radius:12px;padding:22px;margin:18px 0}}a{{color:#096795}}
.start{{display:inline-block;background:#126886;color:white;padding:12px 20px;border-radius:8px;text-decoration:none}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #d7e0e9}}</style>
<h1>{escape(pitcher_id)}：投球動作描述</h1>
<p>本批 {summary['clip_count']} 球、{summary['source_frames']} 格。從已保存骨架與人工事件產生。</p>
<section><h2>開始回看</h2><p>選區段與同投手球對，查看讀值，再按事件影格回看兩側原影片與曲線。</p>
<a class="start" href="review/review_profile.html">開啟動作摘要與影片證據</a>
<p><a href="events/viewer/review_motion_events.html">查看完整逐球事件表與曲線</a> ·
<a href="profile/report.md">完整文字摘要</a></p></section>
<section><h2>本批可描述的範圍</h2><table>
<tr><th>內容</th><th>有讀值</th><th>未定</th></tr>
<tr><td>同投手時距球對</td><td>{summary['timing_comparable_pairs']}</td><td>{summary['timing_unavailable_pairs']}</td></tr>
<tr><td>肘／膝區段端點摘要</td><td>{summary['joint_calculable_summaries']}</td><td>{summary['joint_unavailable_summaries']}</td></tr></table>
<p>未定事件保留原狀，範圍不取中點；有可算端點不代表關節可信。
讀值只描述模型XY投影，逐點可靠性尚未校準，不能用來判斷動作好壞。</p>
<p>單球沒有跨球比較。兩側各按原FPS獨立播放；本次沒有新增骨架推論或人工標註，也沒有提升素材資格。</p></section>
<section><h2>下載資料</h2><p><a href="profile/timing_relations.csv">時距球對 CSV</a> ·
<a href="profile/joint_direction_summary.csv">肘／膝方向摘要 CSV</a> ·
<a href="events/manual_stage_readouts.csv">逐球四段讀值 CSV</a> ·
<a href="events/manual_stage_pairs.csv">全部合法事件端點配對 CSV</a></p>
<details><summary>來源與執行紀錄</summary><p><a href="delivery_manifest.json">本次交付紀錄</a> ·
<a href="profile/profile.json">完整摘要 JSON</a> ·
<a href="events/event_comparison.json">人工事件與讀值 JSON</a></p></details></section>
<p>此入口仍讀取專案內的原影片；不是可攜影片包。實際播放尚未由工具覆核。
Phase 2自動可靠性與Phase 3整體驗收狀態維持原紀錄。</p></html>'''
    if stage_curve_summary is not None:
        section = f'''<section><h2>區段內模型讀值範圍</h2>
<p><a href="stage_curves/report.html">查看區段內模型讀值範圍與來源影格</a></p>
<p>事件已確認區段 {stage_curve_summary['event_confirmed_stages']} 個；事件未定區段 {stage_curve_summary['event_unresolved_stages']} 個。
最小／最大值只描述窗口內已保存的模型讀值，不是新的事件或人體真實活動幅度。
已確認區段仍可能包含缺值／退化影格；請同時查看可算／全部影格與缺失區段。</p></section>
'''
        html = html.replace('<section><h2>下載資料</h2>', section + '<section><h2>下載資料</h2>')
    return html


def write_motion_report(root: str | Path, config_json: str | Path,
                         output: str | Path, *, include_stage_curves: bool = False) -> dict:
    """Preflight saved inputs and run existing writers, with optional stage curves.

    Component contracts and algorithms remain unchanged. A partial delivery is
    preserved with an incomplete marker; it is never presented as a finished
    entry or resumed implicitly. Use another fresh output after resolving errors.
    """
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if output == root / 'analysis_results' or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('Motion report output must be a new analysis_results subdirectory')
    if output.exists():
        raise FileExistsError('Motion report output already exists')
    loaded = load_event_clips(root, config_json, output / 'events')
    refs = loaded['source_refs']
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    output.mkdir(parents=True, exist_ok=False)
    stages = {}
    failed_stage = 'events'
    common = {
        'schema_version': 'native-descriptive-motion-delivery-v1',
        'pitcher_id': loaded['pitcher_id'], 'clip_count': len(loaded['clips']),
        'source_frames': sum(clip['frame_count'] for clip in loaded['clips']),
        'source_refs': refs, 'new_inference_calls': 0, 'new_tracking_replays': 0,
        'new_ground_truth_labels': 0, 'pointwise_reliability': 'unknown',
        'usable_for_analysis': None, 'formal_reference_promotion': False,
        'browser_interaction_verified': False, 'portable_media_copy': False,
    }
    try:
        events = write_event_comparison(root, config_json, output / 'events')
        stages['events'] = {'status': events['status'],
                            'manifest_ref': reference(root, output / 'events/event_comparison.json')}
        failed_stage = 'profile'
        profile = write_descriptive_profile(root, output / 'events/event_comparison.json', output / 'profile')
        stages['profile'] = {'status': profile['status'],
                             'manifest_ref': reference(root, output / 'profile/profile.json')}
        failed_stage = 'review'
        review = write_profile_viewer(root, output / 'profile/profile.json', output / 'review')
        stages['review'] = {'status': review['status'],
                            'manifest_ref': reference(root, output / 'review/profile_viewer_manifest.json')}
        stage_curves = None
        stage_curve_summary = None
        if include_stage_curves:
            failed_stage = 'stage_curves'
            stage_curves = write_stage_curves(root, output / 'events/event_comparison.json', output / 'stage_curves')
            stages['stage_curves'] = {'status': stage_curves['status'],
                                      'manifest_ref': reference(root, output / 'stage_curves/stage_curves.json')}
        failed_stage = 'finalize'
        for ref in refs:
            reader.path(ref)
        summary = profile['summary']
        if (events['pitcher_id'] != common['pitcher_id'] or profile['pitcher_id'] != common['pitcher_id']
                or review['pitcher_id'] != common['pitcher_id']
                or any(value != common['clip_count'] for value in
                       (events['clip_count'], summary['clip_count'], review['clip_count']))
                or any(value != common['source_frames'] for value in
                       (events['source_frames'], summary['source_frames'], review['source_frames']))):
            raise ValueError('Component cohort differs from the preflighted source cohort')
        if stage_curves is not None:
            stage_curve_summary = {key: stage_curves['summary'][key] for key in (
                'clip_count', 'source_frames', 'stage_count', 'event_confirmed_stages',
                'event_unresolved_stages', 'joint_summary_count')}
            expected_count = common['clip_count'] * len(TIMING_PAIRS)
            expected_confirmed = sum(
                all(clip['events'][name]['status'] == 'annotated' for name in bounds)
                for clip in loaded['clips'] for bounds in TIMING_PAIRS.values())
            expected = {
                'clip_count': common['clip_count'], 'source_frames': common['source_frames'],
                'stage_count': expected_count, 'event_confirmed_stages': expected_confirmed,
                'event_unresolved_stages': expected_count - expected_confirmed,
                'joint_summary_count': expected_count * len(ROLES),
            }
            if (stage_curves['pitcher_id'] != common['pitcher_id']
                    or stage_curve_summary != expected
                    or any(type(value) is not int for value in stage_curve_summary.values())):
                raise ValueError('Stage-curve component cohort differs from the preflighted source cohort')
        result = {
            **common, 'status': 'motion_report_created', 'completed_stages': list(stages),
            'stages': stages, 'timing_pairs': summary['timing_pair_count'],
            'comparable_pairs': summary['timing_comparable_pairs'],
            'unavailable_pairs': summary['timing_unavailable_pairs'],
            'joint_summary_count': summary['joint_summary_count'],
            'joint_calculable_summaries': summary['joint_calculable_summaries'],
            'joint_unavailable_summaries': summary['joint_unavailable_summaries'],
            'artifacts': {},
        }
        if stage_curve_summary is not None:
            result['stage_curve_summary'] = stage_curve_summary
        # All component validations finish before creating the success entry.
        with (output / 'START_HERE.html').open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(_entry(common['pitcher_id'], summary, stage_curve_summary))
        result['artifacts']['START_HERE.html'] = reference(root, output / 'START_HERE.html')
        write_json(output / 'delivery_manifest.json', result)
    except Exception as error:
        # The entry is written last; remove only this invocation's partial entry
        # if final output writing failed. All completed component data remain.
        entry = output / 'START_HERE.html'
        if failed_stage == 'finalize' and entry.exists():
            entry.unlink()
        marker = output / 'delivery_manifest.json'
        if not marker.exists():
            write_json(marker, {**common, 'status': 'incomplete', 'failed_stage': failed_stage,
                                'completed_stages': list(stages), 'stages': stages, 'error': str(error),
                                'artifacts': {}})
        raise
    return result
