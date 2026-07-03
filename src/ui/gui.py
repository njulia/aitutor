#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gradio Web 界面模块

提供儿童友好的 Gradio Web 界面，支持自定义学生档案、快速选择、
11+ 备考和作业批改功能。
"""

import os
import json
import base64
import logging
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.models import UK_PRIMARY_SUBJECTS, ELEVEN_PLUS_SUBJECTS, SAMPLE_STUDENT_PROFILES
from src.homework_generator import extract_subjects_from_prompt
from src.homework_manager import (
    generate_homework_with_custom_profile,
    review_uploaded_homework,
)
from src.file_utils import read_text_file, read_pdf_file
from src.ui.shared import display_homeworks, parse_profile_from_natural_language

logger = logging.getLogger(__name__)


def run_gui(llm):
    """Web interface mode - 作业生成器（儿童友好界面）"""
    try:
        import gradio as gr
    except ImportError:
        logger.warning("gradio not installed. Please run: pip install gradio")
        logger.warning("Switching to terminal interactive mode...")
        return

    # 加载外部 CSS 和 HTML 模板
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    css_path = os.path.join(project_dir, "static", "styles.css")
    html_path = os.path.join(project_dir, "templates", "gui_template.html")
    radio_fix_path = os.path.join(project_dir, "templates", "gui_radio_fix.html")
    seo_head_path = os.path.join(project_dir, "templates", "seo_head.html")

    with open(css_path, 'r', encoding='utf-8') as f:
        cute_theme = f.read()

    with open(html_path, 'r', encoding='utf-8') as f:
        main_title_html = f.read()

    with open(radio_fix_path, 'r', encoding='utf-8') as f:
        radio_fix_html = f.read()

    with open(seo_head_path, 'r', encoding='utf-8') as f:
        seo_head_html = f.read()

    # ========== 业务处理函数 ==========

    def process_homework(profile, subject_choices):
        """根据 student profile 和选定科目生成作业"""
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

    def resolve_subjects(profile, subject_choices):
        """解析科目选择：优先用户选择，其次从档案中提取，最后用 LLM 推断"""
        if subject_choices:
            return subject_choices

        if profile and profile.get("extracted_subjects"):
            return profile["extracted_subjects"]

        if profile and profile.get("learning_goals"):
            subjects = extract_subjects_from_prompt(profile["learning_goals"], llm)
            print(f"[Extracted Subjects from Learning Goals] {', '.join(subjects)}")
            return subjects

        print("[Warning] No subjects found in input. Using default subjects: Maths")
        return ["Maths"]

    def process_custom_homework(profile_description, subject_choices):
        """方式1: 使用自然语言描述的学生档案生成作业"""
        profile = parse_profile_from_natural_language(profile_description, llm)
        subjects = resolve_subjects(profile, subject_choices)
        yield from process_homework(profile, subjects)

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

    def save_homework_to_session(homework, session_state, profile, subject):
        """将作业内容保存到 session 状态"""
        doc_id = [h.get('doc_id', '') for h in homework if isinstance(h, dict)]
        homework_content = [h.get('homework', '') for h in homework if isinstance(h, dict)]
        session_state["doc_id"] = doc_id
        session_state["content"] = "\n\n".join(homework_content)
        session_state["year_group"] = profile.get("year_group", -1)
        session_state["subject"] = subject

    def cp_wrapper_with_storage(profile_desc, subject_choices, session_state):
        """Custom Profile: 生成作业并存储到 session"""
        profile = parse_profile_from_natural_language(profile_desc, llm)
        subjects = resolve_subjects(profile, subject_choices)

        if not profile:
            yield "**Hmm,** please check your student profile inputs!", session_state
            return

        if not subjects:
            yield "**Oops!** Please pick at least one subject first!", session_state
            return

        try:
            homework = generate_homework_with_custom_profile(profile, subjects, llm)
            html_page = display_homeworks(homework)
            save_homework_to_session(homework, session_state, profile, subjects[0])
            yield html_page, session_state
        except Exception as e:
            yield f"**Oh no!** Something went wrong: {str(e)}", session_state

    def qs_wrapper_with_storage(year_choice, subject_choice, session_state):
        """Quick Select: 生成作业并存储到 session"""
        if not subject_choice:
            yield "Oops! Please pick a subject first!", session_state
            return

        try:
            year_num = int(year_choice.replace("Year", "").strip())
        except (ValueError, AttributeError):
            yield "Hmm, that year doesn't seem right. Try again!", session_state
            return

        student_id = f"student{year_num}"
        if student_id not in SAMPLE_STUDENT_PROFILES:
            yield f"Oops! No student found for Year {year_num}.", session_state
            return

        profile = SAMPLE_STUDENT_PROFILES[student_id]

        try:
            homework = generate_homework_with_custom_profile(profile, [subject_choice], llm)
            html_page = display_homeworks(homework)
            save_homework_to_session(homework, session_state, profile, subject_choice)
            yield html_page, session_state
        except Exception as e:
            yield f"**Oh no!** Something went wrong: {str(e)}", session_state

    def ep_wrapper_with_storage(profile_desc, subject_choices, session_state):
        """Eleven Plus: 生成作业并存储到 session"""
        profile = parse_profile_from_natural_language(profile_desc, llm)
        subjects = resolve_subjects(profile, subject_choices)

        if not profile:
            yield "**Hmm,** please check your student profile inputs!", session_state
            return

        if not subjects:
            yield "**Oops!** Please pick at least one subject first!", session_state
            return

        try:
            homework = generate_homework_with_custom_profile(profile, subjects, llm)
            html_page = display_homeworks(homework)
            save_homework_to_session(homework, session_state, profile, subjects[0])
            yield html_page, session_state
        except Exception as e:
            yield f"**Oh no!** Something went wrong: {str(e)}", session_state

    def combine_questions_with_answers(homework_content: str, student_answers: str) -> str:
        """将作业题目和学生答案逐对组合，格式为 question: xxx / answer: xxx"""
        questions = [line.strip() for line in homework_content.strip().split('\n') if line.strip()]
        questions = questions[1:]  # 移除首行（通常是标题）
        answers = [line.strip() for line in student_answers.strip().split('\n') if line.strip()]

        combined_lines = []
        max_len = max(len(questions), len(answers))
        for i in range(max_len):
            q = questions[i] if i < len(questions) else ""
            a = answers[i] if i < len(answers) else ""
            if q and a:
                combined_lines.append(f"question: {q}\nanswer: {a}")
            elif q:
                logger.warning(f"Missing answer for question: {q}")
            elif a:
                logger.warning(f"Missing question for answer: {a}")

        return '\n\n'.join(combined_lines)

    def switch_to_check_with_homework(session_state, student_answers):
        """切换到 check tab 并填充当前 session 的作业内容和学生答案"""
        session_state["student_answers"] = student_answers

        homework_content = session_state.get("content", "")
        if homework_content and student_answers:
            combined_assignment = combine_questions_with_answers(homework_content, student_answers)
        elif homework_content:
            combined_assignment = homework_content
        else:
            combined_assignment = student_answers

        return gr.update(selected="check_homework_tab"), combined_assignment

    def handle_submit(photo, file, subject, homework, session_state):
        """批阅上传的作业"""
        yield "**Reviewing your homework...** Please wait a moment."

        student_answers = session_state.get("student_answers", "")
        student_work = ""
        image_path = None

        # 如果用户在答案框中输入了答案，直接使用
        if student_answers:
            student_work = student_answers
            logger.info("[Review] Using student typed answers for review")

        if not student_work:
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

        if not student_work and not image_path:
            yield "**Please enter your answers or upload a photo/file first.**"
            return

        student_profile = {
            "description": "UK Primary School student",
            "year_group": session_state.get("year_group", 3),
            "age": 7,
        }

        metadata_subject = session_state.get("subject", subject)
        logger.info(f"[Review] Reviewing {subject} homework...")

        if image_path:
            yield from _review_image_homework(image_path, subject, student_profile, homework)
        else:
            review = review_uploaded_homework(
                student_profile=student_profile,
                subject=metadata_subject,
                homework=homework,
                doc_id=session_state.get("doc_id", ""),
                llm=llm,
            )
            yield review

    def _review_image_homework(image_path, subject, student_profile, homework):
        """使用多模态 LLM 批阅图片格式的作业"""
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
Homework Assignment (if provided): {homework}

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
                "homework": homework if homework else "Not provided",
                "image_data": image_data
            })
            yield review
        except Exception as e:
            logger.error(f"[Review] Failed to review image: {e}")
            yield f"**Failed to review the image:** {str(e)}"

    # ========== 构建 UI ==========

    year_options = [
        f"Year {p['year_group']}" for p in SAMPLE_STUDENT_PROFILES.values()
    ]

    def init_session_state():
        """初始化 session 状态"""
        return {"content": ""}

    def show_photo_input():
        return gr.update(visible=True), gr.update(visible=False)

    def show_file_input():
        return gr.update(visible=False), gr.update(visible=True)

    _build_gradio_app(
        gr, cute_theme, main_title_html, radio_fix_html, seo_head_html,
        year_options, UK_PRIMARY_SUBJECTS,
        init_session_state,
        cp_wrapper_with_storage,
        qs_wrapper_with_storage,
        ep_wrapper_with_storage,
        switch_to_check_with_homework,
        handle_submit,
        show_photo_input,
        show_file_input,
    )


def _build_gradio_app(
    gr, cute_theme, main_title_html, radio_fix_html, seo_head_html,
    year_options, UK_PRIMARY_SUBJECTS,
    init_session_state,
    cp_wrapper, qs_wrapper, ep_wrapper,
    switch_to_check,
    handle_submit,
    show_photo_input, show_file_input,
):
    """构建并启动 Gradio 应用"""

    DEFAULT_PROFILE_EXAMPLE = (
        "Ana is a 7-year-old student in Year 2 in London. "
        "She has a particular interest in mathematics. "
        "Ana is eager to learn both Chinese and Spanish and is committed to spending 15-30 minutes each day practicing these languages as well as developing her maths skills. "
    )

    DEFAULT_11PLUS_PROFILE = (
        "Ana is a 9 years old student in Year 5 in London."
        "She is a strong student with a solid foundation in mathematics and numerical reasoning."
        "She has Analytical mindset, aided by an early interest in language learning (bilingual/multilingual exposure)."
        "Exam Target: 11+ Grammar School Entrance Exams (focusing on GL Assessment style, covering Mathematics, English, Verbal Reasoning, and Non-Verbal Reasoning)"
        "Academic Strengths:"
        "Development Areas:"
        "Building advanced vocabulary and understanding words in unfamiliar contexts."
        "Mastering specific verbal reasoning question types (e.g., synonyms, antonyms, code-breaking)."
        "Improving speed and accuracy under timed conditions."
        "Study Routine: 45-60 minutes daily, broken down into 15-20 minute focused blocks."
    )

    with gr.Blocks(
            title="Homework Magic — AI Homework Generator & Marker for UK Primary School (KS1–KS2, 11+)",
            css=cute_theme,
            theme=gr.themes.Default(),
            head=seo_head_html,
    ) as demo:
        gr.HTML(f"<style>{cute_theme}</style>")
        gr.HTML(main_title_html)
        gr.HTML(radio_fix_html)

        session_state = gr.State(value=init_session_state())

        with gr.Tabs(elem_classes=["main-tabs"]) as tabs:

            # ====== Tab 1: Custom Student Profile ======
            with gr.Tab("Custom Profile", id="custom_profile_tab"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.HTML('<h2 class="step-header">Describe the Student</h2>')
                        cp_profile = gr.Textbox(
                            label="", lines=8, max_lines=20,
                            placeholder=DEFAULT_PROFILE_EXAMPLE,
                            value=DEFAULT_PROFILE_EXAMPLE, container=False
                        )
                    with gr.Column(scale=2):
                        gr.HTML('<h2 class="step-header">Choose Your Subjects</h2>')
                        cp_subjects = gr.CheckboxGroup(
                            choices=UK_PRIMARY_SUBJECTS, label="", value=None, container=False
                        )
                    with gr.Column(scale=1):
                        gr.HTML('<div class="step-header"></div>')
                        cp_gen_btn = gr.Button("Generate My Homework!", variant="primary", elem_classes=["btn-blue"])
                        cp_check_btn = gr.Button("Check My Homework!", variant="secondary")

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Your Homework</h2>')
                        cp_output = gr.HTML(
                            value='<div class="homework-container"><p class="homework-placeholder">Your custom homework will appear here!</p></div>',
                            elem_classes=["homework-output"])
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Your Answers</h2>')
                        cp_answer_input = gr.Textbox(
                            label="Enter your answers here", lines=6, max_lines=15,
                            placeholder="Type your answers here, one per line or in any format you prefer...",
                            value=""
                        )

            # ====== Tab 2: Quick Select ======
            with gr.Tab("Quick Select", id="quick_select_tab"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Pick Your Year</h2>')
                        qs_year = gr.Radio(
                            choices=year_options, label="", value=year_options[1], container=False
                        )
                    with gr.Column(scale=2):
                        gr.HTML('<h2 class="step-header">Choose Your Subjects</h2>')
                        qs_subjects = gr.Radio(
                            choices=UK_PRIMARY_SUBJECTS, label="", value=UK_PRIMARY_SUBJECTS[0], container=False
                        )
                    with gr.Column(scale=1):
                        gr.HTML('<div class="step-header"></div>')
                        qs_btn = gr.Button("Generate My Homework!", variant="primary", elem_classes=["btn-blue"])
                        qs_check_btn = gr.Button("Check My Homework!", variant="secondary")

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Your Homework</h2>')
                        qs_output = gr.HTML(
                            value='<div class="homework-container"><p class="homework-placeholder">Your quick homework will appear here!</p></div>',
                            elem_classes=["homework-output"])
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Your Answers</h2>')
                        qs_answer_input = gr.Textbox(
                            label="Enter your answers here", lines=6, max_lines=15,
                            placeholder="Type your answers here, one per line or in any format you prefer...",
                            value=""
                        )

            # ====== Tab 3: Eleven Plus ======
            with gr.Tab("Eleven Plus", id="eleven_plus_tab"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Describe the Student</h2>')
                        ep_profile = gr.Textbox(
                            label="", lines=8, max_lines=20,
                            placeholder=DEFAULT_11PLUS_PROFILE,
                            value=DEFAULT_11PLUS_PROFILE, container=False
                        )
                    with gr.Column(scale=2):
                        gr.HTML('<h2 class="step-header">Choose Your Subjects</h2>')
                        ep_subjects = gr.CheckboxGroup(
                            choices=ELEVEN_PLUS_SUBJECTS, label="", value='Maths', container=False
                        )
                    with gr.Column(scale=1):
                        gr.HTML('<div class="step-header"></div>')
                        ep_gen_btn = gr.Button("Generate My Homework!", variant="primary", elem_classes=["btn-blue"])
                        ep_check_btn = gr.Button("Check My Homework!", variant="secondary")

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Your Homework</h2>')
                        ep_output = gr.HTML(
                            value='<div class="homework-container"><p class="homework-placeholder">Your custom homework will appear here!</p></div>',
                            elem_classes=["homework-output"])
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Your Answers</h2>')
                        ep_answer_input = gr.Textbox(
                            label="Enter your answers here", lines=6, max_lines=15,
                            placeholder="Type your answers here, one per line or in any format you prefer...",
                            value=""
                        )

            # ====== Tab 4: Check My Homework ======
            with gr.Tab("Check My Homework", id="check_homework_tab"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML('<h2 class="step-header">Upload Your Work</h2>')
                        take_photo_btn = gr.Button("Take Photo", variant="secondary")
                        upload_file_btn = gr.Button("Upload File", variant="secondary")

                        with gr.Row(visible=False) as photo_input_row:
                            photo_input = gr.Image(
                                label="Take a photo or upload an image",
                                sources=["webcam", "upload"], type="filepath"
                            )

                        with gr.Row(visible=False) as file_input_row:
                            file_input = gr.File(label="Upload your homework file")

                        gr.HTML('<h2 class="step-header">Choose Your Subjects</h2>')
                        check_subject = gr.Radio(
                            choices=UK_PRIMARY_SUBJECTS, label="", value="Maths", container=False
                        )

                        gr.HTML('<h2 class="step-header">Homework Completed (Optional)</h2>')
                        homework_completed = gr.Textbox(
                            label="What was the homework completed? (Optional)",
                            lines=4,
                            placeholder="Paste the homework completed here if available...",
                            value=""
                        )

                        check_btn = gr.Button("Submit for Review", variant="primary", elem_classes=["btn-blue"])

                    with gr.Column(scale=2):
                        gr.HTML('<h2 class="step-header">Teacher Feedback</h2>')
                        check_result = gr.Markdown(value='Upload your homework to get feedback!')

            # ========== 事件绑定 ==========

            take_photo_btn.click(fn=show_photo_input, outputs=[photo_input_row, file_input_row])
            upload_file_btn.click(fn=show_file_input, outputs=[photo_input_row, file_input_row])

            check_btn.click(
                fn=handle_submit,
                inputs=[photo_input, file_input, check_subject, homework_completed, session_state],
                outputs=[check_result]
            )

            cp_gen_btn.click(
                fn=cp_wrapper,
                inputs=[cp_profile, cp_subjects, session_state],
                outputs=[cp_output, session_state]
            )
            cp_check_btn.click(
                fn=switch_to_check,
                inputs=[session_state, cp_answer_input],
                outputs=[tabs, homework_completed]
            )

            qs_btn.click(
                fn=qs_wrapper,
                inputs=[qs_year, qs_subjects, session_state],
                outputs=[qs_output, session_state]
            )
            qs_check_btn.click(
                fn=switch_to_check,
                inputs=[session_state, qs_answer_input],
                outputs=[tabs, homework_completed]
            )

            ep_gen_btn.click(
                fn=ep_wrapper,
                inputs=[ep_profile, ep_subjects, session_state],
                outputs=[ep_output, session_state]
            )
            ep_check_btn.click(
                fn=switch_to_check,
                inputs=[session_state, ep_answer_input],
                outputs=[tabs, homework_completed]
            )

    demo.launch(share=True)
