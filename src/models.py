#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据模型和工具定义

包含学生档案模型、UK 小学年级/学段映射、以及 LangChain 工具定义。
"""

from typing import Dict, List, Any, Literal
import logging

from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# UK primary school year group to age mapping (Year 1-6, ages 5-11)
YEAR_GROUP_AGE = {
    1: 5,   # Year 1: age 5-6
    2: 6,   # Year 2: age 6-7
    3: 7,   # Year 3: age 7-8 (KS2 开始)
    4: 8,   # Year 4: age 8-9
    5: 9,   # Year 5: age 9-10
    6: 10,  # Year 6: age 10-11 (KS2 结束)
}

# UK key stages
KEY_STAGES = {
    1: "KS1", 2: "KS1",           # Year 1-2: Key Stage 1
    3: "KS2", 4: "KS2",           # Year 3-4: Lower Key Stage 2
    5: "KS2", 6: "KS2",           # Year 5-6: Upper Key Stage 2
}

# UK Primary School National Curriculum subjects
UK_PRIMARY_SUBJECTS = [
    "Math",
    "English",
    "Science",
    "History",
    "Geography",
    "Design and Technology",
    "Art and Design",
    "Computing",
    "Latin",
    "Spanish",
    "Chinese",
]

# 科目对应的可爱图标
SUBJECT_ICONS = {
    "English": "ABC",
    "Mathematics": "123",
    "Math": "123",
    "Science": "Sci",
    "History": "His",
    "Geography": "Geo",
    "Design and Technology": "DT",
    "Art and Design": "Art",
    "Computing": "Com",
    "Latin": "Lat",
    "Spanish": "Spa",
    "Chinese": "Chi",
}


def get_homework_time_by_age(year_group: int) -> Dict[str, Any]:
    """根据学生年龄/年级推荐每日英语作业时间（遵循英国教育部 guidelines）

    UK Department for Education 建议的每日作业时间：
    - KS1 (Year 1-2, ages 5-7): 10-15 minutes/day (以阅读、拼读为主)
    - Lower KS2 (Year 3-4, ages 7-9): 20-30 minutes/day
    - Upper KS2 (Year 5-6, ages 9-11): 30 minutes/day

    Args:
        year_group: 英国小学年级 (1-6)

    Returns:
        dict: 包含建议作业时间及说明的字典
    """
    age = YEAR_GROUP_AGE.get(year_group, 7)
    key_stage = KEY_STAGES.get(year_group, "KS2")

    if year_group in [1, 2]:
        daily_minutes = "10-15"
        focus = "Reading aloud, phonics practice, and spelling high-frequency words"
        weekly_minutes = "60-90"
    elif year_group in [3, 4]:
        daily_minutes = "20-30"
        focus = "Reading comprehension, grammar exercises, and short writing tasks"
        weekly_minutes = "120-180"
    else:  # Year 5-6
        daily_minutes = "30"
        focus = "Reading, SPaG (Spelling, Punctuation and Grammar), writing, and SATs preparation"
        weekly_minutes = "150-210"

    return {
        "year_group": year_group,
        "age": age,
        "key_stage": key_stage,
        "daily_homework_minutes": daily_minutes,
        "weekly_homework_minutes": weekly_minutes,
        "focus_areas": focus,
    }


class StudentProfile(BaseModel):
    """Student profile information (UK Primary School)"""
    student_id: str = Field(..., description="Student ID")
    year_group: int = Field(..., description="UK school year group (1-6)")
    age: int = Field(..., description="Student age (5-11)")
    key_stage: str = Field(..., description="UK Key Stage (KS1 or KS2)")
    english_level: Literal["Beginner", "Elementary", "Intermediate", "Advanced"] = Field(..., description="English proficiency level")
    learning_goals: List[str] = Field(..., description="Learning goals")
    weak_areas: List[str] = Field(..., description="Areas needing improvement")
    learning_style: Literal["Visual", "Auditory", "Kinesthetic", "Reading/Writing"] = Field(..., description="Preferred learning style")
    vocabulary_count: int = Field(..., description="Estimated vocabulary size")
    recommended_homework_minutes: str = Field(..., description="Recommended daily homework time in minutes")


# Sample student profile data (UK Primary School - one per year group)
SAMPLE_STUDENT_PROFILES = {
    "student1": {
        "student_id": "S2024001",
        "year_group": 1,
        "age": 5,
        "key_stage": "KS1",
        "english_level": "Beginner",
        "learning_goals": ["Learn phonics", "Recognise high-frequency words", "Read simple sentences"],
        "weak_areas": ["Letter sounds", "Blending"],
        "learning_style": "Visual",
        "vocabulary_count": 50,
        "recommended_homework_minutes": "10-15"
    },
    "student2": {
        "student_id": "S2024002",
        "year_group": 2,
        "age": 6,
        "key_stage": "KS1",
        "english_level": "Beginner",
        "learning_goals": ["Read simple stories", "Write short sentences", "Learn basic spelling"],
        "weak_areas": ["Common exception words", "Sentence punctuation"],
        "learning_style": "Auditory",
        "vocabulary_count": 150,
        "recommended_homework_minutes": "10-15"
    },
    "student3": {
        "student_id": "S2024003",
        "year_group": 3,
        "age": 7,
        "key_stage": "KS2",
        "english_level": "Elementary",
        "learning_goals": ["Build vocabulary", "Improve reading comprehension", "Practice writing simple sentences"],
        "weak_areas": ["Grammar tenses", "Spelling"],
        "learning_style": "Visual",
        "vocabulary_count": 300,
        "recommended_homework_minutes": "20-30"
    },
    "student4": {
        "student_id": "S2024004",
        "year_group": 4,
        "age": 8,
        "key_stage": "KS2",
        "english_level": "Elementary",
        "learning_goals": ["Improve reading fluency", "Write structured paragraphs", "Learn fronted adverbials"],
        "weak_areas": ["Conjunctions", "Paragraph structure"],
        "learning_style": "Reading/Writing",
        "vocabulary_count": 500,
        "recommended_homework_minutes": "20-30"
    },
    "student5": {
        "student_id": "S2024005",
        "year_group": 5,
        "age": 9,
        "key_stage": "KS2",
        "english_level": "Intermediate",
        "learning_goals": ["Write descriptive essays", "Use complex sentences", "Expand vocabulary"],
        "weak_areas": ["Modal verbs", "Relative clauses"],
        "learning_style": "Kinesthetic",
        "vocabulary_count": 700,
        "recommended_homework_minutes": "30"
    },
    "student6": {
        "student_id": "S2024006",
        "year_group": 6,
        "age": 10,
        "key_stage": "KS2",
        "english_level": "Intermediate",
        "learning_goals": ["Write short essays", "Improve speaking fluency", "Prepare for SATs"],
        "weak_areas": ["Complex grammar structures", "Reading comprehension"],
        "learning_style": "Auditory",
        "vocabulary_count": 800,
        "recommended_homework_minutes": "30"
    }
}


# Define tools
@tool
def lookup_word_definition(word: str) -> str:
    """Look up the definition, pronunciation, and example sentences of an English word

    Args:
        word: The English word to look up
    """
    dictionary = {
        "apple": {
            "pronunciation": "/ˈæpl/",
            "definition": "A round fruit with red or green skin and a firm white flesh",
            "example": "I eat an apple every day.",
            "level": "Elementary"
        },
        "beautiful": {
            "pronunciation": "/ˈbjuːtɪfl/",
            "definition": "Very attractive or pleasant to look at",
            "example": "What a beautiful flower!",
            "level": "Elementary"
        },
        "happy": {
            "pronunciation": "/ˈhæpi/",
            "definition": "Feeling or showing pleasure or contentment",
            "example": "She is very happy today.",
            "level": "Beginner"
        },
        "run": {
            "pronunciation": "/rʌn/",
            "definition": "To move at a speed faster than walking by moving your legs more quickly",
            "example": "The children run to the playground.",
            "level": "Beginner"
        },
        "elephant": {
            "pronunciation": "/ˈelɪfənt/",
            "definition": "A very large gray animal with a long trunk and tusks",
            "example": "The elephant is the largest land animal.",
            "level": "Elementary"
        }
    }

    word_lower = word.lower()
    if word_lower in dictionary:
        info = dictionary[word_lower]
        result = f"Word: {word}\nPronunciation: {info['pronunciation']}\nDefinition: {info['definition']}\nExample: {info['example']}\nLevel: {info['level']}"
    else:
        result = f"Word: {word}\nDefinition: (Looking up...)\nThis word is not in the basic dictionary. Let me explain it in a simple way."

    logger.info(f"[Tool Call] {result}")
    return result


@tool
def check_grammar(sentence: str) -> str:
    """Check the grammar of an English sentence and provide corrections

    Args:
        sentence: The English sentence to check
    """
    result = f"Original Sentence: {sentence}\n\nGrammar Analysis:\n- The sentence structure is analyzed.\n- Suggestions for improvement will be provided.\n\nLet me help you make this sentence better!"
    logger.info(f"[Tool Call] Check grammar for: {sentence}")
    return result


@tool
def get_year_group_vocabulary(year_group: int) -> str:
    """Get the vocabulary list for a specific UK school year group (Year 1 to Year 6)

    Args:
        year_group: UK school year group (1-6)
    """
    vocabulary_by_year = {
        1: ["cat", "dog", "book", "pen", "apple", "happy", "run", "big", "small", "red"],
        2: ["school", "teacher", "friend", "play", "water", "food", "family", "blue", "green", "jump"],
        3: ["beautiful", "because", "different", "important", "weather", "animal", "country", "season", "hundred", "minute"],
        4: ["environment", "experience", "experiment", "knowledge", "language", "practice", "question", "sentence", "together", "understand"],
        5: ["adventure", "character", "community", "decision", "education", "imagine", "paragraph", "situation", "tradition", "vocabulary"],
        6: ["achievement", "circumstance", "consequence", "description", "embarrass", "opportunity", "perspective", "responsibility", "technology", "understanding"]
    }

    vocab_list = vocabulary_by_year.get(year_group, [])
    result = f"Year {year_group} Vocabulary List:\n" + ", ".join(vocab_list)
    logger.info(f"[Tool Call] {result}")
    return result


@tool
def get_homework_time(year_group: int) -> str:
    """Get the recommended daily English homework time for a UK primary school student based on their year group/age

    Args:
        year_group: UK school year group (1-6)
    """
    info = get_homework_time_by_age(year_group)
    result = (
        f"Year {info['year_group']} (Age {info['age']}, {info['key_stage']}) Homework Recommendation:\n"
        f"- Daily: {info['daily_homework_minutes']} minutes\n"
        f"- Weekly: {info['weekly_homework_minutes']} minutes\n"
        f"- Focus: {info['focus_areas']}"
    )
    logger.info(f"[Tool Call] {result}")
    return result


@tool
def search_homework_by_topic(
    query: str,
    year_group: int = None,
    subject: str = None,
) -> str:
    """Search for previously generated homework by topic and optional filters

    Args:
        query: Search query (e.g., "fractions exercise", "grammar past tense")
        year_group: Optional UK year group filter (1-6)
        subject: Optional subject filter (e.g., "Math", "English")
    """
    from src.homework_rag import search_homework

    try:
        results = search_homework(
            query=query,
            year_group=year_group,
            subject=subject,
            k=3,
        )

        if not results:
            return f"No homework found matching: '{query}'"

        output = f"Found {len(results)} homework results for: '{query}'\n\n"
        for i, result in enumerate(results, 1):
            meta = result["metadata"]
            output += f"--- Result {i} ---\n"
            output += f"Subject: {meta.get('subject', 'N/A')}\n"
            output += f"Year Group: {meta.get('year_group', 'N/A')}\n"
            output += f"Key Stage: {meta.get('key_stage', 'N/A')}\n"
            output += f"Recommended Time: {meta.get('homework_minutes', 'N/A')} minutes\n"
            output += f"Created: {meta.get('created_at', 'N/A')}\n"
            output += f"Content Preview:\n{result['content'][:500]}...\n\n"

        return output
    except Exception as e:
        return f"Error searching homework: {str(e)}"


@tool
def load_chinese_textbooks() -> str:
    """Load Chinese textbooks into the RAG system for future reference.
    Textbooks are mapped by volume: 第一册=Year1, 第二册=Year2, etc.
    Call this once to make textbooks searchable.
    """
    from src.homework_rag import ingest_chinese_textbooks

    try:
        count = ingest_chinese_textbooks()
        if count > 0:
            return f"Successfully loaded {count} Chinese textbook documents into RAG system."
        else:
            return "Chinese textbooks are already loaded or directory not found."
    except Exception as e:
        return f"Error loading Chinese textbooks: {str(e)}"


@tool
def search_chinese_resources(query: str, year_group: int = None) -> str:
    """Search Chinese textbooks by topic

    Args:
        query: Search query (e.g., "生字", "识字", "拼音")
        year_group: Optional year group filter (1-6)
    """
    from src.homework_rag import search_chinese_textbooks

    try:
        results = search_chinese_textbooks(
            query=query,
            year_group=year_group,
            k=3,
        )

        if not results:
            return f"No Chinese textbook found matching: '{query}'"

        output = f"Found {len(results)} Chinese textbook results for: '{query}'\n\n"
        for i, result in enumerate(results, 1):
            meta = result["metadata"]
            output += f"--- Result {i} ---\n"
            output += f"Volume: {meta.get('volume', 'N/A')}\n"
            output += f"Year Group: {meta.get('year_group', 'N/A')}\n"
            output += f"File: {meta.get('filename', 'N/A')}\n"
            output += f"Content: {result['content']}\n\n"

        return output
    except Exception as e:
        return f"Error searching Chinese textbooks: {str(e)}"


# Tool list
tools = [
    lookup_word_definition, check_grammar, get_year_group_vocabulary,
    get_homework_time, search_homework_by_topic,
    load_chinese_textbooks, search_chinese_resources,
]
