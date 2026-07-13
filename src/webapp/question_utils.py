from __future__ import annotations

import csv
import io
import logging
import re
import uuid
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_QUESTION_START_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(?:\*\*)?"
    r"(?:(?:homework\s+)?question|q)?\s*\(?(\d+)\)?\s*"
    r"(?:[\).:\-]|(?:\*\*)?\s*$)\s*(?:\*\*)?\s*(.*?)\s*$",
    re.IGNORECASE,
)
_OPTION_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?\(?([A-Ha-h])\)?\s*"
    r"[\).:\-]\s*(?:\*\*)?\s*(.+?)\s*$"
)
_OPTIONS_LINE_RE = re.compile(r"^\s*(?:\*\*)?options?(?:\*\*)?\s*:\s*(.*?)\s*$", re.I)
_PRIVATE_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?"
    r"(?:answers?|correct\s+answers?|answer\s+key|solutions?|explanations?|"
    r"worked\s+(?:answers?|solutions?|explanations?))"
    r"(?:\*\*)?\s*:?[\s\-]*$",
    re.I,
)
_PRIVATE_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(?:correct\s+answer|answer|solution|explanation|worked\s+(?:answer|solution|explanation)|"
    r"coaching\s+(?:strategy|tip)|(?:helpful|exam|11\+)?\s*tip)"
    r"(?:\*\*)?\s*:",
    re.I,
)
_GENERIC_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?"
    r"(?:questions?|practice\s+questions?|homework(?:\s+set)?|tasks?)"
    r"(?:\*\*)?\s*:?[\s\-]*$",
    re.I,
)
_CONTEXT_TRANSITION_RE = re.compile(
    r"^(?:read|use|look at|study|refer to|for questions?\b|passage\b|the passage\b|"
    r"read the (?:second|following|next))",
    re.I,
)


def _clean_public_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^\s*#{1,6}\s+", "", text)
    text = re.sub(r"^\s*\*\*(.*?)\*\*\s*$", r"\1", text)
    return text.strip()


def _strip_private_answer_sections(content: str) -> str:
    """Remove answer/solution sections before building learner-facing questions.

    Some legacy or LLM-created 11+ worksheets contain ``ANSWERS`` after the
    student questions. Correct material must never be copied into the public
    question model used by the browser.
    """
    kept: List[str] = []
    for line in str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _PRIVATE_SECTION_HEADING_RE.match(line):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def _normalise_inline_options(content: str) -> str:
    """Put compact ``A) ... B) ...`` choices onto separate lines.

    The replacement is intentionally limited to A-H labels followed by normal
    option punctuation, so ordinary prose is left alone.
    """
    text = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(
        r"(?<=\S)[ \t]+(?=(?:[-*][ \t]+)?(?:\*\*)?\(?[A-Ha-h]\)?[\).:]\s+)",
        "\n",
        text,
    )


def _parse_inline_options(value: str) -> List[Dict[str, str]]:
    raw = str(value or "").strip()
    if not raw:
        return []
    try:
        values = next(csv.reader(io.StringIO(raw), skipinitialspace=True))
    except (csv.Error, StopIteration):
        values = [part.strip() for part in raw.split(",")]
    values = [item.strip() for item in values if item and item.strip()]
    if not 2 <= len(values) <= 8:
        return []
    return [
        {"label": chr(65 + index), "text": _clean_public_text(item)}
        for index, item in enumerate(values)
    ]


def _question_blocks(content: str) -> tuple[str, List[tuple[int, str]]]:
    text = _normalise_inline_options(_strip_private_answer_sections(content))
    lines = text.split("\n")
    starts: List[tuple[int, int, str]] = []
    for line_index, line in enumerate(lines):
        match = _QUESTION_START_RE.match(line)
        if match:
            starts.append((line_index, int(match.group(1)), _clean_public_text(match.group(2))))

    if not starts:
        cleaned_lines = [line for line in lines if not _GENERIC_HEADING_RE.match(line)]
        fallback = "\n".join(cleaned_lines).strip()
        return "", ([(1, fallback)] if fallback else [])

    intro_lines = [
        line for line in lines[:starts[0][0]]
        if line.strip() and not _GENERIC_HEADING_RE.match(line)
    ]
    intro = "\n".join(intro_lines).strip()

    blocks: List[tuple[int, str]] = []
    for index, (start_line, number, first_line) in enumerate(starts):
        end_line = starts[index + 1][0] if index + 1 < len(starts) else len(lines)
        body_lines = []
        if first_line:
            body_lines.append(first_line)
        body_lines.extend(lines[start_line + 1:end_line])
        body = "\n".join(body_lines).strip()
        if body:
            blocks.append((number, body))
    return intro, blocks


