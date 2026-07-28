#!/usr/bin/env bash
#
# Safely rebuild Homework Magic primary and 11+ RAG data in Cloud SQL.
#
# Dedicated Cloud Run jobs use the image serving 100% of production traffic by
# default. Every generator job is saved in plan-only mode. Destructive
# execution uses a one-time argument override only after the password-free
# PostgreSQL target has been read from the plan and explicitly confirmed.

set -Eeuo pipefail

PROJECT_ID="${PROJECT_ID:-aitutor-502921}"
REGION="${REGION:-europe-west2}"
SERVICE="${SERVICE:-aitutor-prod}"
SQL_INSTANCE="${SQL_INSTANCE:-aitutor-prod-pg}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_EMAIL:-aitutor-run@${PROJECT_ID}.iam.gserviceaccount.com}"
DB_SECRET="${DB_SECRET:-aitutor-database-url}"
DB_INIT_JOB="${DB_INIT_JOB:-aitutor-db-init}"
PRIMARY_RAG_JOB="${PRIMARY_RAG_JOB:-aitutor-rag-primary}"
ELEVENPLUS_RAG_JOB="${ELEVENPLUS_RAG_JOB:-aitutor-rag-elevenplus}"
JOB_TIMEOUT="${JOB_TIMEOUT:-2h}"
IMAGE="${IMAGE:-}"

SCOPE="all"
ASSUME_YES=false
PLAN_ONLY=false
RESUME=false

usage() {
  cat <<'USAGE'
Usage:
  ./deploy/deploy_rag_gcp.sh [options]

Deploys safe Cloud Run jobs, initialises the PostgreSQL/pgvector schema, prints
the generator plans, and rebuilds the selected RAG collections sequentially.

Options:
  --project ID             Google Cloud project (default: aitutor-502921)
  --region REGION          Google Cloud region (default: europe-west2)
  --service NAME           Production service used to resolve the image
  --sql-instance NAME      Cloud SQL instance (default: aitutor-prod-pg)
  --service-account EMAIL  Cloud Run job service account
  --database-secret NAME   Secret Manager DATABASE_URL secret
  --image IMAGE            Use this image instead of the production image
  --scope SCOPE            all, primary, or elevenplus (default: all)
  --timeout DURATION       Per-task timeout (default: 2h)
  --plan-only              Run read-only plans, but do not rebuild RAG data
  --resume                 Resume one failed scope without deleting it again
  --yes                    Rebuild without an interactive confirmation
  -h, --help               Show this help

Important:
  --resume requires --scope primary or --scope elevenplus. This prevents a
  successful collection from accidentally skipping its clean rebuild.

Examples:
  ./deploy/deploy_rag_gcp.sh --plan-only
  ./deploy/deploy_rag_gcp.sh
  ./deploy/deploy_rag_gcp.sh --yes
  ./deploy/deploy_rag_gcp.sh --scope elevenplus --resume
USAGE
}

log() {
  printf '\n==> %s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      [ "$#" -ge 2 ] || die "--project requires a value"
      PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      [ "$#" -ge 2 ] || die "--region requires a value"
      REGION="$2"
      shift 2
      ;;
    --service)
      [ "$#" -ge 2 ] || die "--service requires a value"
      SERVICE="$2"
      shift 2
      ;;
    --sql-instance)
      [ "$#" -ge 2 ] || die "--sql-instance requires a value"
      SQL_INSTANCE="$2"
      shift 2
      ;;
    --service-account)
      [ "$#" -ge 2 ] || die "--service-account requires a value"
      SERVICE_ACCOUNT_EMAIL="$2"
      shift 2
      ;;
    --database-secret)
      [ "$#" -ge 2 ] || die "--database-secret requires a value"
      DB_SECRET="$2"
      shift 2
      ;;
    --image)
      [ "$#" -ge 2 ] || die "--image requires a value"
      IMAGE="$2"
      shift 2
      ;;
    --scope)
      [ "$#" -ge 2 ] || die "--scope requires a value"
      SCOPE="$2"
      shift 2
      ;;
    --timeout)
      [ "$#" -ge 2 ] || die "--timeout requires a value"
      JOB_TIMEOUT="$2"
      shift 2
      ;;
    --plan-only)
      PLAN_ONLY=true
      shift
      ;;
    --resume)
      RESUME=true
      shift
      ;;
    --yes)
      ASSUME_YES=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

