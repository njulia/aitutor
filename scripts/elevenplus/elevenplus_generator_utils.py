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
import json
import random as _stdlib_random
import re
from typing import Any, Callable, Iterable, List, Mapping, MutableSequence, Sequence


# Every question is generated locally from original templates and algorithms.
# The scripts do not scrape, download, or depend on paid/proprietary question
# banks.  The curriculum reference is public and released under the Open
# Government Licence:
# https://www.gov.uk/government/collections/national-curriculum
PUBLIC_FREE_RESOURCE_POLICY = "original-content-and-public-free-guidance-only"

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


def _question_text(record: Mapping[str, Any]) -> str:
    value = record.get("question") or record.get("questionText") or ""
    return re.sub(r"^\s*\d+[.)]\s*", "", str(value).strip(), count=1)


def _option_text(option: Any) -> str:
    if isinstance(option, Mapping):
        return str(option.get("text") or option.get("value") or "").strip()
    return str(option).strip()


def question_fingerprint(record: Mapping[str, Any]) -> str:
    """Return a stable identity for one complete MCQ.

    Option order and question numbering are ignored.  A repeated generic stem
    with genuinely different choices remains a different question, while the
    same question with shuffled A-E labels is still recognised as a duplicate.
    """
    stem = _key(_question_text(record))
    options = sorted(
        _key(_option_text(option))
        for option in record.get("options", [])
        if _option_text(option)
    )
    raw = "\x1f".join([stem, *options]).encode("utf-8", "replace")
    return hashlib.blake2b(raw, digest_size=16).hexdigest()


def semantic_question_fingerprint(record: Mapping[str, Any]) -> str:
    """Identify the problem being asked, independently of its distractors.

    Regenerating only the wrong answer choices must not turn a repeated problem
    into a new question.  The complete, possibly multi-line prompt and its
    correct answer therefore define the semantic identity used for within-set
    duplicate checks.
    """
    stem = _key(_question_text(record))
    answer = _key(record.get("answer") or record.get("correct_value") or "")
    raw = "\x1f".join([stem, answer]).encode("utf-8", "replace")
    return hashlib.blake2b(raw, digest_size=16).hexdigest()


def homework_set_fingerprint(
    records: Sequence[Mapping[str, Any]],
    *,
    order_sensitive: bool = False,
) -> str:
    """Identify a complete set while still allowing questions to be reused.

    The default is intentionally order-insensitive: merely shuffling the same
    ten questions does not count as a new homework set.
    """
    fingerprints = [question_fingerprint(record) for record in records]
    if not order_sensitive:
        fingerprints.sort()
    raw = "\x1e".join(fingerprints).encode("ascii")
    return hashlib.blake2b(raw, digest_size=20).hexdigest()


def generate_unique_question_set(
    generator: Callable[[int], tuple[str, Sequence[Mapping[str, Any]]]],
    *,
    subject: str,
    topic: str,
    set_index: int,
    difficulty: Any = "standard",
    variant: int = 0,
    expected: int = 10,
    max_attempts: int = 50,
) -> tuple[str, str, List[dict[str, Any]]]:
    """Generate a worksheet whose ten complete questions are all different.

    Random collisions are handled by regenerating the whole set from a
    deterministic alternate seed.  This keeps the public generator API and
    answer-record schema unchanged and makes rebuilds repeatable.
    """
    public_index = int(set_index)
    attempts = max(1, int(max_attempts))
    for attempt in range(attempts):
        if variant == 0 and attempt == 0:
            seed_index = public_index
        else:
            seed_index = 1 + stable_seed(
                subject,
                topic,
                public_index,
                normalise_difficulty(difficulty),
                "set-variant",
                int(variant),
                attempt,
            ) % 2_000_000_000

        difficulty_name = begin_generation(subject, topic, seed_index, difficulty)
        body, raw_records = generator(seed_index)
        records = [dict(record) for record in raw_records]
        if len(records) != expected:
            continue
        semantic_fingerprints = [
            semantic_question_fingerprint(record) for record in records
        ]
        if len(semantic_fingerprints) == len(set(semantic_fingerprints)):
            return difficulty_name, str(body), records

    raise ValueError(
        f"Could not generate {expected} unique questions for "
        f"{subject} / {topic} set {public_index} after {attempts} attempts"
    )


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

    semantic_fingerprints = [
        semantic_question_fingerprint(record) for record in records
    ]
    if len(semantic_fingerprints) != len(set(semantic_fingerprints)):
        raise ValueError("Homework set contains duplicate questions")


