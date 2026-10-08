"""Import indexed deliveries into an isolated, durable candidate store.

No inference, formal-input conversion, event labeling, or promotion is performed.
The delivery tree is only read. SQLite serializes importers; staged candidates
are renamed before their ledger row is saved, allowing verified crash recovery.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Callable

from .contract import HandoffError, validate_batch, validate_index, validate_pitch
from .review import blank_review, load_review
from .timing import verify_timing


PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOCAL_ID = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _identifier(value: str, prefix: str = "h_") -> str:
    return prefix + _hash(value.encode("utf-8"))


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _json_bytes(data: bytes, label: str):
    try:
        return json.loads(data.decode("utf-8-sig"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError) as exc:
        raise HandoffError("invalid_json", f"{label} is not valid finite JSON") from exc


def _write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _local_path(intake: Path, relative: str) -> Path:
    path = intake / relative
    current = intake
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise HandoffError("unsafe_local_path", "Local intake files cannot use symbolic links or junctions")
    resolved = path.resolve()
    if resolved == intake or not _inside(resolved, intake):
        raise HandoffError("unsafe_local_path", "Local intake path must remain inside its isolated store")
    return path


def _source_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise HandoffError("unsafe_path", "Delivery path must be nonempty relative text")
    normalized = relative.replace("\\", "/")
    windows = PureWindowsPath(relative)
    if windows.drive or windows.root or normalized.startswith("/") or any(part in ("..", "") for part in normalized.split("/")):
        raise HandoffError("unsafe_path", "Delivery path cannot be absolute or escape its delivery directory", {"path": relative})
    try:
        path = (root / normalized).resolve(strict=True)
        if not _inside(path, root) or not path.is_file():
            raise HandoffError("unsafe_path", "Delivery file must resolve inside its delivery directory", {"path": relative})
        return path
    except OSError as exc:
        raise HandoffError("source_unavailable", "Referenced delivery file could not be read", {"path": relative}) from exc


def local_intake_root(intake_root, project_root=PROJECT_ROOT) -> Path:
    """Resolve a dedicated store after refusing aliases of the project data path."""
    project = Path(project_root).resolve(strict=True)
    original = Path(intake_root).absolute()
    try:
        relative = original.relative_to(project)
    except ValueError as exc:
        raise ValueError("intake_root must be below this project's data/intake") from exc
    if len(relative.parts) < 3 or tuple(part.lower() for part in relative.parts[:2]) != ("data", "intake") or ".." in relative.parts:
        raise ValueError("intake_root must be a dedicated directory below project_root/data/intake")
    current = project
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("intake_root components cannot use symbolic links or junctions")
    intake = Path(intake_root).resolve()
    allowed = (project / "data" / "intake").resolve()
    if not _inside(allowed, project) or intake == allowed or not _inside(intake, allowed):
        raise ValueError("intake_root must be a dedicated directory below project_root/data/intake")
    return intake


def _locations(handoff_root, intake_root, project_root) -> tuple[Path, Path]:
    handoff = Path(handoff_root).resolve(strict=True)
    intake = local_intake_root(intake_root, project_root)
    if not handoff.is_dir():
        raise ValueError("handoff_root must be an existing directory")
    if _inside(intake, handoff) or _inside(handoff, intake):
        raise ValueError("intake_root and the read-only delivery folder must be disjoint")
    return handoff, intake


def _pitcher_map(pitcher_map_path, pitcher_map) -> dict[str, str]:
    if pitcher_map_path is not None and pitcher_map is not None:
        raise ValueError("Provide either pitcher_map_path or pitcher_map, not both")
    if pitcher_map_path is not None:
        document = _json_bytes(Path(pitcher_map_path).read_bytes(), "local pitcher map")
        if not isinstance(document, dict) or document.get("schema") != "handoff-pitcher-map-v1":
            raise ValueError("Local pitcher map must use handoff-pitcher-map-v1")
        pitcher_map = document.get("pitchers")
    if pitcher_map is None:
        pitcher_map = {}
    if not isinstance(pitcher_map, dict):
        raise ValueError("pitcher map must be an exact name to local ID mapping")
    for name, local_id in pitcher_map.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(local_id, str) or not _LOCAL_ID.fullmatch(local_id):
            raise ValueError("pitcher map requires nonempty original names and valid local IDs")
    return dict(pitcher_map)


def _database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS batches (
          original_batch_id TEXT PRIMARY KEY, index_sha256 TEXT NOT NULL,
          batch_sha256 TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pitches (
          original_pitch_id TEXT PRIMARY KEY, original_batch_id TEXT NOT NULL,
          internal_pitch_id TEXT NOT NULL UNIQUE, json_sha256 TEXT NOT NULL,
          video_sha256 TEXT NOT NULL, status TEXT NOT NULL, candidate_dir TEXT,
          code TEXT, provenance_sha256 TEXT, timeline_sha256 TEXT);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, recorded_at_utc TEXT NOT NULL,
          batch_id TEXT, pitch_id TEXT, status TEXT NOT NULL, code TEXT, details TEXT NOT NULL);
    """)
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    return connection


