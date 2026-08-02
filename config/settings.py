"""
Centralised settings module.

All environment variables are loaded once at import time.  Every other
module imports from here instead of calling os.getenv() directly, which
makes it easy to swap values in tests and ensures missing required vars
fail loudly at startup rather than mid-run.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _require(name: str) -> str:
    """Return env var value or raise at startup if it is absent."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            f"Copy .env.example to .env and fill in the value."
        )
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = _optional("OLLAMA_BASE_URL", "http://localhost:11434")

# ── Model aliases ─────────────────────────────────────────────────────────────
# All agents use qwen2.5:7b — single lightweight model, low VRAM (~5 GB),
# sufficient for Vietnamese content, code generation, and product matching
# at this video-generation workload.
MODEL_REASONING: str = "qwen2.5:7b"
MODEL_CODE: str = "qwen2.5:7b"
MODEL_FAST: str = "qwen2.5:7b"
MODEL_AFFILIATE: str = "qwen2.5:7b"

# ── YouTube OAuth2 (optional — leave blank to skip upload) ───────────────────
YOUTUBE_CLIENT_ID: str = _optional("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET: str = _optional("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN: str = _optional("YOUTUBE_REFRESH_TOKEN")

# ── Facebook / Meta Graph API (optional — leave blank to skip upload) ─────────
FACEBOOK_ACCESS_TOKEN: str = _optional("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_PAGE_ID: str = _optional("FACEBOOK_PAGE_ID")

# ── Affiliate networks ────────────────────────────────────────────────────────
SHOPEE_AFFILIATE_ID: str = _optional("SHOPEE_AFFILIATE_ID")
LAZADA_AFFILIATE_KEY: str = _optional("LAZADA_AFFILIATE_KEY")
TIKI_AFFILIATE_KEY: str = _optional("TIKI_AFFILIATE_KEY")
# ACCESSTRADE_API_KEY will be added later

# ── Pipeline I/O ──────────────────────────────────────────────────────────────
OUTPUT_DIR: Path = Path(_optional("OUTPUT_DIR", "./outputs")).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = _optional("LOG_LEVEL", "INFO").upper()

# ── Scheduling ────────────────────────────────────────────────────────────────
TIMEZONE: str = _optional("TIMEZONE", "Asia/Ho_Chi_Minh")
