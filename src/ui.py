#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户界面模块

包含 TUI（终端界面）和 GUI（Gradio Web 界面）的实现。
"""

import os
import base64
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from jinja2 import Template

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI

from src.models import (
    UK_PRIMARY_SUBJECTS, SAMPLE_STUDENT_PROFILES, YEAR_GROUP_AGE, KEY_STAGES,
    get_homework_time_by_age, SUBJECT_ICONS,
)
from src.homework_generator import extract_subjects_from_prompt
from src.homework_manager import (
    load_homework_from_file, generate_homework_with_custom_profile,
    review_uploaded_homework,
)
from src.prompts import PROFILE_PARSE_PROMPT

# AGICTO API Key
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
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(project_dir, "templates", "homework.html")

    with open(template_path, mode='r', encoding='utf-8') as temp_file:
        template_content = temp_file.read()

    template = Template(template_content)

    # Normalize section format
    normalized_sections = []
    for item in sections:
        if isinstance(item, dict):
            subject = item.get('subject') or item.get('Subject') or ""
            homework = item.get('content') or item.get('homework') or item.get('Homework') or ""
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


def extract_text_from_image(image_path: str) -> str:
    """从图片中提取文本（使用多模态 LLM）"""
    try:
        vision_llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=AGICTO_API_KEY,
            openai_api_base="https://api.agicto.cn/v1/",
            temperature=0,
        )

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        message = HumanMessage(content=[
            {"type": "text", "text": "Please extract all the text content from this image. This is a student's homework. Only return the text you see, do not add any commentary."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
        ])

        response = vision_llm.invoke([message])
        return response.content
    except Exception as e:
        logger.error(f"Failed to extract text from image: {e}")
        return ""


def read_text_file(file_path: str) -> str:
    """读取文本文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read text file: {e}")
            return ""
    except Exception as e:
        logger.error(f"Failed to read text file: {e}")
        return ""


def read_image_file(image_path: str) -> str:
    """从图片文件中提取文本（使用多模态 LLM）"""
    try:
        return extract_text_from_image(image_path)
    except Exception as e:
        logger.error(f"Failed to read image file: {e}")
        return ""


def read_pdf_file(pdf_path: str) -> str:
    """从 PDF 文件中提取文本内容"""
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader

        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        return "\n\n".join(text_parts) if text_parts else ""
    except ImportError:
        logger.error("pypdf/PyPDF2 not installed. Please run: pip install pypdf")
        return ""
    except Exception as e:
        logger.error(f"Failed to read PDF file: {e}")
        return ""


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


def run_tui(llm):
    """Terminal interactive mode - 作业生成器"""
    print("=== AI Homework Generator for UK Primary School Students (Year 1-6) ===\n")
    print(f"Using Model: AGICTO ({LLM_MODEL})\n")

    # 步骤1: 选择年级
    print("\nStep 1: Select Year Group\n")
    year_choices = {}
    for sid, profile in SAMPLE_STUDENT_PROFILES.items():
        yg = profile["year_group"]
        year_choices[str(yg)] = sid
        print(f"  {yg}. Year {yg} (Age {profile['age']}, {profile['key_stage']}, {profile['english_level']})")

    year_input = input("\nEnter year group (1-6): ").strip()
    student_id = year_choices.get(year_input)
    if not student_id:
        print("Invalid selection, defaulting to Year 1")
        student_id = "student1"

    profile = SAMPLE_STUDENT_PROFILES[student_id]
    hw_info = get_homework_time_by_age(profile["year_group"])
    print(f"\nSelected: Year {profile['year_group']}, Age {profile['age']}, {profile['key_stage']}")
    print(f"Recommended Daily Homework: {hw_info['daily_homework_minutes']} minutes")
    print(f"Focus: {hw_info['focus_areas']}")

    # 步骤2: 选择科目 (多选)
    print("\nStep 2: Select Subjects (enter numbers separated by commas)\n")
    for i, subject in enumerate(UK_PRIMARY_SUBJECTS, 1):
        print(f"  {i}. {subject}")

    subject_input = input("\nEnter subject numbers (e.g., 1,2,3): ").strip()
    selected_indices = []
    for part in subject_input.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(UK_PRIMARY_SUBJECTS):
                selected_indices.append(idx)

    if not selected_indices:
        print("No valid subjects selected, defaulting to English")
        selected_indices = [0]

    selected_subjects = [UK_PRIMARY_SUBJECTS[i] for i in selected_indices]
    print(f"\nSelected Subjects: {', '.join(selected_subjects)}")

    # 步骤3: 生成作业
    print(f"\n{'='*50}")
    print("Generating homework...")
    print(f"{'='*50}\n")

    start_time = datetime.now()
    profile = SAMPLE_STUDENT_PROFILES[student_id]
    result = generate_homework_with_custom_profile(profile, selected_subjects, llm)
    end_time = datetime.now()

    print("\n" + "=" * 50)
    print("=== Homework Generated ===")
    print("=" * 50 + "\n")
    print(result)

    process_time = (end_time - start_time).total_seconds()
    print(f"\nTotal generation time: {process_time:.2f} seconds")


