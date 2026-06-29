#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
作业管理模块

负责作业的保存、加载、检查完成情况、点评等功能。
"""

import csv
import glob
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.models import get_homework_time_by_age
from src.homework_rag import search_homework_answers
from src.prompts import (
    REVIEW_HOMEWORK_PROMPT, REVIEW_UPLOADED_HOMEWORK_PROMPT,
)

logger = logging.getLogger(__name__)


def save_homework_to_file(homework_plan: Dict[int, Dict[str, str]], student_id: str, num_days: int, output_dir: str = "homework_output") -> str:
    """将指定天数的作业保存到本地文件

    Args:
        homework_plan: 作业计划 {day: {subject: content}}
        student_id: 学生ID
        num_days: 天数
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{output_dir}/homework_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# {num_days}-Day Homework Plan\n")
        f.write(f"Student: {student_id}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n\n")

        for day in sorted(homework_plan.keys()):
            day_homework = homework_plan[day]
            f.write(f"\n{'#'*50}\n")
            f.write(f"## Day {day}\n")
            f.write(f"{'#'*50}\n\n")

            for subject, content in day_homework.items():
                f.write(f"### {subject}\n\n")
                f.write(f"{content}\n\n")
                f.write(f"{'~'*40}\n\n")

    logger.info(f"[Save] Homework saved to: {filename}")
    return filename


