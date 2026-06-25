#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Hybrid Agent - AI Tutor for UK Primary School Students (Year 1 to Year 6)

A hybrid agent implemented with LangGraph that combines the instant response capability of reactive architecture
with the long-term planning capability of deliberative architecture, dynamically switching processing modes
through a coordination layer to provide intelligent English tutoring services for UK primary school students.

Homework time is set according to the student's age following UK Department for Education guidelines.

Three-tier architecture:
1. Bottom layer (Reactive): Instant response to student questions with fast feedback
2. Middle layer (Coordination): Evaluates question types and difficulty, dynamically selects processing mode
3. Top layer (Deliberative): Performs learning analysis and creates personalized study plans
"""
import re
import glob
import html
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Literal, TypedDict, Optional, Annotated

from prompts import (
    HOMEWORK_PROMPT,
    SUBJECT_EXTRACTION_PROMPT,
    REVIEW_HOMEWORK_PROMPT,
    ASSESSMENT_PROMPT,
    DATA_COLLECTION_PROMPT,
    ANALYSIS_PROMPT,
    RECOMMENDATION_PROMPT,
    REACTIVE_SYSTEM_PROMPT,
    PROFILE_PARSE_PROMPT,
)

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.tools import tool
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
import warnings


warnings.filterwarnings("ignore")

# AGICTO API Key
LLM_MODEL = "qwen3.5-plus"
AGICTO_API_KEY = os.getenv("AGICTO_API_KEY")

# Check if API Key is set
if not AGICTO_API_KEY:
    print("Error: AGICTO_API_KEY environment variable not found")
    print("Please set the environment variable: export AGICTO_API_KEY='your-api-key'")
    exit(1)

# ==================== LangSmith 配置 ====================
# LangSmith 用于 Agent 调试、追踪和监控
# 使用前需要设置以下环境变量：
# 1. LANGSMITH_API_KEY: 从 https://smith.langchain.com 获取
# 2. LANGCHAIN_TRACING_V2: 设置为 "true" 启用追踪
# 3. LANGCHAIN_PROJECT: 项目名称（可选，用于组织追踪记录）

# 检查是否启用 LangSmith
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
LANGSMITH_PROJECT = os.getenv("LANGCHAIN_PROJECT", "english-tutor-hybrid-agent")

# Create LLM instance (using AGICTO/OpenAI to support tool calling)
llm = ChatOpenAI(
    model=LLM_MODEL,
    openai_api_key=AGICTO_API_KEY,
    openai_api_base="https://api.agicto.cn/v1/",
    temperature=0.7,
)

# UK primary school year group to age mapping (Year 1-6, ages 5-11)
# 英国小学年级与年龄对应表（Year 1-6，年龄 5-11 岁）
YEAR_GROUP_AGE = {
    1: 5,   # Year 1: age 5-6, 使用下限 5
    2: 6,   # Year 2: age 6-7
    3: 7,   # Year 3: age 7-8 (KS2 开始)
    4: 8,   # Year 4: age 8-9
    5: 9,   # Year 5: age 9-10
    6: 10,  # Year 6: age 10-11 (KS2 结束)
}

# UK key stages
# 英国教育学段划分
KEY_STAGES = {
    1: "KS1", 2: "KS1",           # Year 1-2: Key Stage 1
    3: "KS2", 4: "KS2",           # Year 3-4: Lower Key Stage 2
    5: "KS2", 6: "KS2",           # Year 5-6: Upper Key Stage 2
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
        包含建议作业时间及说明的字典
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


# UK Primary School National Curriculum subjects
# 英国小学国家课程科目
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


def generate_homework_for_subject(student_profile: Dict[str, Any], subject: str) -> str:
    """为指定科目生成作业

    Args:
        student_profile: 学生信息字典
        subject: 科目名称
    """
    year_group = student_profile.get("year_group", 3)
    homework_info = get_homework_time_by_age(year_group)
    homework_time = homework_info["daily_homework_minutes"]

    prompt = ChatPromptTemplate.from_template(HOMEWORK_PROMPT)
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({
        "student_profile": json.dumps(student_profile, ensure_ascii=False, indent=2),
        "subject": subject,
        "homework_time": homework_time,
        "year_group": year_group,
        "age": student_profile.get("age", 7),
    })
    print(f"[- {subject}] {result}")
    return result


def extract_subjects_from_prompt(user_input: str) -> List[str]:
    """从用户提示词中提取科目

    Args:
        user_input: 用户的自然语言输入

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


