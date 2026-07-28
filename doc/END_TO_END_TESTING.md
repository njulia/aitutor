# End-to-end testing

Install Chromium once:

```bash
python -m playwright install chromium
```

Start the service with a disposable test database:

```bash
TESTING=true DEV_MODE=true uvicorn web_app:app \
  --host 127.0.0.1 --port 5000
```

In another terminal:

```bash
RUN_E2E=1 pytest test/e2e \
  --browser chromium \
  --tracing retain-on-failure \
  --screenshot only-on-failure
```

The journeys cover guided homework, 11+ setup, parent-note ephemerality,
answer-free rendering and core account interaction. Keep model and external
network calls stubbed so browser tests are repeatable and free.
