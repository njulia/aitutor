#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ (Eleven Plus) Non-Verbal Reasoning Practice Generator
============================================================

Generates ORIGINAL 11+-style Non-Verbal Reasoning (NVR) practice questions
and stores them in the RAG store, mirroring the structure of
generate_11plus_math_homework.py, generate_11plus_english_homework.py and
generate_11plus_vr_homework.py.

IMPORTANT: how shapes are represented
--------------------------------------
Real NVR papers use hand-drawn diagrams (rotated shapes, shaded matrices,
etc.). This script cannot generate image files, and it must not scrape or
reproduce any real exam's artwork. Instead, every "shape" here is built
from two standard, universally-rendering symbol sets:

  - Colour-block emoji for shape + colour (e.g. 🔴 red circle, 🟩 green
    square) — these display as real, distinguishable coloured shapes in
    any modern browser/app, unlike plain black-and-white unicode glyphs.
  - Compass-direction arrows (⬆️ ↗️ ➡️ ↘️ ⬇️ ↙️ ⬅️ ↖️) as a stand-in for
    rotation/orientation, since 8 evenly-spaced directions behave exactly
    like a rotating shape for reasoning purposes.

This lets every question type below be a genuine, self-contained visual
reasoning puzzle (series, matrices, codes, analogies, odd-one-out,
grouping, counting, reflection) without needing any drawn diagram, and
without copying anything from a real paper. Question TYPES are chosen to
match what's publicly documented as standard 11+ NVR content (used by GL
Assessment and similar boards): shape series, matrices, analogies, codes,
odd-one-out, similarity grouping, and reflection/rotation. As with the
Verbal Reasoning generator, no official per-type frequency split is
publicly documented for NVR, so topics are weighted roughly evenly.

