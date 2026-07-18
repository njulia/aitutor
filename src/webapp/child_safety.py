"""Conservative safeguarding checks for learner-provided text.

This is not a diagnostic system. It only catches explicit first-person danger
statements so the tutor can pause normal feedback and direct the child to a
trusted adult. The input text is never logged by this module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SafeguardingConcern:
    category: str
    message: str


_COMMON_MESSAGE = (
    "Your safety matters more than homework. Please stop and tell a trusted adult now — "
    "a parent, carer, teacher or another grown-up you trust. If you or someone else is in "
    "immediate danger, call 999. You can also call Childline free on 0800 1111. "
    "I will pause the homework help here."
)

# Require explicit first-person language. This avoids reacting to ordinary
# curriculum questions about fictional characters, news, history or health.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "self_harm",
        re.compile(
            r"\b(?:i\s+(?:want|plan|intend|am going|(?:am|'m) trying)\s+to\s+"
            r"(?:die|kill myself|hurt myself|end my life)|"
            r"i\s+(?:have\s+)?(?:cut|hurt)\s+myself|"
            r"i\s+do not want to live|i\s+don't want to live)\b",
            re.I,
        ),
    ),
    (
        "abuse_or_immediate_danger",
        re.compile(
            r"\b(?:i\s+(?:am|'m)\s+not safe|"
            r"i\s+(?:am|'m)\s+being\s+(?:hurt|hit|touched|abused|threatened)|"
            r"someone\s+(?:is|keeps?|has been)\s+(?:hurting|hitting|touching|abusing|threatening)\s+me|"
            r"an?\s+adult\s+(?:is|keeps?|has been)\s+(?:hurting|hitting|touching|abusing|threatening)\s+me)\b",
            re.I,
        ),
    ),
    (
        "threat_to_others",
        re.compile(
            r"\bi\s+(?:want|plan|intend|am going|(?:am|'m) trying)\s+to\s+"
            r"(?:kill|stab|shoot|hurt|seriously hurt)\s+(?:someone|him|her|them|a person)\b",
            re.I,
        ),
    ),
)


def detect_safeguarding_concern(text: object) -> Optional[SafeguardingConcern]:
    """Return a concern only for a clear, explicit first-person disclosure."""
    candidate = str(text or "")[:12_000]
    for category, pattern in _PATTERNS:
        if pattern.search(candidate):
            return SafeguardingConcern(category=category, message=_COMMON_MESSAGE)
    return None


def safety_result(field: str, text: object) -> Optional[dict]:
    """Build an API-compatible response for a review/explanation/practice field."""
    concern = detect_safeguarding_concern(text)
    if concern is None:
        return None
    return {
        "success": True,
        field: concern.message,
        "safety_intervention": True,
        "safety_category": concern.category,
        "from_rag_answers": False,
        "model_tier": "none",
        "model_used": None,
    }
