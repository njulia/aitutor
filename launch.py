#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Homework Magic - Unified Launcher

Starts the integrated FastAPI application (SEO pages + AI tutor).
"""

import os
import sys
import webbrowser
import shutil


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_local_environment():
    """Load this checkout's development settings before app imports.

    ``launch.py`` is the local-development entry point.  Make its project
    ``.env`` authoritative so values exported for Cloud SQL Proxy or a prior
    production shell (commonly using port 5433) cannot silently replace the
    local PostgreSQL settings (port 5432 in ``docker-compose.yml``).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)


# PyCharm may start the script with a different working directory. Load the
# project .env before importing any application modules.
load_local_environment()


def generate_seo_pages():
    """Generate SEO landing pages first."""
    print("Generating SEO pages...")
    try:
        import generate_landing_pages  # noqa: F401
        print("SEO pages generated")
    except Exception as exc:
        print(f"Note: Could not regenerate landing pages: {exc}")

    src = os.path.join(PROJECT_ROOT, "templates", "elevenplus-practice.html")
    dst = os.path.join(PROJECT_ROOT, "static", "elevenplus-practice.html")

    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy(src, dst)
        print("Copied elevenplus-practice.html")


def main():
    # Make all relative paths deterministic when launched from PyCharm.
    os.chdir(PROJECT_ROOT)
    generate_seo_pages()

    print("\n" + "=" * 70)
    print("  Homework Magic - AI Tutor (FastAPI)")
    print("=" * 70)
    print("\nStarting integrated web application...")
    print("\n  Homepage:        http://localhost:5000")
    print("  AI Tutor App:    http://localhost:5000/app")
    print("  KS1 Homework:    http://localhost:5000/ks1-homework")
    print("  KS2 Homework:    http://localhost:5000/ks2-homework")
    print("  11+ Practice:    http://localhost:5000/elevenplus-practice")
    # print("  Mark Homework:  http://localhost:5000/check-my-homework")
    print("\nPress Ctrl+C to stop the server\n")

    try:
        import time

        time.sleep(1.5)
        webbrowser.open("http://localhost:5000")
        print("Opening browser...")
    except Exception:
        pass

    os.execv(sys.executable, [sys.executable, os.path.join(PROJECT_ROOT, "web_app.py")])


if __name__ == "__main__":
    main()
