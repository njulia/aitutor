#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ Non-Verbal Reasoning 55-Set Topic-Mastery Plan Generator
============================================================

Generates a comprehensive 55-Set Topic-Mastery Non-Verbal Reasoning curriculum
(11 key topics, each with exactly 5 progressive homework sets, each set consisting
of 10 examination-style multiple-choice questions with worked solutions and private coaching tips).

Saves the generated plan to:
  - 11_Plus_NVR_55_Set_Topic_Mastery_Plan.json
  - 11_Plus_NVR_55_Set_Topic_Mastery_Plan.md

Also registers them in the RAG vector store for instant student access.
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from scripts.elevenplus.elevenplus_nvr_generator import generate_11plus_nvr_homework
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    generate_11plus_nvr_homework = None
    get_elevenplus_rag_store = None

from scripts.elevenplus.elevenplus_generator_utils import (
    ensure_unique_question_stems,
    normalise_difficulty,
    recommended_set_minutes,
    render_student_question_set,
    validate_answer_records,
)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Define the 11 topics explicitly to ensure correct order and exact 55 sets
TOPIC_LIST = [
    "Shape Sequences & Progressions",
    "Rotation & Angular Alignment",
    "Odd One Out & Shape Discrepancy",
    "Shape Analogies & Attribute Changes",
    "Matrix Completion & Grid Logic",
    "Shape Codes & Attribute Translation",
    "Similarity Grouping & Group Association",
    "Shape Counting & Combinatorial Totals",
    "Reflection & Mirror Lines",
    "Layering & Overlapping Shapes",
    "3D Spatial Nets & Isometric Reasoning"
]

# Define the 5 progressive tiers of mastery
MASTERY_TIERS = {
    1: {"name": "Foundational Basics", "difficulty": "Foundational"},
    2: {"name": "Intermediate Application", "difficulty": "Standard"},
    3: {"name": "Advanced Practice", "difficulty": "Advanced"},
    4: {"name": "Selective School Challenge", "difficulty": "Selective / Hard"},
    5: {"name": "Ultimate Mastery & Mixed Drill", "difficulty": "Mastery"}
}

def generate_topic_mastery_plan() -> list:
    """Generate all 55 sets of the Non-Verbal Reasoning Topic-Mastery Plan."""
    print("Generating the 55-Set Non-Verbal Reasoning Topic-Mastery Curriculum...")
    
    if not generate_11plus_nvr_homework:
        print("Error: Could not import generators from elevenplus_nvr_generator.py!")
        sys.exit(1)

    all_sets = []
    global_set_index = 1

    for topic_idx, topic in enumerate(TOPIC_LIST, start=1):
        print(f"\nProcessing Topic {topic_idx}/11: {topic}")
        
        for set_num in range(1, 6):
            tier_info = MASTERY_TIERS[set_num]
            
            # Use deterministic but randomized seed/index offset so each set has unique questions
            seed_index = topic_idx * 100 + set_num
            
            # Generate the 10 MCQ questions for this set
            _, answer_records = generate_11plus_nvr_homework(topic, seed_index, difficulty=tier_info["difficulty"])
            
            # Modify and decorate the content to highlight the mastery level
            header = (
                f"========================================================================\n"
                f"11+ NON-VERBAL REASONING TOPIC MASTERY PLAN - SET {global_set_index} of 55\n"
                f"Topic: {topic}\n"
                f"Mastery Level {set_num}: {tier_info['name']} ({tier_info['difficulty']})\n"
                f"========================================================================\n\n"
                f"Instructions: Answer each of the 10 questions by choosing the correct option (A-E).\n"
                f"Suggested Time: {recommended_set_minutes(tier_info['difficulty'])} minutes. "
                f"Work accurately first, then improve speed.\n\n"
            )
            answer_records = ensure_unique_question_stems(answer_records)
            validate_answer_records(answer_records)
            final_content = header + render_student_question_set(answer_records)
            
            # Build Metadata compatible with ChromaDB sanitization rules
            metadata = {
                "year_group": 6,
                "subject": "NonVerbalReasoning-topic-mastery",
                "content_type": "topic_mastery",
                "homework_minutes": "10",
                "key_stage": "11+",
                "topic": topic,
                "exam_style": "GL Assessment & Selective Style",
                "school_tier": "Selective (Henrietta Barnett / Tiffin / CSSE / St Olave's style)" if set_num >= 4 else "Standard (GL Assessment style)",
                "question_format": "multiple_choice_5_options",
                "mastery_set_index": global_set_index,
                "mastery_level": set_num,
                "mastery_tier_name": tier_info["name"],
                "mastery_difficulty": normalise_difficulty(tier_info["difficulty"]),
                "question_count": 10,
                "answer_schema_version": 2,
                "generator_version": "2026.07",
                "correct_answers": json.dumps(answer_records, ensure_ascii=False),
                "created_at": datetime.now().isoformat()
            }
            
            doc_id = f"elevenplus_nvr_mastery_set_{global_set_index:03d}"
            
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
    print(f"\n[Success] Saved Non-Verbal Reasoning Topic-Mastery JSON data to: {filepath}")

