#!/usr/bin/env bash
#
# Build and safely release a new Homework Magic application image.
#
# The existing Cloud Run service configuration and Secret Manager bindings are
# preserved. The new revision receives no production traffic until it passes
# GET-based staging checks. If the post-promotion checks fail, traffic is
# automatically rolled back to the previously serving revision.

set -Eeuo pipefail

PROJECT_ID="${PROJECT_ID:-aitutor-502921}"
REGION="${REGION:-europe-west2}"
SERVICE="${SERVICE:-aitutor-prod}"
REPOSITORY="${REPOSITORY:-aitutor-repo}"
SQL_INSTANCE="${SQL_INSTANCE:-aitutor-prod-pg}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_EMAIL:-aitutor-run@${PROJECT_ID}.iam.gserviceaccount.com}"
BUSINESS_CONTACT_EMAIL="${BUSINESS_CONTACT_EMAIL:-contact@homeworkmagic.co.uk}"
PRODUCTION_URL="${PRODUCTION_URL:-https://homeworkmagic.co.uk}"
RELEASE="${RELEASE:-}"

ASSUME_YES=false
STAGING_ONLY=false

usage() {
  cat <<'USAGE'
Usage:
  ./deploy/deploy_code_gcp.sh [options]

Builds the current source, creates a zero-traffic staging revision, checks it
with HTTP GET requests, and then optionally promotes it to 100% traffic.

Options:
  --project ID             Google Cloud project (default: aitutor-502921)
  --region REGION          Google Cloud region (default: europe-west2)
  --service NAME           Cloud Run service (default: aitutor-prod)
  --repository NAME        Artifact Registry repository (default: aitutor-repo)
  --sql-instance NAME      Cloud SQL instance (default: aitutor-prod-pg)
  --service-account EMAIL  Runtime service account
  --production-url URL     Public URL checked after promotion
  --contact-email EMAIL    BUSINESS_CONTACT_EMAIL value
  --release TAG            Explicit image tag (default: UTC timestamp)
  --staging-only           Stop after staging checks; do not move traffic
  --yes                    Promote without an interactive confirmation
  -h, --help               Show this help

Environment variables with the uppercase option names are also supported.

Examples:
  ./deploy/deploy_code_gcp.sh
  ./deploy/deploy_code_gcp.sh --yes
  ./deploy/deploy_code_gcp.sh --staging-only
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
    --repository)
      [ "$#" -ge 2 ] || die "--repository requires a value"
      REPOSITORY="$2"
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
    --production-url)
      [ "$#" -ge 2 ] || die "--production-url requires a value"
      PRODUCTION_URL="$2"
      shift 2
      ;;
    --contact-email)
      [ "$#" -ge 2 ] || die "--contact-email requires a value"
      BUSINESS_CONTACT_EMAIL="$2"
      shift 2
      ;;
    --release)
      [ "$#" -ge 2 ] || die "--release requires a value"
      RELEASE="$2"
      shift 2
      ;;
    --staging-only)
      STAGING_ONLY=true
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONNECTION_NAME="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
PRODUCTION_URL="${PRODUCTION_URL%/}"

require_command gcloud
require_command curl
require_command python3

[ -f "${PROJECT_ROOT}/Dockerfile" ] || die "Dockerfile not found in ${PROJECT_ROOT}"
[ -f "${PROJECT_ROOT}/web_app.py" ] || die "web_app.py not found in ${PROJECT_ROOT}"

DEPLOY_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/homeworkmagic-code-deploy.XXXXXX")"
cleanup() {
  if [ -n "${DEPLOY_TMP_DIR:-}" ] && [ -d "${DEPLOY_TMP_DIR}" ]; then
    rm -rf "${DEPLOY_TMP_DIR}"
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

extract_staging_url() {
  gcloud run services describe "${SERVICE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format=json |
  python3 -c '
import json
import sys

traffic = json.load(sys.stdin).get("status", {}).get("traffic", [])
matches = [
    item.get("url")
    for item in traffic
    if item.get("tag") == "staging" and item.get("url")
]
if len(matches) == 1:
    print(matches[0])
'
}

wait_for_staging_url() {
  attempt=1
  candidate=""
  while [ "${attempt}" -le 10 ]; do
    candidate="$(extract_staging_url)"
    if [ -n "${candidate}" ]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
    if [ "${attempt}" -lt 10 ]; then
      sleep 3
    fi
    attempt=$((attempt + 1))
  done
  return 1
}

show_revision_logs() {
  revision="$1"
  [ -n "${revision}" ] || return 0
  printf '\nCloud Run logs for %s:\n' "${revision}" >&2
  gcloud logging read \
    "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE}\" AND resource.labels.revision_name=\"${revision}\"" \
    --project="${PROJECT_ID}" \
    --freshness=2h \
    --order=asc \
    --limit=250 \
    --format="value(timestamp,severity,textPayload,jsonPayload.message)" \
    >&2 || true
}

validate_response_body() {
  label="$1"
  body_file="$2"

  case "${label}" in
    health)
      python3 - "${body_file}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if payload.get("status") != "ok" or payload.get("initialized") is not True:
    raise SystemExit("health response is not ready")
PY
      ;;
    ready)
      python3 - "${body_file}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
