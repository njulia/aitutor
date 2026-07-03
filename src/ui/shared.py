#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
UI 共享工具模块

包含 display_homeworks、parse_profile_from_natural_language 等被 TUI 和 GUI 共用的函数。
"""

import os
import base64
import logging
from typing import Dict, Any, Optional
from jinja2 import Template

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models import (
    UK_PRIMARY_SUBJECTS, ELEVEN_PLUS_SUBJECTS, YEAR_GROUP_AGE, KEY_STAGES,
    get_homework_time_by_age,
)
from src.prompts import PROFILE_PARSE_PROMPT

LLM_MODEL = "qwen3.5-plus"
AGICTO_API_KEY = os.getenv("AGICTO_API_KEY")

logger = logging.getLogger(__name__)


def display_homeworks(sections) -> str:
    """将作业内容转换为带Tab切换的HTML页面，使用 homework.html 模板渲染 markdown

    Args:
        sections: 包含科目和作业的列表

    Returns:
        渲染后的 HTML 字符串（带Tab切换功能）
    """
    # 读取 homework.html 模板（在 templates/ 目录）
    # shared.py 位于 src/ui/ 下，需要向上三级到达项目根目录
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    template_path = os.path.join(project_dir, "templates", "homework.html")

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

    logger.debug(f"Generated {output_path}")

    # 返回 iframe 用于 Gradio 显示
    html_base64 = base64.b64encode(rendered_html.encode('utf-8')).decode('utf-8')
    iframe_html = f'<iframe src="data:text/html;base64,{html_base64}" style="width: 100%; height: 900px; border: none; border-radius: 8px;"></iframe>'
    return iframe_html


def parse_profile_from_natural_language(description: str, llm) -> Optional[Dict[str, Any]]:
    """用 LLM 将自然语言描述解析为学生档案，并从中提取科目

    Args:
        description: 自然语言描述的学生信息
        llm: LangChain LLM 实例

    Returns:
        学生档案字典或 None
    """
    try:
        prompt = ChatPromptTemplate.from_template(PROFILE_PARSE_PROMPT)
        chain = prompt | llm | JsonOutputParser()
        result = chain.invoke({
            "description": description,
            "available_subjects": ", ".join(UK_PRIMARY_SUBJECTS),
        })

        year_num = result.get("year_group", 1)
        age_num = result.get("age", YEAR_GROUP_AGE.get(year_num, 5))
        hw_info = get_homework_time_by_age(year_num)

        extracted_subjects = result.get("extracted_subjects", [])
        if not isinstance(extracted_subjects, list):
            extracted_subjects = []
        extracted_subjects = [s for s in extracted_subjects if s in UK_PRIMARY_SUBJECTS]
        print(
            f"[Profile Parse] Extracted subjects: {', '.join(extracted_subjects) if extracted_subjects else 'None'}")

        return {
            "student_id": f"custom_{result.get('name', 'student').strip()}",
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
    except Exception as e:
        print(f"[Profile Parse Error] {e}")
        return None