def save_to_markdown(all_sets: list, filepath: str):
    """Save the full curriculum to an elegant Markdown file."""
    md_lines = []
    md_lines.append("# 11+ Non-Verbal Reasoning 55-Set Topic-Mastery Curriculum & Practice Sets\n")
    md_lines.append("Formulated for Henrietta Barnett, Tiffin, CSSE, and St Olave's Non-Verbal Reasoning papers.\n")
    md_lines.append("## Curriculum Index\n")
    
    for topic_idx, topic in enumerate(TOPIC_LIST, start=1):
        md_lines.append(f"### Topic {topic_idx}: {topic}")
        for set_num in range(1, 6):
            tier_info = MASTERY_TIERS[set_num]
            global_idx = (topic_idx - 1) * 5 + set_num
            md_lines.append(f"- **Set {global_idx:02d}** (Level {set_num}): {tier_info['name']} (*{tier_info['difficulty']}*)")
        md_lines.append("")
        
    md_lines.append("\n---\n")
    
    for s in all_sets:
        md_lines.append(f"## Global Set {s['metadata']['mastery_set_index']}: {s['topic']}")
        md_lines.append(f"**Level {s['set_num']}:** {s['tier_name']} | **Difficulty:** {s['difficulty']}\n")
        md_lines.append("```text")
        md_lines.append(s["content"])
        md_lines.append("```\n")
        
        md_lines.append("### Answer Key & Worked Solutions\n")
        for q in s["questions"]:
            md_lines.append(f"#### Q{q['q']}. Correct Option: **{q['correct_letter']}** ({q['correct_value']})")
            md_lines.append(f"**Explanation:**\n{q['explanation']}\n")
            if "tip" in q and q["tip"]:
                md_lines.append(f"*Private Coach Pip's Strategy:* *{q['tip']}*\n")
        md_lines.append("\n---\n")
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"[Success] Saved Non-Verbal Reasoning Topic-Mastery Markdown to: {filepath}")

def main():
    print("==========================================================")
    print(" 11+ Non-Verbal Reasoning 55-Set Topic-Mastery Curriculum ")
    print("==========================================================\n")
    
    all_sets = generate_topic_mastery_plan()
    
    # Save files to workspace root
    save_to_json(all_sets, "11_Plus_NVR_55_Set_Topic_Mastery_Plan.json")
    save_to_markdown(all_sets, "11_Plus_NVR_55_Set_Topic_Mastery_Plan.md")
    
    # Expose to RAG if available
    if get_elevenplus_rag_store:
        try:
            print("\nRegistering Non-Verbal Reasoning Topic-Mastery sets with the RAG Store...")
            store = get_elevenplus_rag_store()
            print(f"RAG target: {store.store.database_target}")
            
            batch_data = []
            for s in all_sets:
                batch_data.append({
                    "content": s["content"],
                    "metadata": s["metadata"],
                    "doc_id": s["doc_id"]
                })
                
            store.add_batch_homework(batch_data)
            print(f"Successfully loaded {len(all_sets)} sets into the RAG Store.")
        except Exception as e:
            print(f"Error registering with RAG Store: {e}")

if __name__ == "__main__":
    main()
