"""Link a bound descriptive profile to its unchanged source-frame players."""
from __future__ import annotations

from copy import deepcopy
from html import escape
from importlib.resources import files
from pathlib import Path

from .native_descriptive_profile import summarize_profile
from .native_motion_events import TIMING_LABELS, TIMING_PAIRS
from .native_motion_transition import describe_manual_event_transitions
from .native_motion_viewer import _path
from .native_timing_comparison import _load_report
from .native_timing_viewer import _PAGE, _embedded, _source_player, _url
from ..native_pose_io import BoundReader, read_json, reference, write_json


def _profile_page(root: Path, output: Path, data: dict, profile_ref: dict, text_report_ref: dict) -> str:
    page = _PAGE.replace("人工時距與兩側影片對照", "單投手動作摘要與影片證據")
    page = page.replace("<h1>人工時距：兩側影片對照</h1>",
                        f"<h1>{escape(data['pitcher_id'])}：動作摘要與影片證據</h1>")
    start = page.index('<p class="note">')
    end = page.index('</p>', start) + len('</p>')
    note = '''<p class="note">先選區段與一組已保存的球對，再從兩側事件界線回看原影片與曲線。
範圍保留下界／上界，未確認事件不定位；兩側按原FPS獨立播放。
肘／膝端點差描述模型XY讀值，不是整段活動幅度或品質評分。
按鈕只送出跳格要求，實際呈現請看播放器格號。</p>'''
    page = page[:start] + note + page[end:]
    links = (f'<p><a href="{_url(root, output, text_report_ref)}">完整文字摘要</a> · '
             f'<a href="{_url(root, output, profile_ref)}">下載摘要JSON</a></p>')
    page = page.replace('<label>人工事件區段', links + '<label>人工事件區段', 1)
    page = page.replace('<p id="pair-durations">',
                        '<label>本區段球對 <select id="profile-pair-select"></select></label>'
                        '<section id="profile-stage-summary" aria-live="polite"></section>'
                        '<p id="pair-durations">', 1)
    for side in ('a', 'b'):
        page = page.replace(f'<section><h2 id="{side}-heading">',
                            f'<section id="{side}-panel"><h2 id="{side}-heading">', 1)
        page = page.replace(f'<iframe id="{side}-player"',
                            f'<div id="{side}-joints"></div><iframe id="{side}-player"', 1)
    return page.replace('__DATA__', _embedded(data))


def write_profile_viewer(root: str | Path, profile_json: str | Path,
                         output: str | Path) -> dict:
    """Verify saved profile and original event sources before creating a viewer."""
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if output == root / 'analysis_results' or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('Profile viewer output must be a new analysis_results subdirectory')
    if output.exists():
        raise FileExistsError('Profile viewer output already exists')
    path = _path(root, profile_json)
    payload = read_json(path)
    flags = {'schema_version': 'native-descriptive-pitcher-profile-v1',
             'status': 'descriptive_profile_created',
             'scope': 'same_pitcher_manual_timing_and_model_xy_endpoints',
             'new_inference_calls': 0, 'new_tracking_replays': 0, 'new_ground_truth_labels': 0,
             'pointwise_reliability': 'unknown', 'quality_status': 'not_calibrated',
             'usable_for_analysis': None, 'formal_reference_promotion': False}
    if any(key not in payload or payload[key] != value for key, value in flags.items()):
        raise ValueError('Expected an unchanged descriptive profile with its original scope')
    profile_ref = reference(root, path)
    source_ref = payload['source_ref']
    source_reader = BoundReader(root, [source_ref])
    loaded, report_ref = _load_report(root, source_reader.path(source_ref), output)
    report = read_json(root / report_ref['path'])
    expected_stages = [{'pitch_id': clip['pitch_id'], **stage} for clip in loaded['clips']
                       for stage in describe_manual_event_transitions(clip)]
    if report.get('manual_stage_readouts') != expected_stages:
        raise ValueError('Saved manual stage readouts differ from their original sources')
    summary = summarize_profile(loaded['clips'])
    expected_clips = [{key: value for key, value in clip.items() if key not in {'rows', 'overlay_url'}}
                      for clip in loaded['clips']]
    if (payload.get('pitcher_id') != loaded['pitcher_id'] or payload.get('summary') != summary
            or payload.get('clips') != expected_clips
            or payload.get('source_refs') != [report_ref, *loaded['source_refs']]):
        raise ValueError('Saved profile differs from its bound events, curves or cohort')
    artifacts = payload['artifacts']
    if set(artifacts) != {'report.md', 'timing_relations.csv', 'joint_direction_summary.csv'}:
        raise ValueError('Expected the complete original descriptive profile artifacts')
    refs = [profile_ref, *payload['source_refs'], *artifacts.values()]
    pages, packaged = {}, []
    for index, clip in enumerate(loaded['clips']):
        name = f'source_{index:03d}.html'
        pages[name], item = _source_player(root, output, clip, name)
        item['timing'] = deepcopy(clip['timing'])
        packaged.append(item)
    sides = ('a', 'b') if len(packaged) > 1 else ('a',)
    data = {
        'mode': 'same_pitcher_profile', 'pitcher_id': loaded['pitcher_id'],
        'cohorts': [{'side': side, 'pitcher_id': loaded['pitcher_id'], 'clips': deepcopy(packaged)}
                    for side in sides],
        'stages': [{'key': stage['timing_key'], 'label': TIMING_LABELS[stage['timing_key']],
                    'start': TIMING_PAIRS[stage['timing_key']][0],
                    'end': TIMING_PAIRS[stage['timing_key']][1], **deepcopy(stage)}
                   for stage in summary['stages']],
        'pairs': [{'timing_key': stage['timing_key'], **deepcopy(pair)}
                  for stage in summary['stages'] for pair in stage['timing_pairs']],
    }
    resources = files('pitch_analysis').joinpath('review_assets')
    scripts = {'motion_viewer.js': resources.joinpath('native_motion_viewer.js').read_bytes(),
               'frame_link.js': resources.joinpath('native_motion_frame_link.js').read_bytes(),
               'timing_viewer.js': resources.joinpath('native_timing_viewer.js').read_bytes()}
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    html = _profile_page(root, output, data, profile_ref, artifacts['report.md'])
    output.mkdir(parents=True, exist_ok=False)
    for name, content in {'review_profile.html': html, **pages}.items():
        with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
    for name, content in scripts.items():
        with (output / name).open('xb') as stream:
            stream.write(content)
    for ref in refs:
        reader.path(ref)
    result = {
        'schema_version': 'native-descriptive-profile-viewer-v1', 'status': 'profile_viewer_created',
        'profile_ref': profile_ref, 'pitcher_id': loaded['pitcher_id'],
        'clip_count': summary['clip_count'], 'source_frames': summary['source_frames'],
        'total_pairs': summary['timing_pair_count'], 'comparable_pairs': summary['timing_comparable_pairs'],
        'unavailable_pairs': summary['timing_unavailable_pairs'], 'source_refs': refs,
        'artifacts': {name: reference(root, output / name)
                      for name in ('review_profile.html', *pages, *scripts)},
        'new_inference_calls': 0, 'new_tracking_replays': 0, 'new_ground_truth_labels': 0,
        'independent_playback': True, 'base_player_modified': False,
        'browser_interaction_verified': False, 'pointwise_reliability': 'unknown',
        'usable_for_analysis': None, 'formal_reference_promotion': False,
    }
    write_json(output / 'profile_viewer_manifest.json', result)
    return result
