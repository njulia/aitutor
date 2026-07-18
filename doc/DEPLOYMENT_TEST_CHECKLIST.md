# Deployment test checklist

## Before deployment

- [ ] `python -m compileall -q web_app.py src scripts test`
- [ ] `pytest -q test/unit test/api test/integration`
- [ ] Coverage meets the configured threshold.
- [ ] Chromium E2E suite passes.
- [ ] No real `.env`, database or API key is included in the image.
- [ ] PostgreSQL has `vector` and `pgcrypto` extensions.
- [ ] `DEV_MODE=false` and secure cookies are enabled.
- [ ] CORS contains only approved origins.
- [ ] Raw learner and AI content storage remains disabled.

## Staging

- [ ] `/api/health` returns 200.
- [ ] `/api/ready` returns 200 with database dependencies available.
- [ ] Registration, login and logout work.
- [ ] Parent can add, edit and delete a learner profile.
- [ ] Another account cannot access that learner.
- [ ] Homework generation, answering and review work.
- [ ] 11+ and year-round journeys work.
- [ ] Password reset works once and expires correctly.
- [ ] Contact message and admin reply work.
- [ ] Stripe test checkout and webhook update access.
- [ ] Account export and deletion work.

## Production smoke test

Run only non-destructive tests:

```bash
RUN_E2E=1 E2E_BASE_URL=https://your-production-domain.example \
pytest -q test/e2e/test_browser_smoke.py
```

Do not run account-deletion or payment mutation tests against production.

## Rollback triggers

Rollback when any of these occur:

- authentication or learner isolation failure;
- answer keys visible before submission;
- elevated 5xx rate or repeated worker restarts;
- database migration failure;
- payment access granted incorrectly;
- raw child content appearing in logs; or
- safety intervention unavailable.
