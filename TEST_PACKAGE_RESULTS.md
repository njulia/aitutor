# Test package validation

Validation performed against the latest packaged AI Tutor code with the 11+
year-round-plan changes applied.

```text
Python test-file compilation: passed
Shell syntax checks: passed
Unit/API tests: 18 passed
RAG tests: 3 skipped in this build environment because ChromaDB was not installed
Browser tests: 4 skipped until RUN_E2E=1 and a website is running
```

The project `requirements.txt` includes ChromaDB, so RAG tests run in the normal
application environment and in GitHub Actions. Playwright browser tests run in
the supplied GitHub Actions workflow.
