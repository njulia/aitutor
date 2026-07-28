# Homework Magic

Homework Magic is a FastAPI web application for UK primary-school homework,
guided 11+ practice, marking and parent-managed learner progress.

The request path is RAG-first: it searches the PostgreSQL/pgvector homework
library by exact year and subject before it can call an LLM. A genuine library
miss may create one new worksheet and private answer key, then stores that set
for future reuse. Retrieved answer keys are used for deterministic marking;
saved teaching methods are rendered locally and are never copied into a later
model prompt.

## Main improvements in this version

- Guided primary and 11+ profile fields are validated, bounded and stripped of
  direct identifiers.
- Requested session length now controls the number of returned questions.
- Guided 11+ access is checked before any expensive generation.
- RAG methods are first-write-wins and reused under opaque hashes.
- Static pages use short public caches, assets use revalidation caches, and
  responses larger than 1 KB are compressed.
- `robots.txt`, the canonical sitemap, permanent legacy redirects and article
  metadata have automated SEO contracts.
- Production settings fail closed when database, legal, email or provider
  configuration is unsafe.
- The container runs as an unprivileged user on Python 3.12.

## Local setup

Python 3.12 is the supported runtime.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
uvicorn web_app:app --host 127.0.0.1 --port 5000 --reload
```

The local template uses SQLite and Ollama. Start Ollama separately, or change
the provider settings in `.env`. Do not commit `.env` or any credentials.

Open:

- Website: `http://127.0.0.1:5000/`
- Tutor: `http://127.0.0.1:5000/app`
- Health: `http://127.0.0.1:5000/api/health`
- Readiness: `http://127.0.0.1:5000/api/ready`

## RAG-first request flow

1. Canonicalise the requested year and subject.
2. Read the learner's assigned document IDs.
3. query exact metadata in the homework or 11+ collection, excluding assigned
   sets where rotation is required.
4. Claim one unseen document atomically and return it.
5. Only after a true miss, call the configured provider once, split the public
   worksheet from its private answer key, and write it to RAG.

Selected year-round weeks are stable and may be reopened. General practice
rotates through unseen library items. A RAG outage is logged and can fall back
to generation so a child is not left without a response.

## Tests

```bash
python -m compileall web_app.py src scripts
node --check static/js/app.js
pytest test/unit test/api test/integration
```

For browser tests:

```bash
python -m playwright install chromium
RUN_E2E=1 pytest test/e2e --browser chromium
```

See [doc/TESTING.md](doc/TESTING.md) and
[doc/END_TO_END_TESTING.md](doc/END_TO_END_TESTING.md).

## Google Cloud Run

The production defaults target:

- Project: `aitutor-502921`
- Region: `europe-west2`
- Service: `aitutor-prod`
- Service account: `aitutor-run`
- Cloud SQL instance: `aitutor-prod-pg`
- Artifact Registry repository: `aitutor-repo`

Prepare the non-secret settings:

```bash
cp deploy/cloud-run.env.yaml.example deploy/cloud-run.env.yaml
```

Replace every `REPLACE_` value. Create the Secret Manager entries named by
`deploy/deploy_gcp.sh`, grant the Cloud Run service account access to them, and
then run:

```bash
bash deploy/deploy_gcp.sh
```

The deploy script refuses placeholder configuration, creates the Artifact
Registry repository if needed, builds with Cloud Build, attaches Cloud SQL and
deploys a bounded-concurrency Cloud Run revision. Database and API credentials
are injected from Secret Manager rather than stored in the source archive.

After the first database is available:

```bash
python scripts/gcp_utils.py
```

Run that command from an environment with the same Cloud SQL connection and
secret configuration. It creates the relational and pgvector schema without
printing the connection string.

## Project layout

- `web_app.py` — FastAPI routes and browser response contracts
- `src/homework_generator.py` — RAG-first assignment and miss generation
- `src/homework_rag.py` / `src/elevenplus_rag.py` — vector-library contracts
- `src/webapp/` — account, billing, safety, review and runtime services
- `static/` — public pages and dependency-free learner interface
- `scripts/` — original/open-curriculum question generators and maintenance
- `test/` — unit, API, integration and browser coverage
- `deploy/` — reviewed Cloud Run environment and deployment templates
- `doc/` — test, release and privacy guidance

## Privacy and safety

Parent notes are minimised before use and are not persisted in browser
preferences. Clear emails, phone numbers, postcodes, URLs, names and school
disclosures are removed from prompt inputs. Raw learner and AI content storage
is off by default. Production startup validates public operator details,
transactional email, secure cookies, exact CORS origins, PostgreSQL and provider
credentials.

Parents and guardians should still avoid entering a child's full name, school,
address, phone number, email, exact birthday or password.
