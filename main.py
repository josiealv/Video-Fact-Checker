"""FastAPI entry point for the Chrome extension → fact-check preprocessing pipeline."""

from __future__ import annotations

import config  # noqa: F401 — loads .env before other imports use API keys

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from evaluator import run_initial_analysis
from models import Claim, TopicType
from youtube_fetch import YouTubeFetchError, fetch_youtube_for_analysis

app = FastAPI(title="Video Fact-Checker API", version="0.1.0")


class AnalyzeVideoRequest(BaseModel):
    """YouTube watch URL; metadata and transcript are fetched server-side."""

    video_url: HttpUrl

class AnalyzeVideoResponse(BaseModel):
    eligible_for_fact_check: bool
    skip_reason: Optional[str] = None
    topic_category: Optional[str] = None
    claims: List[Claim] = Field(default_factory=list)
    topic_type: Optional[str] = Field(
        default=None,
        description="Mapped TopicType value for downstream SourceRanker.",
    )
    video_url: str
    from_cache: bool = False


def _map_topic_to_topic_type(topic: str) -> TopicType:
    t = topic.strip().lower().replace(" ", "_")
    if t == "stem":
        return TopicType.STEM
    if t in ("swe_tech", "swetech"):
        return TopicType.SWE_TECH
    if t == "politics":
        return TopicType.POLITICS
    if t in ("pop culture", "pop_culture"):
        return TopicType.POP_CULTURE
    return TopicType.GENERAL


@app.post("/analyze-video", response_model=AnalyzeVideoResponse)
def analyze_video(body: AnalyzeVideoRequest) -> AnalyzeVideoResponse:
    """
    Fetch YouTube metadata (Data API) and transcript, then heuristic filtering,
    topic lane, atomic claims, URL LRU cache.
    """
    url_str = str(body.video_url)
    try:
        bundle = fetch_youtube_for_analysis(url_str)
    except YouTubeFetchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    analysis = run_initial_analysis(
        url_str,
        bundle.transcript_text,
        title=bundle.title,
        description=bundle.description,
        tags=bundle.tags,
    )

    topic_type: Optional[TopicType] = None
    if analysis.topic_category:
        topic_type = _map_topic_to_topic_type(analysis.topic_category)

    video_key = bundle.video_id or url_str
    claims_models: List[Claim] = []
    if analysis.eligible and analysis.topic_category:
        tag = analysis.topic_category
        for statement in analysis.claims:
            claims_models.append(
                Claim(
                    statement=statement,
                    source_video_id=video_key,
                    topic_tag=tag,
                    timestamp=None,
                )
            )

    return AnalyzeVideoResponse(
        eligible_for_fact_check=analysis.eligible,
        skip_reason=analysis.skip_reason,
        topic_category=analysis.topic_category,
        claims=claims_models,
        topic_type=topic_type.value if topic_type else None,
        video_url=url_str,
        from_cache=analysis.from_cache,
    )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}
