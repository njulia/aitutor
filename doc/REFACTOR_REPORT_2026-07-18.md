# Homework Magic AI Tutor — Refactor Report

**Date:** 18 July 2026  
**Scope:** FastAPI web application, account and learner data model, homework generation and marking, RAG, uploads, payments, password reset, support messages, admin APIs, browser code, privacy and child-safety controls.

## Result

The updated project was refactored around seven priorities: correctness, UK child-privacy safeguards, suitability for pupils aged 5–11, latency, stability, token efficiency, and production readiness.

Final automated result:

- **79 tests passed**
- **6 browser tests skipped by design** because they require a separately running staging site and `RUN_E2E=1`
- Python compilation passed
- JavaScript syntax checks passed after excluding JSON-LD data blocks
- No real API keys are included in the delivery package

This work adds technical safeguards and aligns the product design with relevant UK guidance. It is **not a legal certification**. The operator must still complete the DPIA, choose and record lawful bases, verify supplier contracts and data locations, and obtain professional legal/privacy review before a public launch.

## 1. Bugs fixed

### Authentication and account ownership

- Removed `X-User-Id` as an authentication mechanism.
- Replaced browser-controlled learner identity with server-side account ownership checks.
- Fixed anonymous identity generation so it no longer derives a persistent identifier from an IP address.
- Fixed the progress API, which previously compared a learner identifier with the parent login record.
- Fixed logged-in `/api/client-id` handling so it returns an account-owned default learner.
- Fixed password reset to update the same PBKDF2 password store used by login.
- Made password-reset browser validation and API validation consistently require at least 10 characters.
- Added non-enumerating password-reset responses.

### Subscription and billing

- Removed live Stripe subscription lookups from normal request paths.
- Subscription access now uses locally materialised status updated by verified Stripe webhooks.
- Retired unsafe manual/public subscription creation in production.
- Kept manual subscription helpers available only in development/admin-safe paths.

### Progress and review

- Corrected percentage conversion and score field handling in progress responses.
- Preserved homework document identifiers and question indexes through tutor mode.
- Fixed multiple-choice rendering and answer-key handling.
- Added exact metadata-first RAG retrieval and reliable unseen-question selection.
- Added local deterministic marking when an answer key is available.

### Runtime and deployment

- Removed the startup dependency on undeclared `passlib`.
- Reduced `web_app.py` from 2,125 to 1,888 lines by removing dead/copied paths and routing work to focused modules.
- Added `/api/ready` and relational database health checks.
- Made production workers configurable, with a safe default of one worker for the local embedding model.
- Added strict production configuration validation.

## 2. UK child-privacy and safety engineering

### Privacy by default

- Parent/guardian account flow is the default for pupils aged 5–11.
- Registration requires a guardian confirmation in production.
- Raw learner prompts and raw AI content are disabled by default.
- Clear identifiers are minimised before text is sent to an AI provider.
- High-confidence removal covers email addresses, labelled phone numbers, URLs, UK postcodes, names introduced as “my name is”, and school statements.
- Numeric maths answers are preserved so privacy filtering does not damage marking.
- Learner progress, support messages and optional memory have bounded retention settings.
- Account and learner deletion paths preserve parent ownership checks.
- Privacy notices identify data categories, purposes, providers, retention, rights, AI assistance and operator contact details.
- Production requires the data controller name, privacy contact email and postal address.

### Child safety

- Added a conservative first-person safety classifier before AI calls.
- Explicit immediate-danger, abuse, self-harm or credible threat disclosures pause normal tutoring.
- The child receives simple wording telling them to speak to a trusted adult, call 999 in immediate danger, or contact Childline on 0800 1111.
- Story, history and hypothetical text are not automatically treated as a personal disclosure.
- A dedicated `/safety` page is included.

### Age-appropriate behaviour

- Active profile and API contracts are limited to **Year 1–6 and ages 5–11**.
- Tutor prompts require short sentences, supportive feedback, one clear next step and no shaming language.
- Prompts prohibit asking for or repeating a child’s full name, school, address, exact birthday, contact details or account information.
- Practice prompts prohibit advertising, purchase prompts and social-media links.
- Child-facing error messages avoid technical details.

## 3. Latency reductions

- Exact metadata RAG lookup runs before semantic embedding search.
- Answer-key questions are marked locally without an LLM call where possible.
- Detailed explanation for answer-key content can be generated locally.
- Profile and subject extraction use deterministic parsing before falling back to an LLM.
- Multi-subject generation uses bounded parallelism.
- Blocking database and model work is moved off the event loop with bounded concurrency and timeouts.
- Shared request budgets prevent unbounded queues.
- Stripe access checks use the local database rather than a network request.
- Persistent support and reset-token storage uses the shared database in production.

