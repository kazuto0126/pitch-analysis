"""Describe interior model-XY samples under every recorded event choice."""
from __future__ import annotations

from copy import deepcopy
import csv
from fractions import Fraction
from html import escape
from importlib.resources import files
from pathlib import Path

from .native_motion_event_viewer import _validate_clips
from .native_motion_events import ROLES, TIMING_LABELS, _angle_window
from .native_motion_transition import describe_manual_event_transitions
from .native_timing_comparison import _load_report
from .native_timing_viewer import _source_player
from ..native_pose_io import BoundReader, read_json, reference, write_json


def _window(rows: list[dict], role: str, bounds: list[int] | None,
            fps: Fraction, *, unresolved: bool = False) -> dict:
    result = _angle_window({'status': 'uncertain' if unresolved or bounds is None else 'annotated',
                            'frame_bounds': bounds}, rows, role)
    result.update(frame_bounds=deepcopy(bounds), min_frames=None, max_frames=None,
                  min_seconds_fraction=None, max_seconds_fraction=None)
    if unresolved:
        return result
    if bounds is None:
        result.update(status='empty_intersection', total_frames=0, calculated_frames=0,
                      missing_frames=0, degenerate_frames=0, reading_kind='empty_window')
    result.update(min_frames=[], max_frames=[], min_seconds_fraction=[], max_seconds_fraction=[])
    if bounds is not None:
        first, last = bounds
        for which in ('min', 'max'):
            value = result[f'{which}_deg']
            indices = [index for index in range(first, last + 1)
                       if rows[index][f'{role}_coordinate_status'] == 'calculated_from_model_xy'
                       and rows[index][f'{role}_model_xy_deg'] == value]
            result[f'{which}_frames'] = indices
            result[f'{which}_seconds_fraction'] = [str(Fraction(index) / fps) for index in indices]
    return result


def describe_stage_curves(clips: list[dict]) -> dict:
    """Keep inclusive windows, all extrema ties and all legal event intervals.

    The common window is shared by every admitted interval. It says nothing
    about visibility or correctness. Unresolved events never use candidate frames.
    """
    _validate_clips(clips)
    records = []
    for clip in clips:
        fps = Fraction(clip['fps_fraction'])
        for stage in describe_manual_event_transitions(clip):
            known = stage['status'] != 'unavailable'
            intervals = [(pair['start_frame'], pair['end_frame'])
                         for pair in stage['joints'][ROLES[0]]['pairs']] if known else []
            if known and not intervals:
                raise ValueError('Confirmed stage events must admit a chronological interval')
            union = [min(s for s, _ in intervals), max(e for _, e in intervals)] if known else None
            common = [max(s for s, _ in intervals), min(e for _, e in intervals)] if known else None
            if common is not None and common[0] > common[1]:
                common = None
            item = {
                'pitch_id': clip['pitch_id'], 'timing_key': stage['transition_key'],
                'status': 'descriptive_model_xy_stage_curve' if known else 'unavailable',
                'start_event_name': stage['start_event'], 'end_event_name': stage['end_event'],
                'start_event': deepcopy(clip['events'][stage['start_event']]),
                'end_event': deepcopy(clip['events'][stage['end_event']]),
                'all_endpoint_pairs': stage['all_endpoint_pairs'],
                'chronological_pairs': stage['chronological_pairs'],
                'excluded_nonchronological_pairs': stage['excluded_nonchronological_pairs'],
                'union_frame_bounds': union, 'common_frame_bounds': common,
                'joints': {},
            }
            for role in ROLES:
                item['joints'][role] = {
                    'possible_window': _window(clip['rows'], role, union, fps, unresolved=not known),
                    'common_window': _window(clip['rows'], role, common, fps, unresolved=not known),
                    'intervals': [{'start_frame': start, 'end_frame': end,
                                   **_window(clip['rows'], role, [start, end], fps)}
                                  for start, end in intervals],
                }
            records.append(item)
    known = sum(row['status'] != 'unavailable' for row in records)
    return {'clip_count': len(clips), 'source_frames': sum(c['frame_count'] for c in clips),
            'stage_count': len(records), 'event_confirmed_stages': known,
            'event_unresolved_stages': len(records) - known,
            'joint_summary_count': len(records) * len(ROLES), 'records': records}


_WINDOW_FIELDS = ['status', 'total_frames', 'calculated_frames', 'missing_frames', 'degenerate_frames',
                  'min_deg', 'max_deg', 'min_frames', 'max_frames', 'min_seconds_fraction',
                  'max_seconds_fraction', 'sample_span_deg', 'sample_span_scope', 'reading_kind']


