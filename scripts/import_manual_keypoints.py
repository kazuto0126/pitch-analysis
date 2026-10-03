"""Convert independent CVAT image skeleton annotations to a separate human XY reference."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "annotations" / "manual_keypoints"
MAX_XML_BYTES = 16 * 1024 * 1024


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_cvat(path: Path) -> bytes:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            candidates = [entry for entry in archive.infolist()
                          if PurePosixPath(entry.filename).name == "annotations.xml"]
            if len(candidates) != 1:
                raise ValueError("CVAT ZIP must contain exactly one annotations.xml")
            entry = candidates[0]
            if entry.file_size > MAX_XML_BYTES:
                raise ValueError("CVAT XML is too large")
            return archive.read(entry)
    if path.stat().st_size > MAX_XML_BYTES:
        raise ValueError("CVAT XML is too large")
    return path.read_bytes()


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != "manual-pose-package-v1":
        raise ValueError("Expected original manual-pose-package-v1 frame manifest")
    source = manifest["source_video"]
    if manifest["pitch_id"] != source["pitch_id"] or source["frame_index_base"] != 0:
        raise ValueError("Manifest source pitch/frame base mismatch")
    filename = source["filename"]
    if not isinstance(filename, str) or Path(filename).name != filename or Path(filename).stem != source["pitch_id"]:
        raise ValueError("Manifest source filename must identify the same pitch")
    if tuple(manifest["joint_names"]) != JOINT_NAMES:
        raise ValueError("Manifest joint order differs from the manual skeleton contract")
    if not all(type(manifest[name]) is int and manifest[name] > 0
               for name in ("image_width", "image_height")):
        raise ValueError("Manifest dimensions must be positive integers")
    frames = manifest["frames"]
    if len(frames) != source["total_frames"] or len(frames) < 2:
        raise ValueError("Manifest must cover all source frames")
    names = set()
    previous_stamp = -1.0
    for index, frame in enumerate(frames):
        name = frame["image_name"]
        if not isinstance(name, str) or not name or name != PurePosixPath(name).name or "\\" in name:
            raise ValueError("Manifest image names must be simple basenames")
        if name in names or frame["frame_index"] != index:
            raise ValueError("Manifest frame names/indices must be unique and ordered")
        names.add(name)
        stamp = frame["timestamp_ms"]
        if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= previous_stamp:
            raise ValueError("Manifest timestamps must be finite and increasing")
        if index == 0 and abs(stamp) > 1.0:
            raise ValueError("Manifest must start at clip time zero")
        previous_stamp = stamp
        if not re.fullmatch(r"[0-9a-f]{64}", frame["image_sha256"]):
            raise ValueError("Manifest requires each original PNG SHA-256")


def verify_source_timeline(manifest: dict, video: Path) -> None:
    source = manifest["source_video"]
    if video.name != source["filename"] or digest(video) != source["sha256"]:
        raise ValueError("Source filename or SHA-256 differs from the frame manifest")
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot decode the bound source video")
        for expected in manifest["frames"]:
            ok, image = capture.read()
            if not ok or image is None:
                raise ValueError("Source has fewer decoded frames than the manifest")
            if image.shape[:2] != (manifest["image_height"], manifest["image_width"]):
                raise ValueError("Source image dimensions differ from the manifest")
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC)
            if not math.isfinite(timestamp) or abs(timestamp - expected["timestamp_ms"]) > 1.0:
                raise ValueError("Source timestamps differ from the frame manifest")
            ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if not ok or hashlib.sha256(encoded.tobytes()).hexdigest() != expected["image_sha256"]:
                raise ValueError("Original PNG hash differs from the decoded source frame")
        if capture.read()[0]:
            raise ValueError("Source has more decoded frames than the manifest")
    finally:
        capture.release()


def convert_cvat(xml_bytes: bytes, manifest: dict, *, reviewer: str,
                 status: str = "in_progress", reviewed_at_utc: str | None = None) -> dict:
    validate_manifest(manifest)
    if not reviewer.strip():
        raise ValueError("Use the actual human reviewer name or pseudonym")
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", xml_bytes, re.IGNORECASE):
        raise ValueError("CVAT XML cannot contain DTD/entity declarations")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise ValueError("Invalid CVAT XML") from error
    if root.tag != "annotations" or root.find("track") is not None:
        raise ValueError("Use CVAT for images with per-frame Shape skeletons, not tracks")
    frame_by_name = {frame["image_name"]: frame for frame in manifest["frames"]}
    annotated = {}
    for image in root.findall("image"):
        name = PurePosixPath(image.get("name", "").replace("\\", "/")).name
        if name not in frame_by_name or name in annotated:
            raise ValueError("Unknown or duplicate original image name in CVAT export")
        expected = frame_by_name[name]
        if int(image.get("width", "0")) != manifest["image_width"] or int(image.get("height", "0")) != manifest["image_height"]:
            raise ValueError("CVAT image dimensions differ from the original images")
        if int(image.get("id", "-1")) != expected["frame_index"]:
            raise ValueError("CVAT image ID differs from the original frame index")
        skeletons = image.findall("skeleton")
        if len(skeletons) > 1 or any(shape.get("label") != "PITCHER_2D" for shape in skeletons):
            raise ValueError("Each frame may contain only one PITCHER_2D skeleton")
        joints = {}
        if skeletons:
            skeleton = skeletons[0]
            if skeleton.get("source") == "auto" or skeleton.get("track_id") is not None:
                raise ValueError("Independent manual review cannot import auto/track annotations")
            for point in skeleton.findall("points"):
                label = point.get("label")
                if label not in JOINT_NAMES or label in joints:
                    raise ValueError("Unknown or duplicate skeleton joint")
                if point.get("source") == "auto":
                    raise ValueError("Auto-annotated coordinates are not independent human labels")
                attributes = {}
                for attribute in point.findall("attribute"):
                    attr_name = attribute.get("name")
                    if attr_name in attributes:
                        raise ValueError("Duplicate CVAT point attribute")
                    attributes[attr_name] = (attribute.text or "").strip()
                state = attributes.get("human_state", "unreviewed")
                if state not in ("visible", "uncertain", "not_observable", "unreviewed"):
                    raise ValueError("Invalid human_state; use the provided CVAT labels")
                note = attributes.get("review_note", "")
                x = y = None
                if state == "visible":
                    if point.get("outside", "0") != "0" or point.get("occluded", "0") != "0":
                        raise ValueError("Visible human coordinates cannot be marked Outside/Occluded")
                    try:
                        parts = point.get("points", "").split(",")
                        if len(parts) != 2 or ";" in point.get("points", ""):
                            raise ValueError
                        x, y = map(float, parts)
                    except ValueError as error:
                        raise ValueError("Each visible joint needs exactly one pixel coordinate pair") from error
                # CVAT's skeleton template can retain temporary coordinates for hidden points.
                # They are deliberately discarded; only visible human observations carry XY.
                joints[label] = {"name": label, "status": state, "x_px": x, "y_px": y,
                                 "confidence": None, "note": note}
        annotated[name] = joints
    frames = []
    for expected in manifest["frames"]:
        joints = annotated.get(expected["image_name"], {})
        frames.append({**expected, "joints": [joints.get(name, {
            "name": name, "status": "unreviewed", "x_px": None, "y_px": None,
            "confidence": None, "note": "",
        }) for name in JOINT_NAMES]})
    payload = {
        "schema_version": "manual-keypoints-v1", "annotation_status": status,
        "source_video": manifest["source_video"], "coordinate_system": "original_image_pixels_xy",
        "image_size": {"width": manifest["image_width"], "height": manifest["image_height"]},
        "provenance": {"reviewer": reviewer, "reviewed_at_utc": reviewed_at_utc,
                       "method": "manual_cvat_keypoints", "guidelines_version": "manual-keypoints-guidelines-v1",
                       "annotation_mode": "independent",
                       "source_annotation_sha256": hashlib.sha256(xml_bytes).hexdigest()},
        "frames": frames, "notes": [
            "Imported from CVAT per-image Shape annotations. Non-visible XY discarded; missing annotations remain unreviewed.",
            "Human reference is independent of raw predictions; this import does not train or change the pose model.",
        ],
    }
    validate_manual_keypoints(payload)
    return payload


def output_path(output_root: Path, review_id: str, pitch_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", review_id):
        raise ValueError("review-id must be a safe unique name")
    devices = {"con", "prn", "aux", "nul"} | {f"{prefix}{n}" for prefix in ("com", "lpt") for n in range(1, 10)}
    if review_id.lower() in devices or pitch_id.lower() in devices:
        raise ValueError("Reserved Windows output name")
    root = output_root.absolute()
    for component in (root, *root.parents):
        if component.is_symlink() or component.is_junction():
            raise ValueError("Output cannot use symlinks or junctions")
    root = root.resolve()
    if not root.is_relative_to(REPOSITORY_ROOT / "annotations"):
        raise ValueError("Manual reference output must stay under repository annotations")
    target = root / review_id / pitch_id / "manual_keypoints.json"
    if not target.resolve().is_relative_to(root):
        raise ValueError("Output escapes the independent reference directory")
    for component in (target.parent, *target.parent.parents):
        if component.is_symlink() or component.is_junction():
            raise ValueError("Output cannot use symlinks or junctions")
    if target.parent.exists():
        raise FileExistsError("Independent review destination already exists; use a new review ID")
    return target


def import_cvat(export: Path, frame_manifest: Path, source_video: Path, *,
                review_id: str, reviewer: str, status: str = "in_progress",
                reviewed_at_utc: str | None = None,
                output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    manifest = json.loads(frame_manifest.read_text(encoding="utf-8-sig"))
    xml_bytes = read_cvat(export)
    payload = convert_cvat(xml_bytes, manifest, reviewer=reviewer,
                           status=status, reviewed_at_utc=reviewed_at_utc)
    video = source_video.resolve(strict=True)
    verify_source_timeline(manifest, video)
    validate_manual_keypoints(payload, source_video_path=video)
    target = output_path(output_root, review_id, payload["source_video"]["pitch_id"])
    target.parent.mkdir(parents=True, exist_ok=False)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    # Preserve the exact human export as evidence alongside the converted sidecar.
    with (target.parent / "source_annotations.xml").open("xb") as stream:
        stream.write(xml_bytes)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cvat_export", type=Path)
    parser.add_argument("frame_manifest", type=Path)
    parser.add_argument("source_video", type=Path)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--status", choices=("in_progress", "reviewed"), default="in_progress")
    parser.add_argument("--reviewed-at-utc")
    args = parser.parse_args()
    try:
        result = import_cvat(args.cvat_export, args.frame_manifest, args.source_video,
                             review_id=args.review_id, reviewer=args.reviewer,
                             status=args.status, reviewed_at_utc=args.reviewed_at_utc)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(f"Saved independent manual coordinate reference: {result}")
    print("No predictions overwritten; no model training performed.")
