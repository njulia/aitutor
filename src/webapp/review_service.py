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
from typing import Any, Dict, List, Optional

from .prompt_budget import budget_review_inputs, compact_text, stable_cache_key
from .child_safety import safety_result
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


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    """Return a safe integer for provider parameters and learner metadata."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _token_limit(env_name: str, default: int, maximum: int = 4_000) -> int:
    return _bounded_int(
        os.getenv(env_name),
        default=default,
        minimum=128,
        maximum=maximum,
    )


def _normalise_profile(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep only bounded, useful learner context for ages 5-11."""
    source = dict(profile or {})
    year_group = _bounded_int(source.get("year_group"), default=3, minimum=1, maximum=6)
    age = _bounded_int(source.get("age"), default=year_group + 4, minimum=5, maximum=11)
    cleaned: Dict[str, Any] = {
        "year_group": year_group,
        "age": age,
    }
    if source.get("plan_week") is not None:
        cleaned["plan_week"] = _bounded_int(
            source.get("plan_week"), default=1, minimum=1, maximum=52
        )
    if source.get("plan_phase"):
        cleaned["plan_phase"] = compact_text(source.get("plan_phase"), 40)
    if source.get("english_level"):
        cleaned["english_level"] = compact_text(source.get("english_level"), 60)
    goals = source.get("learning_goals")
    if isinstance(goals, (list, tuple)):
        cleaned["learning_goals"] = [compact_text(item, 100) for item in goals[:4]]
    return cleaned


