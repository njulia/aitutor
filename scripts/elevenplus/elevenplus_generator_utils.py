#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared helpers for deterministic, RAG-compatible 11+ generators.

The helpers preserve the public generator return contract:
    (student_facing_content, answer_records)

Answer records deliberately include both the historic keys (``q`` and
``correct_value``) and the canonical keys consumed by ``elevenplus_rag.py``
(``question``, ``options`` and ``answer``).
"""
from __future__ import annotations

import contextvars
import hashlib
import random as _stdlib_random
import re
from typing import Any, Iterable, List, Mapping, MutableSequence, Sequence

_DIFFICULTIES = {
    "foundation": "foundation",
    "foundational": "foundation",
    "foundational basics": "foundation",
    "easy": "foundation",
    "standard": "standard",
    "intermediate": "standard",
    "intermediate application": "standard",
    "advanced": "advanced",
    "advanced practice": "advanced",
    "selective": "selective",
    "selective / hard": "selective",
    "selective school challenge": "selective",
    "hard": "selective",
    "mastery": "mastery",
    "ultimate mastery & mixed drill": "mastery",
}
_DIFFICULTY_RANK = {
    "foundation": 1,
    "standard": 2,
    "advanced": 3,
    "selective": 4,
    "mastery": 5,
}
_TIME_TARGET_SECONDS = {
    "foundation": 75,
    "standard": 60,
    "advanced": 50,
    "selective": 45,
    "mastery": 40,
}


def normalise_difficulty(value: Any) -> str:
    text = str(value or "standard").strip().casefold()
    return _DIFFICULTIES.get(text, "standard")


def difficulty_rank(value: Any) -> int:
    return _DIFFICULTY_RANK[normalise_difficulty(value)]


def time_target_seconds(value: Any) -> int:
    return _TIME_TARGET_SECONDS[normalise_difficulty(value)]


def recommended_set_minutes(value: Any, question_count: int = 10) -> int:
    seconds = time_target_seconds(value) * max(1, int(question_count))
    return max(5, (seconds + 59) // 60)


def difficulty_for_week(week_num: int) -> str:
    """Progress from accuracy-first work to timed exam practice."""
    week = max(1, min(int(week_num), 52))
    if week <= 10:
        return "foundation"
    if week <= 24:
        return "standard"
    if week <= 37:
        return "advanced"
    if week <= 46:
        return "selective"
    return "mastery"




def difficulty_for_batch_position(position: int, total: int) -> str:
    """Balanced library mix: most sets are standard/advanced, with fewer extremes."""
    total_value = max(1, int(total))
    ratio = max(0.0, min(1.0, (int(position) - 0.5) / total_value))
    if ratio < 0.15:
        return "foundation"
    if ratio < 0.50:
        return "standard"
    if ratio < 0.80:
        return "advanced"
    if ratio < 0.95:
        return "selective"
    return "mastery"

def stable_seed(*parts: Any) -> int:
    raw = "|".join(str(part) for part in parts).encode("utf-8", "replace")
    return int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(), "big")


_rng_context: contextvars.ContextVar[_stdlib_random.Random | None] = contextvars.ContextVar(
    "elevenplus_rng", default=None
)
_difficulty_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "elevenplus_difficulty", default="standard"
)


class _SeededRandomProxy:
    """A context-local replacement for the module-level ``random`` object.

    The original generators use ``random.seed`` and module-level random calls.
    A context-local generator keeps deterministic output without sharing mutable
    global random state when worksheets are generated in parallel threads.
    """

    @staticmethod
    def _rng() -> _stdlib_random.Random:
        rng = _rng_context.get()
        if rng is None:
            rng = _stdlib_random.Random()
            _rng_context.set(rng)
        return rng

    def seed(self, value: Any = None) -> None:
        self._rng().seed(value)

    def random(self) -> float:
        return self._rng().random()

    def choice(self, seq: Sequence[Any]) -> Any:
        return self._rng().choice(seq)

    def choices(self, population: Sequence[Any], weights=None, *, cum_weights=None, k: int = 1):
        return self._rng().choices(population, weights=weights, cum_weights=cum_weights, k=k)

    def sample(self, population: Sequence[Any], k: int) -> List[Any]:
        return self._rng().sample(population, k)

    def shuffle(self, values: MutableSequence[Any]) -> None:
        self._rng().shuffle(values)

    def randint(self, a: int, b: int) -> int:
        # Large numeric ranges are gently tiered so mastery sets use more
        # demanding values while visual indexes and small counters stay stable.
        low, high = int(a), int(b)
        span = high - low
        if span >= 20:
            rank = difficulty_rank(_difficulty_context.get())
            if rank == 1:
                high = low + max(1, int(span * 0.45))
            elif rank == 2:
                high = low + max(1, int(span * 0.75))
            elif rank == 4:
                low = low + int(span * 0.25)
            elif rank == 5:
                low = low + int(span * 0.45)
        return self._rng().randint(low, high)

    def randrange(self, *args: int) -> int:
        return self._rng().randrange(*args)

    def uniform(self, a: float, b: float) -> float:
        return self._rng().uniform(a, b)


seeded_random = _SeededRandomProxy()


def begin_generation(subject: str, topic: str, index: int, difficulty: Any = "standard") -> str:
    normalised = normalise_difficulty(difficulty)
    _difficulty_context.set(normalised)
    seeded_random.seed(stable_seed(subject, topic, int(index), normalised))
    return normalised


def current_difficulty() -> str:
    return _difficulty_context.get()


def _key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def _fallback_distractors(correct: Any, existing: Sequence[Any], needed: int) -> List[str]:
    result: List[str] = []
    correct_text = str(correct).strip()
    used = {_key(correct), *(_key(item) for item in existing)}

    number_match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(%|[a-zA-Z²³/]+)?\s*", correct_text)
    if number_match:
        value = float(number_match.group(1))
        suffix = number_match.group(2) or ""
        steps = [1, -1, 2, -2, 5, -5, 10, -10]
        for step in steps:
            candidate_value = value + step
            if value.is_integer() and candidate_value.is_integer():
                rendered = str(int(candidate_value))
            else:
                rendered = f"{candidate_value:.2f}".rstrip("0").rstrip(".")
            candidate = f"{rendered}{suffix}"
            if _key(candidate) not in used:
                result.append(candidate)
                used.add(_key(candidate))
                if len(result) >= needed:
                    return result

    generic = [
        "None of these",
        "Cannot be determined",
        "All of the other options",
        "Not enough information",
    ]
    for candidate in generic:
        if _key(candidate) not in used:
            result.append(candidate)
            used.add(_key(candidate))
            if len(result) >= needed:
                break
    return result


def build_multiple_choice_question(
    num: int,
    text: str,
    correct: Any,
    distractors: Iterable[Any],
    explanation: str,
    tip: str = "",
    difficulty: Any | None = None,
    *,
    skill: str = "",
) -> tuple[str, dict[str, Any]]:
    """Build one five-option MCQ with a canonical, locally markable key."""
    difficulty_name = normalise_difficulty(difficulty or current_difficulty())
    correct_key = _key(correct)
    unique_distractors: List[Any] = []
    seen = {correct_key}
    for item in distractors:
        item_key = _key(item)
        if not item_key or item_key in seen:
            continue
        seen.add(item_key)
        unique_distractors.append(item)
        if len(unique_distractors) == 4:
            break

    if len(unique_distractors) < 4:
        unique_distractors.extend(
            _fallback_distractors(correct, unique_distractors, 4 - len(unique_distractors))
        )
    if len(unique_distractors) < 4:
        raise ValueError(f"Question {num} does not have four unique distractors")

    options: List[Any] = unique_distractors[:4] + [correct]
    seeded_random.shuffle(options)
    option_text = [str(option).strip() for option in options]
    correct_letter = chr(65 + next(i for i, option in enumerate(options) if _key(option) == correct_key))
    question_text = str(text).strip()
    numbered_question = f"{int(num)}. {question_text}"

    lines = [numbered_question]
    for index, option in enumerate(option_text):
        lines.append(f"   {chr(65 + index)}) {option}")

    answer = str(correct).strip()
    record = {
        # Historic generator schema.
        "q": int(num),
        "correct_letter": correct_letter,
        "correct_value": answer,
        # Canonical schema consumed by elevenplus_rag._normalise_answer_records.
        "question": numbered_question,
        "options": option_text,
        "answer": answer,
        # Tutor support.
        "explanation": str(explanation).strip(),
        "tip": str(tip or "").strip(),
        "difficulty": difficulty_name,
        "time_target_seconds": time_target_seconds(difficulty_name),
    }
    if skill:
        record["skill"] = str(skill).strip()
    return "\n".join(lines), record


def validate_answer_records(records: Sequence[Mapping[str, Any]], expected: int = 10) -> None:
    if len(records) != expected:
        raise ValueError(f"Expected {expected} answer records, got {len(records)}")
    for expected_number, record in enumerate(records, start=1):
        options = [str(item).strip() for item in record.get("options", [])]
        if len(options) != 5 or len({_key(item) for item in options}) != 5:
            raise ValueError(f"Question {expected_number} must have five unique options")
        letter = str(record.get("correct_letter", "")).strip().upper()
        if letter not in "ABCDE":
            raise ValueError(f"Question {expected_number} has invalid correct letter")
        answer = str(record.get("answer") or record.get("correct_value") or "").strip()
        if _key(options[ord(letter) - 65]) != _key(answer):
            raise ValueError(f"Question {expected_number} answer does not match its option")


def balanced_weighted_sequence(
    topic_weights: Sequence[tuple[str, int]], count: int, *, seed: Any = "11plus"
) -> List[str]:
    """Return a deterministic, near-exact weighted distribution.

    Unlike ``random.choices``, small batches cannot accidentally omit an entire
    skill area. The final list is shuffled to avoid long blocks of one topic.
    """
    total_count = max(0, int(count))
    if not topic_weights or total_count == 0:
        return []
    cleaned = [(str(topic), max(1, int(weight))) for topic, weight in topic_weights]
    total_weight = sum(weight for _, weight in cleaned)
    exact = [(topic, total_count * weight / total_weight) for topic, weight in cleaned]
    allocations = {topic: int(value) for topic, value in exact}
    remaining = total_count - sum(allocations.values())
    remainders = sorted(
        ((value - int(value), topic) for topic, value in exact), reverse=True
    )
    for _, topic in remainders[:remaining]:
        allocations[topic] += 1
    result = [topic for topic, _ in cleaned for _ in range(allocations[topic])]
    rng = _stdlib_random.Random(stable_seed(seed, total_count))
    rng.shuffle(result)
    return result


def strip_student_header(content: str) -> str:
    lines = str(content or "").splitlines()
    while lines and (
        not lines[0].strip()
        or lines[0].startswith("11+ ")
        or lines[0].startswith("Answer each question")
    ):
        lines.pop(0)
    return "\n".join(lines).strip()


def records_to_year_round_questions(records: Sequence[Mapping[str, Any]]) -> List[dict[str, Any]]:
    result: List[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        question = re.sub(
            r"^\s*\d+[.)]\s*", "", str(record.get("question") or "").strip()
        )
        result.append(
            {
                "id": index,
                "questionText": question,
                "options": [str(item) for item in record.get("options", [])],
                "correctLetter": str(record.get("correct_letter") or "").upper(),
                "correctValue": str(record.get("answer") or record.get("correct_value") or ""),
                "explanation": str(record.get("explanation") or ""),
                "tip": str(record.get("tip") or ""),
                "difficulty": normalise_difficulty(record.get("difficulty")),
                "timeTargetSeconds": int(
                    record.get("time_target_seconds")
                    or time_target_seconds(record.get("difficulty"))
                ),
            }
        )
    return result
