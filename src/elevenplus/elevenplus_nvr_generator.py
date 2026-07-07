#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ (Eleven Plus) Non-Verbal Reasoning Practice Generator
============================================================

Generates ORIGINAL 11+-style Non-Verbal Reasoning (NVR) practice questions
and stores them in the RAG store.

Every "shape" is built from two standard, universally-rendering symbol sets:
  - Colour-block emoji for shape + colour (e.g. 🔴 red circle, 🟩 green square)
  - Compass-direction arrows (⬆️ ↗️ ➡️ ↘️ ⬇️ ↙️ ⬅️ ↖️) for rotation/orientation.
This allows high-fidelity visual reasoning puzzles without needing external images.
"""

import sys
import os
import json
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    get_elevenplus_rag_store = None

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 11 Topics for Non-Verbal Reasoning Topic Mastery (5 sets per topic = 55 sets)
ELEVEN_PLUS_NVR_TOPICS = [
    ("Shape Sequences & Progressions", 1),
    ("Rotation & Angular Alignment", 1),
    ("Odd One Out & Shape Discrepancy", 1),
    ("Shape Analogies & Attribute Changes", 1),
    ("Matrix Completion & Grid Logic", 1),
    ("Shape Codes & Attribute Translation", 1),
    ("Similarity Grouping & Group Association", 1),
    ("Shape Counting & Combinatorial Totals", 1),
    ("Reflection & Mirror Lines", 1),
    ("Layering & Overlapping Shapes", 1),
    ("3D Spatial Nets & Isometric Reasoning", 1),
]

EXAM_STYLE = "GL Assessment & Selective Style"
HOMEWORK_MINUTES = "45-50"
KEY_STAGE = "11+"
YEAR_GROUP = 6

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

COLOR_CODE = {
    "red": "R", "orange": "O", "yellow": "Y", "green": "G", "blue": "U",
    "purple": "P", "brown": "N", "black": "K", "white": "W",
}
SHAPE_CODE = {"circle": "C", "square": "S"}

ARROWS = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]

VERTICAL_MIRROR = {
    "⬆️": "⬆️", "↗️": "↖️", "➡️": "⬅️", "↘️": "↙️",
    "⬇️": "⬇️", "↙️": "↘️", "⬅️": "➡️", "↖️": "↗️",
}

WARM_COLORS = ["red", "orange", "yellow", "brown"]
COOL_COLORS = ["green", "blue", "purple", "black", "white"]

def _emoji(shape_type: str, color: str) -> str:
    return EMOJI_MAP[shape_type][color]

def _random_shape(exclude=None):
    while True:
        st = random.choice(SHAPE_TYPES)
        c = random.choice(COLORS)
        if exclude is None or (st, c) != exclude:
            return st, c

def _build_question(num: int, text: str, correct, distractors, explanation: str, tip: str = "", difficulty: str = "standard"):
    """Render one MCQ block and return its structured answer record."""
    options = list(distractors) + [correct]
    random.shuffle(options)
    letters = ["A", "B", "C", "D", "E"]
    correct_letter = letters[options.index(correct)]

    lines = [f"{num}. {text}"]
    for letter, opt in zip(letters, options):
        lines.append(f"   {letter}) {opt}")
    block = "\n".join(lines)

    answer_record = {
        "q": num,
        "correct_letter": correct_letter,
        "correct_value": str(correct),
        "explanation": explanation,
        "tip": tip,
        "difficulty": difficulty,
    }
    return block, answer_record

# ---------------------------------------------------------------------------
# Topic Generators
# ---------------------------------------------------------------------------
def _gen_shape_sequences(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
    for i in range(1, 11):
        color_start = random.randint(0, 8)
        color_step = random.choice([1, 2, 3, -1, -2])
        type_pattern_len = random.choice([1, 2])

        if type_pattern_len == 1:
            fixed_type = random.choice(SHAPE_TYPES)
            type_at = lambda pos: fixed_type
            pattern_desc = f"keeping the shape type fixed as {fixed_type}s"
        else:
            type_a, type_b = SHAPE_TYPES
            type_at = lambda pos: type_a if pos % 2 == 0 else type_b
            pattern_desc = f"alternating shape types between {type_a}s and {type_b}s"

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

        text = f"Identify what shape and colour comes next in this logical sequence:\n   {'  '.join(sequence)}  [ ? ]"
        
        explanation = (
            f"The sequence is formed by {pattern_desc} while shifting the fill colour. "
            f"The colour shifts by {color_step} positions in our colour list each step. "
            f"The 5th shape is {sequence[-1]}. Applying the same logic, the 6th shape must be {correct}."
        )
        tip = "Solve by isolating attributes. Look at the shape outlines first, then study how the colours shift in sequence."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_rotation_sequences(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
    for i in range(1, 11):
        start = random.randint(0, 7)
        step = random.choice([1, 2, -1, -2, 3, -3])
        sequence = [ARROWS[(start + step * pos) % 8] for pos in range(5)]
        correct = ARROWS[(start + step * 5) % 8]
        distractors = [a for a in ARROWS if a != correct]
        distractors = random.sample(distractors, 4)
        
        text = f"This indicator arrow rotates by a constant angle at each step. What orientation comes next?\n   {'  '.join(sequence)}  [ ? ]"
        
        dir_desc = "clockwise" if step > 0 else "anti-clockwise"
        deg_desc = abs(step) * 45
        explanation = (
            f"The arrow rotates {dir_desc} by {deg_desc}° in each transition. "
            f"The 5th arrow is pointing {sequence[-1]}. Moving another {deg_desc}° {dir_desc} results in pointing {correct}."
        )
        tip = "Use a small mental compass (North, East, South, West) to measure the angular steps (each step is 45°)."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_odd_one_out(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
    for i in range(1, 11):
        shared_type = random.choice(SHAPE_TYPES)
        shared_colors = random.sample(COLORS, 4)
        same_group = [_emoji(shared_type, c) for c in shared_colors]
        odd_type = SHAPE_TYPES[1] if shared_type == SHAPE_TYPES[0] else SHAPE_TYPES[0]
        remaining_colors = [c for c in COLORS if c not in shared_colors]
        odd_color = random.choice(remaining_colors)
        correct = _emoji(odd_type, odd_color)

        text = "Which shape does NOT belong with the other four?"
        
        explanation = (
            f"Four of the options are {shared_type}s ({', '.join(same_group)}), regardless of their individual colours. "
            f"The option '{correct}' is a {odd_type}, which violates this shared structural category, making it the odd one out."
        )
        tip = "Find a general rule that successfully groups four of the options together. The one that breaks this rule is your answer."
        
        block, rec = _build_question(i, text, correct, same_group, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_shape_analogies(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
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
            
            rel_desc = f"shifting the colour forward by {step} places while keeping the shape fixed"
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
            
            rel_desc = "swapping the shape type (circles to squares, or vice versa) while keeping the colour identical"

        while len(distractors) < 4:
            st, c = _random_shape()
            candidate = _emoji(st, c)
            if candidate != correct:
                distractors.add(candidate)
        distractors.discard(correct)
        distractors = list(distractors)[:4]

        text = f"Complete the analogy:\n   {shape_a}  is to  {shape_b}   as   {shape_c}  is to  [ ? ]"
        
        explanation = (
            f"The transformation from the first shape to the second involves {rel_desc}. "
            f"Applying this same relationship to the third shape ({shape_c}) produces {correct}."
        )
        tip = "Say the transformation rule in a simple sentence, then apply that exact sentence to the third shape."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_matrix_completion(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
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
        distractors.add(_emoji(type_a, color_b))
        distractors.add(_emoji(type_b, color_a))
        distractors.add(_emoji(type_b, COLORS[(COLORS.index(color_a) - step) % 9]))
        while len(distractors) < 4:
            st, c = _random_shape(exclude=(type_b, color_b))
            distractors.add(_emoji(st, c))
        distractors.discard(correct)
        distractors = list(distractors)[:4]

        text = (f"Which shape completes the 2x2 grid logically?\n"
                 f"   {top_left}   {top_right}\n"
                 f"   {bottom_left}   [ ? ]")
        
        explanation = (
            f"The horizontal rule is that the shape type remains constant while the colour shifts. "
            f"The vertical rule is that the shape type switches from {type_a} to {type_b} while the colour is preserved. "
            f"Therefore, the missing bottom-right shape must be of type {type_b} with colour {color_b}, which gives {correct}."
        )
        tip = "Solve matrices by looking across the rows first to find a rule, then verify if the same rule holds down the columns."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_shape_codes(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
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
        distractors.add(SHAPE_CODE[t] + COLOR_CODE[c])
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

        text = (f"What is the code for the final shape, given the coded examples?\n"
                 f"   {example_lines[0]}\n"
                 f"   {example_lines[1]}\n"
                 f"   {_emoji(*target_pair)} = [ ? ]")
        
        explanation = (
            f"The two-letter code system maps colour to the first letter and shape type to the second letter. "
            f"Here, {target_pair[1]} translates to '{COLOR_CODE[c]}' and {target_pair[0]} translates to '{SHAPE_CODE[t]}'. "
            f"Combining these, the code is {correct}."
        )
        tip = "Do not try to guess. Match each letter position of the code to a specific attribute of the shape systematically."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_similarity_grouping(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
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
            rule_desc = f"Group 1 is only {group1_type}s, Group 2 is only {group2_type}s."
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
            rule_desc = "Group 1 contains warm-coloured shapes (red, orange, yellow, brown), while Group 2 contains cool-coloured shapes."

        text = (f"Identify which group the target shape belongs to:\n"
                 f"   Group 1: {'  '.join(group1)}\n"
                 f"   Group 2: {'  '.join(group2)}\n"
                 f"   Target Shape: {new_shape}")
        
        distractors = [opt for opt in fixed_options if opt != correct_group]
        
        explanation = (
            f"Analyzing the common attributes: {rule_desc} "
            f"The target shape '{new_shape}' fits the rule of {correct_group} perfectly."
        )
        tip = "Analyze the grouping criteria. If a shape has multiple traits, find the one trait that is completely consistent inside each group."
        
        block, rec = _build_question(i, text, correct_group, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_shape_counting(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
    for i in range(1, 11):
        n_shapes = random.randint(9, 14)
        shapes = [_random_shape() for _ in range(n_shapes)]
        ask_mode = random.choice(["color", "shape_type"])

        if ask_mode == "color":
            target = random.choice(COLORS)
            correct = sum(1 for (_, c) in shapes if c == target)
            question_target_text = f"coloured '{target}'"
            ex_reason = f"Exactly {correct} of the displayed shapes have a '{target}' fill."
        else:
            target = random.choice(SHAPE_TYPES)
            correct = sum(1 for (t, _) in shapes if t == target)
            question_target_text = f"{target}s"
            ex_reason = f"Exactly {correct} of the displayed shapes are of outline type '{target}'."

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

        text = f"Count carefully: how many shapes are {question_target_text} in the set below?\n   {display}"
        
        explanation = (
            f"Scanning and tallying the elements: {ex_reason} "
            f"The correct count is {correct}."
        )
        tip = "Point with your finger or use your pencil to cross off counted shapes in order from left to right to prevent double-counting."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_reflection(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
    for i in range(1, 11):
        arrow = random.choice(ARROWS)
        correct = VERTICAL_MIRROR[arrow]
        distractors = [a for a in ARROWS if a != correct]
        distractors = random.sample(distractors, 4)
        
        text = f"If this pointing arrow is reflected across a vertical mirror line, which way will it point in the reflection?\n   Original Arrow: {arrow}"
        
        explanation = (
            f"Under vertical mirror reflection, vertical alignments (up/down) remain identical, "
            f"while horizontal coordinates are flipped (left turns into right and vice versa). "
            f"Therefore, {arrow} reflects into {correct}."
        )
        tip = "Imagine a flat vertical mirror running along the right side of the shape. What points closest to the mirror line must stay closest."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_layering(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
    for i in range(1, 11):
        # We model layering: shape A on top of shape B
        shape_a_type = random.choice(SHAPE_TYPES)
        shape_b_type = random.choice(SHAPE_TYPES)
        color_a = random.choice(COLORS)
        color_b = random.choice([c for c in COLORS if c != color_a])
        
        emoji_a = _emoji(shape_a_type, color_a)
        emoji_b = _emoji(shape_b_type, color_b)
        
        correct = f"{emoji_a} is layered ON TOP of {emoji_b}"
        distractors = [
            f"{emoji_b} is layered ON TOP of {emoji_a}",
            f"{emoji_a} and {emoji_b} are placed completely side-by-side",
            f"{emoji_a} is nested entirely inside {emoji_b}",
            f"{emoji_b} is nested entirely inside {emoji_a}",
        ]
        
        text = (
            f"In a complex overlapping composite drawing, shape X has an unbroken complete outline, "
            f"while shape Y has its overlapping border partially blocked or interrupted by shape X.\n"
            f"If Shape X is {emoji_a} and Shape Y is {emoji_b}, which layer relation is correct?"
        )
        
        explanation = (
            f"Because shape X ({emoji_a}) has an unbroken complete boundary, it must be in the foreground. "
            f"Shape Y ({emoji_b}) has its border blocked, which means it is in the background. "
            f"Hence, {correct}."
        )
        tip = "The shape with the fully complete, unbroken outline is always the one that is layered on top."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

def _gen_3d_nets(index: int) -> tuple:
    blocks, records = [], []
    random.seed(index)
    faces = ["🔴", "🟩", "🔵", "🟡", "🟣", "⚫"]
    for i in range(1, 11):
        # 3D spatial query
        correct = "🔵 (Right)"
        distractors = ["🟡 (Bottom)", "🟣 (Left)", "⚫ (Back)", "🟩 (Bottom)"]
        
        text = (
            f"A 3D cube is constructed with the following face layout:\n"
            f"   Top Face: 🔴\n"
            f"   Front Face: 🟩\n"
            f"   Right Face: 🔵\n"
            f"If the cube is rotated forward by 90 degrees (so the Top face 🔴 is now the Front face), "
            f"which face is now positioned on the Right side?"
        )
        
        explanation = (
            f"Rotating a cube forward or backward by 90 degrees shifts the Top, Front, Bottom, and Back faces. "
            f"However, the lateral Right and Left faces simply spin in place but do not swap positions. "
            f"Therefore, the Right Face remains 🔵."
        )
        tip = "Visualize rotating a real cardboard box, or use your physical eraser/pencil sharpener as a 3D model."
        
        block, rec = _build_question(i, text, correct, distractors, explanation, tip)
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records

TOPIC_GENERATORS = {
    "Shape Sequences & Progressions": _gen_shape_sequences,
    "Rotation & Angular Alignment": _gen_rotation_sequences,
    "Odd One Out & Shape Discrepancy": _gen_odd_one_out,
    "Shape Analogies & Attribute Changes": _gen_shape_analogies,
    "Matrix Completion & Grid Logic": _gen_matrix_completion,
    "Shape Codes & Attribute Translation": _gen_shape_codes,
    "Similarity Grouping & Group Association": _gen_similarity_grouping,
    "Shape Counting & Combinatorial Totals": _gen_shape_counting,
    "Reflection & Mirror Lines": _gen_reflection,
    "Layering & Overlapping Shapes": _gen_layering,
    "3D Spatial Nets & Isometric Reasoning": _gen_3d_nets,
}

def generate_11plus_nvr_homework(topic: str, index: int) -> tuple:
    """Generate one 11+ Non-Verbal Reasoning worksheet (10 MCQ questions) for a topic.

    Returns:
        (content, answer_records) where content is the student-facing
        worksheet text and answer_records is a list of structured dicts.
    """
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ Non-Verbal Reasoning topic: {topic}")
    body, answer_records = generator(index)
    header = (
        f"11+ Non-Verbal Reasoning Practice (GL Assessment style) - {topic} (Set {index})\n"
        f"Answer each question by choosing the correct option A-E.\n\n"
    )
    return header + body, answer_records

# ---------------------------------------------------------------------------
# Batch generation / RAG store integration
# ---------------------------------------------------------------------------
def _weighted_topic_sequence(count: int) -> list:
    topics = list(TOPIC_GENERATORS.keys())
    return random.choices(topics, k=count)

def check_11plus_nvr_exists() -> bool:
    try:
        store = get_elevenplus_rag_store()
        if store is None:
            return False
        results = store.search(query="non-verbal reasoning", k=1, filters={"subject": "NonVerbalReasoning"})
        return len(results) > 0
    except Exception:
        return False

def clean_111PlusNonVerbalReasoning() -> int:
    store = get_elevenplus_rag_store()
    if store is None:
        return 0
    results = store.search_by_metadata({"subject": "11PlusNonVerbalReasoning"}, k=1000)

    if not results:
        print("  No NVR homework found to clean.")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  Cleaned {deleted} NVR homework files.")
    return deleted

def clean_11plus_nvr() -> int:
    store = get_elevenplus_rag_store()
    if store is None:
        return 0
    results = store.search_by_metadata({"subject": "NonVerbalReasoning"})

    if not results:
        print("  No NVR homework found to clean.")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  Cleaned {deleted} NVR homework files.")
    return deleted

def generate_11plus_nvr_batch(count: int = 300) -> list:
    topic_sequence = _weighted_topic_sequence(count)
    batch_data = []

    for i, topic in enumerate(topic_sequence, start=1):
        content, answer_records = generate_11plus_nvr_homework(topic, i)

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "NonVerbalReasoning",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "question_format": "multiple_choice_5_options",
            "student_id": None,
            "correct_answers": json.dumps(answer_records, ensure_ascii=False),
        }
        doc_id = f"elevenplus_nvr_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  Generated {i}/{count} NVR homework documents")

    return batch_data

def main():
    print("==========================================================")
    print("   11+ Non-Verbal Reasoning Practice Homework Generator   ")
    print("==========================================================\n")

    store = get_elevenplus_rag_store()

    stats = store.get_stats()
    print("\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


    exists = check_11plus_nvr_exists()
    status = "Present" if exists else "Missing"
    print(f"  11+ Non-Verbal Reasoning status: {status}")

    if exists:
        print("\n11+ Non-Verbal Reasoning practice already exists, no need to regenerate.")
        return

    print("\nBeginning generation of 11+ Non-Verbal Reasoning practice sets...")
    batch_data = generate_11plus_nvr_batch(count=300)

    if batch_data and store:
        store.add_batch_homework(batch_data)
        print(f"Successfully added {len(batch_data)} sets to the RAG Store.")

    stats = store.get_stats()
    print("\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")

if __name__ == "__main__":
    main()
