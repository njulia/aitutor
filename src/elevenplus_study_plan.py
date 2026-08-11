"""Adaptive 30-day 11+ study plans built RAG-first.

The plan is created from the completed mock result. Generic practice sets already
in the 11+ RAG are preferred. Only a true RAG miss triggers an LLM generation,
and generated question sets are written back to the shared 11+ RAG for reuse.
No child name, email, or other direct identifier is sent to the model or stored
in generated RAG content.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from src.elevenplus_rag import (
    format_questions_only,
    get_elevenplus_rag_store,
    get_homework_questions,
)
from src.progress_db import save_mock_study_plan

logger = logging.getLogger(__name__)

DAYS = 30
MINUTES_PER_DAY = 30
QUESTIONS_PER_DAY = 5
MAX_WEAK_TOPICS = 6


def _clean(value: Any, limit: int = 100) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _weaknesses(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    for item in result.get("questions") or []:
        if item.get("correct"):
            continue
        subject = _clean(item.get("subject"), 60)
        topic = _clean(item.get("topic"), 80)
        if subject and topic:
            counts[(subject, topic)] += 1
    return [
        {"subject": subject, "topic": topic, "misses": misses}
        for (subject, topic), misses in counts.most_common(MAX_WEAK_TOPICS)
    ]


def _rag_questions(subject: str, topic: str, year_group: int) -> List[Dict[str, Any]]:
    store = get_elevenplus_rag_store()
    query = f"11+ {subject} {topic} targeted practice questions"
    try:
        rows = store.search(
            query,
            k=8,
            filters={"year_group": int(year_group), "subject": subject},
        )
    except Exception:
        logger.exception("Study-plan RAG search failed for %s/%s", subject, topic)
        return []

    questions: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        doc_id = str(row.get("doc_id") or "")
        if doc_id in seen:
            continue
        seen.add(doc_id)
        metadata = row.get("metadata") or {}
        # Never reuse another learner's personalised RAG document. Study-plan
        # retrieval is intentionally limited to shared/generic content.
        if metadata.get("student_id"):
            continue
        row_topic = _clean(metadata.get("topic"), 80)
        # Metadata topic is a strong signal. For legacy documents, semantic
        # retrieval is allowed to provide the fallback.
        if row_topic and row_topic.casefold() != topic.casefold():
            continue
        parsed = get_homework_questions(doc_id, str(row.get("content") or ""))
        for question in parsed:
            question = dict(question)
            question["subject"] = subject
            question["topic"] = topic
            question["doc_id"] = doc_id
            questions.append(question)
    return questions


def _extract_json(text: str) -> Any:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def _generate_missing(subject: str, topic: str, year_group: int, llm_client: Any) -> List[Dict[str, Any]]:
    if llm_client is None:
        from src.llm_client import LLMClient
        llm_client = LLMClient()

    prompt = f"""Create 15 original UK 11+ multiple-choice practice questions.
Subject: {subject}
Weak topic: {topic}
Learner year group: {year_group}

