"""Evaluator-only comparison of frozen experimental measurements with human GT.

Reports continuous evidence distributions, coverage and conditional rank AUC.
Does not fit thresholds, emit warnings or modify any source prediction/label.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw,ImageFont

from pitch_analysis.ground_truth import validate_ground_truth,FULL_JOINT_LABELS
from pitch_analysis.manual_keypoints import validate_manual_keypoints


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    with p.open('x',encoding='utf-8') as sink:json.dump(obj,sink,indent=2,allow_nan=False);sink.write('\n')
def stats(values):
    values=[v for v in values if v is not None]
    return {'n':len(values),'median':float(np.median(values)) if values else None,
        'p95':float(np.percentile(values,95)) if values else None,
        'p99':float(np.percentile(values,99)) if values else None,'max':max(values) if values else None}
def auc(positive,negative):
    if not positive or not negative:return None
    difference=np.asarray(positive)[:,None]-np.asarray(negative)[None,:]
    return float(np.mean((difference>0)+.5*(difference==0)))
def conditional(values,labels,positive='confirmed',negative='known_negative'):
    groups={state:[v for v,label in zip(values,labels,strict=True) if label==state and v is not None] for state in (positive,negative)}
    return {'positive_label':positive,'negative_label':negative,
        'human_positive_total':labels.count(positive),'human_negative_total':labels.count(negative),
        'positive_with_measurement':stats(groups[positive]),'negative_with_measurement':stats(groups[negative]),
        'positive_without_measurement':labels.count(positive)-len(groups[positive]),
        'negative_without_measurement':labels.count(negative)-len(groups[negative]),
        'conditional_rank_auc_higher_is_positive':auc(groups[positive],groups[negative]),
        'excluded_human_counts':dict(Counter(s for s in labels if s not in (positive,negative))),
        'interpretation':'Exploratory separation on measured subset; not warning recall, independent validation or a fitted threshold.'}
def interval_timeline(items,total):
    result=['known_negative']*total
    for item in items:
        result[item['start_frame']:item['end_frame']+1]=[item.get('status','confirmed')]*(item['end_frame']-item['start_frame']+1)
    return result
def joint_timeline(items,total):
    result=[None]*total
    for item in items:result[item['start_frame']:item['end_frame']+1]=[item['status']]*(item['end_frame']-item['start_frame']+1)
    if not all(result):raise ValueError('Human joint timeline incomplete')
    return result


def comparison_reason(frames,index):
    f=frames[index];current=f['raw_geometry'];reasons=[]
    if index==0:return ['no_previous_frame']
    before=frames[index-1]['raw_geometry']
    if current['torso_center_px'] is None:reasons.append('current_raw_torso_missing')
    elif not current['torso_existing_gate_pass']:reasons.append('current_raw_torso_below_existing_gate')
    if before['torso_center_px'] is None:reasons.append('previous_raw_torso_missing')
    elif not before['torso_existing_gate_pass']:reasons.append('previous_raw_torso_below_existing_gate')
    if f['selection_status']!='selected':reasons.append('current_selector_not_selected')
    if f['torso_step'] is None or f['torso_step']['median_displacement_px'] is None:reasons.append('image_cohort_motion_unavailable')
    return reasons


def evaluate(measurement_root: Path,baseline: Path,manual_path: Path,output: Path) -> dict:
    if output.exists():raise FileExistsError(f'Output must be new: {output}')
    run=read(measurement_root/'measurement_run.json')
    if run['status']!='measurements_only' or run['human_annotation_inputs'] or run['warning_thresholds'] is not None:raise ValueError('Not a frozen measurement-only run')
    producer=Path(__file__).with_name('measure_image_pose_evidence.py')
    if sha(producer)!=run['producer_code_sha256']:raise ValueError('Producer code changed since measurement')
    parameter_hash=hashlib.sha256(json.dumps(run['parameters'],sort_keys=True).encode()).hexdigest()
    if parameter_hash!=run['parameters_sha256']:raise ValueError('Measurement parameters changed')
    source_hashes={str(measurement_root/'measurement_run.json'):sha(measurement_root/'measurement_run.json'),str(manual_path):sha(manual_path)}
    manual=read(manual_path);validate_manual_keypoints(manual)
    if manual['annotation_status']!='reviewed':raise ValueError('Coordinates require human-reviewed reference')
    output.mkdir(parents=True)
    clips=[];cases=[];all_frames=[];measured={};all_groups={}
    for entry in run['results']:
        pitch=entry['pitch_id'];path=measurement_root/pitch/'image_pose_measurements.json';data=read(path)
        gtp=baseline/'ground_truth'/pitch/'ground_truth.json';gt=read(gtp);validate_ground_truth(gt)
        if gt['annotation_status']!='reviewed' or gt['review_profile']!='phase2_full_review':raise ValueError('Full canonical review required')
        if gt['source_video']['sha256']!=data['sources']['video']['sha256'] or gt['source_video']['pitch_id']!=pitch:raise ValueError('Human/video binding mismatch')
        frames=data['frames'];total=data['total_frames'];height=data['height']
        if total!=gt['source_video']['total_frames'] or [f['frame_index'] for f in frames]!=list(range(total)):raise ValueError('Frame timeline mismatch')
        if any(f['foreground_validated'] or f['seed_subject_verified'] for f in frames):raise ValueError('Unexpected identity validation claim')
        for source in data['sources'].values():
            p=Path(source['path'])
            if sha(p)!=source['sha256']:raise ValueError('Measurement source changed')
            source_hashes[str(p)]=source['sha256']
        source_hashes[str(path)]=sha(path);source_hashes[str(gtp)]=sha(gtp)
        labels=interval_timeline(gt['labels']['major_pose_failure_intervals'],total)
        feature_errors=[r['fb_error_px'] for f in frames for r in f['torso_features'] if r.get('fb_error_px') is not None]
        fb_stats=stats(feature_errors)
        major={}
        for name in ('raw_image_step_disagreement_px','raw_image_cumulative_disagreement_px'):
            values=[f[name]/height if f[name] is not None else None for f in frames]
            major[name.removesuffix('_px')+'_image_height']=conditional(values,labels)
            unit_name=name.removesuffix('_px')+'_image_height'
            bucket=all_groups.setdefault(unit_name,{'values':[],'labels':[]});bucket['values'].extend(values);bucket['labels'].extend(labels)
        sides=data['throws'];roles={'throwing_shoulder':sides+'_SHOULDER','throwing_elbow':sides+'_ELBOW','throwing_wrist':sides+'_WRIST',
            'lead_hip':('LEFT' if sides=='RIGHT' else 'RIGHT')+'_HIP','lead_knee':('LEFT' if sides=='RIGHT' else 'RIGHT')+'_KNEE',
            'lead_ankle':('LEFT' if sides=='RIGHT' else 'RIGHT')+'_ANKLE'}
        joints={}
        for name in FULL_JOINT_LABELS:
            role=name.removesuffix('_reliability');joint=roles[role]
            human=joint_timeline(gt['labels'][name],total)
            values=[f['local_joint_patch_flow'].get(joint,{}).get('raw_image_disagreement_px') for f in frames]
            normalized=[v/height if v is not None else None for v in values]
            joints[role]={'landmark':joint,'local_patch_disagreement_image_height':conditional(normalized,human,'unreliable','reliable'),
                'local_patch_fb_error_px':stats([f['local_joint_patch_flow'].get(joint,{}).get('fb_error_px') for f in frames]),
                'joint_location_verified':False}
            if role in ('throwing_elbow','throwing_wrist'):
                key=sides+('_upper_arm' if role=='throwing_elbow' else '_forearm')
                length=[f['raw_geometry']['arms'][key]['length_px'] for f in frames]
                angle=[f['raw_geometry']['arms'][key].get('angle_step_deg') for f in frames]
                joints[role]['raw_projected_length_image_height']=conditional([v/height if v is not None else None for v in length],human,'unreliable','reliable')
                joints[role]['raw_angle_step_abs_deg']=conditional([abs(v) if v is not None else None for v in angle],human,'unreliable','reliable')
        ratio=[]
        for f in frames:
            cohort=f['torso_cumulative']
            ratio.append(cohort['current_hull_area_px2']/cohort['seed_hull_area_px2'] if cohort and cohort['seed_hull_area_px2'] else None)
            all_frames.append({'pitch_id':pitch,'frame_index':f['frame_index'],'major_failure_human_label':labels[f['frame_index']],
                'raw_image_step_disagreement_px':f['raw_image_step_disagreement_px'],
                'raw_image_cumulative_disagreement_px':f['raw_image_cumulative_disagreement_px'],
                'raw_comparison_unavailable_reasons':comparison_reason(frames,f['frame_index']) if f['raw_image_step_disagreement_px'] is None else [],
                'measurement_state':f['measurement_state'],'foreground_validated':False})
        clips.append({'pitch_id':pitch,'total_frames':total,'seed_frame':data['seed_frame'],'seed_features':data['seed_feature_count'],
            'final_surviving_features':frames[-1]['active_feature_count'],
            'numerically_supported_frames':sum(f['measurement_state']=='numerically_supported_unverified_seed' for f in frames),
            'major_failure_evidence':major,'joint_evidence':joints,'torso_fb_error_px':fb_stats,
            'feature_hull_expansion_ratio':stats(ratio),'seed_subject_verified':False,'foreground_validated':False})
        measured[pitch]=(data,gt)
        # Every clip gets a plot of available measurements and their quality.
        fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
        index=list(range(total))
        axes[0].plot(index,[f['raw_image_step_disagreement_px'] for f in frames],color='#c27726',label='Adjacent-step discrepancy')
        axes[0].plot(index,[f['raw_image_cumulative_disagreement_px'] for f in frames],color='#4368bd',label='Seed-to-current discrepancy')
        axes[0].set(ylabel='Discrepancy (px)',title=f'{pitch} | candidate image motion; seed/foreground UNVERIFIED');axes[0].legend(fontsize=8)
        medians=[];p95=[]
        for f in frames:
            s=stats([r.get('fb_error_px') for r in f['torso_features']]);medians.append(s['median']);p95.append(s['p95'])
        axes[1].plot(index,medians,label='FB median');axes[1].plot(index,p95,label='FB P95')
        axes[1].set(ylabel='Round-trip error (px)');axes[1].legend(fontsize=8)
        axes[2].plot(index,[f['active_feature_count']/data['seed_feature_count'] if data['seed_feature_count'] else None for f in frames],label='Seed feature survival',color='#26834b')
        axes[2].set(ylabel='Survival fraction',xlabel='Frame (0-based)',ylim=(0,1.05));axes[2].legend(fontsize=8)
        for ax in axes:
            for region in gt['labels']['major_pose_failure_intervals']:
                if region.get('status','confirmed')=='confirmed':ax.axvspan(region['start_frame']-.5,region['end_frame']+.5,color='#8c9bab',alpha=.2)
            ax.grid(alpha=.2)
        fig.savefig(output/f'{pitch}_timeline.png',dpi=150);plt.close(fig)

    mpitch=manual['source_video']['pitch_id'];data,gt=measured[mpitch]
    if manual['source_video']['sha256']!=data['sources']['video']['sha256']:raise ValueError('Coordinate/video binding mismatch')
    raw=read(Path(data['sources']['keypoints.json']['path']))
    raw_frames={f['frame_index']:{p['name']:p for p in f['landmarks']} for f in raw['frames']}
    for human_frame in manual['frames']:
        i=human_frame['frame_index'];f=data['frames'][i]
        for m in human_frame['joints']:
            if m['status']!='visible':continue
            p=raw_frames[i].get(m['name']);error=None
            if p:error=math.hypot(p['x']*data['width']-m['x_px'],p['y']*data['height']-m['y_px'])
            cases.append({'pitch_id':mpitch,'frame_index':i,'joint':m['name'],'manual_state':'visible','raw_coordinate_error_px':error,
                'local_patch_disagreement_px':f['local_joint_patch_flow'].get(m['name'],{}).get('raw_image_disagreement_px'),
                'local_patch_fb_error_px':f['local_joint_patch_flow'].get(m['name'],{}).get('fb_error_px')})
    # A faithful original-frame image to inspect feature scatter; labels are evaluator-only.
    video=cv2.VideoCapture(data['sources']['video']['path'])
    selected={data['seed_frame'],38,95,112} if data['total_frames']>112 else {data['seed_frame'],data['total_frames']-1}
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    bd=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',22)
    panels=[]
    for i in range(data['total_frames']):
        ok,image=video.read()
        if not ok:raise ValueError('Evaluation source decode failed')
        if i not in selected:continue
        picture=Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(picture)
        f=data['frames'][i]
        for feature in f['torso_features']:
            xy=feature.get('forward_xy_px',feature.get('current_xy_px'))
            if xy is None:continue
            error=feature.get('fb_error_px')
            value=min(math.log1p(error)/math.log(101),1) if error is not None else 0
            color=tuple(int(c*255) for c in plt.colormaps['turbo'](value)[:3])
            x,y=xy;draw.ellipse((x-3,y-3,x+3,y+3),fill=color,outline='white')
        torso=[f['raw_geometry']['joints'][n]['xy_px'] for n in ('LEFT_SHOULDER','RIGHT_SHOULDER','RIGHT_HIP','LEFT_HIP')]
        if all(p is not None for p in torso):draw.line([tuple(p) for p in torso+[torso[0]]],fill=(255,150,30),width=2)
        panel=Image.new('RGB',(data['width'],data['height']+115),(17,23,35));d=ImageDraw.Draw(panel)
        d.text((10,7),f'Frame {i}: {f["active_feature_count"]}/{data["seed_feature_count"]} features',font=bd,fill='white')
        d.text((10,38),'Raw torso orange; KLT seed unverified',font=font,fill='white')
        panel.paste(picture,(0,70));d.text((10,data['height']+80),'Color: log FB error, display capped at 100px',font=font,fill='white')
        panels.append(panel)
    video.release()
    combined=Image.new('RGB',(sum(p.width for p in panels),panels[0].height),(17,23,35));offset=0
    for p in panels:combined.paste(p,(offset,0));offset+=p.width
    combined.save(output/f'{mpitch}_feature_scatter.png')
    aggregate={k:conditional(v['values'],v['labels']) for k,v in all_groups.items()}
    summary={'status':'measurement_comparison_only','total_frames':sum(c['total_frames'] for c in clips),
        'parameters_sha256':run['parameters_sha256'],'producer_code_sha256':run['producer_code_sha256'],
        'evaluator_code_sha256':sha(Path(__file__)),'clips':clips,'pooled_major_failure_continuous_evidence':aggregate,
        'visible_coordinate_comparison_count':len(cases),'nonvisible_coordinate_comparisons':0,
        'warning_predictions_generated':False,'warning_thresholds':None,'phase2_acceptance':'in_progress',
        'limits':['Conditional AUC uses only measured subset; missing evidence and positive coverage are shown explicitly.',
                  'No foreground/identity verification, threshold selection, fitted classifier or independent holdout.',
                  'Feature status success and small FB errors do not prove features remain on the pitcher.',
                  'Human reliability judges raw overlay; patch flow is not a human-visible joint estimate.']}
    write(output/'evaluation_summary.json',summary);write(output/'per_frame_evaluation.json',{'frames':all_frames})
    write(output/'visible_coordinate_evidence.json',{'rows':cases})
    if any(sha(Path(p))!=h for p,h in source_hashes.items()):raise ValueError('Evaluation source changed')
    write(output/'evidence_integrity_check.json',{'status':'passed','source_hashes':source_hashes,'all_sources_unchanged':True,
        'producer_and_parameters_hash_matched':True,'ground_truth_input_only_to_evaluator':True,
        'coordinate_eligible_points':len(cases),'new_warning_predictions':False})
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurement_root',type=Path);parser.add_argument('baseline_root',type=Path)
    parser.add_argument('manual_reference',type=Path);parser.add_argument('output_root',type=Path)
    args=parser.parse_args()
    summary=evaluate(args.measurement_root,args.baseline_root,args.manual_reference,args.output_root)
    print(json.dumps({'status':summary['status'],'frames':summary['total_frames'],'visible_points':summary['visible_coordinate_comparison_count']}))
