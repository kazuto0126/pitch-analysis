"""Transport/worker tests use only fake graphs: zero real ONNX inference."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from pitch_analysis.native_pose_transport import (
    INPUT_SHAPE, OUTPUT_SHAPES, IsolatedOnnxTransport, NativePoseTransportError,
    _packet, _read_packet,
)

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "scripts/native_pose_onnx_worker.py"
spec = importlib.util.spec_from_file_location("test_live_native_worker", WORKER_PATH)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

FAKE_WORKER = r'''
import argparse, hashlib, json, pathlib, struct, sys, time
p=argparse.ArgumentParser()
p.add_argument('--model'); p.add_argument('--expected-model-sha256')
p.add_argument('--max-calls',type=int); p.add_argument('--output-dir')
a=p.parse_args(); folder=pathlib.Path(a.output_dir)
MODE=__MODE__
PROTOCOL='native-onnx-transport-v1'
def exact(n):
    v=bytearray()
    while len(v)<n:
        part=sys.stdin.buffer.read(n-len(v))
        if not part: raise EOFError()
        v.extend(part)
    return bytes(v)
def read():
    size=struct.unpack('<Q',exact(8))[0]; value=exact(size)
    n=struct.unpack('<I',value[:4])[0]
    return json.loads(value[4:4+n]),value[4+n:]
def send(header,body=b''):
    data=json.dumps({'protocol':PROTOCOL,**header}).encode()
    value=struct.pack('<I',len(data))+data+body
    sys.stdout.buffer.write(struct.pack('<Q',len(value))+value); sys.stdout.buffer.flush()
ready={'type':'ready','model_sha256':a.expected_model_sha256,
 'runtime':{'numpy':'2.2.6','onnxruntime':'1.23.2'},
 'providers':['CPUExecutionProvider'],'threads':{'intra_op':1,'inter_op':1},'synthetic_pose_calls':0,
 'inputs':[{'name':'input','type':'tensor(float)','shape':['batch',3,256,192]}],
 'outputs':[{'name':'simcc_x','type':'tensor(float)','shape':['batch','joints',384]},
            {'name':'simcc_y','type':'tensor(float)','shape':['batch','joints',512]}]}
if MODE=='bad_metadata': ready['outputs'][0]['shape'][2]=383
if MODE=='startup_timeout': time.sleep(10)
send(ready)
with (folder/'fake_requests.jsonl').open('x',encoding='utf-8') as log:
    while True:
        try: h,b=read()
        except EOFError: break
        log.write(json.dumps(h)+'\n'); log.flush()
        if MODE=='partial_eof':
            sys.stdout.buffer.write(struct.pack('<Q',500)+b'partial');sys.stdout.buffer.flush();break
        if MODE=='run_timeout': time.sleep(10)
        if MODE=='worker_error':
            send({'type':'error','message':'fake inference failed'});break
        body=struct.pack('<f',float('nan'))+bytes((17*384+17*512)*4-4)
        shapes=[[1,17,384],[1,17,512]]
        if MODE=='wrong_shape': shapes[0][1]=16
        send({'type':'result','attempt_index':h['attempt_index'],'input_sha256':h['input_sha256'],
              'output_sha256':hashlib.sha256(body).hexdigest(),'shapes':shapes,'dtype':'float32'},body)
'''


def node(name, shape):
    return SimpleNamespace(name=name, shape=shape, type="tensor(float)")


class FakeGraph:
    def __init__(self):
        self.calls = 0
        self.before_call = None

    def get_inputs(self):
        return [node("input", ["batch", 3, 256, 192])]

    def get_outputs(self):
        return [node("simcc_x", ["batch", "joints", 384]), node("simcc_y", ["batch", "joints", 512])]

    def get_providers(self):
        return ["CPUExecutionProvider"]

    def run(self, names, inputs):
        self.calls += 1
        if self.before_call:
            self.before_call()
        result = [np.zeros(shape, np.float32) for shape in OUTPUT_SHAPES]
        result[0][0, 0, 0] = np.nan
        return result


class NativePoseTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.model = self.folder / "model.onnx"
        self.model.write_bytes(b"fake non-executable model")
        self.digest = hashlib.sha256(self.model.read_bytes()).hexdigest()

    def transport(self, mode="normal", **kwargs):
        script = self.folder / f"fake_{mode}.py"
        script.write_text(FAKE_WORKER.replace("__MODE__", repr(mode)), encoding="utf-8")
        return IsolatedOnnxTransport(sys.executable, script, self.model,
            expected_model_sha256=self.digest, max_calls=kwargs.pop("max_calls", 2),
            output_dir=self.folder / mode, **kwargs)

    def test_context_handshake_makes_no_model_call_and_runtime_is_explicit(self):
        with self.transport() as transport:
            self.assertEqual(transport.calls_attempted, 0)
            self.assertEqual(transport.calls_completed, 0)
            self.assertEqual(transport.metadata["synthetic_pose_calls"], 0)
            self.assertEqual(transport.metadata["runtime"]["numpy"], "2.2.6")
        self.assertIsNotNone(transport._process.poll())
        self.assertEqual(transport._process.returncode, 0)

    def test_one_request_per_run_and_bound_and_nonfinite_output_preserved(self):
        with self.transport() as transport:
            for _ in range(2):
                x, y = transport.run(np.zeros(INPUT_SHAPE, np.float32))
                self.assertEqual(x.shape, OUTPUT_SHAPES[0])
                self.assertEqual(y.shape, OUTPUT_SHAPES[1])
                self.assertEqual(x.dtype, np.float32)
                self.assertTrue(np.isnan(x[0, 0, 0]))
            with self.assertRaisesRegex(NativePoseTransportError, "limit"):
                transport.run(np.zeros(INPUT_SHAPE, np.float32))
            self.assertEqual((transport.calls_attempted, transport.calls_completed), (2, 2))
        lines = (self.folder / "normal/fake_requests.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 2)

    def test_invalid_tensors_are_rejected_before_dispatch(self):
        with self.transport() as transport:
            for tensor in [np.zeros(INPUT_SHAPE, np.float64), np.zeros((1, 3, 192, 256), np.float32),
                           np.full(INPUT_SHAPE, np.nan, np.float32), []]:
                with self.assertRaises(ValueError):
                    transport.run(tensor)
            self.assertEqual(transport.calls_attempted, 0)

    def test_source_sha_and_exclusive_evidence_prevent_restart(self):
        with self.assertRaisesRegex(ValueError, "SHA256"):
            IsolatedOnnxTransport(sys.executable, WORKER_PATH, self.model,
                expected_model_sha256="0" * 64, max_calls=1, output_dir=self.folder / "bad")
        transport = self.transport()
        with self.assertRaises(FileExistsError):
            self.transport()
        transport.close()
        with self.assertRaisesRegex(NativePoseTransportError, "restarted"):
            transport.__enter__()

    def test_bad_metadata_fails_before_dispatch_and_worker_is_closed(self):
        transport = self.transport("bad_metadata")
        with self.assertRaisesRegex(NativePoseTransportError, "metadata"):
            transport.__enter__()
        self.assertEqual(transport.calls_attempted, 0)
        self.assertIsNotNone(transport._process.poll())

    def test_partial_eof_wrong_shape_and_worker_failure_never_retry(self):
        for mode in ["partial_eof", "wrong_shape", "worker_error"]:
            with self.subTest(mode=mode):
                transport = self.transport(mode)
                with transport:
                    with self.assertRaises(NativePoseTransportError):
                        transport.run(np.zeros(INPUT_SHAPE, np.float32))
                    self.assertEqual((transport.calls_attempted, transport.calls_completed), (1, 0))
                    with self.assertRaisesRegex(NativePoseTransportError, "not active"):
                        transport.run(np.zeros(INPUT_SHAPE, np.float32))
                self.assertIsNotNone(transport._process.poll())
                lines = (self.folder / mode / "fake_requests.jsonl").read_text().splitlines()
                self.assertEqual(len(lines), 1)

    def test_startup_and_inference_timeouts_close_process_without_retry(self):
        startup = self.transport("startup_timeout", timeout_seconds=.5)
        with self.assertRaisesRegex(NativePoseTransportError, "timed out"):
            startup.__enter__()
        self.assertEqual(startup.calls_attempted, 0)
        self.assertIsNotNone(startup._process.poll())
        with self.transport("run_timeout", timeout_seconds=.5) as transport:
            with self.assertRaisesRegex(NativePoseTransportError, "timed out"):
                transport.run(np.zeros(INPUT_SHAPE, np.float32))
            self.assertEqual(transport.calls_attempted, 1)
        self.assertIsNotNone(transport._process.poll())

    def test_standalone_worker_has_no_application_or_video_imports(self):
        tree = ast.parse(WORKER_PATH.read_text(encoding="utf-8"))
        imports = [item.module for item in ast.walk(tree) if isinstance(item, ast.ImportFrom)]
        imports.extend(alias.name for item in ast.walk(tree) if isinstance(item, ast.Import) for alias in item.names)
        self.assertFalse(any(value and value.split(".")[0] in {"cv2", "jsonschema", "pitch_analysis"} for value in imports))
        # The parent transport never imports the isolated ORT binary package.
        parent_tree = ast.parse((ROOT / "src/pitch_analysis/native_pose_transport.py").read_text())
        self.assertFalse(any(isinstance(item, ast.Import) and any(alias.name == "onnxruntime" for alias in item.names)
                             for item in ast.walk(parent_tree)))

    def worker_args(self):
        folder = self.folder / "direct"
        folder.mkdir()
        return SimpleNamespace(model=self.model, expected_model_sha256=self.digest, max_calls=2, output_dir=folder)

    def invoke_worker(self, graph, request, args):
        runtime_version = lambda name: {"numpy": "2.2.6", "onnxruntime": "1.23.2"}[name]
        output = io.BytesIO()
        with patch.object(worker, "version", side_effect=runtime_version), patch.object(worker, "create_session", return_value=graph):
            worker.serve(args, io.BytesIO(request), output)
        return io.BytesIO(output.getvalue())

    def test_worker_initialization_only_checks_metadata_zero_calls(self):
        graph = FakeGraph()
        stream = self.invoke_worker(graph, b"", self.worker_args())
        self.assertEqual(_read_packet(stream)[0]["type"], "ready")
        self.assertEqual(graph.calls, 0)

    def request(self, attempt=1):
        body = np.zeros(INPUT_SHAPE, np.float32).tobytes()
        return _packet({"type": "run", "attempt_index": attempt, "input_sha256": hashlib.sha256(body).hexdigest(),
                        "shape": list(INPUT_SHAPE), "dtype": "float32"}, body)

    def test_worker_durable_attempt_precedes_call_and_output_is_preserved(self):
        args = self.worker_args()
        graph = FakeGraph()
        def before_call():
            events = [json.loads(line) for line in (args.output_dir / "worker_calls.jsonl").read_text().splitlines()]
            self.assertEqual([event["event"] for event in events], ["started"])
        graph.before_call = before_call
        stream = self.invoke_worker(graph, self.request(), args)
        _read_packet(stream)
        header, body = _read_packet(stream)
        events = [json.loads(line) for line in (args.output_dir / "worker_calls.jsonl").read_text().splitlines()]
        self.assertEqual([event["event"] for event in events], ["started", "completed"])
        self.assertEqual(graph.calls, 1)
        self.assertEqual((args.output_dir / "worker_outputs.bin").read_bytes(), body)
        self.assertEqual(events[1]["output_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(header["output_sha256"], events[1]["output_sha256"])

    def test_worker_failed_inference_retains_attempt_and_refuses_evidence_reuse(self):
        args = self.worker_args()
        graph = FakeGraph()
        def fail():
            raise RuntimeError("fake inference failed")
        graph.before_call = fail
        with self.assertRaisesRegex(RuntimeError, "fake inference failed"):
            self.invoke_worker(graph, self.request(), args)
        self.assertEqual(graph.calls, 1)
        events = [json.loads(line) for line in (args.output_dir / "worker_calls.jsonl").read_text().splitlines()]
        self.assertEqual([event["event"] for event in events], ["started"])
        with self.assertRaises(FileExistsError):
            self.invoke_worker(graph, self.request(), args)
        self.assertEqual(graph.calls, 1)

    def test_worker_rejects_duplicate_before_second_call_and_shape_metadata(self):
        graph = FakeGraph()
        with self.assertRaisesRegex(ValueError, "repeated"):
            self.invoke_worker(graph, self.request() + self.request(), self.worker_args())
        self.assertEqual(graph.calls, 1)
        worker.validate_metadata(graph.get_inputs(), graph.get_outputs())
        outputs = graph.get_outputs()
        outputs[1].shape[1] = "other"
        with self.assertRaisesRegex(ValueError, "joint axes"):
            worker.validate_metadata(graph.get_inputs(), outputs)
        with self.assertRaisesRegex(ValueError, "shape changed"):
            worker.validate_outputs([np.zeros(shape, np.float64) for shape in OUTPUT_SHAPES])

    def test_worker_independently_enforces_budget_before_model_call(self):
        args = self.worker_args()
        args.max_calls = 1
        graph = FakeGraph()
        with self.assertRaisesRegex(ValueError, "call limit"):
            self.invoke_worker(graph, self.request(1) + self.request(2), args)
        self.assertEqual(graph.calls, 1)
        events = [json.loads(line) for line in (args.output_dir / "worker_calls.jsonl").read_text().splitlines()]
        self.assertEqual([event["event"] for event in events], ["started", "completed"])


if __name__ == "__main__":
    unittest.main()
