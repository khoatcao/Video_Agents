"""
Audio mixing helper for the video pipeline.

Music is split by platform to avoid copyright issues:
  assets/music/facebook/  — Facebook Sound Collection tracks (Facebook/Instagram only)
  assets/music/youtube/   — Royalty-free tracks safe for YouTube monetisation
"""

from __future__ import annotations

import logging
import random
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MUSIC_ROOT = _PROJECT_ROOT / "assets" / "music"

_PLATFORM_DIRS = {
    "facebook": _MUSIC_ROOT / "facebook",
    "youtube": _MUSIC_ROOT / "youtube",
}

_SUPPORTED_EXTS = ("*.mp3", "*.m4a", "*.mp4")


def mix_music(mp4_path: str, platform: str) -> str:
    """
    Mix a random track from assets/music/<platform>/ into the video at 20% volume.

    Creates a new file alongside the original (does NOT modify the source file),
    so both facebook and youtube agents can mix from the same base render concurrently.

    Returns the path to the mixed file on success, or the original path if skipped.
    """
    music_dir = _PLATFORM_DIRS.get(platform)
    if music_dir is None:
        logger.warning("[Audio] Unknown platform %r — skipping mix.", platform)
        return mp4_path

    tracks: list[Path] = []
    for ext in _SUPPORTED_EXTS:
        tracks.extend(music_dir.glob(ext))

    if not tracks:
        logger.info("[Audio] No tracks in %s — skipping mix for %s.", music_dir, platform)
        return mp4_path

    track = random.choice(tracks)
    output_path = mp4_path.replace(".mp4", f"_{platform}.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-i", mp4_path,
        "-i", str(track),
        "-map", "0:v",
        "-map", "1:a",
        "-filter:a", "volume=0.2",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    logger.info("[Audio] Mixing %s track: %s", platform, track.name)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        logger.warning("[Audio] ffmpeg not found — skipping mix.")
        return mp4_path
    except subprocess.TimeoutExpired:
        logger.warning("[Audio] ffmpeg timed out — skipping mix.")
        return mp4_path

    if result.returncode != 0:
        logger.warning("[Audio] ffmpeg failed: %s", result.stderr[-500:])
        return mp4_path

    logger.info("[Audio] Mixed → %s", output_path)
    return output_path
