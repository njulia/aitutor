#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Efficient 52-week Non-Verbal Reasoning plan built from the canonical practice generator.

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
    from scripts.elevenplus.elevenplus_nvr_generator import generate_11plus_nvr_homework, ELEVEN_PLUS_NVR_TOPICS
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    generate_11plus_nvr_homework = None
    ELEVEN_PLUS_NVR_TOPICS = []
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
  'termName': 'Term 1: Visual Sequences, Rotations & Symmetry',
  'focus': 'Developing foundational skills in identifying sequential pattern shifts, directional '
           'orientation, and bilateral symmetry.',
  'weeks': [{'weekNum': 1,
             'topic': 'Shape Sequences & Progressions',
             'focus': 'Single Attribute Progressions',
             'objectives': ['Track shifts across a single visual dimension (colour transitions).',
                            'Deduce cyclic or stepwise sequences using a structured emoji vocabulary.',
                            'Identify correct options based on a single distinct property shift.']},
            {'weekNum': 2,
             'topic': 'Shape Sequences & Progressions',
             'focus': 'Alternating Pattern Sequences',
             'objectives': ['Decipher interleaving rules where shapes follow dual, alternating threads.',
                            'Determine the joint relationship between shape type transitions and color '
                            'cycles.',
                            'Construct logical chains on scrap paper to prevent visual errors.']},
            {'weekNum': 3,
             'topic': 'Shape Sequences & Progressions',
             'focus': 'Complex Progression Steps',
             'objectives': ['Evaluate composite sequences where both shape attributes change simultaneously.',
                            'Identify wrap-around boundaries where attribute lists restart from the '
                            'beginning.',
                            'Practice rapid elimination of distractors in complex multi-step series.']},
            {'weekNum': 4,
             'topic': 'Rotation & Angular Alignment',
             'focus': 'Clockwise Rotations',
             'objectives': ['Understand angular rotations in multiples of 45 degrees.',
                            'Track the clockwise movement of indicator arrows and structural pointers.',
                            'Match orientation outcomes against standardised compass markings.']},
            {'weekNum': 5,
             'topic': 'Rotation & Angular Alignment',
             'focus': 'Anti-Clockwise Rotations',
             'objectives': ['Deduce anti-clockwise rotational steps of 45°, 90°, and 135°.',
                            'Determine standard directional transitions on a mental circle.',
                            'Isolate angle increments from overall shape translations.']},
            {'weekNum': 6,
             'topic': 'Rotation & Angular Alignment',
             'focus': 'Alternating & Multi-Step Rotations',
             'objectives': ['Solve progressive rotations with alternating degrees (e.g., +45°, +90°, +45°).',
                            'Identify complex directional flips (180° turns).',
                            'Handle composite rotation questions with high confidence.']},
            {'weekNum': 7,
             'topic': 'Reflection & Mirror Lines',
             'focus': 'Vertical Mirror Reflection',
             'objectives': ['Perform 2D reflections across a vertical axis of symmetry.',
                            'Understand how left-right properties swap while up-down alignments remain '
                            'unchanged.',
                            'Practice identifying mirrored positions of pointing indicators.']},
            {'weekNum': 8,
             'topic': 'Reflection & Mirror Lines',
             'focus': 'Horizontal Mirror Reflection',
             'objectives': ['Apply reflections across a horizontal baseline.',
                            'Deduce how up-down alignments are inverted while left-right stays fixed.',
                            'Trace mirrored positions of arrows and overlapping segments.']},
            {'weekNum': 9,
             'topic': 'Reflection & Mirror Lines',
             'focus': 'Double & Compound Reflections',
             'objectives': ['Evaluate compound reflections (vertical then horizontal reflections).',
                            'Distinguish simple 180° rotations from composite dual-axis reflections.',
                            'Eliminate deceptively close option traps in reflective reasoning.']},
            {'weekNum': 10,
             'topic': 'Symmetry & Fold lines',
             'focus': 'Axes of Symmetry',
             'objectives': ['Determine how many mirror lines exist in regular and irregular geometric '
                            'shapes.',
                            'Identify matching pairs that reflect perfectly across multiple lines of '
                            'symmetry.',
                            'Master visual fold-and-unfold patterns.']},
            {'weekNum': 11,
             'topic': 'Rotations & Reflections Mixed',
             'focus': 'Distinguishing Rotation vs Reflection',
             'objectives': ['Determine if a test shape is a rotated or a reflected version of a source '
                            'shape.',
                            'Recognize chiral/non-superimposable shapes.',
                            'Apply systematic rotation checks to eliminate reflection options.']},
            {'weekNum': 12,
             'topic': 'Grid Translations',
             'focus': 'Spatial Moves & Coordinates',
             'objectives': ['Track step-by-step movements of symbols inside 2D grid containers.',
                            'Deduce the combined effect of direction, step size, and wrap-around boundaries.',
                            'Verify intermediate spatial positions carefully.']},
            {'weekNum': 13,
             'topic': 'Shape Sequences & Progressions',
             'focus': 'Term 1 Review & Mixed Test',
             'objectives': ['Synthesize shape series, angular rotations, reflections, and translation paths.',
                            'Complete a mixed diagnostic quiz containing multiple NVR topics.',
                            'Review step-by-step explanations to correct visual mistakes.']}]},
 {'termId': 2,
  'termName': 'Term 2: Analogies, Matrices & Grid Completion',
  'focus': 'Expanding skills into relative reasoning, 2D grid matrix configurations, and categorization '
           'rules.',
  'weeks': [{'weekNum': 14,
             'topic': 'Shape Analogies & Attribute Changes',
             'focus': 'Colour Shift Analogies',
             'objectives': ['Understand relative analogies (A is to B as C is to D).',
                            'Detect how colour traits shift under specific transformation rules.',
                            'Apply exact transformation rules to find matching destination shapes.']},
            {'weekNum': 15,
             'topic': 'Shape Analogies & Attribute Changes',
             'focus': 'Type Swap Analogies',
             'objectives': ['Deduce relationships based on switching outline types (circles to squares, '
                            'etc.).',
                            'Isolate multi-level transitions where shape and size parameters are swapped.',
                            'Verify the consistency of transitions across both analogy pairs.']},
            {'weekNum': 16,
             'topic': 'Shape Analogies & Attribute Changes',
             'focus': 'Compound Multi-Attribute Analogies',
             'objectives': ['Solve analogies where type, color, and size vary simultaneously.',
                            'Formulate explicit transformation sentences in your mind before viewing '
                            'options.',
                            'Successfully eliminate options that only satisfy half the rule.']},
            {'weekNum': 17,
             'topic': 'Matrix Completion & Grid Logic',
             'focus': '2x2 Attribute Shift Matrices',
             'objectives': ['Analyse 2x2 grid layouts with a single missing cell.',
                            'Track attribute variations across rows (horizontal rules) and columns (vertical '
                            'rules).',
                            'Identify the correct cell that satisfies both grid vectors simultaneously.']},
            {'weekNum': 18,
             'topic': 'Matrix Completion & Grid Logic',
             'focus': '2x2 Rotational Matrices',
             'objectives': ['Track rotations of symbols inside grid compartments.',
                            'Verify if rotational steps are uniform or variable across rows.',
                            'Isolate orientation directions to pinpoint correct cells.']},
            {'weekNum': 19,
             'topic': 'Matrix Completion & Grid Logic',
             'focus': 'Complex Grid Logic',
             'objectives': ['Analyse grid properties involving additions, subtractions, or intersections.',
                            'Study cell relationships where attributes are combined to form subsequent '
                            'cells.',
                            'Synthesize row and column trends to solve high-difficulty matrices.']},
            {'weekNum': 20,
             'topic': 'Odd One Out & Shape Discrepancy',
             'focus': 'Shape Discrepancies',
             'objectives': ['Locate the single shape that breaks general geometric or category rules.',
                            'Establish systematic checking orders (shape type, size, orientation, count).',
                            'Defeat options designed to look like the odd one out.']},
            {'weekNum': 21,
             'topic': 'Odd One Out & Shape Discrepancy',
             'focus': 'Colour Discrepancies',
             'objectives': ['Isolate groups bound by strict color rules.',
                            'Deduce temperature patterns (warm vs cool colors) as grouping criteria.',
                            'Identify anomalies that break group color trends.']},
            {'weekNum': 22,
             'topic': 'Odd One Out & Shape Discrepancy',
             'focus': 'Orientation Discrepancies',
             'objectives': ['Deduce directional guidelines common to four shapes.',
                            'Identify the single shape that rotates or points in an incompatible direction.',
                            'Perform quick mental rotations to ensure groups are superimposable.']},
            {'weekNum': 23,
             'topic': 'Odd One Out & Shape Discrepancy',
             'focus': 'Counting & Numerical Discrepancies',
             'objectives': ['Spot groupings based on numerical tallies (sides, intersections, elements).',
                            'Isolate odd-one-out cases based on even/odd or specific totals.',
                            'Check segment divisions carefully.']},
            {'weekNum': 24,
             'topic': 'Matrix Completion & Grid Logic',
             'focus': 'Advanced Grid & Analogy Mastery',
             'objectives': ['Solve advanced compound matrices and complex analogies.',
                            'Differentiate near-identical options with extreme accuracy.',
                            'Build mental speed through systematic visual scanning.']},
            {'weekNum': 25,
             'topic': 'Matrix Completion & Grid Logic',
             'focus': 'Find the Missing Section',
             'objectives': ['Reconstruct complete drawings by identifying matching missing patches.',
                            'Align textures, lines, and borders perfectly at boundary interfaces.',
                            'Master continuous spatial line continuation.']},
            {'weekNum': 26,
             'topic': 'Matrix Completion & Grid Logic',
             'focus': 'Term 2 Review & Diagnostic Quiz',
             'objectives': ['Consolidate analogies, grid completion, and odd-one-out rules.',
                            'Diagnose weak areas through a 10-question mixed assessment.',
                            'Analyse detailed worked answers to clarify grid logic.']}]},
 {'termId': 3,
  'termName': 'Term 3: Coding, Groupings & Counting',
  'focus': 'Mastering non-verbal ciphers, group associations, item tallies, and overlap relationships.',
  'weeks': [{'weekNum': 27,
             'topic': 'Shape Codes & Attribute Translation',
             'focus': 'Direct Attribute Mapping',
             'objectives': ['Deconstruct multi-letter code mappings for shapes.',
                            'Associate specific letter slots with individual shape traits (type, color).',
                            'Decode unseen target shapes by combining extracted rules.']},
            {'weekNum': 28,
             'topic': 'Shape Codes & Attribute Translation',
             'focus': 'Alternating Code Patterns',
             'objectives': ['Solve complex codes where letter representations cycle.',
                            'Determine positional rules for codes that represent outline features.',
                            'Verify choices by translating code letters back into shapes.']},
            {'weekNum': 29,
             'topic': 'Shape Codes & Attribute Translation',
             'focus': 'Complex Attribute Translation',
             'objectives': ['Deduce multi-letter codes representing orientation, layering, or sizes.',
                            'Eliminate options rapidly by decoding single letter positions.',
                            'Complete high-difficulty code matching with perfect accuracy.']},
            {'weekNum': 30,
             'topic': 'Similarity Grouping & Group Association',
             'focus': 'Shape Type Associations',
             'objectives': ['Analyse two predefined reference groups of shapes.',
                            'Identify the core defining traits that bind Group 1 and Group 2.',
                            'Assign a target test shape to the correct group based on rules.']},
            {'weekNum': 31,
             'topic': 'Similarity Grouping & Group Association',
             'focus': 'Color Temperature Categories',
             'objectives': ['Recognize abstract color-bound grouping rules.',
                            'Categorize target shapes based on warm versus cool color clusters.',
                            'Differentiate group associations with absolute precision.']},
            {'weekNum': 32,
             'topic': 'Similarity Grouping & Group Association',
             'focus': 'Symmetry & Alignment Grouping',
             'objectives': ['Deduce group boundaries defined by bilateral or rotational symmetry.',
                            'Assign complex shapes to groups based on core structural properties.',
                            'Establish systematic evaluation paths.']},
            {'weekNum': 33,
             'topic': 'Shape Counting & Combinatorial Totals',
             'focus': 'Category Tallies',
             'objectives': ['Scan multi-shape sets to count specific sub-categories.',
                            'Count by color criteria under visual pressure.',
                            'Select the correct total from close numeric MCQ choices.']},
            {'weekNum': 34,
             'topic': 'Shape Counting & Combinatorial Totals',
             'focus': 'Intersecting & Overlapping Counts',
             'objectives': ['Count region overlaps, shared borders, or intersections.',
                            'Distinguish nested symbols from overlapping boundaries.',
                            'Master combinatorial counting.']},
            {'weekNum': 35,
             'topic': 'Shape Counting & Combinatorial Totals',
             'focus': 'Segment & Line Counting',
             'objectives': ['Tally line segments, division lines, or corner vertices.',
                            'Perform quick geometric math on complex multi-line symbols.',
                            'Verify the counts to avoid silly calculation mistakes.']},
            {'weekNum': 36,
             'topic': 'Layering & Overlapping Shapes',
             'focus': 'Foreground Layer Identification',
             'objectives': ['Analyse composite drawings with overlapping shapes.',
                            'Locate which shape has an unbroken, complete boundary (lies on top).',
                            'Identify correct layer order hierarchies.']},
            {'weekNum': 37,
             'topic': 'Layering & Overlapping Shapes',
             'focus': 'Background & Midground Sorting',
             'objectives': ['Determine which shapes are placed at the bottom-most layers.',
                            'Trace partially obstructed borders to identify shape types.',
                            'Evaluate depth indexes in 2D layered graphics.']},
            {'weekNum': 38,
             'topic': 'Similarity Grouping & Group Association',
             'focus': 'Coding & Grouping Integration',
             'objectives': ['Solve hybrid questions that combine coding, groupings, and overlapping layers.',
                            'Isolate distinct variables to avoid confusion.',
                            'Verify choices systematically.']},
            {'weekNum': 39,
             'topic': 'Shape Counting & Combinatorial Totals',
             'focus': 'Term 3 Review & Mixed Diagnostic Exam',
             'objectives': ['Synthesize shape codes, similarity groups, counts, and layering logic.',
                            'Complete a mixed diagnostic test of 10 questions under 10 minutes.',
                            'Eliminate common error patterns.']}]},
 {'termId': 4,
  'termName': 'Term 4: 3D Spatial Reasoning & Advanced Exam Mastery',
  'focus': 'Transitioning to 3D spatial folding, nets of cubes, isometric perspectives, and high-speed mock '
           'exams.',
  'weeks': [{'weekNum': 40,
             'topic': '3D Spatial Nets & Isometric Reasoning',
             'focus': 'Folding Cubes from 2D Nets',
             'objectives': ['Visualize folding a 2D cross-like net into a 3D cube.',
                            'Identify opposite faces that can never touch in 3D space.',
                            'Verify adjacent face arrangements and orientations.']},
            {'weekNum': 41,
             'topic': '3D Spatial Nets & Isometric Reasoning',
             'focus': 'Unfolding Cube Faces',
             'objectives': ['Track 3D cube faces as they are unfolded flat into 2D nets.',
                            'Determine the relative positions of symbols when flattened.',
                            'Match face coordinates perfectly.']},
            {'weekNum': 42,
             'topic': '3D Spatial Nets & Isometric Reasoning',
             'focus': 'Isometric Side Projections',
             'objectives': ['Construct 2D planar silhouettes (top, front, right views) from 3D block '
                            'assemblies.',
                            'Deduce spatial arrangements from orthographic plans.',
                            'Track block visibility accurately.']},
            {'weekNum': 43,
             'topic': '3D Spatial Nets & Isometric Reasoning',
             'focus': 'Block Counting in 3D Structures',
             'objectives': ['Tally individual blocks in complex 3D structures (including hidden support '
                            'blocks).',
                            'Construct block counts layer-by-layer to ensure accuracy.',
                            'Verify totals against distractor choices.']},
            {'weekNum': 44,
             'topic': 'Shape Sequences & Progressions',
             'focus': 'Combined Multi-Step Sequences',
             'objectives': ['Evaluate ultra-complex sequence patterns.',
                            'Formulate explicit attribute tracking grids under time pressure.',
                            'Achieve rapid elimination of distractors.']},
            {'weekNum': 45,
             'topic': 'Rotation & Angular Alignment',
             'focus': 'Advanced Spatial Rotations',
             'objectives': ['Analyse angular alignments combining 2D rotations and mirroring.',
                            'Spot chiral mismatches instantly.',
                            'Boost rotational speed under strict time conditions.']},
            {'weekNum': 46,
             'topic': 'Shape Sequences & Progressions',
             'focus': 'High-Speed Practice: Series & Matrices',
             'objectives': ['Complete rapid series and matrix questions under 45 seconds each.',
                            'Maintain accuracy while working under high-pressure conditions.',
                            'Adopt streamlined elimination tactics.']},
            {'weekNum': 47,
             'topic': 'Shape Codes & Attribute Translation',
             'focus': 'High-Speed Practice: Codes & Grouping',
             'objectives': ['Apply high-speed ciphers and classification grouping tests.',
                            'Diagnose and correct visual parsing slips immediately.',
                            'Solidify the letter-to-attribute mapping methods.']},
            {'weekNum': 48,
             'topic': '3D Spatial Nets & Isometric Reasoning',
             'focus': 'High-Speed Practice: 3D Nets & Layering',
             'objectives': ['Practice folding cubes and overlapping layering questions under time pressure.',
                            'Maintain spatial coordinates without getting confused.',
                            'Solve 3D spatial queries in under 50 seconds.']},
            {'weekNum': 49,
             'topic': 'Odd One Out & Shape Discrepancy',
             'focus': 'Mock Exam Paper 1: Standard GL Style',
             'objectives': ['Complete a 10-question mixed NVR exam representing standard difficulty.',
                            'Adopt appropriate time budgeting: exactly 1 minute per question.',
                            'Refine the tracking of multiple attributes.']},
            {'weekNum': 50,
             'topic': 'Shape Analogies & Attribute Changes',
             'focus': 'Mock Exam Paper 2: Hard Selective Style',
             'objectives': ['Complete a difficult 10-question mixed exam focusing on selective school '
                            'standards.',
                            'Solve complex composite matrices and analogies.',
                            'Learn to manage difficult questions by marking them and moving on.']},
            {'weekNum': 51,
             'topic': '3D Spatial Nets & Isometric Reasoning',
             'focus': 'Mock Exam Paper 3: Ultimate Mastery Style',
             'objectives': ['Complete the most challenging 10-question mixed exam including 3D folding and '
                            'overlapping layers.',
                            'Track 3D structures with extreme precision.',
                            'Achieve a target accuracy of 90% or higher.']},
            {'weekNum': 52,
             'topic': 'Reflection & Mirror Lines',
             'focus': 'Full Year-Round Review & Celebration',
             'objectives': ['Synthesize key methodologies for all 11 NVR topics.',
                            'Celebrate completing the 52-week curriculum successfully.',
                            'Formulate custom checklist reminders for real exam day.']}]}]
