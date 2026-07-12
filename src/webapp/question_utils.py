from __future__ import annotations

import logging
import re
import uuid
from typing import Dict, List

logger = logging.getLogger(__name__)

def _split_homework_into_questions(homework_content: str, subject: str) -> List[Dict[str, str]]:
    """
    Splits a block of homework content into individual questions.
    Assumes questions are numbered (e.g., 1., 2., (1), (2), or bullet points).
    """
    extracted_questions = []
    
    # Normalize newlines and strip leading/trailing whitespace
    homework_content = homework_content.strip().replace('\r\n', '\n')

    # --- Attempt to split by numbered questions first ---
    # This pattern splits on the start of a new numbered question (e.g., "1. ", "2. ")
    # The capturing group `(\d+\.)` means the delimiter itself will be included in the split list.
    numbered_parts = re.split(r'(?m)^\s*(\d+\.)[\s\xa0]+', homework_content)

    # If the first part is not a delimiter, it's either a header or unnumbered intro.
    # If there are subsequent numbered questions (i.e., len(numbered_parts) > 1),
    # we can assume the first part is a header/intro to be discarded.
    if numbered_parts and numbered_parts[0].strip() and len(numbered_parts) > 1 and not re.match(r'^\s*\d+\.', numbered_parts[0]):
        logger.debug(f"Discarding unnumbered intro/header before first numbered question: '{numbered_parts[0].strip()}'")
        numbered_parts = numbered_parts[1:] # Discard the intro part

    i = 0
    while i < len(numbered_parts):
        if re.match(r'^\s*\d+\.', numbered_parts[i]):  # This is a delimiter (e.g., "1.")
            question_number_prefix = numbered_parts[i].strip()
            question_text_segment = numbered_parts[i + 1].strip() if i + 1 < len(numbered_parts) else ""
            
            # Combine prefix and text segment to form the full question content (for RAG)
            full_question_content = f"{question_number_prefix} {question_text_segment}".strip()
            
            extracted_questions.append({
                "subject": subject,
                "content": question_text_segment,
                "full_content": full_question_content,
                "original_full_content": homework_content # This is the content *after* potential initial header removal
            })
            i += 2
        else: # This branch should ideally only be hit if the content is malformed or not numbered.
              # If it's the very first part and we didn't discard it, it's a standalone unnumbered block.
            if numbered_parts[i].strip():
                # If no questions have been added yet, treat this as the first question
                if not extracted_questions: 
                     extracted_questions.append({
                        "subject": subject,
                        "content": numbered_parts[i].strip(),
                        "full_content": numbered_parts[i].strip(),
                        "original_full_content": homework_content
                    })
                else: # This is an unexpected unnumbered block in between or after numbered questions
                    logger.warning(f"Unexpected unnumbered part in homework content after split: '{numbered_parts[i].strip()}'")
                    extracted_questions.append({
                        "subject": subject,
                        "content": numbered_parts[i].strip(),
                        "full_content": numbered_parts[i].strip(),
                        "original_full_content": homework_content
                    })
            i += 1

    # If no questions were found from numbered patterns, try bullet points
    if not extracted_questions:
        bullet_parts = re.split(r'(?m)^\s*([-*])[\s\xa0]+', homework_content)
        # Similar logic for discarding initial unbulleted intro/header
        if bullet_parts and bullet_parts[0].strip() and len(bullet_parts) > 1 and not re.match(r'^\s*[-*]', bullet_parts[0].strip()):
            logger.debug(f"Discarding unbulleted intro/header before first bullet question: '{bullet_parts[0].strip()}'")
            bullet_parts = bullet_parts[1:]

        i = 0
        while i < len(bullet_parts):
            if re.match(r'^\s*[-*]', bullet_parts[i].strip()): # This is a delimiter (e.g., "-")
                bullet_prefix = bullet_parts[i].strip()
                bullet_text_segment = bullet_parts[i + 1].strip() if i + 1 < len(bullet_parts) else ""
                full_bullet_content = f"{bullet_prefix} {bullet_text_segment}".strip()
                extracted_questions.append({
                    "subject": subject,
                    "content": bullet_text_segment,
                    "full_content": full_bullet_content,
                    "original_full_content": homework_content
                })
                i += 2
            else:
                if bullet_parts[i].strip():
                    if not extracted_questions: # If no questions yet, treat as first
                        extracted_questions.append({
                            "subject": subject,
                            "content": bullet_parts[i].strip(),
                            "full_content": bullet_parts[i].strip(),
                            "original_full_content": homework_content
                        })
                    else: # Unexpected unbulleted block
                        logger.warning(f"Unexpected unbulleted part in homework content after split: '{bullet_parts[i].strip()}'")
                        extracted_questions.append({
                            "subject": subject,
                            "content": bullet_parts[i].strip(),
                            "full_content": bullet_parts[i].strip(),
                            "original_full_content": homework_content
                        })
                i += 1

    # If still no clear split, treat the whole content as one question
    if not extracted_questions and homework_content.strip():
        extracted_questions.append({
            "subject": subject,
            "content": homework_content.strip(),
            "full_content": homework_content.strip(),
            "original_full_content": homework_content
        })

    # Filter out any empty content questions that might arise from splitting
    extracted_questions = [q for q in extracted_questions if q["content"].strip()]

    # Assign unique IDs to each question
    for i, q in enumerate(extracted_questions):
        q["question_id"] = f"{subject}_{uuid.uuid4().hex[:8]}_{i + 1}"

    return extracted_questions


