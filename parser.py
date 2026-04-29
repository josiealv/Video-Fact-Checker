"""Transcript → atomic, checkable factual claims (prompt-shaped extraction)."""

from __future__ import annotations

import json
import re
from typing import List, Set

# Load config patterns
EVAL_CONFIG = json.load(open("evaluation_config.json"))

# Opinion/procedural filters
_OPINION_LEADERS = re.compile(r"^\s*(i think|i believe|i feel|maybe|probably|perhaps|imo|in my opinion)\b", re.I)
_SOFT_OPINION = re.compile(r"\b(i really like|i love this|i prefer (this|that)|personally i|in my view|i don't like|i hate this)\b", re.I)
_QUESTION = re.compile(r"\?\s*$")
_SUBSCRIBE = re.compile(r"\b(like and subscribe|hit the bell|smash that|follow me|link in bio)\b", re.I)
_PROCEDURAL = re.compile(r"\b(now,? let'?s|let'?s (create|add|define|write|build|make|open|start)|first,? (we|i)'?(ll)?|next,? (we|i)'?(ll)?|then,? (we|i)'?(ll)?|i'?ll (just )?(type|write|add|create)|we'?(ll)? (just )?(type|write|add))\b", re.I)
_UI_NAV = re.compile(r"\b(click (on |the )?|right[- ]click|navigate to|go to the|open the|select the|press the|hit the|choose the|from the (dropdown|menu)|in the sidebar)\b", re.I)

# Checkable patterns from tech + config
_CHECKABLE_TECH = [
    re.compile(r"(time\s+complexity|space\s+complexity|\bO\s*\([^)]+\)|\bbig\s*o\b|\b(is|are)\s+(a|an)\s+[\w.-]+\s+(server|framework|library|tool|interpreter|compiler|runtime|structure|algorithm|protocol)\b|\b(handles|implements|supports|provides|defines)\b.+\b(async|request|response|server|client|http|asgi|wsgi|native|thread|process)\b|\b(worst case|average case|best case|amortized)\b|\b(data structure|algorithm|solution)\s+(is|has|uses|requires|runs)\b)", re.I),
]

_CHECKABLE_PATTERNS = _CHECKABLE_TECH
_CHECKABLE_PATTERNS += [re.compile(p, re.I) for p in EVAL_CONFIG["patterns"]["politics"] + EVAL_CONFIG["patterns"]["stem"] + EVAL_CONFIG["patterns"]["pop"]]
_CHECKABLE_PATTERNS.append(re.compile(r"\b(president|gas|index|increase|negotiation|delegation|commitment|stockpile|threat|congress|senate|policy|ballot)\b", re.I))

_SPLIT = re.compile(r"(?<=[.!?])\s+|(?:\n\s*){2,}")
_MIN_LEN = 10  # lowered
_MAX_CLAIMS = 100  # increased


def _reconstruct_sentences(transcript: str) -> List[str]:
    """Reconstruct sentences from poorly punctuated transcripts."""
    # Replace single newlines with spaces
    text = re.sub(r'\n', ' ', transcript)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Split into chunks of reasonable length (30-150 words)
    words = text.split()
    sentences = []
    current = []
    
    for word in words:
        current.append(word)
        # Create sentence breaks at 30-80 words
        if len(current) >= 30:
            sentence = ' '.join(current)
            sentences.append(sentence)
            current = []
    
    if current:
        sentences.append(' '.join(current))
    
    return sentences


def extract_claims(transcript: str) -> List[str]:
    if not transcript.strip():
        return []
    
    raw_chunks = _reconstruct_sentences(transcript)
    
    seen = set()
    claims = []
    
    for chunk in raw_chunks:
        sentence = chunk.strip()
        if len(sentence) < _MIN_LEN:
            continue
        if _QUESTION.search(sentence):
            continue
        if _OPINION_LEADERS.search(sentence) or _SOFT_OPINION.search(sentence):
            continue
        if _SUBSCRIBE.search(sentence):
            continue
        if _PROCEDURAL.search(sentence) or _UI_NAV.search(sentence):
            continue
        lower = sentence.lower()
        if lower.startswith(("welcome back", "hey guys", "what's up", "thanks for watching")):
            continue
        if not any(pattern.search(sentence) for pattern in _CHECKABLE_PATTERNS):
            continue
        
        normalized = re.sub(r"\s+", " ", sentence.strip())
        key = normalized.lower()
        if key not in seen:
            seen.add(key)
            claims.append(normalized)
        if len(claims) >= _MAX_CLAIMS:
            break
    
    return claims