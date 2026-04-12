"""Load .env and expose API key environment variable names and accessors."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

# Environment variable names (set values in .env)
ENV_YOUTUBE_API_KEY = "YOUTUBE_API_KEY"
ENV_GOOGLE_API_KEY = "GOOGLE_API_KEY"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_SERPER_API_KEY = "SERPER_API_KEY"


def get_youtube_data_api_key() -> str:
    """Key for YouTube Data API v3. Uses YOUTUBE_API_KEY, else GOOGLE_API_KEY."""
    key = os.environ.get(ENV_YOUTUBE_API_KEY, "").strip()
    if key:
        return key
    return os.environ.get(ENV_GOOGLE_API_KEY, "").strip()


def get_openai_api_key() -> str:
    return os.environ.get(ENV_OPENAI_API_KEY, "").strip()


def get_serper_api_key() -> str:
    return os.environ.get(ENV_SERPER_API_KEY, "").strip()
