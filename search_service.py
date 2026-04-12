"""Serper search + GPT-4o-mini reasoning to build SourceArticle rows for a claim."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI

from config import ENV_OPENAI_API_KEY, ENV_SERPER_API_KEY, get_openai_api_key, get_serper_api_key
from models import Claim, SourceArticle, TopicType

SERPER_URL = "https://google.serper.dev/search"
OPENAI_MODEL_FAST = "gpt-4o-mini"


def _topic_type_from_claim(claim: Claim) -> TopicType:
    tag = claim.topic_tag.strip().lower().replace(" ", "_")
    if tag == "stem":
        return TopicType.STEM
    if tag in ("swe_tech", "swetech"):
        return TopicType.SWE_TECH
    if tag == "politics":
        return TopicType.POLITICS
    if tag in ("pop culture", "pop_culture"):
        return TopicType.POP_CULTURE
    return TopicType.GENERAL


def _host_publisher(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host.replace("www.", "")
    except Exception:
        return ""


async def _serper_search(client: httpx.AsyncClient, query: str, api_key: str) -> List[Dict[str, Any]]:
    resp = await client.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": 5},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    organic = data.get("organic") or []
    return organic[:5]


async def _mini_assess_source(
    oai: AsyncOpenAI,
    *,
    topic_lane: str,
    claim_text: str,
    result_title: str,
    result_url: str,
    snippet: str,
) -> Dict[str, Any]:
    system = (
        "You evaluate whether a web result is a credible source for fact-checking a specific claim. "
        "Reply with compact JSON only, no markdown. Schema:\n"
        '{"accredited_for_topic": bool, "contains_raw_data_or_stats": bool, '
        '"estimated_external_citations": int, "publisher_name": string}\n'
        "- accredited_for_topic: is this publisher/outlet appropriately accredited for THIS topic lane?\n"
        "- contains_raw_data_or_stats: does the snippet suggest tables, numbers, charts, or primary data?\n"
        "- estimated_external_citations: 0-5 guess of how often serious outlets cite this domain.\n"
        "- publisher_name: short label (e.g. site or news org)."
    )
    user = (
        f"Topic lane: {topic_lane}\n"
        f"Claim: {claim_text}\n"
        f"Result title: {result_title}\n"
        f"URL: {result_url}\n"
        f"Snippet: {snippet}\n"
    )
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
    return json.loads(raw)


async def fetch_sources_detailed(claim: Claim) -> List[Tuple[SourceArticle, str]]:
    """
    Serper top-5 + per-result GPT-4o-mini assessment. Returns (article, snippet) pairs.
    """
    serper_key = get_serper_api_key()
    openai_key = get_openai_api_key()
    if not serper_key:
        raise RuntimeError(f"{ENV_SERPER_API_KEY} is not set")
    if not openai_key:
        raise RuntimeError(f"{ENV_OPENAI_API_KEY} is not set")

    topic = _topic_type_from_claim(claim)
    topic_lane = topic.value.replace("_", " ")

    async with httpx.AsyncClient() as http:
        organic = await _serper_search(http, claim.statement, serper_key)

    oai = AsyncOpenAI(api_key=openai_key)
    out: List[Tuple[SourceArticle, str]] = []

    for row in organic:
        title = (row.get("title") or "").strip()
        link = (row.get("link") or "").strip()
        snippet = (row.get("snippet") or "").strip()
        if not link:
            continue
        assessed = await _mini_assess_source(
            oai,
            topic_lane=topic_lane,
            claim_text=claim.statement,
            result_title=title,
            result_url=link,
            snippet=snippet,
        )
        publisher = (assessed.get("publisher_name") or "").strip() or _host_publisher(link)
        citations = assessed.get("estimated_external_citations")
        try:
            citation_count = max(0, min(5, int(citations)))
        except (TypeError, ValueError):
            citation_count = 0
        has_data = bool(assessed.get("contains_raw_data_or_stats"))
        # If the model flags non-accredited, keep row but ranker will score down via publisher heuristics.
        article = SourceArticle(
            url=link,  # type: ignore[arg-type]
            publisher=publisher,
            title=title or publisher or link,
            topic_type=topic,
            credibility_score=0.0,
            citation_count=citation_count,
            has_structured_data=has_data,
        )
        out.append((article, snippet))

    return out


async def fetch_sources(claim: Claim) -> List[SourceArticle]:
    """Search Google (Serper), assess top 5 with GPT-4o-mini, map to SourceArticle."""
    pairs = await fetch_sources_detailed(claim)
    return [a for a, _ in pairs]
