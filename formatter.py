"""User-facing JSON synthesis from structured claim results and source pool."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from models import ClaimCheckResult, ClaimVerdict, SourceArticle


def _article_to_link_dict(a: SourceArticle) -> Dict[str, Any]:
    return {
        "url": str(a.url),
        "title": a.title,
        "publisher": a.publisher,
        "credibility_score": round(float(a.credibility_score), 4),
    }


def _pick_refutation_source(
    result: ClaimCheckResult,
) -> Optional[SourceArticle]:
    """Prefer a 1.0-ranked contradicting source, else highest credibility among contradicting."""
    cons = list(result.contradicting_sources)
    if not cons:
        return None
    perfect = [s for s in cons if s.credibility_score >= 1.0 - 1e-9]
    pool = perfect if perfect else cons
    return max(pool, key=lambda s: (s.credibility_score, s.citation_count, int(s.has_structured_data)))


def _dedupe_best_score(articles: List[SourceArticle]) -> List[SourceArticle]:
    best: Dict[str, SourceArticle] = {}
    for a in articles:
        key = str(a.url)
        if key not in best:
            best[key] = a
            continue
        cur = best[key]
        if (a.credibility_score, a.citation_count, int(a.has_structured_data)) > (
            cur.credibility_score,
            cur.citation_count,
            int(cur.has_structured_data),
        ):
            best[key] = a
    return list(best.values())


def top_educational_sources(
    pool: List[SourceArticle],
    *,
    limit: int = 2,
) -> List[Dict[str, Any]]:
    """Return the most credible unique URLs for end-user reading."""
    uniq = _dedupe_best_score(pool)
    ranked = sorted(
        uniq,
        key=lambda s: (s.credibility_score, s.citation_count, int(s.has_structured_data)),
        reverse=True,
    )
    return [_article_to_link_dict(a) for a in ranked[:limit]]


def build_summary(claim_results: List[ClaimCheckResult]) -> str:
    total = len(claim_results)
    if total == 0:
        return "No claims were evaluated for this video."
    supported = sum(1 for r in claim_results if r.verdict == ClaimVerdict.SUPPORTED)
    contradicted = sum(1 for r in claim_results if r.verdict == ClaimVerdict.CONTRADICTED)
    mixed = sum(1 for r in claim_results if r.verdict == ClaimVerdict.MIXED)
    unverified = sum(1 for r in claim_results if r.verdict == ClaimVerdict.UNVERIFIED)
    factual_pct = round(100.0 * (supported + 0.5 * mixed) / total, 1)
    return (
        f"Evaluated {total} claims: ~{factual_pct}% align with retrieved reputable sources "
        f"({supported} supported, {contradicted} contradicted, {mixed} mixed, {unverified} unverified)."
    )


def format_final_report(
    claim_results: List[ClaimCheckResult],
    source_pool: List[SourceArticle],
) -> Dict[str, Any]:
    """
    User-friendly JSON:
    - summary: concise accuracy overview
    - flagged_claims: contradicted claims + best (prefer score 1.0) refutation link
    - top_educational_sources: two most credible unique links seen overall
    """
    flagged: List[Dict[str, Any]] = []
    for r in claim_results:
        if r.verdict != ClaimVerdict.CONTRADICTED:
            continue
        ref = _pick_refutation_source(r)
        entry: Dict[str, Any] = {
            "claim": r.claim.statement,
            "verdict": r.verdict.value,
        }
        if ref is not None:
            entry["refutation_source"] = _article_to_link_dict(ref)
        flagged.append(entry)

    return {
        "summary": build_summary(claim_results),
        "flagged_claims": flagged,
        "top_educational_sources": top_educational_sources(source_pool, limit=2),
    }


def format_final_report_json(
    claim_results: List[ClaimCheckResult],
    source_pool: List[SourceArticle],
) -> str:
    return json.dumps(format_final_report(claim_results, source_pool), ensure_ascii=False, indent=2)
