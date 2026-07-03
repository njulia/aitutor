#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Homework Magic Web Application

Simple Flask server for SEO-friendly pages only.
Gradio should be run separately.
"""

import os
import sys
import shutil
from flask import Flask, send_from_directory, render_template_string

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='')


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/ks1-homework')
def ks1_homework():
    return send_from_directory('static', 'ks1-homework.html')


@app.route('/ks2-homework')
def ks2_homework():
    return send_from_directory('static', 'ks2-homework.html')


@app.route('/11-plus-practice')
def eleven_plus_practice():
    return send_from_directory('static', '11-plus-practice.html')


@app.route('/check-my-homework')
def check_my_homework():
    return send_from_directory('static', 'check-my-homework.html')


@app.route('/app')
def app_redirect():
    # Simple page telling user how to run Gradio
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en-GB">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Homework Magic - Run the App</title>
        <style>
            body {
                font-family: 'Google Sans', Arial, sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                line-height: 1.6;
            }
            h1 { color: #4285F4; }
            .code-block {
                background: #f5f5f5;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                font-family: monospace;
            }
            .note {
                background: #e3f2fd;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
            }
            .nav-links a {
                display: inline-block;
                margin: 10px 20px 10px 0;
                color: #4285F4;
                text-decoration: none;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <h1>🚀 Run Homework Magic App</h1>

        <div class="note">
            <strong>Note:</strong> The Gradio AI tutor needs to be started separately.
        </div>

        <h2>How to run the app:</h2>

        <div class="code-block">
            # Open a new terminal and run:<br>
            cd {{ project_root }}<br>
            python main.py
        </div>

        <h2>Or use these quick links:</h2>
        <div class="nav-links">
            <a href="/">← Back to Homepage</a>
            <a href="http://localhost:7860" target="_blank">Open Gradio (if running)</a>
        </div>

    </body>
    </html>
    """, project_root=project_root)


def ensure_static_files():
    """Ensure all necessary static files are in place."""
    # Copy 11-plus-practice.html to static folder
    eleven_plus_src = os.path.join(project_root, 'templates', '11-plus-practice.html')
    eleven_plus_dest = os.path.join(project_root, 'static', '11-plus-practice.html')

    if os.path.exists(eleven_plus_src) and not os.path.exists(eleven_plus_dest):
        shutil.copy(eleven_plus_src, eleven_plus_dest)
        print("✓ Copied 11-plus-practice.html to static folder")

    # Also run the landing page generator to make sure files exist
    try:
        import generate_landing_pages
        print("✓ Generated landing pages")
    except Exception as e:
        print(f"Note: Could not regenerate landing pages: {e}")


def main():
    # First ensure static files are present
    ensure_static_files()

    print("\n" + "=" * 70)
    print("  📚 Homework Magic - SEO Landing Pages")
    print("=" * 70)
    print("\n📄 SEO-friendly pages available at:")
    print(f"  • http://localhost:5000/ (Homepage)")
    print(f"  • http://localhost:5000/ks1-homework")
    print(f"  • http://localhost:5000/ks2-homework")
    print(f"  • http://localhost:5000/11-plus-practice")
    print(f"  • http://localhost:5000/check-my-homework")
    print("\n🚀 To run the AI tutor app, open a NEW terminal and run:")
    print(f"  cd {project_root}")
    print(f"  python main.py")
    print("\n💡 The Gradio app will then be available at http://localhost:7860")
    print("\n" + "=" * 70)
    print("\nPress Ctrl+C to stop the server\n")

    # Start Flask on port 5000
    app.run(debug=False, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
