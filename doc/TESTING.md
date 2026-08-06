# Testing

Run tests from the repository root in an isolated virtual environment.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest test/unit test/api test/integration
node --test test/js/*.test.mjs
```

Before release, also validate syntax and deployment scripts:

```bash
python -m compileall -q src web_app.py
find deploy -type f -name '*.sh' -exec bash -n {} \;
```

Tests must use temporary databases and fake external providers. Never point a test run at production Stripe, email, database or AI credentials. A failing security, ownership, billing-entitlement or migration test blocks release.

When changing browser assets, update the relevant cache-busting query string in the HTML and add a focused contract test for the user-visible behaviour.
