"""Side-by-side source curves at all confirmed human foot-plant origins."""
from __future__ import annotations

from copy import deepcopy
import csv
from fractions import Fraction
from html import escape
from pathlib import Path
from importlib.resources import files
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from .native_motion_anchor_bounds import describe_anchor_bounds
from .native_motion_event_viewer import _validate_clips
from .native_motion_events import ROLES
from .native_timing_comparison import _load_report
from .native_timing_viewer import _source_player
from ..native_pose_io import BoundReader, reference, write_json


def prepare_cohort_curves(cohorts: list[dict]) -> dict:
    """Preserve source samples and add candidate-relative display coordinates."""
    if not isinstance(cohorts, list) or len(cohorts) != 2:
        raise ValueError('Supply exactly two source cohorts')
    ids = [cohort.get('pitcher_id') for cohort in cohorts]
    if any(not isinstance(value, str) or not value for value in ids) or ids[0] == ids[1]:
        raise ValueError('Cohort curve review requires two distinct pitcher identities')
    result, bounds = [], []
    counts = dict.fromkeys(('exact', 'bounded', 'unavailable'), 0)
    paths = 0
    for side, cohort in zip(('a', 'b'), cohorts, strict=True):
        _validate_clips(cohort['clips'])
        clips = [describe_anchor_bounds(clip) for clip in cohort['clips']]
        for clip in clips:
            counts[clip['origin_status']] += 1
            paths += len(clip['origin_candidates'])
            if clip['origin_candidates']:
                bounds.extend(Fraction(value) for row in clip['bounded_rows']
                              for value in row['relative_seconds_bounds_fraction'])
        result.append({'side': side, 'pitcher_id': cohort['pitcher_id'], 'clip_count': len(clips),
                       'source_frames': sum(c['frame_count'] for c in clips), 'clips': clips})
    domain = [min(bounds), max(bounds)] if bounds else None
    return {
        'cohorts': result, 'clip_count': sum(c['clip_count'] for c in result),
        'source_frames': sum(c['source_frames'] for c in result), 'origin_counts': counts,
        'origin_candidate_paths': paths,
        'source_time_bounds_fraction': [str(v) for v in domain] if domain is not None else None,
        'full_display_seconds_bounds': [float(v) for v in domain] if domain and domain[0] < domain[1] else [-.5, .5],
        'zoom_display_seconds_bounds': [-.5, .5], 'angle_display_bounds': [0, 180],
    }


def _segments(clip: dict, role: str, origin: int) -> list[list[tuple]]:
    """Only adjacent calculated samples share a line; missing samples break it."""
    fps = Fraction(clip['fps_fraction'])
    segments, current = [], []
    for row in clip['rows']:
        if row[f'{role}_coordinate_status'] != 'calculated_from_model_xy':
            if current:
                segments.append(current)
                current = []
        else:
            current.append((Fraction(row['frame_index'] - origin) / fps,
                            row[f'{role}_model_xy_deg'], row['frame_index']))
    if current:
        segments.append(current)
    return segments


def _tag_svg_links(path: Path, groups: dict) -> int:
    svg, xlink = 'http://www.w3.org/2000/svg', 'http://www.w3.org/1999/xlink'
    ET.register_namespace('', svg)
    ET.register_namespace('xlink', xlink)
    tree = ET.parse(path)
    tagged = 0
    for group in tree.getroot().iter(f'{{{svg}}}g'):
        info = groups.get(group.get('id'))
        if info is None:
            continue
        clip, origin = info['clip'], info['origin']
        anchors = list(group.iter(f'{{{svg}}}a'))
        if len(anchors) != info['point_count']:
            raise RuntimeError('SVG sample links differ from the original plotted samples')
        for anchor in anchors:
            url = anchor.get(f'{{{xlink}}}href') or anchor.get('href')
            frame = int(parse_qs(urlsplit(url).fragment)['frame'][0])
            if not 0 <= frame < clip['frame_count']:
                raise RuntimeError('SVG sample link lies outside its original source')
            seconds = Fraction(frame - origin) / Fraction(clip['fps_fraction'])
            anchor.set('target', '_blank')
            anchor.set('rel', 'noopener')
            for key, value in {'cohort': info['side'], 'pitch-id': clip['pitch_id'],
                               'origin-frame': origin, 'source-frame': frame, 'view': info['view']}.items():
                anchor.set(f'data-{key}', str(value))
            title = ET.Element(f'{{{svg}}}title')
            title.text = (f"{info['side'].upper()} / {clip['pitch_id']} / source frame {frame}; "
                          f"origin candidate {origin}; relative seconds {seconds}; "
                          f"saved model XY {clip['rows'][frame][info['role'] + '_model_xy_deg']} degrees")
            anchor.insert(0, title)
            tagged += 1
    if tagged != sum(info['point_count'] for info in groups.values()):
        raise RuntimeError('SVG did not retain every plotted source-frame link')
    tree.write(path, encoding='utf-8', xml_declaration=True)
    return tagged


def _plot(prepared: dict, role: str, output: Path, pages: dict) -> dict:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(15, 9), dpi=140, layout='constrained')
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 2, sharex='col', sharey=True)
    colors = ['#0072b2', '#d55e00', '#009e73', '#cc79a7', '#82660a']
    groups, panels = {}, []
    for row_index, cohort in enumerate(prepared['cohorts']):
        for column, view in enumerate(('full', 'zoom')):
            axis = axes[row_index][column]
            limits = prepared[f'{view}_display_seconds_bounds']
            panel_points = 0
            for index, clip in enumerate(cohort['clips']):
                color = colors[index % len(colors)]
                origins = clip['origin_candidates']
                if not origins:
                    axis.plot([], [], color=color, label=f"{clip['pitch_id']} (origin unconfirmed)")
                for candidate_index, origin in enumerate(origins):
                    segments = _segments(clip, role, origin)
                    label = f"{clip['pitch_id']} ({clip['origin_status']})" if candidate_index == 0 else None
                    for segment_index, points in enumerate(segments):
                        axis.plot([float(p[0]) for p in points], [p[1] for p in points], color=color,
                                  linewidth=1.05, alpha=.65 if clip['origin_status'] == 'bounded' else .95,
                                  linestyle='--' if clip['origin_status'] == 'bounded' else '-',
                                  label=label if segment_index == 0 else None)
                    if not segments:
                        axis.plot([], [], color=color, label=label)
                    visible = [point for segment in segments for point in segment
                               if limits[0] <= float(point[0]) <= limits[1]]
                    if visible:
                        urls = [f"{pages[(cohort['side'], clip['pitch_id'])]}#frame={p[2]}&request=1" for p in visible]
                        scatter = axis.scatter([float(p[0]) for p in visible], [p[1] for p in visible],
                                               s=9, color=color, alpha=.6, urls=urls, zorder=3)
                        gid = f"points_{cohort['side']}_{index}_{origin}_{view}"
                        scatter.set_gid(gid)
                        groups[gid] = {'clip': clip, 'origin': origin, 'side': cohort['side'],
                                       'view': view, 'role': role, 'point_count': len(visible)}
                        panel_points += len(visible)
            axis.axvline(0, color='#29384b', linewidth=1, linestyle=':')
            axis.set(xlim=limits, ylim=prepared['angle_display_bounds'],
                     xlabel='Seconds relative to a confirmed human foot-plant candidate',
                     ylabel='Saved model XY angle (degrees)')
            axis.set_yticks([0, 45, 90, 135, 180])
            axis.grid(alpha=.2)
            axis.spines[['top', 'right']].set_visible(False)
            axis.set_title(f"{cohort['side'].upper()}: {cohort['pitcher_id']} | "
                           + ('complete source timelines' if view == 'full' else 'display zoom: -0.5 to +0.5 s'),
                           loc='left', fontsize=10)
            axis.legend(fontsize=8, loc='upper right')
            panels.append({'side': cohort['side'], 'view': view, 'xlim': list(axis.get_xlim()),
                           'ylim': list(axis.get_ylim()), 'linked_samples': panel_points})
    title = 'Throwing elbow' if role == 'throwing_elbow' else 'Lead knee'
    figure.suptitle(f'{title} | two source cohorts at human foot-plant origins\n'
                   'Saved model XY projections; alternative shifts are not extra observations', fontsize=13)
    figure.savefig(output / f'{role}.png')
    figure.savefig(output / f'{role}.svg')
    figure.clear()
    return {'role': role, 'panels': panels, 'linked_samples': _tag_svg_links(output / f'{role}.svg', groups),
            'svg_link_metadata_added': True}


