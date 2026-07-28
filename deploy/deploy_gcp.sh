#!/usr/bin/env bash
set -euo pipefail

GCP_PROJECT_ID="${GCP_PROJECT_ID:-aitutor-502921}"
GCP_REGION="${GCP_REGION:-europe-west2}"
GCP_SERVICE="${GCP_SERVICE:-aitutor-prod}"
GCP_REPOSITORY="${GCP_REPOSITORY:-aitutor-repo}"
GCP_SQL_INSTANCE="${GCP_SQL_INSTANCE:-aitutor-prod-pg}"
GCP_SERVICE_ACCOUNT="${GCP_SERVICE_ACCOUNT:-aitutor-run@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"
DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-deploy/cloud-run.env.yaml}"
SECRET_BINDINGS="${SECRET_BINDINGS:-DATABASE_URL=aitutor-database-url:latest,SESSION_OWNER_SECRET=aitutor-session-owner-secret:latest,DEEPSEEK_API_KEY=aitutor-deepseek-api-key:latest,SMTP_PASSWORD=aitutor-smtp-password:latest}"

if [[ ! -f "${DEPLOY_ENV_FILE}" ]]; then
  echo "Create ${DEPLOY_ENV_FILE} from deploy/cloud-run.env.yaml.example first." >&2
  exit 2
fi
if grep -q "REPLACE_" "${DEPLOY_ENV_FILE}"; then
  echo "${DEPLOY_ENV_FILE} still contains REPLACE_ placeholders." >&2
  exit 2
fi

gcloud config set project "${GCP_PROJECT_ID}"
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
  --env-vars-file "${DEPLOY_ENV_FILE}" \
  --set-secrets "${SECRET_BINDINGS}" \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 2 \
  --memory 4Gi \
  --concurrency 8 \
  --min-instances 0 \
  --max-instances 10 \
  --cpu-boost

echo "Deployed ${IMAGE}"
