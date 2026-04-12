"""End-to-end fact check: claim store, retrieval, ranking, LLM verdict, formatted JSON."""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

from openai import AsyncOpenAI

from config import ENV_OPENAI_API_KEY, get_openai_api_key
from formatter import format_final_report
from models import Claim, ClaimCheckResult, ClaimVerdict, SourceArticle
from ranking_engine import SourceRanker
from search_service import OPENAI_MODEL_FAST, fetch_sources_detailed

# --- In-memory claim queue keyed by client-supplied video id -----------------

_VIDEO_CLAIMS: Dict[str, List[Claim]] = {}

# --- LRU cache for completed fact-check payloads (by video_id) ---------------

_FACT_CACHE_MAX = 500
_fact_cache: OrderedDict[str, dict] = OrderedDict()


def register_video_claims(video_id: str, claims: Sequence[Claim]) -> None:
    """Call after /analyze-video (or equivalent) so run_fact_check can resolve claims."""
    _VIDEO_CLAIMS[video_id] = list(claims)


def get_registered_claims(video_id: str) -> List[Claim]:
    return list(_VIDEO_CLAIMS.get(video_id, []))


def _cache_get_fact(video_id: str) -> Optional[dict]:
    if video_id not in _fact_cache:
        return None
    _fact_cache.move_to_end(video_id)
    return _fact_cache[video_id]


def _cache_put_fact(video_id: str, payload: dict) -> None:
    _fact_cache[video_id] = payload
    _fact_cache.move_to_end(video_id)
    while len(_fact_cache) > _FACT_CACHE_MAX:
        _fact_cache.popitem(last=False)


async def _reason_claim_verdict(
    claim: Claim,
    ranked: List[SourceArticle],
    snippets: Dict[str, str],
) -> Tuple[ClaimVerdict, Tuple[SourceArticle, ...], Tuple[SourceArticle, ...]]:
    """
    Second LLM pass: decide support vs contradiction using ranked sources + snippets.
    """
    openai_key = get_openai_api_key()
    if not openai_key:
        raise RuntimeError(f"{ENV_OPENAI_API_KEY} is not set")

    oai = AsyncOpenAI(api_key=openai_key)
    lines: List[str] = []
    for i, a in enumerate(ranked):
        snip = snippets.get(str(a.url), "")[:1200]
        lines.append(
            f"[{i}] score={a.credibility_score:.3f} publisher={a.publisher} title={a.title}\n"
            f"    url={a.url}\n    snippet={snip}"
        )
    bundle = "\n".join(lines)
    system = (
        "You are a careful fact checker. Given a claim and ranked sources, respond JSON only:\n"
        '{"verdict": "supported"|"contradicted"|"unverified"|"mixed", '
        '"supporting_indices": number[], "contradicting_indices": number[]}\n'
        "Use only indices provided. If evidence is weak or off-topic, use unverified. "
        "mixed when sources disagree materially."
    )
    user = f"Claim:\n{claim.statement}\n\nSources:\n{bundle}\n"
    completion = await oai.chat.completions.create(
        model=OPENAI_MODEL_FAST,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)
    verdict_raw = (data.get("verdict") or "unverified").strip().lower()
    try:
        verdict = ClaimVerdict(verdict_raw)
    except ValueError:
        verdict = ClaimVerdict.UNVERIFIED

    def _pick_indices(key: str) -> List[int]:
        out: List[int] = []
        for x in data.get(key) or []:
            try:
                idx = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(ranked):
                out.append(idx)
        return out

    sup_idx = _pick_indices("supporting_indices")
    con_idx = _pick_indices("contradicting_indices")
    supporting = tuple(ranked[i] for i in sup_idx)
    contradicting = tuple(ranked[i] for i in con_idx)
    return verdict, supporting, contradicting


async def run_fact_check(video_id: str, *, use_cache: bool = True) -> dict:
    """
    For each registered claim: Serper + mini assessments → SourceRanker → reasoning → JSON report.

    Returns formatter.format_final_report structure plus lightweight metadata.
    """
    if use_cache:
        hit = _cache_get_fact(video_id)
        if hit is not None:
            return dict(hit, from_cache=True)

    claims = get_registered_claims(video_id)
    if not claims:
        empty = format_final_report([], [])
        payload = {**empty, "video_id": video_id, "from_cache": False, "claims_evaluated": 0}
        if use_cache:
            _cache_put_fact(video_id, {k: v for k, v in payload.items() if k != "from_cache"})
        return payload

    ranker = SourceRanker()
    claim_results: List[ClaimCheckResult] = []
    global_pool: List[SourceArticle] = []

    for claim in claims:
        pairs = await fetch_sources_detailed(claim)
        articles = [a for a, _ in pairs]
        snippets = {str(a.url): snip for a, snip in pairs}
        ordered = ranker.rank_sources(articles)
        scored_all = ranker.with_scores(ordered)
        global_pool.extend(scored_all)
        top3 = scored_all[:3]

        verdict, supporting, contradicting = await _reason_claim_verdict(
            claim, top3, snippets
        )
        claim_results.append(
            ClaimCheckResult(
                claim=claim,
                verdict=verdict,
                supporting_sources=supporting,
                contradicting_sources=contradicting,
            )
        )

    report = format_final_report(claim_results, global_pool)
    payload = {
        **report,
        "video_id": video_id,
        "from_cache": False,
        "claims_evaluated": len(claim_results),
    }
    if use_cache:
        storable = {k: v for k, v in payload.items() if k != "from_cache"}
        _cache_put_fact(video_id, storable)
    return payload
