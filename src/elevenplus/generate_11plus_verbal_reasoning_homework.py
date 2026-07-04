#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ (Eleven Plus) Verbal Reasoning Practice Generator
=======================================================

Generates ORIGINAL 11+-style Verbal Reasoning (VR) practice questions and
stores them in the RAG store, mirroring the structure of
generate_11plus_math_homework.py and generate_11plus_english_homework.py.

Why this doesn't scrape/copy real past papers
----------------------------------------------
Actual 11+ VR past papers (GL Assessment, CEM/CSSE, Bond, CGP, and
individual grammar schools' specimen papers) are copyrighted. This script
does NOT reproduce or paraphrase any of that content. Instead it generates
brand-new letter/number puzzles, word pairs, and codes, but shapes the
question TYPES to match the *publicly documented* list of Verbal Reasoning
question formats used by GL Assessment — the exam board most top-ranking
grammar schools actually use for their 11+.

  GL Assessment publicly documents that its Verbal Reasoning component
  draws from a bank of 21 named question types (e.g. letter series, word
  analogies/related pairs, closest-in-meaning, opposites, compound words,
  hidden words, codes, "odd one out", inserting a letter that completes
  two words, number series/puzzles). Unlike English, GL does not publish
  an exact frequency split for these 21 types, so this generator spreads
  its batch roughly evenly across the ten representative type-families
  implemented below, rather than assuming a weighting that isn't publicly
  documented.

Sources for the above structural facts (the existence and general nature
of the 21 question types) are public exam-board / tutoring-company
explainer pages, not exam content itself — no verbatim question, word
pair, code, or answer key from any real paper is used anywhere in this
file. All letter/number puzzles, word banks and codes below were written
fresh for this script.

Usage mirrors the other 11+ generators: run this script directly to check
whether 11+ Verbal Reasoning homework already exists in the RAG store, and
if not, generate a batch and add it.
"""
import sys
import os
import random
import string

# 添加项目根目录到路径 (same pattern as the other 11+ generators)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Topic list. GL does not publish a frequency split across its 21 VR
# question types the way it does for English, so weights are kept roughly
# equal across the ten representative type-families implemented here.
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
YEAR_GROUP = 6  # 11+ is sat at the start of Year 6 (some in Year 5)

ALPHABET = string.ascii_uppercase


# ---------------------------------------------------------------------------
# Word banks (all general-knowledge word relationships, written fresh for
# this script — not sourced from any exam or wordlist).
# ---------------------------------------------------------------------------
SYNONYM_ANTONYM_BANK = [
    {"word": "happy", "synonym": "cheerful", "antonym": "sad"},
    {"word": "quick", "synonym": "fast", "antonym": "slow"},
    {"word": "large", "synonym": "big", "antonym": "small"},
    {"word": "brave", "synonym": "courageous", "antonym": "cowardly"},
    {"word": "quiet", "synonym": "silent", "antonym": "noisy"},
    {"word": "bright", "synonym": "vivid", "antonym": "dull"},
    {"word": "ancient", "synonym": "old", "antonym": "modern"},
    {"word": "generous", "synonym": "giving", "antonym": "selfish"},
    {"word": "difficult", "synonym": "hard", "antonym": "easy"},
    {"word": "polite", "synonym": "courteous", "antonym": "rude"},
    {"word": "wealthy", "synonym": "rich", "antonym": "poor"},
    {"word": "honest", "synonym": "truthful", "antonym": "dishonest"},
    {"word": "flexible", "synonym": "adaptable", "antonym": "rigid"},
    {"word": "cautious", "synonym": "careful", "antonym": "reckless"},
    {"word": "gigantic", "synonym": "huge", "antonym": "tiny"},
    {"word": "gloomy", "synonym": "dismal", "antonym": "cheerful"},
    {"word": "fragile", "synonym": "delicate", "antonym": "sturdy"},
    {"word": "genuine", "synonym": "authentic", "antonym": "fake"},
    {"word": "vacant", "synonym": "empty", "antonym": "occupied"},
    {"word": "permit", "synonym": "allow", "antonym": "forbid"},
]

# Analogy pairs grouped by relationship type, so an analogy question always
# compares two pairs that share the SAME relationship.
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

# Curated hidden-word pairs: `word1` and `word2` are both real dictionary
# words, and `hidden` is a real word that appears in the string formed by
# joining word1+word2. Each has been checked (see the smoke test) to be a
# genuine substring match.
HIDDEN_WORD_BANK = [
    ("scar", "pet", "carpet"),
    ("grown", "erratic", "owner"),
    ("guitar", "enable", "arena"),
    ("chair", "mango", "airman"),
    ("lion", "essence", "ones"),
    ("drag", "online", "dragon"),
    ("pea", "cockpit", "peacock"),
]

# Curated "insert a letter to complete both words" triples:
# left_fragment + letter = a real word, letter + right_fragment = a real word.
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

# Compound-word "bridge" triples: (left, middle, right) where left+middle
# and middle+right are both real compound words.
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
# MCQ helper (same approach as the maths/English generators: 5 options, A-E)
# ---------------------------------------------------------------------------
def _format_mcq(question_num: int, question_text: str, correct, distractors):
    """Return (question_block_text, correct_letter) for a 5-option MCQ."""
    options = list(distractors) + [correct]
    random.shuffle(options)
    letters = ["A", "B", "C", "D", "E"]
    correct_letter = letters[options.index(correct)]
    lines = [f"{question_num}. {question_text}"]
    for letter, opt in zip(letters, options):
        lines.append(f"   {letter}) {opt}")
    return "\n".join(lines), correct_letter


def _random_letter_distractors(correct: str, count: int = 4) -> list:
    """Random single-letter distractors, distinct from the correct letter."""
    pool = [c for c in ALPHABET if c != correct]
    return random.sample(pool, count)


# ---------------------------------------------------------------------------
# Topic generators — each returns (content_str, correct_answers_list)
# ---------------------------------------------------------------------------
def _gen_letter_series(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["simple_step", "alternating_step", "skip_pattern"])
        start = random.randint(0, 20)
        if kind == "simple_step":
            step = random.choice([1, 2, 3, -1, -2])
            positions = [(start + step * k) % 26 for k in range(5)]
            next_pos = (start + step * 5) % 26
        elif kind == "alternating_step":
            step_a, step_b = random.sample([1, 2, 3, 4], 2)
            positions = [start]
            steps = [step_a, step_b]
            for k in range(4):
                positions.append((positions[-1] + steps[k % 2]) % 26)
            next_pos = (positions[-1] + steps[4 % 2]) % 26
        else:
            step = random.choice([2, 3, 4])
            positions = [(start + step * k) % 26 for k in range(0, 10, 2)][:5]
            next_pos = (positions[-1] + step) % 26

        letters = [ALPHABET[p] for p in positions]
        correct = ALPHABET[next_pos]
        distractors = _random_letter_distractors(correct)
        text = f"What letter comes next in the sequence: {', '.join(letters)}, ?"
        block, letter = _format_mcq(i, text, correct, distractors)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_number_series(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["arithmetic", "geometric", "alternating", "fibonacci_like"])
        if kind == "arithmetic":
            start = random.randint(1, 20)
            step = random.randint(2, 10)
            terms = [start + step * k for k in range(5)]
            correct = start + step * 5
        elif kind == "geometric":
            start = random.choice([1, 2, 3])
            ratio = random.choice([2, 3])
            terms = [start * (ratio ** k) for k in range(4)]
            correct = start * (ratio ** 4)
        elif kind == "alternating":
            start = random.randint(1, 15)
            step_a, step_b = random.randint(2, 6), random.randint(2, 6)
            terms = [start]
            steps = [step_a, -step_b]
            for k in range(4):
                terms.append(terms[-1] + steps[k % 2])
            correct = terms[-1] + steps[4 % 2]
        else:
            a, b = random.randint(1, 5), random.randint(1, 5)
            terms = [a, b]
            for _ in range(3):
                terms.append(terms[-1] + terms[-2])
            correct = terms[-1] + terms[-2]

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
        block, letter = _format_mcq(i, text, correct, list(distractors)[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_word_analogies(index: int) -> tuple:
    blocks, answers = [], []
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
        # add a plausible near-miss: w2 itself as a distractor
        distractor_words.append(w2)
        distractor_words = list(dict.fromkeys([d for d in distractor_words if d != correct]))[:4]
        while len(distractor_words) < 4:
            extra_group = random.choice(list(ANALOGY_GROUPS.values()))
            candidate = random.choice(extra_group)[1]
            if candidate != correct and candidate not in distractor_words:
                distractor_words.append(candidate)

        text = f"{w1.upper()} is to {w2.upper()} as {w3.upper()} is to ?"
        block, letter = _format_mcq(i, text, correct, distractor_words[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_synonyms(index: int) -> tuple:
    blocks, answers = [], []
    entries = random.sample(SYNONYM_ANTONYM_BANK, min(10, len(SYNONYM_ANTONYM_BANK)))
    while len(entries) < 10:
        entries.append(random.choice(SYNONYM_ANTONYM_BANK))
    for i, entry in enumerate(entries, start=1):
        target = entry["word"]
        correct = entry["synonym"]
        pool = [e for e in SYNONYM_ANTONYM_BANK if e["word"] != target]
        distractor_entries = random.sample(pool, min(4, len(pool)))
        distractors = [e["antonym"] for e in distractor_entries]
        distractors = [d for d in distractors if d != correct][:4]
        while len(distractors) < 4:
            extra = random.choice(pool)
            if extra["antonym"] not in distractors and extra["antonym"] != correct:
                distractors.append(extra["antonym"])
        text = f"Which word means most nearly the SAME as '{target}'?"
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_antonyms(index: int) -> tuple:
    blocks, answers = [], []
    entries = random.sample(SYNONYM_ANTONYM_BANK, min(10, len(SYNONYM_ANTONYM_BANK)))
    while len(entries) < 10:
        entries.append(random.choice(SYNONYM_ANTONYM_BANK))
    for i, entry in enumerate(entries, start=1):
        target = entry["word"]
        correct = entry["antonym"]
        pool = [e for e in SYNONYM_ANTONYM_BANK if e["word"] != target]
        distractor_entries = random.sample(pool, min(4, len(pool)))
        distractors = [e["synonym"] for e in distractor_entries]
        distractors = [d for d in distractors if d != correct][:4]
        while len(distractors) < 4:
            extra = random.choice(pool)
            if extra["synonym"] not in distractors and extra["synonym"] != correct:
                distractors.append(extra["synonym"])
        text = f"Which word means most nearly the OPPOSITE of '{target}'?"
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_compound_words(index: int) -> tuple:
    blocks, answers = [], []
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
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_hidden_words(index: int) -> tuple:
    blocks, answers = [], []
    pairs = random.sample(HIDDEN_WORD_BANK, min(10, len(HIDDEN_WORD_BANK)))
    while len(pairs) < 10:
        pairs.append(random.choice(HIDDEN_WORD_BANK))
    all_hidden = [h for (_, _, h) in HIDDEN_WORD_BANK]
    for i, (word1, word2, hidden) in enumerate(pairs, start=1):
        assert hidden in (word1 + word2)  # guard: hidden word must genuinely appear
        others = [h for h in all_hidden if h != hidden]
        distractors = random.sample(others, min(4, len(others)))
        while len(distractors) < 4:
            distractors.append(random.choice(others))
        text = (f"A word is hidden where these two words meet. What is it?\n"
                 f"   {word1.upper()}   {word2.upper()}")
        block, letter = _format_mcq(i, text, hidden, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_letter_codes(index: int) -> tuple:
    blocks, answers = [], []
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
        block, letter = _format_mcq(i, text, correct, list(distractors)[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_odd_one_out(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        category, other_category = random.sample(list(ODD_ONE_OUT_CATEGORIES.keys()), 2)
        same_group_words = random.sample(ODD_ONE_OUT_CATEGORIES[category], 4)
        odd_word = random.choice(ODD_ONE_OUT_CATEGORIES[other_category])
        correct = odd_word
        text = "Which word does NOT belong with the others?"
        block, letter = _format_mcq(i, text, correct, same_group_words)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_insert_letter(index: int) -> tuple:
    blocks, answers = [], []
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
        block, letter_choice = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter_choice)
    return "\n\n".join(blocks), answers


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


def generate_11plus_vr(topic: str, index: int) -> tuple:
    """Generate one 11+ Verbal Reasoning worksheet (MCQ) for a given topic."""
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ Verbal Reasoning topic: {topic}")
    body, correct_answers = generator(index)
    header = (
        f"11+ Verbal Reasoning Practice (GL Assessment style) - {topic} (Set {index})\n"
        f"Answer each question by choosing the correct option A-E.\n\n"
    )
    return header + body, correct_answers


# ---------------------------------------------------------------------------
# Batch generation / RAG store integration (mirrors the other 11+ generators)
# ---------------------------------------------------------------------------
def _weighted_topic_sequence(count: int) -> list:
    """Build an ordered topic list of length `count`. Weights are roughly
    equal across the ten VR type-families, since GL does not publish an
    official frequency split for its 21 VR question types."""
    topics, weights = zip(*ELEVEN_PLUS_VR_TOPICS)
    return random.choices(topics, weights=weights, k=count)


def check_11plus_vr_exists() -> bool:
    """检查是否已有 11+ 言语推理练习"""
    store = get_elevenplus_rag_store()
    results = store.search(query="verbal reasoning", k=1, filters={"subject": "VerbalReasoning"})
    return len(results) > 0


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

    for i, topic in enumerate(topic_sequence, start=1):
        content, correct_answers = generate_11plus_vr(topic, i)

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "VerbalReasoning",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "question_format": "multiple_choice_5_options",
            "student_id": None,
            "correct_answers": ", ".join(correct_answers),
        }
        doc_id = f"elevenplus_vr_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份 11+ 言语推理作业")

    return batch_data


def main():
    """主函数：检查 11+ Verbal Reasoning 练习是否存在，缺失则生成"""
    print("检查 11+ Verbal Reasoning 练习是否存在...\n")

    store = get_elevenplus_rag_store()
    exists = check_11plus_vr_exists()
    status = "已有" if exists else "缺失"
    print(f"  11+ Verbal Reasoning: {status}")

    if exists:
        print("\n11+ Verbal Reasoning 练习已存在，无需生成。")
        return

    print("\n开始生成 11+ Verbal Reasoning 练习 (GL Assessment 风格, MCQ, 10 大主题均匀分布)...")
    batch_data = generate_11plus_vr_batch(count=300)  # 生成 300 份练习

    if batch_data:
        store.add_batch_homework(batch_data)
        print(f"成功添加 {len(batch_data)} 份 11+ Verbal Reasoning 练习到 RAG 存储")

    stats = store.get_stats()
    print("\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()