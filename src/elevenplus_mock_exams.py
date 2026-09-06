"""Original, locally scored 11+ mock exams.

The public sources below are used only to confirm curriculum scope and current
exam format.  Every question in this module is original Homework Magic content;
no commercial or school paper is copied.  Answers stay server-side until an
attempt is submitted, and no LLM or paid API is used on the mock-exam path.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, Mapping

from src.elevenplus_mock_exam_expansion import (
    ADDITIONAL_EXAMS,
    ADDITIONAL_PUBLIC_SOURCES,
    ADDITIONAL_QUESTIONS,
)
from src.webapp.runtime import owner_key


MOCK_EXAM_PLAN = "elevenplus_monthly"
MOCK_EXAM_PLAN_NAME = "11+ Premium"
FREE_MOCK_EXAM_ID = "common-diagnostic-1"
CONTENT_VERSION = 1

PUBLIC_SOURCES: Dict[str, Dict[str, str]] = {
    "dfe-primary": {
        "title": "DfE national curriculum for Key Stages 1 and 2",
        "url": (
            "https://www.gov.uk/government/publications/"
            "national-curriculum-in-england-framework-for-key-stages-1-to-4"
        ),
    },
    "common-four-subject": {
        "title": "Warwickshire Council: 11+ test subjects and format",
        "url": "https://www.warwickshire.gov.uk/grammar-schools-11-test/11-test",
    },
    "qe-barnet": {
        "title": "Queen Elizabeth's School: September 2027 admissions process",
        "url": "https://www.qebarnet.co.uk/admissions-information/admissions/",
    },
    "qe-barnet-samples": {
        "title": "Queen Elizabeth's School: public sample-test information",
        "url": "https://www.qebarnet.co.uk/admissions-information/sample-test-papers/",
    },
    "tiffin-2027": {
        "title": "Tiffin School: September 2027 admissions FAQs",
        "url": (
            "https://www.tiffinschool.co.uk/wp-content/uploads/2026/04/"
            "FREQUENTLY-ASKED-QUESTIONS-FAQs-Entry-Sept-2027.pdf"
        ),
    },
}
PUBLIC_SOURCES.update(ADDITIONAL_PUBLIC_SOURCES)


class MockExamError(ValueError):
    """Base class for safe mock-exam errors."""


class MockExamNotFound(MockExamError):
    """Raised when an exam identifier is not in the public catalogue."""


class InvalidAttempt(MockExamError):
    """Raised when an attempt token is malformed or belongs to another user."""


class ExpiredAttempt(MockExamError):
    """Raised after the bounded submission grace period has elapsed."""


def _question(
    question_id: str,
    subject: str,
    topic: str,
    prompt: str,
    options: Iterable[tuple[str, str]],
    answer: str,
    explanation: str,
    *,
    context: str = "",
) -> Dict[str, Any]:
    option_rows = [{"label": label, "text": text} for label, text in options]
    labels = {row["label"] for row in option_rows}
    if answer not in labels:
        raise ValueError(f"{question_id} has an answer outside its options")
    if len(labels) != len(option_rows) or len(option_rows) < 2:
        raise ValueError(f"{question_id} has invalid options")
    return {
        "id": question_id,
        "subject": subject,
        "topic": topic,
        "prompt": prompt,
        "context": context,
        "options": option_rows,
        "answer": answer,
        "explanation": explanation,
    }


_QUESTIONS = [
    # Mathematics
    _question(
        "m01", "Maths", "Fractions", "What is three fifths of 45?",
        (("A", "18"), ("B", "27"), ("C", "30"), ("D", "35")), "B",
        "One fifth of 45 is 9, so three fifths is 3 × 9 = 27.",
    ),
    _question(
        "m02", "Maths", "Percentages", "What is 15% of 240?",
        (("A", "24"), ("B", "30"), ("C", "36"), ("D", "40")), "C",
        "10% of 240 is 24 and 5% is 12. Together, 15% is 36.",
    ),
    _question(
        "m03", "Maths", "Ratio",
        "Red and blue counters are in the ratio 3:5. There are 64 counters altogether. How many are red?",
        (("A", "16"), ("B", "24"), ("C", "32"), ("D", "40")), "B",
        "There are 8 equal parts. Each part is 64 ÷ 8 = 8, so red counters = 3 × 8 = 24.",
    ),
    _question(
        "m04", "Maths", "Time",
        "A train leaves at 09:47 and travels for 1 hour 38 minutes. When does it arrive?",
        (("A", "11:15"), ("B", "11:25"), ("C", "11:35"), ("D", "12:25")), "B",
        "09:47 plus 1 hour is 10:47. Adding 38 minutes gives 11:25.",
    ),
    _question(
        "m05", "Maths", "Area",
        "A 12 cm by 7 cm rectangle has a 3 cm by 3 cm square cut from it. What area remains?",
        (("A", "66 cm²"), ("B", "72 cm²"), ("C", "75 cm²"), ("D", "81 cm²")), "C",
        "The rectangle is 84 cm² and the removed square is 9 cm². 84 − 9 = 75 cm².",
    ),
    _question(
        "m06", "Maths", "Sequences", "What is the next number? 7, 13, 25, 49, …",
        (("A", "73"), ("B", "87"), ("C", "96"), ("D", "97")), "D",
        "Each term is doubled and then 1 is subtracted. 49 × 2 − 1 = 97.",
    ),
    _question(
        "m07", "Maths", "Averages", "What is the mean of 14, 18, 21 and 27?",
        (("A", "19"), ("B", "20"), ("C", "21"), ("D", "22")), "B",
        "The total is 80. There are four numbers, so the mean is 80 ÷ 4 = 20.",
    ),
    _question(
        "m08", "Maths", "Fractions", "Which fraction is equal to 21/28?",
        (("A", "2/3"), ("B", "3/4"), ("C", "4/5"), ("D", "7/8")), "B",
        "Divide the numerator and denominator by 7: 21/28 = 3/4.",
    ),
    _question(
        "m09", "Maths", "Algebra", "Solve 4n + 7 = 39.",
        (("A", "6"), ("B", "7"), ("C", "8"), ("D", "9")), "C",
        "Subtract 7 to get 4n = 32, then divide by 4. n = 8.",
    ),
    _question(
        "m10", "Maths", "Volume",
        "A cuboid is 6 cm long, 4 cm wide and 3 cm high. What is its volume?",
        (("A", "13 cm³"), ("B", "24 cm³"), ("C", "48 cm³"), ("D", "72 cm³")), "D",
        "Volume = length × width × height, so 6 × 4 × 3 = 72 cm³.",
    ),
    _question(
        "m11", "Maths", "Decimals", "Work out 2.75 + 3.60 − 1.85.",
        (("A", "3.50"), ("B", "4.40"), ("C", "4.50"), ("D", "5.20")), "C",
        "2.75 + 3.60 = 6.35, and 6.35 − 1.85 = 4.50.",
    ),
    _question(
        "m12", "Maths", "Multi-step problems",
        "A school has 168 pencils in packs of 12. Five packs are used. How many pencils remain?",
        (("A", "60"), ("B", "96"), ("C", "108"), ("D", "156")), "C",
        "Five packs contain 5 × 12 = 60 pencils. 168 − 60 = 108.",
    ),
    _question(
        "m13", "Maths", "Angles",
        "Two angles in a triangle are 48° and 67°. What is the third angle?",
        (("A", "55°"), ("B", "65°"), ("C", "75°"), ("D", "115°")), "B",
        "Angles in a triangle total 180°. 180 − 48 − 67 = 65°.",
    ),
    _question(
        "m14", "Maths", "Probability",
        "A bag contains 5 red, 3 blue and 2 green counters. What is the probability of choosing red?",
        (("A", "1/5"), ("B", "3/10"), ("C", "1/2"), ("D", "2/3")), "C",
        "There are 10 counters altogether and 5 are red, so the probability is 5/10 = 1/2.",
    ),
    _question(
        "m15", "Maths", "Scale",
        "On a map, 1 cm represents 5 km. Two towns are 7.4 cm apart on the map. How far apart are they?",
        (("A", "12.4 km"), ("B", "35 km"), ("C", "37 km"), ("D", "42 km")), "C",
        "Multiply the map distance by the scale: 7.4 × 5 = 37 km.",
    ),
    _question(
        "m16", "Maths", "Data handling",
        "Four quiz scores are 18, 22, 15 and 25. What is the median score?",
        (("A", "18"), ("B", "20"), ("C", "22"), ("D", "25")), "B",
        "In order the scores are 15, 18, 22 and 25. The median is the mean of 18 and 22, which is 20.",
    ),

    # English
    _question(
        "e01", "English", "Vocabulary", "Which word is closest in meaning to reluctant?",
        (("A", "eager"), ("B", "unwilling"), ("C", "careless"), ("D", "cheerful")), "B",
        "Reluctant means unsure or unwilling to do something.",
    ),
    _question(
        "e02", "English", "Vocabulary", "Which word is the opposite of scarce?",
        (("A", "rare"), ("B", "hidden"), ("C", "plentiful"), ("D", "tiny")), "C",
        "Scarce means in short supply. Plentiful means there is a lot available.",
    ),
    _question(
        "e03", "English", "Punctuation", "Which sentence is punctuated correctly?",
        (
            ("A", "“Wait for me”! called Arlo."),
            ("B", "“Wait for me!” called Arlo."),
            ("C", "“Wait for me”! Called Arlo."),
            ("D", "“Wait for me!” Called arlo."),
        ),
        "B", "The exclamation mark belongs inside the speech marks, and called is not given a capital letter.",
    ),
    _question(
        "e04", "English", "Spelling", "Which spelling is correct?",
        (("A", "neccessary"), ("B", "necesary"), ("C", "necessary"), ("D", "necessery")), "C",
        "Necessary has one c and two s letters: ne-ce-ss-ary.",
    ),
    _question(
        "e05", "English", "Grammar", "Choose the sentence with correct subject–verb agreement.",
        (
            ("A", "The basket of apples were heavy."),
            ("B", "The basket of apples was heavy."),
            ("C", "The basket of apples are heavy."),
            ("D", "The basket of apples be heavy."),
        ),
        "B", "The subject is the singular noun basket, so the verb is was.",
    ),
    _question(
        "e06", "English", "Apostrophes",
        "Which sentence shows that the coats belong to several pupils?",
        (
            ("A", "The pupils coats were wet."),
            ("B", "The pupil's coats were wet."),
            ("C", "The pupils' coats were wet."),
            ("D", "The pupils's coats were wet."),
        ),
        "C", "For a regular plural noun ending in s, add the apostrophe after the s: pupils'.",
    ),
    _question(
        "e07", "English", "Vocabulary", "If someone is meticulous, what are they like?",
        (
            ("A", "Very careful and precise"),
            ("B", "Often noisy and impatient"),
            ("C", "Quick to forget"),
            ("D", "Easily frightened"),
        ),
        "A", "Meticulous describes someone who pays very close attention to detail.",
    ),
    _question(
        "e08", "English", "Word structure", "Which prefix makes the opposite of legal?",
        (("A", "dis-"), ("B", "il-"), ("C", "mis-"), ("D", "pre-")), "B",
        "The opposite of legal is illegal, formed with the prefix il-.",
    ),
    _question(
        "e09", "English", "Verb forms",
        "Choose the best words: By the time the bell rang, we ___ the puzzle.",
        (("A", "finish"), ("B", "finished"), ("C", "had finished"), ("D", "will finish")), "C",
        "Had finished shows that completing the puzzle happened before the bell rang.",
    ),
    _question(
        "e10", "English", "Clauses",
        "Which part is the subordinate clause? Although it was raining, the match continued.",
        (
            ("A", "Although it was raining"),
            ("B", "the match"),
            ("C", "the match continued"),
            ("D", "continued"),
        ),
        "A", "Although it was raining cannot stand alone here and adds information to the main clause.",
    ),
    _question(
        "e11", "English", "Comprehension",
        "Why did Mina wait before crossing the bridge?",
        (
            ("A", "She had forgotten where the bridge led."),
            ("B", "The boards looked slippery and the river was rising."),
            ("C", "She wanted to watch the sunrise."),
            ("D", "A gate blocked the path."),
        ),
        "B", "The passage links Mina's pause to the shining boards and the higher, faster river.",
        context=(
            "At dawn, Mina reached the old footbridge. Rain had polished the wooden boards until "
            "they shone, and the river below ran higher and faster than yesterday. She tightened "
            "her backpack straps, tested the first board with one boot and hesitated. On the far "
            "bank, the bakery chimney had begun to smoke. Mina took a slow breath and stepped forward."
        ),
    ),
    _question(
        "e12", "English", "Comprehension vocabulary",
        "In the passage, what does hesitated most nearly mean?",
        (("A", "paused because she was unsure"), ("B", "laughed loudly"), ("C", "ran quickly"), ("D", "looked behind her")), "A",
        "Mina pauses to check the bridge before deciding to move.",
        context=(
            "At dawn, Mina reached the old footbridge. Rain had polished the wooden boards until "
            "they shone, and the river below ran higher and faster than yesterday. She tightened "
            "her backpack straps, tested the first board with one boot and hesitated. On the far "
            "bank, the bakery chimney had begun to smoke. Mina took a slow breath and stepped forward."
        ),
    ),
    _question(
        "e13", "English", "Inference", "What can we infer about Mina?",
        (
            ("A", "She is careless."),
            ("B", "She is cautious but determined."),
            ("C", "She is lost."),
            ("D", "She dislikes the bakery."),
        ),
        "B", "She checks the bridge carefully, then controls her nerves and carries on.",
        context=(
            "At dawn, Mina reached the old footbridge. Rain had polished the wooden boards until "
            "they shone, and the river below ran higher and faster than yesterday. She tightened "
            "her backpack straps, tested the first board with one boot and hesitated. On the far "
            "bank, the bakery chimney had begun to smoke. Mina took a slow breath and stepped forward."
        ),
    ),
    _question(
        "e14", "English", "Writer's choices",
        "Why does the writer mention smoke from the bakery chimney?",
        (
            ("A", "To show that the bridge is on fire"),
            ("B", "To give Mina a clear destination on the far bank"),
            ("C", "To prove that it is raining"),
            ("D", "To explain why the river is high"),
        ),
        "B", "The bakery is a visible goal beyond the bridge, helping us understand why Mina continues.",
        context=(
            "At dawn, Mina reached the old footbridge. Rain had polished the wooden boards until "
            "they shone, and the river below ran higher and faster than yesterday. She tightened "
            "her backpack straps, tested the first board with one boot and hesitated. On the far "
            "bank, the bakery chimney had begun to smoke. Mina took a slow breath and stepped forward."
        ),
    ),
    _question(
        "e15", "English", "Word classes",
        "Which word is the adverb in this sentence? The fox moved silently through the grass.",
        (("A", "fox"), ("B", "moved"), ("C", "silently"), ("D", "grass")), "C",
        "Silently describes how the fox moved, so it is an adverb.",
    ),
    _question(
        "e16", "English", "Relative clauses",
        "Choose the best word: The bicycle, ___ had a flat tyre, was left by the gate.",
        (("A", "who"), ("B", "which"), ("C", "where"), ("D", "when")), "B",
        "Which introduces extra information about a thing: the bicycle.",
    ),

    # Verbal reasoning
    _question(
        "v01", "Verbal Reasoning", "Letter codes",
        "In a code, every letter moves one place forward in the alphabet. How is FARM written?",
        (("A", "GBSN"), ("B", "GBSO"), ("C", "FBSN"), ("D", "EZQL")), "A",
        "F→G, A→B, R→S and M→N, so FARM becomes GBSN.",
    ),
    _question(
        "v02", "Verbal Reasoning", "Letter sequences", "What comes next? AZ, BY, CX, DW, …",
        (("A", "EU"), ("B", "EV"), ("C", "FU"), ("D", "FV")), "B",
        "The first letters move forwards A–E while the second letters move backwards Z–V.",
    ),
    _question(
        "v03", "Verbal Reasoning", "Analogies", "Puppy is to dog as kitten is to …",
        (("A", "cub"), ("B", "cat"), ("C", "foal"), ("D", "rabbit")), "B",
        "A puppy is a young dog, and a kitten is a young cat.",
    ),
    _question(
        "v04", "Verbal Reasoning", "Odd one out", "Which word is the odd one out?",
        (("A", "whisper"), ("B", "murmur"), ("C", "shout"), ("D", "mutter")), "C",
        "Whisper, murmur and mutter are quiet ways of speaking. A shout is loud.",
    ),
    _question(
        "v05", "Verbal Reasoning", "Word links",
        "Which word can go after SUN and before POT to make two new words?",
        (("A", "light"), ("B", "flower"), ("C", "shine"), ("D", "beam")), "B",
        "SUN + FLOWER makes sunflower, and FLOWER + POT makes flowerpot.",
    ),
    _question(
        "v06", "Verbal Reasoning", "Alphabet values",
        "Using A=1, B=2, C=3 and so on, what is the value of FACE?",
        (("A", "12"), ("B", "14"), ("C", "15"), ("D", "17")), "C",
        "F=6, A=1, C=3 and E=5. Their total is 6+1+3+5=15.",
    ),
    _question(
        "v07", "Verbal Reasoning", "Anagrams", "Which word is an anagram of SILENT?",
        (("A", "LISTEN"), ("B", "ENLISTS"), ("C", "TINSELLED"), ("D", "SLENDER")), "A",
        "SILENT and LISTEN use exactly the same six letters.",
    ),
    _question(
        "v08", "Verbal Reasoning", "Number sequences", "What is the next number? 3, 6, 11, 18, 27, …",
        (("A", "36"), ("B", "37"), ("C", "38"), ("D", "39")), "C",
        "The gaps are 3, 5, 7 and 9. The next gap is 11, so 27+11=38.",
    ),
    _question(
        "v09", "Verbal Reasoning", "Letter relationships",
        "AC becomes DF by moving each letter three places forward. What does BE become?",
        (("A", "DG"), ("B", "EH"), ("C", "FI"), ("D", "HJ")), "B",
        "B moves to E and E moves to H, so BE becomes EH.",
    ),
    _question(
        "v10", "Verbal Reasoning", "Word relationships", "Which pair has a different relationship?",
        (("A", "hot : cold"), ("B", "day : night"), ("C", "up : down"), ("D", "fast : quick")), "D",
        "The first three pairs are opposites. Fast and quick have similar meanings.",
    ),
    _question(
        "v11", "Verbal Reasoning", "Logic",
        "All lums are bright. No bright things are hidden. Which statement must be true?",
        (
            ("A", "Some lums are hidden."),
            ("B", "No lums are hidden."),
            ("C", "All hidden things are lums."),
            ("D", "Nothing is bright."),
        ),
        "B", "Every lum is bright, and bright things cannot be hidden, so no lum is hidden.",
    ),
    _question(
        "v12", "Verbal Reasoning", "Missing letters",
        "The same two letters complete both words: C __ T and ST __ E. Which letters are they?",
        (("A", "AR"), ("B", "ON"), ("C", "EP"), ("D", "OP")), "A",
        "AR makes C + AR + T = CART and ST + AR + E = STARE.",
    ),
    _question(
        "v13", "Verbal Reasoning", "Anagrams", "Which word can be made from the letters in SECURE?",
        (("A", "RESCUE"), ("B", "CURSES"), ("C", "CURSED"), ("D", "SOURCE")), "A",
        "RESCUE uses the letters R, E, S, C, U and E, exactly matching SECURE.",
    ),
    _question(
        "v14", "Verbal Reasoning", "Letter sequences",
        "What comes next in the sequence B, E, I, N, T, …? Continue after Z from A.",
        (("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")), "A",
        "The jumps are +3, +4, +5 and +6. T plus 7 wraps past Z to A.",
    ),
    _question(
        "v15", "Verbal Reasoning", "Alphabet values",
        "Using A=1, B=2, C=3 and so on, what is the value of DOG?",
        (("A", "22"), ("B", "24"), ("C", "26"), ("D", "28")), "C",
        "D=4, O=15 and G=7. Their total is 4+15+7=26.",
    ),
    _question(
        "v16", "Verbal Reasoning", "Analogies", "Bird is to nest as bee is to …",
        (("A", "web"), ("B", "hive"), ("C", "burrow"), ("D", "kennel")), "B",
        "A nest is a bird's home, and a hive is a bee's home.",
    ),

    # Non-verbal reasoning represented with accessible text symbols.
    _question(
        "n01", "Non-Verbal Reasoning", "Alternating patterns", "What comes next? ▲, ■, ▲, ■, …",
        (("A", "▲"), ("B", "■"), ("C", "●"), ("D", "◆")), "A",
        "The pattern alternates triangle, square, triangle, square.",
    ),
    _question(
        "n02", "Non-Verbal Reasoning", "Rotation", "An arrow turns 90° clockwise each time: ↑, →, ↓, …",
        (("A", "↑"), ("B", "→"), ("C", "↓"), ("D", "←")), "D",
        "After pointing down, a 90° clockwise turn makes the arrow point left.",
    ),
    _question(
        "n03", "Non-Verbal Reasoning", "Growing patterns", "What comes next? ●, ●●, ●●●, …",
        (("A", "●●"), ("B", "●●●"), ("C", "●●●●"), ("D", "●●●●●")), "C",
        "One circle is added at each step, so the next group has four circles.",
    ),
    _question(
        "n04", "Non-Verbal Reasoning", "Odd one out", "Which group is the odd one out?",
        (("A", "▲▲"), ("B", "■■"), ("C", "●●"), ("D", "▲■")), "D",
        "The first three groups contain two matching shapes. The last group mixes two shapes.",
    ),
    _question(
        "n05", "Non-Verbal Reasoning", "Position changes", "What comes next? ○●, ●○, ○●, …",
        (("A", "○○"), ("B", "○●"), ("C", "●○"), ("D", "●●")), "C",
        "The hollow and filled circles swap positions each time.",
    ),
    _question(
        "n06", "Non-Verbal Reasoning", "Shape properties",
        "The shapes gain one side each time: triangle, square, pentagon, …",
        (("A", "circle"), ("B", "hexagon"), ("C", "octagon"), ("D", "rectangle")), "B",
        "A triangle has 3 sides, a square 4 and a pentagon 5. Next is a 6-sided hexagon.",
    ),
    _question(
        "n07", "Non-Verbal Reasoning", "Position sequences",
        "A dot moves around the corners clockwise: top-left, top-right, bottom-right, …",
        (("A", "bottom-left"), ("B", "top-left"), ("C", "centre"), ("D", "top-right")), "A",
        "Moving clockwise from bottom-right takes the dot to bottom-left.",
    ),
    _question(
        "n08", "Non-Verbal Reasoning", "Matrices",
        "Complete the 2×2 pattern. Top row: ▲ then ■. Bottom row: ■ then ?",
        (("A", "▲"), ("B", "■"), ("C", "●"), ("D", "◆")), "A",
        "Each row contains one triangle and one square in opposite positions.",
    ),
    _question(
        "n09", "Non-Verbal Reasoning", "Repeating groups", "What comes next? ▲■●, ■●▲, ●▲■, …",
        (("A", "▲■●"), ("B", "▲●■"), ("C", "■▲●"), ("D", "●■▲")), "A",
        "The first shape moves to the end each time. After three moves, the starting order returns.",
    ),
    _question(
        "n10", "Non-Verbal Reasoning", "Counting",
        "A pattern has 2 stars in picture 1, 4 in picture 2 and 8 in picture 3. How many in picture 4?",
        (("A", "10"), ("B", "12"), ("C", "14"), ("D", "16")), "D",
        "The number of stars doubles each time: 2, 4, 8, 16.",
    ),
    _question(
        "n11", "Non-Verbal Reasoning", "Reflection",
        "A horizontal mirror reflection changes a left arrow (←) into which arrow?",
        (("A", "↑"), ("B", "→"), ("C", "↓"), ("D", "←")), "B",
        "A left-right reflection reverses the horizontal direction, so left becomes right.",
    ),
    _question(
        "n12", "Non-Verbal Reasoning", "Two-rule patterns",
        "The shape alternates circle, square while the shading alternates hollow, filled: ○, ■, ○, …",
        (("A", "□"), ("B", "■"), ("C", "●"), ("D", "○")), "B",
        "The next shape is a square and the next shading is filled, giving ■.",
    ),
    _question(
        "n13", "Non-Verbal Reasoning", "Number and shape patterns",
        "Picture 1 has one square, picture 2 has two circles, picture 3 has three triangles. What should picture 4 have?",
        (
            ("A", "four squares"),
            ("B", "three squares"),
            ("C", "four circles"),
            ("D", "five squares"),
        ),
        "A", "The number rises by one and the shapes repeat square, circle, triangle.",
    ),
    _question(
        "n14", "Non-Verbal Reasoning", "Symmetry", "Which shape has exactly one line of symmetry?",
        (
            ("A", "a square"),
            ("B", "a non-square rectangle"),
            ("C", "an isosceles triangle"),
            ("D", "a scalene triangle"),
        ),
        "C", "An isosceles triangle has one line of symmetry. A square has four, a rectangle two and a scalene triangle none.",
    ),
    _question(
        "n15", "Non-Verbal Reasoning", "Growing patterns", "What comes next? □, □■, □■■, …",
        (("A", "□"), ("B", "□■"), ("C", "□■■"), ("D", "□■■■")), "D",
        "One filled square is added after the hollow square at each step.",
    ),
    _question(
        "n16", "Non-Verbal Reasoning", "Rotation",
        "An arrow turns 45° clockwise each time: ↑, ↗, →, ↘, …",
        (("A", "↓"), ("B", "↙"), ("C", "←"), ("D", "↖")), "A",
        "One more 45° clockwise turn from ↘ makes the arrow point down.",
    ),
]
_QUESTIONS.extend(ADDITIONAL_QUESTIONS)

_QUESTION_BY_ID = {question["id"]: question for question in _QUESTIONS}
if len(_QUESTION_BY_ID) != len(_QUESTIONS):
    raise ValueError("Mock-exam question IDs must be unique")


EXAMS: Dict[str, Dict[str, Any]] = {
    "common-diagnostic-1": {
        "id": "common-diagnostic-1",
        "category": "common",
        "title": "Common 11+ Diagnostic",
        "description": "A short, friendly sample across all four common 11+ subjects.",
        "school": None,
        "stage": "Diagnostic",
        "duration_minutes": 15,
        "is_free": True,
        "question_ids": (
            "m01", "m04", "m08", "e01", "e03", "e11",
            "v01", "v03", "v08", "n01", "n02", "n07",
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Short four-subject multiple-choice diagnostic.",
        "last_verified": "2026-07-28",
    },
    "common-full-1": {
        "id": "common-full-1",
        "category": "common",
        "title": "Common Four-Subject Mock A",
        "description": "A timed mix of Maths, English, Verbal and Non-Verbal Reasoning.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(1, 9)]
            + [f"e{i:02d}" for i in range(1, 9)]
            + [f"v{i:02d}" for i in range(1, 9)]
            + [f"n{i:02d}" for i in range(1, 9)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-07-28",
    },
    "common-full-2": {
        "id": "common-full-2",
        "category": "common",
        "title": "Common Four-Subject Mock B",
        "description": "A second timed paper with a different mix of four-subject questions.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(9, 17)]
            + [f"e{i:02d}" for i in range(9, 17)]
            + [f"v{i:02d}" for i in range(9, 17)]
            + [f"n{i:02d}" for i in range(9, 17)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-07-28",
    },
    "qe-barnet-stage-one-1": {
        "id": "qe-barnet-stage-one-1",
        "category": "school_target",
        "title": "QE Barnet Target Mock",
        "description": "Original Maths and English multiple-choice practice for the published QE format.",
        "school": "Queen Elizabeth's School, Barnet",
        "stage": "Entrance test",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(1, 13)]
            + [f"e{i:02d}" for i in range(1, 13)]
        ),
        "source_ids": ("dfe-primary", "qe-barnet", "qe-barnet-samples"),
        "format_note": "Maths and English multiple-choice practice; not an official QE paper.",
        "last_verified": "2026-07-28",
    },
    "tiffin-stage-one-1": {
        "id": "tiffin-stage-one-1",
        "category": "school_target",
        "title": "Tiffin Stage One Target Mock",
        "description": "Original Maths and English multiple-choice practice for Tiffin Stage One.",
        "school": "Tiffin School",
        "stage": "Stage One",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(3, 15)]
            + [f"e{i:02d}" for i in range(3, 15)]
        ),
        "source_ids": ("dfe-primary", "tiffin-2027"),
        "format_note": "Shortened Stage One-style practice; not an official Tiffin paper.",
        "last_verified": "2026-07-28",
    },
}
EXAMS.update(ADDITIONAL_EXAMS)


def _exam(exam_id: str) -> Dict[str, Any]:
    exam = EXAMS.get(str(exam_id or "").strip())
    if exam is None:
        raise MockExamNotFound("This mock exam is not available.")
    return exam


def _public_exam(exam: Mapping[str, Any], has_mock_access: bool) -> Dict[str, Any]:
    question_ids = tuple(exam["question_ids"])
    subject_counts = Counter(_QUESTION_BY_ID[item]["subject"] for item in question_ids)
    is_free = exam["id"] == FREE_MOCK_EXAM_ID
    is_available = bool(is_free or has_mock_access)
    return {
        "id": exam["id"],
        "category": exam["category"],
        "title": exam["title"],
        "description": exam["description"],
        "school": exam["school"],
        "stage": exam["stage"],
        "duration_minutes": exam["duration_minutes"],
        "question_count": len(question_ids),
        "subject_counts": dict(subject_counts),
        "is_free": is_free,
        "available": is_available,
        "required_plan": None if is_free else MOCK_EXAM_PLAN,
        "required_plan_name": None if is_free else MOCK_EXAM_PLAN_NAME,
        "format_note": exam["format_note"],
        "last_verified": exam["last_verified"],
        "sources": [
            {"title": PUBLIC_SOURCES[source_id]["title"], "url": PUBLIC_SOURCES[source_id]["url"]}
            for source_id in exam["source_ids"]
        ],
    }


def mock_exam_catalogue(has_mock_access: bool = False) -> Dict[str, Any]:
    """Return answer-free exam metadata."""
    exams = [_public_exam(exam, has_mock_access) for exam in EXAMS.values()]
    return {
        "success": True,
        "licensing": (
            "All mock questions are original Homework Magic content. Public sources "
            "are used only for curriculum and format guidance."
        ),
        "disclaimer": (
            "These practice simulations are not official papers and Homework Magic is "
            "not endorsed by the named schools. Families should re-check each school's "
            "current admissions information."
        ),
        "exams": exams,
    }


def _token_secret() -> bytes:
    value = (
        os.getenv("MOCK_EXAM_TOKEN_SECRET")
        or os.getenv("SESSION_OWNER_SECRET")
        or "homework-magic-development-only-mock-secret"
    )
    return value.encode("utf-8")


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def _sign_payload(payload: Mapping[str, Any]) -> str:
    encoded = _b64_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(_token_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64_encode(signature)}"


def _read_payload(token: str) -> Dict[str, Any]:
    clean_token = str(token or "").strip()
    if not clean_token or len(clean_token) > 4096 or clean_token.count(".") != 1:
        raise InvalidAttempt("This mock attempt could not be checked. Please start again.")
    encoded, encoded_signature = clean_token.split(".", 1)
    expected = hmac.new(_token_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    try:
        supplied = _b64_decode(encoded_signature)
        payload_bytes = _b64_decode(encoded)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidAttempt("This mock attempt could not be checked. Please start again.") from exc
    # Reject non-canonical base64 spellings. The unused low bits in the final
    # character can otherwise be changed without changing the decoded bytes,
    # which makes a visibly modified token appear valid.
    canonical = (
        _b64_encode(supplied) == encoded_signature
        and _b64_encode(payload_bytes) == encoded
    )
    if (
        not canonical
        or not hmac.compare_digest(expected, supplied)
        or not isinstance(payload, dict)
    ):
        raise InvalidAttempt("This mock attempt could not be checked. Please start again.")
    if int(payload.get("version") or 0) != CONTENT_VERSION:
        raise InvalidAttempt("This mock has been updated. Please start a fresh attempt.")
    return payload


def start_mock_exam(exam_id: str, identity: str, *, now: int | None = None) -> Dict[str, Any]:
    """Create a bounded, owner-bound attempt without exposing the answer key."""
    exam = _exam(exam_id)
    issued_at = int(now if now is not None else time.time())
    deadline = issued_at + int(exam["duration_minutes"]) * 60
    payload = {
        "version": CONTENT_VERSION,
        "exam_id": exam["id"],
        "owner": owner_key(str(identity)),
        "issued_at": issued_at,
        "deadline": deadline,
        "submit_by": deadline + 15 * 60,
        "nonce": secrets.token_urlsafe(12),
    }
    questions = []
    for number, question_id in enumerate(exam["question_ids"], start=1):
        question = _QUESTION_BY_ID[question_id]
        questions.append({
            "id": question["id"],
            "number": number,
            "subject": question["subject"],
            "topic": question["topic"],
            "prompt": question["prompt"],
            "context": question["context"],
            "options": [dict(option) for option in question["options"]],
        })
    return {
        "success": True,
        "exam": _public_exam(exam, has_mock_access=True),
        "attempt": {
            "token": _sign_payload(payload),
            "started_at": issued_at,
            "deadline": deadline,
        },
        "questions": questions,
    }


def _normalise_answers(answers: Mapping[str, Any]) -> Dict[str, str]:
    if not isinstance(answers, Mapping) or len(answers) > 100:
        raise MockExamError("The answer list is too large.")
    cleaned: Dict[str, str] = {}
    for question_id, raw_answer in answers.items():
        clean_id = str(question_id or "").strip()
        clean_answer = str(raw_answer or "").strip().upper()
        if len(clean_id) > 32 or len(clean_answer) > 16:
            continue
        if clean_answer.startswith("OPTION "):
            clean_answer = clean_answer[7:].strip()
        if clean_answer in {"A", "B", "C", "D", "E", "F", "G", "H"}:
            cleaned[clean_id] = clean_answer
    return cleaned


def _feedback(percent: int) -> tuple[str, str]:
    if percent >= 80:
        return (
            "Strong exam skills",
            "Brilliant focus! Review the few tricky questions, then try another timed mock.",
        )
    if percent >= 60:
        return (
            "Good progress",
            "You are building strong skills. Practise the topics below and try again soon.",
        )
    return (
        "Keep growing",
        "A mock is for learning, not judging. Take a break, practise one topic, and come back.",
    )



def _save_mock_exam_mistakes(student_id: str, exam: Mapping[str, Any], results: list[Dict[str, Any]]) -> int:
    """Persist wrong/unanswered mock questions in the student's 11+ mistake bank."""
    clean_student = str(student_id or '').strip()
    if not clean_student or clean_student in {'anonymous', 'None'} or clean_student.startswith('anon_'):
        return 0
    mistakes = []
    for row in results:
        if bool(row.get('correct')):
            continue
        mistakes.append({
            'question': row.get('question'),
            'subject': row.get('subject') or '11+',
            'topic': row.get('topic') or 'General',
            'mistake_type': row.get('topic') or 'Mock exam mistake',
            'source_type': 'mock_exam',
            'source_doc_id': str(exam.get('id') or '')[:120] or None,
            'options': row.get('options') or [],
            'correct_letter': row.get('correct_answer'),
            'correct_answer': row.get('correct_answer_text') or row.get('correct_answer'),
            'explanation': row.get('explanation') or '',
        })
    if not mistakes:
        return 0
    try:
        from src.progress_db import save_mistake_questions
        return int(save_mistake_questions(clean_student, mistakes))
    except Exception:
        return 0


