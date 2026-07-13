"""Small, deterministic prompt budgets for lower latency and token use."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable

_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def compact_text(value: Any, max_chars: int, *, keep_tail: int = 0) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
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
        "student_id",
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
        "homework_content": compact_text(homework_content, 12_000, keep_tail=1_500),
        "student_answers": compact_text(student_answers, 8_000, keep_tail=1_000),
        "profile": compact_profile(profile),
        "review_feedback": compact_text(review_feedback, 3_000, keep_tail=800),
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
