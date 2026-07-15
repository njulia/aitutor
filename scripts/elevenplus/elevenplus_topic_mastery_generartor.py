#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ Maths 55-Set Topic-Mastery Plan Generator
=============================================

Generates a comprehensive 55-Set Topic-Mastery curriculum (11 key topics,
each with exactly 5 progressive homework sets, each set consisting of 10
examination-style multiple-choice questions with worked solutions and private coaching tips).

Saves the generated plan to:
  - 11_Plus_Maths_55_Set_Topic_Mastery_Plan.json
  - 11_Plus_Maths_55_Set_Topic_Mastery_Plan.md

Also registers them in the RAG vector store for instant student access.
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from scripts.elevenplus.elevenplus_math_generator import generate_11plus_homework, ELEVEN_PLUS_TOPICS
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    # Safe fallback if run in isolated python environments
    generate_11plus_homework = None
    ELEVEN_PLUS_TOPICS = []
    get_elevenplus_rag_store = None

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Define the 11 topics explicitly to ensure correct order
TOPIC_LIST = [
    "Number: Arithmetic & Mental Maths",
    "Number: Fractions, Decimals & Percentages",
    "Number: Primes, Factors & Multiples",
    "Non-Routine Reasoning (Top-School Style)",
    "Ratio and Proportion",
    "Algebra Basics",
    "Shape, Space and Measures",
    "Data Handling and Graphs",
    "Worded Problem Solving",
    "Speed, Distance and Time",
    "Sequences and Patterns"
]

# Define the 5 progressive tiers of mastery
MASTERY_TIERS = {
    1: {"name": "Foundational Basics", "difficulty": "Foundational"},
    2: {"name": "Intermediate Application", "difficulty": "Standard"},
    3: {"name": "Advanced practice", "difficulty": "Advanced"},
    4: {"name": "Selective School Challenge", "difficulty": "Selective / Hard"},
    5: {"name": "Ultimate Mastery & Mixed Drill", "difficulty": "Mastery"}
}


def generate_topic_mastery_plan() -> list:
    """Generate all 55 sets of the Topic-Mastery Plan."""
    print("Generating the 55-Set Topic-Mastery Curriculum...")

    if not generate_11plus_homework:
        print("Error: Could not import generators from elevenplus_math_generator.py!")
        sys.exit(1)

    all_sets = []
    global_set_index = 1

    for topic_idx, topic in enumerate(TOPIC_LIST, start=1):
        print(f"\nProcessing Topic {topic_idx}/11: {topic}")

        for set_num in range(1, 6):
            tier_info = MASTERY_TIERS[set_num]

            # We use a deterministic but randomized seed/index offset so each set has unique numbers
            seed_index = topic_idx * 100 + set_num

            # Generate the 10 MCQ questions for this set
            raw_content, answer_records = generate_11plus_homework(topic, seed_index)

            # Modify and decorate the content to highlight the mastery level
            header = (
                f"========================================================================\n"
                f"11+ TOPIC MASTERY PLAN - SET {global_set_index} of 55\n"
                f"Topic: {topic}\n"
                f"Mastery Level {set_num}: {tier_info['name']} ({tier_info['difficulty']})\n"
                f"========================================================================\n\n"
                f"Instructions: Answer each of the 10 questions by choosing the correct option (A-E).\n"
                f"Time Limit: 10 minutes. Aim for high accuracy and review worked solutions.\n\n"
            )

            # Strip the old header if it exists
            lines = raw_content.split("\n")
            cleaned_lines = []
            skip_header = True
            for line in lines:
                if skip_header and (line.startswith("11+ Maths Practice") or line.startswith("Answer each question")):
                    continue
                if skip_header and len(line.strip()) == 0:
                    continue
                skip_header = False
                cleaned_lines.append(line)

            final_content = header + "\n".join(cleaned_lines)

            # Build Metadata compatible with ChromaDB sanitization rules
            metadata = {
                "year_group": 6,
                "subject": "Maths",
                "homework_minutes": "10",
                "key_stage": "11+",
                "topic": topic,
                "exam_style": "GL Assessment & Selective Style",
                "school_tier": "Selective (Tiffin / Henrietta Barnett / St Olave's / Kent Test / CSSE style)" if set_num >= 4 else "Standard (GL Assessment style)",
                "question_format": "multiple_choice_5_options",
                "mastery_set_index": global_set_index,
                "mastery_level": set_num,
                "mastery_tier_name": tier_info["name"],
                "mastery_difficulty": tier_info["difficulty"],
                "correct_answers": json.dumps(answer_records, ensure_ascii=False),
                "created_at": datetime.now().isoformat()
            }

            doc_id = f"elevenplus_mastery_set_{global_set_index:03d}"

            all_sets.append({
                "doc_id": doc_id,
                "topic": topic,
                "set_num": set_num,
                "tier_name": tier_info["name"],
                "difficulty": tier_info["difficulty"],
                "content": final_content,
                "metadata": metadata,
                "questions": answer_records
            })

            print(f"  -> Generated Set {set_num}/5: {tier_info['name']} (Global Set {global_set_index:02d}/55)")
            global_set_index += 1

    return all_sets


