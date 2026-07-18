# AI Tutor automated testing

Copy the files in this package into the root of the AI Tutor repository.
The paths inside the ZIP already match the project structure.

## Install

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

## Fast local tests

These tests use isolated temporary SQLite databases and make no real LLM or
Stripe calls:

```bash
./scripts/run_tests.sh
```

Or:

```bash
pytest test/unit test/api -v
```

RAG tests are skipped when ChromaDB is not installed. It is included in the
main `requirements.txt`, so they run in the normal project environment.

## Browser tests

Start the site in one terminal:

```bash
DEV_MODE=true uvicorn web_app:app --host 127.0.0.1 --port 5000
```

Run in another terminal:

```bash
./scripts/run_browser_tests.sh
```

Failed browser tests retain Playwright traces and screenshots in
`test-results/`.

## Docker

```bash
docker compose up --build -d
E2E_BASE_URL=http://127.0.0.1:5000 ./scripts/run_browser_tests.sh
```

## GitHub Actions

Commit `.github/workflows/tests.yml`. Every push and pull request then runs:

- Python compilation
- unit tests
- FastAPI endpoint tests
- privacy and admin-access tests
- PostgreSQL-backed CI tests
- Chromium browser tests
- 11+ year-round-plan browser checks

The workflow does not use live Stripe keys or call a live LLM.

## Useful commands

```bash
# One file
pytest test/api/test_auth_admin_memory.py -v

# Stop after the first failure
pytest test/unit test/api -x -vv

# Include browser tests against an already-running site
RUN_E2E=1 E2E_BASE_URL=http://127.0.0.1:5000 pytest test/e2e --browser chromium

# Coverage HTML report
pytest test/unit test/api --cov=src --cov=web_app --cov-report=html
open htmlcov/index.html
```

## Tests included

- public page and health-route availability
- security headers and same-origin write protection
- random anonymous identifiers with no IP disclosure
- opaque, HTTP-only login cookies and server-side logout revocation
- admin dashboard allowlist enforcement
- parent-controlled learning-memory settings, export and erasure
- no raw child answer storage in structured memory
- Year 1 Maths RAG metadata preservation
- tutor question index and RAG document ID preservation
- PostgreSQL configuration fail-closed checks
- learner nickname privacy validation
- 11+ 52-week plan browser rendering
- no third-party learner-page script CDN requests
