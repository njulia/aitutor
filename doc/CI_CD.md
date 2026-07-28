# CI and deployment

GitHub Actions uses Python 3.12, PostgreSQL 16 and Chromium. It compiles the
application, runs unit/API/integration tests with coverage, starts Uvicorn, and
then runs the browser suite. Browser traces and screenshots are retained only
when a job fails.

Production is deployed by `deploy/deploy_gcp.sh`:

1. Verify the non-secret environment file has no placeholders.
2. Create or reuse the regional Artifact Registry repository.
3. Submit the image build to Cloud Build.
4. Deploy one Cloud Run revision with the production service account.
5. Attach the regional Cloud SQL instance.
6. Inject credentials from Secret Manager.

Do not place secret values in `deploy/cloud-run.env.yaml`. Roll back in Cloud
Run by directing traffic to the previous healthy revision. Check `/api/health`
for process health and `/api/ready` for dependency readiness before increasing
traffic.
