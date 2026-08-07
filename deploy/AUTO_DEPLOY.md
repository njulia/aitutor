chmod +x deploy/deploy_code_gcp.sh deploy/deploy_rag_gcp.sh
gcloud auth login

./deploy/deploy_code_gcp.sh

./deploy/deploy_rag_gcp.sh --plan-only
./deploy/deploy_rag_gcp.sh
