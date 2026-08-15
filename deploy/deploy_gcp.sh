#!/usr/bin/env bash
set -euo pipefail

GCP_PROJECT_ID="${GCP_PROJECT_ID:-aitutor-502921}"
GCP_REGION="${GCP_REGION:-europe-west2}"
GCP_SERVICE="${GCP_SERVICE:-aitutor-prod}"
GCP_REPOSITORY="${GCP_REPOSITORY:-aitutor-repo}"
GCP_SQL_INSTANCE="${GCP_SQL_INSTANCE:-aitutor-prod-pg}"
GCP_SERVICE_ACCOUNT="${GCP_SERVICE_ACCOUNT:-aitutor-run@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"
DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-deploy/cloud-run.env.yaml}"
STRIPE_SECRET_KEY_SECRET="${STRIPE_SECRET_KEY_SECRET:-homeworkmagic-stripe-secret-key}"
STRIPE_WEBHOOK_SECRET_SECRET="${STRIPE_WEBHOOK_SECRET_SECRET:-homeworkmagic-stripe-webhook-secret}"
REWARD_DELIVERY_SECRET_SECRET="${REWARD_DELIVERY_SECRET_SECRET:-homeworkmagic-reward-delivery-secret}"
BETA_ACCESS_CODE_SECRET="${BETA_ACCESS_CODE_SECRET:-}"
DEFAULT_SECRET_BINDINGS="DATABASE_URL=aitutor-database-url:latest,SESSION_OWNER_SECRET=aitutor-session-owner-secret:latest,DEEPSEEK_API_KEY=aitutor-deepseek-api-key:latest,SMTP_PASSWORD=aitutor-smtp-password:latest,STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY_SECRET}:latest,STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET_SECRET}:latest,REWARD_DELIVERY_SECRET=${REWARD_DELIVERY_SECRET_SECRET}:latest"
SECRET_BINDINGS="${SECRET_BINDINGS:-${DEFAULT_SECRET_BINDINGS}}"
if [[ -n "${BETA_ACCESS_CODE_SECRET}" && ",${SECRET_BINDINGS}," != *",BETA_ACCESS_CODE="* ]]; then
  SECRET_BINDINGS="${SECRET_BINDINGS},BETA_ACCESS_CODE=${BETA_ACCESS_CODE_SECRET}:latest"
fi
CLOUD_RUN_CONCURRENCY="${CLOUD_RUN_CONCURRENCY:-25}"
CLOUD_RUN_MIN_INSTANCES="${CLOUD_RUN_MIN_INSTANCES:-2}"
CLOUD_RUN_MAX_INSTANCES="${CLOUD_RUN_MAX_INSTANCES:-60}"
CLOUD_RUN_CPU="${CLOUD_RUN_CPU:-2}"
CLOUD_RUN_MEMORY="${CLOUD_RUN_MEMORY:-4Gi}"
BILLING_HEALTH_URL="${BILLING_HEALTH_URL:-https://homeworkmagic.co.uk/api/billing/plans}"

# Production AI routing. These values are enforced on every full deployment.
QUICK_REVIEW_PROVIDER="${QUICK_REVIEW_PROVIDER:-deepseek}"
QUICK_REVIEW_MODEL="${QUICK_REVIEW_MODEL:-deepseek-v4-flash}"
DETAIL_REVIEW_PROVIDER="${DETAIL_REVIEW_PROVIDER:-deepseek}"
DETAIL_REVIEW_MODEL="${DETAIL_REVIEW_MODEL:-deepseek-v4-flash}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REWARD_SECRET_HELPER="${SCRIPT_DIR}/ensure_reward_delivery_secret.sh"

if [[ ! -f "${REWARD_SECRET_HELPER}" ]]; then
  echo "Reward delivery helper not found: ${REWARD_SECRET_HELPER}" >&2
  exit 2
fi
# shellcheck source=deploy/ensure_reward_delivery_secret.sh
source "${REWARD_SECRET_HELPER}"

