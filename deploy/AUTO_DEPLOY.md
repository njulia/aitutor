chmod +x deploy/deploy_code_gcp.sh deploy/deploy_rag_gcp.sh
gcloud auth login

./deploy/deploy_code_gcp.sh

./deploy/deploy_rag_gcp.sh --plan-only
./deploy/deploy_rag_gcp.sh


## Production AI model

Every application deployment automatically sets both quick review and detail review
to DeepSeek `deepseek-v4-flash`. You do not need to edit the Cloud Run environment
variables manually before each deployment.

For a deliberate model override:

```bash
./deploy/deploy_code_gcp.sh --detail-review-model MODEL --yes
```
