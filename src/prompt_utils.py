#!/usr/bin/env python3

"""Prompt optimization helpers to reduce token usage while preserving meaning."""
import hashlib

MAX_SECTION = 1200


def compact_text(text: str, keep_head: int = 800, keep_tail: int = 200) -> str:
    if not text:
        return text
    if len(text) <= MAX_SECTION:
        return text
    # keep head and tail
    head = text[:keep_head].rstrip()
    tail = text[-keep_tail:].lstrip()
    return head + "\n... (truncated) ...\n" + tail


def optimize_kwargs(kwargs: dict) -> dict:
    """Compact common long fields used in prompts."""
    new = dict(kwargs)
    for key in ("homework_content", "student_profile", "review_feedback", "student_answer", "learning_data"):
        if key in new and isinstance(new[key], str):
            new[key] = compact_text(new[key])
    # If profile is a dict, compress to key fields
    if isinstance(new.get("student_profile"), dict):
        prof = new["student_profile"]
        short = {k: prof.get(k) for k in ("year_group", "age", "student_id", "english_level")} if prof else {}
        new["student_profile"] = str(short)
    return new


def compact_format(template: str, **kwargs) -> str:
    opt = optimize_kwargs(kwargs)
    return template.format(**opt)