def generate_5day_homework(student_profile: Dict[str, Any], subjects: List[str]) -> Dict[int, Dict[str, str]]:
    """生成5天的作业，每天最多两个科目

    Args:
        student_profile: 学生信息字典
        subjects: 科目列表

    Returns:
        {day_number: {subject: homework_content}}
    """
    homework_plan = {}

    # 将科目分配到5天中，每天最多2个科目
    day_assignments = distribute_subjects_to_days(subjects, 5)

    for day, day_subjects in day_assignments.items():
        day_homework = {}
        for subject in day_subjects:
            print(f"[Homework] Day {day}: Generating homework for {subject}...")
            homework = generate_homework_for_subject(student_profile, subject)
            day_homework[subject] = homework
        homework_plan[day] = day_homework

    return homework_plan


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


def save_homework_to_file(homework_plan: Dict[int, Dict[str, str]], student_id: str, output_dir: str = "homework_output") -> str:
    """将5天作业保存到本地文件

    Args:
        homework_plan: 作业计划 {day: {subject: content}}
        student_id: 学生ID
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{output_dir}/homework_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# 5-Day Homework Plan\n")
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

    print(f"[Save] Homework saved to: {filename}")
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

    print(f"[Load] Found latest homework file: {latest_file}")

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
    """检查5天作业的完成情况

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


