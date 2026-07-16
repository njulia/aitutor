"""Homework review services with RAG-first marking and bounded prompts.

The functions are synchronous because provider SDKs and local RAG clients are
usually synchronous. FastAPI routes call them through ``run_blocking``.
"""
from __future__ import annotations

import inspect
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .prompt_budget import budget_review_inputs, compact_text, select_relevant_items, stable_cache_key
from .question_utils import _parse_student_answers_to_map, _split_homework_into_questions
from src.models import subject_display_name

logger = logging.getLogger(__name__)

QUICK_REVIEW_MODEL = (
    os.getenv("QUICK_REVIEW_MODEL")
    or os.getenv("FLASH_MODEL")
    or "qwen-flash"
).strip()
DETAIL_REVIEW_MODEL = (
    os.getenv("DETAIL_REVIEW_MODEL")
    or os.getenv("PLUS_MODEL")
    or "qwen-plus"
).strip()


def _prompt_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Remove identifiers before learner context is sent to an LLM."""
    return {key: value for key, value in profile.items() if key != "student_id"}


def _supports_model_override(callable_obj: Any) -> bool:
    try:
        parameters = inspect.signature(callable_obj).parameters.values()
    except (TypeError, ValueError):
        return True
    return any(
        parameter.name == "model" or parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def _complete_review(
    llm_client: Any,
    messages: List[Dict[str, str]],
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    operation: str,
) -> str:
    """Call the selected model while remaining compatible with simple test fakes."""
    logger.info("[Review] operation=%s model=%s max_tokens=%s", operation, model, max_tokens)
    kwargs = {"temperature": temperature, "max_tokens": max_tokens}
    if _supports_model_override(llm_client.complete):
        kwargs["model"] = model
    return str(llm_client.complete(messages, **kwargs))


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
) -> List[Dict[str, Any]]:
    questions = _split_homework_into_questions(homework_content, subject)
    if not raw_answers:
        return []

    if isinstance(raw_answers, str):
        try:
            raw_answers = json.loads(raw_answers)
        except (TypeError, json.JSONDecodeError):
            raw_answers = [raw_answers]

    # In tutor mode the browser sends only the displayed question while the
    # RAG document contains the full answer list. Select by the preserved
    # original index before attempting text matching.
    if (
        is_tutor_mode
        and question_index is not None
        and isinstance(raw_answers, list)
        and 0 <= question_index < len(raw_answers)
    ):
        selected = raw_answers[question_index]
        displayed_question = (
            questions[0].get("full_content") or questions[0]["content"]
            if questions else homework_content
        )
        if isinstance(selected, dict):
            answer = _clean_answer(selected.get("answer"))
            question = _clean_answer(selected.get("question")) or _clean_answer(displayed_question)
            record = {
                "question": question,
                "answer": answer,
                "correct_letter": _clean_answer(selected.get("correct_letter") or selected.get("correctLetter")).upper(),
                "explanation": _clean_answer(selected.get("explanation")),
                "tip": _clean_answer(selected.get("tip") or selected.get("coaching_strategy")),
            }
        else:
            answer = _clean_answer(selected)
            question = _clean_answer(displayed_question)
            record = {"question": question, "answer": answer}
        return [record] if question and answer else []

    pairs: List[Dict[str, Any]] = []
    if isinstance(raw_answers, list) and all(isinstance(item, dict) for item in raw_answers):
        for item in raw_answers:
            question = _clean_answer(item.get("question"))
            answer = _clean_answer(item.get("answer"))
            if question and answer:
                pairs.append({
                    "question": question,
                    "answer": answer,
                    "correct_letter": _clean_answer(item.get("correct_letter") or item.get("correctLetter")).upper(),
                    "explanation": _clean_answer(item.get("explanation")),
                    "tip": _clean_answer(item.get("tip") or item.get("coaching_strategy")),
                })
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


def _answer_matches(student_answer: str, item: Dict[str, Any], subject: str) -> bool:
    correct_answer = _clean_answer(item.get("answer"))
    correct_letter = _clean_answer(item.get("correct_letter")).upper()
    candidate = _clean_answer(student_answer)
    candidate_without_option = re.sub(r"^option\s+", "", candidate, flags=re.I).strip()
    candidate_letter_match = re.match(r"^([A-H])(?:[.)\s:-]|$)", candidate_without_option, re.I)
    if correct_letter and (
        candidate_without_option.upper() == correct_letter
        or (candidate_letter_match and candidate_letter_match.group(1).upper() == correct_letter)
    ):
        return True

    if subject_display_name(subject).casefold() in {"maths", "mathematics"}:
        try:
            from src.tools.math_tools import verify_math_answer

            return bool(
                verify_math_answer(str(item.get("question") or ""), candidate, correct_answer).get("is_correct")
            )
        except Exception:
            return _simple_correct(candidate, correct_answer)
    return _simple_correct(candidate, correct_answer)


def _mark_rows(
    pairs: List[Dict[str, Any]], student_answers: str, subject: str
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

        is_correct = _answer_matches(student_answer, item, subject)
        rows.append(
            {
                "question": question,
                "student_answer": _clean_answer(student_answer) or "No answer provided",
                "correct_answer": correct_answer,
                "correct_letter": _clean_answer(item.get("correct_letter")).upper(),
                "explanation": _clean_answer(item.get("explanation")),
                "tip": _clean_answer(item.get("tip")),
                "is_correct": is_correct,
            }
        )
    return rows


def _clean_question_text(text: str) -> str:
    """Remove common homework title prefixes from question text."""
    if not text:
        return ""
    # Remove "Maths Homework - Year X - Topic (Set Y)" or similar prefixes
    # Matches: "Maths Homework - Year 2 - Fractions (Halves and Quarters) (Set 12) "
    # or "English Homework - Year 3 - Punctuation "
    clean = re.sub(
        r"^[a-zA-Z\s]+Homework\s*-\s*Year\s*\d+\s*-\s*.*?(?:\(Set\s*\d+\))?\s*",
        "",
        str(text),
        flags=re.IGNORECASE
    ).strip()
    return clean or str(text)


def _table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    header = "| Result | Question | Your answer | Correct answer |\n|---|---|---|---|\n"
    body = []
    # We use a custom replacement to avoid breaking Markdown table structure.
    # We replace | with \| and ensure no single-line row breaks.
    for row in rows:
        question = _clean_question_text(row["question"])
        values = [
            "✅" if row["is_correct"] else "❌",
            str(question).replace("\n", " ").replace("|", "\\|"),
            str(row["student_answer"]).replace("\n", " ").replace("|", "\\|"),
            str(row["correct_answer"]).replace("\n", " ").replace("|", "\\|"),
        ]
        body.append("| " + " | ".join(values) + " |")
    return "\n\n## Check your answers\n\n" + header + "\n".join(body) + "\n\n"


def _score_summary(rows: List[Dict[str, Any]]) -> str:
    correct = sum(1 for row in rows if row.get("is_correct"))
    return f"{correct}/{len(rows)} correct"


def _correct_work_summary(rows: List[Dict[str, Any]]) -> str:
    lines = []
    for index, row in enumerate(rows, start=1):
        if not row.get("is_correct"):
            continue
        lines.append(
            f"- Q{index}: {compact_text(_clean_question_text(row.get('question', '')), 120)} "
            f"| pupil answer: {compact_text(row.get('student_answer', ''), 60)}"
        )
    if not lines:
        return "No answers were marked correct. Praise effort without inventing success."
    return compact_text("\n".join(lines), 1_600)


def _rag_review_items(rows: List[Dict[str, Any]], *, correct: bool, detailed: bool) -> str:
    lines = []
    for index, row in enumerate(rows, start=1):
        if bool(row.get("is_correct")) is not correct:
            continue
        question_limit = 150 if detailed else 120
        parts = [
            f"Q{index}",
            f"question: {compact_text(_clean_question_text(row.get('question', '')), question_limit)}",
            f"pupil answer: {compact_text(row.get('student_answer', ''), 90)}",
            f"correct answer: {compact_text(row.get('correct_answer', ''), 100)}",
        ]
        if row.get("correct_letter"):
            parts.append(f"correct option: {row['correct_letter']}")
        if detailed or not correct:
            parts.append(
                "answer-key method: "
                + compact_text(
                    row.get("explanation")
                    or "Use the correct answer and explain the shortest age-appropriate method.",
                    260 if detailed else 180,
                )
            )
        if row.get("tip") and (detailed or not correct):
            parts.append(f"tip: {compact_text(row.get('tip'), 120)}")
        lines.append("- " + " | ".join(parts))
    if not lines:
        return "None."
    return compact_text("\n".join(lines), 8_000 if detailed else 4_500)


def _all_correct_quick_feedback(rows: List[Dict[str, Any]]) -> str:
    count = len(rows)
    noun = "question" if count == 1 else "questions"
    return (
        "## What You Did Well\n"
        f"You answered all {count} {noun} correctly. Your careful checking paid off.\n\n"
        "## What to Improve\n"
        "Keep showing clear working so you can spot small slips in harder questions.\n\n"
        "## Keep Going\n"
        "Brilliant effort — you are ready for the next challenge!"
    )


def _worked_explanations(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    sections = ["## How to work out each answer"]
    for index, row in enumerate(rows, start=1):
        status = "Correct" if row.get("is_correct") else "Try this one again"
        answer_label = row.get("correct_answer") or ""
        if row.get("correct_letter"):
            answer_label = f"Option {row['correct_letter']} — {answer_label}"
        explanation = row.get("explanation") or (
            "Compare the question with the correct answer, then repeat the method slowly and check each step."
        )
        sections.extend(
            [
                f"### Question {index}: {status}",
                f"**Correct answer:** {answer_label}",
                f"**How to get it:** {explanation}",
            ]
        )
        if row.get("tip"):
            sections.append(f"**Helpful 11+ tip:** {row['tip']}")
    return "\n\n".join(sections) + "\n\n"


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
    """Run the quick-check path.

    RAG answers are marked deterministically first, then only wrong-answer
    context is sent to the Flash model. Without RAG, Flash checks all answers.
    """
    from src.cache import review_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import REVIEW_QUICK_WITH_RAG_PROMPT, REVIEW_QUICK_WITHOUT_RAG_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    profile = dict(profile or {"year_group": 3, "age": 7})
    budget = budget_review_inputs(homework_content, student_answers, profile)
    cache_key = stable_cache_key(
        "review_quick_v3",
        QUICK_REVIEW_MODEL,
        subject,
        budget,
        homework_doc_id,
        question_index,
        bool(is_eleven_plus),
    )
    cached = review_cache.get(cache_key)
    if cached:
        if isinstance(cached, dict):
            return {**cached, "from_cache": True}
        return {"success": True, "review": str(cached), "from_cache": True}

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

    correct_count = sum(1 for row in rows if row["is_correct"])
    attempted = len(rows)
    score: Optional[float] = float(correct_count) if rows else None
    max_score: Optional[int] = attempted if rows else None
    model_used: Optional[str] = None

    if rows:
        wrong_rows = [row for row in rows if not row["is_correct"]]
        if wrong_rows:
            prompt = format_prompt(
                REVIEW_QUICK_WITH_RAG_PROMPT,
                student_profile=str(_prompt_profile(budget["profile"])),
                subject=compact_text(subject_display_name(subject), 80),
                score_summary=_score_summary(rows),
                correct_work_summary=_correct_work_summary(rows),
                wrong_answer_items=_rag_review_items(rows, correct=False, detailed=False),
            )
            feedback = _complete_review(
                llm_client,
                build_messages(prompt),
                model=QUICK_REVIEW_MODEL,
                temperature=0.15,
                max_tokens=450,
                operation="quick_review_rag_wrong_only",
            )
            model_used = QUICK_REVIEW_MODEL
        else:
            # No mistakes means there is no wrong-answer context to send.
            feedback = _all_correct_quick_feedback(rows)
        review = _table(rows) + f"**Score: {correct_count}/{attempted}**\n\n" + feedback
    else:
        prompt = format_prompt(
            REVIEW_QUICK_WITHOUT_RAG_PROMPT,
            student_profile=str(_prompt_profile(budget["profile"])),
            subject=compact_text(subject_display_name(subject), 80),
            homework_content=budget["homework_content"],
            student_answer=budget["student_answers"],
        )
        review = _complete_review(
            llm_client,
            build_messages(prompt),
            model=QUICK_REVIEW_MODEL,
            temperature=0.15,
            max_tokens=os.getenv("QUICK_REVIEW_MAX_TOKENS", "1000"),
            operation="quick_review_no_rag_all_answers",
        )
        model_used = QUICK_REVIEW_MODEL
        score, max_score = _extract_score(review)

    result = {
        "success": True,
        "review": review,
        "from_rag_answers": bool(rows),
        "score": score,
        "max_score": max_score,
        "correct_count": correct_count if rows else None,
        "attempted": attempted if rows else None,
        "model_tier": "flash" if model_used else "local",
        "model_used": model_used,
    }
    review_cache.set(cache_key, result)

    if not is_tutor_mode:
        try:
            from src.progress_db import save_homework_session

            save_homework_session(
                student_id=str(profile.get("student_id", "anonymous")),
                subject=subject,
                year_group=int(profile.get("year_group", 3)),
                homework_content=budget["homework_content"],
                student_answers=budget["student_answers"],
                score=score,
                review_text=review,
                max_score=max_score or 10,
            )
        except Exception:
            logger.exception("Could not save homework progress")

    return result

def explain_deep(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile: Optional[dict] = None,
    review_feedback: str = "",
    *,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
    llm_client: Any = None,
) -> Dict[str, Any]:
    """Run the detailed-check path using the Plus model.

    With RAG, correct items are compact and wrong items carry full answer-key
    context. Without RAG, Plus receives all questions and answers.
    """
    from src.cache import explain_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import REVIEW_DETAIL_WITH_RAG_PROMPT, REVIEW_DETAIL_WITHOUT_RAG_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    budget = budget_review_inputs(homework_content, student_answers, profile, review_feedback)
    cache_key = stable_cache_key(
        "review_detail_v3",
        DETAIL_REVIEW_MODEL,
        subject,
        budget,
        homework_doc_id,
        question_index,
        bool(is_eleven_plus),
    )
    cached = explain_cache.get(cache_key)
    if cached:
        if isinstance(cached, dict):
            return {**cached, "from_cache": True}
        return {
            "success": True,
            "explanation": str(cached),
            "from_cache": True,
            "model_tier": "plus",
            "model_used": DETAIL_REVIEW_MODEL,
        }

    rows: List[Dict[str, Any]] = []
    if homework_doc_id:
        try:
            raw_answers = _load_rag_answers(homework_doc_id, is_eleven_plus)
            pairs = _pair_rag_answers(
                raw_answers,
                budget["homework_content"],
                subject,
                is_tutor_mode=False,
                question_index=question_index,
            )
            rows = _mark_rows(pairs, budget["student_answers"], subject)
        except Exception:
            logger.exception("RAG answer lookup failed in explain_deep for %s", homework_doc_id)

    if rows:
        correct_count = sum(1 for row in rows if row["is_correct"])
        prompt = format_prompt(
            REVIEW_DETAIL_WITH_RAG_PROMPT,
            student_profile=str(_prompt_profile(budget["profile"])),
            subject=compact_text(subject_display_name(subject), 80),
            score_summary=_score_summary(rows),
            correct_answer_items=_rag_review_items(rows, correct=True, detailed=True),
            wrong_answer_items=_rag_review_items(rows, correct=False, detailed=True),
        )
        ai_explanation = _complete_review(
            llm_client,
            build_messages(prompt),
            model=DETAIL_REVIEW_MODEL,
            temperature=0.2,
            max_tokens=os.getenv("DETAIL_REVIEW_MAX_TOKENS", 3000),
            operation="detail_review_rag_all_answers",
        )
        explanation = (
            _table(rows)
            + f"**Score: {correct_count}/{len(rows)}**\n\n"
            + ai_explanation
        )
        score: Optional[float] = float(correct_count)
        max_score: Optional[int] = len(rows)
    else:
        prompt = format_prompt(
            REVIEW_DETAIL_WITHOUT_RAG_PROMPT,
            student_profile=str(_prompt_profile(budget["profile"])),
            subject=compact_text(subject_display_name(subject), 80),
            homework_content=budget["homework_content"],
            student_answer=budget["student_answers"],
        )
        explanation = _complete_review(
            llm_client,
            build_messages(prompt),
            model=DETAIL_REVIEW_MODEL,
            temperature=0.2,
            max_tokens=1_600,
            operation="detail_review_no_rag_all_answers",
        )
        score, max_score = _extract_score(explanation)

    result = {
        "success": True,
        "explanation": explanation,
        "from_rag_answers": bool(rows),
        "score": score,
        "max_score": max_score,
        "model_tier": "plus",
        "model_used": DETAIL_REVIEW_MODEL,
    }
    explain_cache.set(cache_key, result)
    return result

def improve_practice(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile: Optional[dict] = None,
    review_feedback: str = "",
    *,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
    llm_client: Any = None,
) -> Dict[str, Any]:
    from src.cache import practice_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import IMPROVE_PRACTICE_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    budget = budget_review_inputs(homework_content, student_answers, profile, review_feedback)
    cache_key = stable_cache_key(
        "practice",
        subject,
        budget,
        homework_doc_id,
        question_index,
    )
    cached = practice_cache.get(cache_key)
    if cached:
        return {"success": True, "practice": cached, "from_cache": True}

    correct_answers_section = ""
    if homework_doc_id:
        try:
            raw_answers = _load_rag_answers(homework_doc_id, is_eleven_plus)
            pairs = _pair_rag_answers(
                raw_answers,
                budget["homework_content"],
                subject,
                is_tutor_mode=False,
                question_index=question_index,
            )
            rows = _mark_rows(pairs, budget["student_answers"], subject)
            if rows:
                correct_answers_section = "## Authoritative Correct Answers and Explanations\n"
                for i, r in enumerate(rows, 1):
                    correct_answers_section += (
                        f"Question {i}: {r['question']}\n"
                        f"Correct Answer: {r['correct_answer']}\n"
                        f"Authoritative Explanation: {r.get('explanation') or 'N/A'}\n"
                    )
        except Exception:
            logger.exception("RAG answer lookup failed in improve_practice for %s", homework_doc_id)

    prompt = format_prompt(
        IMPROVE_PRACTICE_PROMPT,
        homework_content=budget["homework_content"],
        student_answer=budget["student_answers"],
        subject=compact_text(subject_display_name(subject), 80),
        student_profile=str(budget["profile"]),
        review_feedback=budget["review_feedback"] or "No review feedback available",
        year_group=budget["profile"].get("year_group", 3),
        age=budget["profile"].get("age", 7),
        correct_answers_section=correct_answers_section,
    )
    result = str(llm_client.complete(build_messages(prompt), temperature=0.25, max_tokens=1200))
    practice_cache.set(cache_key, result)
    return {"success": True, "practice": result}
