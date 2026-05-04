"""Topic-aware source credibility scoring and deterministic ordering."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from models import SourceArticle, TopicType

# --- Publisher / URL signals (normalized matching) ---------------------------------------------

_ACCREDITED_NEWS = frozenset(
    {
        "associated press",
        "ap news",
        "reuters",
        "the new york times",
        "new york times",
        "nytimes",
        "the washington post",
        "washington post",
        "bbc",
        "npr",
        "pbs",
        "the wall street journal",
        "wall street journal",
        "financial times",
        "the guardian",
        "politico",
        "bloomberg",
    }
)

_ACADEMIC_PUBLISHER_FRAGMENTS = frozenset(
    {
        "university",
        "institute of technology",
        "national laboratory",
        "national lab",
        "research laboratory",
        "college",
        "school of medicine",
        "school of engineering",
        "mit ",
        " mit",
        "caltech",
        "stanford",
        "nih",
        "cdc",
        "nasa",
        "noaa",
        "who",
        "nature",
        "science ",
        "science.",
        "cell press",
        "springer",
        "ieee",
        "arxiv",
        "pubmed",
    }
)

_ACADEMIC_HOST_SUFFIXES = (".edu", ".gov", ".ac.uk", ".ac.jp")

_INDUSTRY_MAGAZINES = frozenset(
    {
        "rolling stone",
        "vogue",
        "variety",
        "the hollywood reporter",
        "hollywood reporter",
        "billboard",
        "pitchfork",
        "entertainment weekly",
        "tmz",
    }
)

_EYEWITNESS_HINTS = frozenset(
    {
        "eyewitness",
        "witness says",
        "i was there",
        "reddit",
        "tweet",
        "twitter thread",
        "tiktok",
        "instagram story",
    }
)

_VERIFIED_SOCIAL_HINTS = frozenset(
    {
        "verified",
        "official account",
        "blue check",
        "✓",
    }
)

# --- Low credibility hosts (Q&A sites, personal blogs) ----------------------------------------

_LOW_CREDIBILITY_HOSTS = frozenset(
    {
        "quora.com",
        "answers.yahoo.com",
        "ask.com",
        "answers.com",
        "blogspot.com",
        "wordpress.com",
    }
)

_VERIFIED_MEDIUM_PUBLICATIONS = frozenset(
    {
        "towardsdatascience.com",
        "betterprogramming.pub",
        "javascript.plainenglish.io",
        "levelup.gitconnected.com",
    }
)

# --- SWE / software-engineering source tiers (TopicType.SWE_TECH) -----------------------------

_SWE_OFFICIAL_DOC_HOSTS = frozenset(
    {
        "fastapi.tiangolo.com",
        "python.org",
        "docs.python.org",
        "www.python.org",
        "pypi.org",
        "docs.aws.amazon.com",
        "kubernetes.io",
        "go.dev",
        "golang.org",
        "rust-lang.org",
        "doc.rust-lang.org",
        "nodejs.org",
        "react.dev",
        "angular.io",
        "learn.microsoft.com",
        "nginx.org",
        "apache.org",
        "postgresql.org",
        "www.postgresql.org",
        "mysql.com",
        "dev.mysql.com",
        "sqlite.org",
        "redis.io",
        "mongodb.com",
        "www.mongodb.com",
        "docker.com",
        "docs.docker.com",
    }
)

_SWE_GITHUB_OFFICIAL_ORGS = frozenset(
    {
        "python",
        "django",
        "pallets",
        "pydantic",
        "tiangolo",
        "sqlalchemy",
        "encode",
        "google",
        "microsoft",
        "dotnet",
        "mozilla",
        "golang",
        "kubernetes",
        "rust-lang",
        "nodejs",
        "npm",
        "facebook",
        "vercel",
        "tailwindlabs",
        "openai",
        "apache",
        "openssl",
        "tensorflow",
        "pytorch",
        "huggingface",
        "redis",
        "mongodb",
        "docker",
    }
)

def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


@lru_cache(maxsize=4096)
def _host_key(url_str: str) -> str:
    # HttpUrl string is absolute; cheap parse without importing urllib if possible
    from urllib.parse import urlparse

    host = urlparse(url_str).hostname or ""
    return host.lower()


def _publisher_blob(article: SourceArticle) -> str:
    return _norm_text(article.publisher)


def _title_blob(article: SourceArticle) -> str:
    return _norm_text(article.title)


def _resolved_topic(article: SourceArticle) -> TopicType:
    t = article.topic_type
    if isinstance(t, TopicType):
        return t
    key = str(t).strip().lower().replace(" ", "_")
    try:
        return TopicType(key)
    except ValueError:
        return TopicType.GENERAL


def _is_accredited_news_publisher(publisher: str) -> bool:
    p = _norm_text(publisher)
    return any(org in p or p in org for org in _ACCREDITED_NEWS)


def _is_industry_magazine_publisher(publisher: str) -> bool:
    p = _norm_text(publisher)
    return any(m in p for m in _INDUSTRY_MAGAZINES)


def _is_low_credibility_host(article: SourceArticle) -> bool:
    """Check if source is from a low-credibility Q&A or personal blog site."""
    host = _host_key(str(article.url))
    url_str = str(article.url)
    
    # Check direct blocklist
    if any(blocked in host for blocked in _LOW_CREDIBILITY_HOSTS):
        # Exception: Medium verified publications
        if "medium.com" in host:
            return not any(pub in url_str for pub in _VERIFIED_MEDIUM_PUBLICATIONS)
        return True
    return False


def _is_academic_publisher_or_host(article: SourceArticle) -> bool:
    pub = _publisher_blob(article)
    if any(frag in pub for frag in _ACADEMIC_PUBLISHER_FRAGMENTS):
        return True
    host = _host_key(str(article.url))
    return any(host.endswith(sfx) for sfx in _ACADEMIC_HOST_SUFFIXES)


def _looks_eyewitness(article: SourceArticle) -> bool:
    blob = _publisher_blob(article) + " " + _title_blob(article)
    return any(h in blob for h in _EYEWITNESS_HINTS)


def _looks_verified_social(article: SourceArticle) -> bool:
    blob = _publisher_blob(article) + " " + _title_blob(article)
    if any(h in blob for h in _VERIFIED_SOCIAL_HINTS):
        return True
    host = _host_key(str(article.url))
    return host in {"x.com", "twitter.com", "instagram.com", "tiktok.com"}


def _swe_host(url_str: str) -> str:
    return _host_key(url_str)


def _swe_github_org(url_str: str) -> Optional[str]:
    p = urlparse(url_str)
    h = (p.hostname or "").lower().replace("www.", "")
    if h != "github.com":
        return None
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return None
    return parts[0].lower()


def _swe_is_official_documentation(url_str: str) -> bool:
    host = _swe_host(url_str)
    if host in _SWE_OFFICIAL_DOC_HOSTS:
        return True
    if "docs." in host:
        return True
    # Broad .org for vendor/project docs; exclude Wikipedia (ranked under interview/DS tier).
    if host.endswith(".org") and "wikipedia.org" not in host:
        return True
    return False


def _swe_is_verified_github_org(url_str: str) -> bool:
    org = _swe_github_org(url_str)
    return org is not None and org in _SWE_GITHUB_OFFICIAL_ORGS


def _swe_is_authoritative_tech_blog(url_str: str) -> bool:
    host = _swe_host(url_str)
    path = urlparse(url_str).path.lower()
    if host.endswith("realpython.com"):
        return True
    if host == "developer.mozilla.org" or host.endswith(".developer.mozilla.org"):
        return True
    if host == "web.dev" or host.endswith(".web.dev"):
        return True
    if host.endswith("blog.cloudflare.com") or host == "blog.cloudflare.com":
        return True
    if "aws.amazon.com" in host and "/blogs/" in path:
        return True
    if host.endswith("cloud.google.com") and "/blog" in path:
        return True
    if host == "blog.google" or host.endswith(".blog.google"):
        return True
    return False


def _swe_is_stackoverflow_family(url_str: str) -> bool:
    host = _swe_host(url_str)
    return host == "stackoverflow.com" or host.endswith(".stackoverflow.com")


def _swe_is_interview_algo_site(url_str: str) -> bool:
    """Competitive programming, interview prep, and canonical DS/algo references."""
    host = _swe_host(url_str)
    if "leetcode.com" in host or host.endswith(".leetcode.com"):
        return True
    if host.endswith("geeksforgeeks.org") or host.endswith(".geeksforgeeks.org"):
        return True
    if host == "neetcode.io" or host.endswith(".neetcode.io"):
        return True
    if "wikipedia.org" in host:
        return True
    if host.endswith("hackerrank.com"):
        return True
    if host.endswith("codeforces.com"):
        return True
    if host.endswith("atcoder.jp"):
        return True
    return False


def _score_swe_tech(article: SourceArticle) -> float:
    """
    Tiered credibility for software / API / tutorial fact-checking.

    Tie-breaks when scores tie: ``sort_key`` uses ``citation_count`` (proxy for
    cross-linkage) then ``has_structured_data`` (per ``SourceRanker.sort_key``).
    """
    if _is_low_credibility_host(article):
        return 0.05
    url_str = str(article.url)
    if _swe_is_official_documentation(url_str):
        return 1.0
    if _swe_is_verified_github_org(url_str):
        return 0.9
    if _swe_is_interview_algo_site(url_str):
        return 0.8
    if _swe_is_authoritative_tech_blog(url_str):
        return 0.7
    if _swe_is_stackoverflow_family(url_str):
        return 0.5
    return 0.1


class SourceRanker:
    """
    Computes a 0.0–1.0 credibility score per topic lane and orders sources with
    explicit tie-breakers: higher citation_count, then has_structured_data.
    """

    __slots__ = ()

    def score(self, article: SourceArticle) -> float:
        topic = _resolved_topic(article)
        if topic in (TopicType.POLITICS, TopicType.NEWS):
            return self._score_politics_news(article)
        if topic is TopicType.STEM:
            return self._score_stem(article)
        if topic is TopicType.SWE_TECH:
            return _score_swe_tech(article)
        if topic is TopicType.POP_CULTURE:
            return self._score_pop_culture(article)
        return self._score_general(article)

    @staticmethod
    def _score_politics_news(article: SourceArticle) -> float:
        if _is_low_credibility_host(article):
            return 0.05
        if _is_accredited_news_publisher(article.publisher):
            return 1.0
        if _looks_eyewitness(article):
            return 0.5
        return 0.35

    @staticmethod
    def _score_stem(article: SourceArticle) -> float:
        # Apply the strict ladder: institution > corroboration > structured data.
        if _is_low_credibility_host(article):
            return 0.05
        if _is_academic_publisher_or_host(article):
            return 1.0
        if article.citation_count >= 2:
            return 0.8
        if article.has_structured_data:
            return 0.6
        return 0.35

    @staticmethod
    def _score_pop_culture(article: SourceArticle) -> float:
        if _is_low_credibility_host(article):
            return 0.05
        if _is_industry_magazine_publisher(article.publisher):
            return 1.0
        if _looks_verified_social(article):
            return 0.5
        return 0.35

    @staticmethod
    def _score_general(article: SourceArticle) -> float:
        if _is_low_credibility_host(article):
            return 0.05
        if article.citation_count >= 3:
            return 1.0
        if article.citation_count <= 1:
            return 0.1
        return 0.55

    def sort_key(self, article: SourceArticle) -> Tuple[float, int, int, str]:
        """
        Descending-quality key as tuple for sorted(..., reverse=True).

        Primary: score (higher better). When scores tie (e.g. two official docs
        at 1.0 for ``SWE_TECH``), higher ``citation_count`` wins as a proxy for
        cross-linkage, then ``has_structured_data``, then URL for stability.
        """
        s = self.score(article)
        return (s, article.citation_count, int(article.has_structured_data), str(article.url))

    def rank_sources(
        self,
        sources: Iterable[SourceArticle],
        *,
        top_n: Optional[int] = None,
    ) -> List[SourceArticle]:
        """Return sources sorted by score, then citation_count, then structured data."""
        ranked = sorted(sources, key=self.sort_key, reverse=True)
        if top_n is not None:
            ranked = ranked[:top_n]
        return ranked

    def with_scores(self, sources: Iterable[SourceArticle]) -> List[SourceArticle]:
        """Copies each article with credibility_score set to the computed value."""
        out: List[SourceArticle] = []
        for a in sources:
            out.append(a.model_copy(update={"credibility_score": self.score(a)}))
        return out

    @staticmethod
    def compare(a: SourceArticle, b: SourceArticle, score_a: float, score_b: float) -> int:
        """
        Three-way comparison for tie-breaks when scores are already known and equal.
        Returns >0 if a wins, <0 if b wins, 0 if still tied.
        """
        if score_a != score_b:
            return (score_a > score_b) - (score_a < score_b)
        if a.citation_count != b.citation_count:
            return a.citation_count - b.citation_count
        return int(a.has_structured_data) - int(b.has_structured_data)


def rank_by_credibility(
    sources: Iterable[SourceArticle],
    *,
    top_n: Optional[int] = None,
) -> List[SourceArticle]:
    """Functional helper using the default SourceRanker."""
    return SourceRanker().rank_sources(sources, top_n=top_n)