def score_mock_exam(
    exam_id: str,
    token: str,
    identity: str,
    answers: Mapping[str, Any],
    *,
    now: int | None = None,
) -> Dict[str, Any]:
    """Verify and locally mark a mock attempt."""
    exam = _exam(exam_id)
    payload = _read_payload(token)
    checked_at = int(now if now is not None else time.time())
    if payload.get("exam_id") != exam["id"]:
        raise InvalidAttempt("This attempt belongs to a different mock exam.")
    if not hmac.compare_digest(str(payload.get("owner") or ""), owner_key(str(identity))):
        raise InvalidAttempt("This attempt belongs to a different learner session.")
    if checked_at > int(payload.get("submit_by") or 0):
        raise ExpiredAttempt("This attempt has closed. Please start a fresh mock.")

    cleaned_answers = _normalise_answers(answers)
    results = []
    subject_totals: Counter[str] = Counter()
    subject_correct: Counter[str] = Counter()
    missed_topics: Counter[str] = Counter()
    correct_count = 0
    answered_count = 0

    for number, question_id in enumerate(exam["question_ids"], start=1):
        question = _QUESTION_BY_ID[question_id]
        selected = cleaned_answers.get(question_id)
        is_correct = selected == question["answer"]
        subject_totals[question["subject"]] += 1
        if selected:
            answered_count += 1
        if is_correct:
            correct_count += 1
            subject_correct[question["subject"]] += 1
        else:
            missed_topics[question["topic"]] += 1
        correct_option = next(
            option for option in question["options"] if option["label"] == question["answer"]
        )
        results.append({
            "id": question_id,
            "number": number,
            "subject": question["subject"],
            "topic": question["topic"],
            # Mock content uses ``prompt`` as its canonical question field.
            # Retain the old key as a compatibility fallback so incorrect
            # answers are saved with usable question text for later practice.
            "question": question.get("prompt") or question.get("question", ""),
            "options": question.get("options", []),
            "selected_answer": selected,
            "correct": is_correct,
            "correct_answer": question["answer"],
            "correct_answer_text": correct_option["text"],
            "explanation": question["explanation"],
        })

    mistakes_saved = _save_mock_exam_mistakes(identity, exam, results)

    total = len(exam["question_ids"])
    percent = round((correct_count / total) * 100) if total else 0
    band, message = _feedback(percent)
    breakdown = []
    for subject, subject_total in subject_totals.items():
        subject_score = subject_correct[subject]
        breakdown.append({
            "subject": subject,
            "correct": subject_score,
            "total": subject_total,
            "percent": round((subject_score / subject_total) * 100),
        })
    try:
        from src.progress_db import save_mock_exam_attempt
        save_mock_exam_attempt(
            str(payload.get("nonce") or ""),
            exam["id"],
            str(identity),
            correct_count,
            total,
            breakdown,
            datetime.fromtimestamp(int(payload["issued_at"]), tz=UTC),
            datetime.fromtimestamp(checked_at, tz=UTC),
            allow_anonymous=(exam["id"] == FREE_MOCK_EXAM_ID),
        )
    except Exception:
        # Statistics must never prevent a pupil from receiving their result.
        pass
    return {
        "success": True,
        "exam": {
            "id": exam["id"],
            "title": exam["title"],
            "category": exam["category"],
            "school": exam["school"],
        },
        "score": {
            "correct": correct_count,
            "total": total,
            "answered": answered_count,
            "unanswered": total - answered_count,
            "percent": percent,
            "band": band,
            "message": message,
        },
        "timing": {
            "started_at": int(payload["issued_at"]),
            "deadline": int(payload["deadline"]),
            "submitted_at": checked_at,
            "timed_out": checked_at > int(payload["deadline"]),
        },
        "subject_breakdown": breakdown,
        "recommended_topics": [
            topic for topic, _count in missed_topics.most_common(4)
        ],
        "questions": results,
        "mistakes_saved": mistakes_saved,
        "disclaimer": (
            "This practice score is not a predicted standardised score or an admissions result."
        ),
    }


