"""
Thumbnail generator — extracts frame 0 from the rendered MP4 using ffmpeg.

Output: thumbnail.jpg in the same folder as the video.
YouTube recommends 1280x720 but for Shorts (1080x1920) we keep native resolution.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_thumbnail(mp4_path: str) -> str:
    """
    Extract frame 0 from mp4_path and save as thumbnail.jpg alongside it.

    Returns the thumbnail path on success, empty string on failure.
    """
    video = Path(mp4_path)
    if not video.is_file():
        logger.warning("[Thumbnail] MP4 not found: %s", mp4_path)
        return ""

    thumbnail_path = str(video.parent / "thumbnail.jpg")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vframes", "1",
        "-q:v", "2",        # high quality JPEG
        thumbnail_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        logger.warning("[Thumbnail] ffmpeg not found — skipping thumbnail.")
        return ""
    except subprocess.TimeoutExpired:
        logger.warning("[Thumbnail] ffmpeg timed out — skipping thumbnail.")
        return ""

    if result.returncode != 0:
        logger.warning("[Thumbnail] ffmpeg failed: %s", result.stderr[-300:])
        return ""

    logger.info("[Thumbnail] Generated → %s", thumbnail_path)
    return thumbnail_path
