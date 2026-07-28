# Homework Magic AI Tutor — Production Deployment Runbook

**Target platform:** Google Cloud Run + Cloud SQL for PostgreSQL/pgvector + Secret Manager + Artifact Registry + Stripe live mode  
**Application:** FastAPI/Uvicorn AI Tutor for UK primary-school learners  
**Last reviewed:** 18 July 2026

> [!IMPORTANT]
> A database password was shared between the application and must be treated as exposed. Rotate it before production deployment. Do not reuse it, commit it, place it in an image, or leave it in shell history.

This document assumes the repository root contains `Dockerfile`, `requirements.txt`, `web_app.py`, `src/`, `scripts/`, `static/`, and `.env.example`.

---

## 1. Production architecture

Recommended production layout:

```text
Internet
   |
HTTPS custom domain
   |
Google Cloud Run service
   |-- Secret Manager: database URL, auth secrets, AI key, SMTP key, Stripe keys
   |-- Cloud Logging / Monitoring
   |
Cloud SQL for PostgreSQL
   |-- relational application tables
   |-- pgvector extension
   |-- homework_collection vectors
   |-- elevenplus_collection vectors
   |
Stripe live mode + signed webhook endpoint
```

Use one Google Cloud region for Cloud Run, Cloud SQL, Artifact Registry and related services where possible. For a UK-focused service, `europe-west2` is the London region, subject to your availability, cost and data-location requirements.

---

## 2. Variables used in this guide

Set these in your terminal. Replace every placeholder first.

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west2"
export SERVICE="homework-magic"
export SQL_INSTANCE="homework-magic-prod-db"
export DB_NAME="aitutor"
export DB_USER="aitutor_app"
export AR_REPOSITORY="homework-magic"
export RUNTIME_SA_NAME="homework-magic-runtime"
export RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
export DOMAIN="https://www.homeworkmagic.co.uk"

# Set the active project and default region.
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"
```

Confirm the current project before making changes:

```bash
gcloud config get-value project
gcloud config get-value run/region
```

---

## 3. Local pre-deployment checks

Run these from the repository root.

```bash
python -m compileall -q web_app.py src scripts test
pytest -q
```

Run the coverage gate used by the project:

```bash
pytest -q test/unit test/api test/integration \
  --cov=src.webapp \
  --cov=web_app \
  --cov-report=term \
  --cov-fail-under=55
```

Optional browser tests:

```bash
RUN_E2E=1 pytest -q test/e2e
```

Check that no secrets or local databases will be included in the image:

```bash
git status --short
find . -maxdepth 3 -type f \
  \( -name '.env' -o -name '*.db' -o -name '*.sqlite' -o -name '.coverage' \) \
  -print
