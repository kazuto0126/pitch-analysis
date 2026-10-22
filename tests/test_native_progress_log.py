"""Immutable snapshots avoid replacing a file held open by a Windows reader."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pitch_analysis.native_progress_log import append_event, latest_event, read_events


class NativeProgressLogTests(unittest.TestCase):
    def test_open_old_snapshot_does_not_block_new_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'events'
            old_path = append_event(directory, 'frame-0', {'completed': 1})
            old_bytes = old_path.read_bytes()
            with old_path.open(encoding='utf-8') as reader:
                new_path = append_event(directory, 'frame-1', {'completed': 2})
                self.assertEqual(json.load(reader)['payload']['completed'], 1)
                self.assertEqual(latest_event(directory)['payload']['completed'], 2)
            self.assertNotEqual(old_path, new_path)
            self.assertEqual(old_path.read_bytes(), old_bytes)
            self.assertEqual([event['sequence'] for event in read_events(directory)], [1, 2])

    def test_duplicate_id_and_stale_listing_never_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = append_event(directory, 'completed', {'calls': 1})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                append_event(directory, 'completed', {'calls': 2})
            # A stale single-writer listing must still hit exclusive creation.
            with patch('pitch_analysis.native_progress_log._snapshot_files', return_value=[]):
                with self.assertRaises(FileExistsError):
                    append_event(directory, 'completed', {'calls': 3})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(list(directory.iterdir())), 1)

    def test_torn_failed_event_keeps_previous_event_and_reserves_sequence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.assertIsNone(latest_event(directory))
            append_event(directory, 'completed-frame', {'completed': 1})
            torn = directory / '00000002_run-failed.json'
            torn.write_text('{"schema_version":', encoding='utf-8')
            self.assertEqual(latest_event(directory)['event_id'], 'completed-frame')
            with self.assertRaises(FileExistsError):
                append_event(directory, 'run-failed', {'state': 'failed'})
            path = append_event(directory, 'cleanup-note', {'preserved': True})
            self.assertEqual(path.name, '00000003_cleanup-note.json')
            self.assertEqual([event['sequence'] for event in read_events(directory)], [1, 3])
            self.assertEqual(torn.read_text(encoding='utf-8'), '{"schema_version":')

    def test_invalid_serialization_and_unsafe_ids_leave_no_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for invalid in (float('nan'), float('inf'), object()):
                with self.subTest(value=type(invalid).__name__):
                    with self.assertRaises((ValueError, TypeError)):
                        append_event(directory, 'invalid', {'value': invalid})
            for event_id in ('../escape', 'UPPER', '', 'a/b', 'a' * 81):
                with self.subTest(event_id=event_id):
                    with self.assertRaises(ValueError):
                        append_event(directory, event_id, {})
            self.assertEqual(list(directory.iterdir()), [])

    def test_fsync_and_failure_recording_preserve_primary_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with patch('pitch_analysis.native_progress_log.os.fsync', wraps=os.fsync) as fsync:
                append_event(directory, 'started', {'state': 'started'})
                fsync.assert_called_once()
            primary = RuntimeError('original model or write failure')
            with self.assertRaises(RuntimeError) as captured:
                try:
                    raise primary
                except RuntimeError:
                    try:
                        with patch('pitch_analysis.native_progress_log.os.fsync', side_effect=OSError('disk failure')):
                            append_event(directory, 'run-failed', {'state': 'failed'})
                    except OSError:
                        pass
                    raise
            self.assertIs(captured.exception, primary)
            # Even if fsync failed after a complete write, prior snapshots stay intact.
            self.assertEqual(read_events(directory)[0]['event_id'], 'started')


if __name__ == '__main__':
    unittest.main()