def _parse_question_block(number: int, body: str) -> Dict[str, Any] | None:
    stem_lines: List[str] = []
    options: List[Dict[str, str]] = []
    trailing_lines: List[str] = []
    in_options = False
    in_trailing_context = False
    gap_after_options = False

    for raw_line in str(body or "").split("\n"):
        line = raw_line.strip()
        if not line:
            if in_options:
                gap_after_options = True
            continue
        if _PRIVATE_LINE_RE.match(line) or _PRIVATE_SECTION_HEADING_RE.match(line):
            break

        if in_trailing_context:
            trailing_lines.append(_clean_public_text(line))
            continue

        options_line = _OPTIONS_LINE_RE.match(line)
        if options_line:
            in_options = True
            inline = _parse_inline_options(options_line.group(1))
            if inline:
                options.extend(inline)
            gap_after_options = False
            continue

        option_match = _OPTION_RE.match(line)
        if option_match:
            in_options = True
            options.append(
                {
                    "label": option_match.group(1).upper(),
                    "text": _clean_public_text(option_match.group(2)),
                }
            )
            gap_after_options = False
            continue

        cleaned = _clean_public_text(line)
        if not cleaned or _GENERIC_HEADING_RE.match(cleaned):
            continue
        if in_options and options:
            is_context = gap_after_options or bool(_CONTEXT_TRANSITION_RE.match(cleaned))
            if is_context:
                in_trailing_context = True
                trailing_lines.append(cleaned)
            else:
                # Wrapped option text is normally indented and directly follows
                # the option with no empty line.
                options[-1]["text"] = f"{options[-1]['text']} {cleaned}".strip()
        else:
            stem_lines.append(cleaned)

    stem = "\n".join(stem_lines).strip()
    options = [item for item in options if item.get("text")]
    if not stem:
        return None
    result: Dict[str, Any] = {
        "number": int(number),
        "question": stem,
        "response_type": "single_choice" if len(options) >= 2 else "text",
        "options": options if len(options) >= 2 else [],
    }
    trailing_context = "\n".join(item for item in trailing_lines if item).strip()
    if trailing_context:
        result["_trailing_context"] = trailing_context
    return result


def parse_public_questions(homework_content: str) -> List[Dict[str, Any]]:
    """Return an answer-free, mixed question model for the browser.

    Each record is either ``single_choice`` with labelled options, or ``text``.
    Shared passages/instructions are carried in ``context`` on the first
    question that needs them. Correct answers, explanations and tips are never
    included.
    """
    intro, blocks = _question_blocks(homework_content)
    questions: List[Dict[str, Any]] = []
    pending_context = intro
    for number, body in blocks:
        parsed = _parse_question_block(number, body)
        if not parsed:
            continue
        if pending_context:
            parsed["context"] = pending_context
        pending_context = str(parsed.pop("_trailing_context", "") or "").strip()
        questions.append(parsed)
    return questions


def _split_homework_into_questions(homework_content: str, subject: str) -> List[Dict[str, Any]]:
    """Split homework into tutor-mode items while preserving choice metadata."""
    public_questions = parse_public_questions(homework_content)
    if public_questions:
        result: List[Dict[str, Any]] = []
        for index, question in enumerate(public_questions):
            number = int(question.get("number") or index + 1)
            lines: List[str] = []
            if question.get("context"):
                lines.append(str(question["context"]).strip())
            lines.append(str(question.get("question") or "").strip())
            for option in question.get("options") or []:
                lines.append(f"{option['label']}) {option['text']}")
            content = "\n".join(line for line in lines if line).strip()
            full_content = f"{number}. {content}".strip()
            result.append(
                {
                    "subject": subject,
                    "content": content,
                    "full_content": full_content,
                    "original_full_content": homework_content,
                    "question_id": f"{subject}_{uuid.uuid4().hex[:8]}_{index + 1}",
                    "questions": [question],
                    "response_type": question.get("response_type", "text"),
                    "options": question.get("options", []),
                    "question_text": question.get("question", ""),
                }
            )
        return result

    content = str(homework_content or "").strip().replace("\r\n", "\n")
    if not content:
        return []
    return [
        {
            "subject": subject,
            "content": content,
            "full_content": content,
            "original_full_content": content,
            "question_id": f"{subject}_{uuid.uuid4().hex[:8]}_1",
            "questions": [],
            "response_type": "text",
            "options": [],
            "question_text": content,
        }
    ]


def _parse_student_answers_to_map(
    student_answers_text: str,
    target_subject: str,
    rag_questions: List[str],
) -> Dict[str, str]:
    """Map numbered or positional learner answers to known RAG questions."""
    answer_map: Dict[str, str] = {}
    start_marker = f"--- {target_subject} ---"
    start_index = student_answers_text.find(start_marker)

    if start_index == -1:
        subject_block = student_answers_text.strip()
    else:
        content_after_marker = student_answers_text[start_index + len(start_marker):].strip()
        next_marker = re.search(r"--- [^-\n]+ ---", content_after_marker)
        subject_block = (
            content_after_marker[:next_marker.start()].strip()
            if next_marker else content_after_marker.strip()
        )

    if not subject_block:
        return {}

    lines = [line.strip() for line in subject_block.split("\n") if line.strip()]
    rag_q_num_to_text: Dict[str, str] = {}
    for q_text in rag_questions:
        match = re.match(r"^\s*(\d+)[\).]\s*", q_text)
        if match:
            rag_q_num_to_text[match.group(1)] = q_text

    numbered: Dict[str, str] = {}
    current_number: str | None = None
    current_parts: List[str] = []
    for line in lines:
        match = re.match(r"^\s*(\d+)[\).]\s*(.*)", line)
        if match:
            if current_number is not None and current_parts and current_number in rag_q_num_to_text:
                numbered[rag_q_num_to_text[current_number]] = " ".join(current_parts).strip()
            current_number = match.group(1)
            current_parts = [match.group(2)]
        elif current_number is not None:
            current_parts.append(line)
    if current_number is not None and current_parts and current_number in rag_q_num_to_text:
        numbered[rag_q_num_to_text[current_number]] = " ".join(current_parts).strip()
    if numbered:
        return numbered

    for index in range(min(len(lines), len(rag_questions))):
        answer_map[rag_questions[index]] = lines[index]
    if not answer_map and len(rag_questions) == 1:
        answer_map[rag_questions[0]] = subject_block.strip()
    return answer_map