def review_day_homework(student_profile: Dict[str, Any], day: int, subjects_homework: Dict[str, str], student_answers: Dict[str, str]) -> str:
    """点评某一天的作业

    Args:
        student_profile: 学生档案
        day: 天数
        subjects_homework: {科目: 作业内容}
        student_answers: {科目: 学生答案}

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

    print(f"[Save] Review saved to: {filename}")
    return filename


def regenerate_5day_homework(student_profile: Dict[str, Any], subjects: List[str], output_dir: str = "homework_output") -> tuple:
    """重新生成5天作业并检查完成情况

    Args:
        student_profile: 学生档案
        subjects: 科目列表
        output_dir: 输出目录

    Returns:
        (homework_plan, incomplete_days, filepath)
    """
    # 尝试加载最近的作业
    latest = load_latest_homework(student_profile["student_id"], output_dir)

    if latest:
        homework_plan, filepath = latest
        print(f"[Load] Loaded existing homework plan from: {filepath}")

        # 检查完成情况
        incomplete = check_homework_completion(homework_plan, student_profile["student_id"], output_dir)

        if not incomplete:
            print("[Info] All homework completed! Generating new 5-day plan...")
            homework_plan = generate_5day_homework(student_profile, subjects)
            filepath = save_homework_to_file(homework_plan, student_profile["student_id"], output_dir)
            incomplete = {day: list(subjects_homework.keys()) for day, subjects_homework in homework_plan.items()}
        else:
            print(f"[Info] Found incomplete days: {list(incomplete.keys())}")
    else:
        print("[Info] No existing homework found. Generating new 5-day plan...")
        homework_plan = generate_5day_homework(student_profile, subjects)
        filepath = save_homework_to_file(homework_plan, student_profile["student_id"], output_dir)
        incomplete = {day: list(subjects_homework.keys()) for day, subjects_homework in homework_plan.items()}

    return homework_plan, incomplete, filepath


def process_homework_with_review(user_input: str, student_id: str = "student1", student_answers: Dict[int, Dict[str, str]] = None) -> str:
    """完整的作业处理流程：导入/生成 -> 点评 -> 保存

    Args:
        user_input: 用户提示词（包含科目信息）
        student_id: 学生ID
        student_answers: 学生答案 {day: {subject: answer}}

    Returns:
        保存的文件路径
    """
    # 1. 提取科目
    subjects = extract_subjects_from_prompt(user_input)

    if not subjects:
        print("[Warning] No subjects found in input. Using default subjects: English, Math")
        subjects = ["English", "Math"]

    print(f"[Extracted Subjects] {', '.join(subjects)}")

    # 2. 获取学生档案
    student_profile = SAMPLE_STUDENT_PROFILES.get(student_id, SAMPLE_STUDENT_PROFILES["student1"])

    # 3. 加载或重新生成作业
    homework_plan, incomplete, filepath = regenerate_5day_homework(student_profile, subjects)

    # 4. 点评未完成的作业
    reviews = {}
    for day, day_subjects in incomplete.items():
        day_homework = {s: homework_plan[day][s] for s in day_subjects if s in homework_plan.get(day, {})}

        # 使用提供的答案或默认"未提交"
        day_answers = student_answers.get(day, {s: "Not submitted" for s in day_subjects})

        print(f"[Review] Reviewing Day {day} homework...")
        review = review_day_homework(student_profile, day, day_homework, day_answers)
        reviews[day] = review

    # 5. 保存作业和点评
    final_filepath = save_review_with_homework(homework_plan, reviews, student_id)

    return final_filepath


def generate_homework_with_custom_profile(student_profile: Dict[str, Any], subjects: List[str]) -> str:
    """使用自定义学生档案生成作业

    Args:
        student_profile: 学生信息字典
        subjects: 选中的科目列表

    Returns:
        按科目分隔的完整作业文本
    """
    sections = []
    separator = f"\n{'~'*60}\n"
    for subject in subjects:
        sections.append( separator)
        print(f"[Homework] Generating homework for {subject}...")
        homework = generate_homework_for_subject(student_profile, subject)
        sections.append( homework)
        # separator = f"\n{'~'*60}\n"
        # sections.append(f"{separator}\n{homework}\n")
        sections.append( separator)

    return "\n".join(sections)


# Define student information data structure
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

# Define tools
@tool
def lookup_word_definition(word: str) -> str:
    """Look up the definition, pronunciation, and example sentences of an English word

    Args:
        word: The English word to look up
    """
    # Mock dictionary data
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

    print(f"[Tool Call] {result}")
    return result

@tool
def check_grammar(sentence: str) -> str:
    """Check the grammar of an English sentence and provide corrections

    Args:
        sentence: The English sentence to check
    """
    # Mock grammar checking
    result = f"Original Sentence: {sentence}\n\nGrammar Analysis:\n- The sentence structure is analyzed.\n- Suggestions for improvement will be provided.\n\nLet me help you make this sentence better!"
    print(f"[Tool Call] Check grammar for: {sentence}")
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
    print(f"[Tool Call] {result}")
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
    print(f"[Tool Call] {result}")
    return result

# Tool list
tools = [lookup_word_definition, check_grammar, get_year_group_vocabulary, get_homework_time]

# Bind tools to LLM
llm_with_tools = llm.bind_tools(tools)

# Create tool node
tool_node = ToolNode(tools)

# Define state type
class EnglishTutorState(TypedDict):
    """English tutor agent state"""
    # Input
    user_query: str
    student_profile: Optional[Dict[str, Any]]

    # Processing state
    query_type: Optional[Literal["vocabulary", "grammar", "reading", "writing", "conversation", "study_plan"]]
    processing_mode: Optional[Literal["reactive", "deliberative"]]
    learning_data: Optional[Dict[str, Any]]
    analysis_results: Optional[Dict[str, Any]]

    # Message history (for tool calling)
    messages: Annotated[List[BaseMessage], add_messages]

    # Output
    final_response: Optional[str]

    # Control flow
    current_phase: Optional[str]
    error: Optional[str]

# Phase 1: Context Assessment - Determine query type and processing mode
def assess_query(state: EnglishTutorState) -> Dict[str, Any]:
    print("[DEBUG] Entering node: assess_query")

    prompt = ChatPromptTemplate.from_template(ASSESSMENT_PROMPT)
    chain = prompt | llm | JsonOutputParser()
    result = chain.invoke({"user_query": state["user_query"]})

    print(f"[DEBUG] LLM assessment output: {result}")

    processing_mode = result.get("processing_mode", "reactive")
    if processing_mode not in ["reactive", "deliberative"]:
        processing_mode = "reactive"

    query_type = result.get("query_type", "vocabulary")
    if query_type not in ["vocabulary", "grammar", "reading", "writing", "conversation", "study_plan"]:
        query_type = "vocabulary"

    print(f"[DEBUG] Branch decision: processing_mode={processing_mode}, query_type={query_type}")

    return {
        "query_type": query_type,
        "processing_mode": processing_mode,
    }

# Reactive processing - Initialize messages and invoke LLM with tools
def reactive_agent(state: EnglishTutorState) -> Dict[str, Any]:
    print("[DEBUG] Entering node: reactive_agent")

    student_info = json.dumps(state.get("student_profile", {}), ensure_ascii=False, indent=2)

    system_prompt = REACTIVE_SYSTEM_PROMPT.format(student_info=student_info)

    messages = state.get("messages", [])
    if not messages:
        messages = [HumanMessage(content=f"{system_prompt}\n\nStudent Question: {state['user_query']}")]

    response = llm_with_tools.invoke(messages)
    print(f"[DEBUG] LLM response: {response}")

    return {"messages": [response]}

# Determine whether to continue calling tools
def should_continue_tools(state: EnglishTutorState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    # Check for tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"[DEBUG] Tool call detected: {last_message.tool_calls}")
        return "tools"

    return "end"

# Extract final response from messages
def extract_reactive_response(state: EnglishTutorState) -> Dict[str, Any]:
    print("[DEBUG] Entering node: extract_reactive_response")

    messages = state.get("messages", [])

    # Find the last AI message as the final response
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return {"final_response": msg.content}

    return {"final_response": "Unable to generate response"}

# Data collection - Gather learning information needed for personalized tutoring
def collect_data(state: EnglishTutorState) -> Dict[str, Any]:
    print("[DEBUG] Entering node: collect_data")

    prompt = ChatPromptTemplate.from_template(DATA_COLLECTION_PROMPT)
    chain = prompt | llm | JsonOutputParser()

    result = chain.invoke({
        "user_query": state["user_query"],
        "student_profile": json.dumps(state.get("student_profile", ), ensure_ascii=False, indent=2)
    })

    return {
        "learning_data": result.get("collected_data", {}),
        "current_phase": "analyze"
    }

# In-depth analysis - Analyze student's learning situation
def analyze_data(state: EnglishTutorState) -> Dict[str, Any]:
    print("[DEBUG] Entering node: analyze_data")

    prompt = ChatPromptTemplate.from_template(ANALYSIS_PROMPT)
    chain = prompt | llm | JsonOutputParser()

    result = chain.invoke({
        "user_query": state["user_query"],
        "student_profile": json.dumps(state.get("student_profile", {}), ensure_ascii=False, indent=2),
        "learning_data": json.dumps(state.get("learning_data", {}), ensure_ascii=False, indent=2)
    })

    return {
        "analysis_results": result,
        "current_phase": "recommend"
    }

# Generate recommendations - Provide tutoring response based on analysis
def generate_recommendations(state: EnglishTutorState) -> Dict[str, Any]:
    print("[DEBUG] Entering node: generate_recommendations")

    prompt = ChatPromptTemplate.from_template(RECOMMENDATION_PROMPT)
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({
        "user_query": state["user_query"],
        "student_profile": json.dumps(state.get("student_profile", {}), ensure_ascii=False, indent=2),
        "analysis_results": json.dumps(state.get("analysis_results", {}), ensure_ascii=False, indent=2)
    })

    return {
        "final_response": result,
        "current_phase": "respond"
    }

# Create agent workflow
def create_english_tutor_workflow() -> StateGraph:
    """Create English tutor hybrid agent workflow"""

    workflow = StateGraph(EnglishTutorState)

    # Add nodes
    workflow.add_node("assess", assess_query)
    workflow.add_node("reactive_agent", reactive_agent)
    workflow.add_node("tools", tool_node)
    workflow.add_node("extract_response", extract_reactive_response)
    workflow.add_node("collect_data", collect_data)
    workflow.add_node("analyze", analyze_data)
    workflow.add_node("recommend", generate_recommendations)

    # Set entry point
    workflow.set_entry_point("assess")

    # Branch routing after assessment
    workflow.add_conditional_edges(
        "assess",
        lambda x: "reactive_agent" if x.get("processing_mode") == "reactive" else "collect_data",
        {
            "reactive_agent": "reactive_agent",
            "collect_data": "collect_data"
        }
    )

    # Tool calling loop for reactive agent
    workflow.add_conditional_edges(
        "reactive_agent",
        should_continue_tools,
        {
            "tools": "tools",
            "end": "extract_response"
        }
    )

    # Return to agent after tool execution
    workflow.add_edge("tools", "reactive_agent")

    # End after extracting response
    workflow.add_edge("extract_response", END)

    # Deliberative mode flow
    workflow.add_edge("collect_data", "analyze")
    workflow.add_edge("analyze", "recommend")
    workflow.add_edge("recommend", END)

    return workflow.compile()

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

# Run the agent
def run_english_tutor(user_query: str, student_id: str = "student1") -> Dict[str, Any]:
    """Run the English tutor agent and return results"""

    agent = create_english_tutor_workflow()
    student_profile = SAMPLE_STUDENT_PROFILES.get(student_id, SAMPLE_STUDENT_PROFILES["student1"])

    initial_state = {
        "user_query": user_query,
        "student_profile": student_profile,
        "query_type": None,
        "processing_mode": None,
        "learning_data": None,
        "analysis_results": None,
        "messages": [],
        "final_response": None,
        "current_phase": "assess",
        "error": None
    }

    print("LangGraph Mermaid Flowchart:")
    print(agent.get_graph().draw_mermaid())

    # 准备 LangSmith 配置（如果启用）
    config = {}
    if LANGSMITH_ENABLED:
        config = RunnableConfig(
            tags=[
                "english-tutor",
                "hybrid-agent",
                f"student-{student_id}",
                student_profile.get("english_level", "unknown")
            ],
            metadata={
                "student_id": student_id,
                "year_group": student_profile.get("year_group", "unknown"),
                "age": student_profile.get("age", "unknown"),
                "english_level": student_profile.get("english_level", "unknown"),
                "user_query": user_query[:100],
                "timestamp": datetime.now().isoformat()
            },
            run_name=f"english-tutor-{student_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

    # 运行智能体
    if config:
        result = agent.invoke(initial_state, config=config)
    else:
        result = agent.invoke(initial_state)
    return result

def run_tui():
    """Terminal interactive mode - 作业生成器"""
    print("=== AI Homework Generator for UK Primary School Students (Year 1-6) ===\n")
    print(f"Using Model: AGICTO ({LLM_MODEL})\n")
    
    # 显示 LangSmith 状态
    if LANGSMITH_ENABLED:
        print(f"✓ LangSmith 追踪已启用")
        print(f"  项目: {LANGSMITH_PROJECT}")
        print(f"  查看追踪: https://smith.langchain.com\n")
    else:
        print("ℹ LangSmith 追踪未启用\n")
    
    print("-" * 50)

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
    result = generate_homework_with_custom_profile(profile, selected_subjects)
    end_time = datetime.now()

    print("\n" + "=" * 50)
    print("=== Homework Generated ===")
    print("=" * 50 + "\n")
    print(result)

    process_time = (end_time - start_time).total_seconds()
    print(f"\nTotal generation time: {process_time:.2f} seconds")


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


def homework_to_html(raw_text: str) -> str:
    """将纯文本作业内容转换为带样式的 HTML

    Args:
        raw_text: 原始纯文本作业内容（多个科目用 ~~~ 分隔）

    Returns:
        渲染后的 HTML 字符串
    """

    # 按分隔符拆分为多个科目
    sections = re.split(r'~{10,}', raw_text)
    html_parts = ['<div class="homework-container">']

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 尝试提取科目名称（第一个标题行）
        lines = section.split('\n')
        subject_name = None
        content_lines = []

        for line in lines:
            line_stripped = line.strip()
            # 匹配类似 "# English" 或 "Subject: English" 或 "English Homework" 这样的标题
            if not subject_name and (line_stripped.startswith('#') or
                                     line_stripped.startswith('Subject:') or
                                     (len(line_stripped) < 50 and line_stripped.endswith('Homework'))):
                subject_name = line_stripped.lstrip('# ').replace('Subject:', '').replace('Homework', '').strip()
                continue
            content_lines.append(line)

        if not subject_name:
            # 如果没有找到科目名，尝试从内容中提取第一行作为标题
            if content_lines:
                subject_name = content_lines.pop(0).strip()
            else:
                subject_name = "Homework"

        icon = SUBJECT_ICONS.get(subject_name, "*")

        html_parts.append(f'<div class="homework-subject">')
        html_parts.append(f'<div class="homework-subject-title">'
                          f'<span class="homework-task-number">{icon}</span>'
                          f'{html.escape(subject_name)}'
                          f'</div>')

        # 保留所有原始内容，只做安全的渲染处理
        full_content = '\n'.join(content_lines)

        # 先按段落分割
        paragraphs = re.split(r'\n{2,}', full_content)
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 检测是否是提示/建议
            is_tip = any(kw in para.lower() for kw in ['tip', 'hint', 'remember', 'note:', 'helpful'])
            # 检测是否是资源链接
            is_resource = any(kw in para.lower() for kw in ['bbc bitesize', 'oak national', 'times tables', 'twinkl', 'national geographic', 'resource', 'http'])

            if is_tip:
                html_parts.append(f'<div class="homework-tip">'
                                  f'<div class="homework-tip-title">Tip</div>'
                                  f'{html.escape(para)}'
                                  f'</div>')
            elif is_resource:
                # 先转换 markdown 风格的链接 [text](url) 为 HTML 链接
                def md_link_to_html(match):
                    text = html.escape(match.group(1))
                    url = html.escape(match.group(2))
                    return f'<a href="{url}" target="_blank">{text}</a>'

                processed = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', md_link_to_html, para)
                # 再转换裸 URL 为 HTML 链接
                processed = re.sub(r'(https?://\S+)', r'<a href="\1" target="_blank">\1</a>', processed)
                html_parts.append(f'<div class="homework-resource">{processed}</div>')
            else:
                # 普通段落：保留所有原始换行和内容，只做 URL 渲染
                escaped = html.escape(para)
                # 转换 URL 为可点击链接
                formatted = re.sub(r'(https?://\S+)', r'<a href="\1" target="_blank">\1</a>', escaped)
                # 保留单换行
                formatted = formatted.replace('\n', '<br>')
                html_parts.append(f'<div class="homework-paragraph">{formatted}</div>')

        html_parts.append('</div>')  # end homework-subject
        html_parts.append('<hr class="homework-divider">')

    html_parts.append('</div>')  # end container
    return '\n'.join(html_parts)


def run_gui():
    """Web interface mode - 作业生成器（儿童友好界面）"""
    try:
        import gradio as gr

        # 加载外部 CSS 和 HTML 模板
        script_dir = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(script_dir, "styles.css")
        html_path = os.path.join(script_dir, "gui_template.html")

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

                # 从 LLM 结果中直接获取科目
                extracted_subjects = result.get("extracted_subjects", [])
                if not isinstance(extracted_subjects, list):
                    extracted_subjects = []
                # 过滤为有效科目
                extracted_subjects = [s for s in extracted_subjects if s in UK_PRIMARY_SUBJECTS]
                print(f"[Profile Parse] Extracted subjects: {', '.join(extracted_subjects) if extracted_subjects else 'None'}")

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
            """根据学生档案和选定科目生成作业"""
            if not subject_choices:
                return "**Oops!** Please pick at least one subject first!"

            if not profile:
                return "**Hmm,** please check your student profile inputs!"

            try:
                homework = generate_homework_with_custom_profile(profile, subject_choices)
                return homework
            except Exception as e:
                return f"**Oh no!** Something went wrong: {str(e)}"

        def process_custom_homework(profile_description, subject_vals):
            """方式1: 使用自然语言描述的学生档案生成作业"""
            profile = parse_profile_from_natural_language(profile_description)

            if subject_vals:
                subject_choices = [strip_emoji(s) for s in subject_vals]
            elif profile and profile.get("extracted_subjects"):
                subject_choices = profile["extracted_subjects"]
            elif profile and profile.get("learning_goals"):
                subject_choices = extract_subjects_from_prompt(profile["learning_goals"])
                print(f"[Extracted Subjects from Learning Goals] {', '.join(subject_choices)}")
            else:
                print("[Warning] No subjects found in input. Using default subjects: Math")
                subject_choices = ["Math"]

            return process_homework(profile, subject_choices)

        def process_quick_homework(year_choice, subject_vals):
            """方式2: 使用预设档案生成作业"""
            if not subject_vals:
                return "Oops! Please pick at least one subject first!"

            try:
                year_num = int(year_choice.replace("Year", "").strip())
            except (ValueError, AttributeError):
                return "Hmm, that year doesn't seem right. Try again!"

            student_id = f"student{year_num}"
            if student_id not in SAMPLE_STUDENT_PROFILES:
                return f"Oops! No student found for Year {year_num}."

            subject_choices = [strip_emoji(s) for s in subject_vals] if subject_vals else []
            profile = SAMPLE_STUDENT_PROFILES[student_id]
            return process_homework(profile, subject_choices)

        # 构建年级选项
        year_options = []
        for profile in SAMPLE_STUDENT_PROFILES.values():
            yg = profile["year_group"]
            year_options.append(f"Year {yg}")

        # 科目对应的可爱图标
        subject_emojis = {
            "English": "ABC",
            "Mathematics": "123",
            "Science": "[*]",
            "Art and Design": "(~)",
            "Computing": ">_<",
            "Geography": "(@)",
            "History": "(?)",
            "Spanish": "(S)",
            "Chinese": "(C)",
        }
        # 构建带可爱图标的科目列表
        cute_subjects = [f"{subject_emojis.get(s, '*')}  {s}" for s in UK_PRIMARY_SUBJECTS]

        # 去掉图标前缀还原科目名（用于内部调用）
        def strip_emoji(subject_with_icon):
            """去除科目名前的图标前缀"""
            return subject_with_icon.split("  ", 1)[-1].strip()

        with gr.Blocks(
            title="Homework Magic - UK Primary School",
            css=cute_theme
        ) as demo:
            # 注入 CSS
            gr.HTML(f"<style>{cute_theme}</style>")

            # 主标题
            gr.HTML(main_title_html)

            with gr.Tabs():

                # ====== Tab 1: Custom Student Profile ======
                DEFAULT_PROFILE_EXAMPLE = (
                    "Ana is a 7-year-old student in Year 2 in London. "
                    "She has a particular interest in mathematics. "
                    "Ana is eager to learn both Chinese and Spanish and is committed to spending 15–30 minutes each day practicing these languages as well as developing her math skills. "
                )
                
                with gr.Tab("Custom Profile"):
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

                            cp_btn = gr.Button("Generate My Homework!", variant="primary")

                        with gr.Column(scale=2):
                            gr.HTML('<div class="step-header">Your Homework</div>')
                            cp_output = gr.Markdown(value='Your custom homework will appear here!')

                    def cp_wrapper(profile_desc, subject_vals):
                        return process_custom_homework(profile_desc, subject_vals)
                        # clean_subjects = [strip_emoji(s) for s in subject_vals] if subject_vals else []
                        # profile = parse_profile_from_natural_language(profile_desc)
                        # return process_homework(profile, clean_subjects)

                    cp_btn.click(
                        fn=cp_wrapper,
                        inputs=[cp_profile, cp_subjects],
                        outputs=[cp_output]
                    )

                # ====== Tab 2: Quick Select ======
                with gr.Tab("Quick Select"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.HTML('<div class="step-header">Pick Your Year</div>')
                            qs_year = gr.Radio(choices=year_options, label="", value=year_options[0], container=False)

                            gr.HTML('<div class="step-header">Choose Your Subjects</div>')
                            qs_subjects = gr.CheckboxGroup(choices=cute_subjects, label="", value=[cute_subjects[0]], container=False)

                            qs_btn = gr.Button("Make My Homework!", variant="primary")

                        with gr.Column(scale=2):
                            gr.HTML('<div class="step-header">Your Homework</div>')
                            qs_output = gr.Markdown(value='Your quick homework will appear here!')

                    def qs_wrapper(year_val, subject_vals):
                        # clean_subjects = [strip_emoji(s) for s in subject_vals] if subject_vals else []
                        return process_quick_homework(year_val, subject_vals)

                    qs_btn.click(
                        fn=qs_wrapper,
                        inputs=[qs_year, qs_subjects],
                        outputs=[qs_output]
                    )

                # ====== Tab 3: Check My Homework ======
                with gr.Tab("Check My Homework"):
                    gr.HTML('<div class="step-header">Check My Homework</div>')

                    with gr.Row():
                        take_photo_btn = gr.Button("Take Photo", variant="secondary")
                        upload_file_btn = gr.Button("Upload File", variant="secondary")

                    with gr.Row(visible=False) as photo_input_row:
                        photo_input = gr.Image(label="Take a photo or upload an image", sources=["webcam", "upload"], type="filepath")

                    with gr.Row(visible=False) as file_input_row:
                        file_input = gr.File(label="Upload your homework file")

                    check_btn = gr.Button("Submit for Review", variant="primary")

                    check_result = gr.Markdown(value='Upload your homework to get feedback!')

                    def show_photo_input():
                        return gr.update(visible=True), gr.update(visible=False)

                    def show_file_input():
                        return gr.update(visible=False), gr.update(visible=True)

                    def handle_submit(photo, file):
                        if photo:
                            return "**Photo received.** Review feature coming soon!"
                        elif file:
                            return f"**File received:** {file.name}. Review feature coming soon!"
                        return "**Please upload a photo or file first.**"

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
                        inputs=[photo_input, file_input],
                        outputs=[check_result]
                    )

        demo.launch(share=True)

    except ImportError:
        print("gradio not installed. Please run: pip install gradio")
        print("Switching to terminal interactive mode...")
        run_tui()


if __name__ == "__main__":
    import sys

    # Select run mode based on command line argument
    if len(sys.argv) > 1:
        if sys.argv[1] == '--tui':
            run_tui()
        elif sys.argv[1] == '--prompt':
            # 从命令行提示词生成/导入作业并点评
            if len(sys.argv) < 3:
                print("Usage: python hybrid_english_tutor_langgraph.py --prompt 'I want Math and English homework'")
                sys.exit(1)
            
            user_input = sys.argv[2]
            student_id = sys.argv[3] if len(sys.argv) > 3 else "student1"
            
            filepath = process_homework_with_review(user_input, student_id)
            print(f"\nDone! Homework with review saved to: {filepath}")
        else:
            print("Unknown argument. Available options:")
            print("  --tui     : Terminal interactive mode")
            print("  --prompt  : Generate/import 5-day homework with review from natural language prompt")
            print("  (no arg)  : Web GUI mode (default)")
            print("\nExample: python hybrid_english_tutor_langgraph.py --prompt 'I need Math, English, and Science homework for this week'")
    else:
        run_gui()  # Default to Web interface
