"""Exclusive native output writes and source-bound, read-only cached inputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Iterable

from .native_pose import NativePoseFrame, _finite_json, _validate_reference, validate_manifest


def sha256(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reference(root: str | Path, path: str | Path) -> dict:
    base, target = Path(root).resolve(strict=True), Path(path).resolve(strict=True)
    if not target.is_relative_to(base) or not target.is_file():
        raise ValueError("Source reference must be a file within the allowed root")
    result = {"path": target.relative_to(base).as_posix(), "sha256": sha256(target)}
    _validate_reference(result)
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Nonfinite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _loads(text: str) -> object:
    value = json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    _finite_json(value)
    return value


def read_json(path: str | Path) -> dict:
    value = _loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


class BoundReader:
    """Only allow declared root-contained files whose current hashes match."""

    def __init__(self, root: str | Path, refs: Iterable[dict]) -> None:
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Allowed source root must be a directory")
        self.allowed: dict[str, str] = {}
        self.opened: list[str] = []
        for ref in refs:
            self._check_ref(ref)
            previous = self.allowed.get(ref["path"])
            if previous is not None and previous != ref["sha256"]:
                raise ValueError("Conflicting source hashes for one path")
            self.allowed[ref["path"]] = ref["sha256"]

    @staticmethod
    def _check_ref(ref: dict) -> None:
        if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or
                not isinstance(ref["path"], str) or not isinstance(ref["sha256"], str) or
                re.fullmatch(r"[a-f0-9]{64}", ref["sha256"]) is None):
            raise ValueError("Invalid path/SHA source reference")
        _validate_reference(ref)

    def path(self, ref: dict) -> Path:
        self._check_ref(ref)
        if self.allowed.get(ref["path"]) != ref["sha256"]:
            raise ValueError("Source not allowed by this reader")
        path = (self.root / ref["path"]).resolve(strict=True)
        if not path.is_relative_to(self.root) or not path.is_file() or sha256(path) != ref["sha256"]:
            raise ValueError("Changed or external source input")
        self.opened.append(ref["path"])
        return path

    def json(self, ref: dict) -> dict:
        return read_json(self.path(ref))


def write_json(path: str | Path, payload: dict) -> None:
    _finite_json(payload)
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def _dataset_frames(manifest: dict, frames: Iterable[NativePoseFrame | dict]) -> list[NativePoseFrame]:
    validate_manifest(manifest)
    result = [frame if isinstance(frame, NativePoseFrame) else NativePoseFrame(frame) for frame in frames]
    if len(result) != manifest["video"]["frame_count"]:
        raise ValueError("Native dataset must preserve the complete declared frame count")
    previous_timestamp = None
    for index, frame in enumerate(result):
        item = frame.to_dict()
        if item["frame_index"] != index:
            raise ValueError("Native dataset requires an ordered complete zero-based timeline")
        expected = {"pitch_id": manifest["pitch_id"], "backend": manifest["backend"]["name"],
                    "topology": manifest["topology"], "image_size": manifest["image_size"],
                    "source_video_sha256": manifest["video"]["sha256"]}
        if any(item[key] != value for key, value in expected.items()):
            raise ValueError("Native frame differs from its source manifest")
        timestamp = item["timestamp_ms"]
        if (index == 0 and timestamp != 0) or (previous_timestamp is not None and timestamp <= previous_timestamp):
            raise ValueError("Native timestamps must begin at zero and increase without shifting")
        previous_timestamp = timestamp
    return result


def write_dataset(folder: str | Path, manifest: dict,
                  frames: Iterable[NativePoseFrame | dict]) -> None:
    """Validate all rows before creating a fresh, non-overwriting dataset."""
    rows = _dataset_frames(manifest, frames)
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=False)
    write_json(target / "native_pose_manifest.json", manifest)
    with (target / "native_keypoints.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row.to_dict(), ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_dataset(folder: str | Path) -> tuple[dict, list[NativePoseFrame]]:
    target = Path(folder)
    manifest = read_json(target / "native_pose_manifest.json")
    rows = []
    with (target / "native_keypoints.jsonl").open(encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip():
                raise ValueError("Blank native frame row is not permitted")
            rows.append(NativePoseFrame(_loads(line)))
    return manifest, _dataset_frames(manifest, rows)
