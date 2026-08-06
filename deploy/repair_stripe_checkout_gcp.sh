#!/usr/bin/env bash
set -euo pipefail

# Repair Stripe variables that an earlier --env-vars-file/--set-secrets deploy
# removed. Export the Price IDs currently used by the live Pricing Table before
# running this script. They are deliberately not hard-coded because editing a
# Pricing Table can create new Price IDs while an old ID remains valid in
# Stripe. Key material remains in Google Secret Manager.

GCP_PROJECT_ID="${GCP_PROJECT_ID:-${PROJECT_ID:-aitutor-502921}}"
GCP_REGION="${GCP_REGION:-${REGION:-europe-west2}}"
GCP_SERVICE="${GCP_SERVICE:-${SERVICE:-aitutor-prod}}"
GCP_SERVICE_ACCOUNT="${GCP_SERVICE_ACCOUNT:-aitutor-run@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"
STRIPE_SECRET_KEY_SECRET="${STRIPE_SECRET_KEY_SECRET:-homeworkmagic-stripe-secret-key}"
STRIPE_WEBHOOK_SECRET_SECRET="${STRIPE_WEBHOOK_SECRET_SECRET:-homeworkmagic-stripe-webhook-secret}"
STRIPE_PRICING_TABLE_ID="${STRIPE_PRICING_TABLE_ID:-}"
STRIPE_PUBLISHABLE_KEY="${STRIPE_PUBLISHABLE_KEY:-}"
BILLING_HEALTH_URL="${BILLING_HEALTH_URL:-https://homeworkmagic.co.uk/api/billing/plans}"

for command_name in gcloud curl python3; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "${command_name} is required." >&2
    exit 2
  fi
done

required_price_variables=(
  STRIPE_PRICE_TRIAL_5DAY
  STRIPE_PRICE_HOMEWORK_MONTHLY
  STRIPE_PRICE_ELEVENPLUS_MONTHLY
)
for variable_name in "${required_price_variables[@]}"; do
  variable_value="${!variable_name:-}"
  if [[ ! "${variable_value}" =~ ^price_[A-Za-z0-9_]+$ ]]; then
    echo "Set ${variable_name} to its live Stripe Price ID (price_...), then run this script again." >&2
    exit 2
  fi
done

if [[ ! "${STRIPE_PRICING_TABLE_ID}" =~ ^prctbl_[A-Za-z0-9_]+$ ]]; then
  echo "STRIPE_PRICING_TABLE_ID must be a Stripe Pricing Table ID (prctbl_...)." >&2
  exit 2
fi
if [[ ! "${STRIPE_PUBLISHABLE_KEY}" =~ ^pk_live_[A-Za-z0-9_]+$ ]]; then
  echo "STRIPE_PUBLISHABLE_KEY must be a live Stripe publishable key (pk_live_...)." >&2
  exit 2
fi

if [[ "${STRIPE_PRICE_TRIAL_5DAY}" == "${STRIPE_PRICE_HOMEWORK_MONTHLY}" \
   || "${STRIPE_PRICE_TRIAL_5DAY}" == "${STRIPE_PRICE_ELEVENPLUS_MONTHLY}" \
   || "${STRIPE_PRICE_HOMEWORK_MONTHLY}" == "${STRIPE_PRICE_ELEVENPLUS_MONTHLY}" ]]; then
  echo "Each plan must use a different Stripe Price ID." >&2
  exit 2
fi

for secret_name in "${STRIPE_SECRET_KEY_SECRET}" "${STRIPE_WEBHOOK_SECRET_SECRET}"; do
  if ! gcloud secrets describe "${secret_name}" \
    --project "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo "Secret Manager secret ${secret_name} does not exist or is not accessible." >&2
    exit 2
  fi
  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --project "${GCP_PROJECT_ID}" \
    --member "serviceAccount:${GCP_SERVICE_ACCOUNT}" \
    --role "roles/secretmanager.secretAccessor" \
    --quiet >/dev/null
done

gcloud run services update "${GCP_SERVICE}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}" \
  --update-env-vars "STRIPE_BILLING_ENABLED=true,STRIPE_EXPECTED_LIVEMODE=true,STRIPE_PRICING_TABLE_ID=${STRIPE_PRICING_TABLE_ID},STRIPE_PUBLISHABLE_KEY=${STRIPE_PUBLISHABLE_KEY},STRIPE_PRICE_TRIAL_5DAY=${STRIPE_PRICE_TRIAL_5DAY},STRIPE_PRICE_HOMEWORK_MONTHLY=${STRIPE_PRICE_HOMEWORK_MONTHLY},STRIPE_PRICE_ELEVENPLUS_MONTHLY=${STRIPE_PRICE_ELEVENPLUS_MONTHLY}" \
  --update-secrets "STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY_SECRET}:latest,STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET_SECRET}:latest" \
  --quiet

curl --fail --silent --show-error --max-time 30 "${BILLING_HEALTH_URL}" \
  | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
availability = payload.get("plan_availability") or {}
required = ("trial_5day", "homework_monthly", "elevenplus_monthly")
missing = [plan for plan in required if availability.get(plan) is not True]
if payload.get("enabled") is not True or missing:
    print(
        "Cloud Run updated, but checkout is not ready for: "
        + ", ".join(missing or required),
        file=sys.stderr,
    )
    raise SystemExit(1)
print("Stripe checkout is ready for all public plans.")
'