if [[ ! -f "${DEPLOY_ENV_FILE}" ]]; then
  echo "Create ${DEPLOY_ENV_FILE} from deploy/cloud-run.env.yaml.example first." >&2
  exit 2
fi

# --env-vars-file is authoritative in Cloud Run. Create an effective temporary
# copy with the production AI routing enforced, so an older value in the
# operator's private env file cannot reappear in the next revision.
DEPLOY_ENV_FILE_EFFECTIVE="${DEPLOY_ENV_FILE}"
DEPLOY_ENV_TMP="$(mktemp "${TMPDIR:-/tmp}/homeworkmagic-env.XXXXXX.yaml")"
trap 'rm -f "${DEPLOY_ENV_TMP}"' EXIT

python3 - "${DEPLOY_ENV_FILE}" "${DEPLOY_ENV_TMP}" "${QUICK_REVIEW_PROVIDER}" "${QUICK_REVIEW_MODEL}" "${DETAIL_REVIEW_PROVIDER}" "${DETAIL_REVIEW_MODEL}" <<'PY'
import pathlib
import re
import sys

source, destination, quick_provider, quick_model, detail_provider, detail_model = sys.argv[1:]
text = pathlib.Path(source).read_text(encoding="utf-8")

def upsert(text, key, value):
    pattern = re.compile(rf"(?m)^{re.escape(key)}:[^\n]*$")
    line = f"{key}: {value}"
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"

text = upsert(text, "QUICK_REVIEW_PROVIDER", quick_provider)
text = upsert(text, "QUICK_REVIEW_MODEL", quick_model)
text = upsert(text, "DETAIL_REVIEW_PROVIDER", detail_provider)
text = upsert(text, "DETAIL_REVIEW_MODEL", detail_model)
pathlib.Path(destination).write_text(text, encoding="utf-8")
PY
DEPLOY_ENV_FILE_EFFECTIVE="${DEPLOY_ENV_TMP}"
if grep -Eq ':[[:space:]]*["'"'"']?REPLACE_' "${DEPLOY_ENV_FILE_EFFECTIVE}"; then
  echo "${DEPLOY_ENV_FILE} still contains placeholder values." >&2
  exit 2
fi

required_public_settings=(
  APP_BASE_URL
  CORS_ORIGINS
  ADMIN_EMAILS
  DATA_CONTROLLER_NAME
  PRIVACY_CONTACT_EMAIL
  PRIVACY_POSTAL_ADDRESS
  BUSINESS_CONTACT_EMAIL
)
for setting in "${required_public_settings[@]}"; do
  if ! grep -Eq "^${setting}:[[:space:]]*[\"']?[^\"'[:space:]][^\"']*[\"']?[[:space:]]*$" "${DEPLOY_ENV_FILE_EFFECTIVE}"; then
    echo "${DEPLOY_ENV_FILE} must contain a non-empty ${setting} value." >&2
    exit 2
  fi
done

required_billing_settings=(
  STRIPE_BILLING_ENABLED
  STRIPE_EXPECTED_LIVEMODE
  STRIPE_PRICE_TRIAL_5DAY
  STRIPE_PRICE_HOMEWORK_MONTHLY
  STRIPE_PRICE_ELEVENPLUS_MONTHLY
)
for setting in "${required_billing_settings[@]}"; do
  if ! grep -Eq "^${setting}:[[:space:]]*[\"']?[^\"'[:space:]][^\"']*[\"']?[[:space:]]*$" "${DEPLOY_ENV_FILE_EFFECTIVE}"; then
    echo "${DEPLOY_ENV_FILE} must contain a non-empty ${setting} value." >&2
    exit 2
  fi
done

