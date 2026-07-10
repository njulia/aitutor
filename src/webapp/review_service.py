"""Homework review, explanation and targeted-practice services."""
import json
import logging
import re
from datetime import datetime
from typing import Optional

from .question_utils import (
    _parse_student_answers_to_map,
    _split_homework_into_questions,
    normalize_question,
)

logger = logging.getLogger(__name__)

def review_homework(homework_content: str, student_answers: str, subject: str, profile=None,
                    is_tutor_mode: bool = False, homework_doc_id: str = None,
                    is_eleven_plus: bool = False, question_index: Optional[int] = None, llm_client=None):
    """批改作业 - 优先从 RAG 读取正确答案，否则使用 LLM 生成"""
    from src.llm_client import format_prompt, build_messages
    from src.prompts import REVIEW_HOMEWORK_PROMPT, REVIEW_TUTOR_QUESTION_PROMPT
    from src.cache import review_cache, make_cache_key

    if profile is None:
        profile = {"year_group": 3, "age": 7}

    # Determine which prompt to use
    prompt_template = REVIEW_TUTOR_QUESTION_PROMPT if is_tutor_mode else REVIEW_HOMEWORK_PROMPT

    # Cache key needs to differentiate between tutor mode and homework mode
    cache_key_prefix = "review_tutor" if is_tutor_mode else "review_homework"
    cache_key = make_cache_key(
        cache_key_prefix,
        subject,
        str(profile.get("year_group", 3)),
        f"qidx={question_index}|{homework_content[:200]}",
        student_answers[:200],
    )
    cached = review_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中批改缓存 (%s)", cache_key_prefix)
        return {"success": True, "review": cached, "from_cache": True}

    try:
        # 1. 优先从 RAG 中读取正确答案（零 LLM 调用）
        rag_answers = None
        correct_answers_section = ""
        generated_table_markdown = ""  # New variable for the Python-generated table

        # Default feedback instruction (LLM will generate this part)
        # This will be used by the prompt template for the LLM's general feedback.
        feedback_instruction_for_llm = """- What the student did well
                    - Areas that need correction or improvement
                    - Specific feedback for each task"""

        if homework_doc_id:
            try:
                if is_eleven_plus:
                    from src.elevenplus.elevenplus_rag import search_homework_answers as _search_answers
                else:
                    from src.homework_rag import search_homework_answers as _search_answers
                
                raw_rag_answers = _search_answers(homework_doc_id)
                
                # Split homework_content into questions (needed for pairing and mapping)
                parsed_questions = _split_homework_into_questions(homework_content, subject)

                processed_rag_answers = []
                target_question = (
                    parsed_questions[0].get("full_content")
                    or parsed_questions[0].get("content")
                    or homework_content
                ).strip() if parsed_questions else homework_content.strip()

                if isinstance(raw_rag_answers, list) and all(isinstance(item, str) for item in raw_rag_answers):
                    if is_tutor_mode and question_index is not None:
                        if 0 <= question_index < len(raw_rag_answers):
                            processed_rag_answers.append({
                                "question": target_question,
                                "answer": raw_rag_answers[question_index].strip(),
                            })
                            logger.info("[RAG] Tutor answer selected by question_index=%s.", question_index)
                        else:
                            logger.warning(
                                "[RAG] question_index=%s is outside answer range 0..%s",
                                question_index, len(raw_rag_answers) - 1,
                            )
                    else:
                        for i, q_dict in enumerate(parsed_questions):
                            if i >= len(raw_rag_answers):
                                break
                            processed_rag_answers.append({
                                "question": q_dict.get("full_content", q_dict["content"]).strip(),
                                "answer": raw_rag_answers[i].strip(),
                            })
                    rag_answers = processed_rag_answers

                elif isinstance(raw_rag_answers, list) and all(
                    isinstance(item, dict) and "question" in item and "answer" in item
                    for item in raw_rag_answers
                ):
                    if is_tutor_mode and question_index is not None:
                        if 0 <= question_index < len(raw_rag_answers):
                            processed_rag_answers.append(raw_rag_answers[question_index])
                            logger.info("[RAG] Tutor Q&A selected by question_index=%s.", question_index)
                        else:
                            logger.warning(
                                "[RAG] question_index=%s is outside Q&A range 0..%s",
                                question_index, len(raw_rag_answers) - 1,
                            )

                    # Backward-compatible fallback for older clients that do not send an index,
                    # or for stale indexes after RAG data has changed.
                    if is_tutor_mode and not processed_rag_answers and len(parsed_questions) == 1:
                        target_q = normalize_question(parsed_questions[0]["content"])
                        for item in raw_rag_answers:
                            if normalize_question(str(item["question"])) == target_q:
                                processed_rag_answers.append(item)
                                logger.info("[RAG] Tutor question matched by normalized text fallback.")
                                break
                    elif not is_tutor_mode:
                        processed_rag_answers.extend(raw_rag_answers)

                    rag_answers = processed_rag_answers
                else:
                    logger.warning(
                        "[RAG] Unexpected answer format for doc_id=%s: %s",
                        homework_doc_id, type(raw_rag_answers),
                    )
                    rag_answers = None

                if rag_answers:
                    # 将正确答案和学生答案一起发给 LLM 做简洁对比
                    logger.info("[RAG] Found correct answers for doc_id=%s. Building comparison table.",
                                homework_doc_id)

                    # Extract questions from RAG answers for mapping
                    rag_questions_list = [item["question"].strip() for item in rag_answers]

                    # Heuristically parse student answers and map them to RAG questions for the current subject
                    student_answers_map = _parse_student_answers_to_map(student_answers, subject, rag_questions_list)

                    # Build the table rows
                    table_rows_data = []
                    # Create a mapping from question content (without numbers) to full content (with numbers) if possible
                    # This helps in case student_answers_map used the stripped content
                    content_to_full = {q["content"].strip(): q["full_content"].strip() for q in parsed_questions if "full_content" in q}

                    for rag_item in rag_answers:
                        q_text = rag_item["question"].strip()
                        correct_ans = rag_item["answer"].strip()

                        # Try to get student answer using the full question text (with number)
                        student_ans = student_answers_map.get(q_text)
                        
                        # Fallback: if student_answers_map used stripped text, try that
                        if student_ans is None:
                            # Find the stripped version of q_text if it has a number
                            # This is a bit tricky, but since q_text came from RAG, it likely HAS a number.
                            # We can try to match it against our parsed questions.
                            for p_q in parsed_questions:
                                if p_q.get("full_content", "").strip() == q_text:
                                    student_ans = student_answers_map.get(p_q["content"].strip())
                                    break
                        
                        if student_ans is None:
                            student_ans = "No answer provided"

                        student_ans = student_ans.strip()

                        # Escape pipe characters in answers to avoid breaking markdown table
                        # Determine if correct
                        if subject == "Maths":
                            from src.tools.math_tools import verify_math_answer
                            verification = verify_math_answer(q_text, student_ans, correct_ans)
                            is_correct = verification["is_correct"]
                        else:
                            is_correct = (student_ans.lower() == correct_ans.lower()) # Simple string comparison for now
                        
                        status_icon = "✅" if is_correct else "❌"

                        student_ans_escaped = student_ans.replace('|', '\\|')
                        correct_ans_escaped = correct_ans.replace('|', '\\|')
                        q_text_escaped = q_text.replace('|', '\\|')

                        table_rows_data.append([status_icon, q_text_escaped, student_ans_escaped, correct_ans_escaped])

                    if table_rows_data:
                        table_header = "| Status | Question | Your Answer | Correct Answer |\n|---|---|---|---|\n"
                        table_content = "\n".join(["| " + " | ".join(row) + " |" for row in table_rows_data])
                        generated_table_markdown = f"\n\n## Homework Review Summary\n{table_header}{table_content}\n\n"

                    # The `correct_answers_section` can still be passed to LLM for context

                    correct_answers_text = json.dumps(rag_answers, ensure_ascii=False) if isinstance(rag_answers, (list,
                                                                                                                   dict)) else str(
                        rag_answers)
                    correct_answers_section = f"\n\n## Correct Answers (for LLM context):\n```json\n{correct_answers_text}\n```\n"

                else:
                    logger.info("[Review] No correct answers found in RAG for doc_id=%s. Using LLM for full review.", homework_doc_id)

            except Exception as e:
                logger.warning("[RAG] Failed to retrieve correct answers or build table: %s", e)
                logger.info(
                    "[Review] Falling back to LLM for full review due to RAG error. No comparison table will be generated.")

        prompt_text = format_prompt(
            prompt_template,
            student_profile=str(profile),
            subject=subject,
            day=datetime.now().strftime("%A, %B %d, %Y"),
            homework_content=homework_content,
            student_answer=student_answers,
            correct_answers_section=correct_answers_section,
            feedback_instruction = feedback_instruction_for_llm  # Use the general instruction for LLM
        )
        messages = build_messages(prompt_text)
        llm_result = llm_client.complete(messages)  # Get LLM's general feedback
        # Combine Python-generated table with LLM's response
        final_review_result = generated_table_markdown + llm_result

        # 写入缓存
        review_cache.set(cache_key, final_review_result)

        # 保存进度到数据库 (Only save for full homework sessions, not individual tutor questions)
        if not is_tutor_mode:
            try:
                from src.progress_db import save_homework_session
                # 从 review 文本中提取分数（如 "Score: 7/10" 或 "7/10"）
                score_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+)", llm_result)  # Score is in LLM's part
                score = float(score_match.group(1)) if score_match else None

                student_id = profile.get("student_id", "anonymous")
                save_homework_session(
                    student_id=student_id,
                    subject=subject,
                    year_group=profile.get("year_group", 3),
                    homework_content=homework_content,
                    student_answers=student_answers,  # Original student answers
                    score=score,
                    review_text=final_review_result,  # Save the combined review
                )

            except Exception as db_exc:
                logger.warning("Failed to save progress: %s", db_exc)

        return {"success": True, "review": final_review_result, "from_rag_answers": rag_answers is not None}
    except Exception as exc:
        logger.error("Error reviewing homework: %s", exc)
        return {"success": False, "error": str(exc)}


