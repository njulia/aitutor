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
from typing import Dict, List, Any, Tuple

from src.llm_client import LLMClient, format_prompt, build_messages
from src.cache import homework_cache, subject_extraction_cache, make_cache_key
from src.models import (
    UK_PRIMARY_SUBJECTS, ELEVEN_PLUS_SUBJECTS, KEY_STAGES, get_homework_time_by_age,
    YEAR_GROUP_AGE,
)
from src.homework_rag import (
    store_homework, search_homework, get_student_previous_topics,
    search_homework_answers,
)
from src.elevenplus.elevenplus_rag import (
    store_homework as elevenplus_store_homework,
    search_homework as elevenplus_search_homework,
    get_student_previous_topics as elevenplus_get_student_previous_topics,
    search_homework_answers as elevenplus_search_homework_answers,
)
from src.elevenplus.prompts import (
    HOMEWORK_PROMPT_11PLUS, RAG_PROMPT_11PLUS,
)
from src.prompts import (
    HOMEWORK_PROMPT, HOMEWORK_ANSWER_PROMPT, SUBJECT_EXTRACTION_PROMPT,
)


logger = logging.getLogger(__name__)


def _is_eleven_plus_subject(subject: str) -> bool:
    """判断是否为 11+ 专属科目（不属于普通小学课程）"""
    return subject in ("Verbal Reasoning", "Non-Verbal Reasoning")


def generate_homewor_by_tools(subject, year_group, student_id, cache_key, store_homework_func):
    # --- TOOL OFFLOADING ---
    # Map subjects to tools
    TOOL_MAP = {
        "Maths": "generate_math_homework_tool",
        "Science": "generate_science_homework_tool",
        "English": "generate_english_homework_tool"
    }

    if subject in TOOL_MAP:
        try:
            from src.tools.math_tools import (
                generate_math_homework_tool,
                generate_science_homework_tool,
                generate_english_homework_tool
            )
            tool_func_name = TOOL_MAP[subject]
            tool_func = locals().get(tool_func_name) or globals().get(tool_func_name)

            # Since we imported them directly, they might not be in locals/globals
            # as expected by the logic above if imported inside the try.
            # Let's just use a simple if-else or direct call.
            if subject == "Maths":
                tool_func = generate_math_homework_tool
            elif subject == "Science":
                tool_func = generate_science_homework_tool
            elif subject == "English":
                tool_func = generate_english_homework_tool

            if tool_func:
                logger.info("[Tool] Using Python tool to generate %s homework for Year %d", subject, year_group)
                tool_result = tool_func(year_group)
                content = tool_result["content"]
                answers = tool_result["answers"]

                # Store to RAG for consistency
                doc_id = store_homework_func(
                    content=content,
                    year_group=year_group,
                    subject=subject,
                    student_id=student_id,
                    answers=answers
                )

                # Update cache
                homework_cache.set(cache_key, {"content": content, "doc_id": doc_id, "from_rag": False})
                return content, doc_id, False
        except Exception as tool_exc:
            logger.warning("[Tool] %s tool failed, falling back to RAG/LLM: %s", subject, tool_exc)
            return None, None, None
    # --- END TOOL OFFLOADING ---


