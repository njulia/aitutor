# Testing

Install `requirements.txt`, then run:

```bash
pytest -q test/unit test/api test/integration
```

Use an isolated test database. Tests must not call paid AI, email or payment
services.
