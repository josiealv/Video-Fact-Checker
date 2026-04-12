"""Resolve a YouTube URL to metadata (YouTube Data API v3) and transcript text.

Transcripts come from the PyPI ``youtube-transcript-api`` package (undocumented
Innertube captions endpoint), not from the official YouTube Data API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from config import get_youtube_data_api_key

YOUTUBE_VIDEOS_API = "https://www.googleapis.com/youtube/v3/videos"
_YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


class YouTubeFetchError(Exception):
    """User-facing error for unsupported URLs, missing keys, or upstream failures."""


@dataclass(frozen=True)
class YouTubeVideoBundle:
    video_id: str
    title: str
    description: str
    tags: List[str]
    channel: str
    transcript_text: str


def extract_youtube_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "youtu.be":
        part = parsed.path.strip("/").split("/")[0]
        if part and _YOUTUBE_ID_RE.match(part):
            return part
        return None
    if host.endswith("youtube.com") or host == "youtube-nocookie.com":
        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            vid = qs["v"][0]
            if _YOUTUBE_ID_RE.match(vid):
                return vid
        segments = [s for s in parsed.path.split("/") if s]
        for prefix in ("shorts", "embed", "live", "v"):
            if len(segments) >= 2 and segments[0] == prefix:
                vid = segments[1].split("?")[0]
                if _YOUTUBE_ID_RE.match(vid):
                    return vid
        return None
    return None


def _fetch_snippet(video_id: str, api_key: str) -> Dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            YOUTUBE_VIDEOS_API,
            params={"part": "snippet", "id": video_id, "key": api_key},
        )
    if resp.status_code == 403:
        raise YouTubeFetchError("YouTube API denied the request (check quota or API key).") from None
    if resp.status_code >= 400:
        raise YouTubeFetchError(f"YouTube API error ({resp.status_code}).") from None
    data = resp.json()
    items = data.get("items") or []
    if not items:
        raise YouTubeFetchError("Video not found or not accessible with this key.")
    return items[0].get("snippet") or {}


def _fetch_transcript_text(video_id: str) -> str:
    from youtube_transcript_api import (
        IpBlocked,
        NoTranscriptFound,
        RequestBlocked,
        TranscriptsDisabled,
        VideoUnavailable,
        YouTubeTranscriptApi,
        YouTubeTranscriptApiException,
    )

    ytt = YouTubeTranscriptApi()
    try:
        fetched = ytt.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except TranscriptsDisabled:
        raise YouTubeFetchError("Captions/transcripts are disabled for this video.") from None
    except NoTranscriptFound:
        raise YouTubeFetchError("No usable transcript found for this video (try a video with captions).") from None
    except VideoUnavailable:
        raise YouTubeFetchError("Video unavailable for transcript fetch.") from None
    except (RequestBlocked, IpBlocked):
        raise YouTubeFetchError(
            "YouTube blocked the transcript request (common on cloud IPs; try another network or proxies)."
        ) from None
    except YouTubeTranscriptApiException as e:
        raise YouTubeFetchError(f"Could not load transcript: {e}") from e
    except Exception as e:
        raise YouTubeFetchError(f"Could not load transcript: {e}") from e

    parts: List[str] = []
    for snippet in fetched:
        t = snippet.text.strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def fetch_youtube_for_analysis(video_url: str) -> YouTubeVideoBundle:
    api_key = get_youtube_data_api_key()
    if not api_key:
        raise YouTubeFetchError(
            "YouTube Data API key is not set. Define YOUTUBE_API_KEY or GOOGLE_API_KEY in .env."
        )

    video_id = extract_youtube_video_id(video_url)
    if not video_id:
        raise YouTubeFetchError("Not a recognized YouTube URL.")

    snippet = _fetch_snippet(video_id, api_key)
    title = (snippet.get("title") or "").strip()
    description = (snippet.get("description") or "").strip()
    channel = (snippet.get("channelTitle") or "").strip()
    tags_raw = snippet.get("tags")
    tags: List[str] = [str(t).strip() for t in tags_raw] if isinstance(tags_raw, list) else []


    transcript_text = _fetch_transcript_text(video_id)
    if not transcript_text:
        raise YouTubeFetchError("Transcript was empty.")

    return YouTubeVideoBundle(
        video_id=video_id,
        title=title,
        description=description,
        tags=tags,
        channel=channel,
        transcript_text=transcript_text,
    )