TOPIC_ALIASES = {'Symmetry & Fold lines': 'Reflection & Mirror Lines',
 'Rotations & Reflections Mixed': 'Rotation & Angular Alignment',
 'Grid Translations': 'Matrix Completion & Grid Logic'}
MIXED_CURRICULUM_TOPICS = set([])
SUBJECT = 'Non-Verbal Reasoning'
RAG_SUBJECT = 'NonVerbalReasoning-1year'
OUTPUT_JSON = '11_Plus_NVR_52_Week_Plan.json'
OUTPUT_MARKDOWN = '11_Plus_NVR_52_Week_Plan.md'
DOC_ID_PREFIX = 'elevenplus_nvr_year_round_week_'


def _find_week(week_num: int) -> tuple[Dict[str, Any], Dict[str, Any]]:
    for term in CURRICULUM:
        for week in term["weeks"]:
            if int(week["weekNum"]) == int(week_num):
                return term, week
    raise ValueError(f"Unknown week number: {week_num}")


def _available_topics() -> List[str]:
    return [str(item[0]) for item in ELEVEN_PLUS_NVR_TOPICS]


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
        _, generated = generate_11plus_nvr_homework(
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
        _, records = generate_11plus_nvr_homework(
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
    if generate_11plus_nvr_homework is None:
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
