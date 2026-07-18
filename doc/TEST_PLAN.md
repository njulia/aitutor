# Test plan

## Objectives

1. Prevent regressions in parent-account ownership and learner isolation.
2. Confirm learning flows are understandable for pupils aged 5–11.
3. Check privacy-protective defaults and safeguarding responses.
4. Keep AI, database and payment failures from destabilising the site.
5. Control latency, prompt size and unnecessary provider calls.

## Test layers

| Layer | Folder | Main purpose |
|---|---|---|
| Unit | `test/unit` | Pure functions, validation, privacy filters, RAG and storage contracts |
| API | `test/api` | Authentication, authorisation, public routes and request/response contracts |
| Integration | `test/integration` | Complete multi-route family and learning journeys |
| Browser E2E | `test/e2e` | Real pages, JavaScript, forms, redirects and learner interactions |

## Required release gates

- Python compilation passes.
- Unit, API and integration tests pass.
- Coverage is at least 55% for the active `src.webapp` package and `web_app`; raise this ratchet as coverage grows.
- Chromium E2E tests pass in CI.
- No test requires a production secret.
- No raw child content appears in test logs or browser-storage assertions.
- Administrator routes reject anonymous and normal family accounts.
- Account A cannot read or modify Account B's learner profile.
- Safety and privacy pages remain accessible without login.

## High-risk scenarios

- Session theft or email-bearing session cookies.
- Insecure direct object references to learner IDs.
- Open redirects after login or registration.
- Answer keys exposed before submission.
- A child identifier sent to an AI provider.
- Raw learner answers persisted when disabled.
- Uploaded file decompression or extraction abuse.
- Stripe access granted without a verified local subscription state.
- AI timeout causing request pile-up.
- Local SQLite or Chroma state used in multi-instance production.

## Manual checks before launch

- Keyboard-only navigation and visible focus.
- Screen-reader labels on authentication, homework and payment forms.
- Mobile layouts at 320, 375 and 768 pixels.
- Plain-language review by a UK primary teacher.
- Safeguarding review by an appropriate professional.
- Parent account deletion, learner deletion and data export.
- Stripe test checkout, webhook, cancellation and failed payment.
- Password-reset email delivery and one-time token behaviour.
- Database backup restore drill.
