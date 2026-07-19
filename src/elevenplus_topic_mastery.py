"""Shared, answer-free catalogue for the 11+ topic-mastery browser page."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import canonical_topic_mastery_subject, subject_display_name


MASTERY_LEVELS = [
    {"level": 1, "name": "Foundational Basics", "difficulty": "Foundational"},
    {"level": 2, "name": "Intermediate Application", "difficulty": "Standard"},
    {"level": 3, "name": "Advanced Practice", "difficulty": "Advanced"},
    {"level": 4, "name": "Selective School Challenge", "difficulty": "Selective / Hard"},
    {"level": 5, "name": "Ultimate Mastery & Mixed Drill", "difficulty": "Mastery"},
]

TOPIC_MASTERY_TOPICS: Dict[str, List[str]] = {
    "Maths-topic-mastery": [
        "Number: Arithmetic & Mental Maths",
        "Number: Fractions, Decimals & Percentages",
        "Number: Primes, Factors & Multiples",
        "Non-Routine Reasoning (Top-School Style)",
        "Ratio and Proportion",
        "Algebra Basics",
        "Shape, Space and Measures",
        "Data Handling and Graphs",
        "Worded Problem Solving",
        "Speed, Distance and Time",
        "Sequences and Patterns",
    ],
    "English-topic-mastery": [
        "Spelling: Vowels & Double Letters",
        "Spelling: Prefixes, Suffixes & Silent Letters",
        "Punctuation: Capital Letters & Full Stops",
        "Punctuation: Apostrophes, Commas & Speech",
        "Vocabulary: Contextual Word Choice (Cloze)",
        "Vocabulary: Synonyms & Definitions",
        "Vocabulary: Antonyms & Word Opposites",
        "Grammar: Subject-Verb Agreement & Tenses",
        "Grammar: Pronouns, Prepositions & Conjunctions",
        "Comprehension: Fact Retrieval & Location",
        "Comprehension: Inference, Meaning & Tone",
    ],
    "VerbalReasoning-topic-mastery": [
        "Letter Series: Simple & Alternating Steps",
        "Number Series: Arithmetic & Geometric",
        "Word Analogies: Opposite & Category Pairs",
        "Closest in Meaning: Synonym Matching",
        "Opposites: Antonym Identification",
        "Compound Words: Dual Bridge Building",
        "Hidden Words: Substring Junctions",
        "Letter Codes: Alphabetical Ciphers",
        "Odd One Out: Category Classification",
        "Insert a Letter: Double Word Completion",
        "Logical Sequences & Alternating Codes",
    ],
    "NonVerbalReasoning-topic-mastery": [
        "Shape Sequences & Progressions",
        "Rotation & Angular Alignment",
        "Odd One Out & Shape Discrepancy",
        "Shape Analogies & Attribute Changes",
        "Matrix Completion & Grid Logic",
        "Shape Codes & Attribute Translation",
        "Similarity Grouping & Group Association",
        "Shape Counting & Combinatorial Totals",
        "Reflection & Mirror Lines",
        "Layering & Overlapping Shapes",
        "3D Spatial Nets & Isometric Reasoning",
    ],
}


def mastery_set_index(topic_index: int, mastery_level: int) -> int:
    """Return the generator's 1-based global set number for a topic/level."""
    topic = int(topic_index)
    level = int(mastery_level)
    if not 1 <= topic <= 11 or not 1 <= level <= 5:
        raise ValueError("Topic must be 1-11 and mastery level must be 1-5")
    return (topic - 1) * 5 + level


def topic_mastery_catalogue() -> Dict[str, Any]:
    """Return public page data without touching the database or an LLM."""
    subjects = []
    for key, topics in TOPIC_MASTERY_TOPICS.items():
        subjects.append({"key": key, "label": subject_display_name(key), "topics": list(topics)})
    return {"subjects": subjects, "levels": list(MASTERY_LEVELS)}


def normalise_topic_mastery_subject(subject: str) -> str:
    key = canonical_topic_mastery_subject(subject)
    return key if key in TOPIC_MASTERY_TOPICS else ""

