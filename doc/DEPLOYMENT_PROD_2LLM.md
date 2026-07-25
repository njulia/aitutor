# Homework Magic — GCP Production Deployment Plan

**Target architecture:** Google Cloud Run + Cloud SQL for PostgreSQL 16 with pgvector + DeepSeek quick review + Vertex AI Gemini detailed review

**Last updated:** 18 July 2026

**Region:** `europe-west2` (London)

**Model routing:**

- Quick review / normal answer checking: `deepseek-v4-flash`
- Explain in detail: `gemini-2.5-flash`
- Help me improve: `gemini-2.5-flash`

> Important: Google currently lists Gemini 2.5 Flash retirement for 16 October 2026. Keep the model name configurable and plan a controlled upgrade before that date.

---

## 1. Production architecture

```text
UK parent or pupil
        |
        v
Cloud Run (FastAPI, London)
        |
        +-- Cloud SQL for PostgreSQL + pgvector
        |      +-- accounts and authentication
        |      +-- progress and subscriptions
        |      +-- messages and tutor sessions
        |      +-- homework documents and embeddings
        |      +-- vector similarity search
        |
        +-- DeepSeek API
        |      +-- quick answer review
        |
        +-- Vertex AI Gemini
        |      +-- Explain in detail
        |      +-- Help me improve
        |
        +-- Secret Manager
        +-- Cloud Storage
        +-- Cloud Logging / Monitoring
```

PostgreSQL is the single production data store. The `vector` extension provides embedding storage and similarity search, so Chroma is not used in production. This allows Cloud Run to use multiple instances safely because every instance reads and writes the same managed database.

---

## 2. Required application configuration

The model selection must be controlled by environment variables, not hard-coded throughout the application.

```env
QUICK_REVIEW_PROVIDER=deepseek
QUICK_REVIEW_MODEL=deepseek-v4-flash
DETAIL_REVIEW_PROVIDER=vertex_ai
DETAIL_REVIEW_MODEL=gemini-2.5-flash

DEEPSEEK_BASE_URL=https://api.deepseek.com
GOOGLE_CLOUD_PROJECT=homework-magic-prod
GOOGLE_CLOUD_LOCATION=europe-west2
```

Expected route behaviour:

| User action | Provider | Model |
|---|---|---|
| Check answers / quick review | DeepSeek | `QUICK_REVIEW_MODEL` |
| Explain in detail | Vertex AI | `DETAIL_REVIEW_MODEL` |
| Help me improve | Vertex AI | `DETAIL_REVIEW_MODEL` |

Do not send a model name from the browser and trust it. Select the provider and model on the server.

### Recommended server-side interface

```python
class ReviewModelRouter:
    def quick_review(self, messages):
        return self.deepseek.complete(
            messages=messages,
            model=os.environ["QUICK_REVIEW_MODEL"],
        )

    def detailed_review(self, messages):
        return self.gemini.complete(
            messages=messages,
            model=os.environ["DETAIL_REVIEW_MODEL"],
        )
```

The quick-review endpoint must call `quick_review`. Both detailed actions must call `detailed_review`.

---

## 3. Fix production blockers before deployment

### 3.1 Disable Uvicorn reload

The uploaded `web_app.py` still contains:

```python
uvicorn.run("web_app:app", host="0.0.0.0", port=port, reload=True)
```

Change it to:

```python
uvicorn.run(
    "web_app:app",
    host="0.0.0.0",
    port=port,
    reload=False,
    proxy_headers=True,
)
```

The Docker command below is preferred, so the Python `__main__` block is not required in production.

### 3.2 Restrict CORS

Do not use wildcard origins with credential cookies.

```python
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
```

Production setting:

```env
ALLOWED_ORIGINS=https://your-domain.co.uk,https://www.your-domain.co.uk
```

### 3.3 Store production sessions in PostgreSQL

`tutor_sessions = {}` will be lost when Cloud Run restarts and will not be shared between instances. Persist tutor sessions in PostgreSQL, with an expiry timestamp and a scheduled cleanup policy. Do not rely on process memory for signed-in state, progress, or tutoring conversations.

### 3.4 Protect admin endpoints

