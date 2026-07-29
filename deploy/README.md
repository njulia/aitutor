# Google Cloud deployment

This directory contains a production-oriented Cloud Run configuration for
Homework Magic. The deployment uses Cloud Build, Artifact Registry, Cloud Run,
Cloud SQL for PostgreSQL/pgvector, Secret Manager, Vertex AI and DeepSeek.

## 1. Prepare Google Cloud

Create the `aitutor-run@aitutor-502921.iam.gserviceaccount.com` service account
and grant it:

- Cloud SQL Client
- Secret Manager Secret Accessor for the secrets listed below
- Vertex AI User

Create the PostgreSQL database and enable the `vector` extension before
ingesting the RAG resources. The default Cloud SQL connection name is:

```text
aitutor-502921:europe-west2:aitutor-prod-pg
```

Google's reference documentation covers
[Cloud Run environment variables](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables),
[Secret Manager integration](https://docs.cloud.google.com/run/docs/configuring/services/secrets),
and [connecting Cloud Run to Cloud SQL](https://docs.cloud.google.com/sql/docs/postgres/connect-run).

## 2. Add production secrets

Create these Secret Manager secrets:

- `aitutor-database-url`
- `aitutor-session-owner-secret`
- `aitutor-deepseek-api-key`
- `aitutor-smtp-password`
- `homeworkmagic-stripe-secret-key`
- `homeworkmagic-stripe-webhook-secret`
- `homeworkmagic-reward-delivery-secret`

The database secret should contain a SQLAlchemy URL using the Cloud SQL Unix
socket. URL-encode the password:

```text
postgresql+psycopg://aitutor_app:PASSWORD@/aitutor?host=/cloudsql/aitutor-502921:europe-west2:aitutor-prod-pg
```

Generate `SESSION_OWNER_SECRET` with at least 32 random characters. Do not put
secret values in `cloud-run.env.yaml`. The Stripe secrets must contain the live
`sk_live_...` key and the `whsec_...` signing secret for
`https://homeworkmagic.co.uk/api/billing/stripe/webhook`. Override
`STRIPE_SECRET_KEY_SECRET` or `STRIPE_WEBHOOK_SECRET_SECRET` when your Secret
Manager entries use different names.

The reward-delivery secret encrypts adult postal addresses for branded gift
orders. The deployment scripts now create a strong value when the secret is
missing, validate that it contains at least 32 characters without printing it,
grant the runtime service account access, and preserve the same value across
later revisions.

To repair an existing service that reports
`REWARD_DELIVERY_SECRET must contain at least 32 characters`, run:

```bash
bash deploy/ensure_reward_delivery_secret.sh
./deploy/deploy_code_gcp.sh
```

You can also create the value manually. Generate it once, keep it stable across
revisions, and never print or commit it:

```bash
openssl rand -base64 48 \
  | gcloud secrets create homeworkmagic-reward-delivery-secret \
      --project="aitutor-502921" \
      --replication-policy="automatic" \
      --data-file=-
```

If that secret already exists, add a version instead of creating it again:

```bash
openssl rand -base64 48 \
  | gcloud secrets versions add homeworkmagic-reward-delivery-secret \
      --project="aitutor-502921" \
      --data-file=-
```

Changing this value later prevents old unfulfilled delivery addresses from
being decrypted, so rotate it only with a planned data migration. Override
`REWARD_DELIVERY_SECRET_SECRET` if a different Secret Manager name is used.

## 3. Configure non-secret values

```bash
cp deploy/cloud-run.env.yaml.example deploy/cloud-run.env.yaml
```

Replace every `REPLACE_...` entry with the legal operator and SMTP details.
Also copy the three live Stripe `price_...` identifiers into their matching
`STRIPE_PRICE_...` fields. A Product ID (`prod_...`) or Pricing Table ID
(`prctbl_...`) will not work. The real file is ignored by Git and Docker.

## 4. Deploy

Authenticate `gcloud`, select a deployer identity with permission to build and
deploy, then run:

```bash
./deploy/deploy_gcp.sh
```

The script creates the Artifact Registry repository if necessary, builds an
immutable timestamped image, and deploys it to Cloud Run in `europe-west2`.
Override any `GCP_*`, `DEPLOY_ENV_FILE`, or `SECRET_BINDINGS` environment
variable when deploying to a different project or topology. The environment
file is authoritative because Cloud Run replaces existing ordinary environment
variables when `--env-vars-file` is used. The deploy script therefore validates
the Stripe values before building and retains existing secret mappings with
`--update-secrets`.

## Repair checkout after an earlier deployment

If the pricing page says secure checkout is temporarily unavailable after an
older deployment, export the three live Price IDs and run the repair script.
The supplied live Pricing Table ID and publishable key are built into the
script as non-secret defaults. It updates only the Stripe settings on the
current `aitutor-prod` service:

```bash
export STRIPE_PRICE_TRIAL_5DAY="price_..."
export STRIPE_PRICE_HOMEWORK_MONTHLY="price_..."
export STRIPE_PRICE_ELEVENPLUS_MONTHLY="price_..."
bash deploy/repair_stripe_checkout_gcp.sh
```

The script verifies both Secret Manager entries, grants the Cloud Run service
account access, deploys a new configuration-only revision, and checks the safe
public `/api/billing/plans` readiness response. It never prints either Stripe
secret.

The default service capacity is 25 concurrent requests per instance, 2 warm
instances and up to 60 instances (1,500 request slots and up to 1,200 admitted
AI calls). Each instance uses one shared, bounded Cloud SQL pool. These limits
protect the database and AI providers while Cloud Run scales out.
Override `CLOUD_RUN_CONCURRENCY`, `CLOUD_RUN_MIN_INSTANCES` and
`CLOUD_RUN_MAX_INSTANCES` only after load testing and checking Cloud SQL,
Vertex AI and DeepSeek quotas.

For cross-instance response caching, set `REDIS_URL` to a managed private Redis
endpoint. The application safely falls back to per-instance caches when Redis
is not configured, but repeated requests landing on different instances will
then make separate AI calls.

## 5. Initialise and ingest

After the first deployment, initialise the shared schema and ingest the
curated homework and 11+ resources against the production database:

```bash
DATABASE_URL='postgresql+psycopg://...' python scripts/gcp_utils.py
DATABASE_URL='postgresql+psycopg://...' python scripts/homework_generator/rebuild_all_homework.py
DATABASE_URL='postgresql+psycopg://...' python scripts/elevenplus/rebuild_all_elevenplus.py
```

Run these from a secured administrative environment; never place the database
URL in shell history or logs.
