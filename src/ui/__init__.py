#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UI package - terminal and shared helpers.

The web interface is served by the FastAPI app in web_app.py.
Run: python web_app.py  or  python launch.py
"""

from src.ui.tui import run_tui
from src.ui.shared import parse_profile_from_natural_language, display_homeworks


def run_web():
    """Start the FastAPI web application."""
    from web_app import main

    main()


__all__ = [
    "run_tui",
    "run_web",
    "parse_profile_from_natural_language",
    "display_homeworks",
]
