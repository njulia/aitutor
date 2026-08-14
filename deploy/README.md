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
Manager entries use different names. For code-only deployments, override
`DEEPSEEK_API_KEY_SECRET` or `SMTP_PASSWORD_SECRET`, or use
`--deepseek-secret` and `--smtp-password-secret`, when those entries use
different names.

### Repair missing DeepSeek or SMTP secrets

Cloud Run validates every referenced secret when it creates a revision. If
either `aitutor-deepseek-api-key` or `aitutor-smtp-password` was deleted, first
check whether the value already exists under a different name:

```bash
gcloud secrets list \
  --project="aitutor-502921" \
  --format="table(name)"
```

If both values exist under different names, rebind them without copying or
printing their contents:

```bash
./deploy/deploy_code_gcp.sh --yes \
  --deepseek-secret="EXISTING_DEEPSEEK_SECRET_NAME" \
  --smtp-password-secret="EXISTING_SMTP_SECRET_NAME"
```

If they are genuinely missing, enter the real DeepSeek API key and Brevo SMTP
password using hidden terminal prompts. This keeps both values out of shell
history:

```bash
PROJECT_ID="aitutor-502921"

read -r -s -p "DeepSeek API key: " DEEPSEEK_SECRET_VALUE
printf '\n'
if gcloud secrets describe aitutor-deepseek-api-key \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  printf '%s' "${DEEPSEEK_SECRET_VALUE}" |
    gcloud secrets versions add aitutor-deepseek-api-key \
      --project="${PROJECT_ID}" \
      --data-file=-
else
  printf '%s' "${DEEPSEEK_SECRET_VALUE}" |
    gcloud secrets create aitutor-deepseek-api-key \
      --project="${PROJECT_ID}" \
      --replication-policy=automatic \
      --data-file=-
fi
unset DEEPSEEK_SECRET_VALUE

read -r -s -p "Brevo SMTP password: " SMTP_SECRET_VALUE
printf '\n'
if gcloud secrets describe aitutor-smtp-password \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  printf '%s' "${SMTP_SECRET_VALUE}" |
    gcloud secrets versions add aitutor-smtp-password \
      --project="${PROJECT_ID}" \
      --data-file=-
else
  printf '%s' "${SMTP_SECRET_VALUE}" |
    gcloud secrets create aitutor-smtp-password \
      --project="${PROJECT_ID}" \
      --replication-policy=automatic \
      --data-file=-
fi
unset SMTP_SECRET_VALUE

./deploy/deploy_code_gcp.sh --yes
```

The code deployment now checks both secrets and their enabled versions before
building, grants the runtime service account access, and reapplies their Cloud
Run bindings. It never reads or prints either value.

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

`DATA_CONTROLLER_NAME` must be the real person or registered organisation
operating Homework Magic. `PRIVACY_POSTAL_ADDRESS` must be an address at which
the operator can be contacted; do not invent these values. The application
will not start in production when either value is missing, and the staging
release checks reject hidden placeholders or an unsupported “50% off” claim.

The signed-in pricing page refreshes the linked Stripe customer before showing
the current plan. This repairs a delayed or missed local webhook record without
putting Stripe calls on learning-request paths. The prominent cancellation
entry opens Stripe's hosted `subscription_cancel` flow. On first use, the
application reuses or creates a Homework Magic portal configuration that
enables end-of-period cancellation. If you manage that configuration manually,
set its public `bpc_...` identifier as `STRIPE_PORTAL_CONFIGURATION_ID`.

Keep the webhook endpoint subscribed to Checkout completion and customer
subscription create, update and delete events. The refresh is a recovery path,
not a replacement for normal webhook materialisation.

## Optional parent beta

The invite-only Year 3 parent beta is disabled by default. It needs no card,
does not renew, unlocks Year 1–6 learning only, never earns Gift Points and is
hard-capped in code at 15 family accounts.

Generate one strong code, store it without printing or committing it, then add
the secret binding when deploying:

```bash
openssl rand -base64 24 \
  | gcloud secrets create homeworkmagic-beta-access-code \
      --project="aitutor-502921" \
      --replication-policy="automatic" \
      --data-file=-

export BETA_ACCESS_CODE_SECRET="homeworkmagic-beta-access-code"
```

Set `BETA_ACCESS_ENABLED: "true"` in the private
`deploy/cloud-run.env.yaml` file only after the secret binding is ready. Share
the code privately with invited parents; never put it in a public webpage,
email campaign URL or source file. The beta page is `/beta` and the five
question parent form is `/beta-feedback`.

The optional first-party marketing counters are aggregate-only. The
`/api/admin/marketing-summary` endpoint returns daily counts and does not store
account, learner, email, cookie, IP, homework, answer, score, school or
free-text fields.

## 4. Deploy

Authenticate `gcloud`, select a deployer identity with permission to build and
deploy. The 11+ mock catalogue is included in the existing £9.99 11+ Premium
plan; verify that plan by following
[`SETUP_11PLUS_MOCK_TIER.md`](SETUP_11PLUS_MOCK_TIER.md), then run:

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

For the reviewed Cloud Run job workflow, use:

```bash
./deploy/deploy_rag_gcp.sh --plan-only
./deploy/deploy_rag_gcp.sh
```


### AI review model

Production detail explanations are deployed with Vertex AI using:

```text
DETAIL_REVIEW_PROVIDER: vertex_ai
DETAIL_REVIEW_MODEL: gemini-3.6-flash
```

Both `deploy_gcp.sh` and `deploy_code_gcp.sh` enforce these values on every
application deployment. This prevents an older Cloud Run value such as
`DETAIL_REVIEW_MODEL=gemini-2.5-flash` from returning in a new revision.
For a deliberate test override, use `DETAIL_REVIEW_MODEL` in the shell or
`--detail-review-model MODEL` with `deploy_code_gcp.sh`.
