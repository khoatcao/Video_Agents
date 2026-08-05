"""
YouTube Data API v3 uploader.

OAuth2 flow:
  - First run: opens browser for Google login, saves token to youtube_token.json
  - Subsequent runs: loads token from youtube_token.json, refreshes automatically

Only YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are needed in .env.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http

from config.settings import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET

logger = logging.getLogger(__name__)

_YOUTUBE_API_SERVICE = "youtube"
_YOUTUBE_API_VERSION = "v3"
_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOKEN_FILE = _PROJECT_ROOT / "youtube_token.json"


def _build_youtube_client() -> googleapiclient.discovery.Resource:
    """
    Build an authenticated YouTube client.

    Loads saved credentials from youtube_token.json if available.
    Otherwise runs the OAuth flow (opens browser once) and saves the token.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    # Load existing token
    if _TOKEN_FILE.is_file():
        data = json.loads(_TOKEN_FILE.read_text())
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=YOUTUBE_CLIENT_ID,
            client_secret=YOUTUBE_CLIENT_SECRET,
            scopes=_SCOPES,
        )

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)

    # First run — open browser for login
    if not creds or not creds.valid:
        logger.info("[YouTubeAPI] No valid token found — opening browser for Google login...")
        client_config = {
            "installed": {
                "client_id": YOUTUBE_CLIENT_ID,
                "client_secret": YOUTUBE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, scopes=_SCOPES)
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        _save_token(creds)
        logger.info("[YouTubeAPI] Token saved → %s", _TOKEN_FILE)

    return googleapiclient.discovery.build(
        _YOUTUBE_API_SERVICE,
        _YOUTUBE_API_VERSION,
        credentials=creds,
        cache_discovery=False,
    )


def _save_token(creds) -> None:
    _TOKEN_FILE.write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
    }))


def upload_youtube_short(
    mp4_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "28",
    privacy_status: str = "public",
) -> str:
    """
    Upload an MP4 as a YouTube Short and return its public URL.

    Args:
        mp4_path:       Absolute path to the MP4 file.
        title:          Video title (max 100 chars).
        description:    Video description.
        tags:           List of tag strings.
        category_id:    YouTube category ID. Default "28" = Science & Tech.
        privacy_status: "public" | "unlisted" | "private".

    Returns:
        Public YouTube URL e.g. "https://www.youtube.com/shorts/xxxxxxx".
    """
    path = Path(mp4_path)
    if not path.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4_path}")

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

    logger.info("[YouTubeAPI] Uploading %s (%s bytes)…", path.name, path.stat().st_size)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.debug("[YouTubeAPI] Upload progress: %d%%", int(status.progress() * 100))

    video_id: str = response["id"]
    url = f"https://www.youtube.com/shorts/{video_id}"
    logger.info("[YouTubeAPI] Upload complete → %s", url)
    return url