Usage mirrors the other 11+ generators: run this script directly to check
whether 11+ Non-Verbal Reasoning homework already exists in the RAG store,
and if not, generate a batch and add it.
"""
import sys
import os
import random

# 添加项目根目录到路径 (same pattern as the other 11+ generators)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Topic list. No official frequency split is publicly documented for NVR
# question types (same caveat as the Verbal Reasoning generator), so
# weights are kept roughly equal across the nine type-families below.
# ---------------------------------------------------------------------------
ELEVEN_PLUS_NVR_TOPICS = [
    ("Shape Sequences (Series)", 1),
    ("Rotation Sequences", 1),
    ("Odd One Out (Shapes)", 1),
    ("Shape Analogies", 1),
    ("Matrix Completion", 1),
    ("Shape Codes", 1),
    ("Similarity Grouping", 1),
    ("Shape Counting", 1),
    ("Reflection (Mirror Image)", 1),
]

EXAM_STYLE = "GL Assessment"
HOMEWORK_MINUTES = "45-50"
KEY_STAGE = "11+"
YEAR_GROUP = 6  # 11+ is sat at the start of Year 6 (some in Year 5)


# ---------------------------------------------------------------------------
# Shape vocabulary: two shape types, nine colours each, using emoji that
# render as real coloured shapes.
# ---------------------------------------------------------------------------
COLORS = ["red", "orange", "yellow", "green", "blue", "purple", "brown", "black", "white"]
SHAPE_TYPES = ["circle", "square"]

EMOJI_MAP = {
    "circle": {
        "red": "🔴", "orange": "🟠", "yellow": "🟡", "green": "🟢", "blue": "🔵",
        "purple": "🟣", "brown": "🟤", "black": "⚫", "white": "⚪",
    },
    "square": {
        "red": "🟥", "orange": "🟧", "yellow": "🟨", "green": "🟩", "blue": "🟦",
        "purple": "🟪", "brown": "🟫", "black": "⬛", "white": "⬜",
    },
}

# Fixed code scheme for the "Shape Codes" topic (first-letter-based, made up
# for this script — not from any real exam's code key).
COLOR_CODE = {
    "red": "R", "orange": "O", "yellow": "Y", "green": "G", "blue": "U",
    "purple": "P", "brown": "N", "black": "K", "white": "W",
}
SHAPE_CODE = {"circle": "C", "square": "S"}

# 8 compass directions, evenly spaced by 45 degrees, used for rotation and
# reflection questions.
ARROWS = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]

# Reflection across a vertical mirror line: east/west-leaning directions
# flip left-right, due-north/south stay the same.
VERTICAL_MIRROR = {
    "⬆️": "⬆️", "↗️": "↖️", "➡️": "⬅️", "↘️": "↙️",
    "⬇️": "⬇️", "↙️": "↘️", "⬅️": "➡️", "↖️": "↗️",
}

WARM_COLORS = ["red", "orange", "yellow", "brown"]
COOL_COLORS = ["green", "blue", "purple", "black", "white"]


def _emoji(shape_type: str, color: str) -> str:
    return EMOJI_MAP[shape_type][color]


def _random_shape(exclude=None):
    """Return a random (shape_type, color) pair, optionally excluding one."""
    while True:
        st = random.choice(SHAPE_TYPES)
        c = random.choice(COLORS)
        if exclude is None or (st, c) != exclude:
            return st, c


# ---------------------------------------------------------------------------
# MCQ helper (same approach as the maths/English/VR generators: 5 options)
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


# ---------------------------------------------------------------------------
# Topic generators — each returns (content_str, correct_answers_list)
# ---------------------------------------------------------------------------
def _gen_shape_sequences(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        color_start = random.randint(0, 8)
        color_step = random.choice([1, 2, 3, -1, -2])
        type_pattern_len = random.choice([1, 2])  # 1 = constant type, 2 = alternating

        if type_pattern_len == 1:
            fixed_type = random.choice(SHAPE_TYPES)
            type_at = lambda pos: fixed_type
        else:
            type_a, type_b = SHAPE_TYPES
            type_at = lambda pos: type_a if pos % 2 == 0 else type_b

        sequence = []
        for pos in range(5):
            color = COLORS[(color_start + color_step * pos) % 9]
            sequence.append(_emoji(type_at(pos), color))

        next_color = COLORS[(color_start + color_step * 5) % 9]
        next_type = type_at(5)
        correct = _emoji(next_type, next_color)

        distractors = set()
        distractors.add(_emoji(next_type, COLORS[(color_start + color_step * 5 + 1) % 9]))
        other_type = SHAPE_TYPES[1] if next_type == SHAPE_TYPES[0] else SHAPE_TYPES[0]
        distractors.add(_emoji(other_type, next_color))
        distractors.add(_emoji(other_type, COLORS[(color_start + color_step * 4) % 9]))
        while len(distractors) < 4:
            st, c = _random_shape(exclude=(next_type, next_color))
            distractors.add(_emoji(st, c))
        distractors.discard(correct)
        distractors = list(distractors)[:4]
        while len(distractors) < 4:
            st, c = _random_shape(exclude=(next_type, next_color))
            candidate = _emoji(st, c)
            if candidate != correct and candidate not in distractors:
                distractors.append(candidate)

        text = f"What comes next in the sequence? {'  '.join(sequence)}  ?"
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_rotation_sequences(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        start = random.randint(0, 7)
        step = random.choice([1, 2, -1, -2, 3, -3])
        sequence = [ARROWS[(start + step * pos) % 8] for pos in range(5)]
        correct = ARROWS[(start + step * 5) % 8]
        distractors = [a for a in ARROWS if a != correct]
        distractors = random.sample(distractors, 4)
        text = f"This shape rotates by the same amount each time. What comes next? {'  '.join(sequence)}  ?"
        block, letter = _format_mcq(i, text, correct, distractors)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_odd_one_out(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        # Only "same shape type, different colours" is used here: with just
        # two shape types available, a "same colour, different type" group
        # can only ever look 2 ways, which isn't enough for 4 distinct
        # options. Sharing type and varying colour gives 9 distinct looks,
        # which is always enough.
        shared_type = random.choice(SHAPE_TYPES)
        shared_colors = random.sample(COLORS, 4)
        same_group = [_emoji(shared_type, c) for c in shared_colors]
        odd_type = SHAPE_TYPES[1] if shared_type == SHAPE_TYPES[0] else SHAPE_TYPES[0]
        remaining_colors = [c for c in COLORS if c not in shared_colors]
        odd_color = random.choice(remaining_colors)
        correct = _emoji(odd_type, odd_color)

        text = "Which shape does NOT belong with the others?"
        block, letter = _format_mcq(i, text, correct, same_group)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_shape_analogies(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        rule = random.choice(["color_shift", "type_swap"])
        if rule == "color_shift":
            step = random.choice([1, 2, 3, -1, -2])
            type1 = random.choice(SHAPE_TYPES)
            color1 = random.choice(COLORS)
            color2 = COLORS[(COLORS.index(color1) + step) % 9]
            shape_a, shape_b = _emoji(type1, color1), _emoji(type1, color2)

            type2 = random.choice(SHAPE_TYPES)
            color3 = random.choice(COLORS)
            color4 = COLORS[(COLORS.index(color3) + step) % 9]
            shape_c, correct = _emoji(type2, color3), _emoji(type2, color4)

            distractors = set()
            distractors.add(_emoji(type2, COLORS[(COLORS.index(color3) - step) % 9]))
            other_type = SHAPE_TYPES[1] if type2 == SHAPE_TYPES[0] else SHAPE_TYPES[0]
            distractors.add(_emoji(other_type, color4))
            distractors.add(shape_c)
        else:
            color1 = random.choice(COLORS)
            type1, type2 = SHAPE_TYPES
            shape_a, shape_b = _emoji(type1, color1), _emoji(type2, color1)

            color2 = random.choice(COLORS)
            shape_c, correct = _emoji(type1, color2), _emoji(type2, color2)

            distractors = set()
            distractors.add(_emoji(type1, color2))
            distractors.add(_emoji(type2, random.choice([c for c in COLORS if c != color2])))
            distractors.add(shape_c)

        while len(distractors) < 4:
            st, c = _random_shape()
            candidate = _emoji(st, c)
            if candidate != correct:
                distractors.add(candidate)
        distractors.discard(correct)
        distractors = list(distractors)[:4]
        while len(distractors) < 4:
            st, c = _random_shape()
            candidate = _emoji(st, c)
            if candidate != correct and candidate not in distractors:
                distractors.append(candidate)

        text = f"{shape_a} is to {shape_b} as {shape_c} is to ?"
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_matrix_completion(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        type_a, type_b = random.sample(SHAPE_TYPES, 2)
        color_a = random.choice(COLORS)
        step = random.choice([1, 2, 3, -1, -2])
        color_b = COLORS[(COLORS.index(color_a) + step) % 9]

        top_left = _emoji(type_a, color_a)
        top_right = _emoji(type_a, color_b)
        bottom_left = _emoji(type_b, color_a)
        correct = _emoji(type_b, color_b)

        distractors = set()
        distractors.add(_emoji(type_a, color_b))       # wrong type (top row's type)
        distractors.add(_emoji(type_b, color_a))        # wrong: unchanged colour
        distractors.add(_emoji(type_b, COLORS[(COLORS.index(color_a) - step) % 9]))  # wrong direction shift
        while len(distractors) < 4:
            st, c = _random_shape(exclude=(type_b, color_b))
            distractors.add(_emoji(st, c))
        distractors.discard(correct)
        distractors = list(distractors)[:4]
        while len(distractors) < 4:
            st, c = _random_shape()
            candidate = _emoji(st, c)
            if candidate != correct and candidate not in distractors:
                distractors.append(candidate)

        text = (f"Which shape completes the grid?\n"
                 f"   {top_left}   {top_right}\n"
                 f"   {bottom_left}   ?")
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_shape_codes(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        example_pairs = random.sample([(t, c) for t in SHAPE_TYPES for c in COLORS], 2)
        target_pair = random.choice(
            [p for p in [(t, c) for t in SHAPE_TYPES for c in COLORS] if p not in example_pairs]
        )

        def code_for(pair):
            t, c = pair
            return COLOR_CODE[c] + SHAPE_CODE[t]

        example_lines = [f"{_emoji(t, c)} is coded {code_for((t, c))}" for (t, c) in example_pairs]
        correct = code_for(target_pair)

        distractors = set()
        t, c = target_pair
        distractors.add(SHAPE_CODE[t] + COLOR_CODE[c])  # swapped order
        wrong_color = random.choice([x for x in COLORS if x != c])
        distractors.add(COLOR_CODE[wrong_color] + SHAPE_CODE[t])
        other_type = SHAPE_TYPES[1] if t == SHAPE_TYPES[0] else SHAPE_TYPES[0]
        distractors.add(COLOR_CODE[c] + SHAPE_CODE[other_type])
        while len(distractors) < 4:
            wc = random.choice(COLORS)
            wt = random.choice(SHAPE_TYPES)
            candidate = COLOR_CODE[wc] + SHAPE_CODE[wt]
            if candidate != correct:
                distractors.add(candidate)
        distractors.discard(correct)
        distractors = list(distractors)[:4]

        text = (f"Using the same code as these examples, what is the code for {_emoji(*target_pair)}?\n"
                 f"   {example_lines[0]}\n   {example_lines[1]}")
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_similarity_grouping(index: int) -> tuple:
    blocks, answers = [], []
    fixed_options = ["Group 1", "Group 2", "Neither group", "Both groups", "Cannot be determined"]
    for i in range(1, 11):
        rule = random.choice(["shape_type", "temperature"])
        used_pairs = set()
        if rule == "shape_type":
            group1_type, group2_type = random.sample(SHAPE_TYPES, 2)
            group1_colors = random.sample(COLORS, 3)
            group2_colors = random.sample(COLORS, 3)
            group1 = [_emoji(group1_type, c) for c in group1_colors]
            group2 = [_emoji(group2_type, c) for c in group2_colors]
            used_pairs = {(group1_type, c) for c in group1_colors} | {(group2_type, c) for c in group2_colors}

            new_type, new_color = _random_shape()
            while (new_type, new_color) in used_pairs:
                new_type, new_color = _random_shape()
            new_shape = _emoji(new_type, new_color)
            correct_group = "Group 1" if new_type == group1_type else "Group 2"
        else:
            group1_colors = random.sample(WARM_COLORS, 3)
            group2_colors = random.sample(COOL_COLORS, 3)
            group1_types = [random.choice(SHAPE_TYPES) for _ in group1_colors]
            group2_types = [random.choice(SHAPE_TYPES) for _ in group2_colors]
            group1 = [_emoji(t, c) for t, c in zip(group1_types, group1_colors)]
            group2 = [_emoji(t, c) for t, c in zip(group2_types, group2_colors)]
            used_pairs = set(zip(group1_types, group1_colors)) | set(zip(group2_types, group2_colors))

            new_type, new_color = _random_shape()
            while (new_type, new_color) in used_pairs or new_color not in (WARM_COLORS + COOL_COLORS):
                new_type, new_color = _random_shape()
            new_shape = _emoji(new_type, new_color)
            correct_group = "Group 1" if new_color in WARM_COLORS else "Group 2"

        text = (f"Group 1: {'  '.join(group1)}\n"
                 f"Group 2: {'  '.join(group2)}\n"
                 f"Which group does {new_shape} belong to?")
        distractors = [opt for opt in fixed_options if opt != correct_group]
        block, letter = _format_mcq(i, text, correct_group, distractors)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_shape_counting(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        n_shapes = random.randint(9, 14)
        shapes = [_random_shape() for _ in range(n_shapes)]
        ask_mode = random.choice(["color", "shape_type"])

        if ask_mode == "color":
            target = random.choice(COLORS)
            correct = sum(1 for (_, c) in shapes if c == target)
            question_target_text = f"coloured {target}"
        else:
            target = random.choice(SHAPE_TYPES)
            correct = sum(1 for (t, _) in shapes if t == target)
            question_target_text = f"{target}s"

        display = "  ".join(_emoji(t, c) for t, c in shapes)
        distractors = set()
        for delta in [-2, -1, 1, 2]:
            candidate = correct + delta
            if candidate >= 0:
                distractors.add(candidate)
        while len(distractors) < 4:
            distractors.add(max(0, correct + random.choice([-3, 3, 4, -4])))
        distractors.discard(correct)
        distractors = list(distractors)[:4]
        while len(distractors) < 4:
            distractors.append(correct + len(distractors) + 5)

        text = f"How many of these shapes are {question_target_text}?\n   {display}"
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_reflection(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        arrow = random.choice(ARROWS)
        correct = VERTICAL_MIRROR[arrow]
        distractors = [a for a in ARROWS if a != correct]
        distractors = random.sample(distractors, 4)
        text = f"If this arrow is reflected in a vertical mirror line, which way will it point? {arrow}"
        block, letter = _format_mcq(i, text, correct, distractors)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


TOPIC_GENERATORS = {
    "Shape Sequences (Series)": _gen_shape_sequences,
    "Rotation Sequences": _gen_rotation_sequences,
    "Odd One Out (Shapes)": _gen_odd_one_out,
    "Shape Analogies": _gen_shape_analogies,
    "Matrix Completion": _gen_matrix_completion,
    "Shape Codes": _gen_shape_codes,
    "Similarity Grouping": _gen_similarity_grouping,
    "Shape Counting": _gen_shape_counting,
    "Reflection (Mirror Image)": _gen_reflection,
}


def generate_11plus_nvr(topic: str, index: int) -> tuple:
    """Generate one 11+ Non-Verbal Reasoning worksheet (MCQ) for a given topic."""
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ Non-Verbal Reasoning topic: {topic}")
    body, correct_answers = generator(index)
    header = (
        f"11+ Non-Verbal Reasoning Practice (GL Assessment style) - {topic} (Set {index})\n"
        f"Answer each question by choosing the correct option A-E.\n\n"
    )
    return header + body, correct_answers


# ---------------------------------------------------------------------------
# Batch generation / RAG store integration (mirrors the other 11+ generators)
# ---------------------------------------------------------------------------
def _weighted_topic_sequence(count: int) -> list:
    """Build an ordered topic list of length `count`. Weights are roughly
    equal across the nine NVR type-families, since no official frequency
    split is publicly documented for NVR question types."""
    topics, weights = zip(*ELEVEN_PLUS_NVR_TOPICS)
    return random.choices(topics, weights=weights, k=count)


def check_11plus_nvr_exists() -> bool:
    """检查是否已有 11+ 非言语推理练习"""
    store = get_elevenplus_rag_store()
    results = store.search(query="11 plus non-verbal reasoning", k=1, filters={"subject": "11PlusNonVerbalReasoning"})
    return len(results) > 0


def clean_11plus_nvr() -> int:
    """清理所有已有的 11+ 非言语推理练习"""
    store = get_elevenplus_rag_store()
    results = store.search_by_metadata({"subject": "11PlusNonVerbalReasoning"})

    if not results:
        print("  没有找到需要清理的 11+ 非言语推理作业")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  已清理 {deleted} 份 11+ 非言语推理作业")
    return deleted


def generate_11plus_nvr_batch(count: int = 500) -> list:
    """生成指定数量的 11+ 非言语推理练习，主题在 9 个类别间大致均匀分布"""
    topic_sequence = _weighted_topic_sequence(count)
    batch_data = []

    for i, topic in enumerate(topic_sequence, start=1):
        content, correct_answers = generate_11plus_nvr(topic, i)

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "11PlusNonVerbalReasoning",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "question_format": "multiple_choice_5_options",
            "representation": "emoji_shape_and_arrow_symbols",
            "student_id": None,
            "correct_answers": ", ".join(correct_answers),
        }
        doc_id = f"elevenplus_nvr_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份 11+ 非言语推理作业")

    return batch_data


def main():
    """主函数：检查 11+ Non-Verbal Reasoning 练习是否存在，缺失则生成"""
    print("检查 11+ Non-Verbal Reasoning 练习是否存在...\n")

    store = get_elevenplus_rag_store()
    exists = check_11plus_nvr_exists()
    status = "已有" if exists else "缺失"
    print(f"  11+ Non-Verbal Reasoning: {status}")

    if exists:
        print("\n11+ Non-Verbal Reasoning 练习已存在，无需生成。")
        return

    print("\n开始生成 11+ Non-Verbal Reasoning 练习 (emoji/符号表示, MCQ, 9 大主题均匀分布)...")
    batch_data = generate_11plus_nvr_batch(count=500)

    if batch_data:
        store.add_batch_homework(batch_data)
        print(f"成功添加 {len(batch_data)} 份 11+ Non-Verbal Reasoning 练习到 RAG 存储")

    stats = store.get_stats()
    print("\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()