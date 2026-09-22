"""Optional, review-oriented CLIP re-identification for candidate clips."""
from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Protocol, Sequence

import cv2
import numpy as np


class EmbeddingBackend(Protocol):
    def embed(self, image: object) -> np.ndarray: ...


def _normalized(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(value))
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError("embedding must have a positive finite norm")
    return value / norm


class OpenClipBackend:
    """Lazy OpenCLIP backend; importing preprocessing does not require Torch."""

    def __init__(self, model_name: str = "RN50", pretrained: str = "openai"):
        self.model_name = model_name
        self.pretrained = pretrained
        self._model = None
        self._preprocess = None
        self._device = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import open_clip
            import torch
        except ImportError as error:
            raise RuntimeError(
                "CLIP re-identification requires requirements-reid.txt"
            ) from error
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            self.model_name,
            pretrained=self.pretrained,
            device=self._device,
        )
        self._model.eval()

    def embed(self, image: object) -> np.ndarray:
        self._load()
        import torch
        from PIL import Image

        if isinstance(image, (str, Path)):
            prepared = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            if image.ndim != 3 or image.shape[2] != 3:
                raise ValueError("OpenCV image must have three BGR channels")
            prepared = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        else:
            raise TypeError(f"Unsupported image input: {type(image)}")
        tensor = self._preprocess(prepared).unsqueeze(0).to(self._device)
        with torch.no_grad():
            features = self._model.encode_image(tensor)
        return _normalized(features.detach().cpu().numpy().reshape(-1))


class ClipReIdentifier:
    """Equal-reference prototype matching with explicit unknown/ambiguous states."""

    def __init__(
        self,
        backend: EmbeddingBackend,
        *,
        threshold: float = 0.30,
        ambiguity_margin: float = 0.03,
    ):
        if not -1.0 <= threshold <= 1.0 or ambiguity_margin < 0:
            raise ValueError("invalid re-identification threshold")
        self.backend = backend
        self.threshold = threshold
        self.ambiguity_margin = ambiguity_margin
        self.prototypes: dict[str, np.ndarray] = {}
        self.reference_counts: dict[str, int] = {}

    def register(self, pitcher_id: str, reference_images: Sequence[object]) -> None:
        if not reference_images:
            raise ValueError("at least one reference image is required")
        embeddings = [_normalized(self.backend.embed(image)) for image in reference_images]
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1:
            raise ValueError("reference embeddings have inconsistent dimensions")
        self.prototypes[pitcher_id] = _normalized(np.mean(embeddings, axis=0))
        self.reference_counts[pitcher_id] = len(embeddings)

    def match_embeddings(self, embeddings: Sequence[np.ndarray]) -> dict:
        if not self.prototypes:
            raise ValueError("no pitcher references are registered")
        if not embeddings:
            return {
                "status": "unknown",
                "pitcher_id": None,
                "score": None,
                "reason": "no_candidate_embeddings",
                "scores": {},
            }
        candidates = [_normalized(embedding) for embedding in embeddings]
        scores = {
            pitcher_id: float(
                median(float(np.dot(candidate, prototype)) for candidate in candidates)
            )
            for pitcher_id, prototype in self.prototypes.items()
        }
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_id, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else None
        if best_score < self.threshold:
            status, pitcher_id, reason = "unknown", None, "below_similarity_threshold"
        elif second_score is not None and best_score - second_score < self.ambiguity_margin:
            status, pitcher_id, reason = "ambiguous", None, "top_matches_too_close"
        else:
            status, pitcher_id, reason = "matched", best_id, None
        return {
            "status": status,
            "pitcher_id": pitcher_id,
            "score": best_score,
            "second_best_score": second_score,
            "reason": reason,
            "scores": dict(ordered),
            "sample_count": len(candidates),
            "threshold": self.threshold,
            "ambiguity_margin": self.ambiguity_margin,
            "reference_counts": dict(self.reference_counts),
            "method": "openclip-equal-reference-prototype-median-clip-score-v0.1",
        }

    def match_images(self, images: Sequence[object]) -> dict:
        return self.match_embeddings([self.backend.embed(image) for image in images])


def sample_pitcher_frames(video_path: str | Path, samples: int = 8) -> list[np.ndarray]:
    if samples < 1:
        raise ValueError("samples must be positive")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Cannot open clip for re-identification: {video_path}")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        capture.release()
        return []
    indices = np.linspace(0, frame_count - 1, num=min(samples, frame_count), dtype=int)
    frames = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if not ok:
            continue
        height, width = frame.shape[:2]
        crop = frame[
            round(height * 0.08) : round(height * 0.96),
            round(width * 0.18) : round(width * 0.82),
        ]
        if crop.size:
            frames.append(crop)
    capture.release()
    return frames


def reidentify_clip(
    video_path: str | Path,
    matcher: ClipReIdentifier,
    *,
    samples: int = 8,
) -> dict:
    result = matcher.match_images(sample_pitcher_frames(video_path, samples))
    return {
        **result,
        "clip": str(video_path),
        "review_status": "needs_human_review",
        "warning": "Center-region CLIP similarity is supporting evidence, not final identity proof.",
    }
