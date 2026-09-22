"""Acquire a local or URL video without guessing stale output files."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .probe import sha256_file


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def is_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def redact_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _download_url(url: str, output_dir: Path, ffmpeg: str | None) -> tuple[Path, dict]:
    try:
        import yt_dlp
    except ImportError as error:
        raise RuntimeError(
            "URL input requires yt-dlp. Install project preprocessing dependencies first."
        ) from error

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"Download directory is not empty: {output_dir}")
    options = {
        "outtmpl": str(output_dir / "downloaded.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "restrictfilenames": True,
    }
    if ffmpeg:
        options["ffmpeg_location"] = str(ffmpeg)
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)

    candidates = sorted(
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    )
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected one downloaded video, found {len(candidates)} in {output_dir}"
        )
    selected = candidates[0]
    metadata = {
        "webpage_url": redact_url(str(info.get("webpage_url") or url)),
        "extractor": info.get("extractor_key") or info.get("extractor"),
        "source_video_id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "reported_duration_seconds": info.get("duration"),
    }
    return selected, metadata


def acquire_source(
    source: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str | None = None,
) -> dict:
    source_text = str(source)
    if is_url(source_text):
        path, remote_metadata = _download_url(source_text, Path(output_dir), ffmpeg)
        kind = "url"
        manifest_source = redact_url(source_text)
    else:
        path = Path(source_text)
        if not path.is_file():
            raise FileNotFoundError(f"Video source not found: {path}")
        remote_metadata = {}
        kind = "local_file"
        manifest_source = str(path.resolve())
    return {
        "kind": kind,
        "source": manifest_source,
        "acquired_path": str(path),
        "sha256": sha256_file(path),
        "remote_metadata": remote_metadata,
    }