case "${SCOPE}" in
  all|primary|elevenplus)
    ;;
  *)
    die "--scope must be all, primary, or elevenplus"
    ;;
esac

if [ "${RESUME}" = true ] && [ "${SCOPE}" = "all" ]; then
  die "--resume requires --scope primary or --scope elevenplus"
fi

CONNECTION_NAME="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
JOB_ENV_VARS="TOKENIZERS_PARALLELISM=false,EMBEDDING_PROVIDER=local,LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2,EMBEDDING_DIMENSION=384,CORS_ORIGINS=https://homeworkmagic.co.uk"

require_command gcloud
require_command python3

RAG_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/homeworkmagic-rag-deploy.XXXXXX")"
cleanup() {
  if [ -n "${RAG_TMP_DIR:-}" ] && [ -d "${RAG_TMP_DIR}" ]; then
    rm -rf "${RAG_TMP_DIR}"
  fi
}
trap cleanup EXIT

extract_live_revision() {
  gcloud run services describe "${SERVICE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format=json |
  python3 -c '
import json
import sys

traffic = json.load(sys.stdin).get("status", {}).get("traffic", [])
matches = [
    item.get("revisionName")
    for item in traffic
    if int(item.get("percent") or 0) == 100 and item.get("revisionName")
]
if len(matches) == 1:
    print(matches[0])
'
}

latest_execution() {
  job_name="$1"
  gcloud run jobs executions describe-latest \
    --job="${job_name}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format="value(metadata.name)" 2>/dev/null || true
}

fetch_job_logs() {
  job_name="$1"
  execution_name="$2"
  expected_text="$3"
  destination="$4"
  attempt=1

  : > "${destination}"
  while [ "${attempt}" -le 10 ]; do
    gcloud logging read \
      "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${job_name}\" AND labels.\"run.googleapis.com/execution_name\"=\"${execution_name}\"" \
      --project="${PROJECT_ID}" \
      --order=asc \
      --limit=2000 \
      --format="value(textPayload,jsonPayload.message)" \
      > "${destination}" || true

    if [ -s "${destination}" ]; then
      if [ -z "${expected_text}" ] || grep -Fq "${expected_text}" "${destination}"; then
        return 0
      fi
    fi
    if [ "${attempt}" -lt 10 ]; then
      sleep 3
    fi
    attempt=$((attempt + 1))
  done
  return 1
}

run_job() {
  job_name="$1"
  args_override="$2"
  expected_text="$3"
  previous_execution="$(latest_execution "${job_name}")"
  command_args=(
    gcloud run jobs execute "${job_name}"
    "--project=${PROJECT_ID}"
    "--region=${REGION}"
    --wait
  )
  if [ -n "${args_override}" ]; then
    command_args+=("--args=${args_override}")
  fi

  set +e
  "${command_args[@]}"
  job_status=$?
  set -e

  LAST_EXECUTION="$(latest_execution "${job_name}")"
  if [ -z "${LAST_EXECUTION}" ] || [ "${LAST_EXECUTION}" = "${previous_execution}" ]; then
    printf 'Could not resolve the new execution for %s.\n' "${job_name}" >&2
    return 1
  fi

  LAST_LOG_FILE="${RAG_TMP_DIR}/${LAST_EXECUTION}.log"
  fetch_job_logs \
    "${job_name}" \
    "${LAST_EXECUTION}" \
    "${expected_text}" \
    "${LAST_LOG_FILE}" || true

  printf '\nLogs for %s (%s):\n' "${job_name}" "${LAST_EXECUTION}"
  if [ -s "${LAST_LOG_FILE}" ]; then
    sed -n '1,2000p' "${LAST_LOG_FILE}"
  else
    printf '(Logs were not available yet.)\n'
  fi

  if [ "${job_status}" -ne 0 ]; then
    return "${job_status}"
  fi
  if [ -n "${expected_text}" ] &&
     ! grep -Fq "${expected_text}" "${LAST_LOG_FILE}"; then
    printf 'Expected completion text was not found: %s\n' "${expected_text}" >&2
    return 1
  fi
  return 0
}

