# Test suite

## Install test dependencies

```bash
python -m pip install -r requirements-test.txt
```

The application dependencies must also be installed, because the API end-to-end
test imports `web_app.py`.

## Run all tests

```bash
pytest
```

## Run unit tests only

```bash
pytest tests/unit
```

## Run end-to-end tests only

```bash
pytest -m e2e
```

## Coverage (optional)

```bash
python -m pip install pytest-cov
pytest --cov=src.webapp --cov=web_app --cov-report=term-missing
```

The API end-to-end test does not call a real LLM, Stripe, or Chroma database.
Those external boundaries are replaced with deterministic test doubles. The
review-service unit tests verify the actual index-based RAG answer selection.
