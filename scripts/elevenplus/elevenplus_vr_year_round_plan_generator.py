#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Efficient 52-week Verbal Reasoning plan built from the canonical practice generator.

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
    from scripts.elevenplus.elevenplus_vr_generator import generate_11plus_vr_homework, ELEVEN_PLUS_VR_TOPICS
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    generate_11plus_vr_homework = None
    ELEVEN_PLUS_VR_TOPICS = []
    get_elevenplus_rag_store = None

from scripts.elevenplus.elevenplus_generator_utils import (
    build_multiple_choice_question,
    difficulty_for_week,
    records_to_year_round_questions,
    validate_answer_records,
)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

CURRICULUM = [{'termId': 1,
  'termName': 'Term 1: Sequences, Numbers & Deciphering Codes',
  'focus': 'Mastering alphabetical progressions, mathematical patterns, visual series, and complex symbol '
           'code translation.',
  'weeks': [{'weekNum': 1,
             'topic': 'Letter Series',
             'focus': 'Single Letter Progressions',
             'objectives': ['Understand how to use the standard 26-letter alphabet sequence.',
                            'Identify and compute simple positive forward leaps (e.g., +1, +2, +3).',
                            'Apply reverse/negative leaps (e.g., -1, -2, -3) across boundary letters (Z back '
                            'to A).']},
            {'weekNum': 2,
             'topic': 'Letter Series',
             'focus': 'Alternating Letter Series',
             'objectives': ['Solve progressions where odd-indexed and even-indexed positions have distinct '
                            'rules.',
                            'Identify secondary overlay sequences in compound sequences.',
                            'Practice skipping letters accurately on scratch paper.']},
            {'weekNum': 3,
             'topic': 'Number Series',
             'focus': 'Basic Arithmetic Sequences',
             'objectives': ['Deduce constant differences between consecutive numbers (+x, -x).',
                            'Recognize simple increasing/decreasing difference patterns.',
                            'Perform quick calculations under 30-second limitations.']},
            {'weekNum': 4,
             'topic': 'Number Series',
             'focus': 'Alternating Number Progressions',
             'objectives': ['Separate dual interleaved series within a single sequence.',
                            'Determine parallel mathematical operations (+ and - working in pairs).',
                            'Establish systematic checking to avoid calculation slips.']},
            {'weekNum': 5,
             'topic': 'Number Series',
             'focus': 'Geometric & Fibonacci-like Sequences',
             'objectives': ['Identify multiplication and division patterns between terms.',
                            'Solve series where the next term is the sum of previous terms.',
                            'Master perfect squares and cubes under 150.']},
            {'weekNum': 6,
             'topic': 'Letter Codes',
             'focus': 'Direct Shift Ciphers',
             'objectives': ['Decipher words where each letter is replaced by a fixed alphabetical offset '
                            '(e.g. A->B, B->C).',
                            'Isolate code translations letter-by-letter.',
                            'Utilize multiple-choice options to rule out incorrect letters early.']},
            {'weekNum': 7,
             'topic': 'Letter Codes',
             'focus': 'Variable Shift Ciphers',
             'objectives': ['Decode ciphers where the shift increases with position (e.g., +1, +2, +3).',
                            'Decipher alternating pattern shifts (+1, -1, +1).',
                            'Improve speed by encoding the last letter of a target word first.']},
            {'weekNum': 8,
             'topic': 'Number Codes',
             'focus': 'Letter-to-Number Transposition',
             'objectives': ['Evaluate codes where letters are replaced by their alphabet position digits.',
                            'Translate number grids to complete hidden keyword matches.',
                            'Establish rapid mental indexes of key checkpoint letters (E=5, J=10, O=15, '
                            'T=20, Y=25).']},
            {'weekNum': 9,
             'topic': 'Logical Puzzles',
             'focus': 'Alphabetical Ordering & Matrix Grids',
             'objectives': ['Arrange lists of similar words in perfect lexicographical dictionary order.',
                            'Navigate simple matrix charts to find matching pairs.',
                            'Differentiate near-spellings in high-speed sorting.']},
            {'weekNum': 10,
             'topic': 'Logical Puzzles',
             'focus': 'Relative Sorting & Family Trees',
             'objectives': ['Construct relational maps based on text statements (A is taller than B, but '
                            'shorter than C).',
                            'Evaluate family relationships from descriptive hints.',
                            'Draw clear shorthand lines/diagrams to organize facts.']},
            {'weekNum': 11,
             'topic': 'Algebraic Puzzles',
             'focus': 'Balance Scales & Symbol Values',
             'objectives': ['Find numerical values of individual shapes in balanced equations.',
                            'Substitute known variables to simplify complex multi-shape balances.',
                            'Solve simple algebraic loops disguised as puzzles.']},
            {'weekNum': 12,
             'topic': 'Algebraic Puzzles',
             'focus': 'Grid Number Puzzles',
             'objectives': ['Deduce horizontal, vertical, or diagonal arithmetic operations inside grid '
                            'cells.',
                            'Locate missing center values using surrounding row/column numbers.',
                            'Spot multiplier relationships in columns.']},
            {'weekNum': 13,
             'topic': 'Sequences & Codes',
             'focus': 'Term 1 Review & Mixed Sequences Test',
             'objectives': ['Synthesize letter series, number sequences, and shift ciphers.',
                            'Complete a high-speed, 10-question mixed test under 8 minutes.',
                            'Eliminate common silly arithmetic errors.']}]},
 {'termId': 2,
  'termName': 'Term 2: Vocabulary, Synonyms & Antonyms',
  'focus': 'Expanding vocabulary bounds, identifying precise synonyms, opposites, category classifications, '
           'and odd-one-out groupings.',
  'weeks': [{'weekNum': 14,
             'topic': 'Closest in Meaning (Synonyms)',
             'focus': 'High-Tier Synonym Recognition',
             'objectives': ['Select the closest matches for academic adjectives (e.g., diligent, eloquent).',
                            'Identify words with identical meanings but distinct contextual registers.',
                            'Practice spelling and reading classic 11+ vocabulary lists.']},
            {'weekNum': 15,
             'topic': 'Closest in Meaning (Synonyms)',
             'focus': 'Contextual Shades of Meaning',
             'objectives': ['Match synonyms when words have multi-layered secondary definitions.',
                            'Isolate meaning groups in standard multiple-choice blocks.',
                            "Differentiate synonyms from mere associations (e.g., 'heat' is not a synonym of "
                            "'fire')."]},
            {'weekNum': 16,
             'topic': 'Opposites (Antonyms)',
             'focus': 'Basic Antonym Identification',
             'objectives': ['Identify the direct antonym from 5 candidate options.',
                            'Avoid the classic trap of choosing synonyms when opposites are requested.',
                            'Recognize prefixes that create opposites (un-, dis-, in-, im-).']},
            {'weekNum': 17,
             'topic': 'Opposites (Antonyms)',
             'focus': 'Advanced Antonyms & Shades of Contrast',
             'objectives': ['Resolve antonyms for abstract concepts and literary verbs.',
                            'Differentiate between partial opposites and exact antonyms.',
                            'Utilize process of elimination for difficult roots.']},
            {'weekNum': 18,
             'topic': 'Word Analogies (Related Pairs)',
             'focus': 'Synonym & Antonym Analogy Pairs',
             'objectives': ['Recognize pairs linked by synonymous or antonymous relationships (e.g., SLOW : '
                            'FAST as WET : DRY).',
                            'Ensure word-class matching (noun to noun, adjective to adjective).',
                            'Identify the correct relationship direction.']},
            {'weekNum': 19,
             'topic': 'Word Analogies (Related Pairs)',
             'focus': 'Functional & Object-to-Use Analogies',
             'objectives': ['Connect objects to their direct functions (e.g., PEN : WRITE as SCISSORS : '
                            'CUT).',
                            'Match categories, parts of a whole, and intensity levels.',
                            'Practice quick reasoning verbal phrasing.']},
            {'weekNum': 20,
             'topic': 'Odd One Out',
             'focus': 'Simple Category Classification',
             'objectives': ['Locate the word that does not belong to a clear logical category.',
                            'Define specific, narrow categories (e.g., identifying deciduous trees vs '
                            'conifers).',
                            'Practice with everyday objects and animals.']},
            {'weekNum': 21,
             'topic': 'Odd One Out',
             'focus': 'Semantic Grouping',
             'objectives': ['Group abstract nouns and literary vocabulary.',
                            'Separate words based on subtle positive/negative connotations.',
                            'Avoid choosing words merely because of physical spelling attributes.']},
            {'weekNum': 22,
             'topic': 'Double Definitions',
             'focus': 'Homonyms & Words with Multiple Meanings',
             'objectives': ['Identify a single word that completes two completely independent sentences.',
                            'Understand dual meaning words (e.g., BARK - tree covering and dog noise).',
                            'Enhance vocabulary flexibility across homonyms.']},
            {'weekNum': 23,
             'topic': 'Word Connections',
             'focus': 'Finding the Link',
             'objectives': ['Select a word that is logically related to two separate groups of words.',
                            'Deduce common categories among diverse nouns.',
                            'Develop lateral thinking vocabulary associations.']},
            {'weekNum': 24,
             'topic': 'Synonyms & Antonyms',
             'focus': 'Advanced Word Associations',
             'objectives': ['Solve complex synonym/antonym pair selections in GL-style grid panels.',
                            'Identify secondary meanings under strict time conditions.',
                            'Eradicate vocabulary gaps.']},
            {'weekNum': 25,
             'topic': 'Odd One Out',
             'focus': 'Abstract Classification Drills',
             'objectives': ['Classify complex vocabulary under high-speed constraints.',
                            'Identify traps where four words share multiple categories but one is excluded '
                            'from the narrowest.',
                            'Build absolute accuracy when choices feel similar.']},
            {'weekNum': 26,
             'topic': 'Vocabulary & Analogies',
             'focus': 'Term 2 Review & Mixed Vocab Test',
             'objectives': ['Synthesize synonyms, antonyms, related pairs, and odd-one-out categories.',
                            'Complete a mixed 10-question vocabulary examination.',
                            'Identify custom vocabulary weakness areas.']}]},
 {'termId': 3,
  'termName': 'Term 3: Word Building & Puzzles',
  'focus': 'Refining word synthesis, locating hidden words, compounding, letter insertion, and prefix/suffix '
           'structures.',
  'weeks': [{'weekNum': 27,
             'topic': 'Compound Words',
             'focus': 'Combining Word Fragments',
             'objectives': ['Form single cohesive compound words by joining smaller words.',
                            'Spot valid combinations in split column layouts.',
                            'Discard misleading false compounds.']},
            {'weekNum': 28,
             'topic': 'Compound Words',
             'focus': 'Compound Bridge Puzzles',
             'objectives': ['Find a single word that fits in the middle to make two separate compound words '
                            '(e.g., FOOT [BALL] ROOM).',
                            'Test candidates systematically with prefix and suffix words.',
                            'Recognize common compounding words (e.g., ball, house, man, land).']},
            {'weekNum': 29,
             'topic': 'Hidden Words',
             'focus': 'Finding Embedded Words',
             'objectives': ['Identify a hidden four-letter word spanning across two adjacent words.',
                            'Understand that punctuation and spacing are ignored in junction spans.',
                            'Scan strings systematically without losing position.']},
            {'weekNum': 30,
             'topic': 'Hidden Words',
             'focus': 'Multi-Word Junction Spans',
             'objectives': ['Locate hidden words across lengthy sentences.',
                            'Isolate start and end letters that bridge gaps.',
                            'Differentiate hidden words from mere phonetic similarities.']},
            {'weekNum': 31,
             'topic': 'Insert a Letter (Completes Both Words)',
             'focus': 'Vowel & Consonant Bridges',
             'objectives': ['Find the single letter that ends the first word and starts the second.',
                            'Test vowels first (A, E, I, O, U) as high-probability connectors.',
                            'Verify that both resulting words are correctly spelled.']},
            {'weekNum': 32,
             'topic': 'Insert a Letter (Completes Both Words)',
             'focus': 'Consonant Cluster Bridges',
             'objectives': ['Identify trickier consonant connectors (e.g., T, S, D, R, N, L).',
                            'Manage fragments that look like words but are incomplete.',
                            'Practice under rigorous time pacing.']},
            {'weekNum': 33,
             'topic': 'Move a Letter',
             'focus': 'Letter Migration',
             'objectives': ['Identify a letter that can be moved from the first word to the second to form '
                            'two brand-new words.',
                            'Ensure that the order of remaining letters in both words remains unchanged.',
                            'Build speed in scanning anagrammatic shifts.']},
            {'weekNum': 34,
             'topic': 'Word Fragments',
             'focus': 'Completing Gaps',
             'objectives': ['Fill missing letter groups to complete a sentence cohesively.',
                            'Apply prefix and suffix rules to reconstruct broken words.',
                            'Deconstruct multi-syllable academic nouns.']},
            {'weekNum': 35,
             'topic': 'Anagrams',
             'focus': 'Solving Reordered Words',
             'objectives': ['Unscramble letters to match a descriptive clue or synonym.',
                            'Recognize common consonant patterns (e.g., th, sh, ch, tr) to group letters.',
                            'Use count limits to eliminate wrong options instantly.']},
            {'weekNum': 36,
             'topic': 'Anagrams',
             'focus': 'Embedded Sentence Anagrams',
             'objectives': ['Locate and unscramble anagrams hidden within parentheses inside sentences.',
                            'Evaluate context to deduce the correct word class of the unscrambled word.',
                            'Apply root structures to assist unscrambling.']},
            {'weekNum': 37,
             'topic': 'Compound Words',
             'focus': 'Complex Compounding Review',
             'objectives': ['Synthesize dual word builders and bridge puzzles.',
                            'Ensure that no stray spelling changes occur during compound generation.',
                            'Review rare compounding exceptions.']},
            {'weekNum': 38,
             'topic': 'Hidden & Inserted Words',
             'focus': 'Junction Mastery Drills',
             'objectives': ['Practice combining hidden word scans and letter insertions under 40 seconds per '
                            'question.',
                            'Refine physical scanning tricks (e.g., hiding distractions with index fingers).',
                            'Avoid spelling traps.']},
            {'weekNum': 39,
             'topic': 'Word Building & Puzzles',
             'focus': 'Term 3 Review & Mixed Word Puzzles Test',
             'objectives': ['Synthesize compound words, hidden words, letter insertions, and anagrams.',
                            'Complete a mixed 10-question word puzzle paper.',
                            'Eradicate mechanical scanning delays.']}]},
 {'termId': 4,
  'termName': 'Term 4: Exam Strategy, Mixed Drills & Advanced Logic',
  'focus': 'Integrating all Verbal Reasoning topics to excel under exam conditions, mastering MCQ '
           'elimination, and maximizing pace and accuracy.',
  'weeks': [{'weekNum': 40,
             'topic': 'Exam Technique',
             'focus': 'Multiple-Choice Elimination (MCQ)',
             'objectives': ['Master the elimination strategy for 5-option Verbal Reasoning questions.',
                            'Identify and discard common distractor traps (near-spellings, false codes, '
                            'reverse shifts).',
                            'Build absolute accuracy when choices feel highly similar.']},
            {'weekNum': 41,
             'topic': 'Exam Technique',
             'focus': 'Time Management & Pacing',
             'objectives': ['Pace yourself during a standard 50-minute Verbal Reasoning paper.',
                            'Learn when to skip a difficult code or number series and return to it later.',
                            'Double-check arithmetic and letters systematically in final minutes.']},
            {'weekNum': 42,
             'topic': 'Logical Puzzles',
             'focus': 'Advanced Logic Matrices',
             'objectives': ['Solve complex grid grids where 3 or 4 variables must be mapped.',
                            'Isolate clues that yield direct facts first.',
                            'Translate multi-step statements into rapid diagram symbols.']},
            {'weekNum': 43,
             'topic': 'Letter Codes',
             'focus': 'Advanced Multi-Step Ciphers',
             'objectives': ['Decipher codes involving spelling reversals and index offsets.',
                            'Decode codes with different rules for vowels and consonants.',
                            'Handle composite letter-symbol codes.']},
            {'weekNum': 44,
             'topic': 'Number Series',
             'focus': 'Two-Step Differences & Squares',
             'objectives': ['Identify series where differences themselves have a pattern (second-order '
                            'differences).',
                            'Recognize series based on mathematical squares, cubes, and prime numbers.',
                            'Solve mixed fraction/decimal progressions.']},
            {'weekNum': 45,
             'topic': 'Word Connections',
             'focus': 'Triple Connections & Triangles',
             'objectives': ['Select words that bridge three independent sets of synonyms.',
                            'Solve triangle word connections where vertices have mathematical/logical '
                            'relationships.',
                            'Expand lateral vocabulary mapping.']},
            {'weekNum': 46,
             'topic': 'Algebraic Puzzles',
             'focus': 'Nested Symbol Equations',
             'objectives': ['Solve scales with nested equations where one symbol is composed of others.',
                            'Deduce negative and fractional symbol weights.',
                            'Speed up algebraic deduction through mental estimation.']},
            {'weekNum': 47,
             'topic': 'Mixed Verbal Reasoning Drill',
             'focus': 'High-Speed Drills - Set A',
             'objectives': ['Solve 10 mixed questions (Series, Codes, Vocab, Word Building) in under 8 '
                            'minutes.',
                            'Pace each item to take no longer than 45 seconds.',
                            'Identify and record personal speed-bump topics.']},
            {'weekNum': 48,
             'topic': 'Mixed Verbal Reasoning Drill',
             'focus': 'High-Speed Drills - Set B',
             'objectives': ['Solve 10 highly difficult, top-school level questions in 8 minutes.',
                            'Maintain structural focus when faced with unfamiliar puzzle formats.',
                            'Practice rapid physical indexing on paper.']},
            {'weekNum': 49,
             'topic': 'Mixed Verbal Reasoning Drill',
             'focus': 'Accuracy & Self-Correction Drills',
             'objectives': ['Solve a standard GL-style paper with deliberate traps included.',
                            'Implement self-correction checklists (e.g., checking possessive apostrophes or '
                            'reverse signs).',
                            'Eliminate silly transcription errors.']},
            {'weekNum': 50,
             'topic': 'Mixed Verbal Reasoning Drill',
             'focus': 'Mock Examination - Paper 1',
             'objectives': ['Complete a comprehensive, 20-question randomized mock Verbal Reasoning paper.',
                            'Simulate full exam noise and time constraints.',
                            'Analyze timing charts to identify bottlenecks.']},
            {'weekNum': 51,
             'topic': 'Mixed Verbal Reasoning Drill',
             'focus': 'Mock Examination - Paper 2',
             'objectives': ['Complete a second 20-question mock paper targeting super-selective grammar '
                            'schools.',
                            'Review comprehensive worked explanations for all 20 questions.',
                            'Polishing final strategy elements.']},
            {'weekNum': 52,
             'topic': 'Logical Puzzles',
             'focus': 'Ultimate Exam Strategy & Checklist',
             'objectives': ["Review Coach Pip's final checklist of selective school Verbal Reasoning traps.",
                            'Establish low-stress confidence-building warmups.',
                            'Visualize flawless performance and calm execution.']}]}]
