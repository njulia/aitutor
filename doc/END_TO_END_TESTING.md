# End-to-end browser testing

## Run locally

Start the application with isolated test data, then run:

```bash
RUN_E2E=1 \
E2E_BASE_URL=http://127.0.0.1:5000 \
pytest -q test/e2e --browser chromium
```

Do not point automated browser tests at production unless a test account, test payment mode and written release procedure explicitly permit it.

## Required smoke journeys

- Homepage loads, contains the Homework Magic heading and reaches the learning app.
- Parent registration, login and logout work without exposing whether unrelated accounts exist.
- A Year 1–6 learner can open a short activity and submit an answer.
- 11+ practice, topic mastery and year-round plan open successfully.
- Progress and learning memory remain attached to the signed-in parent account.
- Contact form rejects missing details and warns against including child identifiers.
- Pricing clearly shows GBP amounts, one-off versus recurring billing and policy links.
- Keyboard navigation, focus visibility, headings, form labels and live status messages remain usable.

## Public launch smoke checks

Use read-only requests to confirm the canonical host, sitemap, robots file and legal pages. Use Stripe test mode for checkout journeys. A live low-value payment should be a controlled final verification performed by the account owner and refunded/cancelled according to the launch checklist.