```

Ensure `.dockerignore` excludes at least:

```text
.env
.env.*
!.env.example
.git
__pycache__
.pytest_cache
.coverage
*.db
*.sqlite
*.sqlite3
uploads/*
!uploads/.gitkeep
test-results
```

Build and test the production image locally:

```bash
docker build -t homework-magic:prod-check .

docker run --rm -p 8080:8080 \
  -e DEV_MODE=true \
  -e TESTING=false \
  -e PORT=8080 \
  homework-magic:prod-check
```

In another terminal:

```bash
curl -fsS http://localhost:8080/api/health
```

Stop the container after the check.

---

## 4. Enable Google Cloud APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

---

## 5. Create Artifact Registry

```bash
gcloud artifacts repositories create "$AR_REPOSITORY" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Homework Magic production images"
```

Set the image name:

```bash
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${SERVICE}:$(git rev-parse --short HEAD)"
echo "$IMAGE"
```

---

## 6. Create the Cloud Run runtime service account

Create a dedicated runtime identity:

```bash
gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
  --display-name="Homework Magic production runtime"
```

Grant Cloud SQL connectivity:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/cloudsql.client"
```

Do not grant `Owner`, `Editor`, `Cloud Run Admin`, `Secret Manager Admin`, or database-administrator roles to the runtime account.

Secret access is granted per secret later in this guide.

---

## 7. Create Cloud SQL PostgreSQL

### 7.1 Create a production instance

The following is a reasonable starting point. Adjust capacity after load testing.

```bash
gcloud sql instances create "$SQL_INSTANCE" \
  --database-version=POSTGRES_17 \
  --region="$REGION" \
  --tier=db-custom-2-7680 \
  --availability-type=REGIONAL \
  --storage-type=SSD \
  --storage-size=20 \
  --storage-auto-increase \
  --backup-start-time=02:00 \
  --enable-point-in-time-recovery \
  --retained-backups-count=14 \
  --deletion-protection
```

Check the instance:

```bash
gcloud sql instances describe "$SQL_INSTANCE" \
  --format='yaml(name,region,databaseVersion,state,settings.availabilityType,settings.backupConfiguration,settings.deletionProtectionEnabled)'
```

### 7.2 Create the application database

```bash
gcloud sql databases create "$DB_NAME" \
  --instance="$SQL_INSTANCE"
```

### 7.3 Generate a new database password

Do not reuse the password that appeared in chat.

```bash
read -r -s -p "Press Enter, then a new password will be generated securely." _
echo

export DB_PASSWORD_RAW="$(openssl rand -base64 48 | tr -d '\n')"
export DB_PASSWORD_URLENCODED="$(DB_PASSWORD_RAW="$DB_PASSWORD_RAW" python - <<'PY'
import os
from urllib.parse import quote
print(quote(os.environ['DB_PASSWORD_RAW'], safe=''))
PY
)"

# Confirm only the lengths, not the values.
printf 'Raw password length: %s\n' "${#DB_PASSWORD_RAW}"
printf 'Encoded password length: %s\n' "${#DB_PASSWORD_URLENCODED}"
```

Base64 passwords can contain characters such as `+`, `/` and `=`. These must be percent-encoded inside a SQLAlchemy URL.

### 7.4 Create the database user

The simplest option is Google Cloud Console:

1. Open **Cloud SQL → your instance → Users**.
2. Choose **Add user account**.
3. Select built-in authentication.
4. Set username to `aitutor_app`.
5. Paste the newly generated raw password.
6. Save.

CLI alternative:

```bash
gcloud sql users create "$DB_USER" \
  --instance="$SQL_INSTANCE" \
  --password="$DB_PASSWORD_RAW"
```

Run this only in a trusted administrator shell. Unset the raw password after the Secret Manager step.

### 7.5 Enable pgvector and grant schema permissions

Set the `postgres` administrator password using an interactive prompt:

```bash
gcloud sql users set-password postgres \
  --instance="$SQL_INSTANCE" \
  --prompt-for-password
```

Connect as `postgres`:

```bash
gcloud sql connect "$SQL_INSTANCE" \
  --user=postgres \
  --database="$DB_NAME"
```

Run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

GRANT CONNECT ON DATABASE aitutor TO aitutor_app;
GRANT USAGE, CREATE ON SCHEMA public TO aitutor_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aitutor_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO aitutor_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aitutor_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO aitutor_app;

SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```

Exit psql:

```text
\q
```

The application calls `CREATE EXTENSION IF NOT EXISTS vector` during RAG initialisation, but in Cloud SQL only a sufficiently privileged administrator can initially create the extension. Create it before starting the application.

### 7.6 Obtain the Cloud SQL connection name

```bash
export INSTANCE_CONNECTION_NAME="$(gcloud sql instances describe "$SQL_INSTANCE" --format='value(connectionName)')"
echo "$INSTANCE_CONNECTION_NAME"
```

Create the SQLAlchemy URL that uses Cloud Run's Cloud SQL Unix socket:

```bash
export DATABASE_URL_VALUE="postgresql+psycopg://${DB_USER}:${DB_PASSWORD_URLENCODED}@/${DB_NAME}?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"
```

Do not print the full URL. Confirm its non-secret parts only:

```bash
DATABASE_URL_VALUE="$DATABASE_URL_VALUE" python - <<'PY'
import os
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL_VALUE'])
print('Backend:', url.get_backend_name())
print('Driver:', url.get_driver_name())
print('Database:', url.database)
print('Socket:', url.query.get('host'))
print('Password present:', bool(url.password))
PY
```

---

## 8. Create production secrets

### 8.1 Secret helper

```bash
add_secret_value() {
  local name="$1"
  local value="$2"

  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=-
  else
    printf '%s' "$value" | gcloud secrets create "$name" \
      --replication-policy=automatic \
      --data-file=-
  fi
}
```

### 8.2 Generate independent application secrets

Every value must be independent. Do not use the same value for several variables.

```bash
export AUTH_SECRET_VALUE="$(openssl rand -hex 48)"
export SESSION_SECRET_VALUE="$(openssl rand -hex 48)"
export SESSION_OWNER_SECRET_VALUE="$(openssl rand -hex 48)"
export SALT_VALUE="$(openssl rand -hex 48)"
export RESET_RATE_SECRET_VALUE="$(openssl rand -hex 48)"
export LANGFUSE_HASH_SALT_VALUE="$(openssl rand -hex 48)"
```

### 8.3 Store core secrets

```bash
add_secret_value DATABASE_URL "$DATABASE_URL_VALUE"
add_secret_value AUTH_SECRET "$AUTH_SECRET_VALUE"
add_secret_value SESSION_SECRET "$SESSION_SECRET_VALUE"
add_secret_value SESSION_OWNER_SECRET "$SESSION_OWNER_SECRET_VALUE"
add_secret_value SALT "$SALT_VALUE"
add_secret_value PASSWORD_RESET_RATE_LIMIT_SECRET "$RESET_RATE_SECRET_VALUE"
add_secret_value LANGFUSE_USER_HASH_SALT "$LANGFUSE_HASH_SALT_VALUE"
```

Store external service credentials using their real values:

```bash
read -r -s -p "AI provider API key: " AI_API_KEY_VALUE; echo
add_secret_value DEFAULT_API_KEY "$AI_API_KEY_VALUE"
unset AI_API_KEY_VALUE

read -r -s -p "SMTP password: " SMTP_PASSWORD_VALUE; echo
add_secret_value SMTP_PASSWORD "$SMTP_PASSWORD_VALUE"
unset SMTP_PASSWORD_VALUE

read -r -s -p "Stripe LIVE secret key: " STRIPE_SECRET_KEY_VALUE; echo
add_secret_value STRIPE_SECRET_KEY "$STRIPE_SECRET_KEY_VALUE"
unset STRIPE_SECRET_KEY_VALUE

read -r -s -p "Stripe LIVE webhook signing secret: " STRIPE_WEBHOOK_SECRET_VALUE; echo
add_secret_value STRIPE_WEBHOOK_SECRET "$STRIPE_WEBHOOK_SECRET_VALUE"
unset STRIPE_WEBHOOK_SECRET_VALUE
```

Optional Langfuse secrets:

```bash
# Run only when Langfuse production tracing is enabled.
# read -r -s -p "Langfuse secret key: " LANGFUSE_SECRET_KEY_VALUE; echo
# add_secret_value LANGFUSE_SECRET_KEY "$LANGFUSE_SECRET_KEY_VALUE"
# unset LANGFUSE_SECRET_KEY_VALUE
#
# read -r -s -p "Langfuse public key: " LANGFUSE_PUBLIC_KEY_VALUE; echo
# add_secret_value LANGFUSE_PUBLIC_KEY "$LANGFUSE_PUBLIC_KEY_VALUE"
# unset LANGFUSE_PUBLIC_KEY_VALUE
```

Grant the runtime account access to each required secret:

```bash
for SECRET_NAME in \
  DATABASE_URL \
  AUTH_SECRET \
  SESSION_SECRET \
  SESSION_OWNER_SECRET \
  SALT \
  PASSWORD_RESET_RATE_LIMIT_SECRET \
  LANGFUSE_USER_HASH_SALT \
  DEFAULT_API_KEY \
  SMTP_PASSWORD \
  STRIPE_SECRET_KEY \
  STRIPE_WEBHOOK_SECRET
do
  gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

Remove secret values from the current shell:

```bash
unset DB_PASSWORD_RAW DB_PASSWORD_URLENCODED DATABASE_URL_VALUE
unset AUTH_SECRET_VALUE SESSION_SECRET_VALUE SESSION_OWNER_SECRET_VALUE SALT_VALUE
unset RESET_RATE_SECRET_VALUE LANGFUSE_HASH_SALT_VALUE
```

---

## 9. Production environment configuration

Create a temporary non-secret environment YAML file:

```bash
cat > /tmp/homework-magic-prod-env.yaml <<EOF_ENV
DEV_MODE: "false"
TESTING: "false"
PORT: "8080"
APP_BASE_URL: "${DOMAIN}"
PUBLIC_BASE_URL: "${DOMAIN}"
CORS_ORIGINS: "${DOMAIN}"
COOKIE_SECURE: "true"
TRUST_PROXY_HEADERS: "true"
ENFORCE_PRODUCTION_CONFIG: "true"

DATA_CONTROLLER_NAME: "Homework Magic"
PRIVACY_CONTACT_EMAIL: "privacy@homeworkmagic.co.uk"
PRIVACY_POSTAL_ADDRESS: "contact@homeworkmagic.co.uk"
ADMIN_EMAILS: "admin@homeworkmagic.co.uk"

LLM_PROVIDER: "api"
DEFAULT_ENDPOINT_OPENAI: "https://your-provider.example/v1"
DEFAULT_MODEL: "your-low-cost-model"
DEFAULT_VISION_MODEL: "your-vision-model"
QUICK_REVIEW_MODEL: "your-low-cost-model"
DETAIL_REVIEW_MODEL: "your-capable-model"
LLM_TIMEOUT_SECONDS: "60"
LLM_MAX_RETRIES: "1"
LLM_RETRY_DELAY: "0.5"
MAX_AI_CONCURRENCY: "8"
AI_QUEUE_TIMEOUT_SECONDS: "4"
AI_REQUEST_TIMEOUT_SECONDS: "90"
HOMEWORK_SUBJECT_WORKERS: "4"

REVIEW_HOMEWORK_MAX_CHARS: "8000"
REVIEW_ANSWERS_MAX_CHARS: "5000"
REVIEW_FEEDBACK_MAX_CHARS: "5000"
QUICK_REVIEW_MAX_TOKENS: "5000"
DETAIL_REVIEW_MAX_TOKENS: "8000"
PRACTICE_MAX_TOKENS: "5000"

EMBEDDING_PROVIDER: "local"
LOCAL_EMBEDDING_MODEL: "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION: "384"
RAG_MAX_QUERY_RESULTS: "50"
RAG_MAX_RETRIES: "3"
RAG_RETRY_DELAY: "0.4"
ELEVENPLUS_RAG_ALLOW_SQLITE: "false"

STORE_RAW_LEARNER_CONTENT: "false"
STORE_RAW_AI_CONTENT: "false"
LEARNING_RECORD_RETENTION_DAYS: "365"
MESSAGE_RETENTION_DAYS: "180"
SESSION_TTL_SECONDS: "43200"
SESSION_MAX_AGE: "43200"

MAX_REQUEST_BYTES: "18874368"
MAX_UPLOAD_BYTES: "16777216"
MAX_EXTRACTED_TEXT_CHARS: "30000"
MAX_PDF_PAGES: "30"
MAX_IMAGE_PIXELS: "25000000"

PASSWORD_RESET_TOKEN_MINUTES: "30"
PASSWORD_RESET_MAX_EMAIL_PER_HOUR: "3"
PASSWORD_RESET_MAX_CLIENT_PER_HOUR: "10"
PASSWORD_RESET_DEV_SHOW_LINK: "false"
SMTP_HOST: "smtp.your-provider.example"
SMTP_PORT: "587"
SMTP_USERNAME: "support@homeworkmagic.co.uk"
SMTP_FROM: "Homework Magic <support@homeworkmagic.co.uk>"
SMTP_TIMEOUT_SECONDS: "15"

STRIPE_EXPECTED_LIVEMODE: "true"
STRIPE_PRICE_HOMEWORK_MONTHLY: "price_live_replace_me"
STRIPE_PRICE_ELEVENPLUS_MONTHLY: "price_live_replace_me"
STRIPE_PRICE_FAMILY_MONTHLY: "price_live_replace_me"

LANGFUSE_ENABLED: "false"
LANGFUSE_HOST: "https://cloud.langfuse.com"
LANGFUSE_TRACING_ENVIRONMENT: "production"

DB_POOL_SIZE: "5"
DB_MAX_OVERFLOW: "5"
DB_POOL_RECYCLE_SECONDS: "1800"
DB_POOL_TIMEOUT_SECONDS: "15"
WEB_CONCURRENCY: "1"
EOF_ENV
```

Replace all placeholder values before deployment.

The application readiness check will reject unsafe production settings, including:

- a non-PostgreSQL `DATABASE_URL`;
- a non-HTTPS `APP_BASE_URL`;
- empty or wildcard CORS origins;
- missing administrator emails;
- missing legal/privacy operator details;
- a `SESSION_OWNER_SECRET` shorter than 32 characters;
- disabled secure cookies;
- raw learner or AI content storage enabled.

---

## 10. Build and push the image

```bash
gcloud builds submit --tag "$IMAGE" .
```

Confirm the image exists:

```bash
gcloud artifacts docker images describe "$IMAGE"
```

---

## 11. Deploy a candidate Cloud Run revision

Use explicit secret versions in production. Google recommends pinning secrets exposed as environment variables because they are resolved when an instance starts.

Get the newest enabled version number for each secret:

```bash
latest_secret_version() {
  gcloud secrets versions list "$1" \
    --filter='state=ENABLED' \
    --sort-by='~createTime' \
    --limit=1 \
    --format='value(name)' | awk -F/ '{print $NF}'
}

export DATABASE_URL_VERSION="$(latest_secret_version DATABASE_URL)"
export AUTH_SECRET_VERSION="$(latest_secret_version AUTH_SECRET)"
export SESSION_SECRET_VERSION="$(latest_secret_version SESSION_SECRET)"
export SESSION_OWNER_SECRET_VERSION="$(latest_secret_version SESSION_OWNER_SECRET)"
export SALT_VERSION="$(latest_secret_version SALT)"
export RESET_SECRET_VERSION="$(latest_secret_version PASSWORD_RESET_RATE_LIMIT_SECRET)"
export HASH_SALT_VERSION="$(latest_secret_version LANGFUSE_USER_HASH_SALT)"
export AI_KEY_VERSION="$(latest_secret_version DEFAULT_API_KEY)"
export SMTP_PASSWORD_VERSION="$(latest_secret_version SMTP_PASSWORD)"
export STRIPE_KEY_VERSION="$(latest_secret_version STRIPE_SECRET_KEY)"
export STRIPE_WEBHOOK_VERSION="$(latest_secret_version STRIPE_WEBHOOK_SECRET)"
```

Deploy without sending public traffic yet:

```bash
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$RUNTIME_SA" \
  --add-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
  --env-vars-file=/tmp/homework-magic-prod-env.yaml \
  --set-secrets="DATABASE_URL=DATABASE_URL:${DATABASE_URL_VERSION},PGVECTOR_DATABASE_URL=DATABASE_URL:${DATABASE_URL_VERSION},AUTH_SECRET=AUTH_SECRET:${AUTH_SECRET_VERSION},SESSION_SECRET=SESSION_SECRET:${SESSION_SECRET_VERSION},SESSION_OWNER_SECRET=SESSION_OWNER_SECRET:${SESSION_OWNER_SECRET_VERSION},SALT=SALT:${SALT_VERSION},PASSWORD_RESET_RATE_LIMIT_SECRET=PASSWORD_RESET_RATE_LIMIT_SECRET:${RESET_SECRET_VERSION},LANGFUSE_USER_HASH_SALT=LANGFUSE_USER_HASH_SALT:${HASH_SALT_VERSION},DEFAULT_API_KEY=DEFAULT_API_KEY:${AI_KEY_VERSION},SMTP_PASSWORD=SMTP_PASSWORD:${SMTP_PASSWORD_VERSION},STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:${STRIPE_KEY_VERSION},STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:${STRIPE_WEBHOOK_VERSION}" \
  --port=8080 \
  --cpu=2 \
  --memory=2Gi \
  --concurrency=20 \
  --timeout=300 \
  --min-instances=0 \
  --max-instances=3 \
  --allow-unauthenticated \
  --tag=candidate \
  --no-traffic
```

The local embedding model consumes memory. Begin with one Uvicorn worker and at least 2 GiB memory, then adjust from real measurements.

Keep total possible PostgreSQL connections within the Cloud SQL limit:

```text
maximum possible connections ≈ max Cloud Run instances
                             × WEB_CONCURRENCY
                             × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

With the sample settings, the theoretical maximum is `3 × 1 × (5 + 5) = 30` application connections.

---

## 12. Test the candidate revision

Get its tagged URL:

```bash
export CANDIDATE_URL="$(gcloud run services describe "$SERVICE" \
  --region="$REGION" \
  --format="value(status.traffic[?tag='candidate'].url)")"

echo "$CANDIDATE_URL"
```

Check liveness:

```bash
curl -fsS "$CANDIDATE_URL/api/health"
```

Check readiness, including production configuration and database access:

```bash
curl -fsS "$CANDIDATE_URL/api/ready"
```

Expected readiness response:

```json
{
  "status": "ready",
  "database": "ok",
  "configuration": "ok"
}
```

Check logs without displaying secret values:

```bash
gcloud run services logs read "$SERVICE" \
  --region="$REGION" \
  --limit=100
```

Confirm the RAG backend reports PostgreSQL rather than SQLite. Search logs for a password-free target similar to:

```text
[PGVector] collection=homework_collection database=postgresql://localhost/aitutor
[PGVector] collection=elevenplus_collection database=postgresql://localhost/aitutor
```

The displayed host may be `localhost` because the SQLAlchemy URL uses a Unix socket. The important check is that the backend begins with `postgresql`, not `sqlite`.

Perform a minimal functional smoke test with a dedicated test parent account:

1. Register and sign in.
2. Create a learner profile with invented data only.
3. Generate one primary Maths worksheet.
4. Submit answers and verify the review.
5. Generate one 11+ practice set.
6. Verify the account, privacy, safety and contact pages.
7. Verify password-reset email delivery.
8. Verify administrator pages reject non-admin users.
9. Verify no raw learner text appears in Cloud Logging or Langfuse.

---

## 13. Send production traffic to the candidate

```bash
gcloud run services update-traffic "$SERVICE" \
  --region="$REGION" \
  --to-tags=candidate=100
```

Get the normal service URL:

```bash
export SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --region="$REGION" \
  --format='value(status.url)')"

echo "$SERVICE_URL"
```

Repeat:

```bash
curl -fsS "$SERVICE_URL/api/health"
curl -fsS "$SERVICE_URL/api/ready"
```

---

## 14. Configure the custom domain and HTTPS

Map your verified domain to the Cloud Run service using Google Cloud's supported domain mapping or an external HTTPS load balancer.

After HTTPS is working:

1. Set `APP_BASE_URL`, `PUBLIC_BASE_URL` and `CORS_ORIGINS` to the exact public HTTPS origin.
2. Do not include a trailing slash unless the application specifically expects one.
3. Keep `COOKIE_SECURE=true`.
4. Keep `TRUST_PROXY_HEADERS=true` behind Cloud Run or a trusted load balancer.
5. Deploy a new revision with the corrected values.
6. Confirm `/api/ready` returns `configuration: ok`.

Do not use `CORS_ORIGINS=*` with authenticated cookies.

---

## 15. Switch Stripe from test mode to live mode

Complete Stripe account activation and business verification before accepting real payments.

### 15.1 Create live products and recurring prices

In Stripe live mode, create the products and prices used by the app. Record the live `price_...` identifiers for:

```text
STRIPE_PRICE_HOMEWORK_MONTHLY
STRIPE_PRICE_ELEVENPLUS_MONTHLY
STRIPE_PRICE_FAMILY_MONTHLY
```

Update `/tmp/homework-magic-prod-env.yaml` with the live price IDs.

### 15.2 Store the live secret key

Use a live secret key or a suitably restricted live key. Never use a test key in production.

```bash
read -r -s -p "New Stripe LIVE secret key: " STRIPE_SECRET_KEY_VALUE; echo
printf '%s' "$STRIPE_SECRET_KEY_VALUE" | \
  gcloud secrets versions add STRIPE_SECRET_KEY --data-file=-
unset STRIPE_SECRET_KEY_VALUE
```

### 15.3 Create a live webhook endpoint

Create a Stripe live webhook pointing to the application's production webhook route. Check the billing router in the deployed version for the exact route, commonly something such as:

```text
https://www.homeworkmagic.co.uk/api/billing/webhook
```

Subscribe only to the events the application handles. Typical subscription applications need events for successful checkout/subscription creation, subscription updates/deletion and relevant payment failures.

Stripe gives each endpoint and mode its own `whsec_...` signing secret. The test signing secret is not valid for the live endpoint.

Store the live signing secret:

```bash
read -r -s -p "New Stripe LIVE webhook secret: " STRIPE_WEBHOOK_SECRET_VALUE; echo
printf '%s' "$STRIPE_WEBHOOK_SECRET_VALUE" | \
  gcloud secrets versions add STRIPE_WEBHOOK_SECRET --data-file=-
unset STRIPE_WEBHOOK_SECRET_VALUE
```

Set:

```text
STRIPE_EXPECTED_LIVEMODE=true
```

Deploy a new revision pinned to the new Stripe secret versions and live price IDs.

### 15.4 Live payment verification

Use a real low-value transaction that you are authorised to make, then verify:

1. Checkout completes on HTTPS.
2. The webhook signature is accepted.
3. A subscription is recorded against the correct parent account.
4. Premium access is granted only after a verified live event.
5. Cancellation and failed-payment events remove or restrict access correctly.
6. No full card data reaches application logs or the database.
7. Refund and cancellation wording is visible to the parent before purchase.

---

## 16. Password rotation

### 16.1 Immediate action for the password exposed in chat

Rotate it before production use. The safe order depends on whether the application is already live.

### 16.2 Rotation before launch

When no production traffic exists:

1. Generate a new random raw password.
2. Change the Cloud SQL user's password.
3. URL-encode it.
4. create a new `DATABASE_URL` secret version.
5. Deploy a revision pinned to the new version.
6. Verify `/api/ready`.
7. Disable the old secret version.

Generate:

```bash
export NEW_DB_PASSWORD_RAW="$(openssl rand -base64 48 | tr -d '\n')"
export NEW_DB_PASSWORD_URLENCODED="$(NEW_DB_PASSWORD_RAW="$NEW_DB_PASSWORD_RAW" python - <<'PY'
import os
from urllib.parse import quote
print(quote(os.environ['NEW_DB_PASSWORD_RAW'], safe=''))
PY
)"
```

Change the Cloud SQL user password:

```bash
gcloud sql users set-password "$DB_USER" \
  --instance="$SQL_INSTANCE" \
  --prompt-for-password
```

Paste `NEW_DB_PASSWORD_RAW` at the prompt.

Build the replacement URL:

```bash
export NEW_DATABASE_URL="postgresql+psycopg://${DB_USER}:${NEW_DB_PASSWORD_URLENCODED}@/${DB_NAME}?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"
```

Add a new Secret Manager version:

```bash
printf '%s' "$NEW_DATABASE_URL" | \
  gcloud secrets versions add DATABASE_URL --data-file=-
```

Find the new version:

```bash
export NEW_DATABASE_URL_VERSION="$(latest_secret_version DATABASE_URL)"
echo "$NEW_DATABASE_URL_VERSION"
```

Update the Cloud Run secret references, which creates a new revision:

```bash
gcloud run services update "$SERVICE" \
  --region="$REGION" \
  --update-secrets="DATABASE_URL=DATABASE_URL:${NEW_DATABASE_URL_VERSION},PGVECTOR_DATABASE_URL=DATABASE_URL:${NEW_DATABASE_URL_VERSION}"
```

Verify:

```bash
curl -fsS "$SERVICE_URL/api/ready"
```

Unset values:

```bash
unset NEW_DB_PASSWORD_RAW NEW_DB_PASSWORD_URLENCODED NEW_DATABASE_URL
```

### 16.3 Same-user rotation on a live service

Changing the password of the active role invalidates new database connections from old Cloud Run instances immediately. Existing pooled connections may continue temporarily, creating inconsistent behaviour.

Use a maintenance window:

1. Record the currently serving Cloud Run revision.
2. Temporarily prevent user writes or announce maintenance.
3. Change the Cloud SQL password.
4. Add a new `DATABASE_URL` secret version.
5. Deploy a revision pinned to the new version.
6. Route 100% traffic to the new revision.
7. Confirm readiness and key user journeys.
8. Stop old revisions by ensuring no traffic remains and reducing minimum instances if needed.
9. Disable the old Secret Manager version.

### 16.4 Lower-downtime rotation using a second database role

For a busy service, use a second role instead of changing the current role in place.

Connect as `postgres` and create a new role:

```sql
CREATE ROLE aitutor_app_next LOGIN PASSWORD 'PASTE_A_NEW_RANDOM_PASSWORD';

GRANT CONNECT ON DATABASE aitutor TO aitutor_app_next;
GRANT USAGE, CREATE ON SCHEMA public TO aitutor_app_next;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aitutor_app_next;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO aitutor_app_next;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aitutor_app_next;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO aitutor_app_next;
```

Then:

1. Create a database URL using `aitutor_app_next`.
2. Add it as a new `DATABASE_URL` secret version.
3. Deploy a candidate Cloud Run revision using the new role.
4. Test `/api/ready` and all write operations.
5. Route traffic to the new revision.
6. Observe logs and database errors.
7. Revoke the old role only after old revisions have fully stopped:

```sql
ALTER ROLE aitutor_app NOLOGIN;
```

After a safe observation period, remove old grants or drop the old role. Do not drop a role that still owns database objects; reassign ownership first if necessary.

### 16.5 Rotate other secrets

Rotate these independently and deploy a new revision after each security-sensitive change:

```text
AUTH_SECRET
SESSION_SECRET
SESSION_OWNER_SECRET
SALT
PASSWORD_RESET_RATE_LIMIT_SECRET
DEFAULT_API_KEY
SMTP_PASSWORD
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
LANGFUSE_SECRET_KEY
LANGFUSE_USER_HASH_SALT
```

Important effects:

- Rotating authentication/session signing secrets may sign out all users.
- Rotating `SESSION_OWNER_SECRET` can affect ownership hashes used across instances; plan and test this carefully.
- Rotating the Stripe webhook secret requires changing the Stripe endpoint configuration and application secret together.
- Secret Manager environment variables are loaded at instance startup, so create a new Cloud Run revision after adding a secret version.

Disable an old secret version only after the replacement revision is healthy:

```bash
gcloud secrets versions disable OLD_VERSION \
  --secret=SECRET_NAME
```

Destroy an old version only when rollback is no longer required:

```bash
gcloud secrets versions destroy OLD_VERSION \
  --secret=SECRET_NAME
```

---

## 17. Backups and recovery

Confirm automated backups and point-in-time recovery:

```bash
gcloud sql instances describe "$SQL_INSTANCE" \
  --format='yaml(settings.backupConfiguration)'
```

Create an on-demand backup before risky changes:

```bash
gcloud sql backups create \
  --instance="$SQL_INSTANCE" \
  --description="Before production release $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

List backups:

```bash
gcloud sql backups list --instance="$SQL_INSTANCE"
```

Test restoration to a separate instance before launch and at least periodically. A backup that has never been restored is not a proven recovery plan.

Document:

- recovery point objective;
- recovery time objective;
- who can authorise a restore;
- how the application database URL is switched to a restored instance;
- how to validate learner/account and subscription consistency after recovery.

---

## 18. Monitoring and alerts

Create alerts for at least:

- Cloud Run 5xx response rate;
- Cloud Run request latency;
- Cloud Run instance count and container startup failures;
- `/api/ready` returning 503;
- Cloud SQL CPU, memory, disk and connection usage;
- Cloud SQL replication/failover events;
- application database exceptions;
- AI provider timeout/error rate;
- Stripe webhook failures;
- SMTP/password-reset failures;
- unusual administrator access attempts.

Keep learner prompts, answers, names, email addresses, access tokens, passwords and API keys out of logs. Keep:

```text
STORE_RAW_LEARNER_CONTENT=false
STORE_RAW_AI_CONTENT=false
```

If Langfuse is enabled, verify traces use pseudonymous identifiers and do not contain raw learner content.

---

## 19. UK child privacy and safety launch gate

Because this service is designed for children, complete and approve a Data Protection Impact Assessment before launch. The UK ICO Children's Code expects services likely to be accessed by children to put the child's best interests first, use high-privacy defaults and minimise data collection.

Before production traffic:

- identify the legal data controller;
- publish the privacy notice and child-friendly explanation;
- publish the safety/safeguarding page;
- record the lawful basis for each processing purpose;
- document parent/guardian account and learner-profile flows;
- collect only the minimum learner information required;
- keep raw learner and AI content storage disabled unless separately justified in the DPIA;
- document retention and deletion schedules;
- test parent data export and deletion;
- test cross-account isolation;
- restrict and audit administrator access;
- document processor contracts and international data transfers;
- confirm AI, email, observability and payment providers are listed in the privacy information;
- prepare a personal-data breach process, including assessment and ICO notification within 72 hours when legally required;
- provide a monitored privacy and safeguarding contact.

This runbook is technical guidance, not legal advice. Obtain professional advice for your exact business structure and processing activities.

---

## 20. Rollback

List revisions:

```bash
gcloud run revisions list \
  --service="$SERVICE" \
  --region="$REGION"
```

Route all traffic to the last known-good revision:

```bash
export GOOD_REVISION="replace-with-known-good-revision"

gcloud run services update-traffic "$SERVICE" \
  --region="$REGION" \
  --to-revisions="${GOOD_REVISION}=100"
```

Verify:

```bash
curl -fsS "$SERVICE_URL/api/health"
curl -fsS "$SERVICE_URL/api/ready"
```

Do not roll back application code across an incompatible database migration without a tested database rollback or forward-fix plan.

---

## 21. Post-deployment verification checklist

### Infrastructure

- [ ] Cloud Run service uses the dedicated runtime service account.
- [ ] Runtime service account has only Cloud SQL Client and per-secret accessor permissions.
- [ ] Cloud SQL is regional/high availability where required.
- [ ] Cloud SQL deletion protection is enabled.
- [ ] Automated backups and PITR are enabled.
- [ ] A restore test has succeeded.
- [ ] pgvector exists and both RAG collections use PostgreSQL.
- [ ] No production component uses SQLite or local Chroma storage.

### Application configuration

- [ ] `DEV_MODE=false`.
- [ ] `TESTING=false`.
- [ ] `ENFORCE_PRODUCTION_CONFIG=true`.
- [ ] `APP_BASE_URL` and `PUBLIC_BASE_URL` are exact HTTPS URLs.
- [ ] `CORS_ORIGINS` contains exact HTTPS origins and no wildcard.
- [ ] `COOKIE_SECURE=true`.
- [ ] `TRUST_PROXY_HEADERS=true` only behind trusted infrastructure.
- [ ] Administrator emails and legal/privacy details are set.
- [ ] All signing secrets are unique and at least 32 characters.
- [ ] `/api/health` returns 200.
- [ ] `/api/ready` returns 200 with database and configuration `ok`.

### Privacy and child safety

- [ ] `STORE_RAW_LEARNER_CONTENT=false`.
- [ ] `STORE_RAW_AI_CONTENT=false`.
- [ ] DPIA is approved and versioned.
- [ ] Privacy, safety and contact pages show real operator details.
- [ ] Parent export and deletion work.
- [ ] Cross-account learner access is blocked.
- [ ] Admin access is restricted and logged.
- [ ] Retention jobs and deletion procedures are documented.

### Billing

- [ ] Stripe account is activated.
- [ ] Live products and price IDs are configured.
- [ ] Live secret key is stored in Secret Manager.
- [ ] Live webhook endpoint and signing secret are configured.
- [ ] `STRIPE_EXPECTED_LIVEMODE=true`.
- [ ] A live authorised payment, cancellation and webhook flow have been verified.

### Operations

- [ ] Monitoring and alerts are active.
- [ ] Rollback has been tested.
- [ ] Password and key rotation owners are assigned.
- [ ] Incident and breach contacts are documented.
- [ ] No exposed password or old test credential remains active.

---

## 22. Recommended release procedure for future deployments

For each release:

1. Pull the release commit and review dependency changes.
2. Run compile, unit, API, integration and browser tests.
3. Scan for secrets and generated database files.
4. Create an on-demand Cloud SQL backup before database-affecting changes.
5. Build an immutable image tagged with the Git commit.
6. Deploy a tagged candidate revision with no traffic.
7. Check `/api/health`, `/api/ready`, logs and key user journeys.
8. Route a small percentage of traffic to the candidate when appropriate.
9. Observe errors, latency, database connections and AI-provider usage.
10. Route 100% traffic after acceptance.
11. Keep the previous revision available for rollback.
12. Record the image, revision, secret versions and deployment operator in the release log.

---

## 23. Official references

- Cloud Run container deployment: <https://docs.cloud.google.com/run/docs/deploying>
- Cloud Run container runtime contract: <https://docs.cloud.google.com/run/docs/container-contract>
- Cloud Run secrets: <https://docs.cloud.google.com/run/docs/configuring/services/secrets>
- Cloud Run to Cloud SQL: <https://docs.cloud.google.com/sql/docs/postgres/connect-run>
- Cloud SQL PostgreSQL extensions: <https://docs.cloud.google.com/sql/docs/postgres/extensions>
- Cloud SQL users and password changes: <https://docs.cloud.google.com/sql/docs/postgres/create-manage-users>
- Cloud SQL backups: <https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/backups>
- Cloud SQL point-in-time recovery: <https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/pitr>
- Secret Manager overview: <https://docs.cloud.google.com/secret-manager/docs/overview>
- Secret Manager best practices: <https://docs.cloud.google.com/secret-manager/docs/best-practices>
- Stripe API keys: <https://docs.stripe.com/keys>
- Stripe webhooks: <https://docs.stripe.com/webhooks>
- ICO Children's Code: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/childrens-code-guidance-and-resources/age-appropriate-design-a-code-of-practice-for-online-services/>
- ICO DPIA guidance for children's services: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/childrens-code-guidance-and-resources/age-appropriate-design-a-code-of-practice-for-online-services/2-data-protection-impact-assessments/>
- ICO breach response: <https://ico.org.uk/for-organisations/advice-for-small-organisations/personal-data-breaches/72-hours-how-to-respond-to-a-personal-data-breach/>

gcloud run services update "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="$FAILED_IMAGE" \
  --update-env-vars="DATA_CONTROLLER_NAME=Homework Magic" \
  --no-traffic \
  --tag=staging