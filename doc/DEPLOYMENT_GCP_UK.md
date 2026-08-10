# AI Tutor: Google Cloud UK production deployment

Last checked: 19 July 2026  
Target: Cloud Run and Cloud SQL in London (`europe-west2`)  
Application: the supplied `aitutor(6).zip`

## Recommended deployment shape

- Cloud Run service in `europe-west2`, using the supplied Dockerfile.
- Cloud SQL for PostgreSQL 17 in `europe-west2`, with `pgvector`, high availability, backups and point-in-time recovery.
- Secret Manager for database credentials, DeepSeek, Stripe and application secrets.
- A dedicated Cloud Run service account with only Cloud SQL, Vertex AI and secret access.
- One staging revision first, then production. Deploy Stripe in sandbox mode before switching to live mode.
- Keep the development `.env` only on the developer machine. Do not copy it, upload it, or use it as Cloud Run configuration.

Cloud Run supports container deployments and Cloud SQL connections through a Unix socket at `/cloudsql/PROJECT:REGION:INSTANCE`. Google recommends Secret Manager for service secrets. See the official [Cloud Run deployment](https://docs.cloud.google.com/run/docs/deploying), [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets), and [Cloud Run to Cloud SQL](https://docs.cloud.google.com/sql/docs/postgres/connect-run) documentation.

## 1. Resolve these issues before a live deployment

Do not accept real users or payments until these items are resolved.

1. **Rotate the exposed database password.** The supplied archive contains a hard-coded PostgreSQL URL in `scripts/gcp_utils.py` and `scripts/password_generator.py`. Treat that password as compromised, remove it from both files and from Git history, and create a new production database user/password. Never deploy that password.
2. **Fix the duplicate Stripe portal call.** `src/webapp/billing.py`, inside the `/portal` handler, calls `create_portal(...)` twice. Remove the duplicate line so one click creates one portal session.
3. **Add the missing deployment files.** `README.md` refers to `.env.example`, `.env.stripe-live.example`, `doc/`, and migrations, but they are absent from the archive. `alembic.ini` points to a missing `migrations/` directory. The current code creates tables with SQLAlchemy `create_all`, which is enough for a new empty database but is not a safe schema-upgrade process. Add and test Alembic migrations before the first later schema change.
4. **Reduce the image contents.** Add `cloud-sql-proxy`, `pytest-of-root`, `.coverage`, and `coverage.xml` to `.dockerignore`. The bundled proxy is about 36 MB and Cloud Run already supplies the Cloud SQL connection.
5. **Make dependency builds reproducible.** The Dockerfile installs the unpinned `requirements.txt` even though lock files are present. Test a lock file and have Docker install that exact file before production.
6. **Plan the embedding model download.** `all-MiniLM-L6-v2` is loaded lazily by `sentence-transformers`. Its first semantic RAG request may download model files. Prefer baking the model into the image or warming and testing it in a Cloud Run Job. Exact metadata RAG lookups do not need an embedding call.
7. **Complete launch governance.** This service is intended for children. Complete a child-focused DPIA before processing, apply the ICO Children’s Code, document the lawful basis, retention, processors and safeguarding process, and publish final controller/contact details. The ICO says a DPIA should identify and minimise risks to children before processing begins. See the [Children’s Code](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/childrens-code-guidance-and-resources/age-appropriate-design-a-code-of-practice-for-online-services/) and [child-focused DPIA guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/childrens-code-guidance-and-resources/age-appropriate-design-a-code-of-practice-for-online-services/2-data-protection-impact-assessments/).

## 2. Confirm the model configuration

The requested model identifiers are valid as of the date above:

```dotenv
QUICK_REVIEW_PROVIDER=deepseek
QUICK_REVIEW_MODEL=deepseek-v4-flash
DETAIL_REVIEW_PROVIDER=vertex_ai
DETAIL_REVIEW_MODEL=gemini-3.6-flash
```

DeepSeek documents `deepseek-v4-pro` at the OpenAI-compatible base URL `https://api.deepseek.com`; Google documents the stable model code `gemini-3.6-flash`. See [DeepSeek models](https://api-docs.deepseek.com/quick_start/pricing/) and [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash).

Important location point: run Cloud Run and Cloud SQL in London, but set `GOOGLE_CLOUD_LOCATION` only to a Vertex location where `gemini-3.6-flash` is enabled for your project. Start by checking Vertex AI Model Garden. If the model is available only through the global endpoint, use:

```dotenv
GOOGLE_CLOUD_LOCATION=global
```

That means the application and database are UK-hosted, but the Gemini inference endpoint is not a UK-only regional endpoint. DeepSeek is also an external provider. Do not describe the whole service as “UK-only data residency” unless your provider contracts and actual endpoints support that claim. Keep `STORE_RAW_LEARNER_CONTENT=false` and `STORE_RAW_AI_CONTENT=false`, minimise prompts, and complete the required international-transfer safeguard and transfer risk assessment. See the ICO’s [international transfer guide](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/a-brief-guide-to-international-transfers/) and [transfer risk assessment guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/completing-a-transfer-risk-assessment/).

The supplied code already uses the correct Google Gen AI SDK pattern: `genai.Client(vertexai=True, project=..., location=...)` with Application Default Credentials. See the [Google Gen AI SDK client documentation](https://googleapis.github.io/python-genai/genai.html).

## 3. Keep development and production environments separate

Keep the existing local `.env` for development tests. It is already excluded by `.gitignore` and `.dockerignore`. Never rename it to a production file and never run Cloud Run with `--env-file .env`.

Create a local, uncommitted `prod-env.yaml` containing only non-secret values:

```yaml
DEV_MODE: "false"
TESTING: "false"
ENFORCE_PRODUCTION_CONFIG: "true"
APP_BASE_URL: "https://YOUR_DOMAIN"
PUBLIC_BASE_URL: "https://YOUR_DOMAIN"
CORS_ORIGINS: "https://YOUR_DOMAIN"
COOKIE_SECURE: "true"
TRUST_PROXY_HEADERS: "true"
WEB_CONCURRENCY: "1"

QUICK_REVIEW_PROVIDER: "deepseek"
QUICK_REVIEW_MODEL: "deepseek-v4-flash"
DETAIL_REVIEW_PROVIDER: "vertex_ai"
DETAIL_REVIEW_MODEL: "gemini-3.6-flash"
GOOGLE_CLOUD_PROJECT: "YOUR_PROJECT_ID"
GOOGLE_CLOUD_LOCATION: "global"
DEEPSEEK_BASE_URL: "https://api.deepseek.com"
LLM_MAX_RETRIES: "1"
LLM_TIMEOUT_SECONDS: "90"

EMBEDDING_PROVIDER: "local"
LOCAL_EMBEDDING_MODEL: "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION: "384"

DB_POOL_SIZE: "3"
DB_MAX_OVERFLOW: "2"
DB_POOL_TIMEOUT_SECONDS: "15"
DB_POOL_RECYCLE_SECONDS: "1800"

MAX_AI_CONCURRENCY: "8"
AI_QUEUE_TIMEOUT_SECONDS: "4"
AI_REQUEST_TIMEOUT_SECONDS: "120"
MAX_REQUEST_BYTES: "18874368"

STORE_RAW_LEARNER_CONTENT: "false"
STORE_RAW_AI_CONTENT: "false"
LEARNING_RECORD_RETENTION_DAYS: "365"
MESSAGE_RETENTION_DAYS: "180"
SESSION_MAX_AGE: "43200"

DATA_CONTROLLER_NAME: "YOUR LEGAL ENTITY"
PRIVACY_CONTACT_EMAIL: "privacy@YOUR_DOMAIN"
PRIVACY_POSTAL_ADDRESS: "YOUR POSTAL ADDRESS"
ADMIN_EMAILS: "YOUR_ADMIN_EMAIL"

STRIPE_BILLING_ENABLED: "false"
STRIPE_EXPECTED_LIVEMODE: "false"
```

Use exact origins, with no wildcard and no trailing slash. Replace `APP_BASE_URL`, `PUBLIC_BASE_URL` and `CORS_ORIGINS` after the custom domain is working.

Store these as secrets, not in `prod-env.yaml`:

- `DATABASE_URL` and `PGVECTOR_DATABASE_URL` (the same Cloud SQL URL is suitable)
- `DEEPSEEK_API_KEY`
- `SESSION_OWNER_SECRET` (at least 32 random characters)
- `PASSWORD_RESET_RATE_LIMIT_SECRET`
- Stripe secret key and webhook secret, when billing is enabled
- SMTP password, if email/password reset is enabled
- Optional Langfuse secret and hashing salt

## 4. Create and select the Google Cloud project

Install the current Google Cloud CLI, sign in, attach a billing account, then run:

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export REGION="europe-west2"
export SERVICE="aitutor-prod"
export SQL_INSTANCE="aitutor-prod-pg"
export DB_NAME="aitutor"
export DB_USER="aitutor_app"
export REPOSITORY="aitutor"

gcloud auth login
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com
```

Create a dedicated runtime service account:

```bash
gcloud iam service-accounts create aitutor-run \
  --display-name="AI Tutor Cloud Run runtime"

export RUNTIME_SA="aitutor-run@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in roles/cloudsql.client roles/aiplatform.user roles/secretmanager.secretAccessor
do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="$ROLE"
done
```

Do not create or download a Google service-account key. Cloud Run supplies Application Default Credentials to the container.

## 5. Create Cloud SQL in London

For a real production service, start with high availability. The following is a sensible baseline, not a final capacity estimate for one million users:

```bash
gcloud sql instances create "$SQL_INSTANCE" \
  --database-version=POSTGRES_17 \
  --region="$REGION" \
  --tier=db-custom-2-7680 \
  --availability-type=REGIONAL \
  --storage-type=SSD \
  --storage-size=50 \
  --storage-auto-increase \
  --backup \
  --enable-point-in-time-recovery \
  --deletion-protection

gcloud sql databases create "$DB_NAME" --instance="$SQL_INSTANCE"
```

Generate a URL-safe password and create the application user. Keep the terminal private and do not paste the resulting value into chat, Git, tickets, or logs.

```bash
DB_PASSWORD="$(openssl rand -hex 32)"
gcloud sql users create "$DB_USER" \
  --instance="$SQL_INSTANCE" \
  --password="$DB_PASSWORD"

INSTANCE_CONNECTION_NAME="$(gcloud sql instances describe "$SQL_INSTANCE" \
  --format='value(connectionName)')"
```

Set a separate administrator password, connect as the PostgreSQL administrator, make the application user the database owner, and enable the extensions. The administrator password must be different from the application password and must not be given to Cloud Run:

```bash
gcloud sql users set-password postgres \
  --instance="$SQL_INSTANCE" \
  --prompt-for-password
gcloud sql connect "$SQL_INSTANCE" --user=postgres --database="$DB_NAME"
```

At the `psql` prompt:

```sql
ALTER DATABASE aitutor OWNER TO aitutor_app;
GRANT CONNECT ON DATABASE aitutor TO aitutor_app;
GRANT USAGE, CREATE ON SCHEMA public TO aitutor_app;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
\dx
\q
```

Replace the literal database and user names in the SQL if you changed `DB_NAME` or `DB_USER`.

Cloud SQL supports pgvector on PostgreSQL 13 and later. See [Cloud SQL PostgreSQL extensions](https://docs.cloud.google.com/sql/docs/postgres/extensions).

Build the socket URL and save it directly to a UK-replicated secret:

```bash
DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"

gcloud secrets create aitutor-database-url \
  --replication-policy=user-managed \
  --locations="$REGION"
printf '%s' "$DATABASE_URL" | \
  gcloud secrets versions add aitutor-database-url --data-file=-

unset DB_PASSWORD DATABASE_URL
```

Create the other secrets in the same way. Enter values without echoing them:

```bash
gcloud secrets create aitutor-deepseek-key \
  --replication-policy=user-managed --locations="$REGION"
read -rsp "DeepSeek API key: " VALUE; printf '\n'
printf '%s' "$VALUE" | gcloud secrets versions add aitutor-deepseek-key --data-file=-
unset VALUE

gcloud secrets create aitutor-session-owner-secret \
  --replication-policy=user-managed --locations="$REGION"
openssl rand -hex 32 | gcloud secrets versions add aitutor-session-owner-secret --data-file=-

gcloud secrets create aitutor-password-reset-secret \
  --replication-policy=user-managed --locations="$REGION"
openssl rand -hex 32 | gcloud secrets versions add aitutor-password-reset-secret --data-file=-
```

Use explicit secret version numbers in Cloud Run rather than `latest`; update the pinned version during rotation.

## 6. Build the supplied Docker image

Run the project tests in a clean Python 3.12 environment before building:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
python -m compileall -q web_app.py src scripts test
pytest -q test/unit test/api test/integration
```

The supplied source compiles, but the attachment environment did not include pytest, so the claimed test suite was not independently rerun while preparing this guide.

Create Artifact Registry and build:

```bash
gcloud artifacts repositories create "$REPOSITORY" \
  --repository-format=docker \
  --location="$REGION" \
  --description="AI Tutor production images"

export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/web:$(date -u +%Y%m%d-%H%M%S)"
gcloud builds submit --tag "$IMAGE" .
```

Do not build until the exposed password has been removed from the source tree and history.

## 7. Deploy Cloud Run with billing disabled

For the first deploy, use the generated Cloud Run URL in `prod-env.yaml`, or map the domain first and use the final HTTPS domain. Deploy:

```bash
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="$RUNTIME_SA" \
  --execution-environment=gen2 \
  --add-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
  --env-vars-file=prod-env.yaml \
  --set-secrets="DATABASE_URL=aitutor-database-url:1,PGVECTOR_DATABASE_URL=aitutor-database-url:1,DEEPSEEK_API_KEY=aitutor-deepseek-key:1,SESSION_OWNER_SECRET=aitutor-session-owner-secret:1,PASSWORD_RESET_RATE_LIMIT_SECRET=aitutor-password-reset-secret:1" \
  --port=8080 \
  --cpu=2 \
  --memory=2Gi \
  --concurrency=8 \
  --min=1 \
  --max=10 \
  --timeout=300s \
  --cpu-boost
```

Why these values match the code:

- The Dockerfile listens on `PORT=8080` with one Uvicorn worker.
- `MAX_AI_CONCURRENCY=8` and Cloud Run concurrency 8 give one bounded request group per instance.
- One worker avoids loading the local embedding model more than once per container.
- `DB_POOL_SIZE=3` plus overflow 2 means a maximum of about five database connections per instance; with 10 instances, budget for about 50 application connections plus administration and jobs.
- One minimum instance reduces cold-start latency but incurs cost. Set it to zero in staging if cost matters more than first-request speed.

After the first service exists, obtain its URL:

```bash
SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --region="$REGION" --format='value(status.url)')"
printf '%s\n' "$SERVICE_URL"
```

If this differs from `APP_BASE_URL`, update `prod-env.yaml` and deploy another revision. For production, map your custom domain, configure DNS and wait for the managed TLS certificate, then set all three URL/origin variables to the final HTTPS origin.

## 8. Initialise and populate PostgreSQL RAG

The normal application import creates most operational tables. The RAG tables and indexes are created on first RAG access. The supplied archive contains deterministic rebuild scripts, so use Cloud Run Jobs rather than running them inside a web request.

Create a primary-homework planning job:

```bash
gcloud run jobs create aitutor-rag-primary \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$RUNTIME_SA" \
  --set-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
  --set-secrets="DATABASE_URL=aitutor-database-url:1,PGVECTOR_DATABASE_URL=aitutor-database-url:1" \
  --set-env-vars="EMBEDDING_PROVIDER=local,LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2,EMBEDDING_DIMENSION=384" \
  --command=python \
  --args=scripts/homework_generator/rebuild_all_homework.py \
  --cpu=2 --memory=4Gi --task-timeout=7200s --max-retries=0

gcloud run jobs execute aitutor-rag-primary --region="$REGION" --wait
```

Read the job log and copy the exact password-free target printed by the plan. On a socket connection it will normally resemble `postgresql://localhost/aitutor`. Then update and execute:

```bash
export CONFIRMED_TARGET="COPY_EXACT_TARGET_FROM_PLAN"
gcloud run jobs update aitutor-rag-primary \
  --region="$REGION" \
  --args="scripts/homework_generator/rebuild_all_homework.py,--execute,--confirm-target,${CONFIRMED_TARGET}"
gcloud run jobs execute aitutor-rag-primary --region="$REGION" --wait
```

Repeat for 11+:

```bash
gcloud run jobs create aitutor-rag-elevenplus \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$RUNTIME_SA" \
  --set-cloudsql-instances="$INSTANCE_CONNECTION_NAME" \
  --set-secrets="DATABASE_URL=aitutor-database-url:1,PGVECTOR_DATABASE_URL=aitutor-database-url:1" \
  --set-env-vars="EMBEDDING_PROVIDER=local,LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2,EMBEDDING_DIMENSION=384" \
  --command=python \
  --args=scripts/elevenplus/rebuild_all_elevenplus.py \
  --cpu=2 --memory=4Gi --task-timeout=7200s --max-retries=0

gcloud run jobs execute aitutor-rag-elevenplus --region="$REGION" --wait

gcloud run jobs update aitutor-rag-elevenplus \
  --region="$REGION" \
  --args="scripts/elevenplus/rebuild_all_elevenplus.py,--execute,--confirm-target,${CONFIRMED_TARGET}"
gcloud run jobs execute aitutor-rag-elevenplus --region="$REGION" --wait
```

These `--execute` runs delete and rebuild their respective collections. Run the planning phase first, make a Cloud SQL backup before rebuilding an existing production database, and never run two rebuilds against the same collection concurrently.

## 9. Verify the application before Stripe

```bash
curl -fsS "$SERVICE_URL/api/health"
curl -fsS "$SERVICE_URL/api/ready"
curl -fsS "$SERVICE_URL/api/billing/plans"

gcloud run services logs read "$SERVICE" \
  --region="$REGION" --limit=100
```

Expected results:

- `/api/health`: HTTP 200 and `status: ok`.
- `/api/ready`: HTTP 200, database `ok`, configuration `ok`.
- `/api/billing/plans`: billing disabled for the first deployment.
- No database password, API key, learner name, email, prompt or answer in logs.

Manually test these journeys on staging:

1. Parent registration, login, logout and password reset.
2. Year 1–6 homework from RAG.
3. 11+ ordinary, topic mastery and week 1 year-round homework.
4. Quick Review and confirm logs show `deepseek-v4-pro`.
5. Explain in detail and Help me improve; confirm logs show `gemini-3.6-flash` on Vertex AI.
6. Progress page, support message, account deletion and session expiry.
7. Upload limits and unsupported file types.

## 10. Stripe integration after the website is deployed

### 10.1 Configure a Stripe sandbox first

In Stripe sandbox/test mode, create exactly these three Prices because the code validates currency, amount and interval before checkout:

| Application plan | Stripe price | Type |
| --- | ---: | --- |
| `trial_5day` | GBP 0.99 | One-time |
| `homework_monthly` | GBP 4.99 | Recurring monthly |
| `elevenplus_monthly` | GBP 9.99 | Recurring monthly |

Copy the three sandbox `price_...` identifiers.

Configure the Stripe customer portal in sandbox mode. Allow customers to update payment methods, see invoices and cancel at the end of the billing period. The application creates short-lived portal sessions and returns users to `/pricing`. See Stripe’s [customer portal configuration](https://docs.stripe.com/customer-management/configure-portal) and [portal API integration](https://docs.stripe.com/customer-management/integrate-customer-portal).

Create this webhook endpoint in Stripe:

```text
https://YOUR_DOMAIN/api/billing/stripe/webhook
```

Subscribe it to exactly the events handled by the code:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `customer.subscription.paused`
- `customer.subscription.resumed`

Copy the endpoint signing secret beginning `whsec_`. Stripe signs webhook requests and recommends rotating signing secrets when necessary; see [Stripe webhooks](https://docs.stripe.com/webhooks).

Create sandbox secrets:

```bash
for SECRET in aitutor-stripe-key-test aitutor-stripe-webhook-test
do
  gcloud secrets create "$SECRET" \
    --replication-policy=user-managed --locations="$REGION"
done

read -rsp "Stripe sandbox secret key: " VALUE; printf '\n'
printf '%s' "$VALUE" | gcloud secrets versions add aitutor-stripe-key-test --data-file=-
unset VALUE

read -rsp "Stripe sandbox webhook secret: " VALUE; printf '\n'
printf '%s' "$VALUE" | gcloud secrets versions add aitutor-stripe-webhook-test --data-file=-
unset VALUE
```

Update the service. Replace all three example Price IDs:

```bash
gcloud run services update "$SERVICE" \
  --region="$REGION" \
  --update-env-vars="STRIPE_BILLING_ENABLED=true,STRIPE_EXPECTED_LIVEMODE=false,STRIPE_PRICE_TRIAL_5DAY=price_TEST_TRIAL,STRIPE_PRICE_HOMEWORK_MONTHLY=price_TEST_HOMEWORK,STRIPE_PRICE_ELEVENPLUS_MONTHLY=price_TEST_ELEVENPLUS" \
  --update-secrets="STRIPE_SECRET_KEY=aitutor-stripe-key-test:1,STRIPE_WEBHOOK_SECRET=aitutor-stripe-webhook-test:1"
```

Verify `/api/billing/plans` reports `checkout_ready: true`. Register a fresh parent test account and complete each checkout. Use Stripe test card `4242 4242 4242 4242`, a future expiry and any three-digit CVC. Do not use a real card in test mode. See [Stripe test cards](https://docs.stripe.com/testing).

Confirm all of the following:

- Successful checkout returns to `/pricing?checkout=success`.
- The webhook shows HTTP 2xx in Stripe Workbench.
- Premium access is not granted before a verified webhook.
- The £0.99 trial lasts five days and cannot be bought twice by the same account.
- Monthly access is granted, cancellation is reflected, and replaying an event is idempotent.
- “Manage billing” opens one portal session after the duplicate-call bug is fixed.

### 10.2 Switch to Stripe live mode

1. Activate and verify the Stripe business account; complete public business details, support details, bank account, statement descriptor, branding, refund policy and terms.
2. Have an accountant confirm UK VAT/tax treatment and invoice settings.
3. Recreate the three products/prices in live mode. Test Price IDs cannot be used in live mode.
4. Configure and activate the live customer portal separately.
5. Create the live webhook endpoint and subscribe to the same events. Its signing secret is different from the sandbox secret.
6. Create new Secret Manager secrets for the live key and live webhook secret. Do not overwrite the sandbox secrets; retaining separate identities makes rollback safer.
7. Deploy a new Cloud Run revision with the three live Price IDs, live secrets, `STRIPE_BILLING_ENABLED=true` and `STRIPE_EXPECTED_LIVEMODE=true`.
8. Verify `/api/billing/plans` reports live mode and checkout ready.
9. Make one small real purchase with an authorised business test account, verify the webhook and entitlement, then refund it in Stripe. Never use Stripe test card numbers in live mode.

The application refuses checkout when a Price is inactive, in the wrong mode, not GBP, or has the wrong amount/interval. That is a useful launch guard; do not disable it.

## 11. Monitoring, scaling and rollback

Create alerts for Cloud Run 5xx responses, instance saturation, request latency, Cloud SQL CPU/storage/connections, failed Stripe webhooks and LLM provider errors. Set Google Cloud budget alerts and separate DeepSeek/Vertex usage alerts.

Before increasing Cloud Run `--max`, recalculate database connections:

```text
maximum approximate app connections = max instances × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

The in-process login/rate limiter is per instance. Before large-scale promotion, add a shared Redis-backed limiter or edge protection such as Cloud Armor through an external HTTPS load balancer. Load-test staging with representative RAG and AI latency; do not load-test Stripe’s production API.

Rollback application traffic without changing the database:

```bash
gcloud run revisions list --service="$SERVICE" --region="$REGION"
gcloud run services update-traffic "$SERVICE" \
  --region="$REGION" \
  --to-revisions="KNOWN_GOOD_REVISION=100"
```

Do not roll back across an incompatible schema change. Take an on-demand Cloud SQL backup before every migration or RAG rebuild.

## 12. Zero-downtime database password rotation

Because Cloud SQL password changes take effect immediately, do not change the password of the user currently serving traffic. Use a second user:

1. Create `aitutor_app_v2` with a new random hex password.
2. Grant it the same database/schema/table/sequence privileges as the current app user.
3. Build a new socket `DATABASE_URL` and add it as a new Secret Manager version.
4. Deploy a Cloud Run revision pinned to that secret version.
5. Verify health, readiness, login, RAG, progress and Stripe webhook processing.
6. Shift 100% traffic to the new revision.
7. Revoke and delete the old database user after the rollback window.

This avoids the outage window created by changing the only active user’s password.

## Final go-live checklist

- [ ] Hard-coded database password removed and rotated.
- [ ] Duplicate Stripe portal call fixed.
- [ ] Test suite passes from a clean install.
- [ ] Cloud Run and Cloud SQL are in `europe-west2`.
- [ ] Actual Gemini endpoint location and DeepSeek international transfer are documented in the DPIA/TRA.
- [ ] No production secret exists in `.env`, Git, image layers or command logs.
- [ ] `/api/health` and `/api/ready` pass.
- [ ] Primary and 11+ RAG counts are complete.
- [ ] Quick and detailed model routing is verified.
- [ ] Stripe sandbox journey passes before live keys are added.
- [ ] Live Stripe Price IDs, webhook mode and portal are verified.
- [ ] Privacy notice contains the real controller, contact and postal address.
- [ ] Backups, point-in-time recovery, monitoring, budgets and rollback are tested.
