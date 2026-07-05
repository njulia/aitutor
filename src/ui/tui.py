#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
终端交互界面 (TUI) 模块
"""

from datetime import datetime

from src.models import (
    UK_PRIMARY_SUBJECTS, SAMPLE_STUDENT_PROFILES, get_homework_time_by_age,
)
from src.homework_manager import generate_homework_with_custom_profile


def run_tui(llm):
    """Terminal interactive mode - 作业生成器"""
    model_name = getattr(llm, "model", "unknown")
    print("=== AI Homework Generator for UK Primary School Students (Year 1-6) ===\n")
    print(f"Using Model: {model_name}\n")

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