def explain_deep(homework_content: str, student_answers: str, subject: str,
                 profile=None, review_feedback: str = "", llm_client=None):
    """深度解释作业答案 - 使用 EXPLAIN_DEEP_PROMPT 生成逐步解释、薄弱点分析等"""
    from src.llm_client import format_prompt, build_messages
    from src.prompts import EXPLAIN_DEEP_PROMPT
    from src.cache import explain_cache, make_cache_key

    if profile is None:
        profile = {"year_group": 3, "age": 7}

    # 检查缓存
    cache_key = make_cache_key("explain", subject, str(profile.get("year_group", 3)),
                               homework_content[:200], student_answers[:200])
    cached = explain_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中深度解释缓存")
        return {"success": True, "explanation": cached, "from_cache": True}

    try:
        prompt_text = format_prompt(
            EXPLAIN_DEEP_PROMPT,
            homework_content=homework_content,
            student_answer=student_answers,
            subject=subject,
            student_profile=str(profile),
            review_feedback=review_feedback or "No review feedback available",
            year_group=profile.get("year_group", 3),
            age=profile.get("age", 7),
        )
        messages = build_messages(prompt_text)
        result = llm_client.complete(messages)

        # 写入缓存
        explain_cache.set(cache_key, result)

        return {"success": True, "explanation": result}
    except Exception as exc:
        logger.error("Error in explain_deep: %s", exc)
        return {"success": False, "error": str(exc)}