Every `/admin/*` and `/api/admin/*` route must require a verified administrator dependency. Never rely only on hiding admin links in the HTML.

### 3.5 Keep uploads temporary

Cloud Run local storage is temporary. Delete files immediately after processing, as the application already attempts to do. Use Cloud Storage only when a file must be retained, and apply a short retention policy.

### 3.6 Minimise child data sent to LLMs

Do not send names, email addresses, school names, IP addresses, home addresses, Stripe identifiers or internal user IDs to either model. Send only the educational context required for the answer.

---

## 4. Prepare the local project

Suggested production files:

```text
.
├── web_app.py
├── app.html
├── homework_rag.py
├── src/
├── static/
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── alembic.ini
└── migrations/                 # includes application and pgvector migrations
```

### requirements.txt

Ensure these are present with versions tested by your application:

```text
fastapi
uvicorn[standard]
gunicorn
python-dotenv
openai
httpx
google-genai
SQLAlchemy
psycopg[binary]
alembic
cloud-sql-python-connector[pg8000]
pgvector
google-cloud-storage
google-cloud-secret-manager
passlib[bcrypt]
python-multipart
stripe
```

Generate a locked snapshot after testing:

```bash
python -m pip freeze > requirements.lock.txt
```

---

## 5. Create the Docker files

### Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD exec uvicorn web_app:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --workers 1
```

Use one worker because Cloud Run scales by container instance. Store all persistent state, including tutor sessions and RAG data, in PostgreSQL rather than process memory.

### .dockerignore

```text
.git
.github
.env
.env.*
venv
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.coverage
htmlcov
uploads/*
*.log
.DS_Store
node_modules
```

Do not package database files inside the container. PostgreSQL and vector data remain in Cloud SQL.

---

## 6. Test the container locally

```bash
docker build -t homework-magic:local .
```

Create a local environment file that is excluded from Git:

```env
DEV_MODE=true
PORT=8080
QUICK_REVIEW_PROVIDER=deepseek
QUICK_REVIEW_MODEL=deepseek-v4-flash
DETAIL_REVIEW_PROVIDER=vertex_ai
DETAIL_REVIEW_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=your-configured-embedding-model
EMBEDDING_DIMENSION=384
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=replace-me
GOOGLE_CLOUD_PROJECT=homework-magic-prod
GOOGLE_CLOUD_LOCATION=europe-west2
ALLOWED_ORIGINS=http://localhost:8080
```

Run:

```bash
docker run --rm -p 8080:8080 \
  --env-file .env.production.local \
  -v "$HOME/.config/gcloud:/home/appuser/.config/gcloud:ro" \
  homework-magic:local
```

Test:

```bash
curl -i http://localhost:8080/api/health
curl -i http://localhost:8080/
```

Run automated tests:

```bash
pytest -q
```

Minimum model-routing tests:

- Quick review calls DeepSeek exactly once.
- Quick review does not call Gemini.
- Explain in detail calls Gemini exactly once.
- Help me improve calls Gemini exactly once.
- DeepSeek failure returns a safe error or uses the configured fallback.
- Model API keys never appear in responses or logs.
- Anonymous and signed-in users are tested according to the paywall rules.

---

## 7. Create the Google Cloud project

Install and initialise the Google Cloud CLI, then:

```bash
export PROJECT_ID="homework-magic-prod"
export REGION="europe-west2"
export SERVICE_NAME="homework-magic"
export REPOSITORY="homework-magic"

gcloud auth login
gcloud projects create "$PROJECT_ID" --name="Homework Magic Production"
gcloud config set project "$PROJECT_ID"
gcloud billing projects link "$PROJECT_ID" \
  --billing-account="YOUR_BILLING_ACCOUNT_ID"
```

List billing accounts when needed:

```bash
gcloud billing accounts list
```

---

## 8. Enable required Google APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

---

## 9. Create the Cloud Run service account

```bash
export RUN_SA_NAME="homework-magic-run"
export RUN_SA="${RUN_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$RUN_SA_NAME" \
  --display-name="Homework Magic Cloud Run"
```

Grant only the required roles:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/monitoring.metricWriter"
```

Add Storage permissions only if the application actually keeps files in Cloud Storage.

---

## 10. Configure Vertex AI Gemini

Cloud Run uses its service account to authenticate to Vertex AI. Do not create a Gemini API key when using Vertex AI.

A typical Google Gen AI SDK client is:

```python
import os
from google import genai

client = genai.Client(
    vertexai=True,
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west2"),
)
```

Call the configured detailed-review model:

```python
response = client.models.generate_content(
    model=os.environ["DETAIL_REVIEW_MODEL"],
    contents=prompt,
)
```

Do not use a long-lived Google service-account JSON key in Cloud Run.

---

## 11. Configure DeepSeek

Create a production DeepSeek API key in the DeepSeek platform.

Use the OpenAI-compatible endpoint:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=45.0,
    max_retries=2,
)
```

Call:

```python
response = client.chat.completions.create(
    model=os.environ["QUICK_REVIEW_MODEL"],
    messages=messages,
    temperature=0.1,
)
```

Use short prompts and strict output formats for quick review to control cost and improve reliable marking.

---

## 12. Store secrets in Secret Manager

Never commit the production `.env` file.

Create secrets:

```bash
printf '%s' 'YOUR_DEEPSEEK_KEY' | \
  gcloud secrets create DEEPSEEK_API_KEY --data-file=-

openssl rand -base64 48 | \
  gcloud secrets create AUTH_SECRET --data-file=-

printf '%s' 'YOUR_STRIPE_SECRET_KEY' | \
  gcloud secrets create STRIPE_SECRET_KEY --data-file=-

printf '%s' 'YOUR_STRIPE_WEBHOOK_SECRET' | \
  gcloud secrets create STRIPE_WEBHOOK_SECRET --data-file=-
```

If a secret already exists, add a new version:

```bash
printf '%s' 'NEW_VALUE' | \
  gcloud secrets versions add DEEPSEEK_API_KEY --data-file=-
```

Grant the Cloud Run identity access:

```bash
for SECRET in \
  DEEPSEEK_API_KEY \
  AUTH_SECRET \
  STRIPE_SECRET_KEY \
  STRIPE_WEBHOOK_SECRET \
  DB_PASSWORD
do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${RUN_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

Create `DB_PASSWORD` after generating the database password in the next step.

---

## 13. Create Cloud SQL PostgreSQL

PostgreSQL 16 defaults to **Enterprise Plus** when no edition is supplied. The old `db-f1-micro` tier is not valid for Enterprise Plus. For this cost-conscious MVP, explicitly create an **Enterprise** edition instance.

```bash
export SQL_INSTANCE="homework-magic-postgres"
export DB_NAME="homework_magic"
export DB_USER="homework_magic_app"
export DB_PASSWORD="$(openssl rand -base64 36 | tr -d '\n')"

gcloud sql instances create "$SQL_INSTANCE" \
  --database-version=POSTGRES_16 \
  --edition=ENTERPRISE \
  --region="$REGION" \
  --tier=db-custom-1-3840 \
  --storage-type=SSD \
  --storage-size=10GB \
  --storage-auto-increase \
  --availability-type=zonal \
  --backup-start-time=02:00
```

This creates a single-zone Enterprise instance with 1 vCPU, 3.75 GB RAM and 10 GB SSD storage. It is suitable for an early market test.

Check available tiers before retrying if Google changes machine availability:

```bash
gcloud sql tiers list --filter="region:$REGION"
```

Create the application database and user:

```bash
gcloud sql databases create "$DB_NAME" \
  --instance="$SQL_INSTANCE"

gcloud sql users create "$DB_USER" \
  --instance="$SQL_INSTANCE" \
  --password="$DB_PASSWORD"
```

Store the password in Secret Manager:

```bash
printf '%s' "$DB_PASSWORD" | \
  gcloud secrets create DB_PASSWORD \
  --data-file=- \
  --replication-policy=automatic
```

If `DB_PASSWORD` already exists:

```bash
printf '%s' "$DB_PASSWORD" | \
  gcloud secrets versions add DB_PASSWORD --data-file=-
```

Then clear it from the shell:

```bash
unset DB_PASSWORD
```

Get the connection name:

```bash
export INSTANCE_CONNECTION_NAME="$(
  gcloud sql instances describe "$SQL_INSTANCE" \
    --format='value(connectionName)'
)"

echo "$INSTANCE_CONNECTION_NAME"
```

Recommended variables:

```env
DB_USER=homework_magic_app
DB_NAME=homework_magic
INSTANCE_CONNECTION_NAME=PROJECT_ID:europe-west2:homework-magic-postgres
```

Build the SQLAlchemy URL in Python so special characters in the password are escaped correctly:

```python
from urllib.parse import quote_plus
import os

password = quote_plus(os.environ["DB_PASSWORD"])
DATABASE_URL = (
    f"postgresql+psycopg://{os.environ['DB_USER']}:{password}"
    f"@/{os.environ['DB_NAME']}"
    f"?host=/cloudsql/{os.environ['INSTANCE_CONNECTION_NAME']}"
)
```

For local development through `127.0.0.1`:

```env
DATABASE_URL=postgresql+psycopg://homework_magic_app:URL_ENCODED_PASSWORD@127.0.0.1:5432/homework_magic
```

Passwords containing `+`, `/`, `@`, `:`, `#` or `%` must be URL-encoded when embedded in a database URL.

---

## 14. Enable pgvector and run database migrations

Enable pgvector once in the application database with a privileged account:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Verify it:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```

### 14.1 Use the correct Python environment

Always run Alembic through the active Python interpreter. This avoids accidentally using `/Users/jing/anaconda3/bin/alembic` from the base Python 3.10 environment.

```bash
conda activate python313
cd /Users/jing/Documents/ai/homework/ai_tutor

which python
python --version
python -m pip install --upgrade \
  alembic \
  sqlalchemy \
  "psycopg[binary]" \
  pgvector \
  python-dotenv

python -m alembic --version
```

`which python` should point inside `/Users/jing/anaconda3/envs/python313/`.

### 14.2 Configure Alembic metadata

Autogeneration works only when `migrations/env.py` imports the same SQLAlchemy `Base` used by every model and imports all model modules before reading `Base.metadata`.

```python
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

# Change these imports to match the project.
from src.database import Base
import src.models  # noqa: F401

config = context.config
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set")

config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

All models must inherit from one shared base:

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

The pgvector column must match the embedding model dimension:

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

embedding: Mapped[list[float]] = mapped_column(
    Vector(384),
    nullable=False,
)
```

### 14.3 Test the database connection

```bash
python - <<'PYTEST'
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
with engine.connect() as connection:
    print(connection.execute(text("SELECT current_database(), current_user")).one())
PYTEST
```

### 14.4 Generate and apply the migration

```bash
python -m alembic current
python -m alembic revision --autogenerate \
  -m "Create production tables"
```

Review the generated migration. Ensure pgvector is enabled before vector columns are created:

```python
from alembic import op


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # generated operations follow
```

Apply and verify:

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic heads
```

Common errors:

| Error | Fix |
|---|---|
| `ModuleNotFoundError` | Activate the project environment, use `python -m alembic`, and add the project root to `sys.path`. |
| `DATABASE_URL is not set` | Load `.env` in `env.py` or export the variable. |
| `Could not parse SQLAlchemy URL` | URL-encode the password and use `postgresql+psycopg://`. |
| `password authentication failed` | Check the user/password and restart the proxy or local database after credential changes. |
| `Target database is not up to date` | Run `python -m alembic upgrade head` first. |
| Empty generated migration | Import all models before assigning `target_metadata`. |
| `type vector does not exist` | Enable the `vector` extension before creating vector columns. |

### 14.5 Production migration job

```bash
gcloud run jobs create homework-magic-migrate \
  --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:VERSION" \
  --region="$REGION" \
  --service-account="$RUN_SA" \
  --set-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
  --set-env-vars="DB_USER=${DB_USER},DB_NAME=${DB_NAME},INSTANCE_CONNECTION_NAME=${INSTANCE_CONNECTION_NAME}" \
  --set-secrets="DB_PASSWORD=DB_PASSWORD:latest" \
  --command="python" \
  --args="-m,alembic,upgrade,head" \
  --max-retries=0 \
  --task-timeout=10m
```

Run it before directing traffic to a new revision:

```bash
gcloud run jobs execute homework-magic-migrate \
  --region="$REGION" \
  --wait
```

For later releases:

```bash
gcloud run jobs update homework-magic-migrate \
  --image="$IMAGE" \
  --region="$REGION"
```

---

## 15. Configure PostgreSQL vector storage

Use PostgreSQL for both normal application records and RAG documents. A suggested table is:

```sql
CREATE TABLE homework_documents (
    id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    year_group SMALLINT,
    subject TEXT,
    topic TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Create normal indexes for filtering before vector search:

```sql
CREATE INDEX ix_homework_documents_year_subject
ON homework_documents (year_group, subject);

CREATE INDEX ix_homework_documents_metadata
ON homework_documents USING gin (metadata);
```

After enough embeddings have been loaded, create an HNSW cosine index:

```sql
CREATE INDEX ix_homework_documents_embedding_hnsw
ON homework_documents
USING hnsw (embedding vector_cosine_ops);
```

A typical similarity query is:

```sql
SELECT id, content, metadata,
       1 - (embedding <=> :query_embedding) AS similarity
FROM homework_documents
WHERE year_group = :year_group
  AND subject = :subject
ORDER BY embedding <=> :query_embedding
LIMIT :limit;
```

Important rules:

- Use the same embedding model for stored documents and search queries.
- Validate that every vector has exactly `EMBEDDING_DIMENSION` values.
- Store the embedding model name and version in metadata.
- Re-embed all documents before switching embedding models.
- Use parameterised SQL; never construct vector queries from raw user text.
- Keep student account data separate from RAG document content, even though both are in PostgreSQL.

## 16. Create Artifact Registry

```bash
gcloud artifacts repositories create "$REPOSITORY" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Homework Magic production images"

gcloud auth configure-docker "${REGION}-docker.pkg.dev"
```

---

## 17. Build and push the image

Use an immutable release tag:

```bash
export VERSION="$(date -u +%Y%m%d-%H%M%S)"
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${VERSION}"

gcloud builds submit --tag "$IMAGE" .
```

Record the image value. It is also your rollback target.

---

## 18. First Cloud Run deployment

```bash
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --service-account="$RUN_SA" \
  --allow-unauthenticated \
  --port=8080 \
  --cpu=1 \
  --memory=1Gi \
  --concurrency=10 \
  --timeout=120s \
  --min-instances=0 \
  --max-instances=2 \
  --set-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
  --set-env-vars="DEV_MODE=false,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},QUICK_REVIEW_PROVIDER=deepseek,QUICK_REVIEW_MODEL=deepseek-v4-flash,DETAIL_REVIEW_PROVIDER=vertex_ai,DETAIL_REVIEW_MODEL=gemini-2.5-flash,DEEPSEEK_BASE_URL=https://api.deepseek.com,DB_USER=${DB_USER},DB_NAME=${DB_NAME},INSTANCE_CONNECTION_NAME=${INSTANCE_CONNECTION_NAME},EMBEDDING_MODEL=your-configured-embedding-model,EMBEDDING_DIMENSION=384" \
  --set-secrets="DEEPSEEK_API_KEY=DEEPSEEK_API_KEY:latest,DB_PASSWORD=DB_PASSWORD:latest,AUTH_SECRET=AUTH_SECRET:latest,STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest"
```

Add `ALLOWED_ORIGINS` after the custom domain is known. During the initial test, use the exact Cloud Run service URL rather than `*`.

Get the URL:

```bash
export SERVICE_URL="$(
  gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --format='value(status.url)'
)"

echo "$SERVICE_URL"
```

Update CORS:

```bash
gcloud run services update "$SERVICE_NAME" \
  --region="$REGION" \
  --update-env-vars="ALLOWED_ORIGINS=${SERVICE_URL}"
```

---

## 19. Run the migration job

Update or create the migration job with the release image, then run it:

```bash
gcloud run jobs update homework-magic-migrate \
  --image="$IMAGE" \
  --region="$REGION"

gcloud run jobs execute homework-magic-migrate \
  --region="$REGION" \
  --wait
```

For future releases, migrate before shifting traffic to an incompatible application revision. Prefer backwards-compatible database changes.

---

## 20. Production smoke tests

### Health and pages

```bash
curl -fsS "${SERVICE_URL}/api/health"
curl -I "${SERVICE_URL}/"
curl -I "${SERVICE_URL}/privacy"
```

### Authentication

Test in a clean browser:

1. Sign up.
2. Sign in.
3. Move between pages.
4. Confirm the home page shows only the signed-in state and logout action.
5. Sign out.
6. Confirm protected APIs reject the old session.

### Model routing

Run three test cases and inspect logs or Langfuse traces:

1. **Check answers** → provider must be DeepSeek, model must equal `QUICK_REVIEW_MODEL`.
2. **Explain in detail** → provider must be Vertex AI, model must equal `DETAIL_REVIEW_MODEL`.
3. **Help me improve** → provider must be Vertex AI, model must equal `DETAIL_REVIEW_MODEL`.

The response shown to the user must not expose provider keys, internal prompts, stack traces or personal identifiers.

### Payment

Use Stripe test mode first:

1. Create checkout.
2. Complete test payment.
3. Verify webhook signature.
4. Confirm subscription state is saved.
5. Confirm paid feature access.
6. Test cancellation and failed payment.

Switch to live Stripe keys only after the full test passes.

---

## 21. Add structured LLM logging

Log metadata, not full child prompts by default:

```json
{
  "event": "llm_request",
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "operation": "quick_review",
  "latency_ms": 820,
  "input_tokens": 620,
  "output_tokens": 180,
  "success": true
}
```

For detailed review:

```json
{
  "event": "llm_request",
  "provider": "vertex_ai",
  "model": "gemini-2.5-flash",
  "operation": "explain_in_detail",
  "latency_ms": 1600,
  "success": true
}
```

Redact prompts and answers before sending them to Langfuse. Use a short retention period for traces containing educational content.

---

## 22. Configure monitoring and alerts

Read recent logs:

```bash
gcloud run services logs read "$SERVICE_NAME" \
  --region="$REGION" \
  --limit=100
```

Create alerts for:

- Cloud Run 5xx rate
- response latency
- container startup failures
- Cloud SQL CPU and connections
- DeepSeek error rate
- Gemini error rate
- payment webhook failures
- unusual LLM token or cost growth

Use Google Cloud budgets to create alerts at 50%, 80% and 100% of the monthly MVP budget.

---

## 23. Model failure policy

Recommended production behaviour:

### Quick review

1. Call DeepSeek.
2. Retry only transient failures, at most twice.
3. Optionally call Gemini Flash as fallback when DeepSeek is unavailable.
4. Record which provider produced the answer.
5. Never silently charge the user twice for the same action.

### Detailed review

1. Call Gemini through Vertex AI.
2. Retry transient errors.
3. Show a friendly error if unavailable.
4. Do not automatically fall back to a weaker quick model unless the product text clearly explains that a shorter review is being shown.

Add circuit-breaking or temporary provider disabling if repeated failures occur.

---

## 24. Cost controls for the market test

Use these starting settings:

```text
Cloud Run min instances: 0
Cloud Run max instances: 3 for the MVP, then tune against Cloud SQL connection limits
Cloud Run CPU: 1
Cloud Run memory: 1 GiB
Cloud Run concurrency: 20
Cloud SQL: small zonal instance
Quick review max output: 300-500 tokens
Detailed review max output: 1,000-1,500 tokens
```

Also:

- Cache deterministic review results where safe.
- Do not resend the full conversation when only the latest question is needed.
- Use PostgreSQL/pgvector retrieval before asking an LLM to mark objective questions.
- Set a SQLAlchemy connection-pool limit so total Cloud Run connections stay below the Cloud SQL limit.
- Set per-user daily limits.
- Add server-side request timeouts.
- Track tokens separately for quick and detailed actions.

---

## 25. Custom domain and HTTPS

After the Cloud Run URL is stable, map the production domain using Google Cloud's supported domain mapping or an external load balancer.

Then set:

```env
ALLOWED_ORIGINS=https://your-domain.co.uk,https://www.your-domain.co.uk
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

Use cookies with `Secure`, `HttpOnly` and an appropriate `SameSite` value. Do not use `0.0.0.0` in browser URLs; it is a server bind address, not the canonical site origin.

Update Stripe's webhook URL and allowed return URLs to the final HTTPS domain.

---

## 26. Child privacy and UK production checklist

Before accepting real users:

- Publish a clear parent-facing privacy notice.
- Complete a Data Protection Impact Assessment.
- Record DeepSeek and Google as processors/sub-processors where applicable.
- Document international data transfers.
- Avoid behavioural advertising and unnecessary tracking.
- Collect the minimum possible child data.
- Provide parent-controlled account deletion.
- Set deletion and retention periods.
- Ensure support messages do not expose one family's data to another.
- Do not store raw passwords.
- Ensure logs and Langfuse traces are access-controlled.
- Provide a way to report unsafe or incorrect educational content.

This is a technical deployment checklist, not legal advice.

---

## 27. Release procedure for every update

```bash
# 1. Run tests
pytest -q

# 2. Build immutable image
export VERSION="$(date -u +%Y%m%d-%H%M%S)"
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${VERSION}"
gcloud builds submit --tag "$IMAGE" .

# 3. Update and execute migrations
# Do this only when a migration exists.
gcloud run jobs update homework-magic-migrate \
  --image="$IMAGE" \
  --region="$REGION"
gcloud run jobs execute homework-magic-migrate \
  --region="$REGION" \
  --wait

# 4. Deploy a new revision
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE" \
  --region="$REGION"

# 5. Smoke-test the new revision
curl -fsS "${SERVICE_URL}/api/health"

# 6. Verify all three model-routing actions
# quick review -> DeepSeek
# explain in detail -> Gemini
# help me improve -> Gemini
```

Use a staging GCP project before production whenever possible.

---

## 28. Rollback

List revisions:

```bash
gcloud run revisions list \
  --service="$SERVICE_NAME" \
  --region="$REGION"
```

Send all traffic to a known-good revision:

```bash
gcloud run services update-traffic "$SERVICE_NAME" \
  --region="$REGION" \
  --to-revisions="KNOWN_GOOD_REVISION=100"
```

Database migrations should be backwards compatible so that application rollback remains possible.

---

## 29. Final launch order

1. Verify quick and detailed model routing in unit tests.
2. Disable Uvicorn reload.
3. Restrict CORS and protect all admin routes.
4. Confirm accounts, progress, subscriptions, messages and tutor sessions use PostgreSQL.
5. Confirm RAG documents and embeddings use PostgreSQL with pgvector.
6. Verify the embedding model and `EMBEDDING_DIMENSION` match the vector column.
7. Build and test the Docker image locally.
8. Create the GCP project, APIs and Cloud Run service account.
9. Create Cloud SQL PostgreSQL and enable the `vector` extension.
10. Apply Alembic migrations and load the RAG embeddings.
11. Store DeepSeek, database, authentication and Stripe secrets.
12. Build an immutable production image.
13. Deploy to Cloud Run in London.
14. Run health, authentication, vector-search, payment and model-routing smoke tests.
15. Configure the custom domain, secure cookies and exact CORS origins.
16. Enable monitoring, budgets, database connection alerts and provider cost tracking.
17. Start with a small group of test parents.
18. Review quality, latency, vector-search accuracy and cost before increasing traffic.
19. Scale Cloud Run only after confirming Cloud SQL connection-pool limits.
20. Upgrade from Gemini 2.5 Flash before its announced retirement date.

---

## Official references checked

- Cloud SQL create instances: https://cloud.google.com/sql/docs/postgres/create-instance
- Cloud SQL editions: https://cloud.google.com/sql/docs/postgres/choose-edition
- Cloud SQL PostgreSQL extensions: https://cloud.google.com/sql/docs/postgres/extensions
- Connect Cloud Run to Cloud SQL: https://cloud.google.com/sql/docs/postgres/connect-instance-cloud-run
- Cloud SQL pgvector guidance: https://cloud.google.com/sql/docs/postgres/generate-manage-vector-embeddings
- Alembic autogenerate: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- Vertex AI Gemini SDK overview: https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview
- DeepSeek API: https://api-docs.deepseek.com/

Review the current model catalogue before each release. Keep `QUICK_REVIEW_MODEL`, `DETAIL_REVIEW_MODEL`, `EMBEDDING_MODEL` and `EMBEDDING_DIMENSION` configurable.