def _parse_student_answers_to_map(student_answers_text: str, target_subject: str, rag_questions: List[str]) -> Dict[
    str, str]:
    """
    Heuristically parses student answers to map them to known RAG questions for a specific subject.
    Assumes student_answers_text might contain multiple subjects delimited by '--- Subject ---'.
    This is a best-effort approach due to unstructured student input.
    """
    answer_map = {}

    # 1. Extract the block of answers for the target_subject
    subject_block = ""
    start_marker = f"--- {target_subject} ---"
    start_index = student_answers_text.find(start_marker)

    if start_index == -1:
        # If subject marker not found, assume the whole text is for the target subject
        # This is a fallback and might be wrong if multiple subjects are present without markers.
        subject_block = student_answers_text.strip()
    else:
        # Extract the content after the start marker
        content_after_marker = student_answers_text[start_index + len(start_marker):].strip()

        # Find the next subject marker
        next_subject_marker_match = re.search(r'--- [^-\n]+ ---', content_after_marker)
        if next_subject_marker_match:
            end_index = next_subject_marker_match.start()
            subject_block = content_after_marker[:end_index].strip()
        else:
            # No other subject markers, so the rest of the content is for the target subject
            subject_block = content_after_marker.strip()

    if not subject_block:
        return {}  # No answers found for this subject

    student_answer_lines = [line.strip() for line in subject_block.split('\n') if line.strip()]

    # Create a map from question number (e.g., "1") to full question text (e.g., "1. 4 x 3 = ?")
    # This is used for matching explicitly numbered student answers.
    rag_q_num_to_full_q_text = {}
    for q_text in rag_questions:
        num_match = re.match(r'^\s*(\d+)\.\s*', q_text)
        if num_match:
            rag_q_num_to_full_q_text[num_match.group(1)] = q_text

    # 2. Attempt to parse explicitly numbered student answers (e.g., "1. My answer")
    temp_answer_map_numbered = {}
    current_student_answer_parts = []
    current_student_q_num = None

    for line in student_answer_lines:
        num_match = re.match(r'^\s*(\d+)\.\s*(.*)', line)
        if num_match:
            if current_student_q_num is not None and current_student_answer_parts:
                if current_student_q_num in rag_q_num_to_full_q_text:
                    temp_answer_map_numbered[rag_q_num_to_full_q_text[current_student_q_num]] = " ".join(current_student_answer_parts)
            current_student_q_num = num_match.group(1)
            current_student_answer_parts = [num_match.group(2)]
        elif current_student_q_num is not None:
            current_student_answer_parts.append(line)
    
    if current_student_q_num is not None and current_student_answer_parts:
        if current_student_q_num in rag_q_num_to_full_q_text:
            temp_answer_map_numbered[rag_q_num_to_full_q_text[current_student_q_num]] = " ".join(current_student_answer_parts)

    if temp_answer_map_numbered:
        return temp_answer_map_numbered

    # 3. Fallback: If no numbered answers were found, try positional mapping
    # This handles cases where student just lists answers without numbering.
    # We map the first N student answer lines to the N RAG questions, where N is min(len(student_answer_lines), len(rag_questions))
    num_to_map = min(len(student_answer_lines), len(rag_questions))
    if num_to_map > 0:
        logger.debug(f"Positional mapping {num_to_map} student answers to RAG questions for subject {target_subject}.")
        for i in range(num_to_map):
            answer_map[rag_questions[i]] = student_answer_lines[i]
        return answer_map
    
    # 4. Fallback for single question (if only one RAG question and no other mapping)
    if not answer_map and len(rag_questions) == 1:
        answer_map[rag_questions[0]] = subject_block.strip()

    return answer_map
