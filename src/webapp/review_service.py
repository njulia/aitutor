"""Homework review services with RAG-first marking and bounded prompts.

The functions are synchronous because provider SDKs and local RAG clients are
usually synchronous. FastAPI routes call them through ``run_blocking``.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .prompt_budget import budget_review_inputs, compact_text, select_relevant_items, stable_cache_key
from .question_utils import _parse_student_answers_to_map, _split_homework_into_questions

logger = logging.getLogger(__name__)


def _clean_answer(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _simple_correct(student_answer: str, correct_answer: str) -> bool:
    left = _clean_answer(student_answer).casefold().rstrip(". ")
    right = _clean_answer(correct_answer).casefold().rstrip(". ")
    return bool(left) and left == right


def _load_rag_answers(homework_doc_id: str, is_eleven_plus: bool) -> Optional[list]:
    if not homework_doc_id:
        return None
    if is_eleven_plus:
        from src.elevenplus_rag import search_homework_answers
    else:
        from src.homework_rag import search_homework_answers
    return search_homework_answers(homework_doc_id)


def _pair_rag_answers(
    raw_answers: Any,
    homework_content: str,
    subject: str,
    *,
    is_tutor_mode: bool,
    question_index: Optional[int],
) -> List[Dict[str, str]]:
    questions = _split_homework_into_questions(homework_content, subject)
    if not raw_answers:
        return []

    if isinstance(raw_answers, str):
        try:
            raw_answers = json.loads(raw_answers)
        except (TypeError, json.JSONDecodeError):
            raw_answers = [raw_answers]

    pairs: List[Dict[str, str]] = []
    if isinstance(raw_answers, list) and all(isinstance(item, dict) for item in raw_answers):
        for item in raw_answers:
            question = _clean_answer(item.get("question"))
            answer = _clean_answer(item.get("answer"))
            if question and answer:
                pairs.append({"question": question, "answer": answer})
    elif isinstance(raw_answers, list):
        for index, answer in enumerate(raw_answers):
            if index >= len(questions):
                break
            pairs.append(
                {
                    "question": questions[index].get("full_content") or questions[index]["content"],
                    "answer": _clean_answer(answer),
                }
            )

    if not is_tutor_mode or not pairs:
        return pairs

    # Tutor mode sends one displayed question, but RAG metadata can contain the
    # complete homework answer list. Preserve and use the original index.
    if question_index is not None and 0 <= question_index < len(pairs):
        return [pairs[question_index]]

    target = questions[0]["content"].casefold() if questions else homework_content.casefold()
    target = re.sub(r"^\s*(?:\d+[.)]|[-*])\s*", "", target)
    for item in pairs:
        candidate = re.sub(r"^\s*(?:\d+[.)]|[-*])\s*", "", item["question"].casefold())
        if candidate == target or candidate in target or target in candidate:
            return [item]
    return []


def _mark_rows(
    pairs: List[Dict[str, str]], student_answers: str, subject: str
) -> List[Dict[str, Any]]:
    question_texts = [item["question"] for item in pairs]
    answer_map = _parse_student_answers_to_map(student_answers, subject, question_texts)
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(pairs):
        question = item["question"]
        correct_answer = item["answer"]
        student_answer = answer_map.get(question)
        if student_answer is None and len(pairs) == 1:
            student_answer = student_answers.strip()
        if student_answer is None:
            lines = [line.strip() for line in student_answers.splitlines() if line.strip()]
            student_answer = lines[index] if index < len(lines) else ""

        is_correct = False
        if subject.casefold() in {"maths", "mathematics"}:
            try:
                from src.tools.math_tools import verify_math_answer

                is_correct = bool(
                    verify_math_answer(question, student_answer, correct_answer).get("is_correct")
                )
            except Exception:
                is_correct = _simple_correct(student_answer, correct_answer)
        else:
            is_correct = _simple_correct(student_answer, correct_answer)
        rows.append(
            {
                "question": question,
                "student_answer": _clean_answer(student_answer) or "No answer provided",
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            }
        )
    return rows


def _table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    header = "| Result | Question | Your answer | Correct answer |\n|---|---|---|---|\n"
    body = []
    for row in rows:
        values = [
            "✅" if row["is_correct"] else "❌",
            row["question"],
            row["student_answer"],
            row["correct_answer"],
        ]
        body.append("| " + " | ".join(str(value).replace("|", "\\|") for value in values) + " |")
    return "\n\n## Check your answers\n\n" + header + "\n".join(body) + "\n\n"


def _extract_score(text: str) -> tuple[Optional[float], Optional[int]]:
    match = re.search(r"(?:score\s*[:=-]?\s*)?(\d+(?:\.\d+)?)\s*/\s*(\d+)", text, re.I)
    if not match:
        return None, None
    numerator, denominator = float(match.group(1)), int(match.group(2))
    if denominator <= 0:
        return None, None
    return numerator, denominator


def review_homework(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile: Optional[dict] = None,
    *,
    is_tutor_mode: bool = False,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
    llm_client: Any = None,
) -> Dict[str, Any]:
    from src.cache import review_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import REVIEW_HOMEWORK_PROMPT, REVIEW_TUTOR_QUESTION_PROMPT, ELEVEN_PLUS_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    profile = dict(profile or {"year_group": 3, "age": 7})
    budget = budget_review_inputs(homework_content, student_answers, profile)
    cache_key = stable_cache_key(
        "review_tutor" if is_tutor_mode else "review_homework",
        subject,
        budget,
        homework_doc_id,
        question_index,
    )
    cached = review_cache.get(cache_key)
    if cached:
        return {"success": True, "review": cached, "from_cache": True}

    raw_answers = None
    rows: List[Dict[str, Any]] = []
    if homework_doc_id:
        try:
            raw_answers = _load_rag_answers(homework_doc_id, is_eleven_plus)
            pairs = _pair_rag_answers(
                raw_answers,
                budget["homework_content"],
                subject,
                is_tutor_mode=is_tutor_mode,
                question_index=question_index,
            )
            rows = _mark_rows(pairs, budget["student_answers"], subject)
        except Exception:
            logger.exception("RAG answer lookup failed for %s", homework_doc_id)

    correct_context = ""
    if rows:
        compact_rows = select_relevant_items(rows, max_items=20)
        correct_context = (
            "\n\n## Verified marking data\n"
            + json.dumps(compact_rows, ensure_ascii=False, separators=(",", ":"))
        )

    if is_eleven_plus:
        prompt_template = ELEVEN_PLUS_PROMPT
    elif is_tutor_mode:
        prompt_template = REVIEW_TUTOR_QUESTION_PROMPT
    else:
        prompt_template = REVIEW_HOMEWORK_PROMPT

    prompt = format_prompt(
        prompt_template,
        student_profile=str(budget["profile"]),
        subject=compact_text(subject, 80),
        day=datetime.now().strftime("%A, %d %B %Y"),
        homework_content=budget["homework_content"],
        student_answer=budget["student_answers"],
        context=correct_context,  # For ELEVEN_PLUS_PROMPT
        question=(
            f"Question: {budget['homework_content']}\n\nStudent Answer: {budget['student_answers']}"
            if is_eleven_plus else budget["student_answers"]
        ),
        correct_answers_section=correct_context,
        feedback_instruction=(
            "Use kind, simple UK English. Praise effort, explain one next step, "
            "and never ask for personal information."
        ),
    )
    llm_text = str(llm_client.complete(build_messages(prompt)))
    review = _table(rows) + llm_text
    review_cache.set(cache_key, review)

    correct_count = sum(1 for row in rows if row["is_correct"])
    attempted = len(rows)
    score: Optional[float] = float(correct_count) if rows else None
    max_score: Optional[int] = attempted if rows else None
    if score is None:
        score, max_score = _extract_score(llm_text)

    if not is_tutor_mode:
        try:
            from src.progress_db import save_homework_session

            save_homework_session(
                student_id=str(profile.get("student_id", "anonymous")),
                subject=subject,
                year_group=int(profile.get("year_group", 3)),
                # Raw child work is not persisted unless explicitly enabled.
                homework_content=budget["homework_content"],
                student_answers=budget["student_answers"],
                score=score,
                review_text=review,
                max_score=max_score or 10,
            )
        except Exception:
            logger.exception("Could not save homework progress")

    return {
        "success": True,
        "review": review,
        "from_rag_answers": bool(rows),
        "score": score,
        "max_score": max_score,
        "correct_count": correct_count if rows else None,
        "attempted": attempted if rows else None,
    }


def explain_deep(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile: Optional[dict] = None,
    review_feedback: str = "",
    *,
    llm_client: Any = None,
) -> Dict[str, Any]:
    from src.cache import explain_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import EXPLAIN_DEEP_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    budget = budget_review_inputs(homework_content, student_answers, profile, review_feedback)
    key = stable_cache_key("explain", subject, budget)
    cached = explain_cache.get(key)
    if cached:
        return {"success": True, "explanation": cached, "from_cache": True}
    prompt = format_prompt(
        EXPLAIN_DEEP_PROMPT,
        homework_content=budget["homework_content"],
        student_answer=budget["student_answers"],
        subject=compact_text(subject, 80),
        student_profile=str(budget["profile"]),
        review_feedback=budget["review_feedback"] or "No review feedback available",
        year_group=budget["profile"].get("year_group", 3),
        age=budget["profile"].get("age", 7),
    )
    result = str(llm_client.complete(build_messages(prompt)))
    explain_cache.set(key, result)
    return {"success": True, "explanation": result}


def improve_practice(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile: Optional[dict] = None,
    review_feedback: str = "",
    *,
    llm_client: Any = None,
) -> Dict[str, Any]:
    from src.cache import practice_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import IMPROVE_PRACTICE_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    budget = budget_review_inputs(homework_content, student_answers, profile, review_feedback)
    key = stable_cache_key("practice", subject, budget)
    cached = practice_cache.get(key)
    if cached:
        return {"success": True, "practice": cached, "from_cache": True}
    prompt = format_prompt(
        IMPROVE_PRACTICE_PROMPT,
        homework_content=budget["homework_content"],
        student_answer=budget["student_answers"],
        subject=compact_text(subject, 80),
        student_profile=str(budget["profile"]),
        review_feedback=budget["review_feedback"] or "No review feedback available",
        year_group=budget["profile"].get("year_group", 3),
        age=budget["profile"].get("age", 7),
    )
    result = str(llm_client.complete(build_messages(prompt)))
    practice_cache.set(key, result)
    return {"success": True, "practice": result}
