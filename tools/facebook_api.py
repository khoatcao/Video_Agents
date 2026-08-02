"""
Facebook / Meta Graph API integration for Reels upload and comment posting.

Upload flow (two-step resumable upload required by Meta):
  1. POST /reels/upload_session  → upload session ID + upload URL
  2. Binary POST to upload URL   → video bytes
  3. POST /<page_id>/video_reels → publish with caption
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from config.settings import FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_UPLOAD_TIMEOUT = 300   # seconds for binary video upload
_API_TIMEOUT = 30       # seconds for short API calls


class FacebookAPIError(Exception):
    """Raised when the Meta Graph API returns an error response."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def _check(response: requests.Response) -> dict:
    """Raise FacebookAPIError on non-2xx responses or Graph error objects."""
    try:
        data = response.json()
    except ValueError:
        response.raise_for_status()
        return {}

    if "error" in data:
        err = data["error"]
        raise FacebookAPIError(
            f"{err.get('message', 'Unknown error')} "
            f"(type={err.get('type')}, code={err.get('code')})",
            code=err.get("code"),
        )
    response.raise_for_status()
    return data


def upload_facebook_reel(mp4_path: str, caption: str) -> str:
    """
    Upload an MP4 as a Facebook Reel on the configured Page and publish it.

    Uses Meta's two-step resumable upload protocol:
      1. Initialise an upload session to obtain an upload URL.
      2. POST the raw video bytes to that URL.
      3. Publish the reel with the caption.

    Args:
        mp4_path: Absolute path to the rendered MP4 file.
        caption:  Post caption (Vietnamese text + hashtags).

    Returns:
        The Facebook post ID of the published Reel (e.g. "123456789_987654321").

    Raises:
        FileNotFoundError: if mp4_path does not exist.
        FacebookAPIError:  on Graph API errors.
    """
    path = Path(mp4_path)
    if not path.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4_path}")

    file_size = path.stat().st_size

    # ── Step 1: Initialise upload session ────────────────────────────────────
    init_resp = requests.post(
        f"{_GRAPH_BASE}/{FACEBOOK_PAGE_ID}/video_reels",
        params={"access_token": FACEBOOK_ACCESS_TOKEN},
        json={
            "upload_phase": "start",
            "file_size": file_size,
        },
        timeout=_API_TIMEOUT,
    )
    init_data = _check(init_resp)
    video_id: str = init_data["video_id"]
    upload_url: str = init_data["upload_url"]
    logger.info("Facebook upload session started. video_id=%s", video_id)

    # ── Step 2: Upload raw video bytes ────────────────────────────────────────
    with path.open("rb") as fh:
        video_bytes = fh.read()

    upload_resp = requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {FACEBOOK_ACCESS_TOKEN}",
            "offset": "0",
            "file_size": str(file_size),
        },
        data=video_bytes,
        timeout=_UPLOAD_TIMEOUT,
    )
    upload_data = _check(upload_resp)
    if not upload_data.get("success"):
        raise FacebookAPIError("Video binary upload did not return success=true")
    logger.info("Facebook video bytes uploaded successfully for video_id=%s", video_id)

    # ── Step 3: Publish the reel ──────────────────────────────────────────────
    publish_resp = requests.post(
        f"{_GRAPH_BASE}/{FACEBOOK_PAGE_ID}/video_reels",
        params={"access_token": FACEBOOK_ACCESS_TOKEN},
        json={
            "upload_phase": "finish",
            "video_id": video_id,
            "description": caption,
            "video_state": "PUBLISHED",
        },
        timeout=_API_TIMEOUT,
    )
    publish_data = _check(publish_resp)

    post_id: str = publish_data.get("post_id") or f"{FACEBOOK_PAGE_ID}_{video_id}"
    logger.info("Facebook Reel published. post_id=%s", post_id)
    return post_id


def post_facebook_comment(post_id: str, comment: str) -> str:
    """
    Post a comment on an existing Facebook Page post (e.g. affiliate links).

    Args:
        post_id: The Facebook post ID returned by upload_facebook_reel.
        comment: Comment text (Vietnamese + affiliate URLs).

    Returns:
        The comment ID string.

    Raises:
        FacebookAPIError: on Graph API errors.
    """
    resp = requests.post(
        f"{_GRAPH_BASE}/{post_id}/comments",
        params={"access_token": FACEBOOK_ACCESS_TOKEN},
        json={"message": comment},
        timeout=_API_TIMEOUT,
    )
    data = _check(resp)
    comment_id: str = data["id"]
    logger.info("Facebook comment posted. comment_id=%s", comment_id)
    return comment_id
