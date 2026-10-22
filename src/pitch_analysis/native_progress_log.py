"""Append-only, single-writer progress snapshots; no file is replaced.

Each event has its own exclusively created JSON file.  Readers may keep old
snapshots open without blocking the next event.  Interrupted, incomplete files
are ignored by readers but keep their sequence and event ID reserved.

To preserve an original exception if recording its failure also has an I/O
failure, use::

    except Exception:
        try:
            append_event(directory, 'run-failed', {'state': 'failed'})
        except OSError:
            pass
        raise

The caller owns the once-only run claim.  This helper does not retry writes or
resume any computation, and requires only one writer per directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any


_EVENT_ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}\Z')
_FILENAME = re.compile(r'([0-9]{8})_([a-z0-9][a-z0-9_-]{0,79})\.json\Z')
_SCHEMA = 'native-progress-event-v1'


def _snapshot_files(directory: Path) -> list[tuple[int, str, Path]]:
    """Include incomplete snapshots so their IDs and sequences stay reserved."""
    if not directory.exists():
        return []
    files = []
    for path in directory.iterdir():
        match = _FILENAME.fullmatch(path.name)
        if match and path.is_file():
            files.append((int(match[1]), match[2], path))
    return sorted(files, key=lambda item: (item[0], item[1]))


def append_event(directory: Path, event_id: str, payload: dict[str, Any]) -> Path:
    """Durably append one JSON snapshot, refusing a repeated event ID.

    ``event_id`` must be a lowercase safe token of at most 80 characters.
    Invalid JSON values (including NaN/infinity) fail before a file is opened.
    An I/O failure may leave an incomplete, reserved snapshot: callers must not
    retry that event or assume a failed write completed.
    """
    if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id):
        raise ValueError('event_id must be a lowercase safe token of 1-80 characters')
    if not isinstance(payload, dict):
        raise TypeError('Progress payload must be a JSON object')
    directory = Path(directory)
    existing = _snapshot_files(directory)
    if any(saved_id == event_id for _, saved_id, _ in existing):
        raise FileExistsError(f'Progress event already exists: {event_id}')
    sequence = max((number for number, _, _ in existing), default=0) + 1
    if sequence > 99_999_999:
        raise ValueError('Progress sequence exhausted')
    record = {'schema_version': _SCHEMA, 'sequence': sequence,
              'event_id': event_id, 'payload': payload}
    encoded = json.dumps(record, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, indent=2) + '\n'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{sequence:08d}_{event_id}.json'
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def read_events(directory: Path) -> list[dict[str, Any]]:
    """Return complete, valid snapshots in sequence order, skipping torn JSON.

    Files that cannot be decoded as strict JSON or whose envelope disagrees
    with their filename are incomplete for this purpose.  Other I/O errors are
    reported to the caller rather than hidden.
    """
    events = []
    for sequence, event_id, path in _snapshot_files(Path(directory)):
        try:
            with path.open(encoding='utf-8') as stream:
                record = json.load(stream, parse_constant=_reject_constant)
        except (json.JSONDecodeError, UnicodeError, ValueError):
            continue
        if (isinstance(record, dict) and record.get('schema_version') == _SCHEMA
                and type(record.get('sequence')) is int
                and record['sequence'] == sequence
                and record.get('event_id') == event_id
                and isinstance(record.get('payload'), dict)):
            events.append(record)
    return events


def _reject_constant(value: str) -> None:
    raise ValueError(f'Non-finite JSON value: {value}')


def latest_event(directory: Path) -> dict[str, Any] | None:
    """Read the latest complete event, or None when no valid snapshot exists."""
    events = read_events(directory)
    return events[-1] if events else None
