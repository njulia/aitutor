#!/bin/bash
# Homework Magic Launcher

echo "========================================"
echo "  Homework Magic - AI Tutor (FastAPI)"
echo "========================================"
echo ""

if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

echo "Generating SEO pages..."
python generate_landing_pages.py

if [ -f "templates/elevenplus-practice.html" ] && [ ! -f "static/elevenplus-practice.html" ]; then
    cp templates/elevenplus-practice.html static/
fi

echo ""
echo "Starting Homework Magic on http://localhost:5000"
echo "  AI Tutor:  http://localhost:5000/app"
echo ""
python web_app.py
