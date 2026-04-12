"""Transcript → atomic, checkable factual claims (prompt-shaped extraction)."""

from __future__ import annotations

import re
from typing import List, Set

# Simulated LLM system prompt (deterministic heuristics implement the same rules):
# """
# You are a fact-checking preprocessor. From a video transcript, output only CHECKABLE
# factual claims suitable for verification against docs and authoritative sources.
#
# DISCARD (skip entirely):
# - Procedural / live-coding narration: "Now, let's create a variable…", "First we define…",
#   "Next I'll add…", step-by-step typing instructions.
# - UI / product navigation: "Click on the button…", "Go to the menu…", "Select the tab…".
# - Personal opinion or taste: "I really like this approach…", "I prefer…", "I think this is nice…"
#   (unless restated as an objective technical fact).
# - Greetings, subscribe CTAs, questions, and pure hedging without a testable claim.
#
# CAPTURE (keep as claims):
# - Complexity / performance: "The time complexity of this is O(n log n).", "Space is O(n)."
# - Definitions: "Uvicorn is an ASGI server.", "A hash map provides O(1) average lookup."
# - System / library behavior: "FastAPI handles async requests natively.", "This runs on the event loop."
# - Other standalone, declarative technical facts that could be checked against documentation
#   or standard references (not instructions to the viewer).
#
# Output: JSON list of short, non-duplicate, declarative strings. No opinions, no questions.
# """

_OPINION_LEADERS = re.compile(
    r"^\s*(i think|i believe|i feel|maybe|probably|perhaps|imo|in my opinion)\b",
    re.I,
)
_SOFT_OPINION = re.compile(
    r"\b(i really like|i love this|i prefer (this|that)|personally i|in my view|"
    r"i don't like|i hate this)\b",
    re.I,
)
_QUESTION = re.compile(r"\?\s*$")
_SUBSCRIBE = re.compile(
    r"\b(like and subscribe|hit the bell|smash that|follow me|link in bio)\b",
    re.I,
)
_PROCEDURAL = re.compile(
    r"\b(now,? let'?s|let'?s (create|add|define|write|build|make|open|start)|"
    r"first,? (we|i)'?(ll)?|next,? (we|i)'?(ll)?|then,? (we|i)'?(ll)?|"
    r"i'?ll (just )?(type|write|add|create)|we'?(ll)? (just )?(type|write|add))\b",
    re.I,
)
_UI_NAV = re.compile(
    r"\b(click (on |the )?|right[- ]click|navigate to|go to the|open the|select the|"
    r"press the|hit the|choose the|from the (dropdown|menu)|in the sidebar)\b",
    re.I,
)
_CHECKABLE_TECH = re.compile(
    r"(time\s+complexity|space\s+complexity|\bO\s*\([^)]+\)|\bbig\s*o\b|"
    r"\b(is|are)\s+(a|an)\s+[\w.-]+\s+"
    r"(server|framework|library|tool|interpreter|compiler|runtime|structure|algorithm|protocol)\b|"
    r"\b(handles|implements|supports|provides|defines)\b.+\b("
    r"async|request|response|server|client|http|asgi|wsgi|native|thread|process)\b|"
    r"\b(worst case|average case|best case|amortized)\b|"
    r"\b(data structure|algorithm|solution)\s+(is|has|uses|requires|runs)\b)",
    re.I,
)
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_MIN_LEN = 16
_MAX_CLAIMS = 80


def extract_claims(transcript: str) -> List[str]:
    """
    Split transcript into checkable factual statements.

    Stand-in for an LLM with the prompt above: drop procedural/UI/opinion noise;
    keep lines that read like verifiable technical or general facts.
    """
    if not transcript or not transcript.strip():
        return []

    raw_chunks: List[str] = []
    for part in _SPLIT.split(transcript.strip()):
        chunk = part.strip()
        if not chunk:
            continue
        raw_chunks.append(chunk)

    seen: Set[str] = set()
    out: List[str] = []

    for chunk in raw_chunks:
        sentence = chunk.strip()
        if len(sentence) < _MIN_LEN:
            continue
        if _QUESTION.search(sentence):
            continue
        if _OPINION_LEADERS.search(sentence):
            continue
        if _SOFT_OPINION.search(sentence):
            continue
        if _SUBSCRIBE.search(sentence):
            continue
        if _PROCEDURAL.search(sentence):
            continue
        if _UI_NAV.search(sentence):
            continue
        lower = sentence.lower()
        if lower.startswith(("welcome back", "hey guys", "what's up", "thanks for watching")):
            continue

        if not _CHECKABLE_TECH.search(sentence):
            continue

        normalized = re.sub(r"\s+", " ", sentence)
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= _MAX_CLAIMS:
            break

    return out