def _rendered_question_first_lines(content: Any) -> List[str]:
    matches = list(re.finditer(r"(?m)^\d+\.\s+", str(content or "")))
    blocks = [
        str(content)[
            match.end() :
            matches[index + 1].start() if index + 1 < len(matches) else None
        ].strip()
        for index, match in enumerate(matches)
    ]
    return [
        _key(block.splitlines()[0] if block.splitlines() else "")
        for block in blocks
    ]


def validate_homework_batch(homework_items: Sequence[Mapping[str, Any]]) -> None:
    """Validate uniqueness before a batch can be written to the 11+ RAG.

    Individual questions may appear in multiple sets.  Only duplicates inside
    one set and completely identical ten-question sets are rejected.
    """
    seen_sets: dict[str, str] = {}
    for item in homework_items:
        doc_id = str(item.get("doc_id") or "<unknown>")
        metadata = item.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError(f"{doc_id} has invalid metadata")
        raw_records: Any = metadata.get("correct_answers")
        if isinstance(raw_records, str):
            try:
                raw_records = json.loads(raw_records)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{doc_id} has invalid correct_answers JSON") from exc
        if not isinstance(raw_records, list):
            raise ValueError(f"{doc_id} is missing structured answer records")

        validate_answer_records(raw_records)
        answer_first_lines = [
            _key(_question_text(record).splitlines()[0])
            for record in raw_records
        ]
        if len(answer_first_lines) != len(set(answer_first_lines)):
            raise ValueError(f"{doc_id} contains duplicate displayed question stems")

        rendered_first_lines = _rendered_question_first_lines(item.get("content"))
        if len(rendered_first_lines) != len(raw_records):
            raise ValueError(
                f"{doc_id} renders {len(rendered_first_lines)} questions "
                f"but stores {len(raw_records)} answer records"
            )
        if rendered_first_lines != answer_first_lines:
            raise ValueError(f"{doc_id} question content does not match its answer records")
        if len(rendered_first_lines) != len(set(rendered_first_lines)):
            raise ValueError(f"{doc_id} contains duplicate rendered questions")

        signature = homework_set_fingerprint(raw_records)
        previous = seen_sets.get(signature)
        if previous is not None and previous != doc_id:
            raise ValueError(f"Homework sets {previous} and {doc_id} are identical")
        seen_sets[signature] = doc_id


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


def ensure_unique_question_stems(
    records: Sequence[Mapping[str, Any]],
) -> List[dict[str, Any]]:
    """Make repeated generic stems distinct without changing their answers.

    Some valid 11+ questions deliberately share an instruction such as
    ``Which word is spelt correctly?`` while presenting different choices.
    The common RAG writer identifies questions by their first visible line, so
    those records must also have distinct first-line stems.  Repeated stems are
    labelled as choice groups; options, answers, explanations and metadata are
    preserved.
    """
    copied = [dict(record) for record in records]
    bare_questions = [_question_text(record) for record in copied]
    first_line_keys = [
        _key(question.splitlines()[0] if question.splitlines() else "")
        for question in bare_questions
    ]
    totals: dict[str, int] = {}
    for key in first_line_keys:
        totals[key] = totals.get(key, 0) + 1

    occurrences: dict[str, int] = {}
    for index, (record, question, key) in enumerate(
        zip(copied, bare_questions, first_line_keys), start=1
    ):
        lines = question.splitlines() or [""]
        if totals.get(key, 0) > 1:
            occurrence = occurrences.get(key, 0) + 1
            occurrences[key] = occurrence
            lines[0] = f"Choice group {occurrence}: {lines[0]}"
        rendered = "\n".join(lines).strip()
        record["q"] = index
        record["question"] = f"{index}. {rendered}"
        if "questionText" in record:
            record["questionText"] = rendered

    first_lines = [
        _key(_question_text(record).splitlines()[0])
        for record in copied
    ]
    if len(first_lines) != len(set(first_lines)):
        raise ValueError("Could not make all question stems unique")
    return copied


def render_student_question_set(
    records: Sequence[Mapping[str, Any]],
) -> str:
    """Render canonical answer records as the existing numbered A-E worksheet."""
    lines: List[str] = []
    for index, record in enumerate(records, start=1):
        question_lines = _question_text(record).splitlines() or [""]
        lines.append(f"{index}. {question_lines[0]}")
        lines.extend(question_lines[1:])
        for option_index, option in enumerate(record.get("options", [])):
            lines.append(f"   {chr(65 + option_index)}) {_option_text(option)}")
        lines.append("")
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
