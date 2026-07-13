#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ Non-Verbal Reasoning 52-Week Year-Round Plan Generator
==========================================================

Generates a comprehensive 52-Week Year-Round Non-Verbal Reasoning study roadmap formulated for
Henrietta Barnett, Tiffin, CSSE, and St Olave's entrance papers.

Saves the generated plan to:
  - 11_Plus_NVR_52_Week_Plan.json
  - 11_Plus_NVR_52_Week_Plan.md

Also registers them in the RAG vector store for student queries.
"""

import sys
import os
import json
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    get_elevenplus_rag_store = None

# ---------------------------------------------------------------------------
# Shape vocabulary
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

# 52-Week Curriculum Schema for Non-Verbal Reasoning
CURRICULUM = [
  {
    "termId": 1,
    "termName": "Term 1: Visual Sequences, Rotations & Symmetry",
    "focus": "Developing foundational skills in identifying sequential pattern shifts, directional orientation, and bilateral symmetry.",
    "weeks": [
      {
        "weekNum": 1,
        "topic": "Shape Sequences & Progressions",
        "focus": "Single Attribute Progressions",
        "objectives": [
          "Track shifts across a single visual dimension (colour transitions).",
          "Deduce cyclic or stepwise sequences using a structured emoji vocabulary.",
          "Identify correct options based on a single distinct property shift."
        ]
      },
      {
        "weekNum": 2,
        "topic": "Shape Sequences & Progressions",
        "focus": "Alternating Pattern Sequences",
        "objectives": [
          "Decipher interleaving rules where shapes follow dual, alternating threads.",
          "Determine the joint relationship between shape type transitions and color cycles.",
          "Construct logical chains on scrap paper to prevent visual errors."
        ]
      },
      {
        "weekNum": 3,
        "topic": "Shape Sequences & Progressions",
        "focus": "Complex Progression Steps",
        "objectives": [
          "Evaluate composite sequences where both shape attributes change simultaneously.",
          "Identify wrap-around boundaries where attribute lists restart from the beginning.",
          "Practice rapid elimination of distractors in complex multi-step series."
        ]
      },
      {
        "weekNum": 4,
        "topic": "Rotation & Angular Alignment",
        "focus": "Clockwise Rotations",
        "objectives": [
          "Understand angular rotations in multiples of 45 degrees.",
          "Track the clockwise movement of indicator arrows and structural pointers.",
          "Match orientation outcomes against standardised compass markings."
        ]
      },
      {
        "weekNum": 5,
        "topic": "Rotation & Angular Alignment",
        "focus": "Anti-Clockwise Rotations",
        "objectives": [
          "Deduce anti-clockwise rotational steps of 45°, 90°, and 135°.",
          "Determine standard directional transitions on a mental circle.",
          "Isolate angle increments from overall shape translations."
        ]
      },
      {
        "weekNum": 6,
        "topic": "Rotation & Angular Alignment",
        "focus": "Alternating & Multi-Step Rotations",
        "objectives": [
          "Solve progressive rotations with alternating degrees (e.g., +45°, +90°, +45°).",
          "Identify complex directional flips (180° turns).",
          "Handle composite rotation questions with high confidence."
        ]
      },
      {
        "weekNum": 7,
        "topic": "Reflection & Mirror Lines",
        "focus": "Vertical Mirror Reflection",
        "objectives": [
          "Perform 2D reflections across a vertical axis of symmetry.",
          "Understand how left-right properties swap while up-down alignments remain unchanged.",
          "Practice identifying mirrored positions of pointing indicators."
        ]
      },
      {
        "weekNum": 8,
        "topic": "Reflection & Mirror Lines",
        "focus": "Horizontal Mirror Reflection",
        "objectives": [
          "Apply reflections across a horizontal baseline.",
          "Deduce how up-down alignments are inverted while left-right stays fixed.",
          "Trace mirrored positions of arrows and overlapping segments."
        ]
      },
      {
        "weekNum": 9,
        "topic": "Reflection & Mirror Lines",
        "focus": "Double & Compound Reflections",
        "objectives": [
          "Evaluate compound reflections (vertical then horizontal reflections).",
          "Distinguish simple 180° rotations from composite dual-axis reflections.",
          "Eliminate deceptively close option traps in reflective reasoning."
        ]
      },
      {
        "weekNum": 10,
        "topic": "Symmetry & Fold lines",
        "focus": "Axes of Symmetry",
        "objectives": [
          "Determine how many mirror lines exist in regular and irregular geometric shapes.",
          "Identify matching pairs that reflect perfectly across multiple lines of symmetry.",
          "Master visual fold-and-unfold patterns."
        ]
      },
      {
        "weekNum": 11,
        "topic": "Rotations & Reflections Mixed",
        "focus": "Distinguishing Rotation vs Reflection",
        "objectives": [
          "Determine if a test shape is a rotated or a reflected version of a source shape.",
          "Recognize chiral/non-superimposable shapes.",
          "Apply systematic rotation checks to eliminate reflection options."
        ]
      },
      {
        "weekNum": 12,
        "topic": "Grid Translations",
        "focus": "Spatial Moves & Coordinates",
        "objectives": [
          "Track step-by-step movements of symbols inside 2D grid containers.",
          "Deduce the combined effect of direction, step size, and wrap-around boundaries.",
          "Verify intermediate spatial positions carefully."
        ]
      },
      {
        "weekNum": 13,
        "topic": "Shape Sequences & Progressions",
        "focus": "Term 1 Review & Mixed Test",
        "objectives": [
          "Synthesize shape series, angular rotations, reflections, and translation paths.",
          "Complete a mixed diagnostic quiz containing multiple NVR topics.",
          "Review step-by-step explanations to correct visual mistakes."
        ]
      }
    ]
  },
  {
    "termId": 2,
    "termName": "Term 2: Analogies, Matrices & Grid Completion",
    "focus": "Expanding skills into relative reasoning, 2D grid matrix configurations, and categorization rules.",
    "weeks": [
      {
        "weekNum": 14,
        "topic": "Shape Analogies & Attribute Changes",
        "focus": "Colour Shift Analogies",
        "objectives": [
          "Understand relative analogies (A is to B as C is to D).",
          "Detect how colour traits shift under specific transformation rules.",
          "Apply exact transformation rules to find matching destination shapes."
        ]
      },
      {
        "weekNum": 15,
        "topic": "Shape Analogies & Attribute Changes",
        "focus": "Type Swap Analogies",
        "objectives": [
          "Deduce relationships based on switching outline types (circles to squares, etc.).",
          "Isolate multi-level transitions where shape and size parameters are swapped.",
          "Verify the consistency of transitions across both analogy pairs."
        ]
      },
      {
        "weekNum": 16,
        "topic": "Shape Analogies & Attribute Changes",
        "focus": "Compound Multi-Attribute Analogies",
        "objectives": [
          "Solve analogies where type, color, and size vary simultaneously.",
          "Formulate explicit transformation sentences in your mind before viewing options.",
          "Successfully eliminate options that only satisfy half the rule."
        ]
      },
      {
        "weekNum": 17,
        "topic": "Matrix Completion & Grid Logic",
        "focus": "2x2 Attribute Shift Matrices",
        "objectives": [
          "Analyse 2x2 grid layouts with a single missing cell.",
          "Track attribute variations across rows (horizontal rules) and columns (vertical rules).",
          "Identify the correct cell that satisfies both grid vectors simultaneously."
        ]
      },
      {
        "weekNum": 18,
        "topic": "Matrix Completion & Grid Logic",
        "focus": "2x2 Rotational Matrices",
        "objectives": [
          "Track rotations of symbols inside grid compartments.",
          "Verify if rotational steps are uniform or variable across rows.",
          "Isolate orientation directions to pinpoint correct cells."
        ]
      },
      {
        "weekNum": 19,
        "topic": "Matrix Completion & Grid Logic",
        "focus": "Complex Grid Logic",
        "objectives": [
          "Analyse grid properties involving additions, subtractions, or intersections.",
          "Study cell relationships where attributes are combined to form subsequent cells.",
          "Synthesize row and column trends to solve high-difficulty matrices."
        ]
      },
      {
        "weekNum": 20,
        "topic": "Odd One Out & Shape Discrepancy",
        "focus": "Shape Discrepancies",
        "objectives": [
          "Locate the single shape that breaks general geometric or category rules.",
          "Establish systematic checking orders (shape type, size, orientation, count).",
          "Defeat options designed to look like the odd one out."
        ]
      },
      {
        "weekNum": 21,
        "topic": "Odd One Out & Shape Discrepancy",
        "focus": "Colour Discrepancies",
        "objectives": [
          "Isolate groups bound by strict color rules.",
          "Deduce temperature patterns (warm vs cool colors) as grouping criteria.",
          "Identify anomalies that break group color trends."
        ]
      },
      {
        "weekNum": 22,
        "topic": "Odd One Out & Shape Discrepancy",
        "focus": "Orientation Discrepancies",
        "objectives": [
          "Deduce directional guidelines common to four shapes.",
          "Identify the single shape that rotates or points in an incompatible direction.",
          "Perform quick mental rotations to ensure groups are superimposable."
        ]
      },
      {
        "weekNum": 23,
        "topic": "Odd One Out & Shape Discrepancy",
        "focus": "Counting & Numerical Discrepancies",
        "objectives": [
          "Spot groupings based on numerical tallies (sides, intersections, elements).",
          "Isolate odd-one-out cases based on even/odd or specific totals.",
          "Check segment divisions carefully."
        ]
      },
      {
        "weekNum": 24,
        "topic": "Matrix Completion & Grid Logic",
        "focus": "Advanced Grid & Analogy Mastery",
        "objectives": [
          "Solve advanced compound matrices and complex analogies.",
          "Differentiate near-identical options with extreme accuracy.",
          "Build mental speed through systematic visual scanning."
        ]
      },
      {
        "weekNum": 25,
        "topic": "Matrix Completion & Grid Logic",
        "focus": "Find the Missing Section",
        "objectives": [
          "Reconstruct complete drawings by identifying matching missing patches.",
          "Align textures, lines, and borders perfectly at boundary interfaces.",
          "Master continuous spatial line continuation."
        ]
      },
      {
        "weekNum": 26,
        "topic": "Matrix Completion & Grid Logic",
        "focus": "Term 2 Review & Diagnostic Quiz",
        "objectives": [
          "Consolidate analogies, grid completion, and odd-one-out rules.",
          "Diagnose weak areas through a 10-question mixed assessment.",
          "Analyse detailed worked answers to clarify grid logic."
        ]
      }
    ]
  },
  {
    "termId": 3,
    "termName": "Term 3: Coding, Groupings & Counting",
    "focus": "Mastering non-verbal ciphers, group associations, item tallies, and overlap relationships.",
    "weeks": [
      {
        "weekNum": 27,
        "topic": "Shape Codes & Attribute Translation",
        "focus": "Direct Attribute Mapping",
        "objectives": [
          "Deconstruct multi-letter code mappings for shapes.",
          "Associate specific letter slots with individual shape traits (type, color).",
          "Decode unseen target shapes by combining extracted rules."
        ]
      },
      {
        "weekNum": 28,
        "topic": "Shape Codes & Attribute Translation",
        "focus": "Alternating Code Patterns",
        "objectives": [
          "Solve complex codes where letter representations cycle.",
          "Determine positional rules for codes that represent outline features.",
          "Verify choices by translating code letters back into shapes."
        ]
      },
      {
        "weekNum": 29,
        "topic": "Shape Codes & Attribute Translation",
        "focus": "Complex Attribute Translation",
        "objectives": [
          "Deduce multi-letter codes representing orientation, layering, or sizes.",
          "Eliminate options rapidly by decoding single letter positions.",
          "Complete high-difficulty code matching with perfect accuracy."
        ]
      },
      {
        "weekNum": 30,
        "topic": "Similarity Grouping & Group Association",
        "focus": "Shape Type Associations",
        "objectives": [
          "Analyse two predefined reference groups of shapes.",
          "Identify the core defining traits that bind Group 1 and Group 2.",
          "Assign a target test shape to the correct group based on rules."
        ]
      },
      {
        "weekNum": 31,
        "topic": "Similarity Grouping & Group Association",
        "focus": "Color Temperature Categories",
        "objectives": [
          "Recognize abstract color-bound grouping rules.",
          "Categorize target shapes based on warm versus cool color clusters.",
          "Differentiate group associations with absolute precision."
        ]
      },
      {
        "weekNum": 32,
        "topic": "Similarity Grouping & Group Association",
        "focus": "Symmetry & Alignment Grouping",
        "objectives": [
          "Deduce group boundaries defined by bilateral or rotational symmetry.",
          "Assign complex shapes to groups based on core structural properties.",
          "Establish systematic evaluation paths."
        ]
      },
      {
        "weekNum": 33,
        "topic": "Shape Counting & Combinatorial Totals",
        "focus": "Category Tallies",
        "objectives": [
          "Scan multi-shape sets to count specific sub-categories.",
          "Count by color criteria under visual pressure.",
          "Select the correct total from close numeric MCQ choices."
        ]
      },
      {
        "weekNum": 34,
        "topic": "Shape Counting & Combinatorial Totals",
        "focus": "Intersecting & Overlapping Counts",
        "objectives": [
          "Count region overlaps, shared borders, or intersections.",
          "Distinguish nested symbols from overlapping boundaries.",
          "Master combinatorial counting."
        ]
      },
      {
        "weekNum": 35,
        "topic": "Shape Counting & Combinatorial Totals",
        "focus": "Segment & Line Counting",
        "objectives": [
          "Tally line segments, division lines, or corner vertices.",
          "Perform quick geometric math on complex multi-line symbols.",
          "Verify the counts to avoid silly calculation mistakes."
        ]
      },
      {
        "weekNum": 36,
        "topic": "Layering & Overlapping Shapes",
        "focus": "Foreground Layer Identification",
        "objectives": [
          "Analyse composite drawings with overlapping shapes.",
          "Locate which shape has an unbroken, complete boundary (lies on top).",
          "Identify correct layer order hierarchies."
        ]
      },
      {
        "weekNum": 37,
        "topic": "Layering & Overlapping Shapes",
        "focus": "Background & Midground Sorting",
        "objectives": [
          "Determine which shapes are placed at the bottom-most layers.",
          "Trace partially obstructed borders to identify shape types.",
          "Evaluate depth indexes in 2D layered graphics."
        ]
      },
      {
        "weekNum": 38,
        "topic": "Similarity Grouping & Group Association",
        "focus": "Coding & Grouping Integration",
        "objectives": [
          "Solve hybrid questions that combine coding, groupings, and overlapping layers.",
          "Isolate distinct variables to avoid confusion.",
          "Verify choices systematically."
        ]
      },
      {
        "weekNum": 39,
        "topic": "Shape Counting & Combinatorial Totals",
        "focus": "Term 3 Review & Mixed Diagnostic Exam",
        "objectives": [
          "Synthesize shape codes, similarity groups, counts, and layering logic.",
          "Complete a mixed diagnostic test of 10 questions under 10 minutes.",
          "Eliminate common error patterns."
        ]
      }
    ]
  },
  {
    "termId": 4,
    "termName": "Term 4: 3D Spatial Reasoning & Advanced Exam Mastery",
    "focus": "Transitioning to 3D spatial folding, nets of cubes, isometric perspectives, and high-speed mock exams.",
    "weeks": [
      {
        "weekNum": 40,
        "topic": "3D Spatial Nets & Isometric Reasoning",
        "focus": "Folding Cubes from 2D Nets",
        "objectives": [
          "Visualize folding a 2D cross-like net into a 3D cube.",
          "Identify opposite faces that can never touch in 3D space.",
          "Verify adjacent face arrangements and orientations."
        ]
      },
      {
        "weekNum": 41,
        "topic": "3D Spatial Nets & Isometric Reasoning",
        "focus": "Unfolding Cube Faces",
        "objectives": [
          "Track 3D cube faces as they are unfolded flat into 2D nets.",
          "Determine the relative positions of symbols when flattened.",
          "Match face coordinates perfectly."
        ]
      },
      {
        "weekNum": 42,
        "topic": "3D Spatial Nets & Isometric Reasoning",
        "focus": "Isometric Side Projections",
        "objectives": [
          "Construct 2D planar silhouettes (top, front, right views) from 3D block assemblies.",
          "Deduce spatial arrangements from orthographic plans.",
          "Track block visibility accurately."
        ]
      },
      {
        "weekNum": 43,
        "topic": "3D Spatial Nets & Isometric Reasoning",
        "focus": "Block Counting in 3D Structures",
        "objectives": [
          "Tally individual blocks in complex 3D structures (including hidden support blocks).",
          "Construct block counts layer-by-layer to ensure accuracy.",
          "Verify totals against distractor choices."
        ]
      },
      {
        "weekNum": 44,
        "topic": "Shape Sequences & Progressions",
        "focus": "Combined Multi-Step Sequences",
        "objectives": [
          "Evaluate ultra-complex sequence patterns.",
          "Formulate explicit attribute tracking grids under time pressure.",
          "Achieve rapid elimination of distractors."
        ]
      },
      {
        "weekNum": 45,
        "topic": "Rotation & Angular Alignment",
        "focus": "Advanced Spatial Rotations",
        "objectives": [
          "Analyse angular alignments combining 2D rotations and mirroring.",
          "Spot chiral mismatches instantly.",
          "Boost rotational speed under strict time conditions."
        ]
      },
      {
        "weekNum": 46,
        "topic": "Shape Sequences & Progressions",
        "focus": "High-Speed Practice: Series & Matrices",
        "objectives": [
          "Complete rapid series and matrix questions under 45 seconds each.",
          "Maintain accuracy while working under high-pressure conditions.",
          "Adopt streamlined elimination tactics."
        ]
      },
      {
        "weekNum": 47,
        "topic": "Shape Codes & Attribute Translation",
        "focus": "High-Speed Practice: Codes & Grouping",
        "objectives": [
          "Apply high-speed ciphers and classification grouping tests.",
          "Diagnose and correct visual parsing slips immediately.",
          "Solidify the letter-to-attribute mapping methods."
        ]
      },
      {
        "weekNum": 48,
        "topic": "3D Spatial Nets & Isometric Reasoning",
        "focus": "High-Speed Practice: 3D Nets & Layering",
        "objectives": [
          "Practice folding cubes and overlapping layering questions under time pressure.",
          "Maintain spatial coordinates without getting confused.",
          "Solve 3D spatial queries in under 50 seconds."
        ]
      },
      {
        "weekNum": 49,
        "topic": "Odd One Out & Shape Discrepancy",
        "focus": "Mock Exam Paper 1: Standard GL Style",
        "objectives": [
          "Complete a 10-question mixed NVR exam representing standard difficulty.",
          "Adopt appropriate time budgeting: exactly 1 minute per question.",
          "Refine the tracking of multiple attributes."
        ]
      },
      {
        "weekNum": 50,
        "topic": "Shape Analogies & Attribute Changes",
        "focus": "Mock Exam Paper 2: Hard Selective Style",
        "objectives": [
          "Complete a difficult 10-question mixed exam focusing on selective school standards.",
          "Solve complex composite matrices and analogies.",
          "Learn to manage difficult questions by marking them and moving on."
        ]
      },
      {
        "weekNum": 51,
        "topic": "3D Spatial Nets & Isometric Reasoning",
        "focus": "Mock Exam Paper 3: Ultimate Mastery Style",
        "objectives": [
          "Complete the most challenging 10-question mixed exam including 3D folding and overlapping layers.",
          "Track 3D structures with extreme precision.",
          "Achieve a target accuracy of 90% or higher."
        ]
      },
      {
        "weekNum": 52,
        "topic": "Reflection & Mirror Lines",
        "focus": "Full Year-Round Review & Celebration",
        "objectives": [
          "Synthesize key methodologies for all 11 NVR topics.",
          "Celebrate completing the 52-week curriculum successfully.",
          "Formulate custom checklist reminders for real exam day."
        ]
      }
    ]
  }
]

# ---------------------------------------------------------------------------
# Weekly Question Generators (returns exactly 3 questions)
# ---------------------------------------------------------------------------
def get_questions_for_week(week_num: int) -> list:
    current_week = None
    for term in CURRICULUM:
        for w in term["weeks"]:
            if w["weekNum"] == week_num:
                current_week = w
                break
        if current_week:
            break
            
    topic = current_week["topic"] if current_week else "Shape Sequences & Progressions"
    questions = []
    
    for q_id in range(1, 11):
        seed_val = week_num * 10 + q_id
        random.seed(seed_val)
        
        if topic == "Shape Sequences & Progressions":
            color_start = random.randint(0, 8)
            color_step = random.choice([1, 2, -1, -2])
            fixed_type = random.choice(SHAPE_TYPES)
            
            sequence = []
            for pos in range(5):
                color = COLORS[(color_start + color_step * pos) % 9]
                sequence.append(_emoji(fixed_type, color))
                
            next_color = COLORS[(color_start + color_step * 5) % 9]
            correct = _emoji(fixed_type, next_color)
            
            distractors = set()
            distractors.add(_emoji(fixed_type, COLORS[(color_start + color_step * 5 + 1) % 9]))
            other_type = SHAPE_TYPES[1] if fixed_type == SHAPE_TYPES[0] else SHAPE_TYPES[0]
            distractors.add(_emoji(other_type, next_color))
            while len(distractors) < 4:
                st, c = _random_shape(exclude=(fixed_type, next_color))
                distractors.add(_emoji(st, c))
            distractors.discard(correct)
            options = list(distractors)[:4] + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Identify which shape comes next in this progressive visual series: {'  '.join(sequence)}  [ ? ]",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"The outlines are constant ({fixed_type}s) while the color shifts. The color shifts by {color_step} positions in our list each step. This makes the next color '{next_color}', yielding {correct}.",
                "tip": "Isolate attributes! Solve outline shapes and fill colors as two separate rules."
            })
            
        elif topic == "Rotation & Angular Alignment":
            start = random.randint(0, 7)
            step = random.choice([1, 2, -1, -2])
            sequence = [ARROWS[(start + step * pos) % 8] for pos in range(5)]
            correct = ARROWS[(start + step * 5) % 8]
            
            distractors = [a for a in ARROWS if a != correct]
            options = random.sample(distractors, 4) + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            dir_desc = "clockwise" if step > 0 else "anti-clockwise"
            deg_desc = abs(step) * 45
            questions.append({
                "id": q_id,
                "questionText": f"Track the constant angular rotation. Which orientation comes next in the sequence? {'  '.join(sequence)}  [ ? ]",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"The indicator arrow rotates {dir_desc} by {deg_desc}° (or {abs(step)} step) in each transition. The last arrow is pointing {sequence[-1]}, so moving another {deg_desc}° {dir_desc} results in pointing {correct}.",
                "tip": "A standard compass has 8 points. Each step in the arrows list represents a 45° rotation."
            })
            
        elif topic == "Reflection & Mirror Lines":
            arrow = random.choice(ARROWS)
            correct = VERTICAL_MIRROR[arrow]
            
            distractors = [a for a in ARROWS if a != correct]
            options = random.sample(distractors, 4) + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"If this pointing arrow is reflected in a vertical mirror line, which way will it point? {arrow}",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"Under a vertical mirror reflection, vertical properties (up/down) are preserved, while horizontal properties (left/right) are flipped. Thus, {arrow} reflects to {correct}.",
                "tip": "Imagine a vertical line next to the arrow. The points closest to the line stay closest in the reflection."
            })
            
        elif topic == "Shape Analogies & Attribute Changes":
            color1 = random.choice(COLORS)
            type1, type2 = SHAPE_TYPES
            shape_a, shape_b = _emoji(type1, color1), _emoji(type2, color1)
            
            color2 = random.choice([c for c in COLORS if c != color1])
            shape_c, correct = _emoji(type1, color2), _emoji(type2, color2)
            
            distractors = set()
            distractors.add(_emoji(type1, color2))
            distractors.add(_emoji(type2, color1))
            while len(distractors) < 4:
                st, c = _random_shape(exclude=(type2, color2))
                distractors.add(_emoji(st, c))
            distractors.discard(correct)
            options = list(distractors)[:4] + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Solve the shape analogy relationship: {shape_a}  is to  {shape_b}  as  {shape_c}  is to  [ ? ]",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"The transformation converts a {type1} into a {type2} while preserving the color. Applying this same rule to {shape_c} ({color2} {type1}) gives a {color2} {type2}, which is {correct}.",
                "tip": "Express the relation in a simple sentence (e.g. 'swaps outline, keeps color') and apply it strictly."
            })
            
        elif topic == "Matrix Completion & Grid Logic":
            type_a, type_b = random.sample(SHAPE_TYPES, 2)
            color_a = random.choice(COLORS)
            step = random.choice([1, 2, -1, -2])
            color_b = COLORS[(COLORS.index(color_a) + step) % 9]
            
            top_left = _emoji(type_a, color_a)
            top_right = _emoji(type_a, color_b)
            bottom_left = _emoji(type_b, color_a)
            correct = _emoji(type_b, color_b)
            
            distractors = set()
            distractors.add(_emoji(type_a, color_b))
            distractors.add(_emoji(type_b, color_a))
            while len(distractors) < 4:
                st, c = _random_shape(exclude=(type_b, color_b))
                distractors.add(_emoji(st, c))
            distractors.discard(correct)
            options = list(distractors)[:4] + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Determine which cell completes the 2x2 grid logically:\n   {top_left}   {top_right}\n   {bottom_left}   [ ? ]",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"Looking horizontally, the shape type remains constant while the color shifts. Looking vertically, the shape type swaps but color is preserved. The missing cell must be {correct}.",
                "tip": "Check horizontal rules first, and verify that they also fit vertical trends."
            })
            
        elif topic == "Shape Codes & Attribute Translation":
            t = random.choice(SHAPE_TYPES)
            c = random.choice(COLORS)
            correct = COLOR_CODE[c] + SHAPE_CODE[t]
            
            example_t, example_c = _random_shape(exclude=(t, c))
            example_shape = _emoji(example_t, example_c)
            example_code = COLOR_CODE[example_c] + SHAPE_CODE[example_t]
            
            distractors = set()
            distractors.add(SHAPE_CODE[t] + COLOR_CODE[c])
            distractors.add(COLOR_CODE[example_c] + SHAPE_CODE[t])
            while len(distractors) < 4:
                rc = random.choice(COLORS)
                rt = random.choice(SHAPE_TYPES)
                candidate = COLOR_CODE[rc] + SHAPE_CODE[rt]
                if candidate != correct:
                    distractors.add(candidate)
            distractors.discard(correct)
            options = list(distractors)[:4] + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Given the code example:\n   {example_shape}  =  {example_code}\nWhat is the correct code for:  {_emoji(t, c)}?",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"The first letter represents the color ('{COLOR_CODE[c]}' for {c}), and the second letter represents the shape type ('{SHAPE_CODE[t]}' for {t}). This maps {_emoji(t, c)} to '{correct}'.",
                "tip": "Break the code letter-by-letter. Find the rule for slot 1 first, then solve slot 2."
            })
            
        elif topic == "Similarity Grouping & Group Association":
            g1_type = random.choice(SHAPE_TYPES)
            g1_colors = random.sample(COLORS, 3)
            group1 = [_emoji(g1_type, col) for col in g1_colors]
            
            g2_type = SHAPE_TYPES[1] if g1_type == SHAPE_TYPES[0] else SHAPE_TYPES[0]
            g2_colors = random.sample(COLORS, 3)
            group2 = [_emoji(g2_type, col) for col in g2_colors]
            
            test_color = random.choice([col for col in COLORS if col not in g1_colors + g2_colors])
            test_shape = _emoji(g1_type, test_color)
            
            correct = "Group 1"
            distractors = ["Group 2", "Neither group", "Both groups", "Cannot be determined"]
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Analyze the groups below:\n   Group 1: {'  '.join(group1)}\n   Group 2: {'  '.join(group2)}\nWhich group does the test shape belong to?  {test_shape}",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"Group 1 contains only {g1_type}s, while Group 2 contains only {g2_type}s. Since the test shape '{test_shape}' is a {g1_type}, it belongs to Group 1.",
                "tip": "Identify a single defining trait that is perfectly consistent across all items in a group."
            })
            
        elif topic == "Shape Counting & Combinatorial Totals":
            n_shapes = random.randint(8, 12)
            shapes = [_random_shape() for _ in range(n_shapes)]
            target_color = random.choice(COLORS)
            correct_val = sum(1 for (_, c) in shapes if c == target_color)
            
            display = "  ".join(_emoji(t, c) for t, c in shapes)
            correct = str(correct_val)
            
            distractors = set()
            for delta in [-2, -1, 1, 2]:
                cv = correct_val + delta
                if cv >= 0:
                    distractors.add(str(cv))
            while len(distractors) < 4:
                distractors.add(str(correct_val + len(distractors) + 3))
            distractors.discard(correct)
            options = list(distractors)[:4] + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Count carefully: how many shapes are coloured '{target_color}' in this set?\n   {display}",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"Scanning and tallying the elements: exactly {correct} shapes are coloured '{target_color}'.",
                "tip": "Touch each matching shape with your pencil/finger in order to prevent errors."
            })
            
        elif topic == "Layering & Overlapping Shapes":
            st1, st2 = random.sample(SHAPE_TYPES, 2)
            c1 = random.choice(COLORS)
            c2 = random.choice([col for col in COLORS if col != c1])
            emoji_a = _emoji(st1, c1)
            emoji_b = _emoji(st2, c2)
            
            correct = f"{emoji_a} is ON TOP of {emoji_b}"
            distractors = [
                f"{emoji_b} is ON TOP of {emoji_a}",
                f"{emoji_a} is completely side-by-side with {emoji_b}",
                f"{emoji_a} is nested inside {emoji_b}",
                f"{emoji_b} is nested inside {emoji_a}",
            ]
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"In a layered diagram, Shape X has an unbroken complete outline, while Shape Y's border is partially hidden. If Shape X is {emoji_a} and Shape Y is {emoji_b}, which is correct?",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"An unbroken outline means Shape X ({emoji_a}) lies in the foreground, on top of Shape Y ({emoji_b}).",
                "tip": "The shape with the fully continuous, unbroken border is always the top-most layered shape."
            })
            
        elif topic == "3D Spatial Nets & Isometric Reasoning":
            correct = "🟩 (Bottom)"
            distractors = ["🔴 (Front)", "🔵 (Left)", "🟡 (Right)", "⚫ (Back)"]
            options = distractors + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"A standard cube has faces: 🔴 (Top), 🟩 (Front), 🔵 (Right). If we tilt the cube backward by 90 degrees so the Front face (🟩) is now on the bottom, which face goes to the bottom?",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"A 90-degree backward tilt moves the Front face (🟩) directly to the bottom.",
                "tip": "Visualize the face movements physically by tilting a nearby object like an eraser."
            })
            
        else: # Odd One Out / default fallback
            shared_type = random.choice(SHAPE_TYPES)
            shared_colors = random.sample(COLORS, 4)
            same_group = [_emoji(shared_type, col) for col in shared_colors]
            
            odd_type = SHAPE_TYPES[1] if shared_type == SHAPE_TYPES[0] else SHAPE_TYPES[0]
            odd_color = random.choice([col for col in COLORS if col not in shared_colors])
            correct = _emoji(odd_type, odd_color)
            
            options = same_group + [correct]
            random.shuffle(options)
            
            correct_letter = ["A", "B", "C", "D", "E"][options.index(correct)]
            
            questions.append({
                "id": q_id,
                "questionText": f"Select the odd shape out that does NOT belong to the same logical category:",
                "options": options,
                "correctLetter": correct_letter,
                "correctValue": correct,
                "explanation": f"Four of the shapes are {shared_type}s. Only '{correct}' is a {odd_type}, making it the odd one out.",
                "tip": "Find a rule that groups exactly four of the options together first."
            })
            
    return questions

# ---------------------------------------------------------------------------
# Markdown Curriculum String Generator
# ---------------------------------------------------------------------------
def generate_markdown_plan() -> str:
    md = [
        "# Eleven Plus (11+) Non-Verbal Reasoning Study Plan",
        "## The 52-Week Year-Round Curriculum & Homework Sets",
        "**Coach Pip's Selective Grammar School Entrance Training Core**",
        "*Prepared for the GL Assessment, CEM, and Super-Selective Stage Two Exams*",
        "",
        "---",
        "",
        "## STUDY PLAN OVERVIEW",
        "Preparing for highly competitive UK selective schools (like Henrietta Barnett, Tiffin, CSSE, and St Olave's) requires a systematic, spaced approach. This 52-week plan covers the complete 11+ Non-Verbal Reasoning syllabus, divided into four strategic terms:",
        "1. **Term 1 (Weeks 1-13)**: Visual Sequences, Rotations & Symmetry",
        "2. **Term 2 (Weeks 14-26)**: Analogies, Matrices & Grid Completion",
        "3. **Term 3 (Weeks 27-39)**: Coding, Groupings & Counting",
        "4. **Term 4 (Weeks 40-52)**: 3D Spatial Reasoning & Advanced Exam Mastery",
        "",
        "Each week contains core focus objectives and a **Homework Set of 10 Selective-School Style questions** with answer keys, worked explanations, and coaching advice.",
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
            md.append(f"*(This week includes {len(questions)} selective-school style practice questions)*\n")
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
    md.append("*Congratulations on working through this plan! Regular practice, spatial visualizations, and careful logical analysis of shapes are the keys to securing a high-accuracy selective school score.*")
    return "\n".join(md)

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main():
    print("==========================================================")
    print("      11+ Non-Verbal Reasoning 52-Week Year-Round Plan Gen")
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
    json_path = "11_Plus_NVR_52_Week_Plan.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_plan_data, f, indent=2, ensure_ascii=False)
    print(f"[Success] Saved 52-Week Plan JSON to: {json_path}")

    # Save to Markdown
    md_path = "11_Plus_NVR_52_Week_Plan.md"
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
                        f"11+ Non-Verbal Reasoning 52-Week Plan - Term {term['termId']} - Week {week['weekNum']}\n"
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
                        "subject": "NonVerbalReasoning-1year",
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
                        "doc_id": f"elevenplus_nvr_year_round_week_{week['weekNum']:02d}"
                    })
            
            store.add_batch_homework(batch_data)
            print("Successfully loaded 52 weekly plan entries into the RAG Store.")
        except Exception as e:
            print(f"RAG Integration skipped or failed: {e}")
    else:
        print("\nNote: RAG Store is not available in standalone execution. Local files generated successfully.")

if __name__ == "__main__":
    main()
