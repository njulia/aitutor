"""Shared helpers for deterministic, RAG-ready homework generation.

The public generator contract is unchanged: each subject generator returns a
worksheet string plus a positional list of correct answers.  These helpers only
make the worksheets easier to mark reliably by ensuring that questions are
numbered, answerable without subjective judgement, and deterministic for a
subject/year/topic/set combination.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from typing import Iterable, Sequence

# Add the project root to the import path when a generator is run directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.homework_rag import get_homework_rag_store


RAG_WRITE_BATCH_SIZE = 250
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def count_year_homework(store, year_group: int, subject: str) -> int:
    """Count every stored subject document for one year."""
    where = {"year_group": year_group, "subject": subject}
    return store.store.count_by_metadata(where)


def clean_year_homeworks(store, year_group: int, subject: str) -> int:
    """Delete all stored homework for one subject and year."""
    results = store.search_by_metadata(
        {"year_group": year_group, "subject": subject}, k=10_000
    )
    if not results:
        print(f"  Year {year_group}: no homework to clean")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1
    print(f"  Year {year_group}: cleaned {deleted} homework documents")
    return deleted


def clean_subject_homeworks(store, subject: str) -> int:
    """Delete all stored homework for one subject."""
    results = store.search_by_metadata({"subject": subject}, k=100_000)
    if not results:
        print(f"  Subject {subject}: no homework to clean")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1
    print(f"  Subject {subject}: cleaned {deleted} homework documents")
    return deleted


def check_year_homework_exists(store, year_group: int, subject: str) -> bool:
    """Return whether an exact year/subject document exists."""
    return count_year_homework(store, year_group, subject) > 0


def add_homework_in_batches(store, homework_items: list) -> int:
    """Store homework safely in small, restartable batches."""
    added_total = 0
    for start in range(0, len(homework_items), RAG_WRITE_BATCH_SIZE):
        batch = homework_items[start : start + RAG_WRITE_BATCH_SIZE]
        requested_ids = [item["doc_id"] for item in batch]
        existing_result = store.store.get_by_ids(ids=requested_ids)
        existing_ids = {row["doc_id"] for row in existing_result}
        new_items = [item for item in batch if item["doc_id"] not in existing_ids]

        if new_items:
            store.add_batch_homework(new_items)
            added_total += len(new_items)

        completed = min(start + len(batch), len(homework_items))
        print(
            f"  Stored {completed}/{len(homework_items)} "
            f"({len(new_items)} new, {len(batch) - len(new_items)} already existed)"
        )
    return added_total


def get_rag_stats(store):
    stats = store.get_stats()
    print("\nRAG storage statistics:")
    print(f"  Total documents: {stats['total_documents']}")
    print(f"  By subject: {stats['by_subject']}")
    print(f"  By year: {stats['by_year_group']}")


def stable_random(subject: str, year_group: int, topic: str, index: int) -> random.Random:
    """Return a repeatable RNG without depending on Python's salted hash()."""
    seed_text = f"{subject}|{year_group}|{topic}|{index}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_text).digest()[:8], "big")
    return random.Random(seed)


def unique_values(values: Iterable[object]) -> list[str]:
    """Normalise option values while preserving order."""
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            output.append(text)
            seen.add(key)
    return output


def make_mcq(
    stem: str,
    correct: object,
    distractors: Sequence[object],
    rng: random.Random,
) -> tuple[str, str]:
    """Build one four-option question and return its exact answer text."""
    answer = str(correct).strip()
    options = unique_values([answer, *distractors])
    # A generated value can occasionally duplicate a distractor (for example,
    # 12:30 when the correct hour is 12). Add neutral fallbacks rather than
    # failing a long batch generation run.
    if len(options) < 4:
        options = unique_values([
            *options,
            "None of these",
            "Cannot be determined",
            "All of these",
            "A different answer",
        ])
    if len(options) < 4:
        raise ValueError(f"Question needs four unique options: {stem!r}")
    # Keep the correct answer and select no more than three distinct distractors.
    wrong = [item for item in options if item.casefold() != answer.casefold()]
    chosen = [answer, *rng.sample(wrong, 3)]
    rng.shuffle(chosen)
    option_lines = [f"{chr(65 + i)}. {value}" for i, value in enumerate(chosen)]
    return f"{stem}\n" + "\n".join(option_lines), answer


def make_true_false(statement: str, is_true: bool, rng: random.Random) -> tuple[str, str]:
    return make_mcq(
        f"Is this statement true or false? {statement}",
        "True" if is_true else "False",
        ["False" if is_true else "True", "Not enough information", "Both true and false"],
        rng,
    )


def render_homework(
    subject: str,
    year_group: int,
    topic: str,
    index: int,
    question_answer_pairs: Sequence[tuple[str, str]],
    *,
    note: str = "",
) -> tuple[str, list[str]]:
    """Render the unchanged numbered worksheet + positional answer-list format."""
    if len(question_answer_pairs) != 10:
        raise ValueError(
            f"{subject} Year {year_group} {topic!r} must contain exactly 10 questions"
        )
    title = f"{subject} Homework - Year {year_group} - {topic} (Set {index})"
    lines = [title]
    if note:
        lines.extend(["", note.strip()])
    lines.append("")
    answers: list[str] = []
    for number, (question, answer) in enumerate(question_answer_pairs, start=1):
        clean_question = str(question).strip()
        clean_answer = str(answer).strip()
        if not clean_question or not clean_answer:
            raise ValueError("Questions and answers must not be empty")
        lines.append(f"{number}. {clean_question}")
        answers.append(clean_answer)
    return "\n".join(lines), answers


def build_batch_item(
    *,
    content: str,
    answers: Sequence[str],
    year_group: int,
    subject: str,
    topic: str,
    homework_minutes: str,
    key_stage: str,
    doc_id: str,
) -> dict:
    """Create the same RAG batch shape used by the existing generators."""
    return {
        "content": content,
        "metadata": {
            "year_group": year_group,
            "subject": subject,
            "homework_minutes": homework_minutes,
            "key_stage": key_stage,
            "topic": topic,
            "student_id": None,
            "correct_answers": json.dumps(list(answers), ensure_ascii=False),
        },
        "doc_id": doc_id,
    }
