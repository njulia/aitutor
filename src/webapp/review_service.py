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
from .question_utils import (
    _parse_student_answers_to_map,
    _split_homework_into_questions,
    normalise_homework_content,
    parse_public_questions,
    public_homework_content,
)
from src.models import subject_display_name

logger = logging.getLogger(__name__)

QUICK_REVIEW_MODEL = (
    os.getenv("QUICK_REVIEW_MODEL")
    or "deepseek-v4-flash"
).strip()
DETAIL_REVIEW_MODEL = (
    os.getenv("DETAIL_REVIEW_MODEL")
    or "gemini-2.5-flash"
).strip()

PRACTICE_GENERATION_UNAVAILABLE_MESSAGE = (
    "The AI tutor did not return any usable practice questions, so no new content "
    "was created. Please try again in a moment."
)

RAG_REVIEW_FALLBACK_FEEDBACK = (
    "## Your answers are marked\n\n"
    "I used the trusted Homework Magic answer key to check this work. "
    "The AI teacher could not add extra comments just now, but your marked "
    "answers and score are ready."
)

_PRACTICE_SECTION_RE = re.compile(
    r"(?im)^\s*#{1,6}\s*(?:\d+\s*[.)-]?\s*)?"
    r"(?:(?:similar|targeted|extra|adaptive)\s+)?practice questions?\s*:?[\s*]*$"
)
_NUMBERED_PRACTICE_QUESTION_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(?:\*\*)?"
    r"(?:(?:practice|challenge)\s+)?(?:question|q)?\s*\d+[ \t]*"
    # 接受三种编号问题格式：1) 行内带标点正文、2) 加粗 **1.** 正文、
    # 3) 标题式 ### Question 1（编号后直接换行，正文在下一行）
    r"(?:[).:\-][ \t]*\S|\*\*[ \t]*\S|$)"
)


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


def _resolved_provider(llm_client: Any, requested_model: str) -> str:
    configured_provider = str(getattr(llm_client, "provider", "") or "").strip().casefold()
    # A local-only client must never be routed to a hosted review provider.
    # Check this before probing provider_for_model: permissive mocks and proxy
    # objects can manufacture arbitrary attributes on access.
    if configured_provider == "ollama":
        return "ollama"
    resolver = getattr(llm_client, "provider_for_model", None)
    if callable(resolver):
        return str(resolver(requested_model) or "").strip().casefold()
    return configured_provider


def _resolved_model(llm_client: Any, requested_model: str) -> str:
    provider = _resolved_provider(llm_client, requested_model)
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
    provider = _resolved_provider(llm_client, model)
    # API tier aliases such as qwen-flash/qwen-plus are usually not local
    # Ollama model names. Keep the model already loaded by a local client.
    selected_model = _resolved_model(llm_client, model)

    safe_max_tokens = _bounded_int(
        max_tokens, default=max_tokens, minimum=128, maximum=8000
    )
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
    raw_result = llm_client.complete(messages, **kwargs)
    if raw_result is None:
        return ""
    return str(raw_result).strip()


def _normalise_generated_practice_text(raw_result: Any) -> str:
    """Make common Gemini/Markdown question formats parseable by our renderer.

    Gemini sometimes returns fenced Markdown or writes ``Question 1:`` /
    ``**1.**`` instead of the numbered worksheet format used by the public
    question parser. This is presentation normalisation only; it does not add
    or change learning content.
    """
    text = str(raw_result or "").replace("\\r\\n", "\\n").strip()
    if not text:
        return ""
    text = re.sub(r"(?im)^\\s*```(?:markdown|text)?\\s*$", "", text)
    text = re.sub(r"(?im)^\\s*```\\s*$", "", text).strip()

    # Normalise heading-style question numbers while preserving the question
    # text and answer choices exactly.
    text = re.sub(
        r"(?im)^\\s*(?:#{1,6}\\s*)?\\*\\*Question\\s+(\\d+)\\s*[:.)-]\\*\\*\\s*",
        r"\\1. ",
        text,
    )
    text = re.sub(
        r"(?im)^\\s*(?:#{1,6}\\s*)?Question\\s+(\\d+)\\s*[:.)-]\\s*",
        r"\\1. ",
        text,
    )
    text = re.sub(
        r"(?im)^\\s*\\*\\*(\\d+)\\s*[.)-]\\s*\\*\\*\\s*",
        r"\\1. ",
        text,
    )
    return text.strip()


