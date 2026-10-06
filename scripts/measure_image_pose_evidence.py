"""Experimental saved-data measurements, separate from the production pipeline.

Consumes prepared videos and saved predictions only. No human annotations,
pose inference, coordinate correction, warning decisions or parameter fitting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np


JOINTS = tuple(f'{side}_{joint}' for joint in ('SHOULDER','ELBOW','WRIST','HIP','KNEE','ANKLE') for side in ('LEFT','RIGHT'))
TORSO = ('LEFT_SHOULDER','RIGHT_SHOULDER','RIGHT_HIP','LEFT_HIP')
PARAMETERS = {
    'corner_max_count':80, 'corner_quality_level':.01, 'corner_min_distance_px':4,
    'corner_block_size':7, 'lk_window_px':[21,21], 'lk_max_level':3,
    'lk_iterations':30, 'lk_epsilon':.01, 'lk_min_eigenvalue':1e-4,
    'minimum_noncollinear_features':3,
    'reseed_policy':'none; earliest existing-gate-supported torso seed, one segment only',
    'feature_validity':'OpenCV forward/backward success, finite in-bounds coordinates; no FB-error cutoff',
    'warning_thresholds':None,
}


def sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1048576),b''):digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as sink:
        json.dump(payload,sink,indent=2,allow_nan=False)
        sink.write('\n')


def point(item: dict | None,width: int,height: int) -> list[float] | None:
    if item is None:return None
    x,y=item.get('x'),item.get('y')
    if not isinstance(x,(int,float)) or not isinstance(y,(int,float)) or not math.isfinite(x+y):return None
    return [float(x*width),float(y*height)]


def gated(item: dict | None,config: dict) -> bool:
    return bool(item and item.get('visibility',0)>=config['min_visibility'] and item.get('presence',0)>=config['min_presence'])


def raw_geometry(pose: dict,width: int,height: int,config: dict) -> dict:
    points={n:point(pose.get(n),width,height) for n in JOINTS}
    centers=[points[n] for n in TORSO]
    center=np.mean(centers,axis=0).tolist() if all(p is not None for p in centers) else None
    result={'torso_center_px':center,'torso_existing_gate_pass':all(gated(pose.get(n),config) for n in TORSO),
            'joints':{},'arms':{}}
    for name in JOINTS:
        p=pose.get(name)
        result['joints'][name]={'xy_px':points[name],
            'visibility':p.get('visibility') if p else None,'presence':p.get('presence') if p else None,
            'existing_gate_pass':gated(p,config)}
    for side in ('LEFT','RIGHT'):
        for label,a,b in (('upper_arm','SHOULDER','ELBOW'),('forearm','ELBOW','WRIST')):
            first,second=points[f'{side}_{a}'],points[f'{side}_{b}']
            if first is not None and second is not None:
                dx,dy=second[0]-first[0],second[1]-first[1]
                length=math.hypot(dx,dy)
                angle=math.degrees(math.atan2(dy,dx)) if length>0 else None
            else:length=angle=None
            result['arms'][f'{side}_{label}']={'length_px':length,'angle_deg':angle,
                'existing_endpoint_gate_pass':gated(pose.get(f'{side}_{a}'),config) and gated(pose.get(f'{side}_{b}'),config)}
    return result


def angular_delta(before: float | None,after: float | None) -> float | None:
    return None if before is None or after is None else (after-before+180)%360-180


def _in_bounds(p: np.ndarray,width: int,height: int) -> bool:
    return bool(np.isfinite(p).all() and 0<=p[0]<width and 0<=p[1]<height)


def flow_pairs(previous: np.ndarray,current: np.ndarray,points: list[list[float]]) -> list[dict]:
    """Record bidirectional KLT diagnostics; FB error is never a warning gate."""
    height,width=previous.shape
    records=[{'index':i,'previous_xy_px':p,'forward_status':False,'backward_status':False,
              'forward_xy_px':None,'backward_xy_px':None,'forward_l1_error':None,
              'backward_l1_error':None,'fb_error_px':None,'numerically_usable':False,
              'reason':'previous_point_out_of_bounds'} for i,p in enumerate(points)]
    indices=[i for i,p in enumerate(points) if _in_bounds(np.asarray(p),width,height)]
    if not indices:return records
    start=np.asarray([points[i] for i in indices],dtype=np.float32).reshape(-1,1,2)
    args={'winSize':tuple(PARAMETERS['lk_window_px']),'maxLevel':PARAMETERS['lk_max_level'],
          'criteria':(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,PARAMETERS['lk_iterations'],PARAMETERS['lk_epsilon']),
          'minEigThreshold':PARAMETERS['lk_min_eigenvalue']}
    forward,status,error=cv2.calcOpticalFlowPyrLK(previous,current,start,None,**args)
    if forward is None:
        for i in indices:records[i]['reason']='forward_flow_unavailable'
        return records
    backward_indices=[]
    for k,i in enumerate(indices):
        r=records[i];r['forward_status']=bool(status[k,0]);r['reason']='forward_flow_failed'
        if r['forward_status'] and _in_bounds(forward[k,0],width,height):
            r['forward_xy_px']=forward[k,0].astype(float).tolist()
            r['forward_l1_error']=float(error[k,0]) if math.isfinite(float(error[k,0])) else None
            backward_indices.append(i)
        elif r['forward_status']:r['reason']='forward_point_out_of_bounds'
    if not backward_indices:return records
    reverse_start=np.asarray([records[i]['forward_xy_px'] for i in backward_indices],dtype=np.float32).reshape(-1,1,2)
    back,bs,be=cv2.calcOpticalFlowPyrLK(current,previous,reverse_start,None,**args)
    if back is None:
        for i in backward_indices:records[i]['reason']='backward_flow_unavailable'
        return records
    for k,i in enumerate(backward_indices):
        r=records[i];r['backward_status']=bool(bs[k,0]);r['reason']='backward_flow_failed'
        if r['backward_status'] and _in_bounds(back[k,0],width,height):
            r['backward_xy_px']=back[k,0].astype(float).tolist()
            r['backward_l1_error']=float(be[k,0]) if math.isfinite(float(be[k,0])) else None
            r['fb_error_px']=float(np.linalg.norm(back[k,0]-np.asarray(points[i])))
            r['numerically_usable']=True;r['reason']=None
        elif r['backward_status']:r['reason']='backward_point_out_of_bounds'
    return records


def cohort_displacement(seed: list,current: list) -> dict:
    """Use exactly the same surviving feature IDs at both endpoints."""
    if len(seed)!=len(current):raise ValueError('Cohort endpoints differ in size')
    result={'feature_count':len(seed),'median_displacement_px':None,'current_hull_area_px2':None,
            'seed_hull_area_px2':None,'reason':'too_few_noncollinear_features'}
    if len(seed)<PARAMETERS['minimum_noncollinear_features']:return result
    a,b=np.asarray(seed,dtype=float),np.asarray(current,dtype=float)
    if not np.isfinite(a).all() or not np.isfinite(b).all():return result
    result['seed_hull_area_px2']=float(cv2.contourArea(cv2.convexHull(a.astype(np.float32))))
    result['current_hull_area_px2']=float(cv2.contourArea(cv2.convexHull(b.astype(np.float32))))
    if np.linalg.matrix_rank(a-a.mean(axis=0))<2 or np.linalg.matrix_rank(b-b.mean(axis=0))<2:return result
    result['median_displacement_px']=np.median(b-a,axis=0).tolist();result['reason']=None
    return result


def discrepancy(raw_delta: list | None,image_delta: list | None) -> float | None:
    if raw_delta is None or image_delta is None:return None
    return float(np.linalg.norm(np.asarray(raw_delta)-np.asarray(image_delta)))


def measure_clip(video: Path,prediction: Path) -> dict:
    filenames=('input_manifest.json','video_metadata.json','keypoints.json','pose_raw.capture.json','pose_clean.clean.json')
    sources={n:{'path':str(prediction/n),'sha256':sha256(prediction/n)} for n in filenames}
    meta,manifest,capture,raw,config=(read(prediction/n) for n in ('video_metadata.json','input_manifest.json','pose_raw.capture.json','keypoints.json','pose_clean.clean.json'))
    if sha256(video)!=meta['sha256'] or video.name!=manifest['video']['file']:raise ValueError('Video binding mismatch')
    total,width,height=meta['frame_count'],meta['width'],meta['height']
    if raw['pitch_id']!=manifest['pitch_id'] or [f['frame_index'] for f in raw['frames']]!=list(range(total)):raise ValueError('Raw timeline mismatch')
    if [f['frame_index'] for f in capture['selection_frames']]!=list(range(total)):raise ValueError('Selection timeline mismatch')
    for f,t in zip(raw['frames'],meta['timestamps_ms'],strict=True):
        if not math.isclose(f['timestamp_ms'],t,abs_tol=1e-7):raise ValueError('Timestamp mismatch')
    sources['video']={'path':str(video),'sha256':sha256(video)}
    reader=cv2.VideoCapture(str(video))
    if not reader.isOpened():raise ValueError('Video cannot be decoded')
    seed_frame=None;seed_center=None;seed_count=0;seed_mask_area=None;seed_cloud={};active={}
    previous_gray=None;previous_geometry=None;frames=[]
    try:
        for index in range(total):
            ok,image=reader.read()
            if not ok or image.shape[:2]!=(height,width):raise ValueError('Decoded timeline/dimensions mismatch')
            gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
            pose={p['name']:p for p in raw['frames'][index]['landmarks']}
            geometry=raw_geometry(pose,width,height,config)
            selection=capture['selection_frames'][index]['status']
            frame={'frame_index':index,'timestamp_ms':meta['timestamps_ms'][index],
                   'selection_status':selection,'raw_geometry':geometry,'seed_frame':seed_frame,
                   'seed_subject_verified':False,'foreground_validated':False,
                   'torso_features':[],'torso_step':None,'torso_cumulative':None,
                   'raw_image_step_disagreement_px':None,'raw_image_cumulative_disagreement_px':None,
                   'local_joint_patch_flow':{},'measurement_state':'insufficient_evidence','reasons':[]}
            if seed_frame is None and selection=='selected' and geometry['torso_existing_gate_pass'] and geometry['torso_center_px']:
                polygon=np.asarray([geometry['joints'][n]['xy_px'] for n in TORSO],dtype=np.float32)
                if all(_in_bounds(p,width,height) for p in polygon):
                    mask=np.zeros_like(gray);cv2.fillConvexPoly(mask,cv2.convexHull(polygon).astype(np.int32),255)
                    corners=cv2.goodFeaturesToTrack(gray,PARAMETERS['corner_max_count'],PARAMETERS['corner_quality_level'],
                        PARAMETERS['corner_min_distance_px'],mask=mask,blockSize=PARAMETERS['corner_block_size'])
                    if corners is not None and cohort_displacement(corners[:,0,:].tolist(),corners[:,0,:].tolist())['reason'] is None:
                        seed_frame=index;seed_center=geometry['torso_center_px'];seed_count=len(corners);seed_mask_area=int(np.count_nonzero(mask))
                        active={k:p.astype(float).tolist() for k,p in enumerate(corners[:,0,:])};seed_cloud=dict(active)
                        frame['seed_frame']=index;frame['measurement_state']='seed_only'
                        frame['torso_features']=[{'feature_id':k,'seed_xy_px':p,'current_xy_px':p,'lifetime_frames':0,
                            'numerically_usable':True,'fb_error_px':None} for k,p in active.items()]
            elif seed_frame is not None and active:
                ids=list(active);flow=flow_pairs(previous_gray,gray,list(active.values()));survivors={}
                first,second,seeds=[],[],[]
                for k,r in zip(ids,flow,strict=True):
                    frame['torso_features'].append({'feature_id':k,'seed_xy_px':seed_cloud[k],
                        'lifetime_frames':index-seed_frame,**r})
                    if r['numerically_usable']:
                        survivors[k]=r['forward_xy_px'];first.append(active[k]);second.append(r['forward_xy_px']);seeds.append(seed_cloud[k])
                frame['torso_step']=cohort_displacement(first,second)
                frame['torso_cumulative']=cohort_displacement(seeds,second)
                if frame['torso_step']['reason'] is None:
                    frame['measurement_state']='numerically_supported_unverified_seed'
                    if previous_geometry['torso_center_px'] is not None and geometry['torso_center_px'] is not None and previous_geometry['torso_existing_gate_pass'] and geometry['torso_existing_gate_pass'] and selection=='selected':
                        delta=(np.asarray(geometry['torso_center_px'])-previous_geometry['torso_center_px']).tolist()
                        frame['raw_image_step_disagreement_px']=discrepancy(delta,frame['torso_step']['median_displacement_px'])
                    if geometry['torso_center_px'] is not None and geometry['torso_existing_gate_pass'] and selection=='selected':
                        delta=(np.asarray(geometry['torso_center_px'])-seed_center).tolist()
                        frame['raw_image_cumulative_disagreement_px']=discrepancy(delta,frame['torso_cumulative']['median_displacement_px'])
                else:frame['reasons'].append(frame['torso_step']['reason'])
                active=survivors
            if frame['measurement_state']=='insufficient_evidence' and not frame['reasons']:
                frame['reasons'].append('no_supported_seed' if seed_frame is None else 'feature_track_exhausted_no_reseed')
            frame['active_feature_count']=len(active);frame['seed_feature_count']=seed_count
            frame['seed_feature_survivor_ratio']=len(active)/seed_count if seed_count else None
            # Adjacent raw-joint patches are separate probes, not torso re-seeding.
            if previous_gray is not None:
                names=[n for n in JOINTS if previous_geometry['joints'][n]['xy_px'] is not None]
                pairs=flow_pairs(previous_gray,gray,[previous_geometry['joints'][n]['xy_px'] for n in names])
                for n,r in zip(names,pairs,strict=True):
                    current=geometry['joints'][n]['xy_px']
                    raw_delta=(np.asarray(current)-r['previous_xy_px']).tolist() if current else None
                    image_delta=(np.asarray(r['forward_xy_px'])-r['previous_xy_px']).tolist() if r['numerically_usable'] else None
                    frame['local_joint_patch_flow'][n]={**r,'raw_current_xy_px':current,
                        'raw_image_disagreement_px':discrepancy(raw_delta,image_delta),
                        'joint_location_verified':False,'raw_existing_gate_at_both_ends':previous_geometry['joints'][n]['existing_gate_pass'] and geometry['joints'][n]['existing_gate_pass']}
                for n,item in geometry['arms'].items():
                    old=previous_geometry['arms'][n]
                    item['angle_step_deg']=angular_delta(old['angle_deg'],item['angle_deg'])
                    item['length_step_px']=item['length_px']-old['length_px'] if item['length_px'] is not None and old['length_px'] is not None else None
            frames.append(frame);previous_gray=gray;previous_geometry=geometry
        if reader.read()[0]:raise ValueError('Extra decoded video frames')
    finally:reader.release()
    for value in sources.values():
        if sha256(Path(value['path']))!=value['sha256']:raise ValueError('Input changed during measurement')
    return {'pitch_id':manifest['pitch_id'],'pitcher_id':manifest['pitcher']['id'],'throws':manifest['pitcher']['throws'],
        'width':width,'height':height,'total_frames':total,'sources':sources,
        'existing_confidence_gate':{'visibility':config['min_visibility'],'presence':config['min_presence']},
        'seed_frame':seed_frame,'seed_mask_area_px2':seed_mask_area,'seed_feature_count':seed_count,
        'seed_subject_verified':False,'foreground_validated':False,'reset_frames':[],
        'frames':frames,'warning_predictions':None,'pose_inference_rerun':False}


def run_measurements(input_dir: Path,predictions_root: Path,output_root: Path) -> Path:
    if output_root.exists():raise FileExistsError(f'Output must be new: {output_root}')
    directories=sorted(p.parent for p in predictions_root.glob('*/*/input_manifest.json'))
    if not directories:raise ValueError('No saved pitch prediction folders')
    output_root.mkdir(parents=True)
    results=[]
    for prediction in directories:
        manifest=read(prediction/'input_manifest.json');filename=manifest['video']['file']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',manifest['pitch_id']):raise ValueError('Invalid pitch identifier')
        if Path(filename).name!=filename:raise ValueError('Prepared filename must be a basename')
        result=measure_clip(input_dir/filename,prediction)
        if any(r['pitch_id']==result['pitch_id'] for r in results):raise ValueError('Duplicate pitch ID')
        write(output_root/result['pitch_id']/'image_pose_measurements.json',result)
        results.append({'pitch_id':result['pitch_id'],'total_frames':result['total_frames'],
            'seed_frame':result['seed_frame'],'seed_feature_count':result['seed_feature_count'],
            'numerically_supported_frames':sum(f['measurement_state']=='numerically_supported_unverified_seed' for f in result['frames']),
            'measurement':str(output_root/result['pitch_id']/'image_pose_measurements.json')})
    params_json=json.dumps(PARAMETERS,sort_keys=True).encode()
    write(output_root/'measurement_run.json',{'status':'measurements_only','producer_code_sha256':sha256(Path(__file__)),
        'opencv_version':cv2.__version__,'numpy_version':np.__version__,'parameters':PARAMETERS,
        'parameters_sha256':hashlib.sha256(params_json).hexdigest(),'results':results,
        'human_annotation_inputs':[],'warning_thresholds':None,'warning_predictions_generated':False,
        'limitations':['Seed and foreground are unverified. Numerically supported flow is not coordinate truth.',
                       'FB error has no cutoff; all valid-status feature quality must be inspected.',
                       'Single seed only. Lost evidence stays missing; no reseed or coordinate repair.']})
    return output_root/'measurement_run.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_dir',type=Path);parser.add_argument('predictions_root',type=Path);parser.add_argument('output_root',type=Path)
    args=parser.parse_args()
    print(run_measurements(args.input_dir,args.predictions_root,args.output_root))