if grep -Eq '^BETA_ACCESS_ENABLED:[[:space:]]*["'"'"']?(true|1|yes|on)["'"'"']?[[:space:]]*$' "${DEPLOY_ENV_FILE_EFFECTIVE}"; then
  if [[ ",${SECRET_BINDINGS}," != *",BETA_ACCESS_CODE="* ]]; then
    echo "BETA_ACCESS_ENABLED is true, but SECRET_BINDINGS does not bind BETA_ACCESS_CODE." >&2
    echo "Store the invite code in Secret Manager and add BETA_ACCESS_CODE=SECRET_NAME:latest." >&2
    exit 2
  fi
fi

gcloud config set project "${GCP_PROJECT_ID}"
for required_secret in \
  "${STRIPE_SECRET_KEY_SECRET}" \
  "${STRIPE_WEBHOOK_SECRET_SECRET}"; do
  if ! gcloud secrets describe "${required_secret}" \
    --project "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo "Secret Manager secret ${required_secret} does not exist or is not accessible." >&2
    echo "Create it before deploying, or override its *_SECRET variable." >&2
    exit 2
  fi
done
if [[ -n "${BETA_ACCESS_CODE_SECRET}" ]] && ! gcloud secrets describe \
  "${BETA_ACCESS_CODE_SECRET}" \
  --project "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
  echo "Secret Manager secret ${BETA_ACCESS_CODE_SECRET} does not exist or is not accessible." >&2
  exit 2
fi

ensure_reward_delivery_secret \
  "${GCP_PROJECT_ID}" \
  "${REWARD_DELIVERY_SECRET_SECRET}" \
  "${GCP_SERVICE_ACCOUNT}"

gcloud artifacts repositories describe "${GCP_REPOSITORY}" \
  --location "${GCP_REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${GCP_REPOSITORY}" \
       --repository-format docker \
       --location "${GCP_REGION}" \
       --description "Homework Magic production images"

IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_REPOSITORY}/${GCP_SERVICE}:$(date -u +%Y%m%d-%H%M%S)"
gcloud builds submit --tag "${IMAGE}" .

gcloud run deploy "${GCP_SERVICE}" \
  --image "${IMAGE}" \
  --region "${GCP_REGION}" \
  --platform managed \
  --service-account "${GCP_SERVICE_ACCOUNT}" \
  --add-cloudsql-instances "${GCP_PROJECT_ID}:${GCP_REGION}:${GCP_SQL_INSTANCE}" \
  --env-vars-file "${DEPLOY_ENV_FILE_EFFECTIVE}" \
  --update-secrets "${SECRET_BINDINGS}" \
  --allow-unauthenticated \
  --port 8080 \
  --cpu "${CLOUD_RUN_CPU}" \
  --memory "${CLOUD_RUN_MEMORY}" \
  --concurrency "${CLOUD_RUN_CONCURRENCY}" \
  --min-instances "${CLOUD_RUN_MIN_INSTANCES}" \
  --max-instances "${CLOUD_RUN_MAX_INSTANCES}" \
  --execution-environment gen2 \
  --timeout 180 \
  --cpu-boost

echo "Deployed ${IMAGE}"
echo "Configured request capacity: $((CLOUD_RUN_CONCURRENCY * CLOUD_RUN_MAX_INSTANCES)) concurrent requests"

if command -v curl >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  if ! curl --fail --silent --show-error --max-time 30 "${BILLING_HEALTH_URL}" \
    | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
availability = payload.get("plan_availability") or {}
required = ("trial_5day", "homework_monthly", "elevenplus_monthly")
missing = [plan for plan in required if availability.get(plan) is not True]
if payload.get("enabled") is not True or missing:
    print(
        "Stripe checkout is not ready for: " + ", ".join(missing or required),
        file=sys.stderr,
    )
    raise SystemExit(1)
print("Stripe checkout configuration is ready for all public plans.")
'; then
    echo "Deployment succeeded, but Stripe checkout is not ready." >&2
    echo "Run deploy/repair_stripe_checkout_gcp.sh after checking the live Price IDs." >&2
    exit 3
  fi
else
  echo "Verify ${BILLING_HEALTH_URL} after deployment (curl and python3 were not both available)."
fi
