#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
作业生成模块

负责为 UK 小学生生成各科作业，包括 RAG 检索、新作业生成、科目提取等。
已移除 LangChain 依赖，使用轻量级 LLMClient 和缓存。
支持多线程并行生成多科目作业，显著降低延迟。
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Tuple

from src.llm_client import LLMClient, format_prompt, build_messages
from src.cache import homework_cache, subject_extraction_cache, make_cache_key
from src.models import (
    UK_PRIMARY_SUBJECTS, KEY_STAGES, get_homework_time_by_age,
    YEAR_GROUP_AGE, is_eleven_plus_subject as is_known_eleven_plus_subject,
    subject_display_name,
)
from src.homework_rag import (
    store_homework, search_homework, search_homework_by_metadata,
    get_student_previous_topics, get_homework_rag_store,
)
from src.elevenplus_rag import (
    store_homework as elevenplus_store_homework,
    search_homework as elevenplus_search_homework,
    search_homework_by_metadata as elevenplus_search_homework_by_metadata,
    get_student_previous_topics as elevenplus_get_student_previous_topics,
    get_homework_questions as elevenplus_get_homework_questions,
    format_questions_only as elevenplus_format_questions_only,
)
from src.prompts import (
    HOMEWORK_PROMPT, SUBJECT_EXTRACTION_PROMPT, HOMEWORK_PROMPT_11PLUS,
    RAG_PROMPT_11PLUS,
)
from src.webapp.homework_assignment_store import get_assignment_store
from src.webapp.prompt_budget import compact_profile, compact_text
from src.webapp.question_utils import parse_public_questions, _split_homework_into_questions


logger = logging.getLogger(__name__)


def _is_eleven_plus_subject(subject: str) -> bool:
    """Recognise ordinary and 52-week 11+ subject identifiers."""
    return is_known_eleven_plus_subject(subject)



_RAG_STOP_WORDS = {
    "and", "the", "for", "with", "from", "year", "age", "practice", "homework",
    "learn", "learning", "help", "need", "needs", "student", "questions", "question",
}


def _search_terms(values: List[str]) -> set[str]:
    text = " ".join(str(value or "") for value in values).casefold()
    return {
        token for token in re.findall(r"[a-z0-9%]+", text)
        if len(token) > 2 and token not in _RAG_STOP_WORDS
    }


def _rank_rag_candidates(candidates: List[Dict[str, Any]], goals: List[str]) -> List[Dict[str, Any]]:
    """Rank exact year/subject matches locally, without an embedding request."""
    terms = _search_terms(goals)
    if not terms:
        return candidates

    def score(item: Dict[str, Any]) -> tuple[int, int]:
        metadata = item.get("metadata") or {}
        haystack = " ".join(
            [
                str(metadata.get("topic") or ""),
                str(metadata.get("learning_goal") or ""),
                str(metadata.get("content_type") or ""),
                str(item.get("content") or "")[:2_000],
            ]
        ).casefold()
        matched = sum(1 for term in terms if term in haystack)
        return matched, -len(haystack)

    return sorted(candidates, key=score, reverse=True)


