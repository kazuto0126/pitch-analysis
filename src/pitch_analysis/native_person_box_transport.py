"""Bounded binary transport to the isolated person detector (no video handling)."""
from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import struct
import subprocess
import threading
from pathlib import Path
from typing import BinaryIO

import numpy as np

PROTOCOL = "native-person-box-transport-v1"
INPUT_SHAPE = (1, 3, 640, 640)
MAX_DETECTIONS = 10000
OUTPUT_DTYPES = ("float32", "int64")
MAX_PACKET_BYTES = 16 * 1024 * 1024


class DetectorTransportError(RuntimeError):
    """Worker failure; an indeterminate model call must never be retried."""


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        piece = stream.read(size - len(chunks))
        if not piece:
            raise EOFError(f"Worker partial EOF: {len(chunks)}/{size} bytes")
        chunks.extend(piece)
    return bytes(chunks)


def _read_packet(stream: BinaryIO) -> tuple[dict, bytes]:
    size = struct.unpack("<Q", _read_exact(stream, 8))[0]
    if not 4 <= size <= MAX_PACKET_BYTES:
        raise DetectorTransportError("Worker packet exceeds protocol bounds")
    packet = _read_exact(stream, size)
    header_size = struct.unpack("<I", packet[:4])[0]
    if not 0 < header_size <= size - 4:
        raise DetectorTransportError("Worker header size is invalid")
    header = json.loads(packet[4:4 + header_size].decode("utf-8"))
    if not isinstance(header, dict) or header.get("protocol") != PROTOCOL:
        raise DetectorTransportError("Worker protocol differs")
    return header, packet[4 + header_size:]


def _packet(header: dict, body: bytes = b"") -> bytes:
    header_bytes = json.dumps({"protocol": PROTOCOL, **header}, allow_nan=False).encode("utf-8")
    packet = struct.pack("<I", len(header_bytes)) + header_bytes + body
    if len(packet) > MAX_PACKET_BYTES:
        raise DetectorTransportError("Request exceeds protocol bounds")
    return struct.pack("<Q", len(packet)) + packet


def _validate_metadata(value: dict, expected_model_sha256: str) -> None:
    if value.get("type") != "ready" or value.get("model_sha256") != expected_model_sha256:
        raise DetectorTransportError("Worker model handshake differs")
    runtime = value.get("runtime", {})
    if runtime.get("numpy") != "2.2.6" or runtime.get("onnxruntime") != "1.23.2":
        raise DetectorTransportError("Worker isolated runtime differs from approved versions")
    if value.get("providers") != ["CPUExecutionProvider"] or value.get("threads") != {
        "intra_op": 1, "inter_op": 1
    } or value.get("synthetic_detector_calls") != 0:
        raise DetectorTransportError("Worker execution settings differ")
    inputs, outputs = value.get("inputs", []), value.get("outputs", [])
    if inputs != [{"name": "input", "type": "tensor(float)", "shape": list(INPUT_SHAPE)}]:
        raise DetectorTransportError("Worker ONNX input metadata differs")
    if len(outputs) != 2 or [v.get("name") for v in outputs] != ["dets", "labels"]:
        raise DetectorTransportError("Worker ONNX output metadata differs")
    ds, ls = outputs[0].get("shape", []), outputs[1].get("shape", [])
    if (outputs[0].get("type") != "tensor(float)" or outputs[1].get("type") != "tensor(int64)"
            or len(ds) != 3 or ds[0] != 1 or ds[2] != 5 or len(ls) != 2 or ls[0] != 1
            or not (isinstance(ds[1], str) and ds[1] and isinstance(ls[1], str) and ls[1] or
                isinstance(ds[1], int) and not isinstance(ds[1], bool) and ds[1] == ls[1]
                and not isinstance(ls[1], bool) and 0 <= ds[1] <= MAX_DETECTIONS)):
        raise DetectorTransportError("Worker ONNX output metadata differs")


def _output_shapes(shapes) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if (not isinstance(shapes, list) or len(shapes) != 2
            or any(not isinstance(s, list) for s in shapes)
            or len(shapes[0]) != 3 or len(shapes[1]) != 2
            or any(isinstance(d, bool) or not isinstance(d, int) for s in shapes for d in s)
            or shapes[0][0] != 1 or shapes[0][2] != 5 or shapes[1][0] != 1
            or shapes[0][1] != shapes[1][1] or not 0 <= shapes[0][1] <= MAX_DETECTIONS):
        raise DetectorTransportError("Worker output shapes differ")
    return tuple(map(tuple, shapes))