## 4. Token reductions

- Added separate character budgets for homework, answers and prior feedback.
- Reduced default quick-review, detail-review and practice output token ceilings.
- Prioritised wrong and unanswered questions in explanation prompts.
- Removed repeated profile data and unnecessary full-history content.
- Added complete cache keys to prevent accidental cache collisions.
- Local marking and RAG answers avoid LLM use entirely for many common flows.
- Prompt boundaries identify learner text as untrusted data and reduce prompt-injection risk.

## 5. Stability and security improvements

- Added request-size, upload-size, PDF-page, image-pixel and extracted-text limits.
- Encrypted PDFs and unsupported image formats fail safely.
- Temporary uploads are deleted after processing.
- Admin APIs are protected globally instead of route-by-route omissions.
- CORS is restricted to configured origins; wildcard credentialed CORS is rejected in production.
- Production requires HTTPS public URLs and secure cookies.
- Session state, support messages and password-reset tokens use shared relational storage in production.
- Rate limiting is applied to sensitive routes; tests bypass only through the explicit `TESTING` flag.
- User-facing 500 responses no longer disclose raw exceptions.
- Database retention cleanup runs on startup.
- Production rejects SQLite and expects managed PostgreSQL.
- Observability defaults avoid storing raw learner or model content.

## 6. Important files added or substantially changed

### New modules and tests

- `src/webapp/child_safety.py`
- `static/safety.html`
- `test/unit/test_child_safety_and_minimisation.py`
- `test/unit/test_shared_sql_stores.py`
- `test/unit/test_password_backend.py`
- `test/api/test_progress_account_ownership.py`
- `.env.example`

### Major refactors

- `web_app.py`
- `src/progress_db.py`
- `src/homework_generator.py`
- `src/file_utils.py`
- `src/prompts.py`
- `src/webapp/account_routes.py`
- `src/webapp/account_store.py`
- `src/webapp/message_store.py`
- `src/webapp/password_reset_store.py`
- `src/webapp/password_reset_routes.py`
- `src/webapp/prompt_budget.py`
- `src/webapp/review_service.py`
- `src/webapp/runtime.py`
- `static/app.html`
- `static/js/app.js`
- `static/register.html`
- `static/privacy.html`

## 7. Production actions still required

1. **Rotate all credentials** that appeared in any previously uploaded or committed environment file.
2. Fill in `DATA_CONTROLLER_NAME`, `PRIVACY_CONTACT_EMAIL` and `PRIVACY_POSTAL_ADDRESS`.
3. Complete and approve a child-focused DPIA before processing live learner data.
4. Record the lawful basis for each processing purpose. Where consent is the chosen basis for an information society service offered directly to an under-13, implement reasonable verification of parental responsibility.
5. Review whether the Online Safety Act applies to any user-to-user, messaging, upload-sharing or community feature before enabling it.
6. Sign data-processing agreements with the AI, email, payment, logging and cloud providers; document sub-processors, data locations and retention.
7. Run the six opt-in browser tests against staging.
8. Test Stripe webhooks, payment failure, cancellation and refund paths in test mode.
9. Enable PostgreSQL backups, point-in-time recovery and restore drills.
10. Use a shared rate limiter such as Redis or a managed edge/WAF limiter before scaling to multiple instances.
11. Add production alerting for readiness failures, elevated 5xx rates, model timeouts and database saturation without recording raw learner content.
12. Arrange independent safeguarding, accessibility and penetration testing.

## 8. Suggested first production configuration

- PostgreSQL with `pgvector`
- `DEV_MODE=false`
- `STORE_RAW_LEARNER_CONTENT=false`
- `STORE_RAW_AI_CONTENT=false`
- `WEB_CONCURRENCY=1`
- one low-cost model for generation/quick feedback and a separate bounded model for paid detailed explanations
- exact `CORS_ORIGINS`
- HTTPS-only cookies
- Stripe test mode until webhook tests pass
- 365-day learning-record retention unless the DPIA supports a shorter period
- 180-day support-message retention or less
- 30-minute reset-token expiry

## 9. Verification commands

```bash
python -m compileall -q web_app.py src scripts test
pytest -q

# Run browser tests against a running staging instance
RUN_E2E=1 BASE_URL=https://staging.example.com pytest -q test/e2e
```

Before deployment, copy `.env.example` to a secure local secret source and replace every placeholder. Do not commit it as `.env` or `env`.
