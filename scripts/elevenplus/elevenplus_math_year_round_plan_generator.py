#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Efficient 52-week Maths plan built from the canonical practice generator.

The curriculum roadmap is unchanged. Question creation is delegated to the main
subject generator so practice, topic mastery and year-round plans share one
validated answer format and one source of question logic.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from scripts.elevenplus.elevenplus_math_generator import generate_11plus_homework, ELEVEN_PLUS_TOPICS
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    generate_11plus_homework = None
    ELEVEN_PLUS_TOPICS = []
    get_elevenplus_rag_store = None

from scripts.elevenplus.elevenplus_generator_utils import (
    build_multiple_choice_question,
    difficulty_for_week,
    ensure_unique_question_stems,
    records_to_year_round_questions,
    validate_answer_records,
)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

CURRICULUM = [{'termId': 1,
  'termName': 'Term 1: Arithmetic & Number Sense Foundations',
  'focus': 'Mastering core operations, order of operations, and fundamental properties of numbers.',
  'weeks': [{'weekNum': 1,
             'topic': 'Number: Arithmetic & Mental Maths',
             'focus': 'Place Value & Large Number Addition/Subtraction',
             'objectives': ['Understand place value up to millions and decimals.',
                            'Perform precise column addition and subtraction on numbers up to 10,000.',
                            'Identify common borrowing and carrying errors.']},
            {'weekNum': 2,
             'topic': 'Number: Arithmetic & Mental Maths',
             'focus': 'Mental Math Shortcuts & Estimation',
             'objectives': ['Use rounding to estimate results of complex calculations.',
                            'Apply mental compensation strategies (e.g., adding 99 by adding 100 and '
                            'subtracting 1).',
                            'Double-check arithmetic using unit-digit analysis.']},
            {'weekNum': 3,
             'topic': 'Number: Arithmetic & Mental Maths',
             'focus': 'Long Multiplication Techniques',
             'objectives': ['Multiply 3-digit numbers by 2-digit numbers using standard column method.',
                            'Understand the grid method and partitioning for visual confirmation.',
                            'Multiply decimals by 10, 100, and 1000.']},
            {'weekNum': 4,
             'topic': 'Number: Arithmetic & Mental Maths',
             'focus': 'Short and Long Division (Bus Stop Method)',
             'objectives': ['Master short division with integer and decimal remainders.',
                            'Perform long division by 2-digit numbers using list-of-multiples scaffolding.',
                            'Express remainders as fractions or decimals.']},
            {'weekNum': 5,
             'topic': 'Number: Arithmetic & Mental Maths',
             'focus': 'Order of Operations (BODMAS/BIDMAS)',
             'objectives': ['Understand priority of brackets, indices, division/multiplication, and '
                            'addition/subtraction.',
                            'Evaluate complex multi-step expressions.',
                            'Insert missing brackets to make equations true.']},
            {'weekNum': 6,
             'topic': 'Number: Primes, Factors & Multiples',
             'focus': 'Factors, Multiples & Prime Numbers',
             'objectives': ['Define and list factors and multiples of numbers up to 100.',
                            'Identify and memorize prime numbers up to 100.',
                            'Recognize prime and composite numbers under time pressure.']},
            {'weekNum': 7,
             'topic': 'Number: Primes, Factors & Multiples',
             'focus': 'Highest Common Factor & Lowest Common Multiple',
             'objectives': ['Find the HCF of two or three numbers using listing and prime factors.',
                            'Find the LCM of two or three numbers using listing and prime factors.',
                            'Solve worded scheduling and grouping problems using LCM/HCF.']},
            {'weekNum': 8,
             'topic': 'Number: Primes, Factors & Multiples',
             'focus': 'Square Numbers, Cube Numbers & Roots',
             'objectives': ['Recognize perfect squares up to 15x15 and cubes up to 5x5x5.',
                            'Understand square roots and cube roots as inverse operations.',
                            'Apply squares and cubes to geometric area/volume problems.']},
            {'weekNum': 9,
             'topic': 'Number: Fractions, Decimals & Percentages',
             'focus': 'Fractions: Equivalent & Ordering',
             'objectives': ['Simplify fractions to their lowest terms using HCF.',
                            'Find equivalent fractions by multiplying or dividing numerators and '
                            'denominators.',
                            'Compare and order fractions using common denominators.']},
            {'weekNum': 10,
             'topic': 'Number: Fractions, Decimals & Percentages',
             'focus': 'Fractions: Addition & Subtraction',
             'objectives': ['Add and subtract fractions with different denominators.',
                            'Work with mixed numbers and improper fractions.',
                            'Solve real-world fraction sharing word problems.']},
            {'weekNum': 11,
             'topic': 'Number: Fractions, Decimals & Percentages',
             'focus': 'Fractions: Multiplication, Division & Quantities',
             'objectives': ['Multiply fractions by integers and other fractions.',
                            'Divide fractions using the reciprocal method (Keep-Change-Flip).',
                            'Calculate fractions of non-routine whole amounts.']},
            {'weekNum': 12,
             'topic': 'Number: Fractions, Decimals & Percentages',
             'focus': 'Decimals: Place Value & Conversions',
             'objectives': ['Understand decimal place value up to thousandths.',
                            'Order and compare decimal values.',
                            'Convert simple fractions to decimals and vice versa.']},
            {'weekNum': 13,
             'topic': 'Number: Arithmetic & Mental Maths',
             'focus': 'Term 1 Review & Foundations Mastery Test',
             'objectives': ['Synthesize arithmetic, division, primes, and fraction basics.',
                            'Solve 10 exam-style mixed multi-step foundation problems.',
                            'Refine timing: achieve under 45 seconds per question.']}]},
 {'termId': 2,
  'termName': 'Term 2: Proportional Reasoning & Basics of Algebra',
  'focus': 'Mastering percentages, ratios, scaling, equations, and number patterns.',
  'weeks': [{'weekNum': 14,
             'topic': 'Number: Fractions, Decimals & Percentages',
             'focus': 'Percentages: Core Concept & Basic Conversions',
             'objectives': ['Understand percentages as parts of 100.',
                            'Convert fluently between fractions, decimals, and percentages.',
                            'Identify key equivalence sets (e.g., 3/8 = 37.5% = 0.375).']},
            {'weekNum': 15,
             'topic': 'Number: Fractions, Decimals & Percentages',
             'focus': 'Percentages of Amounts & Scaling',
             'objectives': ['Calculate 10%, 5%, 1%, 25%, 50%, and 75% of whole amounts.',
                            'Use building blocks to find complex percentages (e.g., 17% of 200).',
                            'Solve percentage word problems in commercial contexts (e.g., sales '
                            'discounts).']},
            {'weekNum': 16,
             'topic': 'Number: Fractions, Decimals & Percentages',
             'focus': 'Percentage Increase and Decrease',
             'objectives': ['Increase and decrease amounts by a given percentage.',
                            'Solve problems involving successive percentage changes.',
                            'Work backwards to find the original amount (reverse percentages).']},
            {'weekNum': 17,
             'topic': 'Ratio and Proportion',
             'focus': 'Introduction to Ratio & Sharing',
             'objectives': ['Understand ratio notation (e.g., A:B) as part-to-part comparisons.',
                            'Simplify ratios to their lowest terms.',
                            "Share a total amount into a given ratio using the 'add parts, divide, multiply' "
                            'rule.']},
            {'weekNum': 18,
             'topic': 'Ratio and Proportion',
             'focus': 'Advanced Ratio & Parts Changing',
             'objectives': ['Solve ratio problems where one part is known and the total must be found.',
                            'Work with multi-part ratios (e.g., A:B:C).',
                            'Analyze problems where ratio proportions change after an addition/removal.']},
            {'weekNum': 19,
             'topic': 'Ratio and Proportion',
             'focus': 'Direct and Inverse Proportion',
             'objectives': ['Solve direct proportion problems (recipes, currency conversions).',
                            'Understand inverse proportion (e.g., more workers taking less time).',
                            'Apply scaling factors to solve multi-variable proportion puzzles.']},
            {'weekNum': 20,
             'topic': 'Ratio and Proportion',
             'focus': 'Scale Drawings, Maps & Model Scales',
             'objectives': ['Interpret scales on map drawings (e.g., 1:25,000).',
                            'Convert scale distances to actual real-world units (cm to m or km).',
                            'Calculate scale factors for models and plans.']},
            {'weekNum': 21,
             'topic': 'Algebra Basics',
             'focus': 'Algebraic Expressions & Substitution',
             'objectives': ['Understand that letters represent variables.',
                            'Simplify expressions by collecting like terms (e.g., 3a + 2b - a).',
                            'Substitute integers and decimals into algebraic formulas.']},
            {'weekNum': 22,
             'topic': 'Algebra Basics',
             'focus': 'Solving Single-Variable Equations',
             'objectives': ['Solve single-step equations using inverse operations (e.g., x + 5 = 12).',
                            'Solve equations involving multiplication and division (e.g., 3x = 15).',
                            'Keep equations balanced by performing identical operations on both sides.']},
            {'weekNum': 23,
             'topic': 'Algebra Basics',
             'focus': 'Two-Step Equations & Word Problem Modeling',
             'objectives': ['Solve two-step equations (e.g., 4x - 3 = 17).',
                            'Translate written word problems into formal algebraic equations.',
                            'Verify answers by substituting them back into the original problem.']},
            {'weekNum': 24,
             'topic': 'Sequences and Patterns',
             'focus': 'Number Sequences: Term-to-Term Rules',
             'objectives': ['Identify arithmetic sequences with constant addition or subtraction.',
                            'Recognize geometric sequences with constant multiplication or division.',
                            'Find missing terms in complex nested or alternating sequences.']},
            {'weekNum': 25,
             'topic': 'Sequences and Patterns',
             'focus': 'Number Sequences: Nth Term Foundations',
             'objectives': ['Find the linear formula (Nth term) for a constant difference sequence.',
                            'Determine if a specific number belongs to a given sequence.',
                            'Explore non-linear sequences (Fibonacci, triangular, square numbers).']},
            {'weekNum': 26,
             'topic': 'Algebra Basics',
             'focus': 'Term 2 Review & Algebra/Ratio Mastery Test',
             'objectives': ['Evaluate percentage increases, ratio division, and algebra equations.',
                            'Complete a mixed 10-question set mimicking Henrietta Barnett exam styles.',
                            'Focus on rigorous working out steps for partial credit.']}]},
 {'termId': 3,
  'termName': 'Term 3: Shape, Space, Measures & Data Handling',
  'focus': 'Developing spatial intelligence, geometry, units, and data analysis skills.',
  'weeks': [{'weekNum': 27,
             'topic': 'Shape, Space and Measures',
             'focus': 'Angles: Basic Rules & Intersecting Lines',
             'objectives': ['Identify acute, obtuse, reflex, and right angles.',
                            'Apply rules: angles on a straight line add to 180°, and around a point add to '
                            '360°.',
                            'Recognize vertically opposite and parallel line angles '
                            '(alternate/corresponding).']},
            {'weekNum': 28,
             'topic': 'Shape, Space and Measures',
             'focus': 'Angles in Triangles & Polygons',
             'objectives': ['Recall that interior angles of a triangle add up to 180°.',
                            'Calculate angles in quadrilaterals (adding to 360°).',
                            'Find interior and exterior angles of regular polygons.']},
            {'weekNum': 29,
             'topic': 'Shape, Space and Measures',
             'focus': 'Area and Perimeter of Core Shapes',
             'objectives': ['Calculate the perimeter of rectangles, squares, and triangles.',
                            'Apply area formulas: Rectangle = L x W; Triangle = (Base x Height) / 2.',
                            'Differentiate clearly between square units and linear units.']},
            {'weekNum': 30,
             'topic': 'Shape, Space and Measures',
             'focus': 'Area and Perimeter of Compound Shapes',
             'objectives': ['Deconstruct irregular compound shapes into standard rectangles and triangles.',
                            'Calculate missing dimensions before performing area/perimeter steps.',
                            'Solve shaded area problems (subtracting one area from another).']},
            {'weekNum': 31,
             'topic': 'Shape, Space and Measures',
             'focus': 'Volume and Surface Area of Cuboids',
             'objectives': ['Calculate volume of cubes and cuboids (Length x Width x Height).',
                            'Find the surface area of a cuboid by calculating the sum of its six faces.',
                            'Solve worded liquid volume and capacity displacement problems.']},
            {'weekNum': 32,
             'topic': 'Shape, Space and Measures',
             'focus': '3D Shapes: Vertices, Edges & Nets',
             'objectives': ['Count faces, edges, and vertices of regular 3D solids (prisms, pyramids).',
                            'Identify valid nets of cubes, prisms, and cylinders.',
                            'Visualize folding nets to solve orientation puzzles.']},
            {'weekNum': 33,
             'topic': 'Shape, Space and Measures',
             'focus': 'Coordinates & Transformations',
             'objectives': ['Read and plot coordinates in all four quadrants.',
                            'Translate shapes on a coordinate grid.',
                            'Reflect shapes across horizontal, vertical, and diagonal mirror lines.']},
            {'weekNum': 34,
             'topic': 'Shape, Space and Measures',
             'focus': 'Metric and Imperial Unit Conversions',
             'objectives': ['Convert between metric units of length (mm, cm, m, km).',
                            'Convert between metric units of mass (g, kg) and capacity (ml, l).',
                            'Know basic imperial conversions (e.g., 5 miles ≈ 8 km, 1 kg ≈ 2.2 lbs).']},
            {'weekNum': 35,
             'topic': 'Shape, Space and Measures',
             'focus': 'Time, Clocks & Calendar Arithmetic',
             'objectives': ['Read analogue clocks and compute elapsed time intervals.',
                            'Convert between 12-hour (am/pm) and 24-hour digital clock notation.',
                            "Solve calendar arithmetic problems (e.g., 'What day is 45 days after "
                            "Tuesday?')."]},
            {'weekNum': 36,
             'topic': 'Speed, Distance and Time',
             'focus': 'Speed, Distance and Time Calculations',
             'objectives': ['Use the speed-distance-time triangle formula.',
                            'Convert time units (e.g., 2.5 hours = 2 hours 30 minutes) before multiplying '
                            'speed.',
                            'Solve multi-leg journeys and average speed word problems.']},
            {'weekNum': 37,
             'topic': 'Data Handling and Graphs',
             'focus': 'Statistics: Averages and Range',
             'objectives': ['Calculate the Mean (average) of a set of data.',
                            'Find the Median (middle value) and Mode (most frequent value).',
                            'Calculate the Range (highest minus lowest) and solve missing-data problems.']},
            {'weekNum': 38,
             'topic': 'Data Handling and Graphs',
             'focus': 'Interpreting Charts & Graphs',
             'objectives': ['Read and interpret data from bar charts, pictograms, and line graphs.',
                            'Deconstruct complex Venn diagrams and Carroll diagrams.',
                            'Answer comparative and multi-step questions based on visual charts.']},
            {'weekNum': 39,
             'topic': 'Shape, Space and Measures',
             'focus': 'Term 3 Review & Geometry/Measures Mastery Test',
             'objectives': ['Apply speed formulas, elapsed time, compound area, and average tables.',
                            'Take an interactive GL-style geometry and measures assessment.',
                            'Analyze and eliminate common decimal conversion errors.']}]},
 {'termId': 4,
  'termName': 'Term 4: Advanced Problem Solving, Non-Routine Reasoning & Exam Mastery',
  'focus': 'Synthesizing all modules to solve complex, super-selective non-routine problems.',
  'weeks': [{'weekNum': 40,
             'topic': 'Worded Problem Solving',
             'focus': 'Multi-Step Worded Problems',
             'objectives': ['Identify and highlight key details in lengthy, wordy scenarios.',
                            'Break a large worded problem into sequential, manageable math operations.',
                            'Verify answers by performing reverse calculation loops.']},
            {'weekNum': 41,
             'topic': 'Data Handling and Graphs',
             'focus': 'Venn Diagrams & Sorting Puzzles',
             'objectives': ['Represent complex multi-factor group data inside Venn diagrams.',
                            "Solve overlap puzzles (e.g., '15 students play tennis, 12 play chess, 5 play "
                            "both...').",
                            'Utilize Carroll diagrams to categorize items using negative properties.']},
            {'weekNum': 42,
             'topic': 'Data Handling and Graphs',
             'focus': 'Probability and Outcomes',
             'objectives': ['Calculate basic probability of single independent events.',
                            'Express probability as a simplified fraction, decimal, and percentage.',
                            'List all possible outcomes of double events (dice and coin, spinners).']},
            {'weekNum': 43,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Non-Routine: Digit Puzzles & Cryptarithms',
             'objectives': ['Solve addition/multiplication cryptarithms where letters represent digits.',
                            'Deduce missing numbers in column additions based on units constraints.',
                            'Apply logical reasoning to solve alphanumeric puzzles.']},
            {'weekNum': 44,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Non-Routine: Work Rates & Shared Speeds',
             'objectives': ['Solve tasks where multiple agents work together at different rates.',
                            'Calculate pipe filling rates and leak drains.',
                            'Apply reciprocal ratios to solve shared speed problems.']},
            {'weekNum': 45,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Non-Routine: Age Problems & Backward Tracking',
             'objectives': ['Solve complex age-related timeline puzzles using algebra or visual blocks.',
                            'Trace operations backwards from a final result to find the starting number.',
                            'Handle multi-variable word constraints.']},
            {'weekNum': 46,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Non-Routine: Venn/Set & Pigeonhole Logic',
             'objectives': ["Apply the Pigeonhole Principle to 'guaranteed worst-case' scenarios.",
                            'Solve advanced subset questions from Henrietta Barnett Stage 2 exams.',
                            'Develop rigorous logic proofs without a calculator.']},
            {'weekNum': 47,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Super-Selective Mock Test 1 (Tiffin/HBS Style)',
             'objectives': ['Attempt 10 high-complexity non-routine questions under 15-minute time pressure.',
                            'Deduce algebraic setups under stress.',
                            'Learn to pass on ultra-hard items to maximize overall points.']},
            {'weekNum': 48,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': "Super-Selective Mock Test 2 (St Olave's Style)",
             'objectives': ['Attempt 10 high-complexity remainder and divisor logic puzzles.',
                            'Practice drafting fast, clear step-by-step scratchpad working.',
                            'Identify and isolate trap options.']},
            {'weekNum': 49,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Exam Timing: Skimming & Guessing Strategy',
             'objectives': ['Master the 3-pass exam technique (Easy first, Medium second, Guess/Hard last).',
                            'Identify and discard incorrect MCQ distractors instantly.',
                            'Develop speed-skimming for lengthy word descriptions.']},
            {'weekNum': 50,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Advanced Crossover: Math and Verbal Reasoning',
             'objectives': ['Solve math codes and letter-digit correlation matrices.',
                            'Read and analyze conditional math clues (if-then statements).',
                            'Master alphanumeric puzzle structures common in GL assessments.']},
            {'weekNum': 51,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Final Full-Syllabus Mock Exam',
             'objectives': ['Complete a full, randomized, multi-module 11+ maths paper (20 questions).',
                            'Review step-by-step feedback across all syllabus sectors.',
                            'Refine final revision flashcards.']},
            {'weekNum': 52,
             'topic': 'Non-Routine Reasoning (Top-School Style)',
             'focus': 'Ultimate Strategy, Anxiety Management & Prep',
             'objectives': ["Review active exam guidelines and Coach Pip's top selective school rules.",
                            "Plan the final week's low-intensity warm-up routine.",
                            'Build mental stamina, positive visualization, and confidence.']}]}]