def _write_csv(output: Path, prepared: dict) -> None:
    fields = ['side', 'pitcher_id', 'pitch_id', 'frame_index', 'timestamp_sec', 'fps_fraction',
              'origin_status', 'origin_frame_min', 'origin_frame_max', 'relative_frame_min', 'relative_frame_max',
              'relative_seconds_min', 'relative_seconds_max', 'relative_fraction_min', 'relative_fraction_max',
              'pointwise_reliability']
    fields += [f'{role}_{key}' for role in ROLES for key in ('model_xy_deg', 'coordinate_status', 'usable_deg')]
    with (output / 'cohort_curves.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for cohort in prepared['cohorts']:
            for clip in cohort['clips']:
                for row in clip['bounded_rows']:
                    origin = clip['origin_frame_bounds'] or [None, None]
                    data = {'side': cohort['side'], 'pitcher_id': cohort['pitcher_id'], 'pitch_id': clip['pitch_id'],
                            'frame_index': row['frame_index'], 'timestamp_sec': row['timestamp_sec'],
                            'fps_fraction': clip['fps_fraction'], 'origin_status': clip['origin_status'],
                            'origin_frame_min': origin[0], 'origin_frame_max': origin[1],
                            'pointwise_reliability': 'unknown'}
                    for key, source in (('frame', 'relative_frame_bounds'), ('seconds', 'relative_seconds_bounds'),
                                        ('fraction', 'relative_seconds_bounds_fraction')):
                        values = row[source] or [None, None]
                        data.update({f'relative_{key}_min': values[0], f'relative_{key}_max': values[1]})
                    for role in ROLES:
                        data[f'{role}_model_xy_deg'] = row[f'{role}_model_xy_deg']
                        data[f'{role}_coordinate_status'] = row[f'{role}_coordinate_status']
                        data[f'{role}_usable_deg'] = None
                    writer.writerow(data)


def _report(prepared: dict, pages: dict) -> str:
    lines = ['<!doctype html><html lang="zh-Hant"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1"><title>兩投手完整模型曲線並列回看</title>',
             '<style>body{font:18px system-ui;line-height:1.8;max-width:1500px;margin:25px auto;padding:0 16px;background:#f3f6fa;color:#203147}'
             'section{padding:18px;background:white;margin:20px 0;border-radius:10px}object{width:100%;height:920px;border:1px solid #d5dce5}'
             'table{border-collapse:collapse;width:100%}th,td{padding:9px;border:1px solid #d5dce5;text-align:left}.table{overflow-x:auto}a{color:#096795}</style>',
             '<h1>兩投手完整模型曲線並列回看</h1>',
             f"<p>{prepared['clip_count']}球、{prepared['source_frames']}個來源影格；"
             f"{prepared['origin_candidate_paths']}個人工落地顯示原點，並非新增投球或觀測。</p>",
             '<section><p>每位投手獨立面板，共用完整秒數範圍與0–180°顯示刻度。0秒是各自已確認落地候選；'
             '範圍的每個候選都作替代平移，虛線不代表機率。右欄是相同樣本的±0.5秒顯示放大。</p>'
             '<p>點彩色樣本圓點會開啟該球原影格／曲線；重疊點可能只有上層可點，請在播放器確認球號。'
             '也可由下表直接開指定球與落地候選。影片跳格實際呈現以播放器格號為準。</p>'
             '<p>模型XY角受攝影投影與定位影響，不能直接解讀為解剖或動作差異。'
             '片頭／片尾長短可能來自剪輯，不表示投球階段長短。沒有平均、插值、時間拉伸、相似度或排名。</p></section>']
    for role, label in zip(ROLES, ('投球肘', '前導膝'), strict=True):
        lines.append(f'<section><h2>{label}：同刻度並列</h2><p>'
                     f'<a href="{role}.svg" target="_blank" rel="noopener">直接開啟可點選SVG</a> · '
                     f'<a href="{role}.png">下載PNG</a></p>'
                     f'<object type="image/svg+xml" data="{role}.svg" aria-label="{label}完整模型曲線">'
                     f'<a href="{role}.svg">開啟SVG圖</a></object></section>')
    lines.append('<section><h2>原片與人工原點</h2><div class="table"><table><tr>'
                 '<th>側／投手</th><th>球</th><th>原格數／FPS</th><th>落地原點狀態</th><th>原落地候選格</th><th>大致出手原格／狀態</th></tr>')
    for cohort in prepared['cohorts']:
        for clip in cohort['clips']:
            page = pages[(cohort['side'], clip['pitch_id'])]
            origins = ', '.join(f'<a href="{page}#frame={frame}&amp;request=1" target="_blank" rel="noopener">{frame}</a>'
                                for frame in clip['origin_candidates']) or '未確認，不指定原點'
            event = clip['events']['approximate_release']
            lines.append(f"<tr><td>{cohort['side'].upper()}／{escape(cohort['pitcher_id'])}</td>"
                         f"<td><a href=\"{page}\" target=\"_blank\" rel=\"noopener\">{escape(clip['pitch_id'])}</a></td>"
                         f"<td>{clip['frame_count']}／{escape(clip['fps_fraction'])}</td>"
                         f"<td>{clip['origin_status']}</td><td>{origins}</td>"
                         f"<td>{event['frame_bounds']}／{escape(event['status'])}</td></tr>")
    lines += ['</table></div><p><a href="cohort_curves.csv">完整來源影格CSV</a> · '
              '<a href="cohort_curves.json">來源與顯示紀錄JSON</a></p></section>',
              '<p>CSV每來源影格一列，缺值保持；替代平移不增加來源分母。未確認落地不畫對齊曲線，原片與資料仍保留。'
              '逐點可靠性尚未校準；不提升素材資格或Phase驗收狀態，瀏覽器實際播放未覆核。</p></html>']
    return '\n'.join(lines)


def write_cohort_curve_review(root: str | Path, report_paths: list[str | Path], output: str | Path) -> dict:
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if output == root / 'analysis_results' or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('Cohort curves output must be a new analysis_results subdirectory')
    if output.exists():
        raise FileExistsError('Cohort curves output already exists')
    if len(report_paths) != 2:
        raise ValueError('Supply exactly two single-pitcher event reports')
    sources = [_load_report(root, path, output) for path in report_paths]
    prepared = prepare_cohort_curves([loaded for loaded, _ in sources])
    refs = [ref for loaded, report_ref in sources for ref in [report_ref, *loaded['source_refs']]]
    pages, html_pages = {}, {}
    for side, (loaded, _) in zip(('a', 'b'), sources, strict=True):
        for index, clip in enumerate(loaded['clips']):
            name = f'source_{side}_{index:03d}.html'
            html_pages[name], _ = _source_player(root, output, clip, name)
            pages[(side, clip['pitch_id'])] = name
    resources = files('pitch_analysis').joinpath('review_assets')
    scripts = {'motion_viewer.js': resources.joinpath('native_motion_viewer.js').read_bytes(),
               'frame_link.js': resources.joinpath('native_motion_frame_link.js').read_bytes()}
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    output.mkdir(parents=True, exist_ok=False)
    _write_csv(output, prepared)
    plots = {role: _plot(prepared, role, output, pages) for role in ROLES}
    for name, content in {'report.html': _report(prepared, pages), **html_pages}.items():
        with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
    for name, content in scripts.items():
        with (output / name).open('xb') as stream:
            stream.write(content)
    for ref in refs:
        reader.path(ref)
    cohorts = []
    for cohort, (loaded, report_ref) in zip(prepared['cohorts'], sources, strict=True):
        cohorts.append({**{k: deepcopy(v) for k, v in cohort.items() if k != 'clips'},
                        'report_ref': report_ref, 'request_ref': loaded['request_ref'],
                        'clips': [{k: deepcopy(v) for k, v in clip.items() if k not in {'rows', 'bounded_rows', 'overlay_url'}}
                                  for clip in cohort['clips']]})
    names = ['report.html', 'cohort_curves.csv', *html_pages, *scripts]
    names += [f'{role}.{kind}' for role in ROLES for kind in ('svg', 'png')]
    result = {
        'schema_version': 'native-cohort-curve-review-v1', 'status': 'cohort_curve_review_created',
        **{key: value for key, value in prepared.items() if key != 'cohorts'}, 'cohorts': cohorts,
        'plots': plots, 'source_refs': refs, 'artifacts': {name: reference(root, output / name) for name in names},
        'new_inference_calls': 0, 'new_tracking_replays': 0, 'new_ground_truth_labels': 0,
        'samples_resampled': False, 'angle_values_recomputed': False, 'smoothed': False, 'interpolated': False,
        'similarity_computed': False, 'cross_pitcher_display': True, 'base_player_modified': False,
        'browser_interaction_verified': False, 'pointwise_reliability': 'unknown', 'quality_status': 'not_calibrated',
        'usable_for_analysis': None, 'formal_reference_promotion': False,
    }
    write_json(output / 'cohort_curves.json', result)
    return result
