"""FastAPI entry point for the Chrome extension → fact-check preprocessing pipeline."""

from __future__ import annotations

import config  # noqa: F401 — loads .env before other imports use API keys

from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from parser import extract_claims
from evaluator import run_initial_analysis, categorize_claim, InitialAnalysisResult
from models import Claim, TopicType
from youtube_fetch import YouTubeFetchError, fetch_youtube_for_analysis, YouTubeVideoBundle
from orchestrator import run_fact_check, register_video_claims

app = FastAPI(title="Video Fact-Checker API", version="0.1.0")


class FactCheckRequest(BaseModel):
    """YouTube watch URL for fact-checking."""
    video_url: HttpUrl


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


def _fetch_and_analyze_video(video_url: str) -> Tuple[YouTubeVideoBundle, InitialAnalysisResult]:
    """Fetch YouTube video and run initial analysis. Raises HTTPException on error."""
    try:
        bundle = fetch_youtube_for_analysis(video_url)
    except YouTubeFetchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    analysis = run_initial_analysis(
        video_url,
        bundle.transcript_text,
        title=bundle.title,
        description=bundle.description,
        tags=bundle.tags,
    )
    return bundle, analysis


def _build_claim_models(
    analysis: InitialAnalysisResult,
    video_key: str,
) -> List[Claim]:
    """Build Claim models with individual categorization for each claim."""
    if not (analysis.eligible and analysis.topic_category):
        return []

    video_category = analysis.topic_category
    claims_models: List[Claim] = []

    for statement in analysis.claims:
        # Categorize each claim individually for more accurate topic tagging
        claim_category = categorize_claim(statement)
        # If claim categorization fails, fall back to video category
        if claim_category.startswith("INELIGIBLE"):
            claim_category = video_category

        claims_models.append(
            Claim(
                statement=statement,
                source_video_id=video_key,
                topic_tag=claim_category,
                timestamp=None,
            )
        )

    return claims_models


@app.post("/analyze-video", response_model=AnalyzeVideoResponse)
def analyze_video(body: AnalyzeVideoRequest) -> AnalyzeVideoResponse:
    """
    Fetch YouTube metadata (Data API) and transcript, then heuristic filtering,
    topic lane, atomic claims, URL LRU cache.
    """
    url_str = str(body.video_url)
    bundle, analysis = _fetch_and_analyze_video(url_str)

    topic_type: Optional[TopicType] = None
    if analysis.topic_category:
        topic_type = _map_topic_to_topic_type(analysis.topic_category)

    video_key = bundle.video_id or url_str
    claims_models = _build_claim_models(analysis, video_key)

    return AnalyzeVideoResponse(
        eligible_for_fact_check=analysis.eligible,
        skip_reason=analysis.skip_reason,
        topic_category=analysis.topic_category,
        claims=claims_models,
        topic_type=topic_type.value if topic_type else None,
        video_url=url_str,
        from_cache=analysis.from_cache,
    )

@app.post("/fact-check")
async def start_fact_check(body: FactCheckRequest):
    """
    Run full fact-check pipeline: analyze video → extract claims → search sources → rank → verify.
    Accepts video URL, performs analysis if needed, registers claims, then runs orchestrator.
    """
    url_str = str(body.video_url)
    bundle, analysis = _fetch_and_analyze_video(url_str)

    # Check eligibility
    if not analysis.eligible:
        raise HTTPException(
            status_code=400,
            detail=f"Video not eligible for fact-checking: {analysis.skip_reason}"
        )

    if not analysis.topic_category:
        raise HTTPException(
            status_code=400,
            detail="Video could not be categorized"
        )

    # Build and register claims
    video_key = bundle.video_id or url_str
    claims_models = _build_claim_models(analysis, video_key)
    register_video_claims(video_key, claims_models)

    # Run fact-check orchestrator
    try:
        report = await run_fact_check(video_key)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fact check failed: {str(e)}")

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}