def validate_mock_exam_content() -> None:
    """Fail fast during tests if an exam leaks, duplicates or references bad data."""
    free_exam_ids = {
        exam_id for exam_id, exam in EXAMS.items() if bool(exam.get("is_free"))
    }
    if free_exam_ids != {FREE_MOCK_EXAM_ID}:
        raise ValueError(
            "Only the Common 11+ Diagnostic may be marked as a free mock exam"
        )
    if EXAMS[FREE_MOCK_EXAM_ID]["title"] != "Common 11+ Diagnostic":
        raise ValueError("The free mock must be the Common 11+ Diagnostic")
    seen_question_sets: Dict[frozenset[str], str] = {}
    for exam_id, exam in EXAMS.items():
        if exam.get("id") != exam_id:
            raise ValueError(f"{exam_id} has a mismatched exam identifier")
        question_ids = tuple(exam["question_ids"])
        if not question_ids or len(question_ids) != len(set(question_ids)):
            raise ValueError(f"{exam_id} contains duplicate or missing questions")
        question_set = frozenset(question_ids)
        duplicate_exam_id = seen_question_sets.get(question_set)
        if duplicate_exam_id:
            raise ValueError(
                f"{exam_id} repeats the question set from {duplicate_exam_id}"
            )
        seen_question_sets[question_set] = exam_id
        unknown = [item for item in question_ids if item not in _QUESTION_BY_ID]
        if unknown:
            raise ValueError(f"{exam_id} references unknown questions: {unknown}")
        if int(exam["duration_minutes"]) < 5:
            raise ValueError(f"{exam_id} has an invalid duration")
        for source_id in exam["source_ids"]:
            if source_id not in PUBLIC_SOURCES:
                raise ValueError(f"{exam_id} references an unknown source")
            if not PUBLIC_SOURCES[source_id]["url"].startswith("https://"):
                raise ValueError(f"{exam_id} references a non-HTTPS source")
    for question in _QUESTIONS:
        # Capitalisation can be the tested distinction in English questions,
        # so only reject byte-for-byte duplicate visible choices here.
        option_texts = [str(option["text"]).strip() for option in question["options"]]
        if len(option_texts) != len(set(option_texts)):
            raise ValueError(f'{question["id"]} contains duplicate answer options')


validate_mock_exam_content()