TOPIC_ALIASES = {}
MIXED_CURRICULUM_TOPICS = set([])
SUBJECT = 'Maths'
RAG_SUBJECT = 'Maths-1year'
OUTPUT_JSON = '11_Plus_Maths_52_Week_Plan.json'
OUTPUT_MARKDOWN = '11_Plus_Maths_52_Week_Plan.md'
DOC_ID_PREFIX = 'elevenplus_math_year_round_week_'


def _find_week(week_num: int) -> tuple[Dict[str, Any], Dict[str, Any]]:
    for term in CURRICULUM:
        for week in term["weeks"]:
            if int(week["weekNum"]) == int(week_num):
                return term, week
    raise ValueError(f"Unknown week number: {week_num}")


def _available_topics() -> List[str]:
    return [str(item[0]) for item in ELEVEN_PLUS_TOPICS]


def _resolve_topic(curriculum_topic: str, week_num: int) -> str:
    available = _available_topics()
    if not available:
        raise RuntimeError("The subject practice generator is unavailable")
    mapped = TOPIC_ALIASES.get(curriculum_topic, curriculum_topic)
    if mapped in available:
        return mapped
    return available[(int(week_num) - 1) % len(available)]


def _mixed_answer_records(week_num: int, difficulty: str) -> List[dict]:
    topics = _available_topics()
    records: List[dict] = []
    for question_number in range(1, 11):
        topic = topics[(week_num + question_number - 2) % len(topics)]
        _, generated = generate_11plus_homework(
            topic,
            week_num * 100 + question_number,
            difficulty=difficulty,
        )
        source = dict(generated[(question_number - 1) % len(generated)])
        question_text = source["question"].split(". ", 1)[-1]
        block, canonical = build_multiple_choice_question(
            question_number,
            question_text,
            source["answer"],
            [option for option in source["options"] if option != source["answer"]],
            source.get("explanation", ""),
            source.get("tip", ""),
            difficulty,
            skill=topic,
        )
        del block
        canonical["topic"] = topic
        records.append(canonical)
    validate_answer_records(records)
    return records