def run_gui(llm):
    """Web interface mode - 作业生成器（儿童友好界面）"""
    try:
        import gradio as gr

        # 加载外部 CSS 和 HTML 模板
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        css_path = os.path.join(project_dir, "static", "styles.css")
        html_path = os.path.join(project_dir, "templates", "gui_template.html")

        with open(css_path, 'r', encoding='utf-8') as f:
            cute_theme = f.read()

        with open(html_path, 'r', encoding='utf-8') as f:
            main_title_html = f.read()

        def parse_profile_from_natural_language(description: str) -> Optional[Dict[str, Any]]:
            """用 LLM 将自然语言描述解析为学生档案，并从中提取科目"""
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

        def process_homework(profile, subject_choices):
            """根据 student profile 和 选定科目生成作业"""
            yield '<div class="homework-container"><p class="homework-placeholder">Generating homework... Please wait a moment.</p></div>'

            if not subject_choices:
                yield "**Oops!** Please pick at least one subject first!"
                return

            if not profile:
                yield "**Hmm,** please check your student profile inputs!"
                return

            try:
                homework = generate_homework_with_custom_profile(profile, subject_choices, llm)
                html_page = display_homeworks(homework)
                yield html_page
            except Exception as e:
                yield f"**Oh no!** Something went wrong: {str(e)}"

        def process_custom_homework(profile_description, subject_choices):
            """方式1: 使用自然语言描述的学生档案生成作业"""
            profile = parse_profile_from_natural_language(profile_description)

            if not subject_choices:
                if profile and profile.get("extracted_subjects"):
                    subject_choices = profile["extracted_subjects"]
                elif profile and profile.get("learning_goals"):
                    subject_choices = extract_subjects_from_prompt(profile["learning_goals"], llm)
                    print(f"[Extracted Subjects from Learning Goals] {', '.join(subject_choices)}")
                else:
                    print("[Warning] No subjects found in input. Using default subjects: Math")
                    subject_choices = ["Math"]

            yield from process_homework(profile, subject_choices)

        def process_quick_homework(year_choice, subject_choices):
            """方式2: 使用预设档案生成作业"""
            yield '<div class="homework-container"><p class="homework-placeholder">Generating homework... Please wait a moment.</p></div>'

            if not subject_choices:
                yield "Oops! Please pick at least one subject first!"
                return

            try:
                year_num = int(year_choice.replace("Year", "").strip())
            except (ValueError, AttributeError):
                yield "Hmm, that year doesn't seem right. Try again!"
                return

            student_id = f"student{year_num}"
            if student_id not in SAMPLE_STUDENT_PROFILES:
                yield f"Oops! No student found for Year {year_num}."
                return

            profile = SAMPLE_STUDENT_PROFILES[student_id]
            yield from process_homework(profile, subject_choices)

        # 构建年级选项
        year_options = []
        for profile in SAMPLE_STUDENT_PROFILES.values():
            yg = profile["year_group"]
            year_options.append(f"Year {yg}")

        cute_subjects = UK_PRIMARY_SUBJECTS

        # 存储生成的作业内容
        last_generated_homework = {"content": ""}

        def cp_wrapper_with_storage(profile_desc, subject_choices):
            """包装 custom homework 生成，存储作业内容"""
            profile = parse_profile_from_natural_language(profile_desc)

            if not subject_choices:
                if profile and profile.get("extracted_subjects"):
                    subject_choices = profile["extracted_subjects"]
                elif profile and profile.get("learning_goals"):
                    subject_choices = extract_subjects_from_prompt(profile["learning_goals"], llm)
                else:
                    subject_choices = ["Math"]

            if not profile:
                yield "**Hmm,** please check your student profile inputs!"
                return

            if not subject_choices:
                yield "**Oops!** Please pick at least one subject first!"
                return

            try:
                homework = generate_homework_with_custom_profile(profile, subject_choices, llm)
                html_page = display_homeworks(homework)
                homework_texts = [h.get('homework', '') for h in homework if isinstance(h, dict)]
                last_generated_homework["content"] = "\n\n".join(homework_texts)
                yield html_page
            except Exception as e:
                yield f"**Oh no!** Something went wrong: {str(e)}"

        def qs_wrapper_with_storage(year_choice, subject_choices):
            """包装 quick homework 生成，存储作业内容"""
            if not subject_choices:
                yield "Oops! Please pick at least one subject first!"
                return

            try:
                year_num = int(year_choice.replace("Year", "").strip())
            except (ValueError, AttributeError):
                yield "Hmm, that year doesn't seem right. Try again!"
                return

            student_id = f"student{year_num}"
            if student_id not in SAMPLE_STUDENT_PROFILES:
                yield f"Oops! No student found for Year {year_num}."
                return

            profile = SAMPLE_STUDENT_PROFILES[student_id]

            if not subject_choices:
                yield "Oops! Please pick at least one subject first!"
                return

            try:
                homework = generate_homework_with_custom_profile(profile, subject_choices, llm)
                html_page = display_homeworks(homework)
                homework_texts = [h.get('homework', '') for h in homework if isinstance(h, dict)]
                last_generated_homework["content"] = "\n\n".join(homework_texts)
                yield html_page
            except Exception as e:
                yield f"**Oh no!** Something went wrong: {str(e)}"

        def switch_to_check_with_homework():
            """切换到 check tab 并填充作业内容"""
            return gr.update(selected="check_homework_tab"), last_generated_homework.get("content", "")

        with gr.Blocks(
                title="Homework Magic - UK Primary School",
                css=cute_theme
        ) as demo:
            gr.HTML(f"<style>{cute_theme}</style>")
            gr.HTML(main_title_html)

            with gr.Tabs() as tabs:

                # ====== Tab 1: Custom Student Profile ======
                DEFAULT_PROFILE_EXAMPLE = (
                    "Ana is a 7-year-old student in Year 2 in London. "
                    "She has a particular interest in mathematics. "
                    "Ana is eager to learn both Chinese and Spanish and is committed to spending 15–30 minutes each day practicing these languages as well as developing her math skills. "
                )

                with gr.Tab("Custom Profile", id="custom_profile_tab"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.HTML('<div class="step-header">Describe the Student</div>')
                            cp_profile = gr.Textbox(
                                label="",
                                lines=8,
                                max_lines=20,
                                placeholder=DEFAULT_PROFILE_EXAMPLE,
                                value=DEFAULT_PROFILE_EXAMPLE,
                                container=False
                            )

                            gr.HTML('<div class="step-header">Choose Your Subjects</div>')
                            cp_subjects = gr.CheckboxGroup(
                                choices=cute_subjects,
                                label="",
                                value=None,
                                container=False
                            )

                            cp_gen_btn = gr.Button("Generate My Homework!", variant="primary")
                            cp_check_btn = gr.Button("Check My Homework!", variant="secondary")

                        with gr.Column(scale=2):
                            gr.HTML('<div class="step-header">Your Homework</div>')
                            cp_output = gr.HTML(
                                value='<div class="homework-container"><p class="homework-placeholder">Your custom homework will appear here!</p></div>')

                # ====== Tab 2: Quick Select ======
                with gr.Tab("Quick Select", id="quick_select_tab"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.HTML('<div class="step-header">Pick Your Year</div>')
                            qs_year = gr.Radio(choices=year_options, label="", value=year_options[0], container=False)

                            gr.HTML('<div class="step-header">Choose Your Subjects</div>')
                            qs_subjects = gr.CheckboxGroup(choices=cute_subjects, label="", value=[cute_subjects[0]],
                                                           container=False)

                            qs_btn = gr.Button("Generate My Homework!", variant="primary")
                            qs_check_btn = gr.Button("Check My Homework!", variant="secondary")

                        with gr.Column(scale=2):
                            gr.HTML('<div class="step-header">Your Homework</div>')
                            qs_output = gr.HTML(
                                value='<div class="homework-container"><p class="homework-placeholder">Your quick homework will appear here!</p></div>')

                # ====== Tab 3: Check My Homework ======
                with gr.Tab("Check My Homework", id="check_homework_tab"):
                    gr.HTML('<div class="step-header">Check My Homework</div>')

                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.HTML('<div class="step-header">Upload Your Work</div>')
                            take_photo_btn = gr.Button("Take Photo", variant="secondary")
                            upload_file_btn = gr.Button("Upload File", variant="secondary")

                            with gr.Row(visible=False) as photo_input_row:
                                photo_input = gr.Image(label="Take a photo or upload an image", sources=["webcam", "upload"],
                                                       type="filepath")

                            with gr.Row(visible=False) as file_input_row:
                                file_input = gr.File(label="Upload your homework file")

                            gr.HTML('<div class="step-header">Choose Your Subject</div>')
                            check_subject = gr.Radio(
                                choices=cute_subjects,
                                label="",
                                value="Math",
                                container=False
                            )

                            gr.HTML('<div class="step-header">Homework Assignment (Optional)</div>')
                            check_assignment = gr.Textbox(
                                label="What was the homework assignment? (Optional)",
                                lines=4,
                                placeholder="Paste the original homework question here if available...",
                                value=""
                            )

                            check_btn = gr.Button("Submit for Review", variant="primary")

                        with gr.Column(scale=2):
                            gr.HTML('<div class="step-header">Teacher Feedback</div>')
                            check_result = gr.Markdown(value='Upload your homework to get feedback!')

                    def show_photo_input():
                        return gr.update(visible=True), gr.update(visible=False)

                    def show_file_input():
                        return gr.update(visible=False), gr.update(visible=True)

                    def handle_submit(photo, file, subject, assignment):
                        """批阅上传的作业"""
                        yield "**Reviewing your homework...** Please wait a moment."

                        if not photo and not file:
                            yield "**Please upload a photo or file first.**"
                            return

                        student_work = ""
                        image_path = None

                        if photo:
                            logger.info(f"[Review] Reviewing image directly: {photo}")
                            image_path = photo
                        elif file:
                            file_ext = os.path.splitext(file.name)[1].lower()
                            if file_ext in ['.txt', '.md', '.csv']:
                                student_work = read_text_file(file.name)
                            elif file_ext in ['.jpg', '.jpeg', '.png', '.heic']:
                                logger.info(f"[Review] Reviewing image directly: {file.name}")
                                image_path = file.name
                            elif file_ext in ['.pdf']:
                                student_work = read_pdf_file(file.name)
                            else:
                                yield f"**Unsupported file type: {file_ext}**. Please upload .txt, .md, .csv, .pdf files, or take a photo of your homework."
                                return

                            if student_work and not image_path:
                                if not student_work:
                                    yield "**Failed to read the file content. Please check the file and try again.**"
                                    return

                        student_profile = {
                            "description": "UK Primary School student",
                            "year_group": 3,
                            "age": 7,
                        }

                        logger.info(f"[Review] Reviewing {subject} homework...")

                        if image_path:
                            try:
                                with open(image_path, "rb") as f:
                                    image_data = base64.b64encode(f.read()).decode("utf-8")

                                review_prompt = ChatPromptTemplate.from_messages([
                                    ("system", """You are a UK primary school teacher reviewing a student's homework.

Please:
1. Analyze the student's work shown in the image
2. Check for correctness in the subject: {subject}
3. Provide encouraging feedback
4. Point out any mistakes and explain the correct answers
5. Give constructive suggestions for improvement

Be warm, encouraging, and age-appropriate in your feedback."""),
                                    ("human", [
                                        {"type": "text", "text": """Please review this student's homework.

Subject: {subject}
Student Profile: {student_profile}
Homework Assignment (if provided): {assignment}

Provide detailed feedback with:
- What the student did well
- Areas that need improvement
- Correct answers for any mistakes
- Encouraging words"""},
                                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,{image_data}"}}
                                    ])
                                ])

                                review_chain = review_prompt | llm | StrOutputParser()
                                review = review_chain.invoke({
                                    "subject": subject,
                                    "student_profile": json.dumps(student_profile, ensure_ascii=False, indent=2),
                                    "assignment": assignment if assignment else "Not provided",
                                    "image_data": image_data
                                })
                                yield review
                            except Exception as e:
                                logger.error(f"[Review] Failed to review image: {e}")
                                yield f"**Failed to review the image:** {str(e)}"
                        else:
                            review = review_uploaded_homework(student_profile, subject, student_work, assignment, llm)
                            yield review

                    take_photo_btn.click(
                        fn=show_photo_input,
                        outputs=[photo_input_row, file_input_row]
                    )

                    upload_file_btn.click(
                        fn=show_file_input,
                        outputs=[photo_input_row, file_input_row]
                    )

                    check_btn.click(
                        fn=handle_submit,
                        inputs=[photo_input, file_input, check_subject, check_assignment],
                        outputs=[check_result]
                    )

                    # Event handlers
                    cp_gen_btn.click(
                        fn=cp_wrapper_with_storage,
                        inputs=[cp_profile, cp_subjects],
                        outputs=[cp_output]
                    )

                    cp_check_btn.click(
                        fn=switch_to_check_with_homework,
                        outputs=[tabs, check_assignment]
                    )

                    qs_btn.click(
                        fn=qs_wrapper_with_storage,
                        inputs=[qs_year, qs_subjects],
                        outputs=[qs_output]
                    )

                    qs_check_btn.click(
                        fn=switch_to_check_with_homework,
                        outputs=[tabs, check_assignment]
                    )

        demo.launch(share=True)

    except ImportError:
        logger.warning("gradio not installed. Please run: pip install gradio")
        logger.warning("Switching to terminal interactive mode...")
        run_tui(llm)
