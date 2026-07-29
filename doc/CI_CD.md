# CI/CD

The GitHub Actions workflow runs unit, API and integration tests before the
separate end-to-end job. Deployment scripts perform production configuration,
legal-page and public-route checks before updating Cloud Run.
