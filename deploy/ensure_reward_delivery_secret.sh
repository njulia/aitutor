#!/usr/bin/env bash
#
# Create and validate the stable Secret Manager value used to encrypt adult
# delivery addresses, then grant the Cloud Run runtime service account access.
# The secret value is never printed.

set -Eeuo pipefail

ensure_reward_delivery_secret() {
  reward_project_id="$1"
  reward_secret_name="$2"
  reward_service_account="$3"

  command -v gcloud >/dev/null 2>&1 || {
    printf 'ERROR: Required command not found: gcloud\n' >&2
    return 1
  }
  command -v python3 >/dev/null 2>&1 || {
    printf 'ERROR: Required command not found: python3\n' >&2
    return 1
  }

  if ! gcloud secrets describe "${reward_secret_name}" \
    --project="${reward_project_id}" >/dev/null 2>&1; then
    printf 'Creating Secret Manager secret %s.\n' "${reward_secret_name}"
    python3 -c \
      'import secrets, sys; sys.stdout.write(secrets.token_urlsafe(48))' |
      gcloud secrets create "${reward_secret_name}" \
        --project="${reward_project_id}" \
        --replication-policy=automatic \
        --data-file=- \
        --quiet >/dev/null
  fi

  reward_enabled_version="$(
    gcloud secrets versions list "${reward_secret_name}" \
      --project="${reward_project_id}" \
      --filter="state=ENABLED" \
      --sort-by="~createTime" \
      --limit=1 \
      --format="value(name)"
  )"
  if [ -z "${reward_enabled_version}" ]; then
    printf 'Adding the first enabled version to %s.\n' "${reward_secret_name}"
    python3 -c \
      'import secrets, sys; sys.stdout.write(secrets.token_urlsafe(48))' |
      gcloud secrets versions add "${reward_secret_name}" \
        --project="${reward_project_id}" \
        --data-file=- \
        --quiet >/dev/null
  fi

  if ! reward_secret_length="$(
    gcloud secrets versions access latest \
      --secret="${reward_secret_name}" \
      --project="${reward_project_id}" 2>/dev/null |
      python3 -c 'import sys; print(len(sys.stdin.read().strip()))'
  )"; then
    printf 'ERROR: Unable to validate %s without exposing it.\n' \
      "${reward_secret_name}" >&2
    printf 'Grant the active gcloud account access to this secret and retry.\n' >&2
    return 1
  fi

  case "${reward_secret_length}" in
    ''|*[!0-9]*)
      printf 'ERROR: Could not validate the reward-delivery secret length.\n' >&2
      return 1
      ;;
  esac
  if [ "${reward_secret_length}" -lt 32 ]; then
    printf 'The existing reward-delivery value is too short; adding a safe version.\n'
    python3 -c \
      'import secrets, sys; sys.stdout.write(secrets.token_urlsafe(48))' |
      gcloud secrets versions add "${reward_secret_name}" \
        --project="${reward_project_id}" \
        --data-file=- \
        --quiet >/dev/null
  fi

  gcloud secrets add-iam-policy-binding "${reward_secret_name}" \
    --project="${reward_project_id}" \
    --member="serviceAccount:${reward_service_account}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null

  printf 'Reward delivery encryption is configured for the Cloud Run service account.\n'
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  PROJECT_ID="${PROJECT_ID:-aitutor-502921}"
  REWARD_DELIVERY_SECRET_SECRET="${REWARD_DELIVERY_SECRET_SECRET:-homeworkmagic-reward-delivery-secret}"
  SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_EMAIL:-aitutor-run@${PROJECT_ID}.iam.gserviceaccount.com}"
  ensure_reward_delivery_secret \
    "${PROJECT_ID}" \
    "${REWARD_DELIVERY_SECRET_SECRET}" \
    "${SERVICE_ACCOUNT_EMAIL}"
fi
