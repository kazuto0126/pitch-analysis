"""Source-bound first-frame preparation for the standard seeded skeleton flow."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import cv2

from .contracts import load_input
from .native_person_boxes import prepare_detector_input, select_person_box
from .native_person_box_transport import IsolatedDetectorTransport
from .native_pose_io import BoundReader, read_json, reference, sha256, write_json
from .native_pose_live import _utc
from .native_progress_log import append_event
from .video.validation import validate_mp4


def prepare_skeleton(root, video_path, metadata_path, runtime_config_path, output, *,
                     fps_fraction, detector_factory=None):
    """Detect frame0 once; never choose a person or run pose for the reviewer.

    The rational FPS is supplied from the source delivery/technical record and
    checked against every decoded frame. Canvas/ROI cover this prepared source,
    without copying another pitcher's absolute crop coordinates.
    """
    root=Path(root).resolve(strict=True)
    video,metadata,runtime_path=[Path(path).resolve(strict=True) for path in (video_path,metadata_path,runtime_config_path)]
    output=Path(output).resolve()
    if any(not path.is_relative_to(root) for path in (video,metadata,runtime_path)):
        raise ValueError('All preparation sources must be within project')
    if output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('A fresh project analysis_results folder is required')
    payload=load_input(video,metadata)
    if payload['video']['camera_view']!='rear_centerfield_broadcast':
        raise ValueError('Seeded skeleton currently requires rear_centerfield_broadcast')
    fps=Fraction(fps_fraction)
    if fps<=0:raise ValueError('Positive source fractional FPS required')
    runtime=read_json(runtime_path)
    if runtime.get('schema_version')!='seeded-skeleton-runtime-v1':
        raise ValueError('Expected seeded-skeleton-runtime-v1')
    keys=('runtime_ref','model_ref','worker_ref','detector_model_ref','detector_worker_ref')
    refs=runtime.get('source_refs',[])
    if any(runtime.get(key) not in refs for key in keys):raise ValueError('All runtime/model/worker refs must be declared')
    reader=BoundReader(root,refs)
    for ref in refs:reader.path(ref)
    technical=validate_mp4(video)
    width,height=technical['width'],technical['height']
    capture=cv2.VideoCapture(str(video));first=None;decoded=0
    try:
        while True:
            okay,image=capture.read()
            if not okay:break
            timestamp=float(Fraction(decoded*1000,1)/fps)
            actual=capture.get(cv2.CAP_PROP_POS_MSEC)
            if image.shape!=(height,width,3) or not math.isfinite(actual) or abs(actual-timestamp)>=1:
                raise ValueError(f'Source fractional timeline differs at frame{decoded}')
            if decoded==0:first=image.copy()
            decoded+=1
    finally:capture.release()
    if first is None or decoded!=technical['frame_count']:
        raise ValueError('Source decode timeline incomplete')
    video_ref,metadata_ref=reference(root,video),reference(root,metadata)
    canvas=[0,0,width,height];roi=[0.,0.,1.,1.]
    identity={'video_ref':video_ref,'metadata_ref':metadata_ref,'runtime_ref':reference(root,runtime_path),
              'fps_fraction':str(fps),'crop_xyxy_px':canvas,'operator_roi':roi}
    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    claims=root/'analysis_results/seeded_skeleton_preparation_claims';claims.mkdir(parents=True,exist_ok=True)
    claim=claims/(key+'.json')
    if claim.exists():raise ValueError('This source/geometry already has a preparation claim; reuse saved frame0')
    output.mkdir(parents=True,exist_ok=False)
    write_json(claim,{'source':identity,'output':output.relative_to(root).as_posix(),
                      'started_at_utc':_utc(),'automatic_retry':False})
    progress=output/'progress';progress.mkdir()
    worker_dir=output/'detector_worker';worker_dir.mkdir()
    detector=None
    receipt={'schema_version':'seeded-skeleton-preparation-execution-v1','state':'running',
             'video_ref':video_ref,'pitch_id':payload['pitch_id'],'frame_count':decoded,
             'detector_calls_attempted':0,'detector_calls_completed':0,'pose_calls':0,'operator_seed_selected':False}
    append_event(progress,'started',receipt)
    try:
        factory=detector_factory or IsolatedDetectorTransport
        with factory(root/runtime['runtime_ref']['path'],root/runtime['detector_worker_ref']['path'],
                     root/runtime['detector_model_ref']['path'],expected_model_sha256=runtime['detector_model_ref']['sha256'],
                     max_calls=1,output_dir=worker_dir) as detector:
            if any(detector.metadata.get('runtime',{}).get(k)!=v for k,v in runtime['expected_runtime'].items()):
                raise ValueError('Approved detector runtime differs')
            tensor,geometry=prepare_detector_input(first,canvas)
            selection=select_person_box(detector.run(tensor),geometry,roi)
            frame0={**selection,'frame_index':0,'timestamp_ms':0.,
                    'decoded_bgr_sha256':hashlib.sha256(first.tobytes()).hexdigest(),'detector_geometry':geometry}
            write_json(output/'first_frame_candidates.json',frame0)
            receipt.update(detector_calls_attempted=detector.calls_attempted,detector_calls_completed=detector.calls_completed)
        display=[];rendered=first.copy()
        palette=[(0,210,255),(255,170,0),(255,100,220),(80,240,80),(200,200,50)]
        for number,candidate in enumerate([c for c in frame0['candidates'] if c['eligible']],1):
            bbox=candidate['bbox_original_xyxy_px'];x1,y1,x2,y2=bbox
            color=palette[(number-1)%len(palette)]
            cv2.rectangle(rendered,(max(0,int(x1)),max(0,int(y1))),(min(width-1,int(x2)),min(height-1,int(y2))),color,2)
            origin=(max(0,min(width-50,int(x1))),max(28,min(height-10,int(y1)+25)))
            cv2.putText(rendered,str(number),origin,cv2.FONT_HERSHEY_SIMPLEX,.95,(0,0,0),5,cv2.LINE_AA)
            cv2.putText(rendered,str(number),origin,cv2.FONT_HERSHEY_SIMPLEX,.95,color,2,cv2.LINE_AA)
            display.append({'display_number':number,'output_index':candidate['output_index'],'bbox_original_xyxy_px':bbox})
        if not cv2.imwrite(str(output/'seed_candidates.png'),rendered):raise ValueError('Could not write seed image')
        sources=[video_ref,metadata_ref,reference(root,runtime_path),*refs,
                 reference(root,output/'first_frame_candidates.json'),reference(root,output/'seed_candidates.png'),
                 *[reference(root,path) for path in worker_dir.iterdir() if path.is_file()]]
        preparation={'schema_version':'seeded-skeleton-preparation-v1','status':'awaiting_operator_seed',
            'pitch_id':payload['pitch_id'],'pitcher_id':payload['pitcher']['id'],
            'video_ref':video_ref,'metadata_ref':metadata_ref,'frame_count':decoded,'width':width,'height':height,
            'fps_fraction':str(fps),'crop_xyxy_px':canvas,'operator_roi':roi,
            **{name:runtime[name] for name in (*keys,'expected_runtime')},
            'frame0_ref':reference(root,output/'first_frame_candidates.json'),
            'seed_image_ref':reference(root,output/'seed_candidates.png'),'source_refs':sources,
            'display_choices':display,'operator_seed':None,'pose_calls_during_preparation':0,
            'first_frame_detector_calls':1,'quality_status':'not_calibrated','usable_for_analysis':None,
            'sampling_canvas_source':'entire source MP4; no borrowed pitcher-specific crop',
            'preparation_implementation_sha256':sha256(Path(__file__).resolve()),
            'prepared_at_utc':_utc()}
        write_json(output/'preparation.json',preparation)
        receipt.update(state='awaiting_operator_seed',eligible_people=len(display),preparation_ref=reference(root,output/'preparation.json'))
        append_event(progress,'prepared',receipt);write_json(output/'prepare_receipt.json',receipt)
    except BaseException as error:
        if detector is not None:receipt.update(detector_calls_attempted=detector.calls_attempted,detector_calls_completed=detector.calls_completed)
        receipt.update(state='failed',failure=f'{type(error).__name__}: {error}')
        try:append_event(progress,'failed',receipt)
        except Exception as record_error:error.add_note('Could not save failure progress: '+str(record_error))
        raise
    return preparation