def get_questions_for_week(week_num: int) -> List[dict]:
    """Return ten questions using the same structure expected by the existing UI."""
    _, week = _find_week(week_num)
    difficulty = difficulty_for_week(week_num)
    curriculum_topic = str(week["topic"])
    if curriculum_topic in MIXED_CURRICULUM_TOPICS:
        records = _mixed_answer_records(week_num, difficulty)
    else:
        generator_topic = _resolve_topic(curriculum_topic, week_num)
        _, records = generate_11plus_homework(
            generator_topic,
            int(week_num),
            difficulty=difficulty,
        )
        for record in records:
            record["curriculum_topic"] = curriculum_topic
            record["focus"] = str(week.get("focus") or "")
    records = ensure_unique_question_stems(records)
    validate_answer_records(records)
    return records_to_year_round_questions(records)


def build_plan_data() -> List[dict]:
    plan: List[dict] = []
    for term in CURRICULUM:
        term_data = {
            "termId": term["termId"],
            "termName": term["termName"],
            "focus": term["focus"],
            "weeks": [],
        }
        for week in term["weeks"]:
            term_data["weeks"].append({
                "weekNum": week["weekNum"],
                "topic": week["topic"],
                "focus": week["focus"],
                "objectives": week["objectives"],
                "difficulty": difficulty_for_week(week["weekNum"]),
                "homeworkSet": get_questions_for_week(week["weekNum"]),
            })
        plan.append(term_data)
    return plan