def _event(connection, run_id: str, batch_id, pitch_id, status: str, code=None, details=None) -> None:
    connection.execute(
        "INSERT INTO events(run_id,recorded_at_utc,batch_id,pitch_id,status,code,details) VALUES(?,?,?,?,?,?,?)",
        (run_id, _now(), batch_id, pitch_id, status, code, json.dumps(details or {}, ensure_ascii=False, allow_nan=False)),
    )


def _persist_pitch(connection, *, pitch_id, batch_id, internal_id, json_hash, video_hash, status, candidate_dir=None, code=None) -> None:
    """Ledger write after the candidate rename (a recoverable crash boundary)."""
    connection.execute(
        "INSERT INTO pitches VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(original_pitch_id) DO UPDATE SET status=excluded.status,candidate_dir=excluded.candidate_dir,code=excluded.code,provenance_sha256=excluded.provenance_sha256,timeline_sha256=excluded.timeline_sha256",
        (pitch_id, batch_id, internal_id, json_hash, video_hash, status, str(candidate_dir) if candidate_dir else None, code,
         _hash_file(candidate_dir / "provenance.json") if candidate_dir else None,
         _hash_file(candidate_dir / "timeline.json") if candidate_dir else None),
    )


def _verified_candidate(destination: Path, provenance: dict, prior=None, timing: dict | None = None) -> None:
    try:
        provenance_data = (destination / "provenance.json").read_bytes()
        existing = _json_bytes(provenance_data, "local provenance")
        if not isinstance(existing, dict):
            raise ValueError("Local provenance must be an object")
        if prior is not None and (_hash(provenance_data) != prior["provenance_sha256"] or _hash_file(destination / "timeline.json") != prior["timeline_sha256"]):
            raise ValueError("Local immutable evidence differs from import ledger")
        # Local mapping and import date are frozen at first import, not silently updated.
        for field in (
            "schema", "status", "internal_pitch_id", "original_pitch_id", "original_batch_id",
            "video", "delivery_json", "batch_sha256", "index_entry_sha256", "required_reviews",
            "contract_version", "pitcher_name", "throws", "context", "source_identity", "view",
            "pipeline_anchors_sec", "pipeline_anchors_are_biomechanical_events", "quality_warning",
            "warnings", "source_paths",
        ):
            if existing.get(field) != provenance[field]:
                raise ValueError(f"Local provenance differs: {field}")
        timeline_data = (destination / "timeline.json").read_bytes()
        if _hash(timeline_data) != existing.get("timeline_sha256"):
            raise ValueError("Local timing evidence differs from frozen provenance")
        timeline = _json_bytes(timeline_data, "local timeline")
        if not isinstance(timeline, dict):
            raise ValueError("Local timeline must be an object")
        if timeline.get("source_video_sha256") != provenance["video"]["sha256"] or timeline.get("internal_pitch_id") != provenance["internal_pitch_id"]:
            raise ValueError("Local timeline binding differs")
        if timing is not None:
            for field in ("pitcher_id", "metadata_blockers"):
                if existing.get(field) != provenance[field]:
                    raise ValueError(f"Recovered local mapping disagrees with explicit map: {field}")
            for field in ("frame_count", "fractional_fps", "timestamps_ms", "native_pts_ms", "normalized_pts_ms", "deviations_ms", "max_abs_deviation_ms"):
                if timeline.get(field) != timing[field]:
                    raise ValueError(f"Recovered timing evidence disagrees with fresh verification: {field}")
        load_review(destination)
    except (OSError, ValueError) as exc:
        raise HandoffError("local_candidate_conflict", "Existing candidate cannot be safely reused", {"error": str(exc)}) from exc


