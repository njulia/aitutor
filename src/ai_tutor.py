#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Hybrid Agent - AI Tutor for UK Primary School Students (Year 1 to Year 6)

A hybrid agent implemented with LangGraph that combines the instant response capability of reactive architecture
with the long-term planning capability of deliberative architecture, dynamically switching processing modes
through a coordination layer to provide intelligent English tutoring services for UK primary school students.

Three-tier architecture:
1. Bottom layer (Reactive): Instant response to student questions with fast feedback
2. Middle layer (Coordination): Evaluates question types and difficulty, dynamically selects processing mode
3. Top layer (Deliberative): Performs learning analysis and creates personalized study plans

Usage:
    python -m src.ai_tutor              # Web GUI mode (default)
    python -m src.ai_tutor --tui        # Terminal interactive mode
    python -m src.ai_tutor --prompt "..."  # Generate homework from prompt
"""

import argparse
import logging

from src.agent_workflow import run_english_tutor, init_llm
from src.homework_manager import process_homework_with_review
from src.ui import run_gui, run_tui

# Configure logging settings
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("aitutor.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for AI Tutor"""
    parser = argparse.ArgumentParser(description="Run AI Tutor")
    parser.add_argument(
        "--tui", action="store_true", required=False,
        help="Run in terminal interactive mode"
    )
    parser.add_argument(
        "--prompt", type=str, required=False,
        help="Input prompt for homework generation/import with review"
    )
    args = parser.parse_args()

    try:
        llm, _, _ = init_llm()

        if args.tui:
            run_tui(llm)
        elif args.prompt:
            user_input = args.prompt
            student_id = "student1"
            filepath = process_homework_with_review(user_input, student_id)
            logger.info(f"\nDone! Homework with review saved to: {filepath}")
        else:
            run_gui(llm)
    except KeyboardInterrupt:
        logger.warning("操作被中断。")
    finally:
        logger.info("程序退出。")


if __name__ == "__main__":
    main()
