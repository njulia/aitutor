chmod +x deploy/deploy_code_gcp.sh deploy/deploy_rag_gcp.sh
gcloud auth login

# This creates a zero-traffic revision, checks the live staging URL (including
# the Study Buddies page), then asks before sending traffic to production.
./deploy/deploy_code_gcp.sh

./deploy/deploy_rag_gcp.sh --plan-only
./deploy/deploy_rag_gcp.sh

## Study Buddy updates

No separate database command is needed for a Study Buddy release. When the new
Cloud Run revision starts, it adds the latest Study Buddy settings and safely
updates any older stored Buddy Codes such as `ALEX-5470` to `ALEX5470`.


## Production AI model

Every application deployment automatically sets both quick review and detail review
to DeepSeek `deepseek-v4-flash`. You do not need to edit the Cloud Run environment
variables manually before each deployment.

For a deliberate model override:

```bash
./deploy/deploy_code_gcp.sh --detail-review-model MODEL --yes
```
