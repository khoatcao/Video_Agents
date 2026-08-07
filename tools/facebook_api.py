"""
Facebook / Meta Graph API integration for Reels upload and comment posting.

Token flow (fully automated — no token in .env):
  First run:  opens browser for Facebook login → saves permanent page token
              to facebook_token.json
  Every run after: loads token from facebook_token.json — never expires.

Only FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, and FACEBOOK_PAGE_ID are needed in .env.

Upload flow (two-step resumable upload required by Meta):
  1. POST /<page_id>/video_reels (upload_phase=start) → video_id + upload_url
  2. Binary POST to upload_url → video bytes
  3. POST /<page_id>/video_reels (upload_phase=finish) → publish
"""

from __future__ import annotations

import http.server
import json
import logging
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

from config.settings import (
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

_OAUTH_SCOPES = ["pages_show_list", "pages_read_management", "pages_manage_posts"]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TOKEN_FILE = _PROJECT_ROOT / "facebook_token.json"


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


# ── Token file ────────────────────────────────────────────────────────────────

def _save_token(page_token: str, page_id: str) -> None:
    _TOKEN_FILE.write_text(json.dumps({
        "page_access_token": page_token,
        "page_id": page_id,
    }))
    logger.info("[FacebookAPI] Token saved → %s", _TOKEN_FILE)


def _load_page_token() -> str:
    """
    Return a valid permanent page access token.

    Loads from facebook_token.json on every run.
    If the file does not exist, runs the full browser OAuth flow once.
    If the token is revoked (code 190), clears the file and re-runs OAuth.
    """
    if _TOKEN_FILE.is_file():
        data = json.loads(_TOKEN_FILE.read_text())
        token = data.get("page_access_token", "")
        if token:
            return token

    logger.info("[FacebookAPI] No token found — opening browser for Facebook login...")
    return _run_oauth_flow()


def _run_oauth_flow() -> str:
    """
    Full OAuth flow: browser login → permanent page token → saved to file.

    Starts a one-shot local HTTP server on port 8080 to capture the redirect code.
    """
    if not FACEBOOK_APP_ID or not FACEBOOK_APP_SECRET:
        raise FacebookAPIError(
            "FACEBOOK_APP_ID and FACEBOOK_APP_SECRET must be set in .env to run OAuth."
        )

    # ── 1. Start local callback server ───────────────────────────────────────
    captured: dict = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            captured["code"] = params.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"<h2>Facebook login successful! You can close this tab.</h2>"
            )

        def log_message(self, *args):
            pass  # suppress server access logs

    port = int(FACEBOOK_REDIRECT_URI.rsplit(":", 1)[-1].split("/")[0]) if ":" in FACEBOOK_REDIRECT_URI else 8080
    server = http.server.HTTPServer(("localhost", port), _Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    # ── 2. Open browser ───────────────────────────────────────────────────────
    oauth_url = (
        f"{_OAUTH_BASE}?"
        + urllib.parse.urlencode({
            "client_id": FACEBOOK_APP_ID,
            "redirect_uri": FACEBOOK_REDIRECT_URI,
            "scope": ",".join(_OAUTH_SCOPES),
            "response_type": "code",
        })
    )
    print(f"\n[FacebookAPI] Opening browser for login...\nIf it doesn't open, go to:\n{oauth_url}\n")
    webbrowser.open(oauth_url)

    # ── 3. Wait for redirect code ─────────────────────────────────────────────
    thread.join(timeout=120)
    code = captured.get("code")
    if not code:
        raise FacebookAPIError("OAuth timed out — no code received within 120 seconds.")

    # ── 4. Exchange code → short-lived token ──────────────────────────────────
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
    short_token: str = _check(resp)["access_token"]

    # ── 5. Exchange short-lived → long-lived (60 days) ────────────────────────
    resp = requests.get(
        f"{_GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FACEBOOK_APP_ID,
            "client_secret": FACEBOOK_APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=_API_TIMEOUT,
    )
    long_token: str = _check(resp)["access_token"]

    # ── 6. Get permanent page access token ────────────────────────────────────
    resp = requests.get(
        f"{_GRAPH_BASE}/me/accounts",
        params={"access_token": long_token},
        timeout=_API_TIMEOUT,
    )
    pages: list[dict] = _check(resp).get("data", [])

    page_token: str = ""
    page_id: str = FACEBOOK_PAGE_ID

    for page in pages:
        if page["id"] == FACEBOOK_PAGE_ID:
            page_token = page["access_token"]
            break

    if not page_token:
        if len(pages) == 1:
            page_token = pages[0]["access_token"]
            page_id = pages[0]["id"]
            logger.warning(
                "[FacebookAPI] FACEBOOK_PAGE_ID not matched — using only available page: %s", page_id
            )
        else:
            available = [f"{p['name']} ({p['id']})" for p in pages]
            raise FacebookAPIError(
                f"Page {FACEBOOK_PAGE_ID} not found. Available pages: {available}"
            )

    _save_token(page_token, page_id)
    return page_token


def _get_token() -> str:
    """Get the page token, re-running OAuth if it has been revoked."""
    try:
        return _load_page_token()
    except FacebookAPIError as exc:
        if exc.code == 190:
            logger.warning("[FacebookAPI] Token revoked (code 190) — clearing and re-authorising.")
            _TOKEN_FILE.unlink(missing_ok=True)
            return _run_oauth_flow()
        raise


# ── Upload helpers ────────────────────────────────────────────────────────────

def upload_facebook_reel(mp4_path: str, caption: str) -> str:
    """
    Upload an MP4 as a Facebook Reel on the configured Page and publish it.

    Args:
        mp4_path: Absolute path to the rendered MP4 file.
        caption:  Post caption (Vietnamese text + hashtags).

    Returns:
        The Facebook post ID of the published Reel.
    """
    path = Path(mp4_path)
    if not path.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4_path}")

    if not FACEBOOK_PAGE_ID:
        raise FacebookAPIError("FACEBOOK_PAGE_ID is not set in .env")

    token = _get_token()
    file_size = path.stat().st_size

    # Step 1: Initialise upload session
    init_resp = requests.post(
        f"{_GRAPH_BASE}/{FACEBOOK_PAGE_ID}/video_reels",
        params={"access_token": token},
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
            "Authorization": f"OAuth {token}",
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
        params={"access_token": token},
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
    """
    token = _get_token()
    resp = requests.post(
        f"{_GRAPH_BASE}/{post_id}/comments",
        params={"access_token": token},
        json={"message": comment},
        timeout=_API_TIMEOUT,
    )
    data = _check(resp)
    comment_id: str = data["id"]
    logger.info("Facebook comment posted. comment_id=%s", comment_id)
    return comment_id
