"""
YouTube Data API v3 uploader.

Handles OAuth2 token refresh + resumable upload for YouTube Shorts.
The caller supplies the MP4 path and metadata; this module returns the
public video URL once the upload is complete.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import google.oauth2.credentials
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http

from config.settings import (
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
)

logger = logging.getLogger(__name__)

_YOUTUBE_API_SERVICE = "youtube"
_YOUTUBE_API_VERSION = "v3"
_YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB resumable chunks


def _build_youtube_client() -> googleapiclient.discovery.Resource:
    """Build an authenticated YouTube API client from stored OAuth2 tokens."""
    credentials = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri=_TOKEN_URI,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=[_YOUTUBE_UPLOAD_SCOPE],
    )
    return googleapiclient.discovery.build(
        _YOUTUBE_API_SERVICE,
        _YOUTUBE_API_VERSION,
        credentials=credentials,
        cache_discovery=False,
    )


def upload_youtube_short(
    mp4_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "28",
    privacy_status: str = "public",
) -> str:
    """
    Upload an MP4 file as a YouTube Short and return its public URL.

    The function uses a resumable upload so large files do not time out.
    `#Shorts` is appended to the title automatically if absent.

    Args:
        mp4_path:       Absolute path to the rendered MP4 file.
        title:          Video title (max 100 chars).
        description:    Full video description.
        tags:           List of tag strings (no leading #).
        category_id:    YouTube category ID. Default "28" = Science & Tech.
        privacy_status: "public" | "unlisted" | "private".

    Returns:
        Public YouTube URL, e.g. "https://www.youtube.com/shorts/xxxxxxx".

    Raises:
        FileNotFoundError: if mp4_path does not exist.
        googleapiclient.errors.HttpError: on API errors.
    """
    path = Path(mp4_path)
    if not path.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4_path}")

    # Ensure #Shorts is present for the algorithm
    if "#Shorts" not in title and "#shorts" not in title:
        title = title[:94] + " #Shorts" if len(title) > 94 else title + " #Shorts"

    youtube = _build_youtube_client()

    body: dict = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = googleapiclient.http.MediaFileUpload(
        str(path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=_CHUNK_SIZE,
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    logger.info("Starting YouTube upload: %s (%s bytes)", path.name, path.stat().st_size)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            logger.debug("YouTube upload progress: %d%%", pct)

    video_id: str = response["id"]
    url = f"https://www.youtube.com/shorts/{video_id}"
    logger.info("YouTube upload complete: %s", url)
    return url
