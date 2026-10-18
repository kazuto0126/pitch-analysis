"""Native datasets preserve complete frames and cannot overwrite bound sources."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from pitch_analysis.native_pose import NativePoseFrame
from pitch_analysis.native_pose_io import (
    BoundReader, read_dataset, read_json, reference, sha256, write_dataset, write_json,
)
from test_native_pose_contract import make_frame, make_manifest


class NativePoseIOTests(unittest.TestCase):
    def test_complete_both_topologies_round_trip_without_clipping_or_gating(self):
        with tempfile.TemporaryDirectory() as temporary:
            for topology in ("mediapipe_33", "coco_17"):
                manifest = make_manifest(topology)
                frames = [NativePoseFrame(make_frame(topology, index)) for index in range(2)]
                folder = Path(temporary) / topology
                write_dataset(folder, manifest, frames)
                restored_manifest, restored = read_dataset(folder)
                self.assertEqual(restored_manifest, manifest)
                self.assertEqual([row.to_dict() for row in restored], [row.to_dict() for row in frames])
                self.assertEqual(restored[0].to_dict()["landmarks"][0]["x_px"], -2.5)

    def test_invalid_complete_timeline_and_source_binding_fail_before_creating_output(self):
        cases = []
        cases.append([make_frame()])
        cases.append([make_frame(index=1), make_frame(index=0)])
        cases.append([make_frame(index=0), make_frame(index=0)])
        bad = [make_frame(index=index) for index in range(2)]
        bad[1]["source_video_sha256"] = "f" * 64
        cases.append(bad)
        for field, value in (("backend", "other"), ("pitch_id", "other"),
                             ("image_size", {"width": 101, "height": 200})):
            bad = [make_frame(index=index) for index in range(2)]
            bad[1][field] = value
            cases.append(bad)
        with tempfile.TemporaryDirectory() as temporary:
            for index, frames in enumerate(cases):
                output = Path(temporary) / str(index)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    write_dataset(output, make_manifest(), frames)
                self.assertFalse(output.exists())

    def test_shifted_or_nonincreasing_timestamps_are_not_silently_recomputed(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, timestamps in enumerate(((1, 34), (0, 0), (0, -1))):
                frames = [make_frame(index=i) for i in range(2)]
                for frame, timestamp in zip(frames, timestamps):
                    frame["timestamp_ms"] = timestamp
                with self.subTest(timestamps=timestamps), self.assertRaises(ValueError):
                    write_dataset(Path(temporary) / str(index), make_manifest(), frames)

    def test_dataset_and_json_writes_refuse_to_overwrite_existing_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "out"
            manifest, frames = make_manifest(), [make_frame(index=i) for i in range(2)]
            write_dataset(folder, manifest, frames)
            before = {path.name: sha256(path) for path in folder.iterdir()}
            with self.assertRaises(FileExistsError):
                write_dataset(folder, manifest, frames)
            with self.assertRaises(FileExistsError):
                write_json(folder / "native_pose_manifest.json", {"overwrite": True})
            self.assertEqual(before, {path.name: sha256(path) for path in folder.iterdir()})

    def test_read_dataset_revalidates_changed_rows_and_missing_or_blank_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "out"
            frames = [make_frame(index=i) for i in range(2)]
            write_dataset(folder, make_manifest(), frames)
            stream = folder / "native_keypoints.jsonl"
            for rows in ([frames[0]], [frames[0], frames[0]]):
                stream.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_dataset(folder)
            stream.write_text("\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Blank"):
                read_dataset(folder)

    def test_bound_reader_allowlist_hash_and_multiple_instances(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.json"
            write_json(source, {"unchanged": True})
            ref = reference(root, source)
            first, second = BoundReader(root, [ref]), BoundReader(root, [ref])
            self.assertEqual(first.json(ref), {"unchanged": True})
            self.assertEqual(first.opened, ["source.json"])
            self.assertEqual(second.opened, [])
            with self.assertRaisesRegex(ValueError, "not allowed"):
                BoundReader(root, []).path(ref)
            changed_ref = deepcopy(ref)
            changed_ref["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                first.path(changed_ref)
            source.write_text('{"changed":true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Changed"):
                first.path(ref)

    def test_source_references_reject_external_absolute_or_traversal_paths(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            root, external = Path(first), Path(second) / "outside.json"
            write_json(external, {"secret": "fixture"})
            with self.assertRaises(ValueError):
                reference(root, external)
            for path in ("../outside.json", external.as_posix(), "C:/outside.json", "x\\y"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    BoundReader(root, [{"path": path, "sha256": sha256(external)}])

    def test_nonfinite_and_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "value.json"
            for body in ('{"a":NaN}', '{"a":Infinity}', '{"a":1e999}', '{"a":1,"a":2}'):
                path.write_text(body, encoding="utf-8")
                with self.subTest(body=body), self.assertRaises(ValueError):
                    read_json(path)
            output = Path(temporary) / "invalid.json"
            with self.assertRaises(ValueError):
                write_json(output, {"nested": [float("nan")]})
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
