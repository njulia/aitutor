# Test and documentation update — 18 July 2026

## Requested structure

- Automated tests are under `test/`.
- Browser end-to-end tests are under `test/e2e/`.
- Multi-route tests are under `test/integration/`.
- Technical documents are under `doc/`.
- GitHub Actions is under `.github/workflows/tests.yml`.

## Added tests

- Complete parent registration, learner creation, memory, homework, review, progress, export and logout journey.
- Cross-account learner-isolation journey.
- Parent registration guardian-confirmation browser test.
- Login open-redirect browser test.
- Primary generate → answer → review browser journey.
- Required-answer browser validation.
- Child-friendly privacy and safety page checks.
- Authentication label and heading checks.
- 11+ year-round browser journey.
- Same-origin learner-script checks in both unit and browser suites.
- Project folder and CI wiring contracts.

## CI fixes

The earlier workflow was stored in `.github/workflow/` rather than GitHub's required `.github/workflows/` directory. It also referred to `tests/` even though the project uses `test/`, and it did not set `RUN_E2E=1`. These issues are corrected.

## Site fix found by the tests

The app page still requested DOMPurify from `cdn.jsdelivr.net`. The remote script was removed. Learner-facing Markdown continues to use the local strict allow-list in `static/js/safe_markdown.js`.

## Verified results

- 93 unit, API and integration tests passed.
- 16 Chromium browser E2E tests passed.
- Active web-layer coverage: 59.28%.
- Coverage gate: 55% passed.
- Python compilation passed.
- JavaScript syntax checks passed.
