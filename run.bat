@echo off
REM Homework Magic Launcher for Windows

echo ========================================
echo   Homework Magic - AI Tutor
echo ========================================
echo.

REM Ensure static files are generated
echo Generating SEO pages...
python generate_landing_pages.py

REM Copy elevenplus-practice.html if needed
if exist "templates\elevenplus-practice.html" if not exist "static\elevenplus-practice.html" (
    copy "templates\elevenplus-practice.html" "static\"
)

echo.
echo ========================================
echo Choose how to run:
echo ========================================
echo 1. Run only SEO pages (Flask on port 5000^)
echo 2. Run only AI Tutor (Gradio on port 7860^)
echo 3. Show instructions for running both
echo.
set /p choice="Enter your choice (1, 2, or 3^): "

if "%choice%"=="1" (
    echo.
    echo Starting SEO pages server...
    echo Open http://localhost:5000 in your browser
    echo.
    python app.py
) else if "%choice%"=="2" (
    echo.
    echo Starting AI Tutor...
    echo Open http://localhost:7860 in your browser
    echo.
    python main.py
) else if "%choice%"=="3" (
    echo.
    echo ========================================
    echo You need to open TWO command prompts:
    echo ========================================
    echo.
    echo Command Prompt 1 (SEO pages^):
    echo   cd %CD%
    echo   python app.py
    echo.
    echo Command Prompt 2 (AI Tutor^):
    echo   cd %CD%
    echo   python main.py
    echo.
    echo Then open:
    echo   ^* http://localhost:5000 (SEO pages^)
    echo   ^* http://localhost:7860 (AI Tutor^)
    echo.
) else (
    echo Invalid choice.
)

pause
