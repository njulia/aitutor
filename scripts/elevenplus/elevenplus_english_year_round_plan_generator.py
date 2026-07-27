#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Efficient 52-week English plan built from the canonical practice generator.

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
    from scripts.elevenplus.elevenplus_english_generator import generate_11plus_english_homework, ELEVEN_PLUS_ENGLISH_TOPICS
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    generate_11plus_english_homework = None
    ELEVEN_PLUS_ENGLISH_TOPICS = []
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
  'termName': 'Term 1: Spelling, Word Patterns & Phonics Mastery',
  'focus': 'Mastering core spelling rules, prefixes, suffixes, homophones, and double-consonant '
           'combinations.',
  'weeks': [{'weekNum': 1,
             'topic': 'Spelling',
             'focus': 'Vowel Patterns and Double Letters',
             'objectives': ["Identify and spell words with complex vowel digraphs (e.g., 'ae', 'oe', 'ie' vs "
                            "'ei').",
                            'Master common double-letter traps in nouns and adjectives.',
                            'Recognize visual patterns of correctly spelled words.']},
            {'weekNum': 2,
             'topic': 'Spelling',
             'focus': 'Plural Rules and Exceptions',
             'objectives': ['Understand rules for adding -s, -es, -ies, and -ves to singular nouns.',
                            'Learn irregular plural forms (e.g., criteria, phenomena, larvae).',
                            'Apply correct spelling to plural possessives.']},
            {'weekNum': 3,
             'topic': 'Spelling',
             'focus': 'Prefixes and Root Words',
             'objectives': ['Understand how common prefixes (un-, dis-, mis-, re-, pre-) modify root '
                            'meanings.',
                            'Avoid spelling mistakes when prefixes meet matching letters (e.g., dis- + '
                            'satisfy = dissatisfy).',
                            'Identify Greek and Latin root origins.']},
            {'weekNum': 4,
             'topic': 'Spelling',
             'focus': 'Suffixes and Word Endings',
             'objectives': ["Learn when to drop 'e', double the consonant, or change 'y' to 'i' before "
                            'adding suffixes.',
                            'Differentiate between -able and -ible endings.',
                            'Identify the grammatical role of suffix endings (-ly, -ment, -ness).']},
            {'weekNum': 5,
             'topic': 'Spelling',
             'focus': 'Silent Letters and Homophones',
             'objectives': ['Locate silent letters in standard vocabulary (e.g., knife, doubt, autumn, '
                            'subtle).',
                            "Differentiate between homophones (their/there/they're, practice/practise, "
                            'advice/advise).',
                            'Use context clues to select the correct homophone spelling.']},
            {'weekNum': 6,
             'topic': 'Spelling',
             'focus': 'High-Frequency Spelling List (Part 1)',
             'objectives': ['Memorize spelling for first 15 words of the 11+ High-Frequency curriculum.',
                            'Break down words into syllables for easier recall (e.g., ac-com-mo-date).',
                            'Practice daily quick spelling drills.']},
            {'weekNum': 7,
             'topic': 'Spelling',
             'focus': 'High-Frequency Spelling List (Part 2)',
             'objectives': ['Memorize spelling for second 15 words of the 11+ High-Frequency curriculum.',
                            "Utilize visual mnemonics for tricky syllables (e.g., 'a rat' in 'separate').",
                            'Test spelling accuracy under a 30-second time constraint.']},
            {'weekNum': 8,
             'topic': 'Spelling',
             'focus': 'Words from Other Languages (Loan Words)',
             'objectives': ['Recognize and spell common French, Latin, and German loan words (e.g., bouquet, '
                            'entrepreneur, curriculum).',
                            'Understand phonetic differences in borrowed vocabulary.',
                            'Master spelling patterns for foreign suffixes.']},
            {'weekNum': 9,
             'topic': 'Spelling',
             'focus': 'Compound Words and Hyphenation',
             'objectives': ['Identify when to write compound words as one word, two words, or with a hyphen.',
                            'Learn rules for hyphenating compound adjectives (e.g., well-known author).',
                            'Master spelling for composite nouns.']},
            {'weekNum': 10,
             'topic': 'Spelling',
             'focus': 'Difficult Double Consonant Pairings',
             'objectives': ['Practice spelling words with multiple double consonants (e.g., embarrassment, '
                            'questionnaire).',
                            'Analyze consonant structures under syllables.',
                            "Recognize patterns of double 'r', 's', 'l', and 'n'."]},
            {'weekNum': 11,
             'topic': 'Spelling',
             'focus': 'Confusion Words (e.g., Affect vs. Effect)',
             'objectives': ['Learn the distinct meanings and grammatical roles of easily confused pairs '
                            '(affect/effect, stationary/stationery).',
                            'Apply vocabulary guidelines to complete sentence gaps.',
                            'Establish rules of thumb for daily differentiation.']},
            {'weekNum': 12,
             'topic': 'Spelling',
             'focus': 'Spelling Under Time Pressure',
             'objectives': ['Complete rapid-fire spelling multiple-choice worksheets.',
                            'Identify spelling errors in lengthy paragraphs of text.',
                            'Review common traps in selective grammar school papers.']},
            {'weekNum': 13,
             'topic': 'Spelling',
             'focus': 'Term 1 Spelling Mastery Review & Test',
             'objectives': ['Synthesize Term 1 spelling rules, plurals, prefixes, and silent letters.',
                            'Complete a mixed 10-question GL-style spelling test.',
                            'Eradicate repeat mistakes on active spelling sheets.']}]},
 {'termId': 2,
  'termName': 'Term 2: Grammar Foundations & Sentence Structure',
  'focus': 'Developing grammatical accuracy, mastering parts of speech, clause properties, and tenses.',
  'weeks': [{'weekNum': 14,
             'topic': 'Grammar',
             'focus': 'Parts of Speech: Nouns & Pronouns',
             'objectives': ['Differentiate between proper, common, concrete, abstract, and collective nouns.',
                            'Master personal, possessive, relative, reflexive, and demonstrative pronouns.',
                            'Avoid pronoun-noun agreement errors.']},
            {'weekNum': 15,
             'topic': 'Grammar',
             'focus': 'Parts of Speech: Verbs & Tenses',
             'objectives': ['Identify action, linking, and helping (auxiliary) verbs.',
                            'Conjugate verbs across simple past/present/future and perfect tenses.',
                            'Master irregular verb forms (e.g., lie vs lay, rise vs raise).']},
            {'weekNum': 16,
             'topic': 'Grammar',
             'focus': 'Parts of Speech: Adjectives & Adverbs',
             'objectives': ['Use adjectives to modify nouns and adverbs to modify verbs, adjectives, or '
                            'other adverbs.',
                            'Understand comparative and superlative forms.',
                            'Avoid confusing adjectives with adverbs (e.g., good vs well).']},
            {'weekNum': 17,
             'topic': 'Grammar',
             'focus': 'Parts of Speech: Prepositions & Conjunctions',
             'objectives': ['Identify prepositions of time, place, and direction.',
                            'Use coordinating (FANBOYS) and subordinating conjunctions to connect clauses.',
                            'Differentiate between prepositions and conjunctions.']},
            {'weekNum': 18,
             'topic': 'Grammar',
             'focus': 'Subject-Verb Agreement (Singular vs. Plural)',
             'objectives': ['Match singular subjects with singular verbs and plural subjects with plural '
                            'verbs.',
                            "Resolve agreement with compound subjects joined by 'and', 'or', or 'nor'.",
                            'Handle collective nouns and parenthetical insertions.']},
            {'weekNum': 19,
             'topic': 'Grammar',
             'focus': 'Pronoun Agreement & Ambiguity',
             'objectives': ['Ensure pronouns agree in number and gender with their antecedents.',
                            'Identify and correct vague or ambiguous pronoun references.',
                            'Master subject vs object pronouns (e.g., he/him, who/whom).']},
            {'weekNum': 20,
             'topic': 'Grammar',
             'focus': 'Sentence Types (Simple, Compound, Complex)',
             'objectives': ['Recognize simple sentences containing a single independent clause.',
                            'Form compound sentences using coordinating conjunctions or semicolons.',
                            'Analyze complex sentences containing independent and subordinate clauses.']},
            {'weekNum': 21,
             'topic': 'Grammar',
             'focus': 'Clauses and Phrases (Relative & Subordinate)',
             'objectives': ['Distinguish clearly between clauses (containing a subject-verb pair) and '
                            'phrases.',
                            'Identify relative clauses starting with relative pronouns (who, which, that).',
                            'Deconstruct complex sentence syntax.']},
            {'weekNum': 22,
             'topic': 'Grammar',
             'focus': 'Active vs. Passive Voice',
             'objectives': ['Identify whether a sentence is in active voice (subject performs action) or '
                            'passive voice.',
                            'Convert sentences from active to passive and vice versa.',
                            'Understand the stylistic purpose of each voice in academic writing.']},
            {'weekNum': 23,
             'topic': 'Grammar',
             'focus': 'Direct vs. Indirect Speech',
             'objectives': ['Identify direct quote speech and indirect reported speech.',
                            'Convert speech styles, noting changes in verb tenses and pronouns.',
                            'Master punctuation associated with dialogue.']},
            {'weekNum': 24,
             'topic': 'Grammar',
             'focus': 'Common Grammatical Traps & Double Negatives',
             'objectives': ['Spot and eliminate double negatives in sentence structures.',
                            'Correct dangling or misplaced modifiers.',
                            'Master correct comparative structures (e.g., more faster -> faster).']},
            {'weekNum': 25,
             'topic': 'Grammar',
             'focus': 'Sentence Combining and Cohesion',
             'objectives': ['Combine multiple short sentences into a cohesive compound-complex sentence.',
                            'Utilize transition words to establish flow and contrast.',
                            'Master logical sequence structures.']},
            {'weekNum': 26,
             'topic': 'Grammar',
             'focus': 'Term 2 Grammar Mastery Review & Test',
             'objectives': ['Synthesize nouns, verbs, tenses, subject-verb agreement, and clause types.',
                            'Complete a mixed 10-question grammar paper.',
                            'Analyze syntactic errors under exam time constraints.']}]},
 {'termId': 3,
  'termName': 'Term 3: Capitalisation, Punctuation & Cloze Mastery',
  'focus': 'Refining punctuation mechanics, complex mark usage, and contextual vocabulary selection.',
  'weeks': [{'weekNum': 27,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Capital Letters & Proper Nouns',
             'objectives': ['Capitalise sentences, direct speech, proper nouns, titles, and abbreviations.',
                            'Avoid unnecessary capitalisation of common terms.',
                            'Correct capitalization in complex headings.']},
            {'weekNum': 28,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Full Stops, Question Marks & Exclamation Marks',
             'objectives': ['Apply terminal punctuation appropriately based on sentence intent.',
                            'Avoid run-on sentences by separating complete thoughts.',
                            'Master correct punctuation after abbreviations.']},
            {'weekNum': 29,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Commas in Lists and Clauses',
             'objectives': ['Use commas to separate items in lists (including the serial/Oxford comma).',
                            'Isolate introductory clauses, parenthetical remarks, and appositives.',
                            'Avoid comma splices when joining independent clauses.']},
            {'weekNum': 30,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Apostrophes for Contraction & Possession',
             'objectives': ["Apply apostrophes of contraction (e.g., can't, wouldn't, it's).",
                            "Master singular and plural possessive rules (e.g., cat's milk vs cats' milk).",
                            'Differentiate possessive pronouns (its, whose) from contractions.']},
            {'weekNum': 31,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Speech Marks and Dialogue Punctuation',
             'objectives': ['Enclose direct spoken words inside double speech marks.',
                            'Place punctuation marks (commas, full stops, question marks) inside speech '
                            'marks.',
                            'Start a new line for a new speaker.']},
            {'weekNum': 32,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Colons and Semicolons',
             'objectives': ['Use colons to introduce lists, explanations, or direct quotes.',
                            'Apply semicolons to join closely related independent clauses without '
                            'conjunctions.',
                            'Organize complex, comma-heavy lists using semicolons.']},
            {'weekNum': 33,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Parenthesis: Brackets, Dashes & Commas',
             'objectives': ['Enclose extra, non-essential information inside brackets or parenthetical '
                            'dashes.',
                            'Understand how brackets, dashes, and commas create different stylistic '
                            'emphasis.',
                            'Maintain grammatical flow when parenthetical parts are removed.']},
            {'weekNum': 34,
             'topic': 'Vocabulary: Word Choice (Cloze)',
             'focus': 'Cloze: Nouns and Verbs in Context',
             'objectives': ['Analyze surrounding words to determine the correct noun or verb category.',
                            'Understand lexical collocations (words that frequently go together).',
                            'Identify and discard contextually invalid options.']},
            {'weekNum': 35,
             'topic': 'Vocabulary: Word Choice (Cloze)',
             'focus': 'Cloze: Adjectives and Adverbs in Context',
             'objectives': ['Evaluate descriptive passages to select the most appropriate tone modifiers.',
                            'Recognize shades of meaning and positive vs negative contexts.',
                            'Master high-tier descriptive adjectives.']},
            {'weekNum': 36,
             'topic': 'Vocabulary: Word Choice (Cloze)',
             'focus': 'Cloze: Prepositions and Transition Words',
             'objectives': ['Fill sentence gaps with prepositions and transitional adverbs (therefore, '
                            'however, although).',
                            'Identify causal, contrast, and sequential relationships.',
                            'Master sentence cohesive devices.']},
            {'weekNum': 37,
             'topic': 'Vocabulary: Synonyms and Antonyms',
             'focus': 'Synonyms and Antonyms in Sentences',
             'objectives': ['Identify synonyms and antonyms for underlined words in written sentences.',
                            'Evaluate vocabulary choices based on contextual nuance.',
                            'Utilize process of elimination to discard unrelated choices.']},
            {'weekNum': 38,
             'topic': 'Vocabulary: Synonyms and Antonyms',
             'focus': 'Context Clues and Tone Matching',
             'objectives': ['Deduce meanings of unfamiliar vocabulary using surrounding context clues.',
                            'Match vocabulary tones (academic, informal, archaic) to the text.',
                            'Master general 11+ vocabulary lists.']},
            {'weekNum': 39,
             'topic': 'Capital Letters and Punctuation',
             'focus': 'Term 3 Punctuation & Cloze Mastery Review & Test',
             'objectives': ['Synthesize colons, semicolons, brackets, speech punctuation, and word cloze.',
                            'Complete a mixed punctuation and vocabulary-cloze test.',
                            'Analyze pacing: complete each item in under 40 seconds.']}]},
 {'termId': 4,
  'termName': 'Term 4: Literary Comprehension, Inference & Exam Success',
  'focus': 'Synthesizing all modules to excel in reading comprehension, inference, and exam time management.',
  'weeks': [{'weekNum': 40,
             'topic': 'Reading Comprehension',
             'focus': 'Reading Comprehension: Literal Fact Retrieval',
             'objectives': ['Locate specific facts directly stated in the text.',
                            'Learn to scan for key terms, dates, and names.',
                            'Avoid overthinking by sticking strictly to what is written.']},
            {'weekNum': 41,
             'topic': 'Reading Comprehension',
             'focus': 'Reading Comprehension: Locating Evidence',
             'objectives': ['Identify the line numbers or paragraph details that prove an answer.',
                            'Understand how to cross-reference multiple parts of a text.',
                            'Track narrative sequence steps.']},
            {'weekNum': 42,
             'topic': 'Reading Comprehension',
             'focus': 'Reading Comprehension: Word Meaning in Context',
             'objectives': ['Deduce what a word means based on how it is used in a specific sentence.',
                            'Identify synonyms for literary terms inside comprehension texts.',
                            'Differentiate between literal and figurative language (metaphor, simile).']},
            {'weekNum': 43,
             'topic': 'Reading Comprehension',
             'focus': 'Reading Comprehension: Simple Inference',
             'objectives': ['Read between the lines to deduce facts not explicitly stated.',
                            'Identify character motivations and implied actions.',
                            'Draw logical conclusions backed by subtle textual clues.']},
            {'weekNum': 44,
             'topic': 'Reading Comprehension',
             'focus': 'Reading Comprehension: Character Feelings and Motives',
             'objectives': ["Interpret a character's emotional state from their dialogue, actions, and body "
                            'language.',
                            'Trace emotional changes throughout a story path.',
                            "Contrast different characters' reactions."]},
            {'weekNum': 45,
             'topic': 'Reading Comprehension',
             'focus': "Reading Comprehension: Author's Tone and Intention",
             'objectives': ["Identify the author's purpose (to persuade, inform, entertain, describe).",
                            'Deconstruct the tone of a passage (humorous, suspenseful, nostalgic).',
                            'Analyze word choices that evoke specific feelings.']},
            {'weekNum': 46,
             'topic': 'Reading Comprehension',
             'focus': 'Reading Comprehension: Text Layout & Formatting Clues',
             'objectives': ['Interpret non-fiction features (subheadings, bullet points, captions).',
                            'Understand the purpose of italics, bolding, and quotation marks.',
                            'Deconstruct informational texts.']},
            {'weekNum': 47,
             'topic': 'Reading Comprehension',
             'focus': 'Exam Technique: Multiple-Choice Elimination (MCQ)',
             'objectives': ['Master the elimination strategy for 5-option English questions.',
                            'Identify and discard common distractor traps (half-truths, extreme statements).',
                            'Build absolute accuracy when choices feel similar.']},
            {'weekNum': 48,
             'topic': 'Reading Comprehension',
             'focus': 'Exam Technique: Skimming and Scanning',
             'objectives': ["Practice high-speed skimming to get the 'gist' of a long passage in under 2 "
                            'minutes.',
                            'Scan targeted areas of text to locate specific information under strict timing.',
                            'Minimize eye regression and stay focused.']},
            {'weekNum': 49,
             'topic': 'Reading Comprehension',
             'focus': 'Exam Technique: Time Management',
             'objectives': ['Pace yourself during a standard 45-minute English paper.',
                            'Learn when to skip a difficult question and come back to it.',
                            'Double-check answers systematically in final minutes.']},
            {'weekNum': 50,
             'topic': 'Reading Comprehension',
             'focus': 'Mixed English Drill - Speed and Accuracy',
             'objectives': ['Solve 10 mixed questions (Spelling, Grammar, Punctuation, Comprehension) under '
                            '8-minute time pressure.',
                            'Maintain composure and logic under stress.',
                            'Review step-by-step solutions instantly.']},
            {'weekNum': 51,
             'topic': 'Reading Comprehension',
             'focus': 'Final Full-Syllabus English Mock Exam',
             'objectives': ['Complete a comprehensive, 20-question randomized mock English paper.',
                            'Review comprehensive explanations for all sections.',
                            'Identify final polish areas for selective school entrance.']},
            {'weekNum': 52,
             'topic': 'Reading Comprehension',
             'focus': 'Ultimate Strategy, Anxiety Management & Prep',
             'objectives': ["Review elite exam guidelines and Coach Pip's checklist for selective schools.",
                            'Establish a low-stress, confidence-building final warm-up routine.',
                            'Visualize exam success with clarity and positive focus.']}]}]
TOPIC_ALIASES = {}
MIXED_CURRICULUM_TOPICS = set([])
SUBJECT = 'English'
RAG_SUBJECT = 'English-1year'
OUTPUT_JSON = '11_Plus_English_52_Week_Plan.json'
OUTPUT_MARKDOWN = '11_Plus_English_52_Week_Plan.md'
DOC_ID_PREFIX = 'elevenplus_english_year_round_week_'


def _find_week(week_num: int) -> tuple[Dict[str, Any], Dict[str, Any]]:
    for term in CURRICULUM:
        for week in term["weeks"]:
            if int(week["weekNum"]) == int(week_num):
                return term, week
    raise ValueError(f"Unknown week number: {week_num}")


def _available_topics() -> List[str]:
    return [str(item[0]) for item in ELEVEN_PLUS_ENGLISH_TOPICS]


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
        _, generated = generate_11plus_english_homework(
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
        _, records = generate_11plus_english_homework(
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
    if generate_11plus_english_homework is None:
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
