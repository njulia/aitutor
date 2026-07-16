#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
UI 共享工具模块

包含 display_homeworks、parse_profile_from_natural_language 等被 TUI 和 GUI 共用的函数。
已移除 LangChain 依赖，使用轻量级 LLMClient 和缓存。
"""

import os
import base64
import logging
import re
from typing import Dict, Any, Optional
from jinja2 import Template

from src.llm_client import LLMClient, format_prompt, build_messages
from src.cache import profile_parse_cache, make_cache_key
from src.models import (
    UK_PRIMARY_SUBJECTS, ELEVEN_PLUS_SUBJECTS, YEAR_GROUP_AGE, KEY_STAGES,
    get_homework_time_by_age,
)
from src.prompts import PROFILE_PARSE_PROMPT

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?44\s?\d{4}|0\d{3,4})[\s-]?\d{3,4}[\s-]?\d{3,4}(?!\d)")
_POSTCODE_RE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.I)


def _minimise_profile_description(description: str) -> str:
    """Remove identifiers that are not needed to choose age or subjects."""
    text = str(description or "")[:2_000]
    text = _EMAIL_RE.sub("[email removed]", text)
    text = _PHONE_RE.sub("[phone removed]", text)
    text = _POSTCODE_RE.sub("[postcode removed]", text)
    # Common input starts with a child's name: "Ana is a 7-year-old...".
    text = re.sub(r"^\s*[A-Z][A-Za-z'’-]{1,30}\s+(?=is\b|aged\b|age\b)", "The pupil ", text)
    # Location is not needed for curriculum level or subject selection.
    text = re.sub(
        r"\s+in\s+(?!Year\b)[A-Z][A-Za-z'’-]{1,40}(?=[,.]|\s|$)",
        "",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def _contains_alias(text: str, alias: str) -> bool:
    escaped = re.escape(alias.strip())
    return bool(escaped and re.search(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", text, re.I))


def display_homeworks(sections) -> str:
    """将作业内容转换为带Tab切换的HTML页面，使用 homework.html 模板渲染 markdown

    Args:
        sections: 包含科目和作业的列表

    Returns:
        渲染后的 HTML 字符串（带Tab切换功能）
    """
    # 读取 homework.html 模板（在 static/ 目录）
    # shared.py 位于 src/ui/ 下，需要向上三级到达项目根目录
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    template_path = os.path.join(project_dir, "static", "homework.html")

    with open(template_path, mode='r', encoding='utf-8') as temp_file:
        template_content = temp_file.read()

    template = Template(template_content)

    # Normalize section format
    normalized_sections = []
    for item in sections:
        if isinstance(item, dict):
            subject = item.get('subject') or item.get('Subject') or ""
            homework = item.get('homework') or item.get('Homework') or ""
            normalized_sections.append({'subject': subject, 'homework': homework})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            normalized_sections.append({'subject': item[0], 'homework': item[1]})

    rendered_html = template.render(homework_items=normalized_sections)

    output_path = os.path.join(project_dir, "data", "output.html")
    with open(output_path, mode='w', encoding='utf-8') as output_file:
        output_file.write(rendered_html)

    logger.debug("Generated %s", output_path)

    # 返回 iframe 用于 Gradio 显示
    html_base64 = base64.b64encode(rendered_html.encode('utf-8')).decode('utf-8')
    iframe_html = f'<iframe src="data:text/html;base64,{html_base64}" style="width: 100%; height: 900px; border: none; border-radius: 8px;"></iframe>'
    return iframe_html


def parse_profile_from_natural_language(description: str, llm: LLMClient) -> Optional[Dict[str, Any]]:
    """用 LLM 将自然语言描述解析为学生档案，并从中提取科目（带缓存）

    Args:
        description: 自然语言描述的学生信息
        llm: LLMClient 实例

    Returns:
        学生档案字典或 None
    """
    safe_description = _minimise_profile_description(description)
    # Cache the minimised form so names, email addresses and locations are not
    # retained in a reusable cache key.
    cache_key = make_cache_key("profile_parse", safe_description)
    cached = profile_parse_cache.get(cache_key)
    if cached is not None:
        logger.info("[Cache] 命中学生档案解析缓存")
        return cached

    try:
        # Most Smart Homework descriptions include a year/age and a named
        # subject. Parse those locally first to avoid an unnecessary LLM call.
        folded = safe_description.casefold()
        year_match = re.search(r"\byear\s*([1-6])\b", folded)
        age_match = re.search(r"\b(?:age|aged|is)\s*(?:a\s*)?(\d{1,2})(?:[- ]year[- ]old|\s+years? old)?\b", folded)
        year_num = int(year_match.group(1)) if year_match else None
        age_num = int(age_match.group(1)) if age_match else None
        if year_num is None and age_num is not None and 5 <= age_num <= 11:
            year_num = max(1, min(6, age_num - 4))
        if age_num is None and year_num is not None:
            age_num = YEAR_GROUP_AGE.get(year_num, year_num + 4)

        subject_aliases = {
            "Maths": ("maths", "math", "mathematics", "numeracy"),
            "English": ("english", "reading", "writing", "spelling", "grammar"),
            "Science": ("science",),
            "Computing": ("computing", "computer", "coding"),
            "History": ("history",),
            "Geography": ("geography",),
            "Art and Design": ("art", "drawing", "design"),
            "Music": ("music",),
            "Physical Education": ("physical education", "p.e.", " sport"),
            "Languages": ("language", "french", "spanish", "german"),
        }
        extracted_subjects = [
            subject for subject in UK_PRIMARY_SUBJECTS
            if any(_contains_alias(folded, alias) for alias in subject_aliases.get(subject, (subject.casefold(),)))
        ]
        if year_num is not None and extracted_subjects:
            homework_info = get_homework_time_by_age(year_num)
            profile = {
                "student_id": "custom_student",
                "year_group": year_num,
                "age": age_num or YEAR_GROUP_AGE.get(year_num, 5),
                "key_stage": KEY_STAGES.get(year_num, "KS1"),
                "english_level": "Age appropriate",
                "learning_goals": extracted_subjects[:4],
                "weak_areas": [],
                "learning_style": "Mixed",
                "vocabulary_count": 50,
                "recommended_homework_minutes": homework_info["daily_homework_minutes"],
                "extracted_subjects": extracted_subjects,
            }
            profile_parse_cache.set(cache_key, profile)
            return profile

        prompt_text = format_prompt(
            PROFILE_PARSE_PROMPT,
            description=safe_description,
            available_subjects=", ".join(UK_PRIMARY_SUBJECTS),
        )
        messages = build_messages(prompt_text)
        result = llm.complete_json(messages, temperature=0, max_tokens=450)

        try:
            year_num = max(1, min(6, int(result.get("year_group", 1))))
        except (TypeError, ValueError):
            year_num = 1
        try:
            age_num = max(5, min(12, int(result.get("age", YEAR_GROUP_AGE.get(year_num, 5)))))
        except (TypeError, ValueError):
            age_num = YEAR_GROUP_AGE.get(year_num, 5)
        hw_info = get_homework_time_by_age(year_num)

        extracted_subjects = result.get("extracted_subjects", [])
        if not isinstance(extracted_subjects, list):
            extracted_subjects = []
        extracted_subjects = [s for s in extracted_subjects if s in UK_PRIMARY_SUBJECTS]
        logger.info("[Profile Parse] Extracted subjects: %s",
                     ', '.join(extracted_subjects) if extracted_subjects else 'None')

        profile = {
            "student_id": "custom_student",
            "year_group": year_num,
            "age": age_num,
            "key_stage": KEY_STAGES.get(year_num, "KS1"),
            "english_level": result.get("english_level", "Beginner"),
            "learning_goals": result.get("learning_goals", ["Learn basics"]),
            "weak_areas": result.get("weak_areas", []),
            "learning_style": result.get("learning_style", "Visual"),
            "vocabulary_count": result.get("vocabulary_count", 50),
            "recommended_homework_minutes": hw_info["daily_homework_minutes"],
            "extracted_subjects": extracted_subjects,
        }

        # 写入缓存
        profile_parse_cache.set(cache_key, profile)
        return profile
    except Exception as e:
        logger.error("[Profile Parse Error] %s", e)
        return None
