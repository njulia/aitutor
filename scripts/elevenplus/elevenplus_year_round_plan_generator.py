#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ Maths 52-Week Year-Round Plan Generator
===========================================

Generates a comprehensive 52-Week Year-Round study roadmap formulated for
Henrietta Barnett, Tiffin, CSSE, and St Olave's math entrance papers.

Saves the generated plan to:
  - 11_Plus_Maths_52_Week_Plan.json
  - 11_Plus_Maths_52_Week_Plan.md

Also registers them in the RAG vector store for student queries.
"""

import sys
import os
import json
import math
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    get_elevenplus_rag_store = None

# Define the 52-Week Curriculum
CURRICULUM = [
    {
        "termId": 1,
        "termName": "Term 1: Arithmetic & Number Sense Foundations",
        "focus": "Mastering core operations, order of operations, and fundamental properties of numbers.",
        "weeks": [
            {
                "weekNum": 1,
                "topic": "Number: Arithmetic & Mental Maths",
                "focus": "Place Value & Large Number Addition/Subtraction",
                "objectives": [
                    "Understand place value up to millions and decimals.",
                    "Perform precise column addition and subtraction on numbers up to 10,000.",
                    "Identify common borrowing and carrying errors."
                ]
            },
            {
                "weekNum": 2,
                "topic": "Number: Arithmetic & Mental Maths",
                "focus": "Mental Math Shortcuts & Estimation",
                "objectives": [
                    "Use rounding to estimate results of complex calculations.",
                    "Apply mental compensation strategies (e.g., adding 99 by adding 100 and subtracting 1).",
                    "Double-check arithmetic using unit-digit analysis."
                ]
            },
            {
                "weekNum": 3,
                "topic": "Number: Arithmetic & Mental Maths",
                "focus": "Long Multiplication Techniques",
                "objectives": [
                    "Multiply 3-digit numbers by 2-digit numbers using standard column method.",
                    "Understand the grid method and partitioning for visual confirmation.",
                    "Multiply decimals by 10, 100, and 1000."
                ]
            },
            {
                "weekNum": 4,
                "topic": "Number: Arithmetic & Mental Maths",
                "focus": "Short and Long Division (Bus Stop Method)",
                "objectives": [
                    "Master short division with integer and decimal remainders.",
                    "Perform long division by 2-digit numbers using list-of-multiples scaffolding.",
                    "Express remainders as fractions or decimals."
                ]
            },
            {
                "weekNum": 5,
                "topic": "Number: Arithmetic & Mental Maths",
                "focus": "Order of Operations (BODMAS/BIDMAS)",
                "objectives": [
                    "Understand priority of brackets, indices, division/multiplication, and addition/subtraction.",
                    "Evaluate complex multi-step expressions.",
                    "Insert missing brackets to make equations true."
                ]
            },
            {
                "weekNum": 6,
                "topic": "Number: Primes, Factors & Multiples",
                "focus": "Factors, Multiples & Prime Numbers",
                "objectives": [
                    "Define and list factors and multiples of numbers up to 100.",
                    "Identify and memorize prime numbers up to 100.",
                    "Recognize prime and composite numbers under time pressure."
                ]
            },
            {
                "weekNum": 7,
                "topic": "Number: Primes, Factors & Multiples",
                "focus": "Highest Common Factor & Lowest Common Multiple",
                "objectives": [
                    "Find the HCF of two or three numbers using listing and prime factors.",
                    "Find the LCM of two or three numbers using listing and prime factors.",
                    "Solve worded scheduling and grouping problems using LCM/HCF."
                ]
            },
            {
                "weekNum": 8,
                "topic": "Number: Primes, Factors & Multiples",
                "focus": "Square Numbers, Cube Numbers & Roots",
                "objectives": [
                    "Recognize perfect squares up to 15x15 and cubes up to 5x5x5.",
                    "Understand square roots and cube roots as inverse operations.",
                    "Apply squares and cubes to geometric area/volume problems."
                ]
            },
            {
                "weekNum": 9,
                "topic": "Number: Fractions, Decimals & Percentages",
                "focus": "Fractions: Equivalent & Ordering",
                "objectives": [
                    "Simplify fractions to their lowest terms using HCF.",
                    "Find equivalent fractions by multiplying or dividing numerators and denominators.",
                    "Compare and order fractions using common denominators."
                ]
            },
            {
                "weekNum": 10,
                "topic": "Number: Fractions, Decimals & Percentages",
                "focus": "Fractions: Addition & Subtraction",
                "objectives": [
                    "Add and subtract fractions with different denominators.",
                    "Work with mixed numbers and improper fractions.",
                    "Solve real-world fraction sharing word problems."
                ]
            },
            {
                "weekNum": 11,
                "topic": "Number: Fractions, Decimals & Percentages",
                "focus": "Fractions: Multiplication, Division & Quantities",
                "objectives": [
                    "Multiply fractions by integers and other fractions.",
                    "Divide fractions using the reciprocal method (Keep-Change-Flip).",
                    "Calculate fractions of non-routine whole amounts."
                ]
            },
            {
                "weekNum": 12,
                "topic": "Number: Fractions, Decimals & Percentages",
                "focus": "Decimals: Place Value & Conversions",
                "objectives": [
                    "Understand decimal place value up to thousandths.",
                    "Order and compare decimal values.",
                    "Convert simple fractions to decimals and vice versa."
                ]
            },
            {
                "weekNum": 13,
                "topic": "Number: Arithmetic & Mental Maths",
                "focus": "Term 1 Review & Foundations Mastery Test",
                "objectives": [
                    "Synthesize arithmetic, division, primes, and fraction basics.",
                    "Solve 10 exam-style mixed multi-step foundation problems.",
                    "Refine timing: achieve under 45 seconds per question."
                ]
            }
        ]
    },
    {
        "termId": 2,
        "termName": "Term 2: Proportional Reasoning & Basics of Algebra",
        "focus": "Mastering percentages, ratios, scaling, equations, and number patterns.",
        "weeks": [
            {
                "weekNum": 14,
                "topic": "Number: Fractions, Decimals & Percentages",
                "focus": "Percentages: Core Concept & Basic Conversions",
                "objectives": [
                    "Understand percentages as parts of 100.",
                    "Convert fluently between fractions, decimals, and percentages.",
                    "Identify key equivalence sets (e.g., 3/8 = 37.5% = 0.375)."
                ]
            },
            {
                "weekNum": 15,
                "topic": "Number: Fractions, Decimals & Percentages",
                "focus": "Percentages of Amounts & Scaling",
                "objectives": [
                    "Calculate 10%, 5%, 1%, 25%, 50%, and 75% of whole amounts.",
                    "Use building blocks to find complex percentages (e.g., 17% of 200).",
                    "Solve percentage word problems in commercial contexts (e.g., sales discounts)."
                ]
            },
            {
                "weekNum": 16,
                "topic": "Number: Fractions, Decimals & Percentages",
                "focus": "Percentage Increase and Decrease",
                "objectives": [
                    "Increase and decrease amounts by a given percentage.",
                    "Solve problems involving successive percentage changes.",
                    "Work backwards to find the original amount (reverse percentages)."
                ]
            },
            {
                "weekNum": 17,
                "topic": "Ratio and Proportion",
                "focus": "Introduction to Ratio & Sharing",
                "objectives": [
                    "Understand ratio notation (e.g., A:B) as part-to-part comparisons.",
                    "Simplify ratios to their lowest terms.",
                    "Share a total amount into a given ratio using the 'add parts, divide, multiply' rule."
                ]
            },
            {
                "weekNum": 18,
                "topic": "Ratio and Proportion",
                "focus": "Advanced Ratio & Parts Changing",
                "objectives": [
                    "Solve ratio problems where one part is known and the total must be found.",
                    "Work with multi-part ratios (e.g., A:B:C).",
                    "Analyze problems where ratio proportions change after an addition/removal."
                ]
            },
            {
                "weekNum": 19,
                "topic": "Ratio and Proportion",
                "focus": "Direct and Inverse Proportion",
                "objectives": [
                    "Solve direct proportion problems (recipes, currency conversions).",
                    "Understand inverse proportion (e.g., more workers taking less time).",
                    "Apply scaling factors to solve multi-variable proportion puzzles."
                ]
            },
            {
                "weekNum": 20,
                "topic": "Ratio and Proportion",
                "focus": "Scale Drawings, Maps & Model Scales",
                "objectives": [
                    "Interpret scales on map drawings (e.g., 1:25,000).",
                    "Convert scale distances to actual real-world units (cm to m or km).",
                    "Calculate scale factors for models and plans."
                ]
            },
            {
                "weekNum": 21,
                "topic": "Algebra Basics",
                "focus": "Algebraic Expressions & Substitution",
                "objectives": [
                    "Understand that letters represent variables.",
                    "Simplify expressions by collecting like terms (e.g., 3a + 2b - a).",
                    "Substitute integers and decimals into algebraic formulas."
                ]
            },
            {
                "weekNum": 22,
                "topic": "Algebra Basics",
                "focus": "Solving Single-Variable Equations",
                "objectives": [
                    "Solve single-step equations using inverse operations (e.g., x + 5 = 12).",
                    "Solve equations involving multiplication and division (e.g., 3x = 15).",
                    "Keep equations balanced by performing identical operations on both sides."
                ]
            },
            {
                "weekNum": 23,
                "topic": "Algebra Basics",
                "focus": "Two-Step Equations & Word Problem Modeling",
                "objectives": [
                    "Solve two-step equations (e.g., 4x - 3 = 17).",
                    "Translate written word problems into formal algebraic equations.",
                    "Verify answers by substituting them back into the original problem."
                ]
            },
            {
                "weekNum": 24,
                "topic": "Sequences and Patterns",
                "focus": "Number Sequences: Term-to-Term Rules",
                "objectives": [
                    "Identify arithmetic sequences with constant addition or subtraction.",
                    "Recognize geometric sequences with constant multiplication or division.",
                    "Find missing terms in complex nested or alternating sequences."
                ]
            },
            {
                "weekNum": 25,
                "topic": "Sequences and Patterns",
                "focus": "Number Sequences: Nth Term Foundations",
                "objectives": [
                    "Find the linear formula (Nth term) for a constant difference sequence.",
                    "Determine if a specific number belongs to a given sequence.",
                    "Explore non-linear sequences (Fibonacci, triangular, square numbers)."
                ]
            },
            {
                "weekNum": 26,
                "topic": "Algebra Basics",
                "focus": "Term 2 Review & Algebra/Ratio Mastery Test",
                "objectives": [
                    "Evaluate percentage increases, ratio division, and algebra equations.",
                    "Complete a mixed 10-question set mimicking Henrietta Barnett exam styles.",
                    "Focus on rigorous working out steps for partial credit."
                ]
            }
        ]
    },
    {
        "termId": 3,
        "termName": "Term 3: Shape, Space, Measures & Data Handling",
        "focus": "Developing spatial intelligence, geometry, units, and data analysis skills.",
        "weeks": [
            {
                "weekNum": 27,
                "topic": "Shape, Space and Measures",
                "focus": "Angles: Basic Rules & Intersecting Lines",
                "objectives": [
                    "Identify acute, obtuse, reflex, and right angles.",
                    "Apply rules: angles on a straight line add to 180°, and around a point add to 360°.",
                    "Recognize vertically opposite and parallel line angles (alternate/corresponding)."
                ]
            },
            {
                "weekNum": 28,
                "topic": "Shape, Space and Measures",
                "focus": "Angles in Triangles & Polygons",
                "objectives": [
                    "Recall that interior angles of a triangle add up to 180°.",
                    "Calculate angles in quadrilaterals (adding to 360°).",
                    "Find interior and exterior angles of regular polygons."
                ]
            },
            {
                "weekNum": 29,
                "topic": "Shape, Space and Measures",
                "focus": "Area and Perimeter of Core Shapes",
                "objectives": [
                    "Calculate the perimeter of rectangles, squares, and triangles.",
                    "Apply area formulas: Rectangle = L x W; Triangle = (Base x Height) / 2.",
                    "Differentiate clearly between square units and linear units."
                ]
            },
            {
                "weekNum": 30,
                "topic": "Shape, Space and Measures",
                "focus": "Area and Perimeter of Compound Shapes",
                "objectives": [
                    "Deconstruct irregular compound shapes into standard rectangles and triangles.",
                    "Calculate missing dimensions before performing area/perimeter steps.",
                    "Solve shaded area problems (subtracting one area from another)."
                ]
            },
            {
                "weekNum": 31,
                "topic": "Shape, Space and Measures",
                "focus": "Volume and Surface Area of Cuboids",
                "objectives": [
                    "Calculate volume of cubes and cuboids (Length x Width x Height).",
                    "Find the surface area of a cuboid by calculating the sum of its six faces.",
                    "Solve worded liquid volume and capacity displacement problems."
                ]
            },
            {
                "weekNum": 32,
                "topic": "Shape, Space and Measures",
                "focus": "3D Shapes: Vertices, Edges & Nets",
                "objectives": [
                    "Count faces, edges, and vertices of regular 3D solids (prisms, pyramids).",
                    "Identify valid nets of cubes, prisms, and cylinders.",
                    "Visualize folding nets to solve orientation puzzles."
                ]
            },
            {
                "weekNum": 33,
                "topic": "Shape, Space and Measures",
                "focus": "Coordinates & Transformations",
                "objectives": [
                    "Read and plot coordinates in all four quadrants.",
                    "Translate shapes on a coordinate grid.",
                    "Reflect shapes across horizontal, vertical, and diagonal mirror lines."
                ]
            },
            {
                "weekNum": 34,
                "topic": "Shape, Space and Measures",
                "focus": "Metric and Imperial Unit Conversions",
                "objectives": [
                    "Convert between metric units of length (mm, cm, m, km).",
                    "Convert between metric units of mass (g, kg) and capacity (ml, l).",
                    "Know basic imperial conversions (e.g., 5 miles \u2248 8 km, 1 kg \u2248 2.2 lbs)."
                ]
            },
            {
                "weekNum": 35,
                "topic": "Shape, Space and Measures",
                "focus": "Time, Clocks & Calendar Arithmetic",
                "objectives": [
                    "Read analogue clocks and compute elapsed time intervals.",
                    "Convert between 12-hour (am/pm) and 24-hour digital clock notation.",
                    "Solve calendar arithmetic problems (e.g., 'What day is 45 days after Tuesday?')."
                ]
            },
            {
                "weekNum": 36,
                "topic": "Speed, Distance and Time",
                "focus": "Speed, Distance and Time Calculations",
                "objectives": [
                    "Use the speed-distance-time triangle formula.",
                    "Convert time units (e.g., 2.5 hours = 2 hours 30 minutes) before multiplying speed.",
                    "Solve multi-leg journeys and average speed word problems."
                ]
            },
            {
                "weekNum": 37,
                "topic": "Data Handling and Graphs",
                "focus": "Statistics: Averages and Range",
                "objectives": [
                    "Calculate the Mean (average) of a set of data.",
                    "Find the Median (middle value) and Mode (most frequent value).",
                    "Calculate the Range (highest minus lowest) and solve missing-data problems."
                ]
            },
            {
                "weekNum": 38,
                "topic": "Data Handling and Graphs",
                "focus": "Interpreting Charts & Graphs",
                "objectives": [
                    "Read and interpret data from bar charts, pictograms, and line graphs.",
                    "Deconstruct complex Venn diagrams and Carroll diagrams.",
                    "Answer comparative and multi-step questions based on visual charts."
                ]
            },
            {
                "weekNum": 39,
                "topic": "Shape, Space and Measures",
                "focus": "Term 3 Review & Geometry/Measures Mastery Test",
                "objectives": [
                    "Apply speed formulas, elapsed time, compound area, and average tables.",
                    "Take an interactive GL-style geometry and measures assessment.",
                    "Analyze and eliminate common decimal conversion errors."
                ]
            }
        ]
    },
    {
        "termId": 4,
        "termName": "Term 4: Advanced Problem Solving, Non-Routine Reasoning & Exam Mastery",
        "focus": "Synthesizing all modules to solve complex, super-selective non-routine problems.",
        "weeks": [
            {
                "weekNum": 40,
                "topic": "Worded Problem Solving",
                "focus": "Multi-Step Worded Problems",
                "objectives": [
                    "Identify and highlight key details in lengthy, wordy scenarios.",
                    "Break a large worded problem into sequential, manageable math operations.",
                    "Verify answers by performing reverse calculation loops."
                ]
            },
            {
                "weekNum": 41,
                "topic": "Data Handling and Graphs",
                "focus": "Venn Diagrams & Sorting Puzzles",
                "objectives": [
                    "Represent complex multi-factor group data inside Venn diagrams.",
                    "Solve overlap puzzles (e.g., '15 students play tennis, 12 play chess, 5 play both...').",
                    "Utilize Carroll diagrams to categorize items using negative properties."
                ]
            },
            {
                "weekNum": 42,
                "topic": "Data Handling and Graphs",
                "focus": "Probability and Outcomes",
                "objectives": [
                    "Calculate basic probability of single independent events.",
                    "Express probability as a simplified fraction, decimal, and percentage.",
                    "List all possible outcomes of double events (dice and coin, spinners)."
                ]
            },
            {
                "weekNum": 43,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Non-Routine: Digit Puzzles & Cryptarithms",
                "objectives": [
                    "Solve addition/multiplication cryptarithms where letters represent digits.",
                    "Deduce missing numbers in column additions based on units constraints.",
                    "Apply logical reasoning to solve alphanumeric puzzles."
                ]
            },
            {
                "weekNum": 44,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Non-Routine: Work Rates & Shared Speeds",
                "objectives": [
                    "Solve tasks where multiple agents work together at different rates.",
                    "Calculate pipe filling rates and leak drains.",
                    "Apply reciprocal ratios to solve shared speed problems."
                ]
            },
            {
                "weekNum": 45,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Non-Routine: Age Problems & Backward Tracking",
                "objectives": [
                    "Solve complex age-related timeline puzzles using algebra or visual blocks.",
                    "Trace operations backwards from a final result to find the starting number.",
                    "Handle multi-variable word constraints."
                ]
            },
            {
                "weekNum": 46,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Non-Routine: Venn/Set & Pigeonhole Logic",
                "objectives": [
                    "Apply the Pigeonhole Principle to 'guaranteed worst-case' scenarios.",
                    "Solve advanced subset questions from Henrietta Barnett Stage 2 exams.",
                    "Develop rigorous logic proofs without a calculator."
                ]
            },
            {
                "weekNum": 47,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Super-Selective Mock Test 1 (Tiffin/HBS Style)",
                "objectives": [
                    "Attempt 10 high-complexity non-routine questions under 15-minute time pressure.",
                    "Deduce algebraic setups under stress.",
                    "Learn to pass on ultra-hard items to maximize overall points."
                ]
            },
            {
                "weekNum": 48,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Super-Selective Mock Test 2 (St Olave's Style)",
                "objectives": [
                    "Attempt 10 high-complexity remainder and divisor logic puzzles.",
                    "Practice drafting fast, clear step-by-step scratchpad working.",
                    "Identify and isolate trap options."
                ]
            },
            {
                "weekNum": 49,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Exam Timing: Skimming & Guessing Strategy",
                "objectives": [
                    "Master the 3-pass exam technique (Easy first, Medium second, Guess/Hard last).",
                    "Identify and discard incorrect MCQ distractors instantly.",
                    "Develop speed-skimming for lengthy word descriptions."
                ]
            },
            {
                "weekNum": 50,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Advanced Crossover: Math and Verbal Reasoning",
                "objectives": [
                    "Solve math codes and letter-digit correlation matrices.",
                    "Read and analyze conditional math clues (if-then statements).",
                    "Master alphanumeric puzzle structures common in GL assessments."
                ]
            },
            {
                "weekNum": 51,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Final Full-Syllabus Mock Exam",
                "objectives": [
                    "Complete a full, randomized, multi-module 11+ maths paper (20 questions).",
                    "Review step-by-step feedback across all syllabus sectors.",
                    "Refine final revision flashcards."
                ]
            },
            {
                "weekNum": 52,
                "topic": "Non-Routine Reasoning (Top-School Style)",
                "focus": "Ultimate Strategy, Anxiety Management & Prep",
                "objectives": [
                    "Review active exam guidelines and Coach Pip's top selective school rules.",
                    "Plan the final week's low-intensity warm-up routine.",
                    "Build mental stamina, positive visualization, and confidence."
                ]
            }
        ]
    }
]


def get_questions_for_week(week_num: int) -> list:
    """Generate 3 homework questions for the specified week."""
    # Custom deterministic randomizer based on week_num as a seed
    seed = week_num

    def rand_num(min_val, max_val, offset=0):
        # A simple stable deterministic hash/sine-randomizer
        x = math.sin(seed * 43758.5453 + offset) * 10000
        r = x - math.floor(x)
        return int(min_val + math.floor(r * (max_val - min_val + 1)))

    questions = []

    if week_num == 1:
        questions.append({
            "id": 1,
            "questionText": "What is the value of the digit 7 in the number 2,374,905?",
            "options": ["Seventy", "Seven Hundred", "Seventy Thousand", "Seven Thousand", "Seven Million"],
            "correctLetter": "C",
            "correctValue": "Seventy Thousand",
            "explanation": "In the number 2,374,905, looking at place value from right to left: 5 is units, 0 is tens, 9 is hundreds, 4 is thousands, 7 is ten-thousands (70,000), 3 is hundred-thousands, and 2 is millions. Therefore, the 7 represents seventy thousand.",
            "tip": "Write out the column headings (M, HTh, TTh, Th, H, T, U) above the digits if you're ever unsure about placing!"
        })
        questions.append({
            "id": 2,
            "questionText": "Calculate: 4,582 + 3,749 = ?",
            "options": ["8,231", "8,331", "7,331", "8,321", "8,311"],
            "correctLetter": "B",
            "correctValue": "8,331",
            "explanation": "Using column addition:\n  4582\n+ 3749\n------\n  8331\n(carrying: 2+9=11 (write 1, carry 1), 8+4+1=13 (write 3, carry 1), 5+7+1=13 (write 3, carry 1), 4+3+1=8).",
            "tip": "Always double check the units column first. 2 + 9 ends in 1, which instantly eliminates some options!"
        })
        questions.append({
            "id": 3,
            "questionText": "A library has 6,013 books. If 2,458 books are loaned out, how many books remain in the library?",
            "options": ["3,545", "3,655", "3,555", "4,555", "3,455"],
            "correctLetter": "C",
            "correctValue": "3,555",
            "explanation": "We perform column subtraction: 6,013 - 2,458.\n  6013\n- 2458\n------\n  3555\n(Borrowing steps: 13-8=5; 10-5=5; 9-4=5; 5-2=3).",
            "tip": "Subtracting from numbers containing zeros (like 6,013) can lead to borrowing mistakes. Check your result by adding the answer to the subtracted number: 3,555 + 2,458 = 6,013!"
        })
    elif week_num == 2:
        questions.append({
            "id": 1,
            "questionText": "Which is the closest estimate to the calculation: 398 × 19?",
            "options": ["4,000", "8,000", "6,000", "7,600", "80,000"],
            "correctLetter": "B",
            "correctValue": "8,000",
            "explanation": "To estimate, round each number to 1 significant figure: 398 rounds to 400, and 19 rounds to 20. Then, 400 × 20 = 8,000.",
            "tip": "Estimating is a vital exam saver! If you are short on time, rounding to the nearest 10 or 100 will help you spot the correct option in seconds."
        })
        questions.append({
            "id": 2,
            "questionText": "What is the quickest way to mentally calculate 456 + 199?",
            "options": ["Add 200, then add 1", "Add 100, then add 99", "Add 200, then subtract 1",
                        "Add 200, then subtract 2", "Multiply by 2, then subtract 1"],
            "correctLetter": "C",
            "correctValue": "Add 200, then subtract 1",
            "explanation": "199 is extremely close to 200 (199 = 200 - 1). Therefore, to add 199 mentally, you can add 200 (getting 656) and then subtract 1 (getting 655).",
            "tip": "This technique is called compensation and is highly valued by top grammar school papers to test mental math agility."
        })
        questions.append({
            "id": 3,
            "questionText": "Without doing the full calculation, what must be the units digit of 34,587 × 6,128?",
            "options": ["5", "8", "7", "6", "4"],
            "correctLetter": "D",
            "correctValue": "6",
            "explanation": "The units digit of any product depends solely on the product of the units digits of the numbers being multiplied. Here, the units digits are 7 and 8. Since 7 × 8 = 56, the units digit of the final product must be 6.",
            "tip": "Checking the units digit is an extremely fast way to eliminate wrong multiple choice options on the 11+ test!"
        })
    elif week_num == 3:
        questions.append({
            "id": 1,
            "questionText": "Calculate: 148 × 12 = ?",
            "options": ["1,776", "1,676", "1,786", "1,480", "1,876"],
            "correctLetter": "A",
            "correctValue": "1,776",
            "explanation": "Using long multiplication or partition:\n148 × 10 = 1,480\n148 × 2 = 296\nSum: 1,480 + 296 = 1,776.",
            "tip": "Multiplying by 12 is common. Think of it as multiplying by 10 and adding double the original amount."
        })
        questions.append({
            "id": 2,
            "questionText": "A box contains 24 chocolates. A wholesale store orders 35 boxes. How many chocolates does the store receive in total?",
            "options": ["740", "840", "820", "940", "850"],
            "correctLetter": "B",
            "correctValue": "840",
            "explanation": "We need to calculate 24 × 35. Let's partition: 24 × 30 = 720; 24 × 5 = 120. Sum: 720 + 120 = 840.",
            "tip": "To multiply by 35, you can also multiply by 70 and then divide by 2! 24 x 70 = 1680, and 1680 / 2 = 840. Always look for creative mental math channels!"
        })
        questions.append({
            "id": 3,
            "questionText": "What is the result of 0.45 × 100?",
            "options": ["4.5", "0.0045", "45", "450", "4500"],
            "correctLetter": "C",
            "correctValue": "45",
            "explanation": "Multiplying a decimal by 100 shifts all digits two places to the left, which has the visual effect of moving the decimal point two places to the right. Hence, 0.45 becomes 45.",
            "tip": "Be careful not to just 'add two zeros'! Adding zeros to 0.45 would make it 0.4500, which has the exact same value. Shift the digits instead!"
        })
    elif week_num == 4:
        questions.append({
            "id": 1,
            "questionText": "Solve: 456 ÷ 8 = ?",
            "options": ["56", "57", "58", "67", "57.5"],
            "correctLetter": "B",
            "correctValue": "57",
            "explanation": "Using short division (the 'bus stop' method):\n- 8 into 4 doesn't go (carry 4 to make 45).\n- 8 into 45 goes 5 times, remainder 5 (write 5 above, carry 5 to make 56).\n- 8 into 56 goes exactly 7 times.\n- The quotient is 57.",
            "tip": "If you divide by 8, you can also half the number three times in a row! Half of 456 is 228, half of 228 is 114, half of 114 is 57. This is incredibly reliable!"
        })
        questions.append({
            "id": 2,
            "questionText": "What is the remainder when 389 is divided by 6?",
            "options": ["1", "5", "3", "2", "4"],
            "correctLetter": "B",
            "correctValue": "5",
            "explanation": "Let's perform short division of 389 by 6:\n- 6 into 38 goes 6 times (since 6 × 6 = 36), remainder 2.\n- 6 into 29 goes 4 times (since 6 × 4 = 24), remainder 5.\n- Therefore, 389 ÷ 6 = 64 with a remainder of 5.",
            "tip": "You can check this instantly by performing: 64 x 6 + 5 = 384 + 5 = 389."
        })
        questions.append({
            "id": 3,
            "questionText": "Express 75 ÷ 4 as a mixed fraction.",
            "options": ["18 1/4", "18 3/4", "19 1/4", "17 3/4", "18.75"],
            "correctLetter": "B",
            "correctValue": "18 3/4",
            "explanation": "75 ÷ 4 = 18 with a remainder of 3. In fraction form, the remainder is placed over the divisor: 18 3/4.",
            "tip": "To convert a division with a remainder into a mixed number, keep the divisor as your denominator and the remainder as your numerator."
        })
    elif week_num == 5:
        questions.append({
            "id": 1,
            "questionText": "Solve: (12 - 4) × 5 + 3 = ?",
            "options": ["43", "61", "17", "67", "53"],
            "correctLetter": "A",
            "correctValue": "43",
            "explanation": "According to BODMAS/BIDMAS, perform operations inside brackets first:\n1) Brackets: 12 - 4 = 8\n2) Multiplication next: 8 × 5 = 40\n3) Addition last: 40 + 3 = 43.",
            "tip": "Always underline or write down the portion of the formula you are solving on each line to keep track!"
        })
        questions.append({
            "id": 2,
            "questionText": "Solve: 24 - 12 ÷ 3 × 2 + 5 = ?",
            "options": ["13", "19", "21", "2", "3"],
            "correctLetter": "C",
            "correctValue": "21",
            "explanation": "According to BODMAS, division and multiplication have equal priority and are performed from left to right, followed by addition and subtraction:\n1) Division: 12 ÷ 3 = 4. The expression becomes: 24 - 4 × 2 + 5\n2) Multiplication: 4 × 2 = 8. Expression becomes: 24 - 8 + 5\n3) Addition/Subtraction from left to right: 24 - 8 = 16, then 16 + 5 = 21.",
            "tip": "A classic 11+ trap is doing 24 - 12 first, or doing 3 × 2 first. Always follow BODMAS rigidly!"
        })
        questions.append({
            "id": 3,
            "questionText": "Where should brackets be placed in the following expression to make it correct? 4 + 6 × 3 - 2 = 28",
            "options": ["(4 + 6) × 3 - 2", "4 + (6 × 3) - 2", "4 + 6 × (3 - 2)", "(4 + 6 × 3) - 2",
                        "Brackets are not needed"],
            "correctLetter": "A",
            "correctValue": "(4 + 6) × 3 - 2",
            "explanation": "Let's test option A: (4 + 6) × 3 - 2.\n- Solve inside brackets first: 4 + 6 = 10\n- Next, multiply: 10 × 3 = 30\n- Finally, subtract: 30 - 2 = 28. This is correct!",
            "tip": "Work backwards from the options provided instead of trying to guess where brackets go from scratch!"
        })
    else:
        # Find week metadata from the CURRICULUM
        current_week = None
        for term in CURRICULUM:
            for week in term["weeks"]:
                if week["weekNum"] == week_num:
                    current_week = week
                    break
            if current_week:
                break

        focus = current_week["focus"] if current_week else "General Practice"

        questions.append({
            "id": 1,
            "questionText": f"An exam question tests your knowledge of [{focus}]. Solve the following: A student has some counters. If they group them into piles of 5, they have 3 left over. If they group them into piles of 6, they have 4 left over. What is the smallest possible number of counters they could have?",
            "options": ["13", "18", "23", "28", "33"],
            "correctLetter": "D",
            "correctValue": "28",
            "explanation": "Let's find a number N that leaves a remainder of 3 when divided by 5, and a remainder of 4 when divided by 6.\n- Multiples of 5 plus 3: 8, 13, 18, 23, 28, 33...\n- Multiples of 6 plus 4: 10, 16, 22, 28, 34...\nThe smallest common number in both lists is 28.",
            "tip": "Notice that in both cases, the remainder is exactly 2 less than the group size (5-3 = 2, and 6-4 = 2). This means the answer is simply the LCM of 5 and 6 (which is 30) minus 2: 30 - 2 = 28!"
        })
        questions.append({
            "id": 2,
            "questionText": f"A selective school workbook presents a challenge for [{focus}]: If 3/5 of a class are girls, and there are 12 boys in the class, how many students are there in total?",
            "options": ["18", "20", "24", "30", "36"],
            "correctLetter": "D",
            "correctValue": "30",
            "explanation": "If 3/5 of the class are girls, then the remaining 2/5 of the class must be boys.\nWe are told that 2/5 of the class is equal to 12 boys.\n- To find 1/5 of the class, divide by 2: 12 ÷ 2 = 6 students.\n- To find the whole class (5/5), multiply by 5: 6 × 5 = 30 students.",
            "tip": "Visualize fractions as block diagrams! 2 blocks represent the boys (12), so each block represents 6. The total class has 5 blocks, which is 5 × 6 = 30."
        })
        questions.append({
            "id": 3,
            "questionText": f"To master [{focus}], solve: A recipe requires 150g of flour to make 6 cupcakes. How much flour is required to make 10 cupcakes?",
            "options": ["200g", "225g", "250g", "300g", "1500g"],
            "correctLetter": "C",
            "correctValue": "250g",
            "explanation": "This is a direct proportion question. Let's find the unitary value first:\n- Flour for 1 cupcake: 150g ÷ 6 = 25g.\n- Flour for 10 cupcakes: 25g × 10 = 250g.",
            "tip": "Alternatively, notice that 10 is 5/3 of 6. Multiply 150g by 5/3: 150 ÷ 3 = 50, and 50 × 5 = 250g."
        })

    return questions


def generate_markdown_plan() -> str:
    """Generate the full Markdown plan matching the TypeScript counterpart."""
    md = [
        "# Eleven Plus (11+) Maths Study Plan",
        "## The 52-Week Year-Round Curriculum & Homework Sets",
        "**Coach Pip's Selective Grammar School Entrance Training Core**",
        "*Prepared for the GL Assessment, CEM, and Super-Selective Stage Two Exams*",
        "",
        "---",
        "",
        "## STUDY PLAN OVERVIEW",
        "Preparing for highly competitive UK selective schools (like Henrietta Barnett, Tiffin, CSSE, and St Olave's) requires a meticulous, systematic, and well-spaced approach. This 52-week plan covers the complete 11+ syllabus, divided into four strategic terms:",
        "1. **Term 1 (Weeks 1-13)**: Arithmetic & Number Sense Foundations",
        "2. **Term 2 (Weeks 14-26)**: Proportional Reasoning & Basics of Algebra",
        "3. **Term 3 (Weeks 27-39)**: Shape, Space, Measures & Data Handling",
        "4. **Term 4 (Weeks 40-52)**: Advanced Problem Solving, Non-Routine Reasoning & Exam Mastery",
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
    md.append(
        "*Congratulations on working through this plan! Regular practice, diligent step-by-step working, and double-checking calculations are the keys to securing a high-accuracy selective school score.*")
    return "\n".join(md)


def main():
    print("==========================================================")
    print("      11+ Maths 52-Week Year-Round Plan Generator        ")
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
    json_path = "11_Plus_Maths_52_Week_Plan.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_plan_data, f, indent=2, ensure_ascii=False)
    print(f"[Success] Saved 52-Week Plan JSON to: {json_path}")

    # Save to Markdown
    md_path = "11_Plus_Maths_52_Week_Plan.md"
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
                    # Store only questions in the RAG document. Answers and worked
                    # explanations stay in metadata and are returned only after marking.
                    content_str = (
                        f"11+ Maths 52-Week Plan - Term {term['termId']} - Week {week['weekNum']}\n"
                        f"Topic Focus: {week['focus']}\n"
                        f"Syllabus: {week['topic']}\n"
                        "QUESTIONS\n\n"
                    )
                    answer_records = []
                    for idx, q in enumerate(week["homeworkSet"], 1):
                        content_str += f"{idx}. {q['questionText']}\n"
                        for option_index, option in enumerate(q["options"]):
                            letter = chr(65 + option_index)
                            content_str += f"{letter}) {option}\n"
                        content_str += "\n"
                        answer_records.append({
                            "question": f"{idx}. {q['questionText']}",
                            "options": q["options"],
                            "answer": q["correctValue"],
                            "correct_letter": q["correctLetter"],
                            "explanation": q["explanation"],
                            "tip": q["tip"],
                        })

                    metadata = {
                        "year_group": 6,
                        "subject": "Maths-1year",
                        "key_stage": "11+",
                        "topic": week["topic"],
                        "week_num": week["weekNum"],
                        "term_id": term["termId"],
                        "content_type": "year_round",
                        "exam_style": "GL & Selective School Style",
                        "correct_answers": json.dumps(answer_records, ensure_ascii=False),
                        "created_at": datetime.now().isoformat(),
                    }

                    batch_data.append({
                        "content": content_str,
                        "metadata": metadata,
                        "doc_id": f"elevenplus_year_round_week_{week['weekNum']:02d}"
                    })

            store.add_batch_homework(batch_data)
            print("Successfully loaded 52 weekly plan entries into the RAG Store.")
        except Exception as e:
            print(f"RAG Integration skipped or failed: {e}")
    else:
        print("\nNote: RAG Store is not available in standalone execution. Local files generated successfully.")


if __name__ == "__main__":
    main()
