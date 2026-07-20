# PostgreSQL, child privacy, Stripe and learning memory

## What changed

### PostgreSQL

All durable relational data now uses SQLAlchemy and `DATABASE_URL`:

- parent/guardian accounts and learner profiles;
- login sessions;
- progress and structured AI telemetry;
- learning-memory settings, events and mastery;
- temporary tutor sessions;
- support messages;
- Stripe webhook idempotency and account entitlements.

Production refuses to start unless `DATABASE_URL` is PostgreSQL. SQLite remains only as a local test/development fallback. The embedding cache may remain local because it is a disposable performance cache, not the system of record. Chroma should use a server-backed deployment in horizontally scaled production.

Start locally with PostgreSQL:

```bash
cp .env.example .env
# Replace secrets and set POSTGRES_PASSWORD.
docker compose up --build
```

Initialise an existing PostgreSQL service:

```bash
python scripts/init_database.py
```

## Learning memory

Memory is **off by default**. A signed-in parent or guardian controls it separately for each learner at `/memory`.

Stored fields are limited to:

- subject and curriculum topic;
- result ratio and counts;
- broad difficulty;
- a controlled misconception code;
- mastery score and last-practised time;
- explanation and hint preferences.

The memory store deliberately has no fields for raw answers, prompts, conversations, images, school names, addresses or family details. Only a short, bounded educational summary is added to an AI prompt.

Parent controls include enable/disable, retention from 30 to 730 days, topic deletion, complete deletion and JSON export. Deleting a learner also removes progress, memory, AI telemetry, support records and temporary sessions.

## Child-safety and privacy defaults

- Parent email is the account boundary; learners use nicknames and pseudonymous IDs.
- Nicknames resembling contact or school information are rejected.
- Anonymous IDs are random cookies, not IP-derived identifiers.
- Login cookies contain random revocable tokens, not email addresses.
- Raw learner work and AI prompts are not stored by default.
- AI telemetry stores metrics only unless both a server feature flag and explicit parent opt-in are present.
- Uploaded files are temporary and removed after extraction.
- Sensitive API responses use `Cache-Control: no-store`.
- Browser state-changing requests are restricted to the same origin.
- Learner-facing AI output is rendered through an allow-listed local Markdown renderer.
- Third-party learner-page CDNs were removed.

## Stripe redesign

Stripe billing belongs only to the authenticated parent/guardian account.

1. The parent selects a plan on `/pricing`.
2. The backend creates or reuses an account-level Stripe Customer.
3. The browser is redirected to hosted Stripe Checkout.
4. Checkout completion alone does not grant access.
5. Signed subscription webhooks update the PostgreSQL entitlement table.
6. Application access checks the local entitlement table for low latency and reliability.
7. The parent manages cancellation and payment details in Stripe's customer portal.

No learner profile, learning result, prompt or homework content is sent to Stripe. Manual live subscription creation is disabled. Development-only test subscriptions remain available behind admin authentication.

Configure the webhook endpoint as:

```text
POST https://homeworkmagic.co.uk/api/billing/stripe/webhook
```

Subscribe it to at least:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `customer.subscription.paused`
- `customer.subscription.resumed`

## Account deletion

A learner may be erased independently. Complete account deletion requires the active Stripe subscription to be cancelled first, because payment records may have separate statutory retention requirements. Local child and account data is then erased and all login sessions are revoked.

## Validation

```bash
python -m compileall -q web_app.py src scripts
node --check static/js/app.js
DEV_MODE=true pytest -q
```
