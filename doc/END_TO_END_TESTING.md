# End-to-end testing

The browser suite is under `test/e2e/` and uses `pytest-playwright`.

It covers:

- homepage and learner app loading;
- same-origin script loading;
- primary and 11+ question rendering;
- a complete generate → answer → review journey;
- unanswered-question validation;
- parent registration and guardian confirmation;
- safe post-login redirects;
- child-friendly privacy and safety pages;
- key form labels and heading structure; and
- the 11+ year-round practice journey.

## Run locally

Terminal 1:

```bash
TESTING=true \
DEV_MODE=true \
DATABASE_URL=sqlite+pysqlite:////tmp/aitutor-e2e.db \
ACCOUNT_DATABASE_URL=sqlite+pysqlite:////tmp/aitutor-e2e.db \
AUTH_DATABASE_URL=sqlite+pysqlite:////tmp/aitutor-e2e.db \
PROGRESS_DATABASE_URL=sqlite+pysqlite:////tmp/aitutor-e2e.db \
SESSION_DATABASE_URL=sqlite+pysqlite:////tmp/aitutor-e2e.db \
MEMORY_DATABASE_URL=sqlite+pysqlite:////tmp/aitutor-e2e.db \
MESSAGE_DATABASE_URL=sqlite+pysqlite:////tmp/aitutor-e2e.db \
ADMIN_EMAILS=admin@example.com \
APP_BASE_URL=http://127.0.0.1:5000 \
CORS_ORIGINS=http://127.0.0.1:5000 \
LLM_PROVIDER=ollama \
uvicorn web_app:app --host 127.0.0.1 --port 5000
```

Terminal 2:

```bash
RUN_E2E=1 \
E2E_BASE_URL=http://127.0.0.1:5000 \
pytest -q test/e2e --browser chromium
```

When using a system-installed browser instead of Playwright's managed browser:

```bash
E2E_BROWSER_EXECUTABLE=/usr/bin/chromium \
RUN_E2E=1 E2E_BASE_URL=http://127.0.0.1:5000 \
pytest -q test/e2e --browser chromium
```

The browser tests intercept AI-generation, AI-review and subscription endpoints where needed. This makes the user journeys deterministic and prevents paid calls.

## Debug a failure

```bash
RUN_E2E=1 E2E_BASE_URL=http://127.0.0.1:5000 \
pytest test/e2e \
  --browser chromium \
  --headed \
  --slowmo 250 \
  --tracing retain-on-failure \
  --screenshot only-on-failure \
  --video retain-on-failure
```

Use a test or staging environment only. Never point destructive account tests at production.

## Staging smoke test

```bash
RUN_E2E=1 \
E2E_BASE_URL=https://staging.example.com \
pytest -q test/e2e/test_browser_smoke.py
```

For staging, use test accounts and Stripe test mode. AI endpoints mocked by browser routes do not need model keys.
