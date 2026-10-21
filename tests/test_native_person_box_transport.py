"""Detector transport tests use synthetic workers/graphs: zero real inference."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from pitch_analysis.native_person_box_transport import (
    INPUT_SHAPE, MAX_PACKET_BYTES, DetectorTransportError, IsolatedDetectorTransport,
    _packet, _read_packet,
)

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "scripts/native_person_box_onnx_worker.py"
spec = importlib.util.spec_from_file_location("test_person_box_worker", WORKER_PATH)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

FAKE_WORKER = r'''
import argparse, hashlib, json, pathlib, struct, sys, time
p=argparse.ArgumentParser()
p.add_argument('--model');p.add_argument('--expected-model-sha256')
p.add_argument('--max-calls',type=int);p.add_argument('--output-dir')
a=p.parse_args();folder=pathlib.Path(a.output_dir);MODE=__MODE__
PROTOCOL='native-person-box-transport-v1'
def exact(n):
    data=bytearray()
    while len(data)<n:
        part=sys.stdin.buffer.read(n-len(data))
        if not part:raise EOFError()
        data.extend(part)
    return bytes(data)
def read():
    size=struct.unpack('<Q',exact(8))[0];value=exact(size)
    n=struct.unpack('<I',value[:4])[0]
    return json.loads(value[4:4+n]),value[4+n:]
def send(header,body=b''):
    h=json.dumps({'protocol':PROTOCOL,**header}).encode()
    value=struct.pack('<I',len(h))+h+body
    sys.stdout.buffer.write(struct.pack('<Q',len(value))+value);sys.stdout.buffer.flush()
ready={'type':'ready','model_sha256':a.expected_model_sha256,
 'runtime':{'numpy':'2.2.6','onnxruntime':'1.23.2'},
 'providers':['CPUExecutionProvider'],'threads':{'intra_op':1,'inter_op':1},'synthetic_detector_calls':0,
 'inputs':[{'name':'input','type':'tensor(float)','shape':[1,3,640,640]}],
 'outputs':[{'name':'dets','type':'tensor(float)','shape':[1,'N',5]},
            {'name':'labels','type':'tensor(int64)','shape':[1,'other_export_symbol']}]}
if MODE=='bad_metadata':ready['outputs'][1]['shape'][0]=2
if MODE=='startup_timeout':time.sleep(10)
send(ready)
with (folder/'fake_requests.jsonl').open('x',encoding='utf-8') as log:
    while True:
        try:h,b=read()
        except EOFError:break
        log.write(json.dumps(h)+'\n');log.flush()
        if MODE=='partial_eof':
            sys.stdout.buffer.write(struct.pack('<Q',500)+b'partial');sys.stdout.buffer.flush();break
        if MODE=='run_timeout':time.sleep(10)
        if MODE=='worker_error':send({'type':'error','message':'fake inference failed'});break
        n=h['attempt_index']
        body=struct.pack('<f',float('nan'))+bytes(n*5*4-4)+struct.pack('<q',-1)*n
        shapes=[[1,n,5],[1,n]]
        if MODE=='wrong_shape':shapes[1][1]+=1
        if MODE=='oversized_shape':shapes=[[1,10001,5],[1,10001]]
        digest=hashlib.sha256(body).hexdigest()
        if MODE=='bad_checksum':digest='0'*64
        send({'type':'result','attempt_index':h['attempt_index'],'input_sha256':h['input_sha256'],
              'output_sha256':digest,'shapes':shapes,'dtypes':['float32','int64']},body)
'''


def node(name, shape, dtype="tensor(float)"):
    return SimpleNamespace(name=name, shape=shape, type=dtype)


class FakeGraph:
    def __init__(self):
        self.calls = 0
        self.before_call = None

    def get_inputs(self):
        return [node("input", [1, 3, 640, 640])]

    def get_outputs(self):
        return [node("dets", [1, "Gatherdets_dim_1", 5]), node("labels", [1, "Gatherlabels_dim_1"], "tensor(int64)")]

    def get_providers(self):
        return ["CPUExecutionProvider"]

    def run(self, names, inputs):
        assert names == ["dets", "labels"]
        assert inputs['input'].shape == INPUT_SHAPE
        self.calls += 1
        if self.before_call:
            self.before_call()
        dets = np.array([[[np.nan, 2., 3., 4., .9], [5., 6., 7., 8., .8]]], np.float32)
        return [dets, np.array([[0, -1]], np.int64)]


class NativePersonBoxTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.model = self.folder / 'fake.onnx'
        self.model.write_bytes(b'non-executable synthetic model')
        self.digest = hashlib.sha256(self.model.read_bytes()).hexdigest()

    def transport(self, mode='normal', **kwargs):
        script = self.folder / f'fake_{mode}.py'
        script.write_text(FAKE_WORKER.replace('__MODE__', repr(mode)), encoding='utf-8')
        return IsolatedDetectorTransport(sys.executable, script, self.model,
            expected_model_sha256=self.digest, max_calls=kwargs.pop('max_calls', 2),
            output_dir=self.folder / mode, **kwargs)

    def test_handshake_zero_inference_and_large_dynamic_mixed_dtype_roundtrip(self):
        self.assertGreater(np.zeros(INPUT_SHAPE, np.float32).nbytes, 4 * 1024 * 1024)
        with self.transport() as transport:
            self.assertEqual((transport.calls_attempted, transport.calls_completed), (0, 0))
            self.assertEqual(transport.metadata['synthetic_detector_calls'], 0)
            for n in (1, 2):
                dets, labels = transport.run(np.zeros(INPUT_SHAPE, np.float32))
                self.assertEqual(dets.shape, (1, n, 5))
                self.assertEqual(labels.shape, (1, n))
                self.assertEqual(dets.dtype, np.float32)
                self.assertEqual(labels.dtype, np.int64)
                self.assertTrue(np.isnan(dets[0, 0, 0]))
                self.assertTrue((labels == -1).all())
            with self.assertRaisesRegex(DetectorTransportError, 'limit'):
                transport.run(np.zeros(INPUT_SHAPE, np.float32))
            self.assertEqual((transport.calls_attempted, transport.calls_completed), (2, 2))
        self.assertEqual(transport._process.returncode, 0)
        self.assertEqual(len((self.folder/'normal/fake_requests.jsonl').read_text().splitlines()), 2)

    def test_invalid_tensor_and_call_limits_rejected_before_dispatch(self):
        for limit in (0, 322, True, 1.5):
            with self.assertRaises(ValueError):
                self.transport(f'limit{limit}', max_calls=limit)
        with self.transport() as transport:
            for tensor in (np.zeros(INPUT_SHAPE, np.float64), np.zeros((1, 3, 640, 639), np.float32),
                           np.full(INPUT_SHAPE, np.inf, np.float32), []):
                with self.assertRaises(ValueError):
                    transport.run(tensor)
            self.assertEqual(transport.calls_attempted, 0)

    def test_source_hash_and_exclusive_evidence_prevent_restart(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            IsolatedDetectorTransport(sys.executable, WORKER_PATH, self.model,
                expected_model_sha256='0'*64, max_calls=1, output_dir=self.folder/'bad')
        transport = self.transport()
        with self.assertRaises(FileExistsError):
            self.transport()
        transport.close()
        with self.assertRaisesRegex(DetectorTransportError, 'restarted'):
            transport.__enter__()

    def test_invalid_metadata_closes_worker_before_dispatch(self):
        transport = self.transport('bad_metadata')
        with self.assertRaisesRegex(DetectorTransportError, 'metadata'):
            transport.__enter__()
        self.assertEqual(transport.calls_attempted, 0)
        self.assertIsNotNone(transport._process.poll())

    def test_failure_shapes_checksum_partial_eof_and_error_never_retry(self):
        for mode in ('partial_eof', 'wrong_shape', 'oversized_shape', 'bad_checksum', 'worker_error'):
            with self.subTest(mode=mode), self.transport(mode) as transport:
                with self.assertRaises(DetectorTransportError):
                    transport.run(np.zeros(INPUT_SHAPE, np.float32))
                self.assertEqual((transport.calls_attempted, transport.calls_completed), (1, 0))
                with self.assertRaisesRegex(DetectorTransportError, 'not active'):
                    transport.run(np.zeros(INPUT_SHAPE, np.float32))
                self.assertIsNotNone(transport._process.poll())
                self.assertEqual(len((self.folder/mode/'fake_requests.jsonl').read_text().splitlines()), 1)

    def test_startup_and_run_timeouts_close_without_retry(self):
        startup = self.transport('startup_timeout', timeout_seconds=.5)
        with self.assertRaisesRegex(DetectorTransportError, 'timed out'):
            startup.__enter__()
        self.assertEqual(startup.calls_attempted, 0)
        self.assertIsNotNone(startup._process.poll())
        with self.transport('run_timeout', timeout_seconds=.5) as transport:
            with self.assertRaisesRegex(DetectorTransportError, 'timed out'):
                transport.run(np.zeros(INPUT_SHAPE, np.float32))
            self.assertEqual(transport.calls_attempted, 1)
        self.assertIsNotNone(transport._process.poll())

    def test_packet_rejects_malformed_protocol_bounds_and_header(self):
        for value in (struct.pack('<Q', MAX_PACKET_BYTES+1),
                      struct.pack('<Q', 4)+struct.pack('<I', 8),
                      _packet({'protocol':'other'})):
            with self.assertRaises((DetectorTransportError, EOFError)):
                _read_packet(io.BytesIO(value))

    def worker_args(self):
        folder = self.folder/'direct'
        folder.mkdir()
        return SimpleNamespace(model=self.model, expected_model_sha256=self.digest, max_calls=2, output_dir=folder)

    def invoke_worker(self, graph, request, args):
        runtime = lambda name: {'numpy':'2.2.6','onnxruntime':'1.23.2'}[name]
        output = io.BytesIO()
        with patch.object(worker, 'version', side_effect=runtime), patch.object(worker, 'create_session', return_value=graph):
            worker.serve(args, io.BytesIO(request), output)
        return io.BytesIO(output.getvalue())

    def request(self, attempt=1):
        body = np.zeros(INPUT_SHAPE, np.float32).tobytes()
        return _packet({'type':'run','attempt_index':attempt,'input_sha256':hashlib.sha256(body).hexdigest(),
                        'shape':list(INPUT_SHAPE),'dtype':'float32'}, body)

    def test_worker_initialization_zero_graph_calls(self):
        graph = FakeGraph()
        stream = self.invoke_worker(graph, b'', self.worker_args())
        self.assertEqual(_read_packet(stream)[0]['type'], 'ready')
        self.assertEqual(graph.calls, 0)

    def test_worker_durable_attempt_precedes_call_and_preserves_float_int_raw(self):
        graph, args = FakeGraph(), self.worker_args()
        def before():
            events = [json.loads(x) for x in (args.output_dir/'worker_calls.jsonl').read_text().splitlines()]
            self.assertEqual([x['event'] for x in events], ['started'])
        graph.before_call = before
        stream = self.invoke_worker(graph, self.request(), args)
        _read_packet(stream)
        header, body = _read_packet(stream)
        events = [json.loads(x) for x in (args.output_dir/'worker_calls.jsonl').read_text().splitlines()]
        self.assertEqual([x['event'] for x in events], ['started','completed'])
        self.assertEqual(header['shapes'], [[1,2,5],[1,2]])
        self.assertEqual(header['dtypes'], ['float32','int64'])
        self.assertEqual((args.output_dir/'worker_outputs.bin').read_bytes(), body)
        self.assertEqual(events[1]['output_sha256'], hashlib.sha256(body).hexdigest())
        self.assertTrue(np.isnan(np.frombuffer(body[:40], dtype='<f4')[0]))
        self.assertEqual(np.frombuffer(body[40:], dtype='<i8').tolist(), [0,-1])
        self.assertEqual(graph.calls, 1)

    def test_worker_failed_call_and_duplicate_keep_no_retry(self):
        graph, args = FakeGraph(), self.worker_args()
        def fail():
            raise RuntimeError('fake inference failed')
        graph.before_call = fail
        with self.assertRaisesRegex(RuntimeError, 'fake inference failed'):
            self.invoke_worker(graph, self.request(), args)
        self.assertEqual(graph.calls, 1)
        events = [json.loads(x) for x in (args.output_dir/'worker_calls.jsonl').read_text().splitlines()]
        self.assertEqual([x['event'] for x in events], ['started'])
        with self.assertRaises(FileExistsError):
            self.invoke_worker(graph, self.request(), args)
        self.assertEqual(graph.calls, 1)

    def test_worker_budget_duplicate_and_shape_validation(self):
        graph, args = FakeGraph(), self.worker_args()
        args.max_calls = 1
        with self.assertRaisesRegex(ValueError, 'call limit'):
            self.invoke_worker(graph, self.request(1)+self.request(2), args)
        self.assertEqual(graph.calls, 1)
        worker.validate_metadata(graph.get_inputs(), graph.get_outputs())
        wrong = graph.get_outputs();wrong[1].shape[0] = 2
        with self.assertRaisesRegex(ValueError, 'axes differ'):
            worker.validate_metadata(graph.get_inputs(), wrong)
        for dets,labels in ((np.zeros((1,1,5),np.float64),np.zeros((1,1),np.int64)),
                            (np.zeros((1,1,5),np.float32),np.zeros((1,2),np.int64)),
                            (np.zeros((1,1,5),np.float32),np.zeros((1,1),np.int32))):
            with self.assertRaisesRegex(ValueError, 'shape changed'):
                worker.validate_outputs([dets,labels])

    def test_worker_rejects_duplicate_before_second_call(self):
        graph = FakeGraph()
        with self.assertRaisesRegex(ValueError, 'repeated'):
            self.invoke_worker(graph, self.request()+self.request(), self.worker_args())
        self.assertEqual(graph.calls, 1)

    def test_no_application_or_video_binary_import_in_worker(self):
        tree = ast.parse(WORKER_PATH.read_text(encoding='utf-8'))
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        self.assertFalse(any(m and m.split('.')[0] in {'cv2','pitch_analysis','jsonschema'} for m in modules))
        tree = ast.parse((ROOT/'src/pitch_analysis/native_person_box_transport.py').read_text())
        self.assertFalse(any(isinstance(n,ast.Import) and any(a.name=='onnxruntime' for a in n.names) for n in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main()
