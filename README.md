# Homework Magic refactor

This package reduces the size of the two largest files without changing API paths.

## Backend
- `web_app.py`: FastAPI composition and routes only.
- `src/webapp/question_utils.py`: question splitting, numbering and fallback matching.
- `src/webapp/review_service.py`: review, detailed explanation and improvement practice.
- `src/webapp/models.py`: Pydantic request models.

## Frontend
- `static/app.html`: page markup only.
- `static/css/app.css`: extracted styles.
- `static/js/app.js`: extracted application logic.

Copy these files into the same relative paths in your project. Keep your existing `homework_rag.py`; it is not changed.
