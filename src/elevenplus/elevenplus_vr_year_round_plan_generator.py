#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ Verbal Reasoning 52-Week Year-Round Plan Generator
======================================================

Generates a comprehensive 52-Week Year-Round Verbal Reasoning study roadmap formulated for
Henrietta Barnett, Tiffin, CSSE, and St Olave's entrance papers.

Saves the generated plan to:
  - 11_Plus_VR_52_Week_Plan.json
  - 11_Plus_VR_52_Week_Plan.md

Also registers them in the RAG vector store for student queries.
"""

import sys
import os
import json
import math
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    get_elevenplus_rag_store = None

# ---------------------------------------------------------------------------
# Core Banks & Helpers
# ---------------------------------------------------------------------------
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

SYNONYMS_FALLBACK = [
    {"word": "happy", "syn": "cheerful", "ant": "sad", "clue": "feeling or showing pleasure or contentment"},
    {"word": "quick", "syn": "fast", "ant": "slow", "clue": "moving or capable of moving at high speed"},
    {"word": "large", "syn": "big", "ant": "small", "clue": "of considerable or relatively great size"},
    {"word": "brave", "syn": "courageous", "ant": "cowardly", "clue": "ready to face and endure danger or pain"},
    {"word": "quiet", "syn": "silent", "ant": "noisy", "clue": "making little or no noise"},
    {"word": "bright", "syn": "vivid", "ant": "dull", "clue": "shining strongly or having striking color"},
    {"word": "ancient", "syn": "old", "ant": "modern", "clue": "belonging to the very distant past"},
    {"word": "generous", "syn": "giving", "ant": "selfish", "clue": "willing to give money, help, or time freely"},
    {"word": "difficult", "syn": "hard", "ant": "easy", "clue": "needing much effort or skill to accomplish"},
    {"word": "polite", "syn": "courteous", "ant": "rude", "clue": "having or showing respectful behavior"},
    {"word": "wealthy", "syn": "rich", "ant": "poor", "clue": "having a great deal of money or assets"},
    {"word": "honest", "syn": "truthful", "ant": "dishonest", "clue": "free of deceit; sincere"},
]

ANALOGY_FALLBACK = {
    "opposite": [("hot", "cold"), ("up", "down"), ("day", "night"), ("happy", "sad")],
    "category": [("rose", "flower"), ("oak", "tree"), ("hammer", "tool"), ("salmon", "fish")],
    "baby": [("puppy", "dog"), ("kitten", "cat"), ("cub", "lion"), ("lamb", "sheep")],
}

ODD_FALLBACK = {
    "fruit": ["apple", "banana", "orange", "grape", "potato"],
    "animal": ["tiger", "elephant", "zebra", "giraffe", "violin"],
    "furniture": ["table", "chair", "sofa", "desk", "weather"],
}

HIDDEN_FALLBACK = [
    ("scar", "pet", "carpet"),
    ("grown", "erratic", "owner"),
    ("guitar", "enable", "arena"),
    ("drag", "online", "dragon"),
]

INSERT_FALLBACK = [
    ("PAR", "K", "IND"),
    ("CAR", "T", "OP"),
    ("BE", "D", "OG"),
    ("CA", "T", "EN"),
]

COMPOUND_FALLBACK = [
    ("FOOT", "BALL", "ROOM"),
    ("SUN", "FLOWER", "POT"),
    ("BED", "ROOM", "MATE"),
    ("RAIN", "BOW", "TIE"),
]

# Define the 52-Week Verbal Reasoning Curriculum
CURRICULUM = [
  {
    "termId": 1,
    "termName": "Term 1: Sequences, Numbers & Deciphering Codes",
    "focus": "Mastering alphabetical progressions, mathematical patterns, visual series, and complex symbol code translation.",
    "weeks": [
      {
        "weekNum": 1,
        "topic": "Letter Series",
        "focus": "Single Letter Progressions",
        "objectives": [
          "Understand how to use the standard 26-letter alphabet sequence.",
          "Identify and compute simple positive forward leaps (e.g., +1, +2, +3).",
          "Apply reverse/negative leaps (e.g., -1, -2, -3) across boundary letters (Z back to A)."
        ]
      },
      {
        "weekNum": 2,
        "topic": "Letter Series",
        "focus": "Alternating Letter Series",
        "objectives": [
          "Solve progressions where odd-indexed and even-indexed positions have distinct rules.",
          "Identify secondary overlay sequences in compound sequences.",
          "Practice skipping letters accurately on scratch paper."
        ]
      },
      {
        "weekNum": 3,
        "topic": "Number Series",
        "focus": "Basic Arithmetic Sequences",
        "objectives": [
          "Deduce constant differences between consecutive numbers (+x, -x).",
          "Recognize simple increasing/decreasing difference patterns.",
          "Perform quick calculations under 30-second limitations."
        ]
      },
      {
        "weekNum": 4,
        "topic": "Number Series",
        "focus": "Alternating Number Progressions",
        "objectives": [
          "Separate dual interleaved series within a single sequence.",
          "Determine parallel mathematical operations (+ and - working in pairs).",
          "Establish systematic checking to avoid calculation slips."
        ]
      },
      {
        "weekNum": 5,
        "topic": "Number Series",
        "focus": "Geometric & Fibonacci-like Sequences",
        "objectives": [
          "Identify multiplication and division patterns between terms.",
          "Solve series where the next term is the sum of previous terms.",
          "Master perfect squares and cubes under 150."
        ]
      },
      {
        "weekNum": 6,
        "topic": "Letter Codes",
        "focus": "Direct Shift Ciphers",
        "objectives": [
          "Decipher words where each letter is replaced by a fixed alphabetical offset (e.g. A->B, B->C).",
          "Isolate code translations letter-by-letter.",
          "Utilize multiple-choice options to rule out incorrect letters early."
        ]
      },
      {
        "weekNum": 7,
        "topic": "Letter Codes",
        "focus": "Variable Shift Ciphers",
        "objectives": [
          "Decode ciphers where the shift increases with position (e.g., +1, +2, +3).",
          "Decipher alternating pattern shifts (+1, -1, +1).",
          "Improve speed by encoding the last letter of a target word first."
        ]
      },
      {
        "weekNum": 8,
        "topic": "Number Codes",
        "focus": "Letter-to-Number Transposition",
        "objectives": [
          "Evaluate codes where letters are replaced by their alphabet position digits.",
          "Translate number grids to complete hidden keyword matches.",
          "Establish rapid mental indexes of key checkpoint letters (E=5, J=10, O=15, T=20, Y=25)."
        ]
      },
      {
        "weekNum": 9,
        "topic": "Logical Puzzles",
        "focus": "Alphabetical Ordering & Matrix Grids",
        "objectives": [
          "Arrange lists of similar words in perfect lexicographical dictionary order.",
          "Navigate simple matrix charts to find matching pairs.",
          "Differentiate near-spellings in high-speed sorting."
        ]
      },
      {
        "weekNum": 10,
        "topic": "Logical Puzzles",
        "focus": "Relative Sorting & Family Trees",
        "objectives": [
          "Construct relational maps based on text statements (A is taller than B, but shorter than C).",
          "Evaluate family relationships from descriptive hints.",
          "Draw clear shorthand lines/diagrams to organize facts."
        ]
      },
      {
        "weekNum": 11,
        "topic": "Algebraic Puzzles",
        "focus": "Balance Scales & Symbol Values",
        "objectives": [
          "Find numerical values of individual shapes in balanced equations.",
          "Substitute known variables to simplify complex multi-shape balances.",
          "Solve simple algebraic loops disguised as puzzles."
        ]
      },
      {
        "weekNum": 12,
        "topic": "Algebraic Puzzles",
        "focus": "Grid Number Puzzles",
        "objectives": [
          "Deduce horizontal, vertical, or diagonal arithmetic operations inside grid cells.",
          "Locate missing center values using surrounding row/column numbers.",
          "Spot multiplier relationships in columns."
        ]
      },
      {
        "weekNum": 13,
        "topic": "Sequences & Codes",
        "focus": "Term 1 Review & Mixed Sequences Test",
        "objectives": [
          "Synthesize letter series, number sequences, and shift ciphers.",
          "Complete a high-speed, 10-question mixed test under 8 minutes.",
          "Eliminate common silly arithmetic errors."
        ]
      }
    ]
  },
  {
    "termId": 2,
    "termName": "Term 2: Vocabulary, Synonyms & Antonyms",
    "focus": "Expanding vocabulary bounds, identifying precise synonyms, opposites, category classifications, and odd-one-out groupings.",
    "weeks": [
      {
        "weekNum": 14,
        "topic": "Closest in Meaning (Synonyms)",
        "focus": "High-Tier Synonym Recognition",
        "objectives": [
          "Select the closest matches for academic adjectives (e.g., diligent, eloquent).",
          "Identify words with identical meanings but distinct contextual registers.",
          "Practice spelling and reading classic 11+ vocabulary lists."
        ]
      },
      {
        "weekNum": 15,
        "topic": "Closest in Meaning (Synonyms)",
        "focus": "Contextual Shades of Meaning",
        "objectives": [
          "Match synonyms when words have multi-layered secondary definitions.",
          "Isolate meaning groups in standard multiple-choice blocks.",
          "Differentiate synonyms from mere associations (e.g., 'heat' is not a synonym of 'fire')."
        ]
      },
      {
        "weekNum": 16,
        "topic": "Opposites (Antonyms)",
        "focus": "Basic Antonym Identification",
        "objectives": [
          "Identify the direct antonym from 5 candidate options.",
          "Avoid the classic trap of choosing synonyms when opposites are requested.",
          "Recognize prefixes that create opposites (un-, dis-, in-, im-)."
        ]
      },
      {
        "weekNum": 17,
        "topic": "Opposites (Antonyms)",
        "focus": "Advanced Antonyms & Shades of Contrast",
        "objectives": [
          "Resolve antonyms for abstract concepts and literary verbs.",
          "Differentiate between partial opposites and exact antonyms.",
          "Utilize process of elimination for difficult roots."
        ]
      },
      {
        "weekNum": 18,
        "topic": "Word Analogies (Related Pairs)",
        "focus": "Synonym & Antonym Analogy Pairs",
        "objectives": [
          "Recognize pairs linked by synonymous or antonymous relationships (e.g., SLOW : FAST as WET : DRY).",
          "Ensure word-class matching (noun to noun, adjective to adjective).",
          "Identify the correct relationship direction."
        ]
      },
      {
        "weekNum": 19,
        "topic": "Word Analogies (Related Pairs)",
        "focus": "Functional & Object-to-Use Analogies",
        "objectives": [
          "Connect objects to their direct functions (e.g., PEN : WRITE as SCISSORS : CUT).",
          "Match categories, parts of a whole, and intensity levels.",
          "Practice quick reasoning verbal phrasing."
        ]
      },
      {
        "weekNum": 20,
        "topic": "Odd One Out",
        "focus": "Simple Category Classification",
        "objectives": [
          "Locate the word that does not belong to a clear logical category.",
          "Define specific, narrow categories (e.g., identifying deciduous trees vs conifers).",
          "Practice with everyday objects and animals."
        ]
      },
      {
        "weekNum": 21,
        "topic": "Odd One Out",
        "focus": "Semantic Grouping",
        "objectives": [
          "Group abstract nouns and literary vocabulary.",
          "Separate words based on subtle positive/negative connotations.",
          "Avoid choosing words merely because of physical spelling attributes."
        ]
      },
      {
        "weekNum": 22,
        "topic": "Double Definitions",
        "focus": "Homonyms & Words with Multiple Meanings",
        "objectives": [
          "Identify a single word that completes two completely independent sentences.",
          "Understand dual meaning words (e.g., BARK - tree covering and dog noise).",
          "Enhance vocabulary flexibility across homonyms."
        ]
      },
      {
        "weekNum": 23,
        "topic": "Word Connections",
        "focus": "Finding the Link",
        "objectives": [
          "Select a word that is logically related to two separate groups of words.",
          "Deduce common categories among diverse nouns.",
          "Develop lateral thinking vocabulary associations."
        ]
      },
      {
        "weekNum": 24,
        "topic": "Synonyms & Antonyms",
        "focus": "Advanced Word Associations",
        "objectives": [
          "Solve complex synonym/antonym pair selections in GL-style grid panels.",
          "Identify secondary meanings under strict time conditions.",
          "Eradicate vocabulary gaps."
        ]
      },
      {
        "weekNum": 25,
        "topic": "Odd One Out",
        "focus": "Abstract Classification Drills",
        "objectives": [
          "Classify complex vocabulary under high-speed constraints.",
          "Identify traps where four words share multiple categories but one is excluded from the narrowest.",
          "Build absolute accuracy when choices feel similar."
        ]
      },
      {
        "weekNum": 26,
        "topic": "Vocabulary & Analogies",
        "focus": "Term 2 Review & Mixed Vocab Test",
        "objectives": [
          "Synthesize synonyms, antonyms, related pairs, and odd-one-out categories.",
          "Complete a mixed 10-question vocabulary examination.",
          "Identify custom vocabulary weakness areas."
        ]
      }
    ]
  },
  {
    "termId": 3,
    "termName": "Term 3: Word Building & Puzzles",
    "focus": "Refining word synthesis, locating hidden words, compounding, letter insertion, and prefix/suffix structures.",
    "weeks": [
      {
        "weekNum": 27,
        "topic": "Compound Words",
        "focus": "Combining Word Fragments",
        "objectives": [
          "Form single cohesive compound words by joining smaller words.",
          "Spot valid combinations in split column layouts.",
          "Discard misleading false compounds."
        ]
      },
      {
        "weekNum": 28,
        "topic": "Compound Words",
        "focus": "Compound Bridge Puzzles",
        "objectives": [
          "Find a single word that fits in the middle to make two separate compound words (e.g., FOOT [BALL] ROOM).",
          "Test candidates systematically with prefix and suffix words.",
          "Recognize common compounding words (e.g., ball, house, man, land)."
        ]
      },
      {
        "weekNum": 29,
        "topic": "Hidden Words",
        "focus": "Finding Embedded Words",
        "objectives": [
          "Identify a hidden four-letter word spanning across two adjacent words.",
          "Understand that punctuation and spacing are ignored in junction spans.",
          "Scan strings systematically without losing position."
        ]
      },
      {
        "weekNum": 30,
        "topic": "Hidden Words",
        "focus": "Multi-Word Junction Spans",
        "objectives": [
          "Locate hidden words across lengthy sentences.",
          "Isolate start and end letters that bridge gaps.",
          "Differentiate hidden words from mere phonetic similarities."
        ]
      },
      {
        "weekNum": 31,
        "topic": "Insert a Letter (Completes Both Words)",
        "focus": "Vowel & Consonant Bridges",
        "objectives": [
          "Find the single letter that ends the first word and starts the second.",
          "Test vowels first (A, E, I, O, U) as high-probability connectors.",
          "Verify that both resulting words are correctly spelled."
        ]
      },
      {
        "weekNum": 32,
        "topic": "Insert a Letter (Completes Both Words)",
        "focus": "Consonant Cluster Bridges",
        "objectives": [
          "Identify trickier consonant connectors (e.g., T, S, D, R, N, L).",
          "Manage fragments that look like words but are incomplete.",
          "Practice under rigorous time pacing."
        ]
      },
      {
        "weekNum": 33,
        "topic": "Move a Letter",
        "focus": "Letter Migration",
        "objectives": [
          "Identify a letter that can be moved from the first word to the second to form two brand-new words.",
          "Ensure that the order of remaining letters in both words remains unchanged.",
          "Build speed in scanning anagrammatic shifts."
        ]
      },
      {
        "weekNum": 34,
        "topic": "Word Fragments",
        "focus": "Completing Gaps",
        "objectives": [
          "Fill missing letter groups to complete a sentence cohesively.",
          "Apply prefix and suffix rules to reconstruct broken words.",
          "Deconstruct multi-syllable academic nouns."
        ]
      },
      {
        "weekNum": 35,
        "topic": "Anagrams",
        "focus": "Solving Reordered Words",
        "objectives": [
          "Unscramble letters to match a descriptive clue or synonym.",
          "Recognize common consonant patterns (e.g., th, sh, ch, tr) to group letters.",
          "Use count limits to eliminate wrong options instantly."
        ]
      },
      {
        "weekNum": 36,
        "topic": "Anagrams",
        "focus": "Embedded Sentence Anagrams",
        "objectives": [
          "Locate and unscramble anagrams hidden within parentheses inside sentences.",
          "Evaluate context to deduce the correct word class of the unscrambled word.",
          "Apply root structures to assist unscrambling."
        ]
      },
      {
        "weekNum": 37,
        "topic": "Compound Words",
        "focus": "Complex Compounding Review",
        "objectives": [
          "Synthesize dual word builders and bridge puzzles.",
          "Ensure that no stray spelling changes occur during compound generation.",
          "Review rare compounding exceptions."
        ]
      },
      {
        "weekNum": 38,
        "topic": "Hidden & Inserted Words",
        "focus": "Junction Mastery Drills",
        "objectives": [
          "Practice combining hidden word scans and letter insertions under 40 seconds per question.",
          "Refine physical scanning tricks (e.g., hiding distractions with index fingers).",
          "Avoid spelling traps."
        ]
      },
      {
        "weekNum": 39,
        "topic": "Word Building & Puzzles",
        "focus": "Term 3 Review & Mixed Word Puzzles Test",
        "objectives": [
          "Synthesize compound words, hidden words, letter insertions, and anagrams.",
          "Complete a mixed 10-question word puzzle paper.",
          "Eradicate mechanical scanning delays."
        ]
      }
    ]
  },
  {
    "termId": 4,
    "termName": "Term 4: Exam Strategy, Mixed Drills & Advanced Logic",
    "focus": "Integrating all Verbal Reasoning topics to excel under exam conditions, mastering MCQ elimination, and maximizing pace and accuracy.",
    "weeks": [
      {
        "weekNum": 40,
        "topic": "Exam Technique",
        "focus": "Multiple-Choice Elimination (MCQ)",
        "objectives": [
          "Master the elimination strategy for 5-option Verbal Reasoning questions.",
          "Identify and discard common distractor traps (near-spellings, false codes, reverse shifts).",
          "Build absolute accuracy when choices feel highly similar."
        ]
      },
      {
        "weekNum": 41,
        "topic": "Exam Technique",
        "focus": "Time Management & Pacing",
        "objectives": [
          "Pace yourself during a standard 50-minute Verbal Reasoning paper.",
          "Learn when to skip a difficult code or number series and return to it later.",
          "Double-check arithmetic and letters systematically in final minutes."
        ]
      },
      {
        "weekNum": 42,
        "topic": "Logical Puzzles",
        "focus": "Advanced Logic Matrices",
        "objectives": [
          "Solve complex grid grids where 3 or 4 variables must be mapped.",
          "Isolate clues that yield direct facts first.",
          "Translate multi-step statements into rapid diagram symbols."
        ]
      },
      {
        "weekNum": 43,
        "topic": "Letter Codes",
        "focus": "Advanced Multi-Step Ciphers",
        "objectives": [
          "Decipher codes involving spelling reversals and index offsets.",
          "Decode codes with different rules for vowels and consonants.",
          "Handle composite letter-symbol codes."
        ]
      },
      {
        "weekNum": 44,
        "topic": "Number Series",
        "focus": "Two-Step Differences & Squares",
        "objectives": [
          "Identify series where differences themselves have a pattern (second-order differences).",
          "Recognize series based on mathematical squares, cubes, and prime numbers.",
          "Solve mixed fraction/decimal progressions."
        ]
      },
      {
        "weekNum": 45,
        "topic": "Word Connections",
        "focus": "Triple Connections & Triangles",
        "objectives": [
          "Select words that bridge three independent sets of synonyms.",
          "Solve triangle word connections where vertices have mathematical/logical relationships.",
          "Expand lateral vocabulary mapping."
        ]
      },
      {
        "weekNum": 46,
        "topic": "Algebraic Puzzles",
        "focus": "Nested Symbol Equations",
        "objectives": [
          "Solve scales with nested equations where one symbol is composed of others.",
          "Deduce negative and fractional symbol weights.",
          "Speed up algebraic deduction through mental estimation."
        ]
      },
      {
        "weekNum": 47,
        "topic": "Mixed Verbal Reasoning Drill",
        "focus": "High-Speed Drills - Set A",
        "objectives": [
          "Solve 10 mixed questions (Series, Codes, Vocab, Word Building) in under 8 minutes.",
          "Pace each item to take no longer than 45 seconds.",
          "Identify and record personal speed-bump topics."
        ]
      },
      {
        "weekNum": 48,
        "topic": "Mixed Verbal Reasoning Drill",
        "focus": "High-Speed Drills - Set B",
        "objectives": [
          "Solve 10 highly difficult, top-school level questions in 8 minutes.",
          "Maintain structural focus when faced with unfamiliar puzzle formats.",
          "Practice rapid physical indexing on paper."
        ]
      },
      {
        "weekNum": 49,
        "topic": "Mixed Verbal Reasoning Drill",
        "focus": "Accuracy & Self-Correction Drills",
        "objectives": [
          "Solve a standard GL-style paper with deliberate traps included.",
          "Implement self-correction checklists (e.g., checking possessive apostrophes or reverse signs).",
          "Eliminate silly transcription errors."
        ]
      },
      {
        "weekNum": 50,
        "topic": "Mixed Verbal Reasoning Drill",
        "focus": "Mock Examination - Paper 1",
        "objectives": [
          "Complete a comprehensive, 20-question randomized mock Verbal Reasoning paper.",
          "Simulate full exam noise and time constraints.",
          "Analyze timing charts to identify bottlenecks."
        ]
      },
      {
        "weekNum": 51,
        "topic": "Mixed Verbal Reasoning Drill",
        "focus": "Mock Examination - Paper 2",
        "objectives": [
          "Complete a second 20-question mock paper targeting super-selective grammar schools.",
          "Review comprehensive worked explanations for all 20 questions.",
          "Polishing final strategy elements."
        ]
      },
      {
        "weekNum": 52,
        "topic": "Logical Puzzles",
        "focus": "Ultimate Exam Strategy & Checklist",
        "objectives": [
          "Review Coach Pip's final checklist of selective school Verbal Reasoning traps.",
          "Establish low-stress confidence-building warmups.",
          "Visualize flawless performance and calm execution."
        ]
      }
    ]
  }
]

# ---------------------------------------------------------------------------
# Structured Question Generator
# ---------------------------------------------------------------------------
def get_questions_for_week(week_num: int) -> list:
    """Generate exactly 3 structured Verbal Reasoning questions for the week."""
    # Deterministic seeding
    random.seed(week_num)
    
    # Identify which topic we should generate
    current_week = None
    for term in CURRICULUM:
        for w in term["weeks"]:
            if w["weekNum"] == week_num:
                current_week = w
                break
        if current_week:
            break
            
    topic = current_week["topic"] if current_week else "Letter Series"
    focus = current_week["focus"] if current_week else "General Practice"
    
    questions = []
    
    # Let's generate 3 questions of the specific topic type!
    for q_id in range(1, 4):
        seed_val = week_num * 10 + q_id
        random.seed(seed_val)
        
        if topic == "Letter Series":
            step = random.choice([1, 2, 3, -1, -2])
            start = random.randint(0, 20)
            positions = [(start + step * k) % 26 for k in range(5)]
            next_pos = (start + step * 5) % 26
            letters = [ALPHABET[p] for p in positions]
            correct = ALPHABET[next_pos]
            
            options = [ALPHABET[(next_pos + offset) % 26] for offset in [-2, -1, 1, 2]]
            options = list(set(options))[:4]
            while len(options) < 4:
                extra = random.choice(ALPHABET)
                if extra != correct and extra not in options:
                    options.append(extra)
            options.append(correct)
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            desc = f"adding {step}" if step > 0 else f"subtracting {abs(step)}"
            questions.append({
                "id": q_id,
                "questionText": f"Find the letter that comes next in the sequence: {', '.join(letters)}, ____?",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"The sequence is formed by {desc} letters in the alphabet. Starting from {letters[0]} ({positions[0]+1}), we apply the step to get {', '.join(letters)}. The next letter is {correct} ({next_pos+1}).",
                "tip": "Write out the alphabet (A-Z) and write their corresponding index numbers (1-26) underneath to easily count the steps!"
            })
            
        elif topic == "Number Series" or topic == "Algebraic Puzzles":
            # Arithmetic series
            start = random.randint(1, 25)
            step = random.randint(2, 8)
            terms = [start + step * k for k in range(5)]
            correct = start + step * 5
            
            options = [correct - 2, correct - 1, correct + 1, correct + 2]
            random.shuffle(options)
            options.append(correct)
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Identify the missing number to complete the arithmetic progression: {', '.join(map(str, terms))}, ____?",
                "options": list(map(str, options)),
                "correctLetter": correct_letter,
                "correctValue": str(correct),
                "explanation": f"This number series increases by a constant step of {step}. Adding {step} to the last term {terms[-1]} gives {correct}.",
                "tip": "Always write down the differences between consecutive terms first. It's the quickest way to spot the underlying progression."
            })
            
        elif topic == "Closest in Meaning (Synonyms)":
            entry = random.choice(SYNONYMS_FALLBACK)
            correct = entry["syn"]
            target = entry["word"]
            clue = entry["clue"]
            
            distractors = [e["ant"] for e in SYNONYMS_FALLBACK if e["word"] != target][:4]
            while len(distractors) < 4:
                distractors.append("unrelated")
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Select the option that is closest in meaning (synonym) to the word: '{target.upper()}'",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"'{target.upper()}' means {clue}. The only synonym listed is '{correct}'.",
                "tip": "If a word is unfamiliar, try putting it into a sentence in your head to guess the general feeling or context of the word."
            })
            
        elif topic == "Opposites (Antonyms)":
            entry = random.choice(SYNONYMS_FALLBACK)
            correct = entry["ant"]
            target = entry["word"]
            clue = entry["clue"]
            
            distractors = [e["syn"] for e in SYNONYMS_FALLBACK if e["word"] != target][:4]
            while len(distractors) < 4:
                distractors.append("unrelated")
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Choose the option that has the opposite meaning (antonym) to the word: '{target.upper()}'",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"'{target.upper()}' means {clue}. The direct opposite meaning is '{correct}'.",
                "tip": "Be careful! The synonym is almost always included as a distractor option. Don't fall into the trap of picking the similar word!"
            })
            
        elif topic == "Word Analogies (Related Pairs)" or topic == "Word Connections":
            relation = random.choice(list(ANALOGY_FALLBACK.keys()))
            pairs = ANALOGY_FALLBACK[relation]
            pair1, pair2 = random.sample(pairs, 2)
            
            w1, w2 = pair1
            w3, w4 = pair2
            correct = w4
            
            distractors = [p[1] for p in pairs if p[1] != correct][:4]
            while len(distractors) < 4:
                distractors.append("unrelated")
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Solve the analogy relationship: {w1.upper()} is to {w2.upper()} as {w3.upper()} is to ____?",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"The relationship between {w1.upper()} and {w2.upper()} is based on '{relation}'. Applying the same relationship to {w3.upper()}, we get {correct.upper()}.",
                "tip": "State how the first two words are related as a precise rule, then apply that rule directly to the third word."
            })
            
        elif topic == "Odd One Out":
            cat = random.choice(list(ODD_FALLBACK.keys()))
            words = ODD_FALLBACK[cat]
            correct = words[-1] # The odd word is always last in the fallback list
            distractors = words[:-1]
            
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Identify the word that does NOT belong to the same logical group: ",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"The words {', '.join(distractors)} belong to the category of '{cat}'. '{correct}' is completely unrelated, so it is the odd one out.",
                "tip": "Name the category in your mind. If 4 words perfectly fit it, the 5th is your correct answer."
            })
            
        elif topic == "Hidden Words":
            word1, word2, hidden = random.choice(HIDDEN_FALLBACK)
            joined = word1.upper() + word2.upper()
            idx_pos = joined.find(hidden.upper())
            
            correct = hidden
            distractors = [h[2] for h in HIDDEN_FALLBACK if h[2] != correct][:4]
            while len(distractors) < 4:
                distractors.append("unrelated")
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Find the hidden four-letter word that spans across the boundary of the words: '{word1.upper()}' and '{word2.upper()}'",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"When joined as '{joined}', the word '{hidden.upper()}' is spelled out starting at position {idx_pos+1}.",
                "tip": "The hidden word is almost always found bridging the last few letters of the first word and the first few letters of the second."
            })
            
        elif topic == "Insert a Letter (Completes Both Words)":
            left, letter, right = random.choice(INSERT_FALLBACK)
            correct = letter
            
            distractors = ["S", "T", "D", "N"]
            if correct in distractors:
                distractors.remove(correct)
            distractors = distractors[:4]
            while len(distractors) < 4:
                distractors.append("X")
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Find the single letter that completes the word before the brackets AND starts the word after the brackets: {left}(_){right}",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"Inserting '{correct}' forms '{left}{correct}' and '{correct}{right}', which are both real, correctly spelled English words.",
                "tip": "Vowels are highly frequent connectors. If vowels don't work, try common word-ending consonants like S, T, D, or N!"
            })
            
        elif topic == "Compound Words":
            left, middle, right = random.choice(COMPOUND_FALLBACK)
            correct = middle
            
            distractors = [c[1] for c in COMPOUND_FALLBACK if c[1] != correct][:4]
            while len(distractors) < 4:
                distractors.append("unrelated")
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Choose the word that forms a compound word with both the word '{left}' (prefixed) and '{right}' (suffixed): {left} (_____) {right}",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"'{correct}' forms '{left}{correct}' (e.g. {left.capitalize()}{correct.lower()}) and '{correct}{right}' (e.g. {correct.capitalize()}{right.lower()}), both of which are valid compound words.",
                "tip": "Say each combination out loud in your head. Real compound words sound natural, whereas incorrect ones sound weird."
            })
            
        else: # Letter Codes and fallback
            shift = random.choice([1, 2, -1, -2])
            word = "CAT"
            
            def encode(w, s):
                return "".join(ALPHABET[(ALPHABET.index(ch) + s) % 26] for ch in w)
                
            code = encode(word, shift)
            correct = code
            
            options = [encode(word, s) for s in [1, 2, -1, -2, 3] if s != shift][:4]
            options = distractors = list(set(options))[:4]
            while len(options) < 4:
                options.append("XXX")
            options.append(correct)
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Using a shift cipher where each letter is moved by {shift} places, what is the code for the word '{word}'?",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"Shifting each letter of '{word}' by {shift} places gives '{correct}'.",
                "tip": "Cipher questions are easiest to solve by doing them letter by letter, and cross-referencing your results with the option choices."
            })
            
    return questions

# ---------------------------------------------------------------------------
# Markdown Curriculum String Generator
# ---------------------------------------------------------------------------
def generate_markdown_plan() -> str:
    """Generate the full Markdown plan for 11+ Verbal Reasoning."""
    md = [
        "# Eleven Plus (11+) Verbal Reasoning Study Plan",
        "## The 52-Week Year-Round Curriculum & Homework Sets",
        "**Coach Pip's Selective Grammar School Entrance Training Core**",
        "*Prepared for the GL Assessment, CEM, and Super-Selective Stage Two Exams*",
        "",
        "---",
        "",
        "## STUDY PLAN OVERVIEW",
        "Preparing for highly competitive UK selective schools (like Henrietta Barnett, Tiffin, CSSE, and St Olave's) requires a systematic, spaced approach. This 52-week plan covers the complete 11+ Verbal Reasoning syllabus, divided into four strategic terms:",
        "1. **Term 1 (Weeks 1-13)**: Sequences, Numbers & Deciphering Codes",
        "2. **Term 2 (Weeks 14-26)**: Vocabulary, Synonyms & Antonyms",
        "3. **Term 3 (Weeks 27-39)**: Word Building & Puzzles",
        "4. **Term 4 (Weeks 40-52)**: Exam Strategy, Mixed Drills & Advanced Logic",
        "",
        "Each week contains core focus objectives and a **Homework Set of 3 Selective-School Style questions** with answer keys, worked explanations, and coaching advice.",
        "",
        "---",
        ""
    ]

    for term in CURRICULUM:
        md.append(f"# {term['termName']}")
        md.append(f"**Term Focus:** {term['focus']}\n")
        
        for week in term["weeks"]:
            md.append(f"## Week {week['weekNum']}: {week['focus']}")
            md.append(f"* **Syllabus Area:** {week['topic']}")
            md.append(f"* **Learning Objectives:**")
            for obj in week["objectives"]:
                md.append(f"  - {obj}")
            md.append("")
            
            md.append(f"### 📝 Homework Set {week['weekNum']}\n")
            questions = get_questions_for_week(week["weekNum"])
            for q in questions:
                md.append(f"#### Q{q['id']}. {q['questionText']}")
                md.append("**Options:**")
                for idx, opt in enumerate(q["options"]):
                    letter = ["A", "B", "C", "D", "E"][idx]
                    md.append(f"   {letter}) {opt}")
                md.append("")
                md.append(f"**Correct Answer:** Option **{q['correctLetter']}** ({q['correctValue']})\n")
                md.append(f"**Worked Step-by-Step Explanation:**\n{q['explanation']}\n")
                md.append(f"**Coach Pip's Elite School Tip:** *{q['tip']}*\n")
                md.append("---")
            md.append("")
            
    md.append("\n### 🎉 End of 52-Week Year-Round Curriculum")
    md.append("*Congratulations on working through this plan! Regular practice, reading widely, and careful analysis of logical and numerical structures are the keys to securing a high-accuracy selective school score.*")
    return "\n".join(md)

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main():
    print("==========================================================")
    print("      11+ Verbal Reasoning 52-Week Year-Round Plan Gen    ")
    print("==========================================================\n")

    # Format data for JSON output
    full_plan_data = []
    for term in CURRICULUM:
        term_data = {
            "termId": term["termId"],
            "termName": term["termName"],
            "focus": term["focus"],
            "weeks": []
        }
        for week in term["weeks"]:
            term_data["weeks"].append({
                "weekNum": week["weekNum"],
                "topic": week["topic"],
                "focus": week["focus"],
                "objectives": week["objectives"],
                "homeworkSet": get_questions_for_week(week["weekNum"])
            })
        full_plan_data.append(term_data)

    # Save to JSON
    json_path = "11_Plus_VR_52_Week_Plan.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_plan_data, f, indent=2, ensure_ascii=False)
    print(f"[Success] Saved 52-Week Plan JSON to: {json_path}")

    # Save to Markdown
    md_path = "11_Plus_VR_52_Week_Plan.md"
    markdown_content = generate_markdown_plan()
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"[Success] Saved 52-Week Plan Markdown to: {md_path}")

    # Register in RAG vector store
    if get_elevenplus_rag_store:
        try:
            print("\nRegistering 52-Week Year-Round sets with the RAG Store...")
            store = get_elevenplus_rag_store()
            
            # Format into batch homework objects for RAG ingestion
            batch_data = []
            for term in full_plan_data:
                for week in term["weeks"]:
                    # Create readable content string
                    content_str = (
                        f"11+ Verbal Reasoning 52-Week Plan - Term {term['termId']} - Week {week['weekNum']}\n"
                        f"Topic Focus: {week['focus']}\n"
                        f"Syllabus: {week['topic']}\n"
                        f"Objectives:\n" + "\n".join([f"- {o}" for o in week['objectives']]) + "\n\n"
                    )
                    
                    for idx, q in enumerate(week["homeworkSet"], 1):
                        content_str += (
                            f"Homework Question {idx}:\n"
                            f"{q['questionText']}\n"
                            f"Options: {', '.join(q['options'])}\n"
                            f"Correct Answer: {q['correctLetter']} ({q['correctValue']})\n"
                            f"Explanation: {q['explanation']}\n"
                            f"Coaching Strategy: {q['tip']}\n\n"
                        )
                    
                    metadata = {
                        "year_group": 6,
                        "subject": "VerbalReasoning",
                        "key_stage": "11+",
                        "topic": week["topic"],
                        "week_num": week["weekNum"],
                        "term_id": term["termId"],
                        "exam_style": "GL & Selective School Style",
                        "created_at": datetime.now().isoformat()
                    }
                    
                    batch_data.append({
                        "content": content_str,
                        "metadata": metadata,
                        "doc_id": f"elevenplus_vr_year_round_week_{week['weekNum']:02d}"
                    })
            
            store.add_batch_homework(batch_data)
            print("Successfully loaded 52 weekly plan entries into the RAG Store.")
        except Exception as e:
            print(f"RAG Integration skipped or failed: {e}")
    else:
        print("\nNote: RAG Store is not available in standalone execution. Local files generated successfully.")

if __name__ == "__main__":
    main()
