"""Package the authorized, sealed five-clip review warnings; no model or GT reads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_disagreement_warning import verify_plan, read
from check_movenet_compatibility import bound, sha

CAPTURE_KEYS = ('width','height','start_frame','end_frame','requested_frames',
                'processed_frames','subject_selection','selection_frames')


def signature(capture):
    data = {k:capture[k] for k in CAPTURE_KEYS}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def build(root, output):
    root, output = Path(root).resolve(),Path(output).resolve()
    if output.exists() or not output.is_relative_to(root): raise ValueError('New local output required')
    setup_path = root/'docs/evaluation_plans/phase2_disagreement_warning_evaluation_20261012_01.json'
    setup = read(setup_path); execution = read(bound(root,setup['producer_plan']))
    verify_plan(root,execution)
    run_path = root/execution['output_directory']/'warning_run.json'; run = read(run_path)
    evaluation_path = root/'analysis_results/phase2_disagreement_warning_20261012_01/evaluation/disagreement_warning_evaluation.json'
    evaluation = read(evaluation_path)
    if evaluation['plan_sha256']!=sha(setup_path) or evaluation['run_sha256']!=sha(run_path):
        raise ValueError('Unbound sealed evaluation')
    counts = evaluation['aggregate']['additive_trial_screen']
    if [counts[k] for k in ('non_seed_frames','tp','fn','fp','tn')]!=[587,20,1,9,557]:
        raise ValueError('Authorized backtest differs')
    refs = [{'id':'warning_execution','path':setup['producer_plan']['path'],'sha256':setup['producer_plan']['sha256']},
        {'id':'evaluation_execution','path':setup_path.relative_to(root).as_posix(),'sha256':sha(setup_path)},
        {'id':'warning_run','path':run_path.relative_to(root).as_posix(),'sha256':sha(run_path)},
        {'id':'backtest','path':evaluation_path.relative_to(root).as_posix(),'sha256':sha(evaluation_path)}]
    clips = []
    for c,receipt in zip(setup['clips'],run['clips'],strict=True):
        target,sources = c['target'],c['sources']; pid=target['pitch_id']
        if pid!=receipt['pitch_id']: raise ValueError('Clip receipt differs')
        tracking,capture,bbox = (read(bound(root,sources[k])) for k in ('tracking','capture','bbox_support'))
        warning = read(bound(root,receipt)); measurement=read(bound(root,warning['source_reference']))
        original_raw = measurement['source_references']['original_raw']
        original_csv = bound(root,original_raw)
        analysis = original_csv.parent; metadata=read(analysis/'input_manifest.json')
        technical=read(analysis/'video_metadata.json'); manifest=read(analysis/'analysis.json')
        if (metadata['pitch_id']!=pid or metadata['pitcher']['id']!='yoshinobu_yamamoto'
            or technical['sha256']!=sources['video']['sha256'] or original_csv.name!='pose_raw.csv'
            or target['total_frames']!=technical['frame_count']): raise ValueError('Original analysis identity differs')
        timelines=(tracking['frames'],capture['selection_frames'],bbox['frames'],warning['frames'])
        for timeline in timelines:
            if [f['frame_index'] for f in timeline]!=list(range(target['total_frames'])): raise ValueError('Incomplete source timeline')
        frames = []
        for i,(old,selected,support,new) in enumerate(zip(*timelines,strict=True)):
            if selected['timestamp_ms']!=new['capture_timestamp_ms']: raise ValueError('Warning/capture timeline differs')
            bits = {'original_warning':old['selection_status']!='selected' or bool(old['warnings']),
                'bbox_warning':support['status']=='warning','shoulder_hip_disagreement_warning':new['warning']}
            reasons=[]
            if bits['original_warning']: reasons.append('existing_tracking_review_warning')
            if bits['bbox_warning']: reasons.append('existing_bbox_support_review_warning')
            if bits['shoulder_hip_disagreement_warning']: reasons.append('cross_clip_shoulder_hip_disagreement')
            frames.append({'frame_index':i,'timestamp_ms':technical['timestamps_ms'][i],
                'review_required':any(bits.values()),'reasons':reasons,'evidence_state':bits,
                'diagnostics':{'bbox_state':support['status'],'disagreement_state':new['evidence_state'],
                    'association_status':new['association_status'],'candidate_slot_indices':new['candidate_slot_indices']}})
        known = evaluation['clips'][len(clips)]['additive_trial_screen']
        expected = known['tp']+known['fp']
        if sum(f['review_required'] for f in frames[1:])!=expected: raise ValueError('Union count differs from sealed score')
        clips.append({'pitch_id':pid,'pitcher_id':metadata['pitcher']['id'],
            'identity':{'throws':metadata['pitcher']['throws'],**{k:metadata['video'][k] for k in
                ('camera_view','horizontal_mirror','playback_speed','contains_single_pitch')}},
            'source':{'video_sha256':technical['sha256'],'raw_csv_sha256':sha(original_csv),
                'capture_semantic_sha256':signature(capture),'model_sha256':manifest['provenance']['model_sha256']},
            'frame_count':target['total_frames'],'frames':frames})
        for k in ('tracking','capture','bbox_support'):
            refs.append({'id':pid+'_'+k,**{x:sources[k][x] for x in ('path','sha256')}})
        refs.extend([{'id':pid+'_disagreement',**{x:receipt[x] for x in ('path','sha256')}},
                     {'id':pid+'_raw',**original_raw}])
    if len(clips)!=5 or sum(c['frame_count'] for c in clips)!=592: raise ValueError('Cohort differs')
    result = {'schema_version':'major-review-development-evidence-v1','status':'sealed_development_evidence',
        'development_scope':{'dataset':'Yamamoto formal five previously inspected development clips','clip_count':5,
            'source_frames':592,'evaluation_non_seed_frames':587,'major_tp':20,'major_fn':1,'major_fp':9,'major_tn':557,
            'known_misses':[{'pitch_id':'pitch_003','frame_index':104}],
            'generalization_claim':False,'absence_of_warning_means_reliable':False},
        'source_evidence':refs,'clips':clips}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,ensure_ascii=False,allow_nan=False,separators=(',',':')); stream.write('\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('output',type=Path)
    args=parser.parse_args(); result=build(Path(__file__).resolve().parents[1],args.output)
    print(json.dumps({'clips':len(result['clips']),'frames':sum(c['frame_count'] for c in result['clips'])}))