deploy_job() {
  job_name="$1"
  script_path="$2"

  gcloud run jobs deploy "${job_name}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${IMAGE}" \
    --service-account="${SERVICE_ACCOUNT_EMAIL}" \
    --set-cloudsql-instances="${CONNECTION_NAME}" \
    --set-secrets="DATABASE_URL=${DB_SECRET}:latest" \
    --set-env-vars="${JOB_ENV_VARS}" \
    --command=python \
    --args="${script_path}" \
    --cpu=2 \
    --memory=4Gi \
    --tasks=1 \
    --parallelism=1 \
    --max-retries=0 \
    --task-timeout="${JOB_TIMEOUT}" \
    --quiet
}

extract_database_target() {
  log_file="$1"
  python3 - "${log_file}" <<'PY'
import sys

marker = "Database target:"
with open(sys.argv[1], encoding="utf-8", errors="replace") as handle:
    for line in handle:
        if marker in line:
            target = line.split(marker, 1)[1].strip()
            if target:
                print(target)
                break
PY
}

validate_database_target() {
  target="$1"
  case "${target}" in
    postgresql://*|postgres://*)
      ;;
    *)
      die "Refusing non-PostgreSQL RAG target: ${target:-missing}"
      ;;
  esac
}

ACTIVE_ACCOUNT="$(
  gcloud auth list --filter="status:ACTIVE" --format="value(account)" |
  sed -n '1p'
)"
[ -n "${ACTIVE_ACCOUNT}" ] || die "No active gcloud account. Run: gcloud auth login"

log "Checking Google Cloud resources"
gcloud projects describe "${PROJECT_ID}" --format="value(projectId)" >/dev/null
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  logging.googleapis.com \
  --project="${PROJECT_ID}" \
  --quiet

gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" \
  --format="value(name)" >/dev/null

gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" \
  --project="${PROJECT_ID}" \
  --format="value(email)" >/dev/null

gcloud secrets describe "${DB_SECRET}" \
  --project="${PROJECT_ID}" \
  --format="value(name)" >/dev/null

if [ -z "${IMAGE}" ]; then
  LIVE_REVISION="$(extract_live_revision)"
  if [ -z "${LIVE_REVISION}" ]; then
    gcloud run services describe "${SERVICE}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --format="yaml(status.traffic)" >&2
    die "Expected exactly one production revision receiving 100% traffic."
  fi
  IMAGE="$(
    gcloud run revisions describe "${LIVE_REVISION}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --format="value(spec.containers[0].image)"
  )"
  [ -n "${IMAGE}" ] || die "Could not resolve the production container image."
  printf 'Production revision: %s\n' "${LIVE_REVISION}"
fi
printf 'RAG job image: %s\n' "${IMAGE}"

log "Deploying and running the idempotent database initialisation job"
deploy_job "${DB_INIT_JOB}" "scripts/gcp_utils.py"
if ! run_job \
  "${DB_INIT_JOB}" \
  "" \
  "PostgreSQL and pgvector schema is ready."; then
  printf '\nDatabase initialisation failed. For a full traceback, run:\n' >&2
  printf 'gcloud run jobs execute %q --project=%q --region=%q --args=%q --wait\n' \
    "${DB_INIT_JOB}" \
    "${PROJECT_ID}" \
    "${REGION}" \
    "-c,import scripts.gcp_utils as g; raise SystemExit(g.initialise_database())" \
    >&2
  exit 1
fi

PRIMARY_TARGET=""
ELEVENPLUS_TARGET=""

if [ "${SCOPE}" = "all" ] || [ "${SCOPE}" = "primary" ]; then
  log "Deploying the primary RAG job in plan-only mode"
  deploy_job \
    "${PRIMARY_RAG_JOB}" \
    "scripts/homework_generator/rebuild_all_homework.py"

  if ! run_job \
    "${PRIMARY_RAG_JOB}" \
    "" \
    "PLAN ONLY: no records were deleted or generated."; then
    die "The primary RAG planning job failed."
  fi
  PRIMARY_TARGET="$(extract_database_target "${LAST_LOG_FILE}")"
  validate_database_target "${PRIMARY_TARGET}"
fi

