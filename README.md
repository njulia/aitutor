# Homework Magic AI Tutor

A FastAPI AI tutor for UK primary pupils in **Year 1–6 (ages 5–11)**. The application supports homework generation, tutor mode, answer review, 11+ practice, parent-owned learner profiles, progress tracking, subscriptions, password reset, support messages and an administrator dashboard.

The current refactor focuses on child privacy, safeguarding, correct account ownership, low-latency RAG, bounded AI usage and multi-instance production storage.

## Read first

- `doc/REFACTOR_REPORT_2026-07-18.md` — changes, tests and production actions
- `doc/UK_CHILD_SAFETY_AND_DPIA_CHECKLIST.md` — launch governance checklist
- `doc/README.md` — documentation index
- `.env.example` — configuration without real secrets

This code contains technical safeguards but does not by itself certify legal compliance. Complete a child-focused DPIA and professional privacy/safeguarding review before launch.

## Local setup

Python 3.12 is recommended.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env
```

For local development, edit `.env` to use a local PostgreSQL database and test AI/payment keys. Never commit `.env`, `env` or real credentials.

Start the application:

```bash
python web_app.py
```

Open:

- `http://localhost:5000/`
- `http://localhost:5000/app`
- `http://localhost:5000/api/health`
- `http://localhost:5000/api/ready`

## Database

Production requires PostgreSQL. RAG uses PostgreSQL with `pgvector`.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

All production stores should normally share `DATABASE_URL`. Optional per-store overrides exist for accounts, sessions, memory, billing, messages and password resets.

Local SQLite support exists only for isolated automated tests and explicitly local compatibility paths. Do not use local SQLite or local Chroma files as production state on replaceable or multi-instance containers.

## Tests

All tests are under `test/`; all technical documents are under `doc/`.

```bash
python -m compileall -q web_app.py src scripts test
pytest -q test/unit test/api test/integration
```

Run browser end-to-end tests against a local or staging server:

```bash
RUN_E2E=1 E2E_BASE_URL=http://127.0.0.1:5000 pytest -q test/e2e --browser chromium
```

See `doc/TESTING.md` and `doc/END_TO_END_TESTING.md` for the complete test guide.

Verified result: **93 unit/API/integration tests passed and 16 Chromium E2E tests passed**. The active web-layer coverage gate is 55%, with 59.28% measured coverage.

## Production essentials

Set at minimum:

```dotenv
DEV_MODE=false
APP_BASE_URL=https://your-domain.example
PUBLIC_BASE_URL=https://your-domain.example
CORS_ORIGINS=https://your-domain.example
COOKIE_SECURE=true
DATABASE_URL=postgresql+psycopg://...
PGVECTOR_DATABASE_URL=postgresql+psycopg://...
DATA_CONTROLLER_NAME=...
PRIVACY_CONTACT_EMAIL=...
PRIVACY_POSTAL_ADDRESS=...
ADMIN_EMAILS=...
AUTH_SECRET=...
SESSION_SECRET=...
SESSION_OWNER_SECRET=...
SALT=...
STORE_RAW_LEARNER_CONTENT=false
STORE_RAW_AI_CONTENT=false
WEB_CONCURRENCY=1
```

Use a secret manager rather than placing production secrets in a file.

## Privacy and safeguarding defaults

- Parent/guardian-owned accounts for pupils aged 5–11
- Minimal learner identifiers
- Raw learner and AI content disabled by default
- Bounded retention for learning records, support messages and memory
- PII minimisation before AI calls
- Safety handling for explicit first-person danger disclosures
- Trusted-adult, 999 and Childline guidance for urgent child-safety messages
- No behavioural advertising or purchase prompts in learning output
- Child-friendly privacy and safety pages

## Performance design

- Exact metadata RAG lookup before semantic search
- Local deterministic marking where answer keys exist
- Prompt and output-token budgets
- Bounded parallel subject generation
- Timeouts and queue limits for blocking/AI work
- Local database subscription checks updated by Stripe webhooks
- Shared PostgreSQL storage for multi-instance stability

## Docker

```bash
docker build -t homework-magic .
docker run --rm -p 8080:8080 --env-file .env -e PORT=8080 homework-magic
```

The image runs as a non-root user and starts one worker by default because the local embedding model consumes memory per process.

## Payments

Start with Stripe test mode. Configure real Price IDs and a signed webhook secret. Access decisions use webhook-synchronised local subscription state; do not restore public/manual production subscription creation.

## Observability

Langfuse is optional. Keep raw content capture disabled. Use pseudonymous identifiers and operational metadata only unless a completed DPIA, privacy notice and provider agreement explicitly support more.
