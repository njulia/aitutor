# Current automated test results

Verified on 18 July 2026.

## Results

| Suite | Result |
|---|---:|
| Unit, API and integration | 93 passed |
| Playwright Chromium E2E | 16 passed |
| Default `pytest -q` | 93 passed, 16 opt-in E2E skipped |
| Active web-layer coverage | 59.28% |
| Coverage gate | 55% passed |
| Python compilation | passed |
| JavaScript syntax checks | passed |

The E2E suite was run against a locally started FastAPI server. AI generation, AI review and subscription calls were intercepted where deterministic browser behaviour was required, so no paid provider calls were made.

## Commands

```bash
pytest -q
```

```bash
pytest -q test/unit test/api test/integration \
  --cov=src.webapp \
  --cov=web_app \
  --cov-report=term \
  --cov-fail-under=55
```

```bash
RUN_E2E=1 \
E2E_BASE_URL=http://127.0.0.1:5000 \
pytest -q test/e2e --browser chromium
```

## Browser regression found during this work

The E2E same-origin test showed that `static/app.html` still loaded DOMPurify from `cdn.jsdelivr.net`. The external script was removed. The existing local allow-list sanitizer in `static/js/safe_markdown.js` now handles learner-facing Markdown without a public script CDN.

The coverage floor is a ratchet, not a target. Increase it as tests are added for billing, email, uploads and administrator monitoring.
