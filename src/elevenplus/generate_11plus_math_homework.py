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
      single topic - so this generator weights "Number" topics 5x heavier
      than the others when building a batch, same as the real paper mix.
    - Common secondary topics: ratio & proportion, basic algebra, shape/
      space/measures, and data interpretation (bar/pie charts, tables),
      usually delivered as short word problems rather than bare sums.

  Super-selective / top-tier grammar schools (e.g. Tiffin, Henrietta
  Barnett, St Olave's, Colyton Grammar, the Kent Test / CSSE-style papers):
    - Publicly-documented tutoring guidance for these schools consistently
      describes their maths sections as leaning further into multi-step,
      "non-routine" reasoning - problems that combine two or three skills
      (e.g. percentages + ratio, or working backwards from an answer)
      rather than testing one skill in isolation.
    - A dedicated "Non-Routine Reasoning (Top-School Style)" topic has been
      added below to reflect that, with its own originally-written question
      types (digit puzzles, work-backwards problems, calendar reasoning,
      two-step percentage change, and LCM-based deduction).

Sources for the above structural facts (topic weighting, format, timing) are
public exam-board / tutoring-company explainer pages, not exam content
itself - no verbatim question, wording, or answer key from any real paper is
used anywhere in this file.

Making answers AI-gradable
--------------------------
Earlier versions of this generator only stored the correct multiple-choice
letter (e.g. "B") for each question. That's fine for marking right/wrong,
but useless for an AI tutor that needs to check a student's actual working
or explain *why* an answer is correct. Every question below now produces a
structured record:

    {"q": 3, "correct_letter": "B", "correct_value": "42",
     "difficulty": "standard", "explanation": "..."}

The full list of these records (one per question, valid JSON) is stored in
the "correct_answers" metadata field, so an AI tutor can parse it directly,
verify a student's numeric working (not just the letter they picked), and
generate a worked explanation without having to re-derive one.

Usage mirrors generate_all_math_homework.py: run this script directly to
check whether 11+ Maths homework already exists in the RAG store, and if
not, generate a batch and add it.
"""
import sys
import os
import json
import math
import random

# 添加项目根目录到路径 (same pattern as generate_all_math_homework.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Topic list + weights, based on the public GL Assessment topic breakdown,
# plus one added topic modeled on top-tier/super-selective school style.
# "Number" is weighted 5x because GL's own guidance states number questions
# come up ~5x more often than any other single question type. The new
# top-school reasoning topic is weighted 3x - meaningfully represented
# without displacing the Number-heavy structure of the real GL paper.
# ---------------------------------------------------------------------------
ELEVEN_PLUS_TOPICS = [
    ("Number: Arithmetic & Mental Maths", 5),
    ("Number: Fractions, Decimals & Percentages", 5),
    ("Number: Primes, Factors & Multiples", 5),
    ("Non-Routine Reasoning (Top-School Style)", 3),
    ("Ratio and Proportion", 1),
    ("Algebra Basics", 1),
    ("Shape, Space and Measures", 1),
    ("Data Handling and Graphs", 1),
    ("Worded Problem Solving", 1),
    ("Speed, Distance and Time", 1),
    ("Sequences and Patterns", 1),
]

# Which "tier" each topic represents, stored in metadata so the RAG can be
# filtered by exam style later (e.g. "give me only top-school-style sets").
TOPIC_SCHOOL_TIER = {
    "Non-Routine Reasoning (Top-School Style)": (
        "Selective (Tiffin / Henrietta Barnett / St Olave's / Kent Test / "
        "CSSE style)"
    ),
}
DEFAULT_SCHOOL_TIER = "Standard (GL Assessment style)"

# Ordering priority used when a batch is assembled: lower number = appears
# earlier in the generated set (i.e. "top school's questions go first").
# Everything not listed defaults to priority 2.
TOPIC_ORDER_PRIORITY = {
    "Non-Routine Reasoning (Top-School Style)": 0,
}
DEFAULT_ORDER_PRIORITY = 2

EXAM_STYLE = "GL Assessment"          # exam board most top grammar schools use
HOMEWORK_MINUTES = "45-50"            # matches the real GL maths paper length
KEY_STAGE = "11+"
YEAR_GROUP = 6                        # 11+ is sat at the start of Year 6 (some in Year 5)


# ---------------------------------------------------------------------------
# Multiple-choice + answer-record helpers
# ---------------------------------------------------------------------------
def _make_distractors(correct, count: int = 4, spread: float = None):
    """Build plausible wrong answers around a correct numeric value.

    Mimics common GL-style distractor patterns: off-by-a-common-mistake
    values (wrong operation, misplaced decimal, off-by-one, etc.) rather
    than random noise, so the question still tests understanding.
    """
    if not isinstance(correct, (int, float)):
        # Non-numeric correct answers (strings like "12" or "2:3") are
        # handled by each generator's own distractor logic; this branch
        # only needs to exist so callers can still reach here safely.
        return [correct]

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


def _build_question(num, text, correct, distractors, explanation, difficulty="standard"):
    """Render one MCQ block and return its structured answer record.

    Returns:
        (block_text, answer_record) where answer_record is a dict with
        correct_letter, correct_value, explanation and difficulty - the
        pieces an AI tutor needs to grade AND explain the question.
    """
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
        "difficulty": difficulty,
    }
    return block, answer_record


# ---------------------------------------------------------------------------
# Topic generators - each returns (content_str, list_of_answer_records)
# All numbers/questions are generated fresh each call; nothing is copied
# from any real exam paper.
# ---------------------------------------------------------------------------
def _gen_arithmetic(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        op = random.choice(["+", "-", "×", "÷", "mixed"])
        if op == "+":
            a, b = random.randint(100, 9999), random.randint(100, 9999)
            correct = a + b
            text = f"{a} + {b} = ?"
            explanation = f"{a} + {b} = {correct}."
        elif op == "-":
            a = random.randint(500, 9999)
            b = random.randint(100, a)
            correct = a - b
            text = f"{a} - {b} = ?"
            explanation = f"{a} - {b} = {correct}."
        elif op == "×":
            a, b = random.randint(12, 99), random.randint(2, 12)
            correct = a * b
            text = f"{a} × {b} = ?"
            explanation = f"{a} × {b} = {correct}."
        elif op == "÷":
            b = random.randint(2, 12)
            result = random.randint(10, 99)
            a = b * result
            correct = result
            text = f"{a} ÷ {b} = ?"
            explanation = f"{a} ÷ {b} = {correct}, since {b} × {correct} = {a}."
        else:
            a, b, c = random.randint(10, 50), random.randint(2, 9), random.randint(5, 40)
            correct = a * b - c
            text = f"({a} × {b}) - {c} = ?"
            explanation = f"First {a} × {b} = {a * b}, then {a * b} - {c} = {correct}."
        distractors = _make_distractors(correct)
        block, record = _build_question(i, text, correct, distractors, explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_fdp(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["frac_of", "pct_of", "dec_to_pct", "frac_to_dec", "pct_change"])
        if kind == "frac_of":
            denom = random.choice([2, 3, 4, 5, 6, 8, 10])
            whole = denom * random.randint(2, 20)
            num = random.randint(1, denom - 1)
            correct = whole * num // denom
            text = f"What is {num}/{denom} of {whole}?"
            explanation = f"{whole} ÷ {denom} = {whole // denom}, then × {num} = {correct}."
        elif kind == "pct_of":
            pct = random.choice([10, 15, 20, 25, 30, 40, 60, 75])
            whole = random.choice([40, 60, 80, 120, 160, 200, 240])
            correct = pct * whole // 100
            text = f"What is {pct}% of {whole}?"
            explanation = f"{pct}% of {whole} = ({pct}/100) × {whole} = {correct}."
        elif kind == "dec_to_pct":
            dec = random.choice([0.05, 0.1, 0.15, 0.2, 0.25, 0.4, 0.6, 0.75])
            correct = round(dec * 100)
            text = f"Write {dec} as a percentage."
            explanation = f"Multiply by 100 to convert a decimal to a percentage: {dec} × 100 = {correct}%."
        elif kind == "frac_to_dec":
            pairs = {2: 0.5, 4: 0.25, 5: 0.2, 8: 0.125, 10: 0.1, 20: 0.05}
            denom = random.choice(list(pairs.keys()))
            correct = pairs[denom]
            text = f"Write 1/{denom} as a decimal."
            explanation = f"1 ÷ {denom} = {correct}."
        else:
            start = random.choice([40, 60, 80, 100, 120])
            pct = random.choice([10, 20, 25, 50])
            direction = random.choice(["increase", "decrease"])
            if direction == "increase":
                correct = start + start * pct // 100
                text = f"Increase {start} by {pct}%."
                explanation = f"{pct}% of {start} = {start * pct // 100}. Add this on: {start} + {start * pct // 100} = {correct}."
            else:
                correct = start - start * pct // 100
                text = f"Decrease {start} by {pct}%."
                explanation = f"{pct}% of {start} = {start * pct // 100}. Take this away: {start} - {start * pct // 100} = {correct}."
        distractors = _make_distractors(correct, spread=max(1, abs(correct) * 0.15))
        block, record = _build_question(i, text, correct, distractors, explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_primes_factors(index: int) -> tuple:
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["is_prime", "hcf", "lcm", "factor_count", "prime_factor"])
        if kind == "is_prime":
            n = random.randint(2, 100)
            is_p = n in primes or (all(n % p != 0 for p in range(2, int(n ** 0.5) + 1)) and n > 1)
            correct = "Yes" if is_p else "No"
            text = f"Is {n} a prime number?"
            distractors = ["Yes", "No", "Only if even", "Cannot tell"]
            distractors = [d for d in distractors if d != correct][:4]
            while len(distractors) < 4:
                distractors.append(random.choice(["Sometimes", "Only if odd"]))
            if is_p:
                explanation = f"{n} is prime - it has no factors other than 1 and itself."
            else:
                factor = next(p for p in range(2, n) if n % p == 0)
                explanation = f"{n} is not prime - it can be divided exactly by {factor} (and others), so it has more than two factors."
        elif kind == "hcf":
            a, b = random.choice([(12, 18), (24, 36), (15, 25), (16, 40), (20, 30), (18, 24)])
            correct = math.gcd(a, b)
            text = f"What is the Highest Common Factor (HCF) of {a} and {b}?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.5))
            explanation = f"The largest number that divides exactly into both {a} and {b} is {correct}."
        elif kind == "lcm":
            a, b = random.choice([(4, 6), (3, 5), (6, 8), (4, 10), (5, 6), (8, 12)])
            correct = a * b // math.gcd(a, b)
            text = f"What is the Lowest Common Multiple (LCM) of {a} and {b}?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.4))
            explanation = f"The smallest number that both {a} and {b} divide into exactly is {correct}."
        elif kind == "factor_count":
            n = random.choice([12, 16, 18, 20, 24, 28, 30, 36])
            correct = sum(1 for d in range(1, n + 1) if n % d == 0)
            text = f"How many factors does {n} have?"
            distractors = _make_distractors(correct, spread=2)
            explanation = f"Checking every whole number from 1 to {n} that divides exactly, {n} has {correct} factors."
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
            explanation = f"Dividing {n} repeatedly by prime numbers gives {correct}."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_ratio(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["simplify", "share", "scale_recipe", "map_scale"])
        if kind == "simplify":
            base_a, base_b = random.choice([(1, 2), (2, 3), (3, 4), (1, 3), (2, 5)])
            k = random.randint(2, 8)
            a, b = base_a * k, base_b * k
            correct = f"{base_a}:{base_b}"
            text = f"Simplify the ratio {a}:{b}."
            distractors = [f"{base_a+1}:{base_b}", f"{base_a}:{base_b+1}", f"{a}:{b}", f"{base_b}:{base_a}"]
            explanation = f"Divide both parts of {a}:{b} by their highest common factor ({k}) to get {correct}."
        elif kind == "share":
            r1, r2 = random.choice([(2, 3), (1, 4), (3, 5), (2, 5), (1, 2)])
            total = (r1 + r2) * random.randint(3, 12)
            per_part = total // (r1 + r2)
            correct = per_part * r1
            text = f"Share £{total} in the ratio {r1}:{r2}. How much is the first share?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.3))
            explanation = f"Total parts = {r1}+{r2} = {r1+r2}. Each part = £{total}÷{r1+r2} = £{per_part}. First share = {r1} × £{per_part} = £{correct}."
        elif kind == "scale_recipe":
            people_from = random.choice([2, 4, 5])
            people_to = random.choice([6, 8, 10, 12])
            amount = random.choice([100, 150, 200, 250, 300])
            correct = amount * people_to // people_from
            text = f"A recipe for {people_from} people needs {amount}g of flour. How much is needed for {people_to} people?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
            explanation = f"Scale factor = {people_to}÷{people_from}. {amount}g × ({people_to}÷{people_from}) = {correct}g."
        else:
            scale = random.choice([10000, 25000, 50000])
            cm = random.randint(2, 15)
            correct_m = cm * scale // 100
            correct = f"{correct_m} m"
            text = f"A map has a scale of 1:{scale}. Two towns are {cm} cm apart on the map. What is the real distance?"
            distractors = [f"{correct_m + 50} m", f"{correct_m - 50} m", f"{correct_m * 10} m", f"{correct_m // 10} m"]
            explanation = f"{cm} cm on the map = {cm} × {scale} = {cm*scale} cm in real life = {correct}."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_algebra(index: int) -> tuple:
    blocks, records = [], []
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
            explanation = f"{coeff}x = {result} - {add} = {result-add}, so x = {result-add} ÷ {coeff} = {correct}."
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
            explanation = f"Substitute a={a_val}, b={b_val} into {expr_choice}: {correct}."
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
            explanation = f"The sequence goes up by {step} each time, and the 1st term is {start}, so the nth term is {step}n + {start - step}."
        else:
            mult = random.randint(2, 6)
            add = random.randint(1, 10)
            correct = f"{mult}x + {mult * add}"
            text = f"Expand: {mult}(x + {add})"
            distractors = [f"{mult}x + {add}", f"x + {mult * add}", f"{mult}x + {add * 2}", f"{mult + 1}x + {mult * add}"]
            explanation = f"Multiply {mult} by each term inside the brackets: {mult}×x + {mult}×{add} = {correct}."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_shape_space_measures(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["area_rect", "perimeter_rect", "angle_triangle", "area_triangle", "unit_convert"])
        if kind == "area_rect":
            l, w = random.randint(4, 20), random.randint(3, 15)
            correct = l * w
            text = f"A rectangle has length {l} cm and width {w} cm. What is its area?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
            explanation = f"Area = length × width = {l} × {w} = {correct} cm²."
        elif kind == "perimeter_rect":
            l, w = random.randint(4, 20), random.randint(3, 15)
            correct = 2 * (l + w)
            text = f"A rectangle has length {l} cm and width {w} cm. What is its perimeter?"
            distractors = _make_distractors(correct, spread=4)
            explanation = f"Perimeter = 2 × (length + width) = 2 × ({l} + {w}) = {correct} cm."
        elif kind == "angle_triangle":
            a1 = random.randint(30, 100)
            a2 = random.randint(30, 100)
            while a1 + a2 >= 170:
                a2 = random.randint(20, 80)
            correct = 180 - a1 - a2
            text = f"A triangle has angles of {a1}° and {a2}°. What is the third angle?"
            distractors = _make_distractors(correct, spread=5)
            explanation = f"Angles in a triangle add up to 180°: 180 - {a1} - {a2} = {correct}°."
        elif kind == "area_triangle":
            base, height = random.randint(4, 20), random.randint(3, 16)
            correct = base * height // 2
            text = f"A triangle has a base of {base} cm and a height of {height} cm. What is its area?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
            explanation = f"Area = (base × height) ÷ 2 = ({base} × {height}) ÷ 2 = {correct} cm²."
        else:
            unit_pairs = [("cm", "m", 100), ("m", "km", 1000), ("g", "kg", 1000), ("ml", "l", 1000)]
            frm, to, factor = random.choice(unit_pairs)
            value = random.choice([1, 2, 3, 4, 5]) * factor
            correct = value // factor
            text = f"Convert {value} {frm} to {to}."
            distractors = _make_distractors(correct, spread=2)
            explanation = f"{value} {frm} ÷ {factor} = {correct} {to}."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_data_handling(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["mean", "mode", "median", "range", "pie_chart_reading"])
        nums = [random.randint(5, 50) for _ in range(random.choice([4, 5, 6]))]
        if kind == "mean":
            correct = round(sum(nums) / len(nums), 1)
            text = f"Find the mean of: {', '.join(map(str, nums))}"
            distractors = _make_distractors(correct, spread=3)
            explanation = f"Add the numbers ({sum(nums)}) and divide by how many there are ({len(nums)}): {correct}."
        elif kind == "mode":
            nums = [random.choice([3, 5, 7, 9]) for _ in range(6)]
            correct = max(set(nums), key=nums.count)
            text = f"Find the mode of: {', '.join(map(str, nums))}"
            distractors = _make_distractors(correct, spread=2)
            explanation = f"{correct} appears more often than any other number in the list."
        elif kind == "median":
            display_nums = sorted(nums, key=lambda x: random.random())
            correct = sorted(nums)[len(nums) // 2]
            text = f"Find the median of: {', '.join(map(str, display_nums))}"
            distractors = _make_distractors(correct, spread=3)
            explanation = f"Arranged in order: {', '.join(map(str, sorted(nums)))}. The middle value is {correct}."
        elif kind == "range":
            correct = max(nums) - min(nums)
            text = f"Find the range of: {', '.join(map(str, nums))}"
            distractors = _make_distractors(correct, spread=3)
            explanation = f"Range = largest - smallest = {max(nums)} - {min(nums)} = {correct}."
        else:
            total = random.choice([200, 240, 300, 360])
            pct = random.choice([10, 20, 25, 30, 40])
            correct = total * pct // 100
            text = (f"A pie chart shows survey results from {total} people. "
                    f"One sector represents {pct}% of the total. How many people does that sector represent?")
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
            explanation = f"{pct}% of {total} = ({pct}/100) × {total} = {correct} people."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_word_problems(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["multi_step_money", "multi_step_sharing", "leftover", "comparison"])
        if kind == "multi_step_money":
            price = random.choice([250, 320, 450, 599, 750])
            qty = random.randint(2, 6)
            discount_pct = random.choice([10, 20, 25])
            subtotal = price * qty
            discount_amt = subtotal * discount_pct // 100
            correct = subtotal - discount_amt
            text = (f"A shop sells pens for {price}p each. Priya buys {qty} pens and gets a "
                    f"{discount_pct}% discount on the total. How much does she pay, in pence?")
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
            explanation = f"{qty} pens cost {qty} × {price}p = {subtotal}p. {discount_pct}% off = {discount_amt}p, leaving {correct}p."
        elif kind == "multi_step_sharing":
            total = random.choice([144, 180, 216, 252, 288])
            people = random.randint(3, 8)
            correct = total // people
            text = f"{total} sweets are shared equally between {people} children. How many does each child get?"
            distractors = _make_distractors(correct, spread=3)
            explanation = f"{total} ÷ {people} = {correct} each."
        elif kind == "leftover":
            total = random.randint(50, 300)
            group = random.randint(6, 15)
            correct = total % group
            text = f"{total} pupils need to be put into groups of {group}. How many pupils are left over after making full groups?"
            distractors = _make_distractors(correct, spread=2)
            explanation = f"{total} ÷ {group} = {total // group} remainder {correct}, so {correct} pupils are left over."
        else:
            a = random.randint(100, 500)
            b = random.randint(100, 500)
            correct = abs(a - b)
            text = f"School A raised £{a} for charity and School B raised £{b}. What is the difference between the two amounts?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
            explanation = f"Difference = larger - smaller = £{max(a,b)} - £{min(a,b)} = £{correct}."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_speed_distance_time(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["find_time", "find_distance", "find_speed"])
        if kind == "find_time":
            speed = random.choice([40, 50, 60, 80])
            distance = speed * random.choice([1, 2, 3, 4])
            correct = distance / speed
            text = f"A car travels {distance} miles at a speed of {speed} mph. How many hours does the journey take?"
            distractors = _make_distractors(correct, spread=1)
            explanation = f"Time = distance ÷ speed = {distance} ÷ {speed} = {correct} hours."
        elif kind == "find_distance":
            speed = random.choice([30, 40, 50, 60])
            time_h = random.choice([1, 1.5, 2, 3])
            correct = speed * time_h
            text = f"A train travels at {speed} mph for {time_h} hours. How far does it travel?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
            explanation = f"Distance = speed × time = {speed} × {time_h} = {correct} miles."
        else:
            distance = random.choice([60, 90, 120, 150, 200])
            time_h = random.choice([1, 2, 3])
            correct = distance / time_h
            text = f"A cyclist travels {distance} km in {time_h} hours. What is their average speed in km/h?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
            explanation = f"Speed = distance ÷ time = {distance} ÷ {time_h} = {correct} km/h."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_sequences(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["arithmetic_next", "geometric_next", "missing_term"])
        if kind == "arithmetic_next":
            start = random.randint(1, 20)
            step = random.randint(2, 12)
            terms = [start + step * k for k in range(5)]
            correct = start + step * 5
            text = f"What is the next number in the sequence: {', '.join(map(str, terms))}, ?"
            distractors = _make_distractors(correct, spread=step)
            explanation = f"Each term increases by {step}, so the next term is {terms[-1]} + {step} = {correct}."
        elif kind == "geometric_next":
            start = random.choice([1, 2, 3])
            ratio_val = random.choice([2, 3])
            terms = [start * (ratio_val ** k) for k in range(4)]
            correct = start * (ratio_val ** 4)
            text = f"What is the next number in the sequence: {', '.join(map(str, terms))}, ?"
            distractors = _make_distractors(correct, spread=max(1, correct * 0.3))
            explanation = f"Each term is multiplied by {ratio_val}, so the next term is {terms[-1]} × {ratio_val} = {correct}."
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
            explanation = f"The sequence increases by {step} each time, so the missing term is {correct}."
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_top_school_reasoning(index: int) -> tuple:
    """Multi-step / non-routine reasoning questions modeled on the style
    that distinguishes super-selective grammar schools' maths papers from
    standard GL Assessment papers: combining two skills, working backwards,
    or requiring a short logical deduction rather than a single calculation.
    All questions are originally constructed here, not copied from any
    real paper.
    """
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice([
            "reverse_digit_puzzle", "work_backwards_money", "calendar_reasoning",
            "two_step_percentage", "lcm_deduction",
        ])
        if kind == "reverse_digit_puzzle":
            t = random.randint(1, 4)
            u = random.randint(t + 1, 9)
            original = 10 * t + u
            reversed_num = 10 * u + t
            diff = reversed_num - original
            digit_sum = t + u
            correct = original
            text = (f"I am a two-digit number. My digits add up to {digit_sum}. When my digits "
                    f"are reversed, the new number is {diff} more than me. What number am I?")
            distractors = list({reversed_num, original + 9, original - 9, digit_sum * 10} - {correct})
            while len(distractors) < 4:
                distractors.append(original + len(distractors) + 1)
            explanation = (f"Let the tens digit be {t} and units digit be {u} (they add to {digit_sum}). "
                            f"The number is {original}; reversed it's {reversed_num}, which is {diff} more. "
                            f"So the number is {correct}.")
        elif kind == "work_backwards_money":
            remaining = random.choice([2, 3, 4, 5, 6, 8, 10])
            spent = random.choice([3, 4, 5, 6, 7, 8])
            correct = 2 * (remaining + spent)
            text = (f"Tom spent half of his money on a book, then spent £{spent} on a pen, "
                    f"and had £{remaining} left. How much money did he start with?")
            distractors = _make_distractors(correct, spread=max(2, correct * 0.15))
            explanation = (f"Before buying the pen he had £{remaining}+£{spent}=£{remaining+spent}; "
                            f"this was half his money, so he started with 2 × £{remaining+spent} = £{correct}.")
        elif kind == "calendar_reasoning":
            days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            d = random.randint(9, 30)
            idx = (d - 1) % 7
            correct = days_names[idx]
            text = f"If the 1st of a month falls on a Monday, what day of the week is the {d}th?"
            distractors = [day for day in days_names if day != correct]
            random.shuffle(distractors)
            distractors = distractors[:4]
            explanation = (f"There are {d-1} days between the 1st and the {d}th. "
                            f"{d-1} ÷ 7 leaves a remainder of {idx} (counting Monday as 0), which is {correct}.")
        elif kind == "two_step_percentage":
            price = random.choice([40, 50, 60, 80, 100, 120])
            pct1 = random.choice([10, 20, 25])
            pct2 = random.choice([10, 20, 25])
            step1 = price * (100 + pct1) // 100
            correct = step1 * (100 - pct2) // 100
            text = (f"A shop increases the price of a £{price} jacket by {pct1}%, then later "
                    f"decreases the new price by {pct2}%. What is the final price, in pounds?")
            distractors = _make_distractors(correct, spread=max(1, correct * 0.1))
            explanation = (f"Increase: £{price} × {100+pct1}/100 = £{step1}. "
                            f"Decrease: £{step1} × {100-pct2}/100 = £{correct}. "
                            f"Note the two percentages don't cancel out, because the second is applied to a different amount.")
        else:  # lcm_deduction
            m1, m2 = random.choice([(4, 6), (3, 8), (6, 9), (4, 10), (5, 6)])
            lcm_val = m1 * m2 // math.gcd(m1, m2)
            k = random.randint(3, 8)
            correct = lcm_val * k
            lo = correct - random.randint(1, lcm_val - 1)
            hi = correct + random.randint(1, lcm_val - 1)
            text = (f"A number is greater than {lo} and less than {hi}. It is a multiple of "
                    f"both {m1} and {m2}. What is the number?")
            distractors = list({lo, hi, lcm_val, correct + lcm_val} - {correct})
            while len(distractors) < 4:
                distractors.append(correct + lcm_val * (len(distractors) + 2))
            explanation = (f"The number must be a multiple of both {m1} and {m2}, so it's a multiple "
                            f"of {lcm_val}. The only multiple of {lcm_val} strictly between {lo} and {hi} is {correct}.")
        block, record = _build_question(i, text, correct, distractors[:4], explanation, difficulty="selective")
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


TOPIC_GENERATORS = {
    "Number: Arithmetic & Mental Maths": _gen_arithmetic,
    "Number: Fractions, Decimals & Percentages": _gen_fdp,
    "Number: Primes, Factors & Multiples": _gen_primes_factors,
    "Non-Routine Reasoning (Top-School Style)": _gen_top_school_reasoning,
    "Ratio and Proportion": _gen_ratio,
    "Algebra Basics": _gen_algebra,
    "Shape, Space and Measures": _gen_shape_space_measures,
    "Data Handling and Graphs": _gen_data_handling,
    "Worded Problem Solving": _gen_word_problems,
    "Speed, Distance and Time": _gen_speed_distance_time,
    "Sequences and Patterns": _gen_sequences,
}


def generate_11plus_homework(topic: str, index: int) -> tuple:
    """Generate one 11+ maths worksheet (10 MCQ questions) for a given topic.

    Returns:
        (content, answer_records) where content is the student-facing
        worksheet text (no answers) and answer_records is a list of dicts
        - one per question - suitable for AI grading/explanation.
    """
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ topic: {topic}")
    body, answer_records = generator(index)
    header = (
        f"11+ Maths Practice (GL Assessment style) - {topic} (Set {index})\n"
        f"Answer each question by choosing the correct option A-E.\n\n"
    )
    return header + body, answer_records


# ---------------------------------------------------------------------------
# Batch generation / RAG store integration (mirrors generate_all_math_homework.py)
# ---------------------------------------------------------------------------
def _weighted_topic_sequence(count: int) -> list:
    """Build a topic list of length `count`, respecting the weights in
    ELEVEN_PLUS_TOPICS so Number topics appear ~5x more often (matching the
    real GL Assessment question mix), then re-ordered so that top-school
    reasoning sets are placed first - i.e. "top school's questions go
    first" - while everything else keeps its random relative order
    (Python's sort is stable, so ties don't get reshuffled).
    """
    topics, weights = zip(*ELEVEN_PLUS_TOPICS)
    sequence = random.choices(topics, weights=weights, k=count)
    sequence.sort(key=lambda t: TOPIC_ORDER_PRIORITY.get(t, DEFAULT_ORDER_PRIORITY))
    return sequence


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
    """生成指定数量的 11+ 数学练习。

    Topic order within the batch is controlled by _weighted_topic_sequence:
    Number topics dominate by volume (5x weight, matching real GL papers),
    and Top-School-style reasoning sets are placed first in the sequence
    (doc_id 001 onward) so the most exam-differentiating practice surfaces
    first when a student or tutor pulls from this batch.
    """
    topic_sequence = _weighted_topic_sequence(count)
    batch_data = []

    for i, topic in enumerate(topic_sequence, start=1):
        content, answer_records = generate_11plus_homework(topic, i)

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "Maths",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "school_tier": TOPIC_SCHOOL_TIER.get(topic, DEFAULT_SCHOOL_TIER),
            "question_format": "multiple_choice_5_options",
            "student_id": None,
            # Structured, per-question answer key (JSON): correct letter,
            # correct value, worked explanation, and difficulty - built for
            # an AI tutor to grade AND explain, not just letter-match.
            "correct_answers": json.dumps(answer_records, ensure_ascii=False),
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

    print("\n开始生成 11+ Maths 练习 (GL Assessment 风格 + Top-School 推理题, MCQ, "
          "Number 主题加权, Top-School 题目优先排序)...")
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