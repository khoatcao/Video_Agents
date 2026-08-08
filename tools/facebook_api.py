"""
Facebook / Meta Graph API integration for Reels upload and comment posting.

OAuth flow (run once to obtain a long-lived Page access token):
  1. Call get_oauth_url()          → open in browser, user authorises
  2. Call exchange_code_for_token(code) → short-lived user token
  3. Call get_long_lived_token(short_token) → 60-day user token
  4. Call get_page_access_token(long_token) → never-expiring Page token
  5. Store the Page token in FACEBOOK_ACCESS_TOKEN env var / .env

Required scopes (requested automatically in get_oauth_url):
  - pages_show_list
  - pages_read_management
  - pages_manage_posts

Upload flow (two-step resumable upload required by Meta):
  1. POST /<page_id>/video_reels (upload_phase=start) → video_id + upload_url
  2. Binary POST to upload_url → video bytes
  3. POST /<page_id>/video_reels (upload_phase=finish) → publish
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from pathlib import Path

import requests

from config.settings import (
    FACEBOOK_ACCESS_TOKEN,
    FACEBOOK_APP_ID,
    FACEBOOK_APP_SECRET,
    FACEBOOK_PAGE_ID,
    FACEBOOK_REDIRECT_URI,
)

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_OAUTH_BASE = "https://www.facebook.com/dialog/oauth"
_UPLOAD_TIMEOUT = 300
_API_TIMEOUT = 30

_PUBLISH_SCOPES = ["pages_read_management", "pages_manage_posts"]
_OAUTH_SCOPES = _PUBLISH_SCOPES + ["pages_show_list"]


class FacebookAPIError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def _check(response: requests.Response) -> dict:
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


# ── OAuth flow ────────────────────────────────────────────────────────────────

def get_oauth_url(state: str = "") -> str:
    params = {
        "client_id": FACEBOOK_APP_ID,
        "redirect_uri": FACEBOOK_REDIRECT_URI,
        "scope": ",".join(_OAUTH_SCOPES),
        "response_type": "code",
    }
    if state:
        params["state"] = state
    return f"{_OAUTH_BASE}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str) -> str:
    resp = requests.get(
        f"{_GRAPH_BASE}/oauth/access_token",
        params={
            "client_id": FACEBOOK_APP_ID,
            "client_secret": FACEBOOK_APP_SECRET,
            "redirect_uri": FACEBOOK_REDIRECT_URI,
            "code": code,
        },
        timeout=_API_TIMEOUT,
    )
    return _check(resp)["access_token"]


def get_long_lived_token(short_lived_token: str) -> str:
    resp = requests.get(
        f"{_GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FACEBOOK_APP_ID,
            "client_secret": FACEBOOK_APP_SECRET,
            "fb_exchange_token": short_lived_token,
        },
        timeout=_API_TIMEOUT,
    )
    return _check(resp)["access_token"]


def get_page_access_token(long_lived_user_token: str, page_id: str | None = None) -> str:
    target_page = page_id or FACEBOOK_PAGE_ID
    resp = requests.get(
        f"{_GRAPH_BASE}/me/accounts",
        params={"access_token": long_lived_user_token},
        timeout=_API_TIMEOUT,
    )
    data = _check(resp)
    for page in data.get("data", []):
        if page["id"] == target_page:
            return page["access_token"]
    raise FacebookAPIError(
        f"Page {target_page} not found in /me/accounts — "
        "make sure the user manages that page and pages_show_list is granted."
    )


# ── Upload helpers ────────────────────────────────────────────────────────────

def upload_facebook_reel(mp4_path: str, caption: str) -> str:
    path = Path(mp4_path)
    if not path.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4_path}")

    if not FACEBOOK_PAGE_ID:
        raise FacebookAPIError("FACEBOOK_PAGE_ID is not set in .env")
    if not FACEBOOK_ACCESS_TOKEN:
        raise FacebookAPIError("FACEBOOK_ACCESS_TOKEN is not set in .env")

    file_size = path.stat().st_size

    # Step 1: Initialise upload session
    init_resp = requests.post(
        f"{_GRAPH_BASE}/{FACEBOOK_PAGE_ID}/video_reels",
        params={"access_token": FACEBOOK_ACCESS_TOKEN},
        json={"upload_phase": "start", "file_size": file_size},
        timeout=_API_TIMEOUT,
    )
    init_data = _check(init_resp)
    video_id: str = init_data["video_id"]
    upload_url: str = init_data["upload_url"]
    logger.info("Facebook upload session started. video_id=%s", video_id)

    # Step 2: Upload raw video bytes
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
    logger.info("Facebook video bytes uploaded. video_id=%s", video_id)

    # Step 3: Publish the reel
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
    logger.info("Facebook Reel publish response: %s", publish_data)
    post_id: str = publish_data.get("post_id") or f"{FACEBOOK_PAGE_ID}_{video_id}"
    logger.info("Facebook Reel published. post_id=%s  video_id=%s", post_id, video_id)
    # Return both ids — comments must use video_id (post_id uses deprecated statuses API)
    return post_id, video_id


def post_facebook_comment(post_id: str, comment: str) -> str:
    url = f"{_GRAPH_BASE}/{post_id}/comments"
    logger.info("Posting comment to %s", url)
    resp = requests.post(
        url,
        params={"access_token": FACEBOOK_ACCESS_TOKEN},
        json={"message": comment},
        timeout=_API_TIMEOUT,
    )
    logger.debug("Comment response status=%d body=%s", resp.status_code, resp.text[:300])
    data = _check(resp)
    comment_id: str = data["id"]
    logger.info("Facebook comment posted. comment_id=%s", comment_id)
    return comment_id
