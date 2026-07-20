@echo off
REM Homework Magic Launcher for Windows

echo ========================================
echo   Homework Magic - AI Tutor (FastAPI)
echo ========================================
echo.

echo Generating SEO pages...
python generate_landing_pages.py

if exist "templates\elevenplus-practice.html" if not exist "static\elevenplus-practice.html" (
    copy "templates\elevenplus-practice.html" "static\"
)

echo.
echo Starting Homework Magic on http://localhost:5000
echo   AI Tutor:  http://localhost:5000/app
echo.
python web_app.py

pause