def generate_homework_for_subject(student_profile: Dict[str, Any], subject: str, llm: LLMClient, is_eleven_plus: bool = False) -> tuple:
    """为指定科目生成作业（每次都生成新作业，避免重复以前的内容）

    优先从 RAG 中检索已有作业，命中则直接返回（零 LLM 调用）。
    未命中则调用 LLM 生成并存入 RAG。

    Args:
        student_profile: 学生信息字典
        subject: 科目名称
        llm: LLMClient 实例
        is_eleven_plus: 是否来自 11+ Practice 标签页（所有科目按 Year 6 难度）

    Returns:
        (作业内容字符串, doc_id, from_rag)
    """
    # 11+ Practice 标签页或 11+ 专属科目，始终按 Year 6 难度生成
    if is_eleven_plus or _is_eleven_plus_subject(subject):
        year_group = 6
        age = 11  # 11+ 考试针对 Year 6 (10-11岁)
    else:
        year_group = student_profile.get("year_group", 6)
        age = student_profile.get("age") or YEAR_GROUP_AGE.get(year_group, 11)
    
    homework_info = get_homework_time_by_age(year_group)
    homework_time = homework_info["daily_homework_minutes"]
    student_id = student_profile.get("student_id", "")

    # 根据 is_eleven_plus 选择对应的 RAG 存储
    if is_eleven_plus:
        _store_homework = elevenplus_store_homework
        _search_homework = elevenplus_search_homework
        _get_previous_topics = elevenplus_get_student_previous_topics
    else:
        _store_homework = store_homework
        _search_homework = search_homework
        _get_previous_topics = get_student_previous_topics

    # 1. 检查内存缓存（同学科同年级的作业可直接复用）
    cache_key = make_cache_key("homework", str(year_group), str(age), subject, "11plus" if is_eleven_plus else "normal")
    cached = homework_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中作业缓存: %s Year %d (%s)", subject, year_group, "11+" if is_eleven_plus else "normal")
        return cached["content"], cached["doc_id"], cached.get("from_rag", False)

    # 2. 获取该学生该科目的历史作业，用于避免重复
    try:
        previous_topics = _get_previous_topics(student_id, subject)
        if previous_topics:
            logger.info("[RAG] Found %d previous homework for %s in %s - will avoid duplicates",
                        len(previous_topics), student_id, subject)
    except Exception as e:
        logger.warning("[RAG] Failed to get previous topics: %s", e)
        previous_topics = []

    # 3. 搜索 RAG 中是否有相关作业
    learning_goals = student_profile.get("learning_goals", [])
    weak_areas = student_profile.get("weak_areas", [])
    search_query = " ".join(learning_goals + weak_areas + [subject])

    # # Create homework with tools
    # content, doc_id, from_rag = generate_homewor_by_tools(subject, year_group, student_id, cache_key, _store_homework)
    # if content and doc_id and not from_rag:
    #     return content, doc_id, from_rag

    try:
        rag_results = _search_homework(
            query=search_query,
            year_group=year_group,
            subject=subject,
            k=1,
        )

        # 如果 RAG 中有相关作业，直接返回（零 LLM 调用）
        if rag_results:
            homework_content = rag_results[0]["content"]
            doc_id = rag_results[0]["doc_id"]
            logger.info("[RAG] Found matching homework in RAG for %s (Year %d, %s)", subject, year_group, "11+" if is_eleven_plus else "normal")
            # 写入内存缓存
            homework_cache.set(cache_key, {"content": homework_content, "doc_id": doc_id, "from_rag": True})
            return homework_content, doc_id, True
    except Exception as e:
        logger.warning("[RAG] Failed to search homework: %s", e)

    # 4. RAG 中没有相关作业，调用 LLM 生成新作业
    logger.info("[Homework] No matching homework in RAG, generating new for %s (Year %d, %s)", subject, year_group, "11+" if is_eleven_plus else "normal")

    # 构建历史主题上下文
    previous_context = ""
    if previous_topics:
        previous_context = "\n\nIMPORTANT - Previously covered topics (DO NOT repeat ANY of these):\n"
        for i, topic in enumerate(previous_topics[-8:], 1):
            previous_context += f"{i}. {topic}\n"
        previous_context += "\nPlease create completely NEW homework that does not cover any of the topics above.\n"

    # 调用 LLM 生成作业
    if is_eleven_plus:
        prompt_template = HOMEWORK_PROMPT_11PLUS
    else:
        prompt_template = HOMEWORK_PROMPT

    prompt_text = format_prompt(
        prompt_template,
        student_profile=json.dumps(student_profile, ensure_ascii=False, indent=2),
        subject=subject,
        homework_time=homework_time,
        year_group=year_group,
        age=age,
        previous_topics=previous_context,
        index=len(previous_topics) + 1,  # For RAG_PROMPT_11PLUS if needed, but we use HOMEWORK_PROMPT_11PLUS
    )
    messages = build_messages(prompt_text)
    result = llm.complete(messages)

    # 5. 将新生成的作业存储到对应的 RAG 中
    doc_id = None
    try:
        doc_id = _store_homework(
            homework_content=result,
            year_group=year_group,
            subject=subject,
            homework_minutes=homework_time,
            key_stage=KEY_STAGES.get(year_group, "KS2"),
            english_level=student_profile.get("english_level", "Beginner"),
            student_id=student_id,
            age=age,
        )
        logger.info("[RAG] Stored NEW homework for %s in %s (Year %d, %s), doc_id: %s",
                     student_id, subject, year_group, "11+" if is_eleven_plus else "normal", doc_id)
    except Exception as e:
        logger.warning("[RAG] Failed to store homework for %s: %s", subject, e)

    # 写入内存缓存
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
                results.append({"subject": subject, "content": content, "doc_id": doc_id, "from_rag": from_rag})
            except Exception as exc:
                logger.error("[Homework] 生成 %s 失败: %s", subject, exc)
                results.append({"subject": subject, "content": f"Error: {exc}", "doc_id": None, "from_rag": False})
        return results

    results = []
    workers = min(len(subjects), max_workers)
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
                results.append({"subject": subject, "content": content, "doc_id": doc_id, "from_rag": from_rag})
                logger.info("[Homework] 并行生成完成: %s", subject)
            except Exception as exc:
                logger.error("[Homework] 并行生成 %s 失败: %s", subject, exc)
                results.append({"subject": subject, "content": f"Error: {exc}", "doc_id": None, "from_rag": False})

    return results
