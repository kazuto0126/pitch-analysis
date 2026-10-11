"""Evaluate sealed, GT-blind support warnings against the original major labels."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from check_movenet_compatibility import bound,sha,write
from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.phase2_evaluation import frame_ranges


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify_tracking_timeline(tracking,frames,capture,total):
    expected=list(range(total))
    selected=capture['selection_frames']
    if ([f['frame_index'] for f in tracking['frames']]!=expected or
        [f['frame_index'] for f in selected]!=expected or
        [f['frame_index'] for f in frames]!=expected):
        raise ValueError('Original tracking/capture/support frame order differs')
    for frame,old,selection in zip(frames,tracking['frames'],selected,strict=True):
        if (old['selection_status']!=selection['status'] or
            not math.isfinite(frame['native_timestamp_ms']) or
            not math.isfinite(selection['timestamp_ms']) or
            abs(frame['native_timestamp_ms']-selection['timestamp_ms'])>1):
            raise ValueError('Original tracking and support capture timeline differs')


def score(intervals, predictions, abstentions, total):
    """Fixed non-seed denominator; abstention does not remove human positives."""
    eligible=set(range(1,total))
    positive=set()
    excluded=set()
    occupied=set()
    for interval in intervals:
        start,end=interval['start_frame'],interval['end_frame']
        if not 0<=start<=end<total:raise ValueError('Invalid human span')
        span=set(range(start,end+1))
        if span & occupied:raise ValueError('Overlapping human spans')
        occupied |= span
        status=interval.get('status','confirmed')
        if status=='confirmed':positive |= span
        elif status in ('uncertain','not_observable'):excluded |= span
        else:raise ValueError('Unknown human status')
    positive &= eligible
    negative=eligible-positive-excluded
    scorable=positive|negative
    predicted=set(predictions)
    abstain=set(abstentions)
    if not (predicted|abstain)<=set(range(total)) or predicted & abstain:
        raise ValueError('Invalid or contradictory prediction states')
    cells={'tp':positive & predicted,'fn':positive-predicted,'fp':negative & predicted,'tn':negative-predicted}
    tp,fp=len(cells['tp']),len(cells['fp'])
    return {'non_seed_frames':len(eligible),'human_positive':len(positive),'human_negative':len(negative),
        'human_excluded':len(eligible&excluded),'scorable_frames':len(scorable),
        **{key:len(value) for key,value in cells.items()},
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/len(positive) if positive else None,
        'fpr':fp/len(negative) if negative else None,
        'abstention_positive':len(abstain&positive),'abstention_negative':len(abstain&negative),
        'decision_coverage':len(scorable-abstain)/len(scorable) if scorable else None,
        'ranges':{key:frame_ranges(value) for key,value in cells.items()}}


def aggregate(rows):
    keys=('non_seed_frames','human_positive','human_negative','human_excluded','scorable_frames',
          'tp','fn','fp','tn','abstention_positive','abstention_negative')
    result={key:sum(row[key] for row in rows) for key in keys}
    tp,fp,positive,negative=(result[k] for k in ('tp','fp','human_positive','human_negative'))
    result.update(precision=tp/(tp+fp) if tp+fp else None,recall=tp/positive if positive else None,
                  fpr=fp/negative if negative else None,
                  decision_coverage=(result['scorable_frames']-result['abstention_positive']-
                       result['abstention_negative'])/result['scorable_frames'] if result['scorable_frames'] else None)
    return result


def evaluate(root,plan_path,run_path,output):
    root,plan_path,run_path,output=map(lambda p:Path(p).resolve(),(root,plan_path,run_path,output))
    if output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('Exclusive evaluation output required')
    plan,run=read(plan_path),read(run_path)
    plan_sha,run_sha=sha(plan_path),sha(run_path)
    if plan['status']!='frozen_before_support_evaluation':raise ValueError('Unfrozen evaluator plan')
    producer_path=bound(root,plan['producer_plan'])
    producer=read(producer_path)
    for entry in plan['code'].values():bound(root,entry)
    if (run['status']!='sealed_movenet_support_diagnostics' or
        run['plan_sha256']!=sha(producer_path) or run['human_annotation_inputs']!=[] or
        run['source_frames']!=592 or run['non_seed_frames']!=587 or
        run['warning_policy']!=producer['warning_policy'] or
        run['producer_sha256']!=producer['code']['producer_code']['sha256'] or
        run['pose_inference_calls']!=0 or run['tracker_inference_calls']!=0 or run['production_adoption']):
        raise ValueError('Unbound or GT-contaminated support receipt')
    if len(run['clips'])!=len(plan['clips']):raise ValueError('Incomplete clip denominator')
    reports=[]
    for setup,result in zip(plan['clips'],run['clips'],strict=True):
        target=setup['target'];name,total=target['pitch_id'],target['total_frames']
        for entry in setup['sources'].values():bound(root,entry)
        data=read(bound(root,result))
        matching=next(c for c in producer['clips'] if c['target']['pitch_id']==name)
        if (result['pitch_id']!=name or data['status']!='sealed_support_diagnostics_only' or
                data['target']!=target or data['source_references']!=matching['sources'] or
                data['warning_policy']!=producer['warning_policy'] or
                data['producer_sha256']!=producer['code']['producer_code']['sha256'] or
                data['plan_sha256']!=sha(producer_path) or data['human_annotation_inputs']!=[]):
            raise ValueError('Wrong source/clip/plan support binding')
        frames=data['frames']
        if [f['frame_index'] for f in frames]!=list(range(total)) or any(
                f['effectiveness_eligible']!=(f['frame_index']!=0) for f in frames):
            raise ValueError('Changed frame denominator')
        if any(f['status'] not in ('warning','no_warning','insufficient_evidence') for f in frames):
            raise ValueError('Invalid support state')
        canonical=read(root/setup['sources']['canonical_review']['path'])
        validate_ground_truth(canonical,source_video_path=root/setup['sources']['video']['path'])
        if (canonical['annotation_status']!='reviewed' or canonical['review_profile']!='phase2_full_review' or
            (canonical['source_video']['pitch_id'],canonical['source_video']['total_frames'],canonical['source_video']['sha256'])
            !=(name,total,setup['sources']['video']['sha256'])):
            raise ValueError('Wrong human review/source')
        tracking=read(root/setup['sources']['tracking']['path'])
        if tracking['pitch_id']!=name or tracking['total_frames']!=total or [f['frame_index'] for f in tracking['frames']]!=list(range(total)):
            raise ValueError('Wrong original tracking timeline')
        capture=read(bound(root,matching['sources']['capture']))
        verify_tracking_timeline(tracking,frames,capture,total)
        old={f['frame_index'] for f in tracking['frames'] if f['selection_status']!='selected' or f['warnings']}
        new={f['frame_index'] for f in frames if f['status']=='warning'}
        abstain={f['frame_index'] for f in frames if f['status']=='insufficient_evidence'}
        intervals=canonical['labels']['major_pose_failure_intervals']
        reports.append({'pitch_id':name,'source_frames':total,
            'state_counts_non_seed':dict(Counter(f['status'] for f in frames[1:])),
            'association_counts_non_seed':dict(Counter(f['association']['status'] for f in frames[1:])),
            'original_tracking_screen':score(intervals,old,set(),total),
            'new_geometric_conflict_screen':score(intervals,new,abstain,total),
            'additive_union_screen':score(intervals,old|new,abstain-old,total)})
    if sum(c['source_frames'] for c in reports)!=592:raise ValueError('Incomplete cohort')
    for entry in plan['code'].values():bound(root,entry)
    bound(root,plan['producer_plan'])
    for setup in plan['clips']:
        for entry in setup['sources'].values():bound(root,entry)
    for entry in run['clips']:bound(root,entry)
    if sha(plan_path)!=plan_sha or sha(run_path)!=run_sha:raise ValueError('Evidence changed')
    output.mkdir()
    report={'status':'complete_offline_support_warning_evaluation','plan_sha256':plan_sha,'run_sha256':run_sha,
        'source_frames':592,'non_seed_frames':587,'clips':reports,
        'aggregate':{key:aggregate([c[key] for c in reports]) for key in
             ('original_tracking_screen','new_geometric_conflict_screen','additive_union_screen')},
        'pose_inference_calls':0,'tracker_inference_calls':0,'production_adoption':False,
        'new_model_identity_or_joint_accuracy':None,'phase2_automatic_reliability':'NOT PASSED',
        'interpretation':'Warnings screen original VIDEO major labels. Geometry conflict is not confirmed identity or anatomy. Abstentions remain in primary denominators; known development data, no generalization claim.'}
    write(output/'support_evaluation.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path);parser.add_argument('run',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=evaluate(Path(__file__).resolve().parents[1],args.plan,args.run,args.output)
    print(json.dumps(result['aggregate']))