def improve_practice(homework_content: str, student_answers: str, subject: str,
                     profile=None, review_feedback: str = "", llm_client=None):
    """根据学生的弱项生成针对性练习 - 使用 IMPROVE_PRACTICE_PROMPT"""
    from src.llm_client import format_prompt, build_messages
    from src.prompts import IMPROVE_PRACTICE_PROMPT
    from src.cache import practice_cache, make_cache_key

    if profile is None:
        profile = {"year_group": 3, "age": 7}

    # 检查缓存
    cache_key = make_cache_key("practice", subject, str(profile.get("year_group", 3)),
                               homework_content[:200], student_answers[:200])
    cached = practice_cache.get(cache_key)
    if cached:
        logger.info("[Cache] 命中练习生成缓存")
        return {"success": True, "practice": cached, "from_cache": True}

    try:
        prompt_text = format_prompt(
            IMPROVE_PRACTICE_PROMPT,
            homework_content=homework_content,
            student_answer=student_answers,
            subject=subject,
            student_profile=str(profile),
            review_feedback=review_feedback or "No review feedback available",
            year_group=profile.get("year_group", 3),
            age=profile.get("age", 7),
        )
        messages = build_messages(prompt_text)
        result = llm_client.complete(messages)

        # 写入缓存
        practice_cache.set(cache_key, result)

        return {"success": True, "practice": result}
    except Exception as exc:
        logger.error("Error in improve_practice: %s", exc)
        return {"success": False, "error": str(exc)}
