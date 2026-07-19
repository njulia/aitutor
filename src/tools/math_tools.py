import random
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_math_homework_tool(year_group: int, topic: str = None) -> Dict[str, Any]:
    """
    Python tool to generate math homework for a specific year group and topic.
    """
    from scripts.homework_generator.homework_math_generator import generate_math_homework as _gen_math, MATH_TOPICS_BY_YEAR
    
    if not topic:
        topics = MATH_TOPICS_BY_YEAR.get(year_group, ["General Arithmetic"])
        topic = random.choice(topics)
    
    index = random.randint(1, 1000)
    content, answers = _gen_math(year_group, topic, index)
    
    return {
        "content": content,
        "answers": answers,
        "topic": topic,
        "year_group": year_group
    }

def generate_science_homework_tool(year_group: int, topic: str = None) -> Dict[str, Any]:
    """
    Python tool to generate science homework.
    """
    from scripts.homework_generator.homework_science_generator import generate_science_homework as _gen_science, SCIENCE_TOPICS_BY_YEAR
    
    if not topic:
        topics = SCIENCE_TOPICS_BY_YEAR.get(year_group, ["General Science"])
        topic = random.choice(topics)
        
    index = random.randint(1, 1000)
    content, answers = _gen_science(year_group, topic, index)
    
    return {
        "content": content,
        "answers": answers,
        "topic": topic,
        "year_group": year_group
    }

def generate_english_homework_tool(year_group: int, topic: str = None) -> Dict[str, Any]:
    """
    Python tool to generate english homework.
    """
    from scripts.homework_generator.homework_english_generator import generate_english_homework as _gen_english, ENGLISH_TOPICS_BY_YEAR
    
    if not topic:
        topics = ENGLISH_TOPICS_BY_YEAR.get(year_group, ["General English"])
        topic = random.choice(topics)
        
    index = random.randint(1, 1000)
    content, answers = _gen_english(year_group, topic, index)
    
    return {
        "content": content,
        "answers": answers,
        "topic": topic,
        "year_group": year_group
    }

def verify_math_answer(question: str, student_answer: str, correct_answer: str) -> Dict[str, Any]:
    """
    Verifies if a math answer is correct using Python logic for better accuracy than LLM.
    """
    # Basic normalization
    s_ans = str(student_answer).strip().lower()
    c_ans = str(correct_answer).strip().lower()
    
    # Remove units if they match (e.g., "5cm" vs "5")
    # This is a bit simplified, but helps.
    s_ans_clean = re.sub(r'[^0-9.\-]', '', s_ans)
    c_ans_clean = re.sub(r'[^0-9.\-]', '', c_ans)
    
    is_correct = False
    if s_ans == c_ans:
        is_correct = True
    elif s_ans_clean and c_ans_clean:
        try:
            if float(s_ans_clean) == float(c_ans_clean):
                is_correct = True
        except ValueError:
            pass
            
    return {
        "is_correct": is_correct,
        "student_answer": student_answer,
        "correct_answer": correct_answer
    }
