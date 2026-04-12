"""Core domain models for the video fact-checking pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator


class TopicType(str, Enum):
    """Primary topic lane for credibility rules."""

    POLITICS = "politics"
    NEWS = "news"
    STEM = "stem"
    SWE_TECH = "swe_tech"
    POP_CULTURE = "pop_culture"
    GENERAL = "general"


class ClaimVerdict(str, Enum):
    """Outcome of checking one claim against retrieved sources."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"
    MIXED = "mixed"


class VideoMetadata(BaseModel):
    model_config = {"frozen": True}

    url: HttpUrl
    title: str
    channel: str
    description: str = ""
    category: Union[TopicType, str]

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, v: Any) -> Union[TopicType, str]:
        if isinstance(v, TopicType):
            return v
        if isinstance(v, str):
            key = v.strip().lower().replace(" ", "_")
            try:
                return TopicType(key)
            except ValueError:
                return v
        return v


class Claim(BaseModel):
    model_config = {"frozen": True}

    statement: str
    source_video_id: str
    topic_tag: str
    timestamp: Optional[float] = Field(
        default=None,
        description="Seconds from start of video, if known.",
    )


class SourceArticle(BaseModel):
    model_config = {"frozen": True}

    url: HttpUrl
    publisher: str
    title: str
    topic_type: Union[TopicType, str]
    credibility_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Filled by SourceRanker; initial value ignored for ranking.",
    )
    citation_count: int = Field(default=0, ge=0)
    has_structured_data: bool = False

    @field_validator("topic_type", mode="before")
    @classmethod
    def _coerce_topic_type(cls, v: Any) -> Union[TopicType, str]:
        if isinstance(v, TopicType):
            return v
        if isinstance(v, str):
            key = v.strip().lower().replace(" ", "_")
            try:
                return TopicType(key)
            except ValueError:
                return v
        return v


class ClaimCheckResult(BaseModel):
    """Per-claim outcome attached to a fact-check report."""

    model_config = {"frozen": True}

    claim: Claim
    verdict: ClaimVerdict
    supporting_sources: Tuple[SourceArticle, ...] = ()
    contradicting_sources: Tuple[SourceArticle, ...] = ()


class FactCheckReport(BaseModel):
    model_config = {"frozen": True}

    overall_verdict: str
    claim_results: List[ClaimCheckResult] = Field(default_factory=list)
    top_credible_sources: List[SourceArticle] = Field(default_factory=list)
