# Continuous integration

The GitHub Actions workflow is `.github/workflows/tests.yml`.

It has two independent jobs:

1. `python-tests` runs compilation, unit, API and integration tests with coverage.
2. `browser-tests` starts the FastAPI app and runs Chromium E2E tests.

## Why the jobs are separate

- Browser installation is slower and does not delay fast feedback.
- Unit/API failures are easier to diagnose separately.
- Playwright traces, screenshots and videos can be uploaded only for browser failures.

## CI data safety

- CI uses a disposable SQLite database.
- AI and payment endpoints are not called with real keys.
- Raw learner and AI content storage is disabled.
- Test emails use the reserved `example.com` domain.
- CI secrets are not required for the default test jobs.

## Branch protection recommendation

Require both checks before merging to `main`:

- `Automated tests / python-tests`
- `Automated tests / browser-tests`

Also require at least one review for changes to:

- authentication and session code;
- account or learner ownership checks;
- payment webhooks;
- data retention and deletion;
- safeguarding logic;
- AI prompt construction; and
- upload processing.

## Adding a regression test

1. Reproduce the bug with a failing test in the narrowest suitable folder.
2. Apply the fix.
3. Run the focused test.
4. Run `pytest -q`.
5. Run browser tests if HTML or JavaScript changed.
6. Update documentation when behaviour or setup changed.
