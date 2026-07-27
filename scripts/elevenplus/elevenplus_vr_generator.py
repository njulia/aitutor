#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ (Eleven Plus) Verbal Reasoning Practice Generator
=======================================================

Generates ORIGINAL 11+-style Verbal Reasoning (VR) practice questions and
stores them in the RAG store, mirroring the structure of
elevenplus_english_generator.py.

GL Assessment publicly documents that its Verbal Reasoning component
draws from a bank of 21 named question types (e.g. letter series, word
analogies/related pairs, closest-in-meaning, opposites, compound words,
hidden words, codes, "odd one out", inserting a letter that completes
two words, number series/puzzles). Unlike English, GL does not publish
an exact frequency split for these 21 types, so this generator spreads
its batch roughly evenly across the ten representative type-families
implemented below, rather than assuming a weighting that isn't publicly
documented.

Usage: Run this script directly to check whether 11+ Verbal Reasoning homework already
exists in the RAG store, and if not, generate a batch of 300 sets and add it.
"""

import sys
import os
import json
import string

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.elevenplus_rag import get_elevenplus_rag_store, count_homework_by_metadata
from scripts.homework_generator.homework_generator_utils import add_homework_in_batches, get_rag_stats
from scripts.elevenplus.elevenplus_generator_utils import (
    balanced_weighted_sequence,
    build_multiple_choice_question,
    current_difficulty,
    difficulty_for_batch_position,
    ensure_unique_question_stems,
    generate_unique_question_set,
    homework_set_fingerprint,
    normalise_difficulty,
    render_student_question_set,
    seeded_random as random,
    validate_answer_records,
    validate_homework_batch,
)


os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Topic list + weights (kept equal across the ten representative type-families)
# ---------------------------------------------------------------------------
ELEVEN_PLUS_VR_TOPICS = [
    ("Letter Series", 1),
    ("Number Series", 1),
    ("Word Analogies (Related Pairs)", 1),
    ("Closest in Meaning (Synonyms)", 1),
    ("Opposites (Antonyms)", 1),
    ("Compound Words", 1),
    ("Hidden Words", 1),
    ("Letter Codes", 1),
    ("Odd One Out", 1),
    ("Insert a Letter (Completes Both Words)", 1),
]

EXAM_STYLE = "GL Assessment"
HOMEWORK_MINUTES = "45-50"
KEY_STAGE = "11+"
YEAR_GROUP = 6

ALPHABET = string.ascii_uppercase

# ---------------------------------------------------------------------------
# Word banks & definitions
# ---------------------------------------------------------------------------
SYNONYM_ANTONYM_BANK = [
    {"word": "happy", "synonym": "cheerful", "antonym": "sad", "clue": "feeling or showing pleasure or contentment"},
    {"word": "quick", "synonym": "fast", "antonym": "slow", "clue": "moving or capable of moving at high speed"},
    {"word": "large", "synonym": "big", "antonym": "small", "clue": "of considerable or relatively great size, extent, or quantity"},
    {"word": "brave", "synonym": "courageous", "antonym": "cowardly", "clue": "ready to face and endure danger or pain"},
    {"word": "quiet", "synonym": "silent", "antonym": "noisy", "clue": "making little or no noise"},
    {"word": "bright", "synonym": "vivid", "antonym": "dull", "clue": "shining strongly or having striking color"},
    {"word": "ancient", "synonym": "old", "antonym": "modern", "clue": "belonging to the very distant past"},
    {"word": "generous", "synonym": "giving", "antonym": "selfish", "clue": "willing to give money, help, or time freely"},
    {"word": "difficult", "synonym": "hard", "antonym": "easy", "clue": "needing much effort or skill to accomplish or understand"},
    {"word": "polite", "synonym": "courteous", "antonym": "rude", "clue": "having or showing behavior that is respectful and considerate"},
    {"word": "wealthy", "synonym": "rich", "antonym": "poor", "clue": "having a great deal of money, resources, or assets"},
    {"word": "honest", "synonym": "truthful", "antonym": "dishonest", "clue": "free of deceit and untruthful behavior; sincere"},
    {"word": "flexible", "synonym": "adaptable", "antonym": "rigid", "clue": "able to adjust readily to different conditions"},
    {"word": "cautious", "synonym": "careful", "antonym": "reckless", "clue": "avoiding unnecessary risks or mistakes"},
    {"word": "gigantic", "synonym": "huge", "antonym": "tiny", "clue": "of very great size; colossal"},
    {"word": "gloomy", "synonym": "dismal", "antonym": "cheerful", "clue": "dark or poorly lit, or feeling depressed/sad"},
    {"word": "fragile", "synonym": "delicate", "antonym": "sturdy", "clue": "easily broken, damaged, or vulnerable"},
    {"word": "genuine", "synonym": "authentic", "antonym": "fake", "clue": "truly what something is said to be; sincere"},
    {"word": "vacant", "synonym": "empty", "antonym": "occupied", "clue": "having no fixtures, furniture, or inhabitants; unoccupied"},
    {"word": "permit", "synonym": "allow", "antonym": "forbid", "clue": "give authorization or consent to someone to do something"},
]

ANALOGY_GROUPS = {
    "opposite": [
        ("hot", "cold"), ("up", "down"), ("day", "night"), ("happy", "sad"),
        ("big", "small"), ("fast", "slow"), ("open", "closed"), ("wet", "dry"),
        ("loud", "quiet"), ("full", "empty"),
    ],
    "member_of_category": [
        ("rose", "flower"), ("oak", "tree"), ("hammer", "tool"),
        ("violin", "instrument"), ("salmon", "fish"), ("sparrow", "bird"),
        ("chair", "furniture"), ("apple", "fruit"), ("carrot", "vegetable"),
        ("saxophone", "instrument"),
    ],
    "baby_to_adult": [
        ("puppy", "dog"), ("kitten", "cat"), ("cub", "lion"), ("calf", "cow"),
        ("foal", "horse"), ("lamb", "sheep"), ("chick", "hen"),
        ("duckling", "duck"), ("fawn", "deer"), ("joey", "kangaroo"),
    ],
    "worker_to_place": [
        ("chef", "kitchen"), ("teacher", "classroom"), ("doctor", "hospital"),
        ("farmer", "field"), ("pilot", "cockpit"), ("artist", "studio"),
        ("judge", "courtroom"), ("dentist", "clinic"), ("librarian", "library"),
        ("scientist", "laboratory"),
    ],
}

ODD_ONE_OUT_CATEGORIES = {
    "fruit": ["apple", "banana", "orange", "grape", "mango", "pear"],
    "animal": ["tiger", "elephant", "zebra", "giraffe", "panda", "otter"],
    "vehicle": ["car", "bicycle", "train", "aeroplane", "lorry", "scooter"],
    "musical instrument": ["violin", "trumpet", "flute", "drum", "piano", "cello"],
    "furniture": ["table", "chair", "sofa", "wardrobe", "desk", "bookshelf"],
    "weather": ["rain", "snow", "sunshine", "fog", "hail", "wind"],
    "sport": ["football", "tennis", "cricket", "rugby", "hockey", "swimming"],
    "colour": ["scarlet", "crimson", "burgundy", "maroon", "turquoise", "azure"],
    "tool": ["hammer", "screwdriver", "spanner", "chisel", "pliers", "saw"],
    "building": ["cottage", "bungalow", "mansion", "cabin", "palace", "castle"],
}

HIDDEN_WORD_BANK = [
    ("scar", "pet", "carpet"),
    ("grown", "erratic", "owner"),
    ("guitar", "enable", "arena"),
    ("chair", "mango", "airman"),
    ("lion", "essence", "ones"),
    ("drag", "online", "dragon"),
    ("pea", "cockpit", "peacock"),
    ("some", "thing", "something"),
    ("with", "outcome", "without"),
    ("butter", "flywheel", "butterfly"),
    ("rain", "bowling", "rainbow"),
    ("book", "casework", "bookcase"),
    ("foot", "balloon", "football"),
    ("sun", "flowerpot", "sunflower"),
    ("bed", "roommate", "bedroom"),
    ("door", "bellows", "doorbell"),
    ("note", "booklet", "notebook"),
]

INSERT_LETTER_BANK = [
    ("PAR", "K", "IND"),
    ("CAR", "T", "OP"),
    ("BE", "D", "OG"),
    ("CA", "T", "EN"),
    ("HE", "N", "AP"),
    ("SU", "N", "OW"),
    ("PI", "N", "OT"),
    ("RA", "T", "EA"),
    ("MA", "T", "IN"),
    ("CO", "T", "OP"),
]

COMPOUND_BRIDGE_BANK = [
    ("FOOT", "BALL", "ROOM"),
    ("SUN", "FLOWER", "POT"),
    ("BED", "ROOM", "MATE"),
    ("RAIN", "BOW", "TIE"),
    ("CUP", "BOARD", "WALK"),
    ("DOOR", "BELL", "BOY"),
    ("FIRE", "WORK", "SHOP"),
    ("NOTE", "BOOK", "CASE"),
    ("ARM", "CHAIR", "MAN"),
    ("TOOTH", "BRUSH", "WOOD"),
]

# ---------------------------------------------------------------------------
# MCQ helpers
# ---------------------------------------------------------------------------
def _build_question(num, text, correct, distractors, explanation, tip="", difficulty="standard"):
    """Render one validated five-option question and canonical answer record."""
    effective_difficulty = current_difficulty() if normalise_difficulty(difficulty) == "standard" else difficulty
    return build_multiple_choice_question(
        num, text, correct, distractors, explanation, tip, effective_difficulty
    )

def _random_letter_distractors(correct: str, count: int = 4) -> list:
    """Random single-letter distractors, distinct from the correct letter."""
    pool = [c for c in ALPHABET if c != correct]
    return random.sample(pool, count)

# ---------------------------------------------------------------------------
# Topic generators — each returns (content_str, answer_records)
# ---------------------------------------------------------------------------
def _gen_letter_series(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["simple_step", "alternating_step", "skip_pattern"])
        start = random.randint(0, 20)
        if kind == "simple_step":
            step = random.choice([1, 2, 3, -1, -2])
            positions = [(start + step * k) % 26 for k in range(5)]
            next_pos = (start + step * 5) % 26
            desc = f"moving forward by {step} letters each time" if step > 0 else f"moving backward by {abs(step)} letters each time"
        elif kind == "alternating_step":
            step_a, step_b = random.sample([1, 2, 3, 4], 2)
            positions = [start]
            steps = [step_a, step_b]
            for k in range(4):
                positions.append((positions[-1] + steps[k % 2]) % 26)
            next_pos = (positions[-1] + steps[4 % 2]) % 26
            desc = f"alternating steps of +{step_a} and +{step_b}"
        else:
            step = random.choice([2, 3, 4])
            positions = [(start + step * k) % 26 for k in range(0, 10, 2)][:5]
            next_pos = (positions[-1] + step) % 26
            desc = f"skipping {step - 1} letters each time (step of +{step})"

        letters = [ALPHABET[p] for p in positions]
        correct = ALPHABET[next_pos]
        distractors = _random_letter_distractors(correct)
        text = f"What letter comes next in the sequence: {', '.join(letters)}, ?"
        
        explanation = (
            f"The sequence is formed by starting at '{letters[0]}' and applying a pattern of {desc}. "
            f"The positions of the letters in the alphabet are: {', '.join([f'{l}({p+1})' for l, p in zip(letters, positions)])}. "
            f"The next position is {next_pos + 1}, which corresponds to the letter '{correct}'."
        )
        tip = "Write down the alphabet A to Z at the start of your paper and number them 1 to 26 to avoid mental mistakes!"
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_number_series(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["arithmetic", "geometric", "alternating", "fibonacci_like"])
        if kind == "arithmetic":
            start = random.randint(1, 20)
            step = random.randint(2, 10)
            terms = [start + step * k for k in range(5)]
            correct = start + step * 5
            desc = f"adding {step} to each term"
            calc = f"{terms[-1]} + {step}"
        elif kind == "geometric":
            start = random.choice([1, 2, 3])
            ratio = random.choice([2, 3])
            terms = [start * (ratio ** k) for k in range(4)]
            correct = start * (ratio ** 4)
            desc = f"multiplying each term by {ratio}"
            calc = f"{terms[-1]} * {ratio}"
        elif kind == "alternating":
            start = random.randint(1, 15)
            step_a, step_b = random.randint(2, 6), random.randint(2, 6)
            terms = [start]
            steps = [step_a, -step_b]
            for k in range(4):
                terms.append(terms[-1] + steps[k % 2])
            correct = terms[-1] + steps[4 % 2]
            desc = f"alternating between adding {step_a} and subtracting {step_b}"
            op = "+" if steps[4 % 2] >= 0 else "-"
            calc = f"{terms[-1]} {op} {abs(steps[4 % 2])}"
        else:
            a, b = random.randint(1, 5), random.randint(1, 5)
            terms = [a, b]
            for _ in range(3):
                terms.append(terms[-1] + terms[-2])
            correct = terms[-1] + terms[-2]
            desc = "adding the two previous terms to find the next one (Fibonacci-like)"
            calc = f"{terms[-1]} + {terms[-2]}"

        distractors = set()
        spread = max(1, abs(correct) // 5)
        attempts = 0
        while len(distractors) < 4 and attempts < 30:
            attempts += 1
            delta = random.choice([-2, -1, 1, 2]) * random.randint(1, max(1, spread))
            candidate = correct + delta
            if candidate != correct:
                distractors.add(candidate)
        while len(distractors) < 4:
            distractors.add(correct + len(distractors) + 1)

        text = f"What number comes next in the sequence: {', '.join(map(str, terms))}, ?"
        explanation = (
            f"The sequence is formed by {desc}. The terms are: {', '.join(map(str, terms))}. "
            f"The next term is calculated as: {calc} = {correct}."
        )
        tip = "Look at the differences between adjacent numbers first. If they don't form a simple pattern, check if there are two alternating sequences!"
        block, rec = _build_question(i, text, correct, list(distractors)[:4], explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_word_analogies(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        relation = random.choice(list(ANALOGY_GROUPS.keys()))
        group = ANALOGY_GROUPS[relation]
        pair_a, pair_b = random.sample(group, 2)
        w1, w2 = pair_a
        w3, w4 = pair_b
        correct = w4

        other_relations = [r for r in ANALOGY_GROUPS if r != relation]
        distractor_words = []
        for r in random.sample(other_relations, min(3, len(other_relations))):
            distractor_words.append(random.choice(ANALOGY_GROUPS[r])[1])
        distractor_words.append(w2)
        distractor_words = list(dict.fromkeys([d for d in distractor_words if d != correct]))[:4]
        while len(distractor_words) < 4:
            extra_group = random.choice(list(ANALOGY_GROUPS.values()))
            candidate = random.choice(extra_group)[1]
            if candidate != correct and candidate not in distractor_words:
                distractor_words.append(candidate)

        text = f"{w1.upper()} is to {w2.upper()} as {w3.upper()} is to ?"
        
        rel_desc = {
            "opposite": "being opposites (antonyms)",
            "member_of_category": "being a specific member of a broader category",
            "baby_to_adult": "being the baby form and the adult form of the animal",
            "worker_to_place": "being the professional worker and their typical place of work"
        }.get(relation, "having a specific relationship")

        explanation = (
            f"The relationship between '{w1.upper()}' and '{w2.upper()}' is {rel_desc}. "
            f"Applying the same relationship to '{w3.upper()}', we find '{w4.upper()}' (since '{w3.upper()}' is related to '{w4.upper()}' in the exact same way)."
        )
        tip = "Try to formulate a short, precise sentence to describe how the first two words relate, then apply that exact sentence structure to the third word!"
        block, rec = _build_question(i, text, correct, distractor_words[:4], explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_synonyms(index: int) -> tuple:
    blocks, records = [], []
    entries = random.sample(SYNONYM_ANTONYM_BANK, min(10, len(SYNONYM_ANTONYM_BANK)))
    while len(entries) < 10:
        entries.append(random.choice(SYNONYM_ANTONYM_BANK))
    for i, entry in enumerate(entries, start=1):
        target = entry["word"]
        correct = entry["synonym"]
        clue = entry["clue"]
        pool = [e for e in SYNONYM_ANTONYM_BANK if e["word"] != target]
        distractor_entries = random.sample(pool, min(4, len(pool)))
        distractors = [e["antonym"] for e in distractor_entries]
        distractors = [d for d in distractors if d != correct][:4]
        while len(distractors) < 4:
            extra = random.choice(pool)
            if extra["antonym"] not in distractors and extra["antonym"] != correct:
                distractors.append(extra["antonym"])
        text = f"Which word means most nearly the SAME as '{target}'?"
        explanation = (
            f"The word '{target}' means: {clue}. "
            f"Among the choices, '{correct}' is the synonym with the closest definition."
        )
        tip = "If you're unsure of the word, try to recall its usage in a sentence or check if any of the other options are direct opposites that can be crossed out."
        block, rec = _build_question(i, text, correct, distractors[:4], explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_antonyms(index: int) -> tuple:
    blocks, records = [], []
    entries = random.sample(SYNONYM_ANTONYM_BANK, min(10, len(SYNONYM_ANTONYM_BANK)))
    while len(entries) < 10:
        entries.append(random.choice(SYNONYM_ANTONYM_BANK))
    for i, entry in enumerate(entries, start=1):
        target = entry["word"]
        correct = entry["antonym"]
        clue = entry["clue"]
        pool = [e for e in SYNONYM_ANTONYM_BANK if e["word"] != target]
        distractor_entries = random.sample(pool, min(4, len(pool)))
        distractors = [e["synonym"] for e in distractor_entries]
        distractors = [d for d in distractors if d != correct][:4]
        while len(distractors) < 4:
            extra = random.choice(pool)
            if extra["synonym"] not in distractors and extra["synonym"] != correct:
                distractors.append(extra["synonym"])
        text = f"Which word means most nearly the OPPOSITE of '{target}'?"
        explanation = (
            f"The word '{target}' means: {clue}. "
            f"The word with the opposite meaning (antonym) is '{correct}'."
        )
        tip = "Make sure you do not accidentally pick a synonym! Take a breath and double-check if your chosen option is the opposite."
        block, rec = _build_question(i, text, correct, distractors[:4], explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_compound_words(index: int) -> tuple:
    blocks, records = [], []
    triples = random.sample(COMPOUND_BRIDGE_BANK, min(10, len(COMPOUND_BRIDGE_BANK)))
    while len(triples) < 10:
        triples.append(random.choice(COMPOUND_BRIDGE_BANK))
    for i, (left, middle, right) in enumerate(triples, start=1):
        correct = middle
        other_middles = [m for (_, m, _) in COMPOUND_BRIDGE_BANK if m != middle]
        distractors = random.sample(other_middles, min(4, len(other_middles)))
        while len(distractors) < 4:
            distractors.append(random.choice(other_middles))
        text = f"Which word completes a compound word with both '{left}' and '{right}'?\n   {left} (_____) {right}"
        explanation = (
            f"The word '{correct}' can be joined to both '{left}' and '{right}' to form two valid compound words: "
            f"'{left}{correct}' (e.g., {left.capitalize()}{correct.lower()}) and '{correct}{right}' (e.g., {correct.capitalize()}{right.lower()})."
        )
        tip = "Say each combination out loud in your head. Real compound words will sound familiar and natural, while incorrect ones will sound odd."
        block, rec = _build_question(i, text, correct, distractors[:4], explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_hidden_words(index: int) -> tuple:
    blocks, records = [], []
    pairs = random.sample(HIDDEN_WORD_BANK, min(10, len(HIDDEN_WORD_BANK)))
    while len(pairs) < 10:
        pairs.append(random.choice(HIDDEN_WORD_BANK))
    all_hidden = [h for (_, _, h) in HIDDEN_WORD_BANK]
    for i, (word1, word2, hidden) in enumerate(pairs, start=1):
        joined = word1.upper() + word2.upper()
        idx_pos = joined.find(hidden.upper())
        others = [h for h in all_hidden if h != hidden]
        distractors = random.sample(others, min(4, len(others)))
        while len(distractors) < 4:
            distractors.append(random.choice(others))
        text = (f"A word is hidden where these two words meet. What is it?\n"
                 f"   {word1.upper()}   {word2.upper()}")
        explanation = (
            f"If we join '{word1.upper()}' and '{word2.upper()}' to form '{joined}', "
            f"the hidden word '{hidden.upper()}' is spelled out consecutively across the junction: "
            f"{joined[:idx_pos]}[{hidden.upper()}]{joined[idx_pos + len(hidden):]}."
        )
        tip = "Run your pencil or finger slowly across the boundary of the two words. The hidden word almost always starts in the first word and ends in the second!"
        block, rec = _build_question(i, text, hidden, distractors[:4], explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_letter_codes(index: int) -> tuple:
    blocks, records = [], []
    sample_words = ["CAT", "DOG", "SUN", "BAT", "HAT", "PEN", "BOX", "CUP", "MAP", "TOP", "BIN", "JAM"]
    for i in range(1, 11):
        shift = random.choice([1, 2, 3, -1, -2])
        example_word = random.choice(sample_words)
        target_word = random.choice([w for w in sample_words if w != example_word])

        def encode(word, s):
            return "".join(ALPHABET[(ALPHABET.index(ch) + s) % 26] for ch in word)

        example_code = encode(example_word, shift)
        correct = encode(target_word, shift)

        distractors = set()
        wrong_shifts = [s for s in [1, 2, 3, -1, -2, -3] if s != shift]
        for s in random.sample(wrong_shifts, min(4, len(wrong_shifts))):
            candidate = encode(target_word, s)
            if candidate != correct:
                distractors.add(candidate)
        while len(distractors) < 4:
            distractors.add(encode(target_word, random.choice(wrong_shifts)))

        text = (f"In a code, {example_word} is written as {example_code}. "
                f"Using the same code, how is {target_word} written?")
        
        shift_desc = f"+{shift}" if shift > 0 else f"{shift}"
        ex_steps = []
        for ch, code_ch in zip(example_word, example_code):
            ex_steps.append(f"{ch} -> {code_ch} ({shift_desc})")
        
        explanation = (
            f"To decode the cipher, find the shift for each letter: "
            f"{', '.join(ex_steps)}. "
            f"Applying the same shift of {shift_desc} to '{target_word}' gives: "
            f"{' -> '.join([target_word, correct])}."
        )
        tip = "Solve letter by letter. Find the code for the first letter, search the multiple-choice options to eliminate wrong choices, and save precious time!"
        block, rec = _build_question(i, text, correct, list(distractors)[:4], explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_odd_one_out(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        category, other_category = random.sample(list(ODD_ONE_OUT_CATEGORIES.keys()), 2)
        same_group_words = random.sample(ODD_ONE_OUT_CATEGORIES[category], 4)
        odd_word = random.choice(ODD_ONE_OUT_CATEGORIES[other_category])
        correct = odd_word
        text = "Which word does NOT belong with the others?"
        explanation = (
            f"The words '{', '.join(same_group_words)}' all belong to the category of '{category}'. "
            f"In contrast, '{odd_word}' belongs to '{other_category}', making it the odd one out."
        )
        tip = "Try to name the category that four of the words share. The one that cannot fit that specific category is your correct answer."
        block, rec = _build_question(i, text, correct, same_group_words, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_insert_letter(index: int) -> tuple:
    blocks, records = [], []
    triples = random.sample(INSERT_LETTER_BANK, min(10, len(INSERT_LETTER_BANK)))
    while len(triples) < 10:
        triples.append(random.choice(INSERT_LETTER_BANK))
    all_letters = [letter for (_, letter, _) in INSERT_LETTER_BANK]
    for i, (left, letter, right) in enumerate(triples, start=1):
        correct = letter
        pool = [l for l in all_letters if l != letter] or _random_letter_distractors(letter, 6)
        distractors = list(dict.fromkeys(pool))[:4]
        while len(distractors) < 4:
            extra = random.choice(ALPHABET)
            if extra != correct and extra not in distractors:
                distractors.append(extra)
        text = (f"Which letter completes the word before the brackets AND starts "
                f"the word after the brackets?\n   {left}(_){right}")
        explanation = (
            f"Inserting the letter '{correct}' forms '{left}{correct}' (a real word) "
            f"and '{correct}{right}' (also a real word)."
        )
        tip = "Try vowels first (A, E, I, O, U) as they are the most common letters bridging word fragments, then try common consonants!"
        block, letter_choice = _build_question(i, text, correct, distractors[:4], explanation, tip)
        blocks.append(block)
        records.append(letter_choice)
    return "\n\n".join(blocks), records

TOPIC_GENERATORS = {
    "Letter Series": _gen_letter_series,
    "Number Series": _gen_number_series,
    "Word Analogies (Related Pairs)": _gen_word_analogies,
    "Closest in Meaning (Synonyms)": _gen_synonyms,
    "Opposites (Antonyms)": _gen_antonyms,
    "Compound Words": _gen_compound_words,
    "Hidden Words": _gen_hidden_words,
    "Letter Codes": _gen_letter_codes,
    "Odd One Out": _gen_odd_one_out,
    "Insert a Letter (Completes Both Words)": _gen_insert_letter,
}

def _generate_11plus_vr_homework(
    topic: str,
    index: int,
    difficulty: str,
    *,
    variant: int,
) -> tuple:
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ Verbal Reasoning topic: {topic}")
    difficulty_name, _body, answer_records = generate_unique_question_set(
        generator,
        subject="verbal_reasoning",
        topic=topic,
        set_index=index,
        difficulty=difficulty,
        variant=variant,
    )
    for record in answer_records:
        record["difficulty"] = difficulty_name
        record["topic"] = topic
    answer_records = ensure_unique_question_stems(answer_records)
    validate_answer_records(answer_records)
    body = render_student_question_set(answer_records)
    header = (
        f"11+ Verbal Reasoning Practice (GL-style familiarisation) - {topic} (Set {index})\n"
        f"Difficulty: {difficulty_name.title()} | Choose one option A-E for each question.\n"
        f"Suggested pace: {answer_records[0]['time_target_seconds']} seconds per question.\n\n"
    )
    return header + body, answer_records


def generate_11plus_vr_homework(topic: str, index: int, difficulty: str = "standard") -> tuple:
    """Generate one original Verbal Reasoning worksheet with 10 locally markable MCQs.

    ``difficulty`` is optional, so existing generation and review callers remain compatible.
    """
    return _generate_11plus_vr_homework(
        topic,
        index,
        difficulty,
        variant=0,
    )


def _weighted_topic_sequence(count: int) -> list:
    """Build a deterministic near-exact topic distribution for the library."""
    sequence = balanced_weighted_sequence(ELEVEN_PLUS_VR_TOPICS, count, seed="verbal_reasoning")
    return sequence

def check_11plus_vr_exists() -> bool:
    """Check exact metadata without paying for a query embedding."""
    try:
        return count_homework_by_metadata(YEAR_GROUP, "VerbalReasoning") > 0
    except Exception:
        return False

def clean_11plus_vr() -> int:
    """清理所有已有的 11+ 言语推理练习"""
    store = get_elevenplus_rag_store()
    results = store.search_by_metadata({"subject": "VerbalReasoning"})

    if not results:
        print("  没有找到需要清理的 11+ 言语推理作业")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  已清理 {deleted} 份 11+ 言语推理作业")
    return deleted

def generate_11plus_vr_batch(count: int = 300) -> list:
    """生成指定数量的 11+ 言语推理练习，主题在 10 个类别间大致均匀分布"""
    topic_sequence = _weighted_topic_sequence(count)
    batch_data = []
    seen_sets = set()

    for i, topic in enumerate(topic_sequence, start=1):
        difficulty = difficulty_for_batch_position(i, count)
        for variant in range(50):
            content, answer_records = _generate_11plus_vr_homework(
                topic,
                i,
                difficulty,
                variant=variant,
            )
            signature = homework_set_fingerprint(answer_records)
            if signature not in seen_sets:
                seen_sets.add(signature)
                break
        else:
            raise ValueError(f"Could not create a distinct Verbal Reasoning set {i}")

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "VerbalReasoning",
            "content_type": "practice",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "question_format": "multiple_choice_5_options",
            "question_count": 10,
            "difficulty": difficulty,
            "answer_schema_version": 2,
            "generator_version": "2026.07",
            "correct_answers": json.dumps(answer_records, ensure_ascii=False),
        }
        doc_id = f"elevenplus_vr_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份 11+ 言语推理作业")

    validate_homework_batch(batch_data)
    return batch_data

def main():
    """主函数：检查 11+ Verbal Reasoning 练习是否存在，缺失则生成"""
    print("==========================================================")
    print("   11+ Verbal Reasoning Practice Homework Generator       ")
    print("==========================================================\n")

    store = get_elevenplus_rag_store()
    print(f"RAG target: {store.store.database_target}")

    exists = check_11plus_vr_exists()
    status = "已有" if exists else "缺失"
    print(f"  11+ Verbal Reasoning: {status}")

    if exists:
        print("\n11+ Verbal Reasoning 练习已存在，无需生成。")
        return

    print("\n开始生成 11+ Verbal Reasoning 练习 (GL Assessment 风格, MCQ, 10 大主题均匀分布)...")
    batch_data = generate_11plus_vr_batch(count=300)  # 生成 300 份练习

    if batch_data:
        add_homework_in_batches(store, batch_data)
        print(f"成功添加 {len(batch_data)} 份 11+ Verbal Reasoning 练习到 RAG 存储")

    get_rag_stats(store)


if __name__ == "__main__":
    main()
