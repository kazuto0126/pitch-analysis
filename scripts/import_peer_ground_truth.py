"""Import a human review as independent evidence, preserving its original bytes.

This creates one versioned JSON file. It never replaces canonical HSU ground
truth, edits predictions, fills missing labels, or compares reviewer judgments.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import cv2

from pitch_analysis.ground_truth import validate_ground_truth


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPOSITORY_ROOT / "annotations" / "phase2_peer_reviews"
_REVIEW_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
_WINDOWS_DEVICES = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
}
_PROTECTED_COMPONENTS = {
    "ground_truth", "ground-truth", "predictions", "prediction", "input", "inputs",
    ".git", ".agents", ".codex", ".aws",
}


def _safe_review_id(review_id: str) -> None:
    if not isinstance(review_id, str) or not _REVIEW_ID.fullmatch(review_id):
        raise ValueError("review_id must use 1-80 letters, numbers, underscores, or hyphens and start with a letter or number")
    if review_id.lower() in _WINDOWS_DEVICES:
        raise ValueError("review_id cannot be a reserved Windows device name")


def _reject_links(path: Path) -> None:
    """Reject symlinks and Windows junctions in any existing path component."""
    for component in (path, *path.parents):
        if component.is_symlink() or component.is_junction():
            raise ValueError(f"Review output cannot use a symlink or junction: {component}")


def _output_path(output_root: str | Path, review_id: str, pitch_id: str) -> Path:
    root = Path(output_root).absolute()
    _reject_links(root)
    root = root.resolve()
    if REPOSITORY_ROOT == root or REPOSITORY_ROOT.is_relative_to(root):
        raise ValueError("Review output root cannot be the repository or its ancestor")
    if root.is_relative_to(REPOSITORY_ROOT):
        relative = root.relative_to(REPOSITORY_ROOT)
        if not relative.parts or relative.parts[0].lower() != "annotations":
            raise ValueError("Review output within the repository must be under annotations")
    if any(part.lower() in _PROTECTED_COMPONENTS for part in root.parts):
        raise ValueError("Review output cannot target ground truth, input, predictions, or protected directories")
    if pitch_id.lower() in _WINDOWS_DEVICES:
        raise ValueError("pitch_id cannot be a reserved Windows device name")
    output = root / review_id / pitch_id / "ground_truth.json"
    _reject_links(output)
    if not output.resolve().is_relative_to(root):
        raise ValueError("Review output must stay within the requested output root")
    return output


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Review JSON has duplicate field: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Review JSON contains a non-finite number: {value}")


def _decoded_frame_count(video: Path) -> int:
    """Count actual source frames without reading pose or tracking outputs."""
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Source video cannot be decoded: {video}")
        total = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame is None:
                raise ValueError(f"Source video has an undecodable frame at {total}")
            total += 1
        if total < 2:
            raise ValueError("Source video must have at least two decoded frames")
        return total
    except cv2.error as error:
        raise ValueError(f"Source video cannot be decoded: {video}") from error
    finally:
        capture.release()


def import_peer_ground_truth(
    review_json: str | Path,
    source_video: str | Path,
    *,
    review_id: str,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> Path:
    """Validate and copy one review without modifying any supplied human fields.

    ``in_progress`` reviews may contain partial intervals, event supplements,
    and null labels. A ``reviewed`` review must satisfy the full review contract.
    Existing pitch destinations are refused, including empty directories.
    """
    _safe_review_id(review_id)
    review = Path(review_json).resolve(strict=True)
    video = Path(source_video).resolve(strict=True)
    if not review.is_file() or not video.is_file():
        raise ValueError("Review JSON and source video must be regular files")
    content = review.read_bytes()
    payload = json.loads(
        content.decode("utf-8-sig"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_nonfinite,
    )
    validate_ground_truth(payload, source_video_path=video)
    if payload.get("review_profile") != "phase2_full_review":
        raise ValueError("Peer import requires review_profile phase2_full_review")
    if payload["annotation_status"] not in ("in_progress", "reviewed"):
        raise ValueError("Peer import requires an in_progress or reviewed human annotation")
    pitch_id = payload["source_video"]["pitch_id"]
    if re.fullmatch(r"pitch_[0-9]+", video.stem, re.IGNORECASE) and video.stem != pitch_id:
        raise ValueError("Review pitch_id does not match the source video filename")
    output = _output_path(output_root, review_id, pitch_id)
    if output.resolve() == review or output.resolve() == video:
        raise ValueError("Review output cannot be the input review or source video")
    if output.parent.exists():
        raise FileExistsError(f"Refusing existing review destination: {output.parent}")
    actual_frames = _decoded_frame_count(video)
    if actual_frames != payload["source_video"]["total_frames"]:
        raise ValueError(
            f"Review total_frames {payload['source_video']['total_frames']} does not match "
            f"the source video's {actual_frames} decoded frames"
        )
    output.parent.parent.mkdir(parents=True, exist_ok=True)
    _reject_links(output.parent.parent)
    output.parent.mkdir(exist_ok=False)
    _reject_links(output)
    if not output.resolve().is_relative_to(Path(output_root).resolve()):
        raise ValueError("Review output must stay within the requested output root")
    with output.open("xb") as target:
        target.write(content)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_json", type=Path, help="returned human ground-truth-v1 JSON")
    parser.add_argument("source_video", type=Path, help="the original MP4 bound to this review")
    parser.add_argument("--review-id", required=True, help="versioned review identifier, for example CLASSMATE_20261003")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                        help="independent review tree (default: annotations/phase2_peer_reviews)")
    args = parser.parse_args(argv)
    try:
        output = import_peer_ground_truth(
            args.review_json, args.source_video,
            review_id=args.review_id, output_root=args.output_root,
        )
    except (OSError, ValueError, UnicodeError) as error:
        parser.error(str(error))
    print(f"Imported human review: {output}")
    print("Saved as independent evidence; canonical HSU ground truth was not replaced. No comparison performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