def save_to_json(all_sets: list, filepath: str):
    """Save the full curriculum to a clean JSON file."""
    # We clean up some python-specific fields before writing to JSON
    json_data = []
    for s in all_sets:
        json_data.append({
            "doc_id": s["doc_id"],
            "topic": s["topic"],
            "set_index": s["metadata"]["mastery_set_index"],
            "mastery_level": s["set_num"],
            "tier_name": s["tier_name"],
            "difficulty": s["difficulty"],
            "content": s["content"],
            "metadata": s["metadata"]
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"\n[Success] Saved Topic-Mastery JSON data to: {filepath}")


def save_to_markdown(all_sets: list, filepath: str):
    """Save the full curriculum to an elegant Markdown file."""
    md_lines = []
    md_lines.append("# 11+ Maths 55-Set Topic-Mastery Curriculum & Practice Sets\n")
    md_lines.append("Formulated for Henrietta Barnett, Tiffin, CSSE, and St Olave's maths entrance papers.\n")
    md_lines.append("## Curriculum Index\n")

    for topic_idx, topic in enumerate(TOPIC_LIST, start=1):
        md_lines.append(f"### Topic {topic_idx}: {topic}")
        for set_num in range(1, 6):
            tier_info = MASTERY_TIERS[set_num]
            global_idx = (topic_idx - 1) * 5 + set_num
            md_lines.append(
                f"- **Set {global_idx:02d}** (Level {set_num}): {tier_info['name']} (*{tier_info['difficulty']}*)")
        md_lines.append("")

    md_lines.append("\n---\n")

    for s in all_sets:
        md_lines.append(f"## Global Set {s['metadata']['mastery_set_index']}: {s['topic']}")
        md_lines.append(f"**Level {s['set_num']}:** {s['tier_name']} | **Difficulty:** {s['difficulty']}\n")
        md_lines.append("```text")
        md_lines.append(s["content"])
        md_lines.append("```\n")

        md_lines.append("### Answer Key & worked Solutions\n")
        for q in s["questions"]:
            md_lines.append(f"#### Q{q['q']}. Correct Option: **{q['correct_letter']}** ({q['correct_value']})")
            md_lines.append(f"**Explanation:**\n{q['explanation']}\n")
            if "tip" in q and q["tip"]:
                md_lines.append(f"*Private Coach Pip's Strategy:* *{q['tip']}*\n")
        md_lines.append("\n---\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"[Success] Saved Topic-Mastery Markdown to: {filepath}")


def main():
    print("==========================================================")
    print("   11+ Maths 55-Set Topic-Mastery Curriculum Generator    ")
    print("==========================================================\n")

    all_sets = generate_topic_mastery_plan()

    # Save files to workspace root for easy download and verification
    save_to_json(all_sets, "11_Plus_Maths_55_Set_Topic_Mastery_Plan.json")
    save_to_markdown(all_sets, "11_Plus_Maths_55_Set_Topic_Mastery_Plan.md")

    # Expose them to RAG if available
    if get_elevenplus_rag_store:
        try:
            print("\nRegistering Topic-Mastery sets with the RAG Store...")
            store = get_elevenplus_rag_store()
            print(f"RAG target: {store.store.database_target}")

            # Format into batch homework objects for get_elevenplus_rag_store()
            batch_data = []
            for s in all_sets:
                batch_data.append({
                    "content": s["content"],
                    "metadata": s["metadata"],
                    "doc_id": s["doc_id"]
                })

            store.add_batch_homework(batch_data)
            print(f"Successfully loaded 55 sets into the RAG Store.")
        except Exception as e:
            print(f"RAG Integration skipped or failed: {e}")
    else:
        print("\nNote: RAG Store is not available in standalone execution. Local files generated successfully.")


if __name__ == "__main__":
    main()
