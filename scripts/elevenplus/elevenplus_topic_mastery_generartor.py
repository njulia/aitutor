#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Backward-compatible entry point for the Maths topic-mastery generator."""
from scripts.elevenplus.elevenplus_math_topic_mastery_generator import (
    MASTERY_TIERS,
    TOPIC_LIST,
    generate_topic_mastery_plan,
    main,
    save_to_json,
    save_to_markdown,
)

__all__ = [
    "MASTERY_TIERS",
    "TOPIC_LIST",
    "generate_topic_mastery_plan",
    "save_to_json",
    "save_to_markdown",
    "main",
]

if __name__ == "__main__":
    main()