def _usable_generated_practice(raw_result: Any) -> tuple[str, List[Dict[str, Any]]]:
    """Return learner-safe practice only when the model produced questions."""
    practice = public_homework_content(
        normalise_homework_content(_normalise_generated_practice_text(raw_result))
    ).strip()
    if not practice or practice.casefold() in {"none", "null", "undefined", "{}", "[]"}:
        logger.debug("[Review] _usable_generated_practice: empty/null content after normalisation")
        return "", []

    section_match = _PRACTICE_SECTION_RE.search(practice)
    question_area = practice[section_match.end():] if section_match else practice
    if not _NUMBERED_PRACTICE_QUESTION_RE.search(question_area):
        logger.debug(
            "[Review] _usable_generated_practice: no numbered questions found in question_area (len=%d, preview=%r)",
            len(question_area),
            question_area[:300],
        )
        return "", []

    questions = parse_public_questions(practice)
    if not questions:
        logger.debug(
            "[Review] _usable_generated_practice: parse_public_questions returned empty (practice preview=%r)",
            practice[:300],
        )
    return (practice, questions) if questions else ("", [])


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
        for item in raw_answers[:len(questions)]:
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
    """Remove full homework headers including Topic and (Set XXX) while preserving leading numbers."""
    if not text:
        return ""
    # Remove "Maths Homework - Year X - Topic (Set Y)" or similar prefixes
    # Matches: "Maths Homework - Year 2 - Fractions (Halves and Quarters) (Set 12) "
    # or "English Homework - Year 3 - Punctuation "
    pattern = r"^[a-zA-Z\s]+Homework\s*-\s*Year\s*\d+\s*-\s*.*?(?:\(Set\s*\d+\))?\s*"
    clean = re.sub(pattern,"", str(text), flags=re.IGNORECASE).strip()

    if "Homework" in clean:
        # \1 captures leading number like "1. "
        # Match through (Set XXX) if present, or up to the start of the question text
        pattern = r"^(\d+[\.\)]\s*)?[a-zA-Z\s]+Homework\s*-\s*Year\s*\d+\s*-\s*(?:.*?\(Set\s*\d+\)|.*?)\s*"
        clean = re.sub(pattern, r"\1", str(text), flags=re.IGNORECASE).strip()
        return clean or str(text)

    return clean or str(text)


def _table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    header = "| Result | Question | Your answer | Correct answer |\n|---|---|---|---|\n"
    body = []

    def markdown_cell(value: Any) -> str:
        # A generated multiple-choice question can contain blank lines between
        # its stem and options. Markdown treats those newlines as the end of the
        # table, so collapse all whitespace and escape column separators.
        return re.sub(r"\s+", " ", str(value or "")).strip().replace("|", "\\|")

    for row in rows:
        question = _clean_question_text(row["question"])
        values = [
            "✅" if row["is_correct"] else "❌",
            markdown_cell(question),
            markdown_cell(row["student_answer"]),
            markdown_cell(row["correct_answer"]),
        ]
        body.append("| " + " | ".join(values) + " |")
    return "\n\n## Homework Review Summary\n\n" + header + "\n".join(body) + "\n\n"


def _score_summary(rows: List[Dict[str, Any]]) -> str:
    correct = sum(1 for row in rows if row.get("is_correct"))
    return f"{correct}/{len(rows)} correct"


