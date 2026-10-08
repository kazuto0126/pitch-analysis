"""Record explicit human input reviews for copied handoff candidates.

Completing a review only updates ``review.json``. It never promotes a candidate
or produces the analysis pipeline's input contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


REVIEW_SCHEMA = "handoff-input-review-v1"
CONCLUSIONS = frozenset({"pass", "fail", "uncertain", "not_observable"})
LOCAL_REQUIRED_REVIEWS = ("preparation_complete", "follow_through_complete")
_IDENTITY_FIELDS = ("internal_pitch_id", "original_pitch_id", "original_batch_id")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_FIELDS = {"reviewer", "reviewed_at_utc", "conclusion", "note"}
_REVIEW_FIELDS = {
    "schema", *_IDENTITY_FIELDS, "source_video_sha256", "source_json_sha256",
    "overall_status", "items",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def _timestamp(value: Any) -> str:
    value = _text(value, "reviewed_at_utc")
    if "T" not in value:
        raise ValueError("reviewed_at_utc must be an ISO datetime with an explicit timezone")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("reviewed_at_utc must be an ISO datetime with an explicit timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reviewed_at_utc must include an explicit timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _asset(asset: Any, field: str) -> tuple[str, str]:
    if not isinstance(asset, dict):
        raise ValueError(f"provenance {field} must be an object")
    name = _text(asset.get("file"), f"{field}.file")
    if name != asset["file"] or name in {".", ".."} or any(char in name for char in "/\\:\x00"):
        raise ValueError(f"{field}.file must be an original basename")
    digest = asset.get("sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise ValueError(f"{field}.sha256 must be a lowercase SHA-256 hash")
    return name, digest


def _validate_provenance(provenance: Any) -> list[str]:
    if not isinstance(provenance, dict) or provenance.get("schema") != "handoff-candidate-v1":
        raise ValueError("provenance must use schema handoff-candidate-v1")
    if provenance.get("status") != "candidate":
        raise ValueError("local input review requires candidate status")
    for field in _IDENTITY_FIELDS:
        _text(provenance.get(field), field)
    _asset(provenance.get("video"), "video")
    _asset(provenance.get("delivery_json"), "delivery_json")
    items = provenance.get("required_reviews")
    if not isinstance(items, list) or not items:
        raise ValueError("required_reviews must be a nonempty list of item names")
    for item in items:
        if _text(item, "required review item") != item:
            raise ValueError("required review item names must not have surrounding whitespace")
    if len(set(items)) != len(items):
        raise ValueError("required_reviews must not contain duplicate items")
    if not set(LOCAL_REQUIRED_REVIEWS).issubset(items):
        raise ValueError("required_reviews must include preparation_complete and follow_through_complete")
    return items


def blank_review(provenance: dict[str, Any]) -> dict[str, Any]:
    """Create a pending review without supplying any human findings."""
    required = _validate_provenance(provenance)
    return {
        "schema": REVIEW_SCHEMA,
        **{field: provenance[field] for field in _IDENTITY_FIELDS},
        "source_video_sha256": provenance["video"]["sha256"],
        "source_json_sha256": provenance["delivery_json"]["sha256"],
        "overall_status": "pending",
        "items": {item: {"history": [], "latest": None} for item in required},
    }


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _candidate_root(candidate_dir: str | os.PathLike[str]) -> Path:
    root = Path(candidate_dir).absolute()
    if _is_link(root) or not root.is_dir():
        raise ValueError("candidate_dir must be an existing local directory without a symbolic link")
    return root.resolve(strict=True)


def _inside_file(root: Path, path: Path) -> Path:
    try:
        relative = path.relative_to(root)
        current = root
        for part in relative.parts:
            current = current / part
            if _is_link(current):
                raise ValueError("candidate files must not use symbolic links or junctions")
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"candidate file must exist inside candidate_dir: {path.name}") from exc
    if not resolved.is_file():
        raise ValueError(f"candidate file must be a regular file: {path.name}")
    return resolved


def _read_json(root: Path, path: Path) -> Any:
    with _inside_file(root, path).open("r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"invalid JSON in {path.name}") from exc


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_provenance(root: Path) -> dict[str, Any]:
    provenance = _read_json(root, root / "provenance.json")
    _validate_provenance(provenance)
    for field in ("video", "delivery_json"):
        name, expected_hash = _asset(provenance[field], field)
        source = _inside_file(root, root / "source" / name)
        if _hash_file(source) != expected_hash:
            raise ValueError(f"source {field} SHA-256 differs from candidate provenance")
    return provenance


def _record(reviewer: Any, reviewed_at_utc: Any, conclusion: Any, note: Any) -> dict[str, str]:
    if not isinstance(conclusion, str) or conclusion not in CONCLUSIONS:
        raise ValueError("conclusion must be pass, fail, uncertain, or not_observable")
    return {
        "reviewer": _text(reviewer, "human reviewer"),
        "reviewed_at_utc": _timestamp(reviewed_at_utc),
        "conclusion": conclusion,
        "note": _text(note, "human review note"),
    }


def _overall_status(items: dict[str, Any]) -> str:
    conclusions = [entry["latest"]["conclusion"] if entry["latest"] else None for entry in items.values()]
    if "fail" in conclusions:
        return "rejected"
    if None in conclusions:
        return "pending"
    if any(value in {"uncertain", "not_observable"} for value in conclusions):
        return "requires_review"
    return "review_complete"


def _validate_review(review: Any, provenance: dict[str, Any]) -> dict[str, Any]:
    blank = blank_review(provenance)
    if not isinstance(review, dict) or set(review) != _REVIEW_FIELDS or review.get("schema") != REVIEW_SCHEMA:
        raise ValueError("review must use the complete handoff-input-review-v1 schema")
    for field in (*_IDENTITY_FIELDS, "source_video_sha256", "source_json_sha256"):
        if review[field] != blank[field]:
            raise ValueError(f"review {field} differs from candidate provenance")
    items = review["items"]
    if not isinstance(items, dict) or set(items) != set(blank["items"]):
        raise ValueError("review items must exactly match all required_reviews")
    for item, entry in items.items():
        if not isinstance(entry, dict) or set(entry) != {"history", "latest"} or not isinstance(entry["history"], list):
            raise ValueError(f"review item {item} must contain history and latest")
        for record in entry["history"]:
            if not isinstance(record, dict) or set(record) != _RECORD_FIELDS:
                raise ValueError(f"review item {item} contains an incomplete human record")
            if record != _record(**record):
                raise ValueError(f"review item {item} contains a record that is not normalized")
        expected_latest = entry["history"][-1] if entry["history"] else None
        if entry["latest"] != expected_latest:
            raise ValueError(f"review item {item} latest must equal the last submitted history record")
    if review["overall_status"] != _overall_status(items):
        raise ValueError("review overall_status differs from recorded human findings")
    return review


def load_review(candidate_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Read a review and validate its identities, source files, and history."""
    root = _candidate_root(candidate_dir)
    provenance = _load_provenance(root)
    return _validate_review(_read_json(root, root / "review.json"), provenance)


@contextmanager
def _review_lock(root: Path) -> Iterator[None]:
    lock = root / ".review.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise FileExistsError("candidate review is locked; another review write may be in progress") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def _atomic_write(root: Path, review: dict[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=root,
            prefix=".review.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(review, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, root / "review.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def record_review(
    candidate_dir: str | os.PathLike[str], *, item: str, reviewer: str,
    reviewed_at_utc: str, conclusion: str, note: str,
) -> dict[str, Any]:
    """Append one explicit human finding and atomically save its full history.

    The supplied date is retained as the review instant in UTC. ``latest`` is
    the last submitted record, even when that record has an earlier date.
    """
    record = _record(reviewer, reviewed_at_utc, conclusion, note)
    item = _text(item, "review item")
    root = _candidate_root(candidate_dir)
    with _review_lock(root):
        provenance = _load_provenance(root)
        review = _validate_review(_read_json(root, root / "review.json"), provenance)
        if item not in review["items"]:
            raise ValueError(f"unknown review item: {item}")
        entry = review["items"][item]
        entry["history"].append(record)
        entry["latest"] = dict(record)
        review["overall_status"] = _overall_status(review["items"])
        _validate_review(review, provenance)
        _atomic_write(root, review)
    return review