TOPIC_ALIASES = {'Number Codes': 'Letter Codes',
 'Logical Puzzles': 'Odd One Out',
 'Algebraic Puzzles': 'Number Series',
 'Sequences & Codes': 'Letter Series',
 'Double Definitions': 'Closest in Meaning (Synonyms)',
 'Word Connections': 'Word Analogies (Related Pairs)',
 'Synonyms & Antonyms': 'Closest in Meaning (Synonyms)',
 'Vocabulary & Analogies': 'Word Analogies (Related Pairs)',
 'Move a Letter': 'Insert a Letter (Completes Both Words)',
 'Word Fragments': 'Hidden Words',
 'Anagrams': 'Hidden Words',
 'Hidden & Inserted Words': 'Hidden Words',
 'Word Building & Puzzles': 'Compound Words'}
MIXED_CURRICULUM_TOPICS = set(['Exam Technique', 'Mixed Verbal Reasoning Drill'])
SUBJECT = 'Verbal Reasoning'
RAG_SUBJECT = 'VerbalReasoning-1year'
OUTPUT_JSON = '11_Plus_VR_52_Week_Plan.json'
OUTPUT_MARKDOWN = '11_Plus_VR_52_Week_Plan.md'
DOC_ID_PREFIX = 'elevenplus_vr_year_round_week_'


def _find_week(week_num: int) -> tuple[Dict[str, Any], Dict[str, Any]]:
    for term in CURRICULUM:
        for week in term["weeks"]:
            if int(week["weekNum"]) == int(week_num):
                return term, week
    raise ValueError(f"Unknown week number: {week_num}")


def _available_topics() -> List[str]:
    return [str(item[0]) for item in ELEVEN_PLUS_VR_TOPICS]


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
        _, generated = generate_11plus_vr_homework(
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
        _, records = generate_11plus_vr_homework(
            generator_topic,
            int(week_num),
            difficulty=difficulty,
        )
        for record in records:
            record["curriculum_topic"] = curriculum_topic
            record["focus"] = str(week.get("focus") or "")
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
    if generate_11plus_vr_homework is None:
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
