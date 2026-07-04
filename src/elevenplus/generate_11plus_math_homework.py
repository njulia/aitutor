#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ (Eleven Plus) Maths Practice Generator
===========================================

Generates ORIGINAL 11+-style maths practice questions and stores them in the
RAG store, mirroring the structure of generate_all_math_homework.py.

Why this doesn't scrape/copy real past papers
----------------------------------------------
Actual 11+ past papers (GL Assessment, CEM/CSSE, Bond, CGP, and individual
grammar schools' specimen papers) are copyrighted. This script does NOT
reproduce or paraphrase any of that content. Instead it generates brand-new
questions, but weights topics and format to match the *publicly documented*
structure of the exam board most top-ranking grammar schools actually use:

  GL Assessment (the successor to NFER, used by the majority of grammar
  school consortia in England):
    - Maths paper: ~50 questions in ~50 minutes, multiple-choice with
      5 answer options (A-E) per question.
    - Content stays rooted in the KS2 National Curriculum but reaches into
      Year 6 objectives children may not have met yet at school.
    - "Number" questions (arithmetic, fractions, decimals, percentages,
      primes/factors/multiples) appear roughly 5x more often than any other
      single topic — so this generator weights "Number" topics 5x heavier
      than the others when building a batch, same as the real paper mix.
    - Common secondary topics: ratio & proportion, basic algebra, shape/
      space/measures, and data interpretation (bar/pie charts, tables),
      usually delivered as short word problems rather than bare sums.

Sources for the above structural facts (topic weighting, format, timing) are
public exam-board / tutoring-company explainer pages, not exam content
itself — no verbatim question, wording, or answer key from any real paper is
used anywhere in this file.

Usage mirrors generate_all_math_homework.py: run this script directly to
check whether 11+ Maths homework already exists in the RAG store, and if
not, generate a batch and add it.
"""
import sys
import os
import random

# 添加项目根目录到路径 (same pattern as generate_all_math_homework.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Topic list + weights, based on the public GL Assessment topic breakdown.
# "Number" is weighted 5x because GL's own guidance states number questions
# come up ~5x more often than any other single question type.
# ---------------------------------------------------------------------------
ELEVEN_PLUS_TOPICS = [
    ("Number: Arithmetic & Mental Maths", 5),
    ("Number: Fractions, Decimals & Percentages", 5),
    ("Number: Primes, Factors & Multiples", 5),
    ("Ratio and Proportion", 1),
    ("Algebra Basics", 1),
    ("Shape, Space and Measures", 1),
    ("Data Handling and Graphs", 1),
    ("Worded Problem Solving", 1),
    ("Speed, Distance and Time", 1),
    ("Sequences and Patterns", 1),
]

EXAM_STYLE = "GL Assessment"          # exam board most top grammar schools use
HOMEWORK_MINUTES = "45-50"            # matches the real GL maths paper length
KEY_STAGE = "11+"
YEAR_GROUP = 6                        # 11+ is sat at the start of Year 6 (some in Year 5)


# ---------------------------------------------------------------------------
# Multiple-choice helpers
# ---------------------------------------------------------------------------
def _make_distractors(correct: float, count: int = 4, spread: float = None):
    """Build plausible wrong answers around a correct numeric value.

    Mimics common GL-style distractor patterns: off-by-a-common-mistake
    values (wrong operation, misplaced decimal, off-by-one, etc.) rather
    than random noise, so the question still tests understanding.
    """
    if spread is None:
        spread = max(1, abs(correct) * 0.2)

    candidates = set()
    attempts = 0
    while len(candidates) < count and attempts < 50:
        attempts += 1
        delta = random.choice([-2, -1, 1, 2]) * random.uniform(0.5, 1.5) * spread
        wrong = correct + delta
        if isinstance(correct, int) and float(wrong).is_integer():
            wrong = int(wrong)
        elif isinstance(correct, int):
            wrong = round(wrong)
        else:
            wrong = round(wrong, 2)
        if wrong != correct:
            candidates.add(wrong)

    while len(candidates) < count:
        candidates.add(correct + len(candidates) + 1)

    return list(candidates)[:count]


def _format_mcq(question_num: int, question_text: str, correct, distractors):
    """Return (question_block_text, correct_letter) for a 5-option MCQ."""
    options = distractors + [correct]
    random.shuffle(options)
    letters = ["A", "B", "C", "D", "E"]
    correct_letter = letters[options.index(correct)]
    lines = [f"{question_num}. {question_text}"]
    for letter, opt in zip(letters, options):
        lines.append(f"   {letter}) {opt}")
    return "\n".join(lines), correct_letter


# ---------------------------------------------------------------------------
# Topic generators — each returns (content_str, correct_answers_list)
# All numbers/questions are generated fresh each call; nothing is copied
# from any real exam paper.
# ---------------------------------------------------------------------------
def _gen_arithmetic(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        op = random.choice(["+", "-", "×", "÷", "mixed"])
        if op == "+":
            a, b = random.randint(100, 9999), random.randint(100, 9999)
            correct = a + b
            text = f"{a} + {b} = ?"
        elif op == "-":
            a = random.randint(500, 9999)
            b = random.randint(100, a)
            correct = a - b
            text = f"{a} - {b} = ?"
        elif op == "×":
            a, b = random.randint(12, 99), random.randint(2, 12)
            correct = a * b
            text = f"{a} × {b} = ?"
        elif op == "÷":
            b = random.randint(2, 12)
            result = random.randint(10, 99)
            a = b * result
            correct = result
            text = f"{a} ÷ {b} = ?"
        else:
            a, b, c = random.randint(10, 50), random.randint(2, 9), random.randint(5, 40)
            correct = a * b - c
            text = f"({a} × {b}) - {c} = ?"
        distractors = _make_distractors(correct)
        block, letter = _format_mcq(i, text, correct, distractors)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_fdp(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["frac_of", "pct_of", "dec_to_pct", "frac_to_dec", "pct_change"])
        if kind == "frac_of":
            denom = random.choice([2, 3, 4, 5, 6, 8, 10])
            whole = denom * random.randint(2, 20)
            num = random.randint(1, denom - 1)
            correct = whole * num // denom
            text = f"What is {num}/{denom} of {whole}?"
        elif kind == "pct_of":
            pct = random.choice([10, 15, 20, 25, 30, 40, 60, 75])
            whole = random.choice([40, 60, 80, 120, 160, 200, 240])
            correct = pct * whole // 100
            text = f"What is {pct}% of {whole}?"
        elif kind == "dec_to_pct":
            dec = random.choice([0.05, 0.1, 0.15, 0.2, 0.25, 0.4, 0.6, 0.75])
            correct = round(dec * 100)
            text = f"Write {dec} as a percentage."
        elif kind == "frac_to_dec":
            pairs = {2: 0.5, 4: 0.25, 5: 0.2, 8: 0.125, 10: 0.1, 20: 0.05}
            denom = random.choice(list(pairs.keys()))
            correct = pairs[denom]
            text = f"Write 1/{denom} as a decimal."
        else:
            start = random.choice([40, 60, 80, 100, 120])
            pct = random.choice([10, 20, 25, 50])
            direction = random.choice(["increase", "decrease"])
            if direction == "increase":
                correct = start + start * pct // 100
                text = f"Increase {start} by {pct}%."
            else:
                correct = start - start * pct // 100
                text = f"Decrease {start} by {pct}%."
        distractors = _make_distractors(correct, spread=max(1, abs(correct) * 0.15))
        block, letter = _format_mcq(i, text, correct, distractors)
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_primes_factors(index: int) -> tuple:
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["is_prime", "hcf", "lcm", "factor_count", "prime_factor"])
        if kind == "is_prime":
            n = random.randint(2, 100)
            is_p = n in primes or all(n % p != 0 for p in range(2, int(n ** 0.5) + 1)) and n > 1
            correct = "Yes" if is_p else "No"
            text = f"Is {n} a prime number?"
            distractors = ["Yes", "No", "Only if even", "Cannot tell"]
            distractors = [d for d in distractors if d != correct][:4]
            while len(distractors) < 4:
                distractors.append(random.choice(["Sometimes", "Only if odd"]))
        elif kind == "hcf":
            a, b = random.choice([(12, 18), (24, 36), (15, 25), (16, 40), (20, 30), (18, 24)])
            import math
            correct = math.gcd(a, b)
            text = f"What is the Highest Common Factor (HCF) of {a} and {b}?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.5))
        elif kind == "lcm":
            a, b = random.choice([(4, 6), (3, 5), (6, 8), (4, 10), (5, 6), (8, 12)])
            import math
            correct = a * b // math.gcd(a, b)
            text = f"What is the Lowest Common Multiple (LCM) of {a} and {b}?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.4))
        elif kind == "factor_count":
            n = random.choice([12, 16, 18, 20, 24, 28, 30, 36])
            correct = sum(1 for d in range(1, n + 1) if n % d == 0)
            text = f"How many factors does {n} have?"
            distractors = _make_distractors(correct, spread=2)
        else:
            n = random.choice([12, 18, 20, 28, 30, 45, 50])
            factors = []
            temp = n
            for p in primes:
                while temp % p == 0:
                    factors.append(p)
                    temp //= p
            correct = " × ".join(str(f) for f in factors)
            text = f"Write {n} as a product of its prime factors."
            distractors = [
                " × ".join(str(f) for f in sorted(factors, reverse=True)),
                " × ".join(str(f + 1) for f in factors),
                " × ".join(str(f) for f in factors[:-1]) if len(factors) > 1 else "2 × 3",
                " × ".join(str(f) for f in factors) + " × 1",
            ]
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_ratio(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["simplify", "share", "scale_recipe", "map_scale"])
        if kind == "simplify":
            import math
            base_a, base_b = random.choice([(1, 2), (2, 3), (3, 4), (1, 3), (2, 5)])
            k = random.randint(2, 8)
            a, b = base_a * k, base_b * k
            correct = f"{base_a}:{base_b}"
            text = f"Simplify the ratio {a}:{b}."
            distractors = [f"{base_a+1}:{base_b}", f"{base_a}:{base_b+1}", f"{a}:{b}", f"{base_b}:{base_a}"]
        elif kind == "share":
            r1, r2 = random.choice([(2, 3), (1, 4), (3, 5), (2, 5), (1, 2)])
            total = (r1 + r2) * random.randint(3, 12)
            correct = total * r1 // (r1 + r2)
            text = f"Share £{total} in the ratio {r1}:{r2}. How much is the smaller/first share?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.3))
        elif kind == "scale_recipe":
            people_from = random.choice([2, 4, 5])
            people_to = random.choice([6, 8, 10, 12])
            amount = random.choice([100, 150, 200, 250, 300])
            correct = amount * people_to // people_from
            text = f"A recipe for {people_from} people needs {amount}g of flour. How much is needed for {people_to} people?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
        else:
            scale = random.choice([10000, 25000, 50000])
            cm = random.randint(2, 15)
            correct_m = cm * scale // 100
            correct = f"{correct_m} m"
            text = f"A map has a scale of 1:{scale}. Two towns are {cm} cm apart on the map. What is the real distance?"
            distractors = [f"{correct_m + 50} m", f"{correct_m - 50} m", f"{correct_m * 10} m", f"{correct_m // 10} m"]
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_algebra(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["solve_linear", "substitute", "sequence_nth", "expand"])
        if kind == "solve_linear":
            x = random.randint(2, 20)
            coeff = random.randint(2, 9)
            add = random.randint(1, 30)
            result = coeff * x + add
            correct = x
            text = f"Solve for x: {coeff}x + {add} = {result}"
            distractors = _make_distractors(correct, spread=2)
        elif kind == "substitute":
            a_val, b_val = random.randint(2, 10), random.randint(2, 10)
            expr_choice = random.choice(["2a + b", "a - b", "a × b", "3a - 2b"])
            if expr_choice == "2a + b":
                correct = 2 * a_val + b_val
            elif expr_choice == "a - b":
                correct = a_val - b_val
            elif expr_choice == "a × b":
                correct = a_val * b_val
            else:
                correct = 3 * a_val - 2 * b_val
            text = f"If a = {a_val} and b = {b_val}, find {expr_choice}."
            distractors = _make_distractors(correct, spread=3)
        elif kind == "sequence_nth":
            start = random.randint(1, 10)
            step = random.randint(2, 8)
            correct = f"{step}n + {start - step}"
            terms = [start + step * k for k in range(4)]
            text = f"Find the nth term of the sequence: {', '.join(map(str, terms))}, ..."
            distractors = [
                f"{step}n + {start}",
                f"{step + 1}n + {start - step}",
                f"n + {step}",
                f"{step}n - {start}",
            ]
        else:
            mult = random.randint(2, 6)
            add = random.randint(1, 10)
            correct = f"{mult}x + {mult * add}"
            text = f"Expand: {mult}(x + {add})"
            distractors = [f"{mult}x + {add}", f"x + {mult * add}", f"{mult}x + {add * 2}", f"{mult + 1}x + {mult * add}"]
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_shape_space_measures(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["area_rect", "perimeter_rect", "angle_triangle", "area_triangle", "unit_convert"])
        if kind == "area_rect":
            l, w = random.randint(4, 20), random.randint(3, 15)
            correct = l * w
            text = f"A rectangle has length {l} cm and width {w} cm. What is its area?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
        elif kind == "perimeter_rect":
            l, w = random.randint(4, 20), random.randint(3, 15)
            correct = 2 * (l + w)
            text = f"A rectangle has length {l} cm and width {w} cm. What is its perimeter?"
            distractors = _make_distractors(correct, spread=4)
        elif kind == "angle_triangle":
            a1 = random.randint(30, 100)
            a2 = random.randint(30, 100 - min(0, 0))
            while a1 + a2 >= 170:
                a2 = random.randint(20, 80)
            correct = 180 - a1 - a2
            text = f"A triangle has angles of {a1}° and {a2}°. What is the third angle?"
            distractors = _make_distractors(correct, spread=5)
        elif kind == "area_triangle":
            base, height = random.randint(4, 20), random.randint(3, 16)
            correct = base * height // 2
            text = f"A triangle has a base of {base} cm and a height of {height} cm. What is its area?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
        else:
            unit_pairs = [("cm", "m", 100), ("m", "km", 1000), ("g", "kg", 1000), ("ml", "l", 1000)]
            frm, to, factor = random.choice(unit_pairs)
            value = random.choice([1, 2, 3, 4, 5]) * factor
            correct = value // factor
            text = f"Convert {value} {frm} to {to}."
            distractors = _make_distractors(correct, spread=2)
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_data_handling(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["mean", "mode", "median", "range", "pie_chart_reading"])
        nums = [random.randint(5, 50) for _ in range(random.choice([4, 5, 6]))]
        if kind == "mean":
            correct = round(sum(nums) / len(nums), 1)
            text = f"Find the mean of: {', '.join(map(str, nums))}"
            distractors = _make_distractors(correct, spread=3)
        elif kind == "mode":
            nums = [random.choice([3, 5, 7, 9]) for _ in range(6)]
            correct = max(set(nums), key=nums.count)
            text = f"Find the mode of: {', '.join(map(str, nums))}"
            distractors = _make_distractors(correct, spread=2)
        elif kind == "median":
            correct = sorted(nums)[len(nums) // 2]
            text = f"Find the median of: {', '.join(map(str, sorted(nums, key=lambda x: random.random())))}"
            distractors = _make_distractors(correct, spread=3)
        elif kind == "range":
            correct = max(nums) - min(nums)
            text = f"Find the range of: {', '.join(map(str, nums))}"
            distractors = _make_distractors(correct, spread=3)
        else:
            total = random.choice([200, 240, 300, 360])
            pct = random.choice([10, 20, 25, 30, 40])
            correct = total * pct // 100
            text = (f"A pie chart shows survey results from {total} people. "
                    f"One sector represents {pct}% of the total. How many people does that sector represent?")
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_word_problems(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["multi_step_money", "multi_step_sharing", "leftover", "comparison"])
        if kind == "multi_step_money":
            price = random.choice([250, 320, 450, 599, 750])
            qty = random.randint(2, 6)
            discount_pct = random.choice([10, 20, 25])
            subtotal = price * qty
            correct = subtotal - subtotal * discount_pct // 100
            text = (f"A shop sells pens for {price}p each. Priya buys {qty} pens and gets a "
                    f"{discount_pct}% discount on the total. How much does she pay, in pence?")
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
        elif kind == "multi_step_sharing":
            total = random.choice([144, 180, 216, 252, 288])
            people = random.randint(3, 8)
            correct = total // people
            text = f"{total} sweets are shared equally between {people} children. How many does each child get?"
            distractors = _make_distractors(correct, spread=3)
        elif kind == "leftover":
            total = random.randint(50, 300)
            group = random.randint(6, 15)
            correct = total % group
            text = f"{total} pupils need to be put into groups of {group}. How many pupils are left over after making full groups?"
            distractors = _make_distractors(correct, spread=2)
        else:
            a = random.randint(100, 500)
            b = random.randint(100, 500)
            correct = abs(a - b)
            text = f"School A raised £{a} for charity and School B raised £{b}. What is the difference between the two amounts?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_speed_distance_time(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["find_time", "find_distance", "find_speed"])
        if kind == "find_time":
            speed = random.choice([40, 50, 60, 80])
            distance = speed * random.choice([1, 2, 3, 4])
            correct = distance / speed
            text = f"A car travels {distance} miles at a speed of {speed} mph. How many hours does the journey take?"
            distractors = _make_distractors(correct, spread=1)
        elif kind == "find_distance":
            speed = random.choice([30, 40, 50, 60])
            time_h = random.choice([1, 1.5, 2, 3])
            correct = speed * time_h
            text = f"A train travels at {speed} mph for {time_h} hours. How far does it travel?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
        else:
            distance = random.choice([60, 90, 120, 150, 200])
            time_h = random.choice([1, 2, 3])
            correct = distance / time_h
            text = f"A cyclist travels {distance} km in {time_h} hours. What is their average speed in km/h?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_sequences(index: int) -> tuple:
    blocks, answers = [], []
    for i in range(1, 11):
        kind = random.choice(["arithmetic_next", "geometric_next", "missing_term"])
        if kind == "arithmetic_next":
            start = random.randint(1, 20)
            step = random.randint(2, 12)
            terms = [start + step * k for k in range(5)]
            correct = start + step * 5
            text = f"What is the next number in the sequence: {', '.join(map(str, terms))}, ?"
            distractors = _make_distractors(correct, spread=step)
        elif kind == "geometric_next":
            start = random.choice([1, 2, 3])
            ratio_val = random.choice([2, 3])
            terms = [start * (ratio_val ** k) for k in range(4)]
            correct = start * (ratio_val ** 4)
            text = f"What is the next number in the sequence: {', '.join(map(str, terms))}, ?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.3))
        else:
            start = random.randint(1, 15)
            step = random.randint(2, 10)
            terms = [start + step * k for k in range(5)]
            gap_index = random.randint(1, 3)
            correct = terms[gap_index]
            display = terms.copy()
            display[gap_index] = "?"
            text = f"Find the missing number: {', '.join(map(str, display))}"
            distractors = _make_distractors(correct, spread=step)
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


TOPIC_GENERATORS = {
    "Number: Arithmetic & Mental Maths": _gen_arithmetic,
    "Number: Fractions, Decimals & Percentages": _gen_fdp,
    "Number: Primes, Factors & Multiples": _gen_primes_factors,
    "Ratio and Proportion": _gen_ratio,
    "Algebra Basics": _gen_algebra,
    "Shape, Space and Measures": _gen_shape_space_measures,
    "Data Handling and Graphs": _gen_data_handling,
    "Worded Problem Solving": _gen_word_problems,
    "Speed, Distance and Time": _gen_speed_distance_time,
    "Sequences and Patterns": _gen_sequences,
}


def generate_11plus_homework(topic: str, index: int) -> tuple:
    """Generate one 11+ maths worksheet (10 MCQ questions) for a given topic."""
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ topic: {topic}")
    body, correct_answers = generator(index)
    header = (
        f"11+ Maths Practice (GL Assessment style) - {topic} (Set {index})\n"
        f"Answer each question by choosing the correct option A-E.\n\n"
    )
    return header + body, correct_answers


# ---------------------------------------------------------------------------
# Batch generation / RAG store integration (mirrors generate_all_math_homework.py)
# ---------------------------------------------------------------------------
def _weighted_topic_sequence(count: int) -> list:
    """Build an ordered topic list of length `count`, respecting the weights
    in ELEVEN_PLUS_TOPICS so Number topics appear ~5x more often, matching
    the real GL Assessment question mix."""
    topics, weights = zip(*ELEVEN_PLUS_TOPICS)
    return random.choices(topics, weights=weights, k=count)


def check_11plus_math_exists() -> bool:
    """检查是否已有 11+ 数学练习"""
    store = get_elevenplus_rag_store()
    results = store.search(query="maths", k=1, filters={"subject": "Maths"})
    return len(results) > 0


def clean_11plus_math() -> int:
    """清理所有已有的 11+ 数学练习"""
    store = get_elevenplus_rag_store()
    results = store.search_by_metadata({"subject": "Maths"})

    if not results:
        print("  没有找到需要清理的 11+ 作业")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  已清理 {deleted} 份 11+ 作业")
    return deleted


def generate_11plus_batch(count: int = 500) -> list:
    """生成指定数量的 11+ 数学练习，主题按权重（Number 类主题权重更高）分布"""
    topic_sequence = _weighted_topic_sequence(count)
    batch_data = []

    for i, topic in enumerate(topic_sequence, start=1):
        content, correct_answers = generate_11plus_homework(topic, i)

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "Maths",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "question_format": "multiple_choice_5_options",
            "student_id": None,
            "correct_answers": ", ".join(correct_answers),
        }
        doc_id = f"elevenplus_math_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份 11+ 作业")

    return batch_data


def main():
    """主函数：检查 11+ Maths 练习是否存在，缺失则生成"""
    print("检查 11+ Maths 练习是否存在...\n")

    store = get_elevenplus_rag_store()
    exists = check_11plus_math_exists()
    status = "已有" if exists else "缺失"
    print(f"  11+ Maths: {status}")

    if exists:
        print("\n11+ Maths 练习已存在，无需生成。")
        return

    print("\n开始生成 11+ Maths 练习 (GL Assessment 风格, MCQ, Number 主题加权)...")
    batch_data = generate_11plus_batch(count=500)

    if batch_data:
        store.add_batch_homework(batch_data)
        print(f"成功添加 {len(batch_data)} 份 11+ Maths 练习到 RAG 存储")

    stats = store.get_stats()
    print("\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()