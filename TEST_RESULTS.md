# Validation results

Validated on 16 July 2026 after the review reliability, privacy and latency refactor.

```text
python -m py_compile web_app.py src/webapp/review_service.py src/webapp/models.py src/ui/shared.py src/webapp/prompt_budget.py
passed

node --check static/js/app.js
passed

pytest -q
70 passed, 6 skipped
```

The six skipped tests are Playwright browser tests guarded by `RUN_E2E=1`. The current execution environment did not provide the pytest Playwright `page` fixture/browser installation, so they were not claimed as executed. Unit and API coverage includes:

- 11+ year-round correct and wrong answer review without an LLM call;
- detailed RAG explanation without an LLM call;
- Ollama-safe model routing and integer token limits;
- request-field propagation for document IDs and question indexes;
- profile PII minimisation and whole-word subject extraction;
- existing authentication, privacy, generation, RAG and persistence contracts.
