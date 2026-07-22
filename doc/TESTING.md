# Testing

## Local prerequisites

Use Python 3.12+ and install the locked application and test dependencies in an isolated virtual environment. Use test credentials and a temporary database only.

## Fast release suite

```bash
python -m compileall -q web_app.py src scripts test
pytest -q test/unit test/api test/integration
```

Focused public-site and billing checks:

```bash
pytest -q \
  test/unit/test_public_seo.py \
  test/unit/test_stripe_website_requirements.py \
  test/unit/test_subscription_plan_access.py \
  test/unit/test_static_asset_security.py
```

## Test isolation

`test/conftest.py` sets development/testing mode before importing the application and directs relational stores to a temporary SQLite database. Production continues to require managed PostgreSQL. Tests must not call live AI, email, payment or production database services.

## Before sharing a build

1. Run compile checks.
2. Run unit, API and integration tests.
3. Run browser tests for user-interface changes.
4. Confirm no `.env`, credentials, database files, uploads or test artefacts are in the archive.
5. Review changed public claims, prices and privacy text against the production configuration.
