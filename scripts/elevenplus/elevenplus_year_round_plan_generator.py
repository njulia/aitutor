#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Backward-compatible entry point for the Maths 52-week generator."""
from scripts.elevenplus.elevenplus_math_year_round_plan_generator import (
    CURRICULUM,
    build_plan_data,
    build_rag_batch,
    generate_markdown_plan,
    get_questions_for_week,
    main,
)

__all__ = [
    "CURRICULUM",
    "get_questions_for_week",
    "build_plan_data",
    "build_rag_batch",
    "generate_markdown_plan",
    "main",
]

if __name__ == "__main__":
    main()
