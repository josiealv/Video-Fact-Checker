"""Video fact-checker core: models and credibility ranking."""

from models import (
    Claim,
    ClaimCheckResult,
    ClaimVerdict,
    FactCheckReport,
    SourceArticle,
    TopicType,
    VideoMetadata,
)
from ranking_engine import SourceRanker, rank_by_credibility

__all__ = [
    "Claim",
    "ClaimCheckResult",
    "ClaimVerdict",
    "FactCheckReport",
    "SourceArticle",
    "SourceRanker",
    "TopicType",
    "VideoMetadata",
    "rank_by_credibility",
]