if [ "${SCOPE}" = "all" ] || [ "${SCOPE}" = "elevenplus" ]; then
  log "Deploying the 11+ RAG job in plan-only mode"
  deploy_job \
    "${ELEVENPLUS_RAG_JOB}" \
    "scripts/elevenplus/rebuild_all_elevenplus.py"

  if ! run_job \
    "${ELEVENPLUS_RAG_JOB}" \
    "" \
    "PLAN ONLY: no records were deleted or generated."; then
    die "The 11+ RAG planning job failed."
  fi
  ELEVENPLUS_TARGET="$(extract_database_target "${LAST_LOG_FILE}")"
  validate_database_target "${ELEVENPLUS_TARGET}"
fi

if [ -n "${PRIMARY_TARGET}" ] && [ -n "${ELEVENPLUS_TARGET}" ] &&
   [ "${PRIMARY_TARGET}" != "${ELEVENPLUS_TARGET}" ]; then
  die "Primary and 11+ plans resolved different database targets."
fi

DATABASE_TARGET="${PRIMARY_TARGET:-${ELEVENPLUS_TARGET}}"
[ -n "${DATABASE_TARGET}" ] || die "No database target was resolved."

log "RAG plans completed"
printf 'Confirmed password-free target: %s\n' "${DATABASE_TARGET}"
printf 'Selected scope: %s\n' "${SCOPE}"
if [ "${RESUME}" = true ]; then
  printf 'Mode: resume without deleting the selected collection\n'
else
  printf 'Mode: clean rebuild of the selected collection(s)\n'
fi

if [ "${PLAN_ONLY}" = true ]; then
  printf '\nPlan-only run completed. No RAG records were deleted or generated.\n'
  exit 0
fi

if [ "${ASSUME_YES}" != true ]; then
  if [ ! -t 0 ]; then
    die "Interactive confirmation is unavailable. Rerun with --yes or --plan-only."
  fi
  CONFIRM_TEXT="REBUILD RAG ${DATABASE_TARGET}"
  printf '\nThis permanently replaces the selected RAG data.\n'
  printf 'Type exactly: %s\n> ' "${CONFIRM_TEXT}"
  read -r ANSWER
  [ "${ANSWER}" = "${CONFIRM_TEXT}" ] || die "Confirmation did not match; no RAG data was changed."
fi

RESUME_ARG=""
if [ "${RESUME}" = true ]; then
  RESUME_ARG=",--skip-clean"
fi

if [ "${SCOPE}" = "all" ] || [ "${SCOPE}" = "primary" ]; then
  log "Rebuilding primary Year 1-6 RAG"
  PRIMARY_ARGS="scripts/homework_generator/rebuild_all_homework.py,--execute,--confirm-target,${PRIMARY_TARGET}${RESUME_ARG}"
  if ! run_job \
    "${PRIMARY_RAG_JOB}" \
    "${PRIMARY_ARGS}" \
    "All discovered primary subject generators completed successfully."; then
    printf '\nPrimary RAG rebuild failed.\n' >&2
    printf 'After fixing the generator, resume with:\n' >&2
    printf '%q --scope primary --resume\n' "$0" >&2
    exit 1
  fi
fi

if [ "${SCOPE}" = "all" ] || [ "${SCOPE}" = "elevenplus" ]; then
  log "Rebuilding 11+ RAG"
  ELEVENPLUS_ARGS="scripts/elevenplus/rebuild_all_elevenplus.py,--execute,--confirm-target,${ELEVENPLUS_TARGET}${RESUME_ARG}"
  if ! run_job \
    "${ELEVENPLUS_RAG_JOB}" \
    "${ELEVENPLUS_ARGS}" \
    "All 11+ practice, topic-mastery and year-round generators completed successfully."; then
    printf '\n11+ RAG rebuild failed.\n' >&2
    printf 'After fixing the generator, resume with:\n' >&2
    printf '%q --scope elevenplus --resume\n' "$0" >&2
    exit 1
  fi
fi

log "RAG deployment completed"
printf 'Image: %s\n' "${IMAGE}"
printf 'Database target: %s\n' "${DATABASE_TARGET}"
printf 'Completed scope: %s\n' "${SCOPE}"
printf 'The saved Cloud Run jobs remain in plan-only mode for accidental-run safety.\n'