def _csv_window(window: dict) -> dict:
    return {key: ';'.join(str(x) for x in value) if isinstance(value, list) else value
            for key in _WINDOW_FIELDS for value in [window[key]]}


def _write_csvs(output: Path, summary: dict) -> None:
    base = ['pitch_id', 'timing_key', 'joint']
    with (output / 'stage_windows.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=base + ['window', 'start_frame', 'end_frame'] + _WINDOW_FIELDS)
        writer.writeheader()
        for row in summary['records']:
            for role, joint in row['joints'].items():
                for name in ('possible_window', 'common_window'):
                    window = joint[name]
                    bounds = window['frame_bounds']
                    writer.writerow({'pitch_id': row['pitch_id'], 'timing_key': row['timing_key'], 'joint': role,
                                     'window': name, 'start_frame': bounds[0] if bounds else None,
                                     'end_frame': bounds[1] if bounds else None, **_csv_window(window)})
    with (output / 'stage_intervals.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=base + ['start_frame', 'end_frame'] + _WINDOW_FIELDS)
        writer.writeheader()
        for row in summary['records']:
            for role, joint in row['joints'].items():
                for interval in joint['intervals']:
                    writer.writerow({'pitch_id': row['pitch_id'], 'timing_key': row['timing_key'], 'joint': role,
                                     'start_frame': interval['start_frame'], 'end_frame': interval['end_frame'],
                                     **_csv_window(interval)})


def _number(value: object) -> str:
    return '未定' if value is None else f'{value:.6f}' if isinstance(value, float) else str(value)


def _extreme(window: dict, which: str, page: str) -> str:
    frames = window[f'{which}_frames']
    if frames is None or not frames:
        return '未定'
    links = ', '.join(f'<a href="{page}#frame={index}&amp;request=1" target="_blank" rel="noopener">{index}</a>'
                      for index in frames)
    return f"{_number(window[f'{which}_deg'])}°<details><summary>原格號（{len(frames)}格）</summary>{links}</details>"


def _cells(window: dict, page: str) -> str:
    bounds = window['frame_bounds']
    span = _number(window['sample_span_deg'])
    return (f"<td>{bounds if bounds is not None else '無共同影格' if window['status'] == 'empty_intersection' else '事件未定'}</td>"
            f"<td>{_number(window['calculated_frames'])}／{_number(window['total_frames'])}</td>"
            f"<td>{_number(window['missing_frames'])}／{_number(window['degenerate_frames'])}</td>"
            f"<td>{_extreme(window, 'min', page)}</td><td>{_extreme(window, 'max', page)}</td>"
            f"<td>{span}<br>{escape(window['sample_span_scope'])}</td>")


def _report(pitcher_id: str, summary: dict, pages: dict[str, str]) -> str:
    header = '<th>影格範圍</th><th>可算／全部格</th><th>缺座標／退化格</th><th>最小模型角</th><th>最大模型角</th><th>樣本跨度（度）</th>'
    lines = ['<!doctype html><html lang="zh-Hant"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{escape(pitcher_id)}：區段內模型讀值範圍</title>',
             '<style>body{font:17px system-ui;line-height:1.7;max-width:1500px;margin:24px auto;padding:0 16px;color:#203147;background:#f3f6fa}'
             'section,details.clip{background:white;padding:16px;margin:16px 0;border-radius:10px}summary{cursor:pointer}'
             'table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border:1px solid #d5dde8;text-align:left;vertical-align:top}'
             '.table{overflow-x:auto}a{color:#096795}</style>',
             f'<h1>{escape(pitcher_id)}：區段內模型讀值範圍</h1>',
             f"<p>{summary['clip_count']}球、{summary['source_frames']}格；{summary['stage_count']}段中"
             f"{summary['event_confirmed_stages']}段事件已確認、{summary['event_unresolved_stages']}段未定。</p>",
             '<section><p>「可能影格」是所有合法事件區間的聯集；「共同影格」是所有合法選格都包含的交集，並不表示關節可信。'
             '每個區間含首尾，不選事件中點，未知候選不參與計算。</p>'
             '<p>這些極值是保存的模型XY讀值，不是新投球事件、真實活動幅度、轉折偵測或品質評分。'
             '肘與膝極值可發生於不同格，不能合成同一姿勢。展開極值原格號可回看既有影片與曲線。</p>'
             '<p>跨度至少需要兩個可算樣本；缺值不補點。部分樣本跨度不能代表完整期間軌跡，'
             '配對共用影格，也不是獨立樣本或機率。逐點可靠性尚未校準。</p>'
             '<p><a href="stage_windows.csv">影格窗口CSV</a> · <a href="stage_intervals.csv">全部合法區間CSV</a> · '
             '<a href="stage_curves.json">完整資料JSON</a></p></section>']
    role_labels = {'throwing_elbow': '投球肘', 'lead_knee': '前導膝'}
    for pitch_id, page in pages.items():
        lines.append(f'<details class="clip"><summary>{escape(pitch_id)}：展開四段曲線讀值</summary>')
        lines.append(f'<p><a href="{page}" target="_blank" rel="noopener">開啟本球原影格／曲線播放器</a></p>')
        for row in (r for r in summary['records'] if r['pitch_id'] == pitch_id):
            label = TIMING_LABELS[row['timing_key']]
            lines.append(f'<h2>{label}</h2><div class="table"><table><tr><th>關節</th><th>窗口</th>{header}</tr>')
            for role, joint in row['joints'].items():
                for key, name in (('possible_window', '可能影格'), ('common_window', '共同影格')):
                    lines.append(f'<tr><td>{role_labels[role]}</td><td>{name}</td>{_cells(joint[key], page)}</tr>')
            lines.append('</table></div>')
            if row['status'] == 'unavailable':
                lines.append('<p>人工起終事件未確認；候選影格未用於上述計算。</p>')
                continue
            lines.append(f"<details><summary>全部合法事件選格（{row['chronological_pairs']}組；"
                         f"排除倒序{row['excluded_nonchronological_pairs']}組）</summary>"
                         f'<div class="table"><table><tr><th>關節</th>{header}</tr>')
            for role, joint in row['joints'].items():
                for interval in joint['intervals']:
                    lines.append(f'<tr><td>{role_labels[role]}</td>{_cells(interval, page)}</tr>')
            lines.append('</table></div></details>')
        lines.append('</details>')
    lines.append('<p>未改原曲線、人工事件、模型或品質門檻；不提升素材資格或Phase驗收狀態。'
                 '原播放器與跳格adapter保持，實際瀏覽器播放尚未覆核。</p></html>')
    return '\n'.join(lines)


def write_stage_curves(root: str | Path, event_report_json: str | Path, output: str | Path) -> dict:
    """Write source-bound interior curve descriptions and original-frame links."""
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if output == root / 'analysis_results' or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('Stage curves output must be a new analysis_results subdirectory')
    if output.exists():
        raise FileExistsError('Stage curves output already exists')
    loaded, source_ref = _load_report(root, event_report_json, output)
    payload = read_json(root / source_ref['path'])
    expected = [{'pitch_id': clip['pitch_id'], **stage} for clip in loaded['clips']
                for stage in describe_manual_event_transitions(clip)]
    if payload.get('manual_stage_readouts') != expected:
        raise ValueError('Saved manual stage readouts differ from their bound sources')
    summary = describe_stage_curves(loaded['clips'])
    pages, player_names = {}, {}
    for index, clip in enumerate(loaded['clips']):
        name = f'source_{index:03d}.html'
        pages[name], _ = _source_player(root, output, clip, name)
        player_names[clip['pitch_id']] = name
    resources = files('pitch_analysis').joinpath('review_assets')
    scripts = {'motion_viewer.js': resources.joinpath('native_motion_viewer.js').read_bytes(),
               'frame_link.js': resources.joinpath('native_motion_frame_link.js').read_bytes()}
    refs = [source_ref, *loaded['source_refs']]
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    html = _report(loaded['pitcher_id'], summary, player_names)
    output.mkdir(parents=True, exist_ok=False)
    _write_csvs(output, summary)
    for name, content in {'report.html': html, **pages}.items():
        with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
    for name, content in scripts.items():
        with (output / name).open('xb') as stream:
            stream.write(content)
    for ref in refs:
        reader.path(ref)
    result = {
        'schema_version': 'native-stage-curves-v1', 'status': 'stage_curves_created',
        'pitcher_id': loaded['pitcher_id'], 'summary': summary,
        'source_ref': source_ref, 'source_refs': refs,
        'artifacts': {name: reference(root, output / name)
                      for name in ('report.html', 'stage_windows.csv', 'stage_intervals.csv', *pages, *scripts)},
        'new_inference_calls': 0, 'new_tracking_replays': 0, 'new_ground_truth_labels': 0,
        'pointwise_reliability': 'unknown', 'quality_status': 'not_calibrated', 'usable_for_analysis': None,
        'browser_interaction_verified': False, 'formal_reference_promotion': False,
    }
    write_json(output / 'stage_curves.json', result)
    return result
