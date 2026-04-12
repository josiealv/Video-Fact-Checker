"""Video eligibility heuristics, topic categorization, and URL-bounded LRU cache."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from parser import extract_claims

# --- Stage 1: exclusion heuristics (title + tags only, case-insensitive) -----------------------

_BLOCK_PHRASES: Tuple[str, ...] = (
    "music video", "official music video", "lyric video", "soundfont", 
    "ost", "soundtrack", "instrumental", "visualizer", "remix",
    "satire", "asmr", "parody", "meme", "memetic", "humor", "joke", "jokes",
)

# --- Stage 2: simulated LLM topic tagging (keyword scoring on transcript + light context) -------

_STEM_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(study|studies|research|hypothesis|experiment|peer[- ]reviewed|dataset)\b", re.I),
    re.compile(r"\b(gene|dna|rna|protein|molecule|clinical trial|p value|statistic)\b", re.I),
    re.compile(r"\b(physics|chemistry|biology|mathematics|engineering|arxiv|doi:)\b", re.I),
    re.compile(r"\b(laboratory|university|institute of)\b", re.I),
)

_POLITICS_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(election|electorate|congress|senate|parliament|white house)\b", re.I),
    re.compile(r"\b(president|prime minister|legislation|ballot|polling|campaign)\b", re.I),
    re.compile(r"\b(policy|sanction|treaty|nato|united nations|geopolitic)\b", re.I),
    re.compile(r"\b(republican|democrat|gop|liberal|conservative)\b", re.I),
)

_POP_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(celebrity|gossip|red carpet|box office|billboard|chart)\b", re.I),
    re.compile(r"\b(album|single|tour|concert|festival|streaming)\b", re.I),
    re.compile(r"\b(movie|film|tv show|series|netflix|premiere)\b", re.I),
    re.compile(r"\b(fashion|magazine|influencer|viral)\b", re.I),
)

# --- SWE / technical tutorial gate (transcript + tags only, before category scoring) ------------

_SWE_TECH_TERMS: Tuple[str, ...] = (
    "pip",
    "install",
    "server",
    "api",
    "java",
    "kotlin",
    "c++",
    "c#",
    "c",
    "golang",
    "rust",
    "scala",
    "haskell",
    "ocaml",
    "prolog",
    "linux",
    "windows",
    "macos",
    "docker",
    "kubernetes",
    "helm",
    "terraform",
    "ansible",
    "puppet",
    "async",
    "python",
    "javascript",
    "typescript",
    "react",
    "node",
    "express",
    "next",
    "nest",
    "nestjs",
    "framework",
    "uvicorn",
    "fastapi",
    "localhost",
    "endpoint",
    "aws",
    "database",
    "apache",
    "azure",
    "cloudflare",
)

_SWE_TECH_TERM_COUNT_FORCE = 3

# --- Computer science / algorithms (LeetCode-style): any hit forces SWE_TECH over Pop Culture ---

_CS_ALGO_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\bleetcode\b", re.I),
    re.compile(r"\bhash\s*map\b|\bhashmap\b", re.I),
    re.compile(r"\bpointer(s)?\b", re.I),
    re.compile(r"time\s+complexity", re.I),
    re.compile(r"space\s+complexity", re.I),
    re.compile(r"\bbig\s*o\b", re.I),
    re.compile(r"\bruntime\b", re.I),
    re.compile(r"\biteration\b", re.I),
    re.compile(r"\brecursion\b", re.I),
    re.compile(r"\bsorting\b", re.I),
    re.compile(r"binary\s+search", re.I),
    re.compile(r"\barray\b", re.I),
)

_TUTORIAL_MARKERS = re.compile(
    r"\b(how\s+to|tutorial|walkthrough)\b",
    re.I,
)
_CODE_NEAR_TUTORIAL = re.compile(
    r"\b(code|coding|function|def\b|variable|class\b|method|loop|leetcode|algorithm|"
    r"implement|syntax|runtime|compile|debug|refactor|repository|repo\b|git\b|"
    r"array|hash\s*map|pointer|complexity|recursion|iteration)\b",
    re.I,
)


def _has_cs_algo_signal(transcript: str, tags: Sequence[str]) -> bool:
    blob = f"{' '.join(tags)}\n{transcript}"
    return any(p.search(blob) for p in _CS_ALGO_PATTERNS)


def _has_tutorial_plus_code_signal(transcript: str, tags: Sequence[str]) -> bool:
    """'how to' / 'tutorial' / 'walkthrough' plus code-related vocabulary → SWE_TECH."""
    blob = f"{' '.join(tags)}\n{transcript}"
    return bool(_TUTORIAL_MARKERS.search(blob) and _CODE_NEAR_TUTORIAL.search(blob))


def _count_swe_tech_term_hits(transcript: str, tags: Sequence[str]) -> int:
    """How many distinct SWE terms from _SWE_TECH_TERMS appear in transcript or tags (word-boundary)."""
    blob = f"{' '.join(tags)}\n{transcript}".lower()
    hits = 0
    for term in _SWE_TECH_TERMS:
        if re.search(rf"\b{re.escape(term.lower())}\b", blob):
            hits += 1
    return hits


def _score_patterns(text: str, patterns: Iterable[re.Pattern[str]]) -> int:
    return sum(1 for p in patterns if p.search(text))


@dataclass(frozen=True)
class InitialAnalysisResult:
    """Outcome of initial filtering, categorization, and claim extraction."""

    eligible: bool
    skip_reason: Optional[str]
    topic_category: Optional[str]
    claims: Tuple[str, ...]
    from_cache: bool = False


class _UrlLRUCache:
    """In-memory LRU keyed by normalized video URL (max 1000 entries)."""

    __slots__ = ("_max", "_data")

    def __init__(self, maxsize: int = 1000) -> None:
        self._max = maxsize
        self._data: OrderedDict[str, InitialAnalysisResult] = OrderedDict()

    def get(self, url: str) -> Optional[InitialAnalysisResult]:
        if url not in self._data:
            return None
        self._data.move_to_end(url)
        return self._data[url]

    def set(self, url: str, value: InitialAnalysisResult) -> None:
        self._data[url] = value
        self._data.move_to_end(url)
        while len(self._data) > self._max:
            self._data.popitem(last=False)


_CACHE = _UrlLRUCache(maxsize=1000)


def _normalize_video_url(url: str) -> str:
    return url.strip().rstrip("/")


def stage_one_heuristic_reject(title: str, tags: Sequence[str]) -> Optional[str]:
    """
    Return a human-readable skip reason if the video should not be fact-checked,
    or None if it passes Stage 1.
    """
    blob = f"{title}\n{' '.join(tags)}".lower()
    for phrase in _BLOCK_PHRASES:
        if phrase in blob:
            return f"Heuristic exclusion: title/tags contain {phrase!r}"
    return None


def get_video_category(
    transcript: str,
    *,
    title: str = "",
    description: str = "",
    tags: Optional[Sequence[str]] = None,
) -> str:
    """
    Simulated topic tag (mirrors a short structured LLM prompt).

    1) **CS / algorithms:** If any ``_CS_ALGO_PATTERNS`` match (e.g. LeetCode,
       complexity, binary search), return ``SWE_TECH`` — beats Pop Culture even
       when the tone is casual or conversational.

    2) **Tutorial + code:** If ``how to``, ``tutorial``, or ``walkthrough``
       appears together with code-related terms, return ``SWE_TECH``.

    3) **SWE density:** If transcript or tags contain at least
       ``_SWE_TECH_TERM_COUNT_FORCE`` distinct terms from ``_SWE_TECH_TERMS``,
       return ``SWE_TECH``.

    4) **Otherwise:** Score **STEM** vs **Politics** vs **Pop Culture** using
       weighted keyword patterns. **STEM** here means *general STEM* —
       academic research, labs, papers, clinical science — not software how-tos
       (those are ``SWE_TECH`` when the gate fires). **SWE_TECH** means
       software engineering, platforms, APIs, and hands-on technical tutorials
       grounded in official docs and repos.

    5) If there are no claims being made based on the transcript, 
        the video is not eligible for fact-checking. Return "No claims".

    Context for scoring uses title, description, tags, and transcript; SWE
    overrides (1–3) use transcript + tags only.
    """
    tags = tags or ()
    if _has_cs_algo_signal(transcript, tags):
        return "SWE_TECH"
    if _has_tutorial_plus_code_signal(transcript, tags):
        return "SWE_TECH"
    if _count_swe_tech_term_hits(transcript, tags) >= _SWE_TECH_TERM_COUNT_FORCE:
        return "SWE_TECH"

    context = f"{title}\n{description}\n{' '.join(tags)}\n{transcript}"
    stem = _score_patterns(context, _STEM_PATTERNS)
    pol = _score_patterns(context, _POLITICS_PATTERNS)
    pop = _score_patterns(context, _POP_PATTERNS)
    scores: Dict[str, int] = {
        "STEM": stem * 2 + _score_patterns(transcript, _STEM_PATTERNS),
        "Politics": pol * 2 + _score_patterns(transcript, _POLITICS_PATTERNS),
        "Pop Culture": pop * 2 + _score_patterns(transcript, _POP_PATTERNS),
    }

    # Safety valve for low-signal videos
    if len(transcript.split()) < 50 :
         return "INELIGIBLE_LOW_INFORMATION_DENSITY"

    # Calculate scores...
    best_category = max(scores, key=scores.get)
    
    # If the highest score is still 0, it's not a factual video we can categorize
    if scores[best_category] == 0:
        return "INELIGIBLE_UNCERTAIN"
    return best_category


def run_initial_analysis(
    video_url: str,
    transcript_text: str,
    *,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
) -> InitialAnalysisResult:
    """
    Full pipeline: LRU lookup → Stage 1 → category → claim extraction → cache store.

    Cached entries are keyed by URL only (last 1000 distinct URLs).
    """
    key = _normalize_video_url(video_url)
    cached = _CACHE.get(key)
    if cached is not None:
        return replace(cached, from_cache=True)

    tags = tags or []
    reason = stage_one_heuristic_reject(title, tags)
    if reason is not None:
        result = InitialAnalysisResult(
            eligible=False,
            skip_reason=reason,
            topic_category=None,
            claims=(),
            from_cache=False,
        )
        _CACHE.set(key, result)
        return result

    topic = get_video_category(
        transcript_text,
        title=title,
        description=description,
        tags=tags,
    )
    claims = tuple(extract_claims(transcript_text))
    result = InitialAnalysisResult(
        eligible=True,
        skip_reason=None,
        topic_category=topic,
        claims=claims,
        from_cache=False,
    )
    _CACHE.set(key, result)
    return result
