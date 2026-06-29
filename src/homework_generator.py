#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
作业生成模块

负责为 UK 小学生生成各科作业，包括 RAG 检索、新作业生成、科目提取等。
"""

import json
import logging
from typing import Dict, List, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

from src.models import (
    UK_PRIMARY_SUBJECTS, KEY_STAGES, get_homework_time_by_age,
)
from src.homework_rag import (
    store_homework, search_homework, get_student_previous_topics,
    search_homework_answers,
)
from src.prompts import (
    HOMEWORK_PROMPT, HOMEWORK_ANSWER_PROMPT, SUBJECT_EXTRACTION_PROMPT,
)

# AGICTO API Key
LLM_MODEL = "qwen3.5-plus"

logger = logging.getLogger(__name__)


def generate_homework_for_subject(student_profile: Dict[str, Any], subject: str, llm) -> str:
    """为指定科目生成作业（优先从 RAG 中查找，未找到则生成新作业）

    Args:
        student_profile: 学生信息字典
        subject: 科目名称
        llm: LangChain LLM 实例

    Returns:
        作业内容字符串
    """
    year_group = student_profile.get("year_group", 3)
    homework_info = get_homework_time_by_age(year_group)
    homework_time = homework_info["daily_homework_minutes"]
    student_id = student_profile.get("student_id", "")

    # 1. 先从 RAG 中搜索该学生该科目的历史作业
    try:
        previous_topics = get_student_previous_topics(student_id, subject)
        if previous_topics:
            logger.info(f"[RAG] Found {len(previous_topics)} previous homework for {student_id} in {subject}")
    except Exception as e:
        logger.warning(f"[RAG] Failed to get previous topics: {e}")
        previous_topics = []

    # 2. 使用学习目标和弱项构建查询，搜索 RAG 中是否有相关作业
    learning_goals = student_profile.get("learning_goals", [])
    weak_areas = student_profile.get("weak_areas", [])
    search_query = " ".join(learning_goals + weak_areas + [subject])

    try:
        rag_results = search_homework(
            query=search_query,
            year_group=year_group,
            subject=subject,
            k=1,
        )

        # 如果 RAG 中有相关作业，直接返回
        if rag_results:
            homework_content = rag_results[0]["content"]
            logger.info(f"[RAG] Found matching homework in RAG for {subject} (Year {year_group})")
            return homework_content
    except Exception as e:
        logger.warning(f"[RAG] Failed to search homework: {e}")

    # 3. RAG 中没有相关作业，生成新作业
    logger.info(f"[RAG] No matching homework found in RAG, generating new homework for {subject}")

    # Build previous topics context to avoid duplicates
    previous_context = ""
    if previous_topics:
        previous_context = "\n\nPreviously covered topics (DO NOT repeat these):\n"
        for i, topic in enumerate(previous_topics[-5:], 1):  # Last 5 homework
            previous_context += f"{i}. {topic}\n"

    prompt = ChatPromptTemplate.from_template(HOMEWORK_PROMPT)
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({
        "student_profile": json.dumps(student_profile, ensure_ascii=False, indent=2),
        "subject": subject,
        "homework_time": homework_time,
        "year_group": year_group,
        "age": student_profile.get("age", 7),
        "previous_topics": previous_context,
    })

    # 4. 生成正确答案（针对有唯一答案的作业）
    correct_answers = None
    try:
        answer_prompt = ChatPromptTemplate.from_template(HOMEWORK_ANSWER_PROMPT)
        answer_chain = answer_prompt | llm | StrOutputParser()
        correct_answers = answer_chain.invoke({
            "homework_content": result,
            "subject": subject,
            "year_group": year_group,
        })
        logger.info(f"[RAG] Generated correct answers for {subject} (Year {year_group})")
    except Exception as e:
        logger.warning(f"[RAG] Failed to generate correct answers for {subject}: {e}")

    # 5. 将新生成的作业存储到 RAG 中（包含正确答案）
    try:
        store_homework(
            homework_content=result,
            year_group=year_group,
            subject=subject,
            homework_minutes=homework_time,
            key_stage=KEY_STAGES.get(year_group, "KS2"),
            english_level=student_profile.get("english_level", "Beginner"),
            student_id=student_id,
            correct_answers=correct_answers,
        )
        logger.info(f"[RAG] Stored new homework for {subject} (Year {year_group}) in vector database")
    except Exception as e:
        logger.warning(f"[RAG] Failed to store homework for {subject}: {e}")

    return result


def extract_subjects_from_prompt(user_input: str, llm) -> List[str]:
    """从用户提示词中提取科目

    Args:
        user_input: 用户的自然语言输入
        llm: LangChain LLM 实例

    Returns:
        提取到的科目列表
    """
    prompt = ChatPromptTemplate.from_template(SUBJECT_EXTRACTION_PROMPT)
    chain = prompt | llm | JsonOutputParser()

    result = chain.invoke({
        "available_subjects": ", ".join(UK_PRIMARY_SUBJECTS),
        "user_input": user_input,
    })

    if isinstance(result, list):
        return [s for s in result if s in UK_PRIMARY_SUBJECTS]
    return []


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


def generate_multiday_homework(student_profile: Dict[str, Any], subjects: List[str], num_days: int, llm) -> Dict[int, Dict[str, str]]:
    """生成指定天数的作业，每天最多两个科目

    Args:
        student_profile: 学生信息字典
        subjects: 科目列表
        num_days: 天数
        llm: LangChain LLM 实例

    Returns:
        {day_number: {subject: homework_content}}
    """
    homework_plan = {}

    # 将科目分配到5天中，每天最多2个科目
    day_assignments = distribute_subjects_to_days(subjects, num_days)

    for day, day_subjects in day_assignments.items():
        day_homework = {}
        for subject in day_subjects:
            logger.info(f"[Homework] Day {day}: Generating homework for {subject}...")
            homework = generate_homework_for_subject(student_profile, subject, llm)
            day_homework[subject] = homework
        homework_plan[day] = day_homework

    return homework_plan
