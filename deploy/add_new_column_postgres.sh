# Set your variables (matching those in your deploy script)
PROJECT_ID="aitutor-502921"
REGION="europe-west2"
SQL_INSTANCE="aitutor-prod-pg"
DB_NAME="aitutor" # Replace with the actual database name defined in your application config
DB_USER="aitutor_app" # Replace with your actual database user
DB_PASSWORD="f2e533fd6d70dd8f878f6763aebd8a313d81f79dc48ec0864655de93a9ccd210"

# Construct the connection name
CONNECTION_NAME="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"

# Execute the schema change using PGPASSWORD for authentication
echo "ALTER TABLE students ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE;" | \
PGPASSWORD="${DB_PASSWORD}" gcloud sql connect "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" \
  --user="${DB_USER}" \
  --database="${DB_NAME}" \
  --quiet