# CI/CD safeguards

The repository workflow should run on pull requests and protected-branch pushes.

## Continuous integration

1. Check out the exact revision.
2. Install dependencies from the lock file.
3. Run `python -m compileall -q web_app.py src scripts test`.
4. Run `pytest -q test/unit test/api test/integration`.
5. Run browser tests when UI dependencies are available.
6. Build the container without production secrets.
7. Scan the change and image for committed credentials and vulnerable dependencies.

## Deployment

- Deploy an immutable image by digest.
- Inject secrets through Google Secret Manager and public configuration through controlled environment values.
- Keep `DEV_MODE=false`, raw learner/AI content storage disabled and secure cookies enabled.
- Run readiness checks before shifting traffic.
- Preserve the previous healthy revision for rollback.
- Verify the canonical domain, public policy pages, support email, payment mode and webhook health after deployment.

Do not automatically enable live billing merely because a deployment succeeded. Live payment keys, price IDs, webhook secret and public legal details must all belong to the reviewed production account.