def _prompt_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return non-identifying, age-bounded context for an LLM prompt."""
    return _normalise_profile(profile)


def _supports_model_override(callable_obj: Any) -> bool:
    try:
        parameters = inspect.signature(callable_obj).parameters.values()
    except (TypeError, ValueError):
        return True
    return any(
        parameter.name == "model" or parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def _resolved_model(llm_client: Any, requested_model: str) -> str:
    provider = str(getattr(llm_client, "provider", "") or "").strip().casefold()
    selected_model = str(requested_model or "").strip()
    if provider == "ollama":
        env_name = (
            "OLLAMA_DETAIL_REVIEW_MODEL"
            if requested_model == DETAIL_REVIEW_MODEL
            else "OLLAMA_QUICK_REVIEW_MODEL"
        )
        selected_model = (
            os.getenv(env_name)
            or getattr(llm_client, "model", None)
            or selected_model
        )
    return str(selected_model or getattr(llm_client, "model", "default"))


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
    provider = str(getattr(llm_client, "provider", "") or "").strip().casefold()
    # API tier aliases such as qwen-flash/qwen-plus are usually not local
    # Ollama model names. Keep the model already loaded by a local client.
    selected_model = _resolved_model(llm_client, model)

    safe_max_tokens = _bounded_int(max_tokens, default=1_000, minimum=128, maximum=4_000)
    logger.info(
        "[Review] operation=%s provider=%s model=%s max_tokens=%s",
        operation,
        provider or "unknown",
        selected_model,
        safe_max_tokens,
    )
    kwargs = {"temperature": float(temperature), "max_tokens": safe_max_tokens}
    if _supports_model_override(llm_client.complete):
        kwargs["model"] = selected_model
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


def _rag_quick_feedback(rows: List[Dict[str, Any]]) -> str:
    """Build instant, answer-key-grounded feedback without an LLM call."""
    correct_rows = [row for row in rows if row.get("is_correct")]
    wrong_rows = [row for row in rows if not row.get("is_correct")]

    sections = ["## What You Did Well"]
    if correct_rows:
        count = len(correct_rows)
        noun = "answer" if count == 1 else "answers"
        sections.append(
            f"You got {count} {noun} right. You used the question information carefully."
        )
    else:
        sections.append(
            "You had a good try. Checking the method one small step at a time will help."
        )

    sections.append("## What to Improve")
    if not wrong_rows:
        sections.append(
            "Nothing needs correcting this time. Keep showing your working on harder questions."
        )
    else:
        for index, row in enumerate(rows, start=1):
            if row.get("is_correct"):
                continue
            answer_label = row.get("correct_answer") or ""
            if row.get("correct_letter"):
                answer_label = f"Option {row['correct_letter']} — {answer_label}"
            explanation = row.get("explanation") or (
                "Read the question again, use the correct method, and check each step."
            )
            sections.append(
                f"- **Question {index}:** The correct answer is **{answer_label}**. "
                f"{compact_text(explanation, 220)}"
            )

    sections.extend(
        [
            "## Keep Going",
            "Well done for checking your work — one careful correction makes the next question easier.",
        ]
    )
    return "\n\n".join(sections)


def _rag_detailed_feedback(rows: List[Dict[str, Any]]) -> str:
    """Create a full child-friendly explanation from authoritative RAG data."""
    correct_count = sum(1 for row in rows if row.get("is_correct"))
    wrong_count = len(rows) - correct_count
    sections = ["## What You Did Well"]
    if correct_count:
        sections.append(
            f"You answered {correct_count} out of {len(rows)} correctly. "
            "You showed that you can use the information in the question and check an answer."
        )
    else:
        sections.append(
            "You kept trying. That matters, because each corrected step helps your brain learn the method."
        )

    sections.append("## What to Improve")
    if wrong_count:
        wrong_numbers = [str(index) for index, row in enumerate(rows, start=1) if not row.get("is_correct")]
        sections.append(
            f"There {'is' if wrong_count == 1 else 'are'} {wrong_count} "
            f"{'answer' if wrong_count == 1 else 'answers'} to revisit. "
            f"Focus on Question{'s' if wrong_count != 1 else ''} {', '.join(wrong_numbers)}. "
            "Work slowly, use the method below, and check the final answer against the question."
        )
    else:
        sections.append(
            "All answers are correct. Your next step is to keep your working clear and tidy."
        )

    sections.append(_worked_explanations(rows).strip())
    sections.extend(
        [
            "## Keep Going",
            "Excellent effort. Try to explain one method aloud in your own words — that helps it stick.",
        ]
    )
    return "\n\n".join(section for section in sections if section)


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
        if not row.get("is_correct"):
            sections.append(
                "**Why it may have gone wrong:** You may have chosen an answer before checking the final step."
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
    from src.prompts import REVIEW_QUICK_WITHOUT_RAG_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    intervention = safety_result("review", student_answers)
    if intervention is not None:
        return intervention
    raw_profile = dict(profile or {})
    student_id = raw_profile.get("student_id", "anonymous")
    profile = _normalise_profile(raw_profile)
    budget = budget_review_inputs(homework_content, student_answers, profile)
    cache_key = stable_cache_key(
        "review_quick_v4",
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
        # RAG already contains the authoritative answers and short methods.
        # Build the review locally: this is faster, cheaper and cannot fail due
        # to a missing provider model alias.
        feedback = _rag_quick_feedback(rows)
        worked = _worked_explanations(rows) if is_eleven_plus else ""
        review = (
            _table(rows)
            + f"**Score: {correct_count}/{attempted}**\n\n"
            + feedback
            + ("\n\n" + worked if worked else "")
        )
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
            max_tokens=_token_limit("QUICK_REVIEW_MAX_TOKENS", 900, maximum=1_600),
            operation="quick_review_no_rag_all_answers",
        )
        model_used = _resolved_model(llm_client, QUICK_REVIEW_MODEL)
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

    if not is_tutor_mode and student_id not in {None, "", "anonymous"} and not str(student_id).startswith("anon_"):
        try:
            from src.progress_db import save_homework_session

            save_homework_session(
                student_id=str(student_id),
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
    from src.prompts import REVIEW_DETAIL_WITHOUT_RAG_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    intervention = safety_result("explanation", student_answers)
    if intervention is not None:
        return intervention
    raw_profile = dict(profile or {})
    profile = _normalise_profile(raw_profile)
    budget = budget_review_inputs(homework_content, student_answers, profile, review_feedback)
    cache_key = stable_cache_key(
        "review_detail_v4",
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
        # Detailed RAG explanations can also be produced from the trusted
        # stored methods. Avoid a second paid/remote call and return instantly.
        ai_explanation = _rag_detailed_feedback(rows)
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
            max_tokens=_token_limit("DETAIL_REVIEW_MAX_TOKENS", 1_600, maximum=3_000),
            operation="detail_review_no_rag_all_answers",
        )
        score, max_score = _extract_score(explanation)

    model_used = None if rows else _resolved_model(llm_client, DETAIL_REVIEW_MODEL)
    result = {
        "success": True,
        "explanation": explanation,
        "from_rag_answers": bool(rows),
        "score": score,
        "max_score": max_score,
        "model_tier": "local" if rows else "plus",
        "model_used": model_used,
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
    intervention = safety_result("practice", student_answers)
    if intervention is not None:
        return intervention
    profile = _normalise_profile(dict(profile or {}))
    budget = budget_review_inputs(homework_content, student_answers, profile, review_feedback)
    cache_key = stable_cache_key(
        "practice_v2",
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
        student_profile=str(_prompt_profile(budget["profile"])),
        review_feedback=budget["review_feedback"] or "No review feedback available",
        year_group=budget["profile"].get("year_group", 3),
        age=budget["profile"].get("age", 7),
        correct_answers_section=compact_text(correct_answers_section, 4_000),
    )
    result = _complete_review(
        llm_client,
        build_messages(prompt),
        model=DETAIL_REVIEW_MODEL,
        temperature=0.25,
        max_tokens=_token_limit("PRACTICE_MAX_TOKENS", 1_000, maximum=1_600),
        operation="targeted_practice",
    )
    practice_cache.set(cache_key, result)
    return {"success": True, "practice": result}
