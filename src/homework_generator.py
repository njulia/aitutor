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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any

from src.llm_client import LLMClient, format_prompt, build_messages
from src.cache import homework_cache, subject_extraction_cache, make_cache_key
from src.models import (
    UK_PRIMARY_SUBJECTS, KEY_STAGES, get_homework_time_by_age,
    YEAR_GROUP_AGE, is_eleven_plus_subject as is_known_eleven_plus_subject,
    subject_display_name,
)
from src.homework_rag import (
    store_homework, search_homework, search_homework_by_metadata,
    get_student_previous_topics,
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
from src.webapp.question_utils import parse_public_questions


logger = logging.getLogger(__name__)


def _is_eleven_plus_subject(subject: str) -> bool:
    """Recognise ordinary and 52-week 11+ subject identifiers."""
    return is_known_eleven_plus_subject(subject)



def generate_homework_for_subject(
    student_profile: Dict[str, Any],
    subject: str,
    llm: LLMClient,
    is_eleven_plus: bool = False,
) -> tuple:
    """Return unseen RAG homework first; call the LLM only after an exact RAG miss.

    Assignment history is stored separately from the shared RAG library. This
    makes no-repeat behaviour reliable across workers without storing child
    answers or personal profile text in Chroma.
    """
    if is_eleven_plus:
        year_group = 6
        age = 11
    else:
        year_group = int(student_profile.get("year_group", 6))
        age = int(student_profile.get("age") or YEAR_GROUP_AGE.get(year_group, 11))

    homework_info = get_homework_time_by_age(year_group)
    homework_time = homework_info["daily_homework_minutes"]
    learner_key = str(student_profile.get("student_id") or "anonymous")[:100]
    plan_week = 0
    try:
        requested_week = int(student_profile.get("plan_week") or 0)
        if 1 <= requested_week <= 52:
            plan_week = requested_week
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
        semantic_search = elevenplus_search_homework
        metadata_search = elevenplus_search_homework_by_metadata
        previous_topics_func = elevenplus_get_student_previous_topics
    else:
        store_func = store_homework
        semantic_search = search_homework
        metadata_search = search_homework_by_metadata
        previous_topics_func = get_student_previous_topics

    cache_key = make_cache_key(
        "homework",
        str(year_group),
        str(age),
        subject,
        learner_key,
        str(plan_week),
        "|".join(str(item) for item in student_profile.get("learning_goals", [])[:4]),
        "|".join(str(item) for item in student_profile.get("weak_areas", [])[:4]),
    )
    assignment_store = get_assignment_store()

    learning_goals = [compact_text(item, 120) for item in student_profile.get("learning_goals", []) if item]
    weak_areas = [compact_text(item, 120) for item in student_profile.get("weak_areas", []) if item]
    has_personalised_query = bool(learning_goals or weak_areas)

    try:
        # Exact metadata lookup is faster and avoids creating an embedding for
        # the common year/subject request. Semantic search is reserved for a
        # real learning-goal query.
        if is_eleven_plus and plan_week:
            # The 52-week plan must never drift to another week. Use a hard
            # metadata filter rather than a similarity query based on topic text.
            candidates = metadata_search(
                year_group=year_group,
                subject=subject,
                week_num=plan_week,
                content_type="year_round",
                k=20,
            )
        elif has_personalised_query:
            query = compact_text(" ".join(learning_goals + weak_areas + [subject_label]), 600)
            candidates = semantic_search(
                query=query, year_group=year_group, subject=subject, k=50
            )
        else:
            candidates = metadata_search(year_group=year_group, subject=subject, k=100)

        if candidates:
            candidate_by_id = {str(item.get("doc_id")): item for item in candidates if item.get("doc_id")}
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
                    homework_cache.set(
                        cache_key,
                        {"content": content, "doc_id": claimed_id, "from_rag": True},
                    )
                    logger.info(
                        "[RAG] Assigned unseen %s homework for Year %d, week=%s, doc_id=%s",
                        subject, year_group, plan_week or "general", claimed_id,
                    )
                    return content, claimed_id, True
            logger.info("[RAG] No unseen exact candidates remain for %s Year %d", subject, year_group)
    except Exception:
        logger.exception("[RAG] Homework lookup failed for %s Year %d", subject, year_group)

    # RAG miss: build a compact, privacy-minimised prompt. The learner ID and
    # free-text description are intentionally excluded from the model input.
    try:
        previous_topics = previous_topics_func(learner_key, subject)
    except Exception:
        previous_topics = []

    previous_context = ""
    if previous_topics:
        previews = [compact_text(topic, 180) for topic in previous_topics[-6:]]
        previous_context = (
            "Previously used material. Create different questions:\n- "
            + "\n- ".join(previews)
        )

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
        previous_topics=compact_text(previous_context, 1_500),
        index=len(previous_topics) + 1,
    )
    result = str(llm.complete(build_messages(prompt_text))).strip()
    if not result:
        raise RuntimeError("The homework generator returned an empty response")

    doc_id = None
    try:
        store_kwargs = {
            "homework_content": result,
            "year_group": year_group,
            "subject": subject,
            "homework_minutes": homework_time,
            "key_stage": KEY_STAGES.get(year_group, "KS2"),
            "english_level": student_profile.get("english_level"),
            "student_id": None,  # shared library content must not be owned by one learner
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

    homework_cache.set(cache_key, {"content": result, "doc_id": doc_id, "from_rag": False})
    return result, doc_id, False

def extract_subjects_from_prompt(user_input: str, llm: LLMClient) -> List[str]:
    """从用户提示词中提取科目（带缓存）

    Args:
        user_input: 用户的自然语言输入
        llm: LLMClient 实例

    Returns:
        提取到的科目列表
    """
    # 检查缓存
    cache_key = make_cache_key("subject_extract", user_input)
    cached = subject_extraction_cache.get(cache_key)
    if cached is not None:
        logger.info("[Cache] 命中科目提取缓存")
        return cached

    prompt_text = format_prompt(
        SUBJECT_EXTRACTION_PROMPT,
        available_subjects=", ".join(UK_PRIMARY_SUBJECTS),
        user_input=user_input,
    )
    messages = build_messages(prompt_text)
    result = llm.complete_json(messages)

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
