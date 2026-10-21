"""Standalone binary ONNX worker: stdlib, NumPy and ONNX Runtime only.

Do not import the application package or its ABI-sensitive video dependencies.
Initializing this worker never performs a synthetic or compatibility inference.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import struct
import sys

import numpy as np

PROTOCOL = "native-onnx-transport-v1"
INPUT_SHAPE = (1, 3, 256, 192)
OUTPUT_SHAPES = ((1, 17, 384), (1, 17, 512))
MAX_PACKET_BYTES = 4 * 1024 * 1024


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_exact(stream, size):
    value = bytearray()
    while len(value) < size:
        part = stream.read(size - len(value))
        if not part:
            raise EOFError("Incomplete parent request")
        value.extend(part)
    return bytes(value)


def read_packet(stream):
    size = struct.unpack("<Q", read_exact(stream, 8))[0]
    if not 4 <= size <= MAX_PACKET_BYTES:
        raise ValueError("Request packet exceeds bounds")
    packet = read_exact(stream, size)
    header_size = struct.unpack("<I", packet[:4])[0]
    if not 0 < header_size <= size - 4:
        raise ValueError("Request header size is invalid")
    header = json.loads(packet[4:4 + header_size].decode("utf-8"))
    if not isinstance(header, dict) or header.get("protocol") != PROTOCOL:
        raise ValueError("Request protocol differs")
    return header, packet[4 + header_size:]


def write_packet(stream, header, body=b""):
    encoded = json.dumps({"protocol": PROTOCOL, **header}, allow_nan=False).encode("utf-8")
    packet = struct.pack("<I", len(encoded)) + encoded + body
    if len(packet) > MAX_PACKET_BYTES:
        raise ValueError("Response packet exceeds bounds")
    stream.write(struct.pack("<Q", len(packet)) + packet)
    stream.flush()


def metadata(node):
    return {"name": node.name, "type": node.type, "shape": list(node.shape)}


def validate_metadata(inputs, outputs):
    if (len(inputs) != 1 or inputs[0].name != "input" or inputs[0].type != "tensor(float)" or
        len(inputs[0].shape) != 4 or list(inputs[0].shape)[1:] != [3, 256, 192] or
        len(outputs) != 2 or [item.name for item in outputs] != ["simcc_x", "simcc_y"] or
        any(item.type != "tensor(float)" or len(item.shape) != 3 or item.shape[2] != shape[2]
            for item, shape in zip(outputs, OUTPUT_SHAPES, strict=True))):
        raise ValueError("ONNX does not provide the frozen native SimCC contract")
    axes = [item.shape[1] for item in outputs]
    if not (axes == [17, 17] or isinstance(axes[0], str) and axes[0] and axes[0] == axes[1]):
        raise ValueError("ONNX joint axes do not share the native SimCC contract")
    if any(item.shape[0] not in (1, "batch") for item in [*inputs, *outputs]):
        raise ValueError("Unexpected ONNX batch axis")


def create_session(model):
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    graph = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
    validate_metadata(graph.get_inputs(), graph.get_outputs())
    if graph.get_providers() != ["CPUExecutionProvider"]:
        raise ValueError("Unexpected ONNX provider")
    return graph


def validate_outputs(outputs):
    if len(outputs) != 2 or any(not isinstance(array, np.ndarray) or array.dtype != np.float32 or array.shape != shape
                               for array, shape in zip(outputs, OUTPUT_SHAPES, strict=True)):
        raise ValueError("Native float32 SimCC output shape changed")
    # Nonfinite model output is preserved. The native decoder decides missing.


def append_journal(stream, value):
    stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def serve(args, input_stream, output_stream):
    if isinstance(args.max_calls, bool) or args.max_calls <= 0:
        raise ValueError("Positive approved call budget required")
    if sha(args.model) != args.expected_model_sha256:
        raise ValueError("Model SHA256 differs in isolated worker")
    runtime = {"python": platform.python_version(), "python_executable_sha256": sha(sys.executable),
               "numpy": version("numpy"), "onnxruntime": version("onnxruntime")}
    if runtime["numpy"] != "2.2.6" or runtime["onnxruntime"] != "1.23.2":
        raise ValueError("Isolated runtime differs from approved versions")
    folder = Path(args.output_dir).resolve(strict=True)
    with (folder / "worker_calls.jsonl").open("x", encoding="utf-8", newline="\n") as journal, \
         (folder / "worker_outputs.bin").open("xb") as outputs_file:
        graph = create_session(args.model)
        write_packet(output_stream, {"type": "ready", "model_sha256": args.expected_model_sha256,
                     "runtime": runtime, "inputs": [metadata(item) for item in graph.get_inputs()],
                     "outputs": [metadata(item) for item in graph.get_outputs()],
                     "providers": graph.get_providers(), "threads": {"intra_op": 1, "inter_op": 1},
                     "synthetic_pose_calls": 0})
        calls = 0
        while True:
            try:
                header, body = read_packet(input_stream)
            except EOFError:
                return
            if header.get("type") != "run" or header.get("attempt_index") != calls + 1:
                raise ValueError("Unknown/repeated worker request")
            if calls >= args.max_calls:
                raise ValueError("Approved model call limit reached")
            if (header.get("dtype") != "float32" or header.get("shape") != list(INPUT_SHAPE) or
                len(body) != math.prod(INPUT_SHAPE) * 4 or
                header.get("input_sha256") != hashlib.sha256(body).hexdigest()):
                raise ValueError("Input tensor contract/checksum differs")
            tensor = np.frombuffer(body, dtype="<f4").reshape(INPUT_SHAPE)
            if not np.isfinite(tensor).all():
                raise ValueError("Input tensor must be finite")
            calls += 1
            started = {"event": "started", "attempt_index": calls, "input_sha256": header["input_sha256"],
                       "model_sha256": args.expected_model_sha256}
            append_journal(journal, started)
            # This is the sole model-call site. Failures are never retried.
            native = graph.run(["simcc_x", "simcc_y"], {"input": tensor})
            validate_outputs(native)
            output_body = b"".join(np.ascontiguousarray(array, dtype="<f4").tobytes() for array in native)
            output_sha = hashlib.sha256(output_body).hexdigest()
            offset = outputs_file.tell()
            outputs_file.write(output_body)
            outputs_file.flush()
            os.fsync(outputs_file.fileno())
            append_journal(journal, {"event": "completed", "attempt_index": calls,
                           "input_sha256": header["input_sha256"], "output_sha256": output_sha,
                           "output_offset_bytes": offset, "output_length_bytes": len(output_body),
                           "output_shapes": [list(shape) for shape in OUTPUT_SHAPES], "dtype": "float32"})
            write_packet(output_stream, {"type": "result", "attempt_index": calls,
                         "input_sha256": header["input_sha256"], "output_sha256": output_sha,
                         "shapes": [list(shape) for shape in OUTPUT_SHAPES], "dtype": "float32"}, output_body)


def main():
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        serve(args, sys.stdin.buffer, sys.stdout.buffer)
    except Exception as exc:
        write_packet(sys.stdout.buffer, {"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
