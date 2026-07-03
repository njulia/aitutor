#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Homework Magic - Unified Launcher

This script launches the new integrated Flask application
that includes both SEO pages and the AI tutor.
"""

import os
import sys
import webbrowser
import shutil


def generate_seo_pages():
    """Generate SEO landing pages first."""
    print("🔧 Generating SEO pages...")
    try:
        import generate_landing_pages
        print("✓ SEO pages generated")
    except Exception as e:
        print(f"Note: Could not regenerate landing pages: {e}")

    # Copy 11-plus-practice.html to static folder
    project_root = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(project_root, 'templates', '11-plus-practice.html')
    dst = os.path.join(project_root, 'static', '11-plus-practice.html')

    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy(src, dst)
        print("✓ Copied 11-plus-practice.html")


def main():
    # First generate SEO pages
    generate_seo_pages();

    print("\n" + "=" * 70)
    print("  ✨ Homework Magic - AI Tutor")
    print("=" * 70)
    print("\nStarting integrated Flask application...")
    print("\n📄 Homepage:        http://localhost:5000")
    print("🚀 AI Tutor App:    http://localhost:5000/app")
    print("📚 KS1 Homework:    http://localhost:5000/ks1-homework")
    print("📚 KS2 Homework:    http://localhost:5000/ks2-homework")
    print("🎯 11+ Practice:    http://localhost:5000/11-plus-practice")
    print("✅ Check Homework:  http://localhost:5000/check-my-homework")
    print("\nPress Ctrl+C to stop the server\n")

    # Try to open browser
    try:
        import time
        time.sleep(1.5)
        webbrowser.open("http://localhost:5000")
        print("🌐 Opening browser...")
    except:
        pass

    # Start the web app
    os.execvp(sys.executable, [sys.executable, "web_app.py"])


if __name__ == "__main__":
    main()
