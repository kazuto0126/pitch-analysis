"""Isolated ONNX CPU worker. Only frozen input tensors, never human annotations."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
import numpy as np

SHAPES = ((1, 17, 384), (1, 17, 512))


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, data):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def runtime():
    return {'python': platform.python_version(), 'python_executable_sha256': sha(sys.executable),
        'numpy': version('numpy'), 'onnxruntime': version('onnxruntime')}


def bound(root, ref):
    path = (root/ref['path']).resolve()
    if not path.is_relative_to(root) or sha(path) != ref['sha256']:
        raise ValueError('Changed/external native input: '+ref['path'])
    return path


@contextmanager
def locked(path):
    with path.open('a+b') as stream:
        if stream.tell() == 0: stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def validate_metadata(inputs, outputs):
    # ONNX may leave the shared joint axis symbolic; only actual tensors prove 17.
    if (len(inputs) != 1 or inputs[0].name != 'input' or inputs[0].type != 'tensor(float)' or
            len(inputs[0].shape) != 4 or
            list(inputs[0].shape)[1:] != [3, 256, 192] or
            [o.name for o in outputs] != ['simcc_x','simcc_y'] or
            any(o.type != 'tensor(float)' or len(o.shape) != 3 or o.shape[2] != shape[2]
                for o,shape in zip(outputs,SHAPES,strict=True))):
        raise ValueError('ONNX does not provide the frozen native SimCC contract')
    joint_axes = [o.shape[1] for o in outputs]
    if not (joint_axes == [17, 17] or
            isinstance(joint_axes[0], str) and joint_axes[0] and joint_axes[0] == joint_axes[1]):
        raise ValueError('ONNX joint axes do not share the native SimCC contract')
    if any(a.shape[0] not in (1, 'batch') for a in [*inputs, *outputs]):
        raise ValueError('Unexpected ONNX batch axis')


def session(model):
    import onnxruntime as ort
    options = ort.SessionOptions(); options.intra_op_num_threads = 1; options.inter_op_num_threads = 1
    result = ort.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
    validate_metadata(result.get_inputs(), result.get_outputs())
    if result.get_providers() != ['CPUExecutionProvider']: raise ValueError('Unexpected ONNX provider')
    return result


def validate_outputs(outputs):
    if len(outputs) != 2 or any(a.dtype != np.float32 or a.shape != shape for a,shape in zip(outputs,SHAPES,strict=True)):
        raise ValueError('Native float32 SimCC output shape changed')


def compatibility(root, plan, output):
    result_path = output/'compatibility.json'; attempt = output/'compatibility_attempt.json'
    if result_path.exists():
        value = read(result_path)
        if value['plan_sha256'] != plan['_sha256']: raise ValueError('Compatibility seal changed')
        return {'status':'skipped_completed_compatibility','new_calls':0}
    if attempt.exists(): raise ValueError('Indeterminate synthetic inference; automatic retry refused')
    graph = session(bound(root,plan['model']))
    synthetic = np.zeros((1,3,256,192),dtype=np.float32)
    save(attempt,{'plan_sha256':plan['_sha256'],'synthetic_sha256':hashlib.sha256(synthetic.tobytes()).hexdigest()})
    result = graph.run(['simcc_x','simcc_y'],{'input':synthetic}); validate_outputs(result)
    if not all(np.isfinite(a).all() for a in result): raise ValueError('Nonfinite synthetic outputs')
    with (output/'synthetic_native.npz').open('xb') as stream:
        np.savez_compressed(stream,simcc_x=result[0],simcc_y=result[1]); stream.flush(); os.fsync(stream.fileno())
    value = {'status':'compatible_synthetic_only','plan_sha256':plan['_sha256'],'runtime':runtime(),
        'output_shapes':[list(a.shape) for a in result],'output_dtypes':[str(a.dtype) for a in result],
        'native_sha256':sha(output/'synthetic_native.npz'),'synthetic_pose_calls':1,'real_pose_calls':0,
        'human_annotation_inputs':[],'providers':graph.get_providers()}
    save(result_path,value); return value


def measure(root,plan,output):
    export_run = read(bound(root,plan['export_run']))
    if export_run['plan_sha256'] != plan['parent_plan_sha256'] or export_run['human_annotation_inputs'] != []:
        raise ValueError('Wrong GT-blind input export')
    graph = None; total_calls = 0; refs = []
    for clip in export_run['clips']:
        pid = clip['pitch_id']; folder = output/'native'/pid; folder.mkdir(parents=True,exist_ok=True)
        tensor_path = bound(root,clip['tensor']); tensors = np.load(tensor_path,allow_pickle=False,mmap_mode='r')
        if tensors.dtype != np.float32 or tensors.shape != (clip['total_frames'],1,3,256,192): raise ValueError('Input tensor contract differs')
        journal = folder/'attempts.jsonl'; started,completed = {},{}
        if journal.exists():
            for line in journal.read_text(encoding='utf-8').splitlines():
                event= json.loads(line); i=event['frame_index']; target=started if event['event']=='started' else completed
                if i in target or not 0<=i<clip['total_frames']: raise ValueError('Repeated native attempt')
                target[i]=event
        def append(event):
            with journal.open('a',encoding='utf-8',newline='\n') as stream:
                stream.write(json.dumps(event,sort_keys=True)+'\n'); stream.flush(); os.fsync(stream.fileno())
        for i,tensor in enumerate(tensors):
            path=folder/f'frame_{i:04}.npz'
            start={'event':'started','frame_index':i,'plan_sha256':plan['_sha256'],
                'tensor_sha256':hashlib.sha256(tensor.tobytes()).hexdigest()}
            if i in started:
                if started[i] != start or not path.exists(): raise ValueError('Indeterminate native call; automatic retry refused')
                finish={'event':'completed','frame_index':i,'native_sha256':sha(path)}
                if i in completed and completed[i] != finish: raise ValueError('Completed native output changed')
                if i not in completed: append(finish)
                with np.load(path,allow_pickle=False) as native: validate_outputs([native['simcc_x'],native['simcc_y']])
            else:
                if path.exists() or i in completed: raise ValueError('Unjournaled native output')
                if graph is None: graph=session(bound(root,plan['model']))
                append(start); started[i]=start
                native=graph.run(['simcc_x','simcc_y'],{'input':np.asarray(tensor)}); total_calls+=1; validate_outputs(native)
                with path.open('xb') as stream:
                    np.savez_compressed(stream,simcc_x=native[0],simcc_y=native[1]); stream.flush(); os.fsync(stream.fileno())
                finish={'event':'completed','frame_index':i,'native_sha256':sha(path)}; append(finish); completed[i]=finish
            refs.append({'pitch_id':pid,'frame_index':i,'path':path.relative_to(root).as_posix(),'sha256':sha(path)})
        print(json.dumps({'pitch_id':pid,'native_frames':clip['total_frames'],'new_calls_so_far':total_calls}),flush=True)
    if len(refs)!=592: raise ValueError('Complete 592 native outputs required')
    value={'status':'sealed_native_rtmpose_run','plan_sha256':plan['_sha256'],'frames':refs,
        'native_frames':len(refs),'new_calls_in_invocation':total_calls,'human_annotation_inputs':[],
        'read_paths':[plan['model']['path'],plan['export_run']['path'],*[c['tensor']['path'] for c in export_run['clips']]]}
    path=output/'native/native_run.json'
    if path.exists():
        old=read(path)
        if old['frames']!=refs or old['plan_sha256']!=plan['_sha256']: raise ValueError('Native seal differs')
        return {'status':'skipped_completed_native_run','new_calls':total_calls}
    save(path,value); return {'status':value['status'],'native_frames':len(refs),'new_calls':total_calls}


def main(root,plan_path):
    root=root.resolve(); plan=read(plan_path); plan['_sha256']=sha(plan_path)
    if plan['runtime']!=runtime() or plan['worker_sha256']!=sha(__file__): raise ValueError('Worker/runtime changed')
    output=(root/plan['output_path']).resolve()
    if not output.is_relative_to(root/'analysis_results') or not output.is_dir(): raise ValueError('Independent output required')
    with locked(output/'native.lock'):
        if plan['mode']=='compatibility': return compatibility(root,plan,output)
        if plan['mode']=='measure': return measure(root,plan,output)
        raise ValueError('Unknown native stage')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('plan',type=Path)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); a=p.parse_args()
    print(json.dumps(main(a.root,a.plan)),flush=True)
