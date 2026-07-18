# Testing guide

All automated tests live under the `test/` directory.

```text
test/
├── api/          FastAPI route and security contracts
├── e2e/          Playwright browser journeys against a running site
├── integration/  Multi-route and shared-component journeys
├── unit/         Fast isolated tests
└── conftest.py   Shared deterministic fixtures
```

## Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Install Chromium for browser tests:

```bash
python -m playwright install chromium
```

On Linux CI, install browser system dependencies too:

```bash
python -m playwright install --with-deps chromium
```

## Fast local suite

```bash
pytest -q test/unit test/api test/integration
```

Run every test. Browser tests are skipped unless `RUN_E2E=1`:

```bash
pytest -q
```

## Coverage

```bash
pytest test/unit test/api test/integration \
  --cov=src.webapp \
  --cov=web_app \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-fail-under=55
```

Open `htmlcov/index.html` after the run.

## Markers

```bash
pytest -m unit
pytest -m api
pytest -m integration
pytest -m e2e
pytest -m "not e2e"
```

## Test isolation

`test/conftest.py` sets test environment variables before importing the application. Relational stores use a temporary SQLite database unless `AITUTOR_TEST_DATABASE_URL` is supplied. Production still requires PostgreSQL.

The normal suite uses a deterministic fake LLM. It does not call a paid model, Stripe, email provider or production database.

## Useful quality checks

```bash
python -m compileall -q web_app.py src scripts test
node --check static/js/app.js
node --check static/js/login.js
node --check static/js/multiple-choice.js
```

## Common failures

- `playwright browser executable does not exist`: run `python -m playwright install chromium`.
- E2E tests skip: set `RUN_E2E=1` and make sure the server health endpoint is reachable.
- Database locked: delete the temporary local test database or run with a fresh `AITUTOR_TEST_DATABASE_URL`.
- E2E server unreachable: check `E2E_BASE_URL`, the Uvicorn process and `/api/health`.