def load_latest_homework(student_id: str, output_dir: str = "homework_output") -> Optional[tuple]:
    """从本地加载最近一天的作业文件

    Args:
        student_id: 学生ID
        output_dir: 作业输出目录

    Returns:
        (homework_plan, filepath) 或 None
    """
    if not os.path.exists(output_dir):
        return None

    # 查找所有匹配的作业文件
    pattern = f"{output_dir}/homework_{student_id}_*.md"
    files = glob.glob(pattern)

    if not files:
        return None

    # 按修改时间排序，获取最新的
    files.sort(key=os.path.getmtime, reverse=True)
    latest_file = files[0]

    logger.info(f"[Load] Found latest homework file: {latest_file}")

    # 解析文件内容
    homework_plan = {}
    current_day = None
    current_subject = None
    current_content = []

    with open(latest_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')

            if line.startswith('## Day '):
                # 保存之前的内容
                if current_day and current_subject:
                    homework_plan.setdefault(current_day, {})[current_subject] = '\n'.join(current_content).strip()
                    current_content = []

                # 提取天数
                try:
                    current_day = int(line.replace('## Day ', '').strip())
                except ValueError:
                    continue

            elif line.startswith('### '):
                # 保存之前的科目内容
                if current_day and current_subject:
                    homework_plan.setdefault(current_day, {})[current_subject] = '\n'.join(current_content).strip()
                    current_content = []

                current_subject = line.replace('### ', '').strip()

            elif current_day and current_subject:
                current_content.append(line)

        # 保存最后一个科目
        if current_day and current_subject:
            homework_plan.setdefault(current_day, {})[current_subject] = '\n'.join(current_content).strip()

    if homework_plan:
        return homework_plan, latest_file

    return None


def check_homework_completion(homework_plan: Dict[int, Dict[str, str]], student_id: str, output_dir: str = "homework_output") -> Dict[int, List[str]]:
    """检查指定天数的作业的完成情况

    Args:
        homework_plan: 作业计划
        student_id: 学生ID
        output_dir: 输出目录

    Returns:
        {day: [未完成科目]} - 返回未完成的天和科目
    """
    # 查找所有点评文件，确定哪些天已完成
    review_pattern = f"{output_dir}/review_{student_id}_*.md"
    review_files = glob.glob(review_pattern)

    completed_days = set()
    for rf in review_files:
        # 从文件名提取天数信息（如果有）
        basename = os.path.basename(rf)
        # 格式: review_student1_20260621_HHMMSS_DayX.md 或 review_student1_20260621_HHMMSS.md
        if '_Day' in basename:
            try:
                day_str = basename.split('_Day')[1].split('.')[0]
                completed_days.add(int(day_str))
            except ValueError:
                pass

    # 找出未完成的日期
    incomplete = {}
    for day in sorted(homework_plan.keys()):
        if day not in completed_days:
            incomplete[day] = list(homework_plan[day].keys())

    return incomplete


def review_day_homework(student_profile: Dict[str, Any], day: int, subjects_homework: Dict[str, str], student_answers: Dict[str, str], llm) -> str:
    """点评某一天的作业

    Args:
        student_profile: 学生档案
        day: 天数
        subjects_homework: {科目: 作业内容}
        student_answers: {科目: 学生答案}
        llm: LangChain LLM 实例

    Returns:
        点评内容
    """
    reviews = []

    for subject, homework in subjects_homework.items():
        student_answer = student_answers.get(subject, "Not submitted")

        prompt = ChatPromptTemplate.from_template(REVIEW_HOMEWORK_PROMPT)
        chain = prompt | llm | StrOutputParser()

        review = chain.invoke({
            "student_profile": json.dumps(student_profile, ensure_ascii=False, indent=2),
            "subject": subject,
            "day": day,
            "homework_content": homework,
            "student_answer": student_answer,
        })

        reviews.append(f"### {subject}\n\n{review}\n")

    return "\n".join(reviews)


def save_review_with_homework(homework_plan: Dict[int, Dict[str, str]], reviews: Dict[int, str], student_id: str, output_dir: str = "homework_output") -> str:
    """将作业和点评一起保存到本地

    Args:
        homework_plan: 作业计划 {day: {subject: content}}
        reviews: 点评内容 {day: review_text}
        student_id: 学生ID
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{output_dir}/review_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# Homework & Review\n")
        f.write(f"Student: {student_id}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n\n")

        for day in sorted(homework_plan.keys()):
            day_homework = homework_plan[day]
            f.write(f"\n{'#'*50}\n")
            f.write(f"## Day {day}\n")
            f.write(f"{'#'*50}\n\n")

            # 作业内容
            f.write(f"### Homework\n\n")
            for subject, content in day_homework.items():
                f.write(f"#### {subject}\n\n")
                f.write(f"{content}\n\n")

            # 点评
            f.write(f"\n### Review\n\n")
            day_review = reviews.get(day, "No review available")
            f.write(f"{day_review}\n\n")
            f.write(f"{'~'*40}\n\n")

    logger.info(f"[Save] Review saved to: {filename}")
    return filename


def regenerate_multiday_homework(student_profile: Dict[str, Any], subjects: List[str], num_days: int, llm, output_dir: str = "homework_output") -> tuple:
    """重新生成指定天数的作业并检查完成情况

    Args:
        student_profile: 学生档案
        subjects: 科目列表
        num_days: 天数
        llm: LangChain LLM 实例
        output_dir: 输出目录

    Returns:
        (homework_plan, incomplete_days, filepath)
    """
    from src.homework_generator import generate_multiday_homework

    # 尝试加载最近的作业
    latest = load_latest_homework(student_profile["student_id"], output_dir)

    if latest:
        homework_plan, filepath = latest
        logger.info(f"[Load] Loaded existing homework plan from: {filepath}")

        # 检查完成情况
        incomplete = check_homework_completion(homework_plan, student_profile["student_id"], output_dir)

        if not incomplete:
            logger.info(f"[Info] All homework completed! Generating new {num_days}-day plan...")
            homework_plan = generate_multiday_homework(student_profile, subjects, num_days, llm)
            filepath = save_homework_to_file(homework_plan, student_profile["student_id"], num_days, output_dir)
            incomplete = {day: list(subjects_homework.keys()) for day, subjects_homework in homework_plan.items()}
        else:
            logger.info(f"[Info] Found incomplete days: {list(incomplete.keys())}")
    else:
        logger.info(f"[Info] No existing homework found. Generating new {num_days}-day plan...")
        homework_plan = generate_multiday_homework(student_profile, subjects, num_days, llm)
        filepath = save_homework_to_file(homework_plan, student_profile["student_id"], num_days, output_dir)
        incomplete = {day: list(subjects_homework.keys()) for day, subjects_homework in homework_plan.items()}

    return homework_plan, incomplete, filepath


def load_homework_from_file(filepath: str = None) -> List[Dict[str, str]]:
    """从 CSV 文件加载作业

    Args:
        filepath: CSV 文件路径（可选）

    Returns:
        包含科目和作业的列表
    """
    sections = []
    # 数据文件在父目录的 data/ 文件夹
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rag_path = os.path.join(project_dir, "data", "homework.csv") if not filepath else filepath

    if os.path.exists(rag_path):
        with open(rag_path, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            # Skip the header row
            next(reader, None)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                subject = row[0].strip()
                homework = row[1].strip().replace('\\""', '"').replace('""', '"')
                sections.append({
                    'subject': subject,
                    'homework': homework
                })
        logger.info(f"[Load] Loaded existing homework plan from {rag_path}")
        logger.debug(sections)
    return sections


def generate_homework_with_custom_profile(student_profile: Dict[str, Any], subjects: List[str], llm) -> list:
    """使用自定义学生档案生成作业

    Args:
        student_profile: 学生信息字典
        subjects: 选中的科目列表
        llm: LangChain LLM 实例

    Returns:
        包含科目和作业字典的列表
    """
    # 从文件加载（现有逻辑）
    return load_homework_from_file()


def process_homework_with_review(user_input: str, student_id: str = "student1", student_answers: Dict[int, Dict[str, str]] = None, llm = None, output_dir: str = "homework_output") -> str:
    """完整的作业处理流程：导入/生成 -> 点评 -> 保存

    Args:
        user_input: 用户提示词（包含科目信息）
        student_id: 学生ID
        student_answers: 学生答案 {day: {subject: answer}}
        llm: LangChain LLM 实例
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    from src.ui import parse_profile_from_natural_language
    from src.homework_generator import extract_subjects_from_prompt

    # 1. 获取学生档案
    profile = parse_profile_from_natural_language(user_input, llm)

    # 2. 提取科目
    if profile and profile.get("extracted_subjects"):
        subjects = profile["extracted_subjects"]
    elif profile and profile.get("learning_goals"):
        subjects = extract_subjects_from_prompt(profile["learning_goals"], llm)
        logger.info(f"[Extracted Subjects from Learning Goals] {', '.join(subjects)}")
    else:
        logger.warning("[Warning] No subjects found in input. Using default subjects: English, Math")
        subjects = ["English", "Math"]

    logger.info(f"[Extracted Subjects] {', '.join(subjects)}")

    # 3. 加载或重新生成作业
    num_days = 5
    homework_plan, incomplete, filepath = regenerate_multiday_homework(profile, subjects, num_days, llm, output_dir)

    # 4. 点评未完成的作业
    reviews = {}
    for day, day_subjects in incomplete.items():
        day_homework = {s: homework_plan[day][s] for s in day_subjects if s in homework_plan.get(day, {})}

        # 使用提供的答案或默认"未提交"
        day_answers = student_answers.get(day, {s: "Not submitted" for s in day_subjects}) if student_answers else {s: "Not submitted" for s in day_subjects}

        logger.info(f"[Review] Reviewing Day {day} homework...")
        review = review_day_homework(profile, day, day_homework, day_answers, llm)
        reviews[day] = review

    # 5. 保存作业和点评
    final_filepath = save_review_with_homework(homework_plan, reviews, student_id, output_dir)

    return final_filepath


def review_uploaded_homework(student_profile: Dict[str, Any], subject: str, student_work: str, homework_assignment: str, llm) -> str:
    """批阅上传的作业

    Args:
        student_profile: 学生档案
        subject: 科目
        student_work: 学生提交的作业内容
        homework_assignment: 原始作业题目（如果有）
        llm: LangChain LLM 实例

    Returns:
        批阅结果
    """
    prompt_template = REVIEW_UPLOADED_HOMEWORK_PROMPT

    if homework_assignment:
        # 1. 先从 RAG 中检索是否有该作业的答案
        correct_answers = None
        year_group = student_profile.get("year_group")
        try:
            correct_answers = search_homework_answers(
                homework_content=homework_assignment,
                year_group=year_group,
                subject=subject,
                k=1,
            )
            if correct_answers:
                logger.info(f"[RAG] Found correct answers in RAG for {subject} review")
            else:
                logger.info(f"[RAG] No matching answers found in RAG, using LLM for review")
        except Exception as e:
            logger.warning(f"[RAG] Failed to search answers for review: {e}")

        # 2. 构建 prompt（如果有正确答案，加入到 prompt 中）
        if correct_answers:
            prompt_template = REVIEW_UPLOADED_HOMEWORK_PROMPT + f"""
            Correct Answers (use these to check student's work):
            {correct_answers}
            """

    # 3. 调用 LLM 进行批阅
    homework_assignment = "Please analyze the homework assignment from the context."
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | StrOutputParser()
    review = chain.invoke({
        "student_profile": json.dumps(student_profile, ensure_ascii=False, indent=2),
        "subject": subject,
        "homework_assignment": homework_assignment,
        "student_work": student_work,
    })

    return review
