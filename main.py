#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Tutor - entry point.

Default: FastAPI web application (SEO pages + AI tutor UI).
Optional: terminal mode (--tui) or one-shot homework generation (--prompt).
"""

import argparse
import logging

from src.agent_workflow import init_llm
from src.homework_manager import process_homework_with_review
from src.ui import run_tui

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("aitutor.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run AI Tutor")
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Run in terminal interactive mode",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Input prompt for homework generation/import with review",
    )
    args = parser.parse_args()

    try:
        if args.tui:
            llm, _, _ = init_llm()
            run_tui(llm)
        elif args.prompt:
            llm, _, _ = init_llm()
            filepath = process_homework_with_review(args.prompt, "student1")
            logger.info("Done! Homework with review saved to: %s", filepath)
        else:
            from web_app import main as run_web

            run_web()
    except KeyboardInterrupt:
        logger.warning("Interrupted.")
    finally:
        logger.info("Exiting.")


if __name__ == "__main__":
    main()