Return ONLY a JSON array. Each item must contain:
question (string), options (array of exactly 4 strings), correct_letter (A-D),
answer (the exact correct option text), explanation (short child-friendly explanation).
Do not copy or quote any school or commercial exam paper. Keep the questions
age-appropriate, clear, and focused on the weak topic. Vary the difficulty.
"""
    raw = llm_client.complete(
        [
            {"role": "system", "content": "You create safe, original UK primary 11+ practice questions."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=7000,
    )
    data = _extract_json(raw)
    if not isinstance(data, list):
        raise ValueError("The generated study questions were not a JSON list")

    valid: List[Dict[str, Any]] = []
    for index, item in enumerate(data[:15], start=1):
        if not isinstance(item, dict):
            continue
        question = _clean(item.get("question"), 500)
        options = [
            _clean(option, 250)
            for option in (item.get("options") or [])
            if _clean(option, 250)
        ]
        letter = _clean(item.get("correct_letter"), 2).upper()
        if not question or len(options) != 4 or letter not in {"A", "B", "C", "D"}:
            continue
        answer = options[ord(letter) - 65]
        valid.append({
            "number": index,
            "question": question,
            "options": options,
            "correct_letter": letter,
            "answer": answer,
            "explanation": _clean(item.get("explanation"), 500),
            "subject": subject,
            "topic": topic,
        })
    if len(valid) < 5:
        raise ValueError("The LLM returned too few usable study questions")
    return valid


def _store_generated(subject: str, topic: str, year_group: int, questions: List[Dict[str, Any]]) -> str:
    store = get_elevenplus_rag_store()
    records = []
    for question in questions:
        records.append({
            "question": question["question"],
            "options": question["options"],
            "correct_letter": question["correct_letter"],
            "answer": question["answer"],
            "explanation": question.get("explanation", ""),
        })
    content_questions = [
        {"number": i + 1, "question": q["question"], "options": [
            {"label": chr(65 + j), "text": option} for j, option in enumerate(q["options"])
        ]}
        for i, q in enumerate(questions)
    ]
    content = format_questions_only(content_questions)
    metadata = {
        "year_group": int(year_group),
        "subject": subject,
        "topic": topic,
        "homework_minutes": "30",
        "content_type": "adaptive_study_question",
        "source": "llm_fallback",
        "correct_answers": json.dumps(records, ensure_ascii=False, separators=(",", ":")),
    }
    return store.add_homework(content, metadata)


def _make_days(question_pool: List[Dict[str, Any]], weaknesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not question_pool:
        return []
    days: List[Dict[str, Any]] = []
    pool_size = len(question_pool)
    for day in range(1, DAYS + 1):
        start = ((day - 1) * QUESTIONS_PER_DAY) % pool_size
        selected = [question_pool[(start + offset) % pool_size] for offset in range(QUESTIONS_PER_DAY)]
        topic_counts = Counter(q.get("topic") for q in selected)
        focus = topic_counts.most_common(1)[0][0] if topic_counts else weaknesses[(day - 1) % len(weaknesses)]["topic"]
        days.append({
            "day": day,
            "minutes": MINUTES_PER_DAY,
            "focus_topic": focus,
            "activity": "5 targeted questions + review your answers",
            "questions": [
                {
                    "number": index + 1,
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "subject": q.get("subject", ""),
                    "topic": q.get("topic", ""),
                    "doc_id": q.get("doc_id", ""),
                }
                for index, q in enumerate(selected)
            ],
        })
    return days


def generate_mock_study_plan(
    *,
    student_id: str,
    year_group: int,
    exam_result: Dict[str, Any],
    llm_client: Any = None,
) -> Dict[str, Any]:
    """Build and persist the latest 30-day plan. Safe to call more than once."""
    weaknesses = _weaknesses(exam_result)
    if not weaknesses:
        # A strong score still gets a maintenance plan based on all subjects.
        subjects = [str(item.get("subject") or "") for item in exam_result.get("subject_breakdown") or []]
        weaknesses = [{"subject": s, "topic": "Mixed practice", "misses": 0} for s in subjects if s][:4]
    if not weaknesses:
        weaknesses = [{"subject": "Maths", "topic": "Mixed practice", "misses": 0}]

    pool: List[Dict[str, Any]] = []
    sources: List[str] = []
    generated_topics: List[str] = []
    for weakness in weaknesses:
        subject = weakness["subject"]
        topic = weakness["topic"]
        matches = _rag_questions(subject, topic, year_group)
        if matches:
            pool.extend(matches[:20])
            sources.append(f"RAG:{subject}:{topic}")
            continue
        generated = _generate_missing(subject, topic, year_group, llm_client)
        doc_id = _store_generated(subject, topic, year_group, generated)
        for question in generated:
            question["doc_id"] = doc_id
        pool.extend(generated)
        sources.append(f"LLM→RAG:{subject}:{topic}")
        generated_topics.append(f"{subject}: {topic}")

    # Keep the plan compact and deterministic. If the library is small, the
    # scheduler intentionally revisits questions so the learner can improve.
    days = _make_days(pool, weaknesses)
    plan = {
        "version": 1,
        "duration_days": DAYS,
        "minutes_per_day": MINUTES_PER_DAY,
        "questions_per_day": QUESTIONS_PER_DAY,
        "created_at": datetime.now(UTC).isoformat(),
        "exam": exam_result.get("exam") or {},
        "score": exam_result.get("score") or {},
        "weaknesses": weaknesses,
        "sources": sources,
        "generated_topics": generated_topics,
        "days": days,
    }
    if not days:
        raise RuntimeError("No practice questions were available for the study plan")
    save_mock_study_plan(student_id, plan)
    return plan
