#!/bin/bash
# Homework Magic Launcher

echo "========================================"
echo "  Homework Magic - AI Tutor"
echo "========================================"
echo ""

# Check if virtual environment exists (optional)
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Ensure static files are generated
echo "Generating SEO pages..."
python generate_landing_pages.py

# Copy 11-plus-practice.html if needed
if [ -f "templates/11-plus-practice.html" ] && [ ! -f "static/11-plus-practice.html" ]; then
    cp templates/11-plus-practice.html static/
fi

echo ""
echo "========================================"
echo "Choose how to run:"
echo "========================================"
echo "1. Run only SEO pages (Flask on port 5000)"
echo "2. Run only AI Tutor (Gradio on port 7860)"
echo "3. Run both (requires two terminals)"
echo ""
read -p "Enter your choice (1, 2, or 3): " choice

case $choice in
    1)
        echo ""
        echo "Starting SEO pages server..."
        echo "Open http://localhost:5000 in your browser"
        echo ""
        python app.py
        ;;
    2)
        echo ""
        echo "Starting AI Tutor..."
        echo "Open http://localhost:7860 in your browser"
        echo ""
        python main.py
        ;;
    3)
        echo ""
        echo "========================================"
        echo "You need to open TWO terminals:"
        echo "========================================"
        echo ""
        echo "Terminal 1 (SEO pages):"
        echo "  cd $(pwd)"
        echo "  python app.py"
        echo ""
        echo "Terminal 2 (AI Tutor):"
        echo "  cd $(pwd)"
        echo "  python main.py"
        echo ""
        echo "Then open:"
        echo "  • http://localhost:5000 (SEO pages)"
        echo "  • http://localhost:7860 (AI Tutor)"
        echo ""
        ;;
    *)
        echo "Invalid choice. Exiting."
        ;;
esac