def _rag_prompt_context(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """Build bounded answer-key context for quick and detailed LLM reviews."""
    correct_summary: List[str] = []
    correct_items: List[str] = []
    wrong_items: List[str] = []
    for index, row in enumerate(rows, start=1):
        question = compact_text(_clean_question_text(row.get("question", "")), 260)
        pupil_answer = compact_text(row.get("student_answer", ""), 140)
        correct_answer = compact_text(row.get("correct_answer", ""), 140)
        correct_letter = compact_text(row.get("correct_letter", ""), 12)
        answer_label = (
            f"Option {correct_letter} — {correct_answer}"
            if correct_letter else correct_answer
        )
        if row.get("is_correct"):
            correct_summary.append(f"- Question {index}: correct — {question}")
            correct_items.append(
                f"Question {index}: {question}\n"
                f"Pupil answer: {pupil_answer}\n"
                f"Correct answer: {answer_label}"
            )
        else:
            item = (
                f"Question {index}: {question}\n"
                f"Pupil answer: {pupil_answer}\n"
                f"Correct answer: {answer_label}"
            )
            wrong_items.append(item)
    return {
        "score_summary": _score_summary(rows),
        "correct_work_summary": "\n".join(correct_summary) or "No correct answers this time.",
        "correct_answer_items": "\n\n".join(correct_items) or "No correct answers this time.",
        "wrong_answer_items": "\n\n".join(wrong_items) or "No incorrect answers.",
    }


_SOLUTION_METHOD_SECTION_RE = re.compile(
    r"(?ims)^\s*##\s+A Helpful Way to Solve This Question\s*\n"
    r".*?(?=^\s*##\s+|\Z)"
)


def _without_rendered_solution_methods(value: Any) -> str:
    """Remove locally rendered methods before a follow-up model call."""
    return _SOLUTION_METHOD_SECTION_RE.sub("", str(value or "")).strip()


def _method_questions(
    homework_content: str, rows: List[Dict[str, Any]]
) -> List[str]:
    if rows:
        return [
            compact_text(row.get("question"), 600)
            for row in rows
            if compact_text(row.get("question"), 600)
        ]
    parsed = parse_public_questions(homework_content)
    questions = [
        compact_text(item.get("question"), 600)
        for item in parsed
        if compact_text(item.get("question"), 600)
    ]
    if questions:
        return questions[:20]
    split = _split_homework_into_questions(homework_content)
    return [
        compact_text(item.get("content") or item.get("full_content"), 600)
        for item in split[:20]
        if compact_text(item.get("content") or item.get("full_content"), 600)
    ]


def _prepare_solution_methods(
    questions: List[str],
    rows: List[Dict[str, Any]],
    subject: str,
    year_group: int,
) -> tuple[Dict[str, str], Dict[str, str], List[Dict[str, str]]]:
    """Load cached methods and promote RAG methods without prompting an LLM."""
    from src import homework_rag

    initial: Dict[str, str] = {}
    available: Dict[str, str] = {}
    try:
        initial = homework_rag.load_solution_methods(
            questions, subject, year_group
        )
        available.update(initial)
    except Exception:
        logger.exception("Could not load saved solution methods")

    rag_records: List[Dict[str, str]] = []
    for index, question in enumerate(questions):
        method_id = homework_rag.solution_method_key(
            question, subject, year_group
        )
        if method_id in available or index >= len(rows):
            continue
        method = compact_text(rows[index].get("explanation"), 2_000)
        if method:
            rag_records.append({"question": question, "method": method})
            available[method_id] = method
    if rag_records:
        try:
            available.update(
                homework_rag.save_solution_methods(
                    rag_records, subject, year_group
                )
            )
        except Exception:
            logger.exception("Could not save RAG solution methods")

    missing = []
    for index, question in enumerate(questions, start=1):
        method_id = homework_rag.solution_method_key(
            question, subject, year_group
        )
        if method_id not in available:
            missing.append(
                {
                    "id": f"q{index}",
                    "question": question,
                    "method_id": method_id,
                }
            )
    return initial, available, missing


def _solution_method_prompt(missing: List[Dict[str, str]]) -> str:
    public_missing = [
        {"id": item["id"], "question": item["question"]}
        for item in missing
    ]
    status = (
        "Create one concise, age-appropriate method for each missing item."
        if public_missing
        else "No method is missing."
    )
    return (
        "\n\nSOLUTION METHOD OUTPUT\n"
        "Previously saved methods are rendered locally and are not present in "
        "this prompt. Do not invent or repeat a method unless it appears in "
        "MISSING_METHODS.\n"
        f"{status}\n"
        "MISSING_METHODS:\n"
        f"{json.dumps(public_missing, ensure_ascii=False)}\n"
        "Return JSON with feedback_markdown and solution_methods. Each solution "
        "method must use the supplied id and method_markdown. If there are no "
        "missing methods, solution_methods must be an empty list."
    )


def _parse_review_response(
    raw_response: str, missing: List[Dict[str, str]]
) -> tuple[str, List[Dict[str, str]]]:
    text = str(raw_response or "").strip()
    candidate = re.sub(
        r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.I
    ).strip()
    try:
        parsed = json.loads(candidate)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        feedback = str(
            parsed.get("feedback_markdown")
            or parsed.get("feedback")
            or ""
        ).strip()
        methods: List[Dict[str, str]] = []
        for item in parsed.get("solution_methods") or []:
            if not isinstance(item, dict):
                continue
            method_id = str(item.get("id") or "").strip()
            method = compact_text(
                item.get("method_markdown") or item.get("method"), 2_000
            )
            if method_id and method:
                methods.append({"id": method_id, "method": method})
        return feedback, methods

    section = _SOLUTION_METHOD_SECTION_RE.search(text)
    methods = []
    if section and missing:
        method = re.sub(
            r"(?ims)^\s*##\s+A Helpful Way to Solve This Question\s*\n",
            "",
            section.group(0),
        ).strip()
        if method:
            methods.append({"id": missing[0]["id"], "method": method})
    return _without_rendered_solution_methods(text), methods


def _finish_solution_methods(
    questions: List[str],
    subject: str,
    year_group: int,
    initial: Dict[str, str],
    available: Dict[str, str],
    missing: List[Dict[str, str]],
    returned: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    from src import homework_rag

    missing_by_id = {item["id"]: item for item in missing}
    new_records: List[Dict[str, str]] = []
    for item in returned:
        descriptor = missing_by_id.get(item.get("id"))
        method = compact_text(item.get("method"), 2_000)
        if descriptor and method:
            new_records.append(
                {"question": descriptor["question"], "method": method}
            )
            available[descriptor["method_id"]] = method
    if new_records:
        try:
            available.update(
                homework_rag.save_solution_methods(
                    new_records, subject, year_group
                )
            )
        except Exception:
            logger.exception("Could not save new solution methods")

    result = []
    for index, question in enumerate(questions, start=1):
        method_id = homework_rag.solution_method_key(
            question, subject, year_group
        )
        method = available.get(method_id)
        if method:
            result.append(
                {
                    "id": f"q{index}",
                    "method": method,
                    "from_cache": method_id in initial,
                }
            )
    return result


def _render_solution_methods(methods: List[Dict[str, Any]]) -> str:
    if not methods:
        return ""
    sections = ["\n\n## A Helpful Way to Solve This Question\n"]
    for index, item in enumerate(methods, start=1):
        if len(methods) > 1:
            sections.append(f"\n### Question {index}\n")
        sections.append(str(item.get("method") or "").strip())
        sections.append("\n")
    return "".join(sections).strip()


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
    quick_review: bool = False,
    uploaded_work: bool = False,
    is_tutor_mode: bool = False,
    homework_doc_id: Optional[str] = None,
    is_eleven_plus: bool = False,
    question_index: Optional[int] = None,
    llm_client: Any = None,
) -> Dict[str, Any]:
    """Review with an LLM, using trusted RAG answers as marking context when present."""
    from src.cache import review_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import (
        REVIEW_DETAIL_WITH_RAG_PROMPT,
        REVIEW_DETAIL_WITHOUT_RAG_PROMPT,
        REVIEW_QUICK_WITH_RAG_PROMPT,
        REVIEW_QUICK_WITHOUT_RAG_PROMPT,
        REVIEW_UPLOADED_HOMEWORK_PROMPT,
    )

    intervention = safety_result("review", student_answers)
    if intervention is not None:
        return intervention
    raw_profile = dict(profile or {})
    student_id = raw_profile.get("student_id", "anonymous")
    profile = _normalise_profile(raw_profile)
    budget = budget_review_inputs(homework_content, student_answers, profile)
    # Uploaded marking asks for concise/basic feedback and uses its dedicated
    # prompt. Tutor and year-round paths remain detailed even if a client sends
    # a conflicting quick-review flag.
    use_quick_model = bool(
        uploaded_work
        or (
            quick_review
            and not is_tutor_mode
            and not budget["profile"].get("plan_week")
        )
    )
    use_detail_model = not use_quick_model
    selected_model = DETAIL_REVIEW_MODEL if use_detail_model else QUICK_REVIEW_MODEL
    cache_key = stable_cache_key(
        (
            "review_uploaded_v1"
            if uploaded_work
            else ("review_detail_v6" if use_detail_model else "review_quick_v6")
        ),
        selected_model,
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
    if homework_doc_id and not uploaded_work:
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
    
    # Quick review with RAG answers: skip LLM call, return only table and score
    if quick_review and rows:
        correct_count = sum(1 for row in rows if row["is_correct"])
        attempted = len(rows)
        display_review = (
            _table(rows)
            + f"**Score: {correct_count}/{attempted}**\n"
        )
        result = {
            "success": True,
            "review": display_review,
            "llm_response": "",
            "solution_methods": [],
            "from_rag_answers": True,
            "score": float(correct_count),
            "max_score": attempted,
            "correct_count": correct_count,
            "attempted": attempted,
            "model_tier": "flash",
            "model_used": None,
            "llm_fallback": True,
            "display_review": display_review,
        }
        review_cache.set(cache_key, result)
        # 保存作业记录到 progress 数据库，供进度页面使用
        if not is_tutor_mode and student_id not in {None, "", "anonymous"} and not str(student_id).startswith("anon_"):
            try:
                from src.progress_db import save_homework_session
                save_homework_session(
                    student_id=str(student_id),
                    subject=subject,
                    year_group=int(profile.get("year_group", 3)),
                    homework_content=budget["homework_content"],
                    student_answers=budget["student_answers"],
                    score=float(correct_count),
                    review_text=display_review,
                    max_score=attempted,
                )
            except Exception:
                logger.exception("Could not save homework progress")
        return result

    year_group = int(profile.get("year_group", 3))
    if uploaded_work:
        # Basic uploaded-file marking does not need the detailed solution-method
        # persistence path. Skipping those extra database reads removes a common
        # source of latency and failure before the provider request.
        method_questions: List[str] = []
        initial_methods: Dict[str, str] = {}
        available_methods: Dict[str, str] = {}
        missing_methods: List[Dict[str, str]] = []
    else:
        method_questions = _method_questions(budget["homework_content"], rows)
        initial_methods, available_methods, missing_methods = (
            _prepare_solution_methods(
                method_questions, rows, subject, year_group
            )
        )

    correct_count = sum(1 for row in rows if row["is_correct"])
    attempted = len(rows)
    score: Optional[float] = float(correct_count) if rows else None
    max_score: Optional[int] = attempted if rows else None
    model_used: Optional[str] = None
    raw_feedback = ""
    llm_fallback = False

    if uploaded_work:
        if llm_client is None:
            raise RuntimeError("LLM client is not configured")
        submitted_work = (
            "Homework questions and extracted writing:\n"
            f"{budget['homework_content']}\n\n"
            "Pupil answers:\n"
            f"{budget['student_answers']}"
        )
        prompt = format_prompt(
            REVIEW_UPLOADED_HOMEWORK_PROMPT,
            student_profile=str(_prompt_profile(budget["profile"])),
            subject=compact_text(subject_display_name(subject), 80),
            homework=submitted_work,
            correct_answers_section=(
                "No separate trusted answer key was supplied. Work out only "
                "answers that can be checked confidently."
            ),
        )
        raw_feedback = _complete_review(
            llm_client,
            build_messages(prompt),
            model=selected_model,
            temperature=0.1,
            max_tokens=_token_limit(
                "UPLOADED_REVIEW_MAX_TOKENS", 1_600, maximum=4_000
            ),
            operation="uploaded_homework_review",
        )
        model_used = _resolved_model(llm_client, selected_model)
    elif rows:
        if llm_client is None:
            llm_fallback = True
            logger.warning(
                "LLM client is unavailable; returning trusted RAG marking for %s",
                homework_doc_id,
            )
        else:
            rag_context = _rag_prompt_context(rows)
            prompt = format_prompt(
                REVIEW_DETAIL_WITH_RAG_PROMPT if use_detail_model else REVIEW_QUICK_WITH_RAG_PROMPT,
                student_profile=str(_prompt_profile(budget["profile"])),
                subject=compact_text(subject_display_name(subject), 80),
                **rag_context,
            )
            prompt += _solution_method_prompt(missing_methods)
            try:
                raw_feedback = _complete_review(
                    llm_client,
                    build_messages(prompt),
                    model=selected_model,
                    temperature=0.2 if use_detail_model else 0.15,
                    max_tokens=(
                        _token_limit("DETAIL_REVIEW_MAX_TOKENS", 3000, maximum=8000)
                        if use_detail_model else
                        _token_limit("QUICK_REVIEW_MAX_TOKENS", 1000, maximum=5000)
                    ),
                    operation=(
                        "detail_review_with_rag"
                        if use_detail_model
                        else "quick_review_with_rag"
                    ),
                )
                model_used = _resolved_model(llm_client, selected_model)
            except Exception:
                llm_fallback = True
                logger.exception(
                    "LLM review failed; returning trusted RAG marking for %s",
                    homework_doc_id,
                )
    else:
        if llm_client is None:
            raise RuntimeError("LLM client is not configured")
        prompt = format_prompt(
            REVIEW_DETAIL_WITHOUT_RAG_PROMPT if use_detail_model else REVIEW_QUICK_WITHOUT_RAG_PROMPT,
            student_profile=str(_prompt_profile(budget["profile"])),
            subject=compact_text(subject_display_name(subject), 80),
            homework_content=budget["homework_content"],
            student_answer=budget["student_answers"],
        )
        prompt += _solution_method_prompt(missing_methods)
        raw_feedback = _complete_review(
            llm_client,
            build_messages(prompt),
            model=selected_model,
            temperature=0.15,
            max_tokens=(
                _token_limit("DETAIL_REVIEW_MAX_TOKENS", 3000, maximum=8000)
                if use_detail_model else
                _token_limit("QUICK_REVIEW_MAX_TOKENS", 1000, maximum=5000)
            ),
            operation=(
                "detail_review_no_rag"
                if use_detail_model
                else "quick_review_no_rag_all_answers"
            ),
        )
        model_used = _resolved_model(llm_client, selected_model)
    if not str(raw_feedback or "").strip():
        if not rows:
            raise RuntimeError("The AI provider returned an empty homework review")
        if not llm_fallback:
            logger.warning(
                "LLM returned an empty review; returning trusted RAG marking for %s",
                homework_doc_id,
            )
        llm_fallback = True
        feedback = RAG_REVIEW_FALLBACK_FEEDBACK
        returned_methods: List[Dict[str, str]] = []
    else:
        feedback, returned_methods = _parse_review_response(
            raw_feedback, missing_methods
        )
    solution_methods = (
        []
        if uploaded_work
        else _finish_solution_methods(
            method_questions,
            subject,
            year_group,
            initial_methods,
            available_methods,
            missing_methods,
            returned_methods,
        )
    )
    rendered_methods = _render_solution_methods(solution_methods)
    if rows:
        display_review = (
            _table(rows)
            + f"**Score: {correct_count}/{attempted}**\n\n"
            + feedback
        )
        review = display_review
    else:
        display_review = feedback
        review = feedback
        score, max_score = _extract_score(feedback)
    if rendered_methods:
        review = f"{review.rstrip()}\n\n{rendered_methods}".strip()

    result = {
        "success": True,
        "review": review,
        "llm_response": "" if llm_fallback else feedback,
        "solution_methods": solution_methods,
        "from_rag_answers": bool(rows),
        "score": score,
        "max_score": max_score,
        "correct_count": correct_count if rows else None,
        "attempted": attempted if rows else None,
        "model_tier": "plus" if use_detail_model else "flash",
        "model_used": model_used,
        "llm_fallback": llm_fallback,
    }
    if llm_fallback:
        # Tutor mode normally renders llm_response separately from locally
        # stored solution methods. Give it the table and score without
        # duplicating those methods.
        result["display_review"] = display_review
    else:
        # A provider outage should not pin the fallback in cache after the
        # provider recovers.
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
    """Run the detailed-check path using the configured detail model.

    With RAG, correct items are compact and wrong items carry full answer-key
    context. Without RAG, the detail model receives all questions and answers.
    """
    from src.cache import explain_cache
    from src.llm_client import build_messages, format_prompt
    from src.prompts import REVIEW_DETAIL_WITH_RAG_PROMPT, REVIEW_DETAIL_WITHOUT_RAG_PROMPT

    if llm_client is None:
        raise RuntimeError("LLM client is not configured")
    intervention = safety_result("explanation", student_answers)
    if intervention is not None:
        return intervention
    raw_profile = dict(profile or {})
    profile = _normalise_profile(raw_profile)
    budget = budget_review_inputs(
        homework_content,
        student_answers,
        profile,
        _without_rendered_solution_methods(review_feedback),
    )
    cache_key = stable_cache_key(
        "review_detail_v6",
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
                is_tutor_mode=question_index is not None,
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
            **_rag_prompt_context(rows),
        )
        try:
            ai_explanation = _complete_review(
                llm_client,
                build_messages(prompt),
                model=DETAIL_REVIEW_MODEL,
                temperature=0.2,
                max_tokens=_token_limit("DETAIL_REVIEW_MAX_TOKENS", 3000, maximum=8000),
                operation="detail_explanation_with_rag",
            )
        except Exception:
            # The deterministic RAG marking is still useful even if the
            # explanation provider is temporarily unavailable.
            logger.exception("[Review] detail explanation provider failed; using trusted RAG explanation")
            ai_explanation = (
                "The detailed AI explanation is temporarily unavailable, but "
                "your answers and the trusted marking above are ready. "
                "Review the method shown for each question and try the next step."
            )
        if not str(ai_explanation or "").strip():
            ai_explanation = (
                "The detailed AI explanation is temporarily unavailable, but "
                "your answers and the trusted marking above are ready."
            )
        local_methods = [
            {
                "id": f"q{index}",
                "method": compact_text(row.get("explanation"), 2_000),
                "from_cache": True,
            }
            for index, row in enumerate(rows, start=1)
            if compact_text(row.get("explanation"), 2_000)
        ]
        explanation = (
            _table(rows)
            + f"**Score: {correct_count}/{len(rows)}**\n\n"
            + ai_explanation
        )
        rendered_methods = _render_solution_methods(local_methods)
        if rendered_methods:
            explanation = (
                f"{explanation.rstrip()}\n\n{rendered_methods}"
            )
        score = float(correct_count)
        max_score = len(rows)
    else:
        prompt = format_prompt(
            REVIEW_DETAIL_WITHOUT_RAG_PROMPT,
            student_profile=str(_prompt_profile(budget["profile"])),
            subject=compact_text(subject_display_name(subject), 80),
            homework_content=budget["homework_content"],
            student_answer=budget["student_answers"],
        )
        try:
            explanation = _complete_review(
                llm_client,
                build_messages(prompt),
                model=DETAIL_REVIEW_MODEL,
                temperature=0.2,
                max_tokens=_token_limit("DETAIL_REVIEW_MAX_TOKENS", 3000, maximum=8000),
                operation="detail_review_no_rag_all_answers",
            )
        except Exception:
            logger.exception("[Review] detail explanation provider failed")
            return {
                "success": False,
                "error": "The detailed explanation service is temporarily unavailable. Please try again in a moment.",
                "llm_no_response": True,
                "model_tier": "plus",
                "model_used": _resolved_model(llm_client, DETAIL_REVIEW_MODEL),
            }
        if not str(explanation or "").strip():
            return {
                "success": False,
                "error": "The detailed explanation service returned no explanation. Please try again in a moment.",
                "llm_no_response": True,
                "model_tier": "plus",
                "model_used": _resolved_model(llm_client, DETAIL_REVIEW_MODEL),
            }
        score, max_score = _extract_score(explanation)

    model_used = _resolved_model(llm_client, DETAIL_REVIEW_MODEL)
    result = {
        "success": True,
        "explanation": explanation,
        "from_rag_answers": bool(rows),
        "score": score,
        "max_score": max_score,
        "model_tier": "plus",
        "model_used": model_used,
    }
    explain_cache.set(cache_key, result)
    return result

def improve_practice(
    homework_content: str,
    student_answers: str,
    subject: str,
    profile: Optional[dict] = None,
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
    budget = budget_review_inputs(
        homework_content,
        student_answers,
        profile,
    )
    cache_key = stable_cache_key(
        "practice_v4",
        subject,
        budget,
        homework_doc_id,
        question_index,
    )
    cached = practice_cache.get(cache_key)
    if cached:
        cached_practice, cached_questions = _usable_generated_practice(cached)
        if cached_practice:
            return {
                "success": True,
                "practice": cached_practice,
                "questions": cached_questions,
                "from_cache": True,
            }

    # 默认用原始作业和学生答案作为上下文，确保 LLM 始终有足够信息生成练习
    wrong_questions_section = (
        "## Questions that need practice\n"
        f"{compact_text(budget['homework_content'], 2_000)}\n"
        f"Student answers: {compact_text(budget['student_answers'], 1_000)}\n"
    )
    correct_answers_section = ""
    if homework_doc_id:
        try:
            raw_answers = _load_rag_answers(homework_doc_id, is_eleven_plus)
            pairs = _pair_rag_answers(
                raw_answers,
                budget["homework_content"],
                subject,
                is_tutor_mode=question_index is not None,
                question_index=question_index,
            )
            rows = _mark_rows(pairs, budget["student_answers"], subject)
            if rows:
                wrong_rows = [r for r in rows if not r["is_correct"]]
                if wrong_rows:
                    wrong_questions_section = "## Questions the student got wrong\n"
                    for i, r in enumerate(wrong_rows, 1):
                        wrong_questions_section += f"{i}. {r['question']} (student answered: {r['student_answer']})\n"
                correct_answers_section = "## Correct Answers for Reference\n"
                for i, r in enumerate(rows, 1):
                    correct_answers_section += (
                        f"Question {i}: {r['question']}\n"
                        f"Correct Answer: {r['correct_answer']}\n"
                    )
        except Exception:
            logger.exception("RAG answer lookup failed in improve_practice for %s", homework_doc_id)

    prompt = format_prompt(
        IMPROVE_PRACTICE_PROMPT,
        subject=compact_text(subject_display_name(subject), 80),
        year_group=budget["profile"].get("year_group", 3),
        age=budget["profile"].get("age", 7),
        wrong_questions_section=compact_text(wrong_questions_section, 2_000),
        correct_answers_section=compact_text(correct_answers_section, 4_000),
    )
    messages = build_messages(prompt)
    raw_result = _complete_review(
        llm_client,
        messages,
        model=DETAIL_REVIEW_MODEL,
        temperature=0.25,
        max_tokens=_token_limit("PRACTICE_MAX_TOKENS", 3000, maximum=5000),
        operation="targeted_practice",
    )
    practice, questions = _usable_generated_practice(raw_result)

    # A successful provider call can still return prose that is not renderable
    # (for example a model may omit the numbered-question section). Retry once
    # with a short, explicit output contract before reporting failure.
    if not practice:
        retry_prompt = prompt + """\n\nFINAL OUTPUT CHECK:
Return ONLY these sections:
## Similar Practice Questions
1. [new question]
2. [new question]
3. [new question]
4. [new question]
5. [slightly harder challenge question]

## Quick Revision Notes
- [short note]

## Tips and Tricks
- [short tip]

Do not use JSON, code fences, tables, or prose before question 1. Number every
practice question as 1., 2., 3., 4., 5. Keep answer choices on separate lines.
"""
        try:
            raw_result = _complete_review(
                llm_client,
                build_messages(retry_prompt),
                model=DETAIL_REVIEW_MODEL,
                temperature=0.15,
                max_tokens=_token_limit("PRACTICE_MAX_TOKENS", 3000, maximum=5000),
                operation="targeted_practice_retry",
            )
            practice, questions = _usable_generated_practice(raw_result)
        except Exception:
            logger.exception("[Review] targeted_practice retry failed")
    if not practice:
        preview = str(raw_result or "")[:500]
        logger.warning(
            "[Review] targeted_practice returned no usable practice (raw=%r chars, preview=%r)",
            len(str(raw_result or "")),
            preview,
        )
        return {
            "success": False,
            "error": PRACTICE_GENERATION_UNAVAILABLE_MESSAGE,
            "llm_no_response": True,
        }
    practice_cache.set(cache_key, practice)
    return {"success": True, "practice": practice, "questions": questions}