def _normalise_answer_records(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    records: List[Dict[str, str]] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            question = str(item.get("question") or item.get("question_text") or "").strip()
            answer = str(item.get("answer") or item.get("correct_answer") or "").strip()
            explanation = str(item.get("explanation") or "").strip()
            correct_letter = str(item.get("correct_letter") or item.get("letter") or "").strip().upper()
        else:
            question = ""
            answer = str(item or "").strip()
            explanation = ""
            correct_letter = ""
        if not answer:
            continue
        record = {"question": question or f"Question {index}", "answer": answer}
        if explanation:
            record["explanation"] = explanation
        if correct_letter:
            record["correct_letter"] = correct_letter
        records.append(record)
    return records


def _extract_generated_payload(raw_result: str, subject: str) -> Tuple[str, List[Dict[str, str]]]:
    """Separate the public worksheet from its private answer key.

    New prompts request JSON. The section parser keeps older/local models safe by
    stripping an ANSWERS heading before anything is returned to the browser.
    """
    text = str(raw_result or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        payload = None

    if isinstance(payload, dict):
        homework = str(payload.get("homework") or payload.get("worksheet") or payload.get("content") or "").strip()
        answers = _normalise_answer_records(
            payload.get("correct_answers") or payload.get("answers") or payload.get("answer_key")
        )
        if homework:
            return homework, answers

    parts = re.split(r"(?im)^\s*#{0,6}\s*ANSWERS?\s*:?[ \t]*$", text, maxsplit=1)
    if len(parts) == 1:
        return text, []

    homework = parts[0].strip()
    private = parts[1]
    answer_block = re.split(
        r"(?im)^\s*#{0,6}\s*(?:EXPLANATIONS?|WORKED SOLUTIONS?|BONUS)\s*:?[ \t]*$",
        private,
        maxsplit=1,
    )[0]
    answer_map: Dict[int, str] = {}
    for match in re.finditer(r"(?m)^\s*(\d+)[.)]\s*(.+?)\s*$", answer_block):
        answer_map[int(match.group(1))] = match.group(2).strip()

    questions = _split_homework_into_questions(homework, subject)
    answers: List[Dict[str, str]] = []
    for index, question in enumerate(questions, start=1):
        answer = answer_map.get(index)
        if answer:
            answers.append({
                "question": str(question.get("full_content") or question.get("content") or f"Question {index}"),
                "answer": answer,
            })
    return homework, answers


def generate_homework_for_subject(
    student_profile: Dict[str, Any],
    subject: str,
    llm: LLMClient,
    is_eleven_plus: bool = False,
) -> tuple:
    """Return unseen exact RAG homework first; call the LLM only on a RAG miss."""
    if is_eleven_plus:
        year_group = 6
        age = 11
    else:
        year_group = int(student_profile.get("year_group", 6))
        age = int(student_profile.get("age") or YEAR_GROUP_AGE.get(year_group, 11))

    homework_info = get_homework_time_by_age(year_group)
    homework_time = homework_info["daily_homework_minutes"]
    learner_key = str(student_profile.get("student_id") or "anonymous")[:100]
    try:
        requested_week = int(student_profile.get("plan_week") or 0)
        plan_week = requested_week if 1 <= requested_week <= 52 else 0
    except (TypeError, ValueError):
        plan_week = 0

    subject_label = subject_display_name(subject)
    content_kind = (
        f"elevenplus_week_{plan_week:02d}"
        if is_eleven_plus and plan_week
        else ("elevenplus" if is_eleven_plus else "primary")
    )
    if is_eleven_plus:
        store_func = elevenplus_store_homework
        metadata_search = elevenplus_search_homework_by_metadata
    else:
        store_func = store_homework
        metadata_search = search_homework_by_metadata

    learning_goals = [compact_text(item, 120) for item in student_profile.get("learning_goals", []) if item]
    weak_areas = [compact_text(item, 120) for item in student_profile.get("weak_areas", []) if item]
    assignment_store = get_assignment_store()

    try:
        if is_eleven_plus and plan_week:
            candidates = metadata_search(
                year_group=year_group,
                subject=subject,
                week_num=plan_week,
                content_type="year_round",
                k=20,
            )
        else:
            # Exact metadata lookup is the fastest and most reliable match. It
            # deliberately avoids loading the embedding model on the hot path.
            # Exclude all IDs already assigned to this learner in SQL. The old
            # implementation inspected only the newest 50 rows, so it could
            # report a false miss even while hundreds of older unseen rows
            # remained in the RAG library.
            seen_ids = assignment_store.seen_doc_ids(
                learner_key,
                subject=subject,
                year_group=year_group,
                content_kind=content_kind,
                limit=20_000,
            )
            candidates = metadata_search(
                year_group=year_group,
                subject=subject,
                k=50,
                exclude_ids=seen_ids,
            )
            candidates = _rank_rag_candidates(candidates, learning_goals + weak_areas)

        candidate_by_id = {
            str(item.get("doc_id")): item for item in candidates or [] if item.get("doc_id")
        }
        claimed_id = assignment_store.claim_first_unseen(
            learner_key,
            list(candidate_by_id),
            subject=subject,
            year_group=year_group,
            content_kind=content_kind,
        )
        if claimed_id:
            selected = candidate_by_id[claimed_id]
            content = str(selected.get("content") or "").strip()
            if content:
                logger.info(
                    "[RAG] Assigned %s homework for Year %d, week=%s, doc_id=%s",
                    subject, year_group, plan_week or "general", claimed_id,
                )
                return content, claimed_id, True
        if is_eleven_plus:
            logger.info("[RAG] No unseen exact candidate for %s Year %d", subject, year_group)
        else:
            total_exact = get_homework_rag_store().store.count_by_metadata(
                {"year_group": year_group, "subject": subject}
            )
            logger.info(
                "[RAG] No unseen exact candidate for %s Year %d "
                "(exact_in_database=%d, already_seen=%d, database=%s)",
                subject,
                year_group,
                total_exact,
                len(seen_ids),
                get_homework_rag_store().store.database_target,
            )
    except Exception:
        logger.exception("[RAG] Homework lookup failed for %s Year %d", subject, year_group)

    # True RAG miss. Keep the model input small and exclude identifiers/free
    # profile text. The one generation call also creates a private answer key,
    # so future marking can remain deterministic and token-free.
    prompt_profile = compact_profile(student_profile)
    prompt_profile.pop("student_id", None)
    prompt_template = RAG_PROMPT_11PLUS if is_eleven_plus else HOMEWORK_PROMPT
    prompt_text = format_prompt(
        prompt_template,
        student_profile=json.dumps(prompt_profile, ensure_ascii=False, separators=(",", ":")),
        subject=compact_text(subject_label, 80),
        homework_time=homework_time,
        year_group=year_group,
        age=age,
        previous_topics="",
        index=1,
    )
    raw_result = str(
        llm.complete(
            build_messages(prompt_text),
            temperature=0.25,
            max_tokens=1800 if is_eleven_plus else 1200,
        )
    ).strip()
    if not raw_result:
        raise RuntimeError("The homework generator returned an empty response")
    result, correct_answers = _extract_generated_payload(raw_result, subject)
    if not result:
        raise RuntimeError("The homework generator returned no public questions")

    doc_id = None
    try:
        store_kwargs = {
            "homework_content": result,
            "year_group": year_group,
            "subject": subject,
            "homework_minutes": homework_time,
            "key_stage": KEY_STAGES.get(year_group, "KS2"),
            "english_level": student_profile.get("english_level"),
            "student_id": None,
            "correct_answers": correct_answers or None,
            "age": age,
        }
        if is_eleven_plus and plan_week:
            store_kwargs.update(
                {
                    "week_num": plan_week,
                    "content_type": "year_round",
                    "topic": learning_goals[0] if learning_goals else f"Week {plan_week}",
                }
            )
        doc_id = store_func(**store_kwargs)
        assignment_store.record(
            learner_key, doc_id, subject=subject, year_group=year_group, content_kind=content_kind
        )
    except Exception:
        logger.exception("[RAG] Could not store generated %s homework", subject)

    return result, doc_id, False

def extract_subjects_from_prompt(user_input: str, llm: LLMClient) -> List[str]:
    """从用户提示词中提取科目（带缓存）

    Args:
        user_input: 用户的自然语言输入
        llm: LLMClient 实例

    Returns:
        提取到的科目列表
    """
    source_text = " ".join(user_input) if isinstance(user_input, (list, tuple)) else str(user_input or "")
    safe_source_text = compact_text(source_text, 2_000)
    cache_key = make_cache_key("subject_extract", safe_source_text)
    cached = subject_extraction_cache.get(cache_key)
    if cached is not None:
        logger.info("[Cache] 命中科目提取缓存")
        return cached

    folded = safe_source_text.casefold()
    aliases = {
        "Maths": ("maths", "math", "mathematics"),
        "English": ("english", "reading", "writing", "spelling", "grammar"),
        "Science": ("science",),
        "Computing": ("computing", "computer", "coding"),
        "History": ("history",),
        "Geography": ("geography",),
        "Art and Design": ("art", "drawing", "design"),
        "Music": ("music",),
        "Physical Education": ("physical education", "p.e.", " pe ", "sport"),
        "Languages": ("language", "french", "spanish", "german"),
    }
    local_subjects = [
        subject for subject in UK_PRIMARY_SUBJECTS
        if any(alias in folded for alias in aliases.get(subject, (subject.casefold(),)))
    ]
    if local_subjects:
        subject_extraction_cache.set(cache_key, local_subjects)
        return local_subjects

    prompt_text = format_prompt(
        SUBJECT_EXTRACTION_PROMPT,
        available_subjects=", ".join(UK_PRIMARY_SUBJECTS),
        user_input=safe_source_text,
    )
    messages = build_messages(prompt_text)
    result = llm.complete_json(messages, temperature=0, max_tokens=128)

    if isinstance(result, list):
        subjects = [s for s in result if s in UK_PRIMARY_SUBJECTS]
    else:
        subjects = []

    # 写入缓存
    subject_extraction_cache.set(cache_key, subjects)
    return subjects


def distribute_subjects_to_days(subjects: List[str], num_days: int) -> Dict[int, List[str]]:
    """将科目分配到指定天数中，每天最多2个科目

    Args:
        subjects: 科目列表
        num_days: 天数

    Returns:
        {day_number: [subjects]}
    """
    assignments = {day: [] for day in range(1, num_days + 1)}

    if not subjects:
        return assignments

    # 轮流分配科目到每一天
    for i, subject in enumerate(subjects):
        day = (i % num_days) + 1
        if len(assignments[day]) < 2:
            assignments[day].append(subject)
        else:
            # 如果当天已有2个科目，找下一个有空位的日期
            for d in range(1, num_days + 1):
                if len(assignments[d]) < 2:
                    assignments[d].append(subject)
                    break

    return assignments


def generate_multiday_homework(student_profile: Dict[str, Any], subjects: List[str], num_days: int, llm: LLMClient) -> Dict[int, Dict[str, str]]:
    """生成指定天数的作业，每天最多两个科目

    Args:
        student_profile: 学生信息字典
        subjects: 科目列表
        num_days: 天数
        llm: LLMClient 实例

    Returns:
        {day_number: {subject: homework_content}}
    """
    homework_plan = {}

    # 将科目分配到5天中，每天最多2个科目
    day_assignments = distribute_subjects_to_days(subjects, num_days)

    for day, day_subjects in day_assignments.items():
        day_homework = {}
        for subject in day_subjects:
            logger.info("[Homework] Day %d: Generating homework for %s...", day, subject)
            homework, _, _ = generate_homework_for_subject(student_profile, subject, llm)
            day_homework[subject] = homework
        homework_plan[day] = day_homework

    return homework_plan


def _public_homework_result(
    *,
    subject: str,
    content: str,
    doc_id: Any,
    from_rag: bool,
    student_profile: Dict[str, Any],
    is_eleven_plus: bool,
) -> Dict[str, Any]:
    """Build an API result and remove answer material from weekly practice."""
    result: Dict[str, Any] = {
        "subject": subject,
        "subject_label": subject_display_name(subject),
        "content": content,
        "doc_id": doc_id,
        "from_rag": from_rag,
    }

    # Every generated worksheet receives the same answer-free question model.
    # The browser uses it to render explicit options as single-choice controls
    # for Years 1-6 and all 11+ modes. Text questions remain text responses.
    public_questions = parse_public_questions(content)
    if public_questions:
        result["questions"] = public_questions
    try:
        plan_week = int(student_profile.get("plan_week") or 0)
    except (TypeError, ValueError):
        plan_week = 0
    if is_eleven_plus and 1 <= plan_week <= 52:
        questions = elevenplus_get_homework_questions(doc_id, content)
        if questions:
            result["questions"] = questions
            result["content"] = elevenplus_format_questions_only(questions)
        result["plan_week"] = plan_week
        result["content_type"] = "year_round"
    return result


def generate_homework_parallel(
    student_profile: Dict[str, Any],
    subjects: List[str],
    llm: LLMClient,
    max_workers: int = 4,
    is_eleven_plus: bool = False,
) -> List[Dict[str, Any]]:
    """并行生成多科目作业，显著降低延迟

    使用线程池同时为多个科目生成作业。
    每个科目的生成流程（缓存检查 -> RAG 检索 -> LLM 生成）独立执行。

    Args:
        student_profile: 学生信息字典
        subjects: 科目列表
        llm: LLMClient 实例
        max_workers: 最大线程数（默认 4）
        is_eleven_plus: 是否来自 11+ Practice 标签页

    Returns:
        [{"subject": str, "content": str, "doc_id": str, "from_rag": bool}]
    """
    if len(subjects) <= 1:
        # 单科目无需并行
        results = []
        for subject in subjects:
            try:
                content, doc_id, from_rag = generate_homework_for_subject(student_profile, subject, llm, is_eleven_plus=is_eleven_plus)
                results.append(_public_homework_result(
                    subject=subject,
                    content=content,
                    doc_id=doc_id,
                    from_rag=from_rag,
                    student_profile=student_profile,
                    is_eleven_plus=is_eleven_plus,
                ))
            except Exception as exc:
                logger.error("[Homework] 生成 %s 失败: %s", subject, exc)
                results.append({"subject": subject, "content": "We could not prepare this homework just now. Please try again.", "doc_id": None, "from_rag": False})
        return results

    result_by_subject: Dict[str, Dict[str, Any]] = {}
    configured_workers = max(1, min(int(__import__("os").getenv("HOMEWORK_SUBJECT_WORKERS", str(max_workers))), 8))
    workers = min(len(subjects), configured_workers)
    logger.info(
        "[Homework] 并行生成 %d 个科目作业 (workers=%d, 11+=%s)",
        len(subjects), workers, is_eleven_plus,
    )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_subject = {
            executor.submit(generate_homework_for_subject, student_profile, subject, llm, is_eleven_plus): subject
            for subject in subjects
        }

        for future in as_completed(future_to_subject):
            subject = future_to_subject[future]
            try:
                content, doc_id, from_rag = future.result()
                result_by_subject[subject] = _public_homework_result(
                    subject=subject,
                    content=content,
                    doc_id=doc_id,
                    from_rag=from_rag,
                    student_profile=student_profile,
                    is_eleven_plus=is_eleven_plus,
                )
                logger.info("[Homework] 并行生成完成: %s", subject)
            except Exception as exc:
                logger.error("[Homework] 并行生成 %s 失败: %s", subject, exc)
                result_by_subject[subject] = {"subject": subject, "content": "We could not make this subject just now. Please try again.", "doc_id": None, "from_rag": False}

    return [result_by_subject[subject] for subject in subjects if subject in result_by_subject]