def _candidate(intake: Path, video: Path, json_data: bytes, provenance: dict, timeline: dict) -> Path:
    destination = _local_path(intake, "candidates/" + provenance["internal_pitch_id"])
    if destination.exists():
        _verified_candidate(destination, provenance, timing=timeline)
        return destination
    stage = _local_path(intake, ".staging/" + provenance["internal_pitch_id"] + "." + uuid.uuid4().hex)
    stage.mkdir(parents=True)
    try:
        source = stage / "source"
        source.mkdir()
        copied_video = source / provenance["video"]["file"]
        shutil.copyfile(video, copied_video)
        (source / provenance["delivery_json"]["file"]).write_bytes(json_data)
        if _hash_file(copied_video) != provenance["video"]["sha256"]:
            raise HandoffError("copy_sha256_mismatch", "Copied MP4 SHA-256 differs from verified delivery")
        if _hash_file(source / provenance["delivery_json"]["file"]) != provenance["delivery_json"]["sha256"]:
            raise HandoffError("copy_sha256_mismatch", "Copied JSON SHA-256 differs from delivery")
        _write_json(stage / "timeline.json", timeline)
        provenance["timeline_sha256"] = _hash_file(stage / "timeline.json")
        _write_json(stage / "provenance.json", provenance)
        _write_json(stage / "review.json", blank_review(provenance))
        load_review(stage)
        destination.parent.mkdir(exist_ok=True)
        stage.rename(destination)
        return destination
    finally:
        if stage.exists():
            resolved_stage = stage.resolve(strict=True)
            staging_root = (intake / ".staging").resolve(strict=True)
            if resolved_stage == staging_root or not _inside(resolved_stage, staging_root):
                raise ValueError("Unsafe staging cleanup target")
            shutil.rmtree(resolved_stage)


def _snapshot_batch(intake: Path, batch_id: str, index: dict, batch_data: bytes, contract_data: bytes) -> None:
    destination = _local_path(intake, "batches/" + _identifier(batch_id, "b_"))
    destination.mkdir(parents=True, exist_ok=True)
    expected = {"batch.json": batch_data, "index_entry.json": _canonical(index), "CONTRACT.md": contract_data}
    for name, data in expected.items():
        path = _local_path(intake, "batches/" + _identifier(batch_id, "b_") + "/" + name)
        if path.exists():
            # A newer delivery spec may be snapshotted by a new batch; old batches stay frozen.
            if name != "CONTRACT.md" and path.read_bytes() != data:
                raise HandoffError("local_batch_conflict", "Existing local batch snapshot differs", {"file": name})
        else:
            path.write_bytes(data)


