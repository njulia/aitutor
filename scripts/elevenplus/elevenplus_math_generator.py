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

from src.elevenplus_rag import get_elevenplus_rag_store
from scripts.homework_generator_utils import count_year_homework, add_homework_in_batches, get_rag_stats


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
            text = f"Calculate the sum: {a} + {b} = ?"
            explanation = (
                f"Use column addition to add the numbers:\n"
                f"  {a:4d}\n"
                f"+ {b:4d}\n"
                f"------\n"
                f"  {correct:4d}\n"
                f"------\n"
                f"Align the place values (ones, tens, hundreds, thousands) and add from right to left, carrying over to the next column where necessary."
            )
        elif op == "-":
            a = random.randint(500, 9999)
            b = random.randint(100, a)
            correct = a - b
            text = f"Calculate the difference: {a} - {b} = ?"
            explanation = (
                f"Use column subtraction to subtract the numbers:\n"
                f"  {a:4d}\n"
                f"- {b:4d}\n"
                f"------\n"
                f"  {correct:4d}\n"
                f"------\n"
                f"Align the place values and subtract from right to left, borrowing/exchanging from the left column when a top digit is smaller than the bottom one."
            )
        elif op == "×":
            a, b = random.randint(12, 99), random.randint(2, 12)
            correct = a * b
            text = f"Solve the multiplication: {a} × {b} = ?"
            explanation = (
                f"To calculate {a} × {b}:\n"
                f"1) Partition {a} into tens and ones: {a} = {a - a % 10} + {a % 10}.\n"
                f"2) Multiply each part by {b}:\n"
                f"   - {a - a % 10} × {b} = {(a - a % 10) * b}\n"
                f"   - {a % 10} × {b} = {a % 10 * b}\n"
                f"3) Add the results together: {(a - a % 10) * b} + {a % 10 * b} = {correct}."
            )
        elif op == "÷":
            b = random.randint(2, 12)
            result = random.randint(10, 99)
            a = b * result
            correct = result
            text = f"Solve the division: {a} ÷ {b} = ?"
            explanation = (
                f"To solve {a} ÷ {b}, find how many times {b} goes into {a}:\n"
                f"1) {b} goes into {a - a % 10} exactly {(a - a % 10) // b} times.\n"
                f"2) This leaves a remainder of {a % 10}.\n"
                f"3) {b} goes into {a % 10} exactly {(a % 10) // b} times.\n"
                f"Combining these, {a} ÷ {b} = {correct}.\n"
                f"You can double check your answer by multiplying: {b} × {correct} = {a}."
            )
        else:
            a, b, c = random.randint(10, 50), random.randint(2, 9), random.randint(5, 40)
            correct = a * b - c
            text = f"Solve the multi-step equation: ({a} × {b}) - {c} = ?"
            explanation = (
                f"Following the BIDMAS/BODMAS order of operations (Brackets, Indices, Division/Multiplication, Addition/Subtraction):\n"
                f"1) Solve the multiplication inside the brackets first: {a} × {b} = {a * b}.\n"
                f"2) Next, perform the subtraction outside the brackets: {a * b} - {c} = {correct}."
            )
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
            explanation = (
                f"To find a fraction of a quantity, divide the quantity by the denominator, then multiply by the numerator:\n"
                f"1) Divide by the denominator: {whole} ÷ {denom} = {whole // denom}.\n"
                f"2) Multiply by the numerator: {whole // denom} × {num} = {correct}.\n"
                f"Therefore, {num}/{denom} of {whole} is {correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, abs(correct) * 0.15))
        elif kind == "pct_of":
            pct = random.choice([10, 15, 20, 25, 30, 40, 60, 75])
            whole = random.choice([40, 60, 80, 120, 160, 200, 240])
            correct = pct * whole // 100
            text = f"What is {pct}% of {whole}?"
            if pct == 10:
                shortcut = f"Find 10% by dividing by 10: {whole} ÷ 10 = {correct}."
            elif pct == 20:
                shortcut = f"Find 10% first: {whole} ÷ 10 = {whole // 10}.\nThen multiply by 2 for 20%: {whole // 10} × 2 = {correct}."
            elif pct == 30:
                shortcut = f"Find 10% first: {whole} ÷ 10 = {whole // 10}.\nThen multiply by 3 for 30%: {whole // 10} × 3 = {correct}."
            elif pct == 40:
                shortcut = f"Find 10% first: {whole} ÷ 10 = {whole // 10}.\nThen multiply by 4 for 40%: {whole // 10} × 4 = {correct}."
            elif pct == 60:
                shortcut = f"Find 50% (half of {whole}): {whole // 2}.\nFind 10% of {whole}: {whole // 10}.\nAdd them together for 60%: {whole // 2} + {whole // 10} = {correct}."
            elif pct == 25:
                shortcut = f"Find 25% by dividing by 4 (halving and halving again): {whole} ÷ 4 = {correct}."
            elif pct == 75:
                shortcut = f"Find 25% first by dividing by 4: {whole} ÷ 4 = {whole // 4}.\nMultiply by 3 for 75%: {whole // 4} × 3 = {correct}."
            elif pct == 15:
                shortcut = f"Find 10% first: {whole} ÷ 10 = {whole // 10}.\nFind 5% by halving the 10% value: {whole // 10} ÷ 2 = {whole // 20}.\nAdd them together for 15%: {whole // 10} + {whole // 20} = {correct}."
            else:
                shortcut = f"Multiply by the fraction: ({pct}/100) × {whole} = {correct}."
            explanation = (
                f"To find {pct}% of {whole}, use a smart mental method:\n"
                f"{shortcut}\n"
                f"Therefore, {pct}% of {whole} is {correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, abs(correct) * 0.15))
        elif kind == "dec_to_pct":
            dec = random.choice([0.05, 0.1, 0.15, 0.2, 0.25, 0.4, 0.6, 0.75])
            correct_val = round(dec * 100)
            correct = f"{correct_val}%"
            text = f"Express {dec} as a percentage."
            explanation = (
                f"To convert a decimal to a percentage, multiply by 100 and add the % sign:\n"
                f"{dec} × 100 = {correct_val}%."
            )
            # Custom distractors for percentages to avoid numeric formatting issues
            distractors = [f"{correct_val // 10}%", f"{correct_val * 10}%", f"{correct_val + 5}%", f"{correct_val - 2 if correct_val > 2 else correct_val + 15}%"]
            # Ensure unique options
            distractors = list(set(distractors) - {correct})[:4]
            while len(distractors) < 4:
                distractors.append(f"{correct_val + len(distractors) + 1}%")
        elif kind == "frac_to_dec":
            pairs = {2: 0.5, 4: 0.25, 5: 0.2, 8: 0.125, 10: 0.1, 20: 0.05}
            denom = random.choice(list(pairs.keys()))
            correct = pairs[denom]
            text = f"Write 1/{denom} as a decimal."
            explanation = (
                f"To write a fraction as a decimal, divide the numerator by the denominator:\n"
                f"1 ÷ {denom} = {correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, abs(correct) * 0.15))
        else:
            start = random.choice([40, 60, 80, 100, 120])
            pct = random.choice([10, 20, 25, 50])
            direction = random.choice(["increase", "decrease"])
            if direction == "increase":
                correct = start + start * pct // 100
                text = f"Increase {start} by {pct}%."
                explanation = (
                    f"First calculate {pct}% of {start}:\n"
                    f"1) {pct}% of {start} = {start * pct // 100}.\n"
                    f"2) Add this increase to the original amount: {start} + {start * pct // 100} = {correct}."
                )
            else:
                correct = start - start * pct // 100
                text = f"Decrease {start} by {pct}%."
                explanation = (
                    f"First calculate {pct}% of {start}:\n"
                    f"1) {pct}% of {start} = {start * pct // 100}.\n"
                    f"2) Subtract this decrease from the original amount: {start} - {start * pct // 100} = {correct}."
                )
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
                explanation = (
                    f"{n} is a prime number because it has exactly two factors: 1 and itself.\n"
                    f"It cannot be divided exactly by any other whole number."
                )
            else:
                factor = next(p for p in range(2, n) if n % p == 0)
                explanation = (
                    f"{n} is NOT a prime number (it is a composite number) because it has more than two factors.\n"
                    f"For example, it can be divided exactly by {factor}: {n} ÷ {factor} = {n // factor}."
                )
        elif kind == "hcf":
            a, b = random.choice([(12, 18), (24, 36), (15, 25), (16, 40), (20, 30), (18, 24)])
            correct = math.gcd(a, b)
            text = f"What is the Highest Common Factor (HCF) of {a} and {b}?"
            factors_a = [x for x in range(1, a + 1) if a % x == 0]
            factors_b = [x for x in range(1, b + 1) if b % x == 0]
            common = sorted(list(set(factors_a) & set(factors_b)))
            explanation = (
                f"To find the Highest Common Factor (HCF) of {a} and {b}:\n"
                f"1) List the factors of {a}: {', '.join(map(str, factors_a))}.\n"
                f"2) List the factors of {b}: {', '.join(map(str, factors_b))}.\n"
                f"3) Identify the common factors: {', '.join(map(str, common))}.\n"
                f"4) Choose the largest number that appears in both lists, which is {correct}.\n"
                f"Therefore, the HCF of {a} and {b} is {correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.5))
        elif kind == "lcm":
            a, b = random.choice([(4, 6), (3, 5), (6, 8), (4, 10), (5, 6), (8, 12)])
            correct = a * b // math.gcd(a, b)
            text = f"What is the Lowest Common Multiple (LCM) of {a} and {b}?"
            multiples_a = [a * x for x in range(1, 7)]
            multiples_b = [b * x for x in range(1, 7)]
            explanation = (
                f"To find the Lowest Common Multiple (LCM) of {a} and {b}:\n"
                f"1) List the first few multiples of {a}: {', '.join(map(str, multiples_a))}...\n"
                f"2) List the first few multiples of {b}: {', '.join(map(str, multiples_b))}...\n"
                f"3) Find the smallest multiple that is in both lists, which is {correct}.\n"
                f"Therefore, the LCM of {a} and {b} is {correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.4))
        elif kind == "factor_count":
            n = random.choice([12, 16, 18, 20, 24, 28, 30, 36])
            correct = sum(1 for d in range(1, n + 1) if n % d == 0)
            text = f"How many factors does the number {n} have?"
            factors = [x for x in range(1, n + 1) if n % x == 0]
            explanation = (
                f"To find how many factors {n} has, we find all the whole numbers that divide into {n} exactly:\n"
                f"The factors of {n} are: {', '.join(map(str, factors))}.\n"
                f"Counting them, there are exactly {correct} factors."
            )
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
            explanation = (
                f"To write {n} as a product of prime factors, we perform repeated division by prime numbers:\n"
                f"1) {n} ÷ {factors[0]} = {n // factors[0]}\n"
                + "\n".join(f"2) {n // np} ÷ {nf} = {n // np // nf}" for np, nf in zip([1] + factors[:-2], factors[1:-1]) if len(factors) > 2) + "\n"
                f"The prime factors are: {', '.join(map(str, factors))}.\n"
                f"Multiplying them together gives: {correct} = {n}."
            )
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
            text = f"Simplify the ratio {a}:{b} to its simplest form."
            distractors = [f"{base_a+1}:{base_b}", f"{base_a}:{base_b+1}", f"{a}:{b}", f"{base_b}:{base_a}"]
            explanation = (
                f"To simplify the ratio {a}:{b}:\n"
                f"1) Find the Highest Common Factor (HCF) of {a} and {b}, which is {k}.\n"
                f"2) Divide both parts of the ratio by {k}:\n"
                f"   - {a} ÷ {k} = {base_a}\n"
                f"   - {b} ÷ {k} = {base_b}\n"
                f"The simplified ratio is {correct}."
            )
        elif kind == "share":
            r1, r2 = random.choice([(2, 3), (1, 4), (3, 5), (2, 5), (1, 2)])
            total = (r1 + r2) * random.randint(3, 12)
            per_part = total // (r1 + r2)
            correct = per_part * r1
            text = f"Share £{total} in the ratio {r1}:{r2}. How much is the first (smaller) share?"
            explanation = (
                f"To share £{total} in the ratio {r1}:{r2}:\n"
                f"1) Find the total number of parts: {r1} + {r2} = {r1+r2} parts.\n"
                f"2) Find the value of one part: £{total} ÷ {r1+r2} = £{per_part}.\n"
                f"3) Find the first share ({r1} parts): {r1} × £{per_part} = £{correct}.\n"
                f"4) Find the second share ({r2} parts): {r2} × £{per_part} = £{per_part * r2}.\n"
                f"The shares are £{correct} and £{per_part * r2}."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.3))
        elif kind == "scale_recipe":
            people_from = random.choice([2, 4, 5])
            people_to = random.choice([6, 8, 10, 12])
            amount = random.choice([100, 150, 200, 250, 300])
            correct = amount * people_to // people_from
            text = f"A baking recipe for {people_from} people requires {amount}g of flour. How much flour is needed to make the same recipe for {people_to} people?"
            explanation = (
                f"To scale the recipe from {people_from} people to {people_to} people:\n"
                f"1) Find the scaling factor: {people_to} ÷ {people_from} = {people_to / people_from}.\n"
                f"2) Multiply the amount of flour by the scaling factor: {amount}g × {people_to / people_from} = {correct}g.\n"
                f"Therefore, {correct}g of flour is needed."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
        else:
            scale = random.choice([10000, 25000, 50000])
            cm = random.randint(2, 15)
            correct_m = cm * scale // 100
            correct = f"{correct_m} m"
            text = f"On a map with a scale of 1:{scale}, two school fields are {cm} cm apart. What is the actual distance in metres?"
            distractors = [f"{correct_m + 50} m", f"{correct_m - 50} m", f"{correct_m * 10} m", f"{correct_m // 10} m"]
            explanation = (
                f"To find the actual distance from the map scale of 1:{scale}:\n"
                f"1) Multiply the map distance by the scale factor: {cm} cm × {scale} = {cm * scale} cm.\n"
                f"2) Convert the real distance from cm to metres (divide by 100): {cm * scale} ÷ 100 = {correct_m} m.\n"
                f"Therefore, the real distance is {correct}."
            )
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
            text = f"Find the value of x: {coeff}x + {add} = {result}"
            explanation = (
                f"To solve the equation {coeff}x + {add} = {result} for x:\n"
                f"1) Subtract {add} from both sides to isolate the term with x:\n"
                f"   {coeff}x = {result} - {add}\n"
                f"   {coeff}x = {result - add}\n"
                f"2) Divide both sides by {coeff} to find x:\n"
                f"   x = {result - add} ÷ {coeff}\n"
                f"   x = {correct}"
            )
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
            text = f"If a = {a_val} and b = {b_val}, evaluate the algebraic expression: {expr_choice}"
            explanation = (
                f"Substitute a = {a_val} and b = {b_val} into the expression '{expr_choice}':\n"
                f"We replace 'a' with {a_val} and 'b' with {b_val}:\n"
                f"   - Expression: {expr_choice}\n"
                f"   - Calculation: {correct}\n"
                f"Therefore, the value of the expression is {correct}."
            )
            distractors = _make_distractors(correct, spread=3)
        elif kind == "sequence_nth":
            start = random.randint(1, 10)
            step = random.randint(2, 8)
            correct = f"{step}n + {start - step}"
            terms = [start + step * k for k in range(4)]
            text = f"Find the general nth term expression for this sequence: {', '.join(map(str, terms))}, ..."
            distractors = [
                f"{step}n + {start}",
                f"{step + 1}n + {start - step}",
                f"n + {step}",
                f"{step}n - {start}",
            ]
            explanation = (
                f"To find the nth term of the sequence {', '.join(map(str, terms))}:\n"
                f"1) Find the common difference between consecutive terms: {terms[1]} - {terms[0]} = {step}.\n"
                f"   This tells us the rule involves '{step}n'.\n"
                f"2) Test the first term (n = 1) with '{step}n': {step} × 1 = {step}.\n"
                f"3) Find the adjustment needed to reach the actual first term ({start}):\n"
                f"   We need to go from {step} to {start}, which is an adjustment of: {start - step}.\n"
                f"4) Combine these into the formula: {correct}."
            )
        else:
            mult = random.randint(2, 6)
            add = random.randint(1, 10)
            correct = f"{mult}x + {mult * add}"
            text = f"Expand the single bracket: {mult}(x + {add})"
            distractors = [f"{mult}x + {add}", f"x + {mult * add}", f"{mult}x + {add * 2}", f"{mult + 1}x + {mult * add}"]
            explanation = (
                f"To expand {mult}(x + {add}):\n"
                f"Multiply the number outside the bracket ({mult}) by each term inside the bracket:\n"
                f"1) Multiply by x: {mult} × x = {mult}x.\n"
                f"2) Multiply by {add}: {mult} × {add} = {mult * add}.\n"
                f"Combining these gives: {correct}."
            )
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
            text = f"A rectangular playground measures {l}m by {w}m. What is its total area in square metres?"
            explanation = (
                f"To find the area of a rectangle:\n"
                f"Area = Length × Width\n"
                f"Area = {l} m × {w} m = {correct} m²."
            )
        elif kind == "perimeter_rect":
            l, w = random.randint(4, 20), random.randint(3, 15)
            correct = 2 * (l + w)
            text = f"A rectangle has a length of {l}cm and a width of {w}cm. What is its perimeter in centimetres?"
            explanation = (
                f"To find the perimeter of a rectangle:\n"
                f"Perimeter = 2 × (Length + Width)\n"
                f"Perimeter = 2 × ({l} cm + {w} cm) = 2 × {l + w} cm = {correct} cm."
            )
        elif kind == "angle_triangle":
            a1 = random.randint(30, 100)
            a2 = random.randint(30, 100)
            while a1 + a2 >= 170:
                a2 = random.randint(20, 80)
            correct = 180 - a1 - a2
            text = f"Two angles in a triangle measure {a1}° and {a2}°. Calculate the size of the third missing angle."
            explanation = (
                f"To find the third angle of a triangle:\n"
                f"1) The sum of all angles in any triangle is always 180°.\n"
                f"2) Add the two known angles: {a1}° + {a2}° = {a1 + a2}°.\n"
                f"3) Subtract the sum from 180°: 180° - {a1 + a2}° = {correct}°.\n"
                f"Therefore, the third angle is {correct}°."
            )
        elif kind == "area_triangle":
            base, height = random.randint(4, 20), random.randint(3, 16)
            # Ensure area is a clean integer or at most ends in .5, but base*height//2 is fine here
            correct = base * height // 2
            text = f"A triangle has a base of {base}cm and a vertical height of {height}cm. What is its area in cm²?"
            explanation = (
                f"To find the area of a triangle:\n"
                f"Area = (Base × Height) ÷ 2\n"
                f"Area = ({base} cm × {height} cm) ÷ 2 = {base * height} cm² ÷ 2 = {correct} cm²."
            )
        else:
            unit_pairs = [("cm", "m", 100), ("m", "km", 1000), ("g", "kg", 1000), ("ml", "l", 1000)]
            frm, to, factor = random.choice(unit_pairs)
            value = random.choice([1, 2, 3, 4, 5]) * factor
            correct = value // factor
            text = f"Convert {value} {frm} into {to}."
            explanation = (
                f"To convert {value} {frm} to {to}:\n"
                f"1) We know that 1 {to} is equal to {factor} {frm}.\n"
                f"2) Since we are converting from a smaller unit ({frm}) to a larger unit ({to}), we divide:\n"
                f"   {value} ÷ {factor} = {correct}.\n"
                f"Therefore, {value} {frm} = {correct} {to}."
            )
        distractors = _make_distractors(correct, spread=max(2, correct * 0.15))
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
            text = f"Calculate the mean (average) of these test scores: {', '.join(map(str, nums))}"
            explanation = (
                f"To find the mean of the scores: {', '.join(map(str, nums))}:\n"
                f"1) Find the sum of all values: { ' + '.join(map(str, nums)) } = {sum(nums)}.\n"
                f"2) Divide the sum by the total count of values ({len(nums)}):\n"
                f"   {sum(nums)} ÷ {len(nums)} = {correct}.\n"
                f"Therefore, the mean is {correct}."
            )
            distractors = _make_distractors(correct, spread=3)
        elif kind == "mode":
            nums = [random.choice([3, 5, 7, 9]) for _ in range(6)]
            correct = max(set(nums), key=nums.count)
            text = f"Find the mode of the following data set: {', '.join(map(str, nums))}"
            explanation = (
                f"To find the mode of the numbers: {', '.join(map(str, nums))}:\n"
                f"The mode is the number that appears most frequently.\n"
                f"Count of occurrences:\n"
                + "\n".join(f"  - {val}: {nums.count(val)} time(s)" for val in sorted(list(set(nums)))) + "\n"
                f"The number with the highest count is {correct}, which appears {nums.count(correct)} times."
            )
            distractors = _make_distractors(correct, spread=2)
        elif kind == "median":
            display_nums = sorted(nums, key=lambda x: random.random())
            correct = sorted(nums)[len(nums) // 2]
            sorted_nums = sorted(nums)
            text = f"What is the median of this data set: {', '.join(map(str, display_nums))}?"
            explanation = (
                f"To find the median of the numbers: {', '.join(map(str, display_nums))}:\n"
                f"1) Arrange the numbers in ascending order: {', '.join(map(str, sorted_nums))}.\n"
                f"2) Locate the middle value. Since there are {len(nums)} numbers (an odd number), the middle position is at index {len(nums)//2 + 1}.\n"
                f"The number at this middle position is {correct}."
            )
            distractors = _make_distractors(correct, spread=3)
        elif kind == "range":
            correct = max(nums) - min(nums)
            text = f"What is the range of this data set: {', '.join(map(str, nums))}?"
            explanation = (
                f"To find the range of the numbers: {', '.join(map(str, nums))}:\n"
                f"1) Identify the largest value: {max(nums)}.\n"
                f"2) Identify the smallest value: {min(nums)}.\n"
                f"3) Subtract the smallest from the largest: {max(nums)} - {min(nums)} = {correct}.\n"
                f"Therefore, the range is {correct}."
            )
            distractors = _make_distractors(correct, spread=3)
        else:
            total = random.choice([200, 240, 300, 360])
            pct = random.choice([10, 20, 25, 30, 40])
            correct = total * pct // 100
            text = (f"A school pie chart surveys {total} children. "
                    f"One sector representing 'Cycling to School' measures {pct}% of the total. How many children cycle to school?")
            explanation = (
                f"To find how many people are represented by {pct}% of a pie chart of {total} people:\n"
                f"1) Calculate {pct}% of {total}:\n"
                f"   ({pct} ÷ 100) × {total} = {correct} children.\n"
                f"Therefore, that sector represents {correct} children."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
        block, record = _build_question(i, text, correct, distractors[:4], explanation)
        blocks.append(block)
        records.append(record)
    return "\n\n".join(blocks), records


def _gen_word_problems(index: int) -> tuple:
    blocks, records = [], []
    for i in range(1, 11):
        kind = random.choice(["multi_step_money", "multi_step_sharing", "leftover", "comparison"])
        if kind == "multi_step_money":
            price = random.choice([250, 320, 450, 500, 750])
            qty = random.randint(2, 6)
            discount_pct = random.choice([10, 20, 25])
            subtotal = price * qty
            discount_amt = subtotal * discount_pct // 100
            correct = subtotal - discount_amt
            text = (f"A shop sells geometry sets for {price}p each. Priya buys {qty} sets and receives a "
                    f"bulk discount of {discount_pct}% off. How much does she pay in total (in pence)?")
            explanation = (
                f"Let's calculate the total cost step-by-step:\n"
                f"1) Cost of {qty} sets before discount: {qty} × {price}p = {subtotal}p.\n"
                f"2) Find the discount amount ({discount_pct}% of {subtotal}p):\n"
                f"   ({discount_pct} ÷ 100) × {subtotal}p = {discount_amt}p.\n"
                f"3) Subtract the discount from the subtotal: {subtotal}p - {discount_amt}p = {correct}p.\n"
                f"Therefore, Priya pays {correct}p."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
        elif kind == "multi_step_sharing":
            total = random.choice([144, 180, 216, 252, 288])
            people = random.randint(3, 8)
            correct = total // people
            text = f"A box containing {total} marbles is shared equally among {people} children. How many marbles does each child receive?"
            explanation = (
                f"To share {total} marbles equally between {people} children:\n"
                f"We divide the total number of marbles by the number of children:\n"
                f"   {total} ÷ {people} = {correct}.\n"
                f"Therefore, each child gets {correct} marbles."
            )
            distractors = _make_distractors(correct, spread=3)
        elif kind == "leftover":
            total = random.randint(50, 300)
            group = random.randint(6, 15)
            correct = total % group
            text = f"A group of {total} students are divided into sports teams of exactly {group} students. How many students will be left over without a full team?"
            explanation = (
                f"To find how many pupils are left over when putting {total} pupils into groups of {group}:\n"
                f"1) Perform division: {total} ÷ {group} = {total // group} groups.\n"
                f"2) Find the total number of pupils in these groups: {total // group} × {group} = {total - total % group} pupils.\n"
                f"3) Subtract from the starting total to find the remainder: {total} - {total - total % group} = {correct} leftover pupils.\n"
                f"Therefore, {correct} pupils are left over."
            )
            distractors = _make_distractors(correct, spread=2)
        else:
            a = random.randint(100, 500)
            b = random.randint(100, 500)
            correct = abs(a - b)
            text = f"School A raised £{a} for a charity run, and School B raised £{b}. What is the absolute difference between the amounts raised?"
            explanation = (
                f"To find the difference between School A (£{a}) and School B (£{b}):\n"
                f"Subtract the smaller amount from the larger amount:\n"
                f"   £{max(a, b)} - £{min(a, b)} = £{correct}.\n"
                f"Therefore, the difference is £{correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.2))
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
            correct = distance // speed
            text = f"A delivery van travels {distance} miles at an average constant speed of {speed} mph. How many hours does the journey take?"
            explanation = (
                f"To find the journey time:\n"
                f"Formula: Time = Distance ÷ Speed\n"
                f"Time = {distance} miles ÷ {speed} mph = {correct} hour(s).\n"
                f"Therefore, the journey takes {correct} hour(s)."
            )
            distractors = _make_distractors(correct, spread=1)
        elif kind == "find_distance":
            speed = random.choice([30, 40, 50, 60])
            time_h = random.choice([1, 1.5, 2, 3])
            # Keep distance as clean integer if possible, speed * time_h is clean since speeds are multiples of 10
            correct = int(speed * time_h)
            text = f"A high-speed train travels at a constant velocity of {speed} km/h for exactly {time_h} hours. What total distance does it cover?"
            explanation = (
                f"To find the distance travelled:\n"
                f"Formula: Distance = Speed × Time\n"
                f"Distance = {speed} km/h × {time_h} hours = {correct} km.\n"
                f"Therefore, the distance is {correct} km."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
        else:
            distance = random.choice([60, 90, 120, 150, 200])
            time_h = random.choice([1, 2, 3])
            correct = distance // time_h
            text = f"A marathon cyclist covers a distance of {distance} km in exactly {time_h} hours. What was their average speed in km/h?"
            explanation = (
                f"To find the average speed:\n"
                f"Formula: Speed = Distance ÷ Time\n"
                f"Speed = {distance} km ÷ {time_h} hours = {correct} km/h.\n"
                f"Therefore, the average speed is {correct} km/h."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.15))
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
            text = f"What is the next consecutive term in this sequence: {', '.join(map(str, terms))}, ?"
            explanation = (
                f"To find the next number in the arithmetic sequence {', '.join(map(str, terms))}:\n"
                f"1) Find the common difference between consecutive terms: {terms[1]} - {terms[0]} = {step}.\n"
                f"2) Add this difference to the last term: {terms[-1]} + {step} = {correct}.\n"
                f"Therefore, the next number is {correct}."
            )
            distractors = _make_distractors(correct, spread=step)
        elif kind == "geometric_next":
            start = random.choice([1, 2, 3])
            ratio_val = random.choice([2, 3])
            terms = [start * (ratio_val ** k) for k in range(4)]
            correct = start * (ratio_val ** 4)
            text = f"What is the next term in this multiplicative sequence: {', '.join(map(str, terms))}, ?"
            explanation = (
                f"To find the next number in the geometric sequence {', '.join(map(str, terms))}:\n"
                f"1) Find the common ratio by dividing consecutive terms: {terms[1]} ÷ {terms[0]} = {ratio_val}.\n"
                f"2) Multiply the last term by this ratio: {terms[-1]} × {ratio_val} = {correct}.\n"
                f"Therefore, the next number is {correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.3))
        else:
            start = random.randint(1, 15)
            step = random.randint(2, 10)
            terms = [start + step * k for k in range(5)]
            gap_index = random.randint(1, 3)
            correct = terms[gap_index]
            display = terms.copy()
            display[gap_index] = "?"
            text = f"Find the missing term '?' in this arithmetic progression: {', '.join(map(str, display))}"
            explanation = (
                f"To find the missing term in the sequence {', '.join(map(str, display))}:\n"
                f"1) Find the common difference between adjacent known terms: {terms[gap_index + 1]} - {terms[gap_index - 1]} = {2 * step}, which is 2 × {step}.\n"
                f"2) This tells us the progression increases by {step} each time.\n"
                f"3) Add the difference of {step} to the preceding term: {terms[gap_index - 1]} + {step} = {correct}.\n"
                f"Therefore, the missing number is {correct}."
            )
            distractors = _make_distractors(correct, spread=step)
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
            text = (f"I am a two-digit whole number. My digits add up to {digit_sum}. When my digits "
                    f"are reversed to form a new number, the new number is exactly {diff} greater than me. What number am I?")
            distractors = list({reversed_num, original + 9, original - 9, digit_sum * 10} - {correct})
            while len(distractors) < 4:
                distractors.append(original + len(distractors) + 1)
            explanation = (
                f"Let the tens digit be T and the units digit be U.\n"
                f"1) The sum of the digits is: T + U = {digit_sum}.\n"
                f"2) The value of the original number is 10*T + U.\n"
                f"3) The value of the reversed number is 10*U + T.\n"
                f"4) We are told: (10*U + T) - (10*T + U) = {diff}, which simplifies to: 9*(U - T) = {diff}.\n"
                f"5) Dividing by 9, we get: U - T = {diff} // 9 = {u - t}.\n"
                f"6) Now we have a system of two simple equations:\n"
                f"   - U + T = {digit_sum}\n"
                f"   - U - T = {u - t}\n"
                f"7) Adding these equations gives: 2*U = {digit_sum + (u - t)} => U = {u}.\n"
                f"8) Subtracting them gives: 2*T = {digit_sum - (u - t)} => T = {t}.\n"
                f"So the original number is {correct}."
            )
        elif kind == "work_backwards_money":
            remaining = random.choice([2, 3, 4, 5, 6, 8, 10])
            spent = random.choice([3, 4, 5, 6, 7, 8])
            correct = 2 * (remaining + spent)
            text = (f"Ethan spent half of his savings on a new science book. He then spent £{spent} on "
                    f"some lunch, which left him with exactly £{remaining} in his wallet. How much money did Ethan have initially?")
            distractors = _make_distractors(correct, spread=max(2, correct * 0.15))
            explanation = (
                f"Let's work backwards from the end of the story:\n"
                f"1) Ethan had £{remaining} left at the very end.\n"
                f"2) Before buying lunch which cost £{spent}, he must have had: £{remaining} + £{spent} = £{remaining + spent}.\n"
                f"3) This £{remaining + spent} was what remained after he spent half of his savings on a book. This means £{remaining + spent} represents exactly the other half of his starting savings.\n"
                f"4) To find the total starting amount, we multiply this half by 2: 2 × £{remaining + spent} = £{correct}.\n"
                f"Therefore, Ethan started with £{correct}."
            )
        elif kind == "calendar_reasoning":
            days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            d = random.randint(9, 30)
            idx = (d - 1) % 7
            correct = days_names[idx]
            text = f"If the 1st day of a certain month falls on a Monday, what day of the week will the {d}th day of the same month be?"
            distractors = [day for day in days_names if day != correct]
            random.shuffle(distractors)
            distractors = distractors[:4]
            explanation = (
                f"Let's count the calendar days systematically:\n"
                f"1) The 1st day of the month is a Monday.\n"
                f"2) Days of the week repeat every 7 days, so the 1st, 8th, 15th, 22nd, and 29th are all Mondays.\n"
                f"3) The number of days between the 1st and the {d}th is: {d} - 1 = {d - 1} days.\n"
                f"4) We divide the difference by 7 to find how many full weeks pass: {d - 1} ÷ 7 = {(d - 1) // 7} weeks with a remainder of {idx}.\n"
                f"5) Starting on Monday and counting forward {idx} days gives us: {correct}.\n"
                f"Therefore, the {d}th of the month is a {correct}."
            )
        elif kind == "two_step_percentage":
            # Curated combinations to guarantee integer steps and answers
            combos = [
                (200, 10, 10, "increase", "decrease"), # 200 -> 220 -> 198
                (100, 20, 25, "increase", "decrease"), # 100 -> 120 -> 90
                (120, 25, 20, "increase", "decrease"), # 120 -> 150 -> 120
                (80, 25, 10, "increase", "decrease"),  # 80 -> 100 -> 90
                (150, 20, 15, "increase", "decrease"), # 150 -> 180 -> 153
                (160, 25, 20, "increase", "decrease"), # 160 -> 200 -> 160
                (50, 20, 25, "increase", "decrease"),  # 50 -> 60 -> 45
                (120, 10, 25, "decrease", "increase"), # 120 -> 108 -> 135
                (200, 15, 20, "decrease", "increase"), # 200 -> 170 -> 204
                (80, 20, 25, "decrease", "increase"),  # 80 -> 64 -> 80
            ]
            price, pct1, pct2, dir1, dir2 = random.choice(combos)
            if dir1 == "increase":
                step1 = price + (price * pct1) // 100
                verb1 = f"raises the price of a £{price} coat by {pct1}%"
                expl1 = f"1) First change (increase): {pct1}% of £{price} is £{(price * pct1) // 100}. The new increased price is £{price} + £{(price * pct1) // 100} = £{step1}."
            else:
                step1 = price - (price * pct1) // 100
                verb1 = f"reduces the price of a £{price} coat by {pct1}%"
                expl1 = f"1) First change (reduction): {pct1}% of £{price} is £{(price * pct1) // 100}. The new reduced price is £{price} - £{(price * pct1) // 100} = £{step1}."
                
            if dir2 == "increase":
                correct = step1 + (step1 * pct2) // 100
                verb2 = f"raises this new increased price by {pct2}%"
                expl2 = f"2) Second change (increase): {pct2}% of the new £{step1} price is £{(step1 * pct2) // 100}. The final price is £{step1} + £{(step1 * pct2) // 100} = £{correct}."
            else:
                correct = step1 - (step1 * pct2) // 100
                verb2 = f"reduces this new price by {pct2}% in a clearance sale"
                expl2 = f"2) Second change (reduction): {pct2}% of the new £{step1} price is £{(step1 * pct2) // 100}. The final clearance price is £{step1} - £{(step1 * pct2) // 100} = £{correct}."

            text = f"A shop {verb1}, then later {verb2}. What is the final clearance price of the coat in pounds?"
            explanation = (
                f"Let's break down the two sequential percentage changes step-by-step:\n"
                f"{expl1}\n"
                f"{expl2}\n"
                f"Therefore, the final clearance price of the coat is £{correct}."
            )
            distractors = _make_distractors(correct, spread=max(1, correct * 0.1))
        else:  # lcm_deduction
            m1, m2 = random.choice([(4, 6), (3, 8), (6, 9), (4, 10), (5, 6)])
            lcm_val = m1 * m2 // math.gcd(m1, m2)
            k = random.randint(3, 8)
            correct = lcm_val * k
            lo = correct - random.randint(1, lcm_val - 1)
            hi = correct + random.randint(1, lcm_val - 1)
            text = (f"I am a whole number greater than {lo} and less than {hi}. It is exactly divisible "
                    f"by both {m1} and {m2}. What number am I?")
            distractors = list({lo + 1, hi - 1, lcm_val, correct + lcm_val} - {correct})
            while len(distractors) < 4:
                distractors.append(correct + lcm_val * (len(distractors) + 2))
            explanation = (
                f"Let's solve this logical puzzle step-by-step:\n"
                f"1) The mystery number is a multiple of both {m1} and {m2}. This means it must be a multiple of their Least Common Multiple (LCM).\n"
                f"2) To find the LCM of {m1} and {m2}:\n"
                f"   - Multiples of {m1}: {', '.join(str(m1 * x) for x in range(1, 6))}...\n"
                f"   - Multiples of {m2}: {', '.join(str(m2 * x) for x in range(1, 6))}...\n"
                f"   The smallest common multiple is {lcm_val}.\n"
                f"3) Since the number is a multiple of {lcm_val}, we list the multiples of {lcm_val}:\n"
                f"   {', '.join(str(lcm_val * x) for x in range(1, 10))}...\n"
                f"4) We are told the number is strictly between {lo} and {hi}.\n"
                f"5) Looking at our list of multiples, {correct} is the only multiple of {lcm_val} that is greater than {lo} and less than {hi}.\n"
                f"Therefore, the mystery number is {correct}."
            )
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
    try:
        store = get_elevenplus_rag_store()
        results = store.search(query="maths", k=1, filters={"subject": "Maths"})
        return len(results) > 0
    except Exception:
        return False


def clean_11plus_math() -> int:
    """清理所有已有的 11+ 数学练习"""
    store = get_elevenplus_rag_store()
    results = store.search_by_metadata({"subject": "Maths"})

    if not results:
        print("  没有找到需要清理 of 11+ 作业")
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
    print(f"RAG target: {store.store.database_target}")

    exists = check_11plus_math_exists()
    status = "已有" if exists else "缺失"
    print(f"  11+ Maths: {status}")

    if exists:
        print("\n11+ Maths 练习已存在，无需生成。")
        return

    print("\n开始生成 11+ Maths 练习 (GL Assessment 风格 + Top-School 推理题, MCQ, "
          "Number 主题加权, Top-School 题目优先排序)...")
    batch_data = generate_11plus_batch(count=1000)

    if batch_data:
        added = add_homework_in_batches(store, batch_data)
        print(
            f"11+: added {added} new Maths homework documents; "
            f"target total is {len(batch_data)}"
        )

    get_rag_stats(store)


if __name__ == "__main__":
    main()