expected = {
    "status": "ready",
    "database": "ok",
    "configuration": "ok",
}
if any(payload.get(key) != value for key, value in expected.items()):
    raise SystemExit("readiness response is not ready")
PY
      ;;
    robots)
      grep -Eq '^User-agent:[[:space:]]*\*' "${body_file}" &&
        grep -Eq '^Sitemap:[[:space:]]*https://' "${body_file}"
      ;;
    sitemap)
      python3 - "${body_file}" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
if not root.tag.endswith("urlset"):
    raise SystemExit("sitemap root element is not urlset")
PY
      ;;
    app)
      grep -Eiq '<html([[:space:]>])' "${body_file}"
      ;;
    *)
      return 0
      ;;
  esac
}

check_get() {
  base_url="$1"
  path_name="$2"
  label="$3"
  body_file="${DEPLOY_TMP_DIR}/${label}.body"
  attempt=1
  status_code=""

  while [ "${attempt}" -le 5 ]; do
    status_code="$(
      curl --silent --show-error --location --compressed \
        --connect-timeout 10 \
        --max-time 90 \
        --output "${body_file}" \
        --write-out "%{http_code}" \
        "${base_url}${path_name}"
    )" || status_code="curl_error"

    if [ "${status_code}" = "200" ] &&
       validate_response_body "${label}" "${body_file}"; then
      printf '200  %s\n' "${path_name}"
      return 0
    fi

    if [ "${attempt}" -lt 5 ]; then
      sleep 3
    fi
    attempt=$((attempt + 1))
  done

  printf 'FAILED  %s (last HTTP result: %s)\n' "${path_name}" "${status_code}" >&2
  if [ -s "${body_file}" ]; then
    sed -n '1,20p' "${body_file}" >&2
  fi
  return 1
}

check_application() {
  base_url="$1"
  check_get "${base_url}" "/api/health" health &&
    check_get "${base_url}" "/api/ready" ready &&
    check_get "${base_url}" "/robots.txt" robots &&
    check_get "${base_url}" "/sitemap.xml" sitemap &&
    check_get "${base_url}" "/app" app
}

log "Checking local source"
python3 - "${PROJECT_ROOT}" <<'PY'
import ast
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
excluded = {".git", ".venv", "venv", "data", "uploads", "pytest-of-root"}
files = [
    path
    for path in root.rglob("*.py")
    if not any(part in excluded for part in path.relative_to(root).parts)
]
errors = []
for path in files:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        errors.append(f"{path.relative_to(root)}: {exc}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Python syntax check passed for {len(files)} files.")
PY

ACTIVE_ACCOUNT="$(
  gcloud auth list --filter="status:ACTIVE" --format="value(account)" |
  sed -n '1p'
)"
[ -n "${ACTIVE_ACCOUNT}" ] || die "No active gcloud account. Run: gcloud auth login"

log "Checking Google Cloud resources"
gcloud projects describe "${PROJECT_ID}" --format="value(projectId)" >/dev/null
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}" \
  --quiet

gcloud run services describe "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(metadata.name)" >/dev/null

gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" \
  --format="value(name)" >/dev/null

gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" \
  --project="${PROJECT_ID}" \
  --format="value(email)" >/dev/null

OLD_REVISION="$(extract_live_revision)"
if [ -z "${OLD_REVISION}" ]; then
  gcloud run services describe "${SERVICE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format="yaml(status.traffic)" >&2
  die "Expected exactly one revision receiving 100% traffic. Resolve split traffic before deploying."
fi
printf 'Current production revision: %s\n' "${OLD_REVISION}"

if gcloud artifacts repositories describe "${REPOSITORY}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" >/dev/null 2>&1; then
  REPOSITORY_FORMAT="$(
    gcloud artifacts repositories describe "${REPOSITORY}" \
      --project="${PROJECT_ID}" \
      --location="${REGION}" \
      --format="value(format)"
  )"
  [ "${REPOSITORY_FORMAT}" = "DOCKER" ] ||
    die "Artifact Registry repository ${REPOSITORY} is not a Docker repository."
else
  log "Creating Artifact Registry repository ${REPOSITORY}"
  gcloud artifacts repositories create "${REPOSITORY}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --repository-format=docker \
    --description="Homework Magic production container images" \
    --quiet