def import_handoff(handoff_root, intake_root, *, pitcher_map_path=None, pitcher_map=None, ffprobe_path=None, timing_verifier: Callable | None = None, project_root=PROJECT_ROOT) -> dict:
    """Read only indexed v2 batches and import valid clips as pending candidates."""
    handoff, intake = _locations(handoff_root, intake_root, project_root)
    mapping = _pitcher_map(pitcher_map_path, pitcher_map)
    timing_verifier = timing_verifier or verify_timing
    # Read required discovery/spec files before any local mutation.
    contract_data = _source_file(handoff, "CONTRACT.md").read_bytes()
    lines = _source_file(handoff, "index.jsonl").read_bytes().decode("utf-8-sig").splitlines()
    intake.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ_") + uuid.uuid4().hex[:8]
    report = {"schema": "handoff-import-report-v1", "run_id": run_id, "status": "complete", "handoff_root": str(handoff), "intake_root": str(intake), "started_at_utc": _now(), "contract_sha256": _hash(contract_data), "batches_seen": 0, "imported_candidates": 0, "already_imported": 0, "rejected": 0, "conflicts": 0, "results": [], "analysis_executed": False, "formal_inputs_modified": False}
    connection = _database(_local_path(intake, "state.sqlite3"))
    try:
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            report["batches_seen"] += 1
            result = {"batch_id": None, "status": "rejected", "index_line": line_number, "pitches": []}
            report["results"].append(result)
            try:
                index = _json_bytes(line.encode("utf-8"), f"index line {line_number}")
                if isinstance(index, dict) and isinstance(index.get("batch_id"), str):
                    result["batch_id"] = index["batch_id"]
                validate_index(index)
                batch_id = index["batch_id"]
                index_hash = _hash(_canonical(index))
                prior_batch = connection.execute("SELECT * FROM batches WHERE original_batch_id=?", (batch_id,)).fetchone()
                if prior_batch and prior_batch["index_sha256"] != index_hash:
                    raise HandoffError("immutable_conflict", "Previously seen batch has a changed index entry")
                batch_path = _source_file(handoff, index["batch_json"])
                batch_data = batch_path.read_bytes()
                batch_hash = _hash(batch_data)
                if prior_batch and prior_batch["batch_sha256"] != batch_hash:
                    raise HandoffError("immutable_conflict", "Previously seen batch JSON has changed")
                batch = _json_bytes(batch_data, "batch.json")
                validate_batch(batch, index)
                _snapshot_batch(intake, batch_id, index, batch_data, contract_data)
                connection.execute("INSERT OR IGNORE INTO batches VALUES(?,?,?,?)", (batch_id, index_hash, batch_hash, "pending"))
                for item in batch["pitches"]:
                    pitch_id = item["pitch_id"]
                    internal_id = _identifier(pitch_id)
                    pitch_result = {"pitch_id": pitch_id, "internal_pitch_id": internal_id, "status": "rejected"}
                    result["pitches"].append(pitch_result)
                    json_hash = video_hash = None
                    prior = connection.execute("SELECT * FROM pitches WHERE original_pitch_id=?", (pitch_id,)).fetchone()
                    try:
                        json_path = _source_file(batch_path.parent, item["json"])
                        video_path = _source_file(batch_path.parent, item["video_file"])
                        json_data = json_path.read_bytes()
                        json_hash, video_hash = _hash(json_data), _hash_file(video_path)
                        if prior and (prior["original_batch_id"] != batch_id or prior["json_sha256"] != json_hash or prior["video_sha256"] != video_hash):
                            raise HandoffError("immutable_conflict", "Previously seen pitch files have changed")
                        payload = _json_bytes(json_data, "pitch JSON")
                        mapped = validate_pitch(payload, batch, item)
                        if video_hash != payload["sha256"].lower():
                            raise HandoffError("sha256_mismatch", "Delivered MP4 SHA-256 differs from pitch JSON", {"expected": payload["sha256"].lower(), "actual": video_hash})
                        local_pitcher = mapping.get(mapped["pitcher_name"])
                        blockers = []
                        if local_pitcher is None:
                            blockers.append("pitcher_id_unmapped")
                        if mapped["throws"] is None:
                            blockers.append("throws_unknown")
                        provenance = {
                            "schema": "handoff-candidate-v1", "status": "candidate", "internal_pitch_id": internal_id,
                            "original_pitch_id": pitch_id, "original_batch_id": batch_id,
                            "contract_version": 2, "imported_at_utc": _now(), "contract_sha256": _hash(contract_data),
                            "batch_sha256": batch_hash, "index_entry_sha256": index_hash,
                            "video": {"file": video_path.name, "sha256": video_hash},
                            "delivery_json": {"file": json_path.name, "sha256": json_hash},
                            **mapped, "pitcher_id": local_pitcher, "metadata_blockers": blockers,
                            "view": payload["view"], "pipeline_anchors_sec": payload["pipeline_anchors_sec"],
                            "pipeline_anchors_are_biomechanical_events": False,
                            "quality_warning": batch["quality_warning"], "warnings": batch["warnings"],
                            "source_paths": {"batch_json": index["batch_json"], "video": video_path.relative_to(handoff).as_posix(), "json": json_path.relative_to(handoff).as_posix()},
                        }
                        destination = _local_path(intake, "candidates/" + internal_id)
                        if prior and prior["status"] == "imported":
                            _verified_candidate(destination, provenance, prior=prior)
                            pitch_result.update(status="already_imported", candidate_dir=str(destination))
                            report["already_imported"] += 1
                        else:
                            # A rename without a committed ledger row requires fresh timing verification.
                            if destination.exists():
                                timing = timing_verifier(video_path, payload["video"], ffprobe_path=ffprobe_path)
                                _verified_candidate(destination, provenance, timing=timing)
                            else:
                                timing = timing_verifier(video_path, payload["video"], ffprobe_path=ffprobe_path)
                                timeline = {**timing, "schema": "handoff-timeline-v1", "internal_pitch_id": internal_id, "source_video_sha256": video_hash, "frame_origin": 0, "time_rule": "frame_index / fps_float", "validation_time_rule": "(native PTS - first PTS) compared with frame_index / fractional fps", "container_start_time_applied": False, "biomechanical_events": None}
                                destination = _candidate(intake, video_path, json_data, provenance, timeline)
                            _persist_pitch(connection, pitch_id=pitch_id, batch_id=batch_id, internal_id=internal_id, json_hash=json_hash, video_hash=video_hash, status="imported", candidate_dir=destination)
                            pitch_result.update(status="imported", candidate_dir=str(destination))
                            report["imported_candidates"] += 1
                        _event(connection, run_id, batch_id, pitch_id, pitch_result["status"])
                    except (HandoffError, OSError) as exc:
                        code = exc.code if isinstance(exc, HandoffError) else "source_io_error"
                        is_conflict = "conflict" in code
                        pitch_result.update(status="conflict" if is_conflict else "rejected", code=code, reason=str(exc), details=getattr(exc, "details", None))
                        report["conflicts" if is_conflict else "rejected"] += 1
                        if json_hash and video_hash and not prior:
                            _persist_pitch(connection, pitch_id=pitch_id, batch_id=batch_id, internal_id=internal_id, json_hash=json_hash, video_hash=video_hash, status="rejected", code=code)
                        _event(connection, run_id, batch_id, pitch_id, pitch_result["status"], code, {"reason": str(exc), "details": getattr(exc, "details", None)})
                states = {pitch["status"] for pitch in result["pitches"]}
                result["status"] = "complete" if states <= {"imported", "already_imported"} else "partial" if states & {"imported", "already_imported"} else "rejected"
                connection.execute("UPDATE batches SET status=? WHERE original_batch_id=?", (result["status"], batch_id))
                _event(connection, run_id, batch_id, None, result["status"])
            except (HandoffError, OSError) as exc:
                code = exc.code if isinstance(exc, HandoffError) else "source_io_error"
                is_conflict = "conflict" in code
                result.update(status="conflict" if is_conflict else "rejected", code=code, reason=str(exc), details=getattr(exc, "details", None))
                report["conflicts" if is_conflict else "rejected"] += 1
                _event(connection, run_id, result["batch_id"], None, result["status"], code, {"reason": str(exc), "details": getattr(exc, "details", None)})
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    report["finished_at_utc"] = _now()
    if report["conflicts"] or report["rejected"]:
        report["status"] = "needs_attention"
    reports = _local_path(intake, "reports")
    reports.mkdir(exist_ok=True)
    path = reports / (run_id + ".json")
    report["report_path"] = str(path)
    _write_json(path, report)
    return report


def list_candidates(intake_root) -> list[dict]:
    """Read local ledger identities and validated human-review status only."""
    intake = Path(intake_root).resolve(strict=True)
    database = intake / "state.sqlite3"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM pitches ORDER BY original_batch_id,original_pitch_id").fetchall()
    results = []
    for row in rows:
        value = dict(row)
        if row["status"] == "imported":
            value["review_status"] = load_review(intake / "candidates" / row["internal_pitch_id"])["overall_status"]
        results.append(value)
    return results
