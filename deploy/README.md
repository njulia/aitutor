# Google Cloud deployment

This directory contains a production-oriented Cloud Run configuration for
Homework Magic. The deployment uses Cloud Build, Artifact Registry, Cloud Run,
Cloud SQL for PostgreSQL/pgvector, Secret Manager, Vertex AI and DeepSeek.

## 1. Prepare Google Cloud

Create the `aitutor-run@aitutor-502921.iam.gserviceaccount.com` service account
and grant it:

- Cloud SQL Client
- Secret Manager Secret Accessor for the four secrets listed below
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

The database secret should contain a SQLAlchemy URL using the Cloud SQL Unix
socket. URL-encode the password:

```text
postgresql+psycopg://aitutor_app:PASSWORD@/aitutor?host=/cloudsql/aitutor-502921:europe-west2:aitutor-prod-pg
```

Generate `SESSION_OWNER_SECRET` with at least 32 random characters. Do not put
secret values in `cloud-run.env.yaml`.

## 3. Configure non-secret values

```bash
cp deploy/cloud-run.env.yaml.example deploy/cloud-run.env.yaml
```

Replace every `REPLACE_...` entry with the legal operator and SMTP details.
The real file is ignored by Git and Docker.

## 4. Deploy

Authenticate `gcloud`, select a deployer identity with permission to build and
deploy, then run:

```bash
./deploy/deploy_gcp.sh
```

The script creates the Artifact Registry repository if necessary, builds an
immutable timestamped image, and deploys it to Cloud Run in `europe-west2`.
Override any `GCP_*`, `DEPLOY_ENV_FILE`, or `SECRET_BINDINGS` environment
variable when deploying to a different project or topology.

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
