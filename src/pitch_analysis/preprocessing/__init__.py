"""Video-source intake and pitch-clip preparation.

This package ends at reviewable MP4 samples.  It deliberately does not bypass
the existing pose-quality, event-review, registry, or ranking gates.
"""

from .workflow import preprocess_video

__all__ = ["preprocess_video"]
