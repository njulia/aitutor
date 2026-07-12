# Homework Magic AI Tutor

A FastAPI AI tutor for UK primary-school learners and 11+ practice. This release adds PostgreSQL persistence, privacy-first learning memory, parent/guardian account controls and Stripe Checkout billing.

## Main features

- Year 1–6 and 11+ homework generation and review
- Tutor mode with one question at a time
- RAG-first answer checking to reduce latency and token use
- Parent/guardian accounts with multiple learner profiles
- Structured learning memory, disabled by default
- Progress, mastery and misconception tracking
- PostgreSQL for durable production data
- Random, revocable login sessions
- Stripe hosted Checkout, customer portal and signed webhooks
- Temporary, bounded uploads and privacy-safe AI telemetry
- Admin dashboard protected by authenticated email allow-list

## Quick start for development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For a zero-setup local run, set `DEV_MODE=true`; SQLite is then used only as a development fallback:

```bash
DEV_MODE=true python web_app.py
```

Open `http://localhost:5000`.

## PostgreSQL production setup

Production refuses to start without PostgreSQL.

```bash
cp .env.example .env
# Edit secrets, domain, Stripe price IDs and POSTGRES_PASSWORD.
docker compose up --build
```

The production database URL is:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

Common `postgres://` and `postgresql://` URLs are normalised automatically to psycopg 3.

## Learning memory

Parents manage memory at `/memory` for each learner profile.

Memory is off until a parent enables it. It stores only structured educational signals:

- subject and topic;
- outcome and question counts;
- broad difficulty and misconception code;
- mastery score and last practice time;
- explanation and hint preferences.

It does not store raw conversations, answers, uploaded images, school names, addresses or family details. Parents can export, disable or erase memory, including one topic at a time.

## Stripe setup

Create recurring Stripe prices and set their IDs in `.env`. Configure this webhook endpoint:

```text
https://YOUR_DOMAIN/api/billing/stripe/webhook
```

Required event types are listed in [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md). Access is granted only from webhook-updated PostgreSQL entitlements, never from a browser success redirect.

## Child privacy defaults

- Parent account is the identity and billing boundary.
- Learner profiles use nicknames and pseudonymous IDs.
- Raw learner content and raw AI payloads are off by default.
- Anonymous IDs are random and are not derived from IP addresses.
- Sensitive API responses are not browser-cached.
- External learner-page script CDNs were removed.
- Learner deletion and account deletion erase associated local data.

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for architecture, deployment, retention and erasure details.

## Validation

```bash
python -m compileall -q web_app.py src scripts
node --check static/js/app.js
node --check static/js/chart-lite.js
DEV_MODE=true pytest -q
```
