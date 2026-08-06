# CI/CD

Every proposed release should run these gates in order:

1. Install pinned Python and JavaScript dependencies.
2. Run Python unit, API and integration tests.
3. Run JavaScript tests and syntax checks.
4. Compile Python modules and validate deployment shell syntax.
5. Build the container once and scan it for known vulnerabilities and accidental secrets.
6. Deploy that immutable image to staging.
7. Run health, authentication, family-isolation, mock-exam and Stripe test-mode smoke checks.
8. Promote the same image to production and verify `/health`, canonical redirects and billing webhooks.

Production deployment must fail closed when required legal identity, HTTPS origin, session secrets, database configuration or Stripe webhook settings are missing. Keep price identifiers and other environment-specific values outside committed scripts.

Roll back to the previous immutable image if learner access, ownership checks, checkout confirmation or core marking fails. Database migrations must remain backward-compatible for at least the duration of the rollout.
