# Testing

Use Python 3.12 and install both requirement files.

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m compileall web_app.py src scripts
node --check static/js/app.js
pytest test/unit test/api test/integration
```

The test fixtures use isolated databases and set `TESTING=true`. Unit tests
must not replace top-level `src` or `scripts` modules during collection.

Useful focused commands:

```bash
pytest test/unit/test_rag_first_assignment.py
pytest test/unit/test_solution_method_reuse.py
pytest test/unit/test_public_seo.py
pytest test/api/test_generation_contract.py
```

Before release, run the complete suite and the browser tests described in
`END_TO_END_TESTING.md`.