fi

if [ -z "${RELEASE}" ]; then
  RELEASE="$(date -u +%Y%m%d-%H%M%S)"
fi
case "${RELEASE}" in
  *[!A-Za-z0-9_.-]*|"")
    die "Release tag contains unsupported characters: ${RELEASE}"
    ;;
esac

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE}:${RELEASE}"

log "Building ${IMAGE}"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE}" \
  "${PROJECT_ROOT}"

gcloud artifacts docker images describe "${IMAGE}" \
  --project="${PROJECT_ID}" >/dev/null

log "Creating a zero-traffic staging revision"
set +e
gcloud run services update "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --add-cloudsql-instances="${CONNECTION_NAME}" \
  --port=8080 \
  --cpu=2 \
  --memory=4Gi \
  --concurrency=8 \
  --min-instances=0 \
  --max-instances=10 \
  --cpu-boost \
  --update-env-vars="BUSINESS_CONTACT_EMAIL=${BUSINESS_CONTACT_EMAIL}" \
  --no-traffic \
  --tag=staging \
  --quiet
DEPLOY_STATUS=$?
set -e

NEW_REVISION="$(
  gcloud run services describe "${SERVICE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format="value(status.latestCreatedRevisionName)" 2>/dev/null || true
)"

if [ "${DEPLOY_STATUS}" -ne 0 ]; then
  show_revision_logs "${NEW_REVISION}"
  die "The staging revision failed to deploy. Production traffic was not changed."
fi
[ -n "${NEW_REVISION}" ] || die "Cloud Run did not report the new revision name."
[ "${NEW_REVISION}" != "${OLD_REVISION}" ] ||
  die "Cloud Run did not create a new revision."

STAGING_URL="$(wait_for_staging_url || true)"
if [ -z "${STAGING_URL}" ]; then
  show_revision_logs "${NEW_REVISION}"
  die "The staging traffic tag or URL was not found."
fi

printf 'New staging revision: %s\n' "${NEW_REVISION}"
printf 'Staging URL: %s\n' "${STAGING_URL}"

log "Running staging checks with HTTP GET"
if ! check_application "${STAGING_URL%/}"; then
  show_revision_logs "${NEW_REVISION}"
  die "Staging checks failed. Production remains on ${OLD_REVISION}."
fi

if [ "${STAGING_ONLY}" = true ]; then
  log "Staging deployment completed"
  printf 'Production remains on: %s\n' "${OLD_REVISION}"
  printf 'Test revision: %s\n' "${NEW_REVISION}"
  printf 'Test URL: %s\n' "${STAGING_URL}"
  exit 0
fi

if [ "${ASSUME_YES}" != true ]; then
  if [ ! -t 0 ]; then
    die "Interactive confirmation is unavailable. Rerun with --yes or --staging-only."
  fi
  printf '\nPromote %s to 100%% production traffic? [y/N] ' "${NEW_REVISION}"
  read -r ANSWER
  case "${ANSWER}" in
    y|Y|yes|YES)
      ;;
    *)
      log "Promotion cancelled"
      printf 'The tested revision remains available at %s\n' "${STAGING_URL}"
      exit 0
      ;;
  esac
fi

log "Promoting the tested revision"
gcloud run services update-traffic "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --to-revisions="${NEW_REVISION}=100" \
  --remove-tags=staging \
  --quiet

LIVE_REVISION="$(extract_live_revision)"
if [ "${LIVE_REVISION}" != "${NEW_REVISION}" ]; then
  die "Traffic verification failed: expected ${NEW_REVISION}, found ${LIVE_REVISION:-none}."
fi

log "Running production checks"
if ! check_application "${PRODUCTION_URL}"; then
  printf '\nProduction checks failed; rolling traffic back to %s.\n' "${OLD_REVISION}" >&2
  if gcloud run services update-traffic "${SERVICE}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --to-revisions="${OLD_REVISION}=100" \
    --quiet; then
    printf 'Rollback completed.\n' >&2
  else
    printf 'AUTOMATIC ROLLBACK FAILED. Restore traffic manually immediately.\n' >&2
  fi
  show_revision_logs "${NEW_REVISION}"
  exit 1
fi

log "Code deployment completed"
printf 'Image: %s\n' "${IMAGE}"
printf 'Previous revision: %s\n' "${OLD_REVISION}"
printf 'Production revision: %s\n' "${NEW_REVISION}"
printf 'Production URL: %s\n' "${PRODUCTION_URL}"
printf '\nRollback command:\n'
printf 'gcloud run services update-traffic %q --project=%q --region=%q --to-revisions=%q\n' \
  "${SERVICE}" "${PROJECT_ID}" "${REGION}" "${OLD_REVISION}=100"
