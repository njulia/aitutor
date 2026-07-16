# AI Tutor code review and refactor

## Scope

This refactor focused on the requested priorities:

1. concurrency and latency;
2. privacy protection for a UK primary-school service;
3. lower LLM token usage;
4. RAG-first generation and marking;
5. no repeated homework, including concurrent requests;
6. return to generated homework after login;
7. user/admin messaging;
8. registration and password reset;
9. child-appropriate reliability and safety defaults.

## Highest-risk findings fixed

### Concurrency and latency

- Synchronous LLM, OCR, database, Chroma and provider calls were reachable from `async` routes and could block the FastAPI event loop.
- Expensive endpoints had no shared concurrency bulkhead.
- Tutor sessions were process-local dictionaries, so they disappeared after restart and did not work reliably with multiple workers.
- Subject generation could return results in completion order rather than the order selected by the user.

Changes:

- expensive work now runs through bounded worker execution with timeouts;
- expensive routes use a concurrency bulkhead and friendly busy response;
- tutor sessions are persistent, owner-bound and support optimistic versioning;
- per-subject worker count is capped and output order is stable;
- production startup rejects unsuitable local database configuration.

### RAG-first and token reduction

- Normal year/subject requests performed semantic embedding searches even when exact metadata was enough;
- review still called the LLM after finding authoritative RAG answers;
- prompts could include unnecessary learner identifiers and long free-text profiles;
- the LLM completion default was larger than needed.

Changes:

- exact year/subject metadata lookup runs first and creates no query embedding;
- semantic search is used only for genuine learning-goal/weak-area queries;
- the LLM is called only after unseen RAG content is exhausted or no authoritative answer exists;
- RAG answers are marked deterministically in Python, including tutor-question index matching;
- profile, homework, answer and feedback inputs are compacted before prompts;
- learner IDs and free-text descriptions are excluded from homework-generation prompts;
- default completion budget is reduced and provider retry/timeout behaviour is bounded.

### Repeated homework

The old design used RAG document metadata such as `student_id` as a proxy for “shown to this learner”. That does not represent assignment history and races when requests arrive together.

Changes:

- added a privacy-minimised SQL assignment ledger;
- it stores only a pseudonymous learner key, RAG document ID, subject/year/kind and timestamp;
- a unique database constraint atomically claims the first unseen document;
- concurrent requests therefore claim different homework;
- newly generated library content is shared and no longer stores a learner ID in Chroma.

### Authentication, sessions and access control

- an `X-User-Id` header was treated like authentication;
- anonymous identity was derived from IP address and the API returned the IP;
- admin APIs were not consistently guarded;
- wildcard credentialed CORS was configured;
- logout removed only browser state rather than revoking the server token;
- production subscription checks could make live Stripe calls per request.

Changes:

- only verified session/Authorization tokens identify a user;
- anonymous IDs are random, cookie-backed and not derived from IP;
- all admin pages/APIs are protected by a configured administrator allow-list;
- CORS uses explicit configured origins and write requests receive same-origin protection;
- logout revokes the server-side token;
- entitlements come from locally materialised subscription state updated by verified billing flows.

### Privacy and child data

- parent email addresses were stored in browser `localStorage`;
- raw uploads were read fully into memory and saved under collision-prone original names;
- base64 images had no strict data-URL/type/size validation;
- generated shared RAG documents could contain learner ownership metadata;
- erasure did not include assignment history, legacy learner-owned RAG records or account-owned support messages.

Changes:

- browser storage keeps only a non-sensitive login-state flag; email is not persisted there;
- uploads stream to unique temporary files, enforce limits and are removed after extraction;
- image data URLs are strictly validated and size-limited;
- raw learner content remains off by default in progress/memory stores;
- account/learner erasure now covers progress, memory, telemetry, support messages, temporary sessions, assignment history and legacy RAG ownership records;
- shared homework content is separated from learner history.

### Login return flow

- generated homework could be lost when a paid action redirected an anonymous user to login.

Changes:

- the server creates a short-lived owner-bound pending session before returning login/payment-required;
- the browser carries only the opaque pending session ID;
- after login in the same browser, the session is atomically claimed by the account and the exact generated homework is restored;
- safe relative return paths prevent open redirects.

### Messaging and password reset

The project already contained message, account, billing, memory and password-reset modules, but they were not all connected to the main application.

Changes:

- connected user message box and administrator message/reply routes;
- connected optional support-reply email delivery;
- connected registration, parent account/default learner creation and server session cookies;
- connected forgot-password, token validation and password reset routes;
- connected account/learner management and privacy-erasure routes.

### Browser safety and usability

- the main app loaded a Markdown parser from a third-party CDN;
- email identifiers were exposed in browser storage and progress URLs;
- several UI handlers depended on a browser-global `event` object;
- stale local UI state could overwrite restored server-side homework.

Changes:

- Markdown rendering uses local scripts and safe rendering helpers;
- no learner/email identifier is added to progress URLs;
- tab/input handlers receive their element explicitly;
- server-restored pending homework takes precedence over stale session storage;
- user-facing errors avoid internal exception details and use simple language.

## Automated verification

Command:

```text
pytest -q
```

Result:

```text
35 passed, 7 skipped
```

Skipped checks:

- 3 Chroma integration checks because `chromadb` is not installed in this execution environment;
- 4 browser end-to-end checks because they require `RUN_E2E=1` and a running website/browser.

Additional checks completed:

- Python compile check for changed modules;
- JavaScript syntax check for `static/js/app.js` and `static/js/login.js`;
- scan for wildcard credentialed CORS, IP-derived client identity, `X-User-Id`, email/student localStorage writes and production `reload=True` usage.

## Production actions still required

This is an engineering hardening pass, not a legal compliance certificate. Before launch:

- deploy PostgreSQL and server-backed Chroma for multiple application workers;
- set strong production secrets, `ADMIN_EMAILS`, `APP_BASE_URL`, `CORS_ORIGINS`, SMTP and verified Stripe webhook settings;
- install ChromaDB and run the skipped RAG integration tests against a copy of production-like data;
- run the browser E2E suite against the built container;
- complete a child-focused DPIA, lawful-basis/retention assessment, privacy notices and processor agreements;
- define and automate retention for uploads, support messages, telemetry, password-reset records and assignment history;
- add independent safeguarding/content-quality evaluation for model fallbacks;
- move the remaining inline page scripts/styles to local files, then change CSP from report-only to enforced;
- load-test `/api/generate`, `/api/review` and OCR with realistic worker/provider limits.