def generate_markdown_plan(plan_data: List[dict] | None = None) -> str:
    plan = plan_data or build_plan_data()
    lines = [f"# 11+ {SUBJECT} 52-Week Plan", ""]
    for term in plan:
        lines.extend([f"## {term['termName']}", str(term["focus"]), ""])
        for week in term["weeks"]:
            lines.append(f"### Week {week['weekNum']}: {week['focus']}")
            lines.append(f"**Topic:** {week['topic']}  ")
            lines.append(f"**Difficulty:** {week['difficulty'].title()}")
            lines.append("")
            for question in week["homeworkSet"]:
                lines.append(f"{question['id']}. {question['questionText']}")
                for option_index, option in enumerate(question["options"]):
                    lines.append(f"   {chr(65 + option_index)}) {option}")
                lines.append("")
            lines.append("#### Answer key and coaching")
            for question in week["homeworkSet"]:
                lines.append(
                    f"- **{question['id']}. {question['correctLetter']} — "
                    f"{question['correctValue']}:** {question['explanation']}"
                )
                if question.get("tip"):
                    lines.append(f"  - Tip: {question['tip']}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_rag_batch(plan_data: List[dict]) -> List[dict]:
    created_at = datetime.now(UTC).isoformat()
    batch: List[dict] = []
    for term in plan_data:
        for week in term["weeks"]:
            content_lines = [
                f"11+ {SUBJECT} 52-Week Plan - Term {term['termId']} - Week {week['weekNum']}",
                f"Topic Focus: {week['focus']}",
                f"Syllabus: {week['topic']}",
                "QUESTIONS",
                "",
            ]
            answer_records = []
            for question in week["homeworkSet"]:
                number = int(question["id"])
                content_lines.append(f"{number}. {question['questionText']}")
                for option_index, option in enumerate(question["options"]):
                    content_lines.append(f"{chr(65 + option_index)}) {option}")
                content_lines.append("")
                answer_records.append({
                    "question": f"{number}. {question['questionText']}",
                    "options": question["options"],
                    "answer": question["correctValue"],
                    "correct_letter": question["correctLetter"],
                    "explanation": question["explanation"],
                    "tip": question["tip"],
                    "difficulty": question["difficulty"],
                    "time_target_seconds": question["timeTargetSeconds"],
                })
            batch.append({
                "content": "\n".join(content_lines).strip(),
                "metadata": {
                    "year_group": 6,
                    "subject": RAG_SUBJECT,
                    "key_stage": "11+",
                    "topic": week["topic"],
                    "focus": week["focus"],
                    "week_num": week["weekNum"],
                    "term_id": term["termId"],
                    "content_type": "year_round",
                    "exam_style": "GL-style familiarisation and selective-school practice",
                    "difficulty": week["difficulty"],
                    "question_count": 10,
                    "answer_schema_version": 2,
                    "generator_version": "2026.07",
                    "correct_answers": json.dumps(answer_records, ensure_ascii=False),
                    "created_at": created_at,
                },
                "doc_id": f"{DOC_ID_PREFIX}{int(week['weekNum']):02d}",
            })
    return batch


def main() -> None:
    if generate_11plus_homework is None:
        raise RuntimeError("The canonical subject generator could not be imported")
    plan = build_plan_data()
    Path(OUTPUT_JSON).write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(OUTPUT_MARKDOWN).write_text(generate_markdown_plan(plan), encoding="utf-8")
    print(f"Saved {OUTPUT_JSON} and {OUTPUT_MARKDOWN}")

    if get_elevenplus_rag_store:
        try:
            store = get_elevenplus_rag_store()
            store.add_batch_homework(build_rag_batch(plan))
            print(f"Stored {sum(len(term['weeks']) for term in plan)} weekly sets in the 11+ RAG")
        except Exception as exc:
            print(f"RAG integration skipped or failed: {exc}")


if __name__ == "__main__":
    main()
