"""Small, deterministic prompt budgets for lower latency and token use."""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, Iterable



def _bounded_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


REVIEW_HOMEWORK_MAX_CHARS = _bounded_env("REVIEW_HOMEWORK_MAX_CHARS", 8_000, 1_000, 20_000)
REVIEW_ANSWERS_MAX_CHARS = _bounded_env("REVIEW_ANSWERS_MAX_CHARS", 4_000, 500, 12_000)
REVIEW_FEEDBACK_MAX_CHARS = _bounded_env("REVIEW_FEEDBACK_MAX_CHARS", 2_000, 250, 6_000)

_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.I)
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.I)
_LABELLED_PHONE = re.compile(
    r"(?i)(\b(?:my\s+)?(?:phone|mobile|telephone|contact)\s*(?:number)?\s*(?:is|:)?\s*)"
    r"(?:\+?44\s?\d{4}|0\d{3,4})[\s-]?\d{3,4}[\s-]?\d{3,4}"
)
_NAME_DISCLOSURE = re.compile(
    r"(?i)\b(my\s+(?:full\s+)?name\s+is|i\s+am\s+called)\s+[A-Z][A-Za-z'’.-]+"
    r"(?:\s+[A-Z][A-Za-z'’.-]+){0,3}"
)
_SCHOOL_DISCLOSURE = re.compile(
    r"(?i)\b(i\s+(?:go\s+to|attend)|my\s+school\s+is)\s+[^\n,.!?]{2,80}"
)


def minimise_personal_data(value: Any) -> str:
    """Remove clear identifiers that are not needed for tutoring.

    Phone-like digit strings are removed only when labelled as contact details,
    so ordinary arithmetic answers and large numbers remain intact.
    """
    text = str(value or "")
    text = _EMAIL.sub("[email removed]", text)
    text = _POSTCODE.sub("[postcode removed]", text)
    text = _URL.sub("[link removed]", text)
    text = _LABELLED_PHONE.sub(r"\1[phone removed]", text)
    text = _NAME_DISCLOSURE.sub(r"\1 [name removed]", text)
    text = _SCHOOL_DISCLOSURE.sub(r"\1 [school removed]", text)
    return text


def compact_text(value: Any, max_chars: int, *, keep_tail: int = 0) -> str:
    text = minimise_personal_data(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(_WHITESPACE.sub(" ", line).strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text).strip()
    if len(text) <= max_chars:
        return text
    if keep_tail > 0 and keep_tail < max_chars - 40:
        head = max_chars - keep_tail - 32
        return f"{text[:head]}\n…[trimmed]…\n{text[-keep_tail:]}"
    return f"{text[: max_chars - 14]}…[trimmed]"


def compact_profile(profile: Dict[str, Any] | None) -> Dict[str, Any]:
    source = profile or {}
    allowed = (
        "year_group",
        "age",
        "key_stage",
        "english_level",
        "learning_needs",
        "learning_goals",
        "weak_areas",
        "plan_week",
        "plan_phase",
        "preferred_session_minutes",
    )
    result: Dict[str, Any] = {}
    for key in allowed:
        if key in source and source[key] not in (None, ""):
            value = source[key]
            if isinstance(value, str):
                result[key] = compact_text(value, 240)
            elif isinstance(value, list):
                result[key] = [compact_text(item, 120) for item in value[:6] if item not in (None, "")]
            else:
                result[key] = value
    return result


def budget_review_inputs(
    homework_content: str,
    student_answers: str,
    profile: Dict[str, Any] | None,
    review_feedback: str = "",
) -> Dict[str, Any]:
    return {
        "homework_content": compact_text(homework_content, REVIEW_HOMEWORK_MAX_CHARS, keep_tail=1_000),
        "student_answers": compact_text(student_answers, REVIEW_ANSWERS_MAX_CHARS, keep_tail=600),
        "profile": compact_profile(profile),
        "review_feedback": compact_text(review_feedback, REVIEW_FEEDBACK_MAX_CHARS, keep_tail=400),
    }


def stable_cache_key(namespace: str, *parts: Any) -> str:
    """Hash complete compacted inputs instead of collision-prone 200-char prefixes."""
    serialised = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.blake2b(serialised.encode("utf-8"), digest_size=20).hexdigest()
    return f"{namespace}:{digest}"


def select_relevant_items(items: Iterable[Dict[str, Any]], max_items: int = 20) -> list[Dict[str, Any]]:
    """Keep incorrect/unanswered items first before sending context to an LLM."""
    materialised = list(items)
    priority = [item for item in materialised if not item.get("is_correct", False)]
    correct = [item for item in materialised if item.get("is_correct", False)]
    return (priority + correct)[: max(1, min(max_items, 50))]