class IsolatedDetectorTransport:
    """One persistent CPU session; each accepted run makes at most one model call.

    Construction creates exclusive evidence files. Context entry starts the worker
    without a compatibility inference. A protocol, I/O, or inference failure makes
    the transport permanently unusable; no automatic restart/retry is performed.
    """

    def __init__(self, python_executable, worker_script, model_path, *, expected_model_sha256,
                 max_calls, output_dir, timeout_seconds=120.0):
        self.python_executable = Path(python_executable).resolve(strict=True)
        self.worker_script = Path(worker_script).resolve(strict=True)
        self.model_path = Path(model_path).resolve(strict=True)
        self.output_dir = Path(output_dir).resolve()
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or not 1 <= max_calls <= 321:
            raise ValueError("max_calls must be an integer between 1 and 321")
        if not isinstance(expected_model_sha256, str) or len(expected_model_sha256) != 64:
            raise ValueError("Expected SHA256 is required")
        try:
            int(expected_model_sha256, 16)
        except ValueError as exc:
            raise ValueError("Expected SHA256 is invalid") from exc
        if _sha(self.model_path) != expected_model_sha256:
            raise ValueError("Model SHA256 differs before worker startup")
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.expected_model_sha256 = expected_model_sha256
        self.max_calls = max_calls
        self.timeout_seconds = float(timeout_seconds)
        self.calls_attempted = 0
        self.calls_completed = 0
        self.metadata = None
        self._process = None
        self._stderr = None
        self._closed = False
        self._started = False
        self._messages = queue.Queue(maxsize=2)
        self._operation_lock = threading.Lock()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Refuse resumption after any earlier attempt, including an incomplete one.
        reserved = ["transport_claim.json", "worker_stderr.log", "worker_calls.jsonl", "worker_outputs.bin"]
        if any((self.output_dir / name).exists() for name in reserved):
            raise FileExistsError("Transport evidence already exists; automatic retry refused")
        with (self.output_dir / "transport_claim.json").open("x", encoding="utf-8") as stream:
            json.dump({"protocol": PROTOCOL, "model_path": str(self.model_path),
                       "model_sha256": expected_model_sha256, "worker_sha256": _sha(self.worker_script),
                       "max_calls": max_calls, "synthetic_detector_calls": 0}, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _read_messages(self):
        try:
            while True:
                value = _read_packet(self._process.stdout)
                self._messages.put(value, timeout=self.timeout_seconds)
        except BaseException as exc:
            try:
                self._messages.put(exc, timeout=1)
            except queue.Full:
                pass

    def _receive(self):
        try:
            value = self._messages.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            raise DetectorTransportError("Worker timed out; automatic retry refused") from exc
        if isinstance(value, BaseException):
            raise DetectorTransportError(f"Worker protocol/EOF failure: {value}; automatic retry refused") from value
        header, body = value
        if header.get("type") == "error":
            raise DetectorTransportError(f"Worker error: {header.get('message')}; automatic retry refused")
        return header, body

    def _send(self, header, body=b""):
        # A bounded writer thread prevents a stalled worker from hanging a caller
        # even on Windows, where pipe descriptors cannot use select().
        result = queue.Queue(maxsize=1)
        packet = _packet(header, body)
        def write():
            try:
                pending = memoryview(packet)
                while pending:
                    written = self._process.stdin.write(pending)
                    if not written:
                        raise BrokenPipeError("Worker accepted zero request bytes")
                    pending = pending[written:]
                self._process.stdin.flush()
                result.put(None)
            except BaseException as exc:
                result.put(exc)
        threading.Thread(target=write, daemon=True).start()
        try:
            error = result.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            raise DetectorTransportError("Worker write timed out; automatic retry refused") from exc
        if error is not None:
            raise DetectorTransportError(f"Worker write failed: {error}; automatic retry refused") from error

    def __enter__(self):
        if self._started or self._closed:
            raise DetectorTransportError("Transport cannot be restarted")
        self._started = True
        try:
            self._stderr = (self.output_dir / "worker_stderr.log").open("xb")
            self._process = subprocess.Popen(
                [str(self.python_executable), "-I", "-u", str(self.worker_script),
                 "--model", str(self.model_path), "--expected-model-sha256", self.expected_model_sha256,
                 "--max-calls", str(self.max_calls), "--output-dir", str(self.output_dir)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
                bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            threading.Thread(target=self._read_messages, daemon=True).start()
            header, body = self._receive()
            if body:
                raise DetectorTransportError("Unexpected handshake payload")
            _validate_metadata(header, self.expected_model_sha256)
            self.metadata = header
            return self
        except BaseException:
            self.close()
            raise

    def run(self, tensor):
        with self._operation_lock:
            if self._closed or not self._started or self.metadata is None:
                raise DetectorTransportError("Transport is not active")
            if not isinstance(tensor, np.ndarray) or tensor.dtype != np.float32 or tensor.shape != INPUT_SHAPE:
                raise ValueError("Expected float32 tensor with shape (1,3,640,640)")
            if not np.isfinite(tensor).all():
                raise ValueError("Input tensor must be finite")
            if self.calls_attempted >= self.max_calls:
                raise DetectorTransportError("Approved model call limit reached")
            payload = np.ascontiguousarray(tensor, dtype="<f4").tobytes()
            digest = hashlib.sha256(payload).hexdigest()
            self.calls_attempted += 1
            attempt_index = self.calls_attempted
            try:
                self._send({"type": "run", "attempt_index": attempt_index,
                            "input_sha256": digest, "dtype": "float32", "shape": list(INPUT_SHAPE)}, payload)
                header, body = self._receive()
                shapes = _output_shapes(header.get("shapes"))
                expected_size = math.prod(shapes[0]) * 4 + math.prod(shapes[1]) * 8
                if (header.get("type") != "result" or header.get("attempt_index") != attempt_index or
                    header.get("input_sha256") != digest or header.get("dtypes") != list(OUTPUT_DTYPES) or
                    len(body) != expected_size or header.get("output_sha256") != hashlib.sha256(body).hexdigest()):
                    raise DetectorTransportError("Worker output contract or checksum differs")
                first_size = math.prod(shapes[0]) * 4
                outputs = (np.frombuffer(body[:first_size], dtype="<f4").copy().reshape(shapes[0]),
                           np.frombuffer(body[first_size:], dtype="<i8").copy().reshape(shapes[1]))
                self.calls_completed += 1
                return outputs
            except BaseException:
                self.close()
                raise

    def close(self):
        self._closed = True
        process = self._process
        if process is not None:
            # Never send another inference and never wait indefinitely for EOF.
            if process.poll() is None:
                # A complete stream may end normally. Pending/failed requests
                # are terminated because their inference outcome is uncertain.
                complete = self.metadata is not None and self.calls_attempted == self.calls_completed
                if complete and process.stdin is not None:
                    process.stdin.close()
                else:
                    process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    stream.close()
        if self._stderr is not None:
            self._stderr.close()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
