# Homework Magic code audit and refactor report

**Audit date:** 11 July 2026  
**Repository reviewed:** `njulia/aitutor`, public `main` branch (72 commits when reviewed)  
**Additional supplied files:** `web_app.py`, `homework_rag.py`, and the earlier monolithic `app.html`

## Scope and limits

I reviewed the public repository tree and the current raw source for the main application, account/student module, message module, RAG module, frontend application logic, and existing test layout. I also inspected the three supplied files locally.

The execution environment could read the public repository through GitHub but could not make a Git clone. Therefore I could not run the repository's complete existing test suite against its exact checkout. The patch package itself was compiled, applied successfully to a representative checkout built from the supplied files, and its isolated tests passed.

## Executive result

The application has a good MVP foundation and recent separation of the largest backend/frontend files. It is **not ready for an internet-facing production launch for children yet** because several security and concurrency defects are release blockers.

The hardening package fixes the highest-impact defects without changing the main API contracts:

1. Protects legacy admin routes globally.
2. Replaces IP-derived anonymous identity with a random cookie-backed identity.
3. Replaces process-local tutor sessions with owner-bound, expiring SQLite sessions.
4. Adds bounded concurrency and safe timeouts for costly routes.
5. Moves account database work away from the async event loop and removes first-request races.
6. Streams uploads to unique temporary files and validates file signatures.
7. Sanitises AI-generated Markdown before inserting it into the DOM.
8. Uses collision-free RAG IDs and fixes the broken Chinese collection path.
9. Adds prompt budgets and full-content cache-key helpers.
10. Disables Uvicorn reload in production and supports a controlled worker count.

## Release blockers — fix before production

### P0-1: Most legacy admin endpoints are not authorised

The application defines an admin checker, and the newer account routes call it, but many old `/api/admin/*` endpoints do not. These include user management, subscription creation, test-account management, cache clearing, AI request detail, conversation history, and embedding-cache maintenance.

**Impact:** an unauthorised visitor could read sensitive operational or student-related information, change users/subscriptions, create test accounts, or clear caches.

**Patch:** `AdminPathGuardMiddleware` protects every `/api/admin/*`, `/admin`, and `/admin/*` path even when a route forgot its local check. Keep local route checks as defence in depth.

**Required configuration:** set `ADMIN_EMAILS` to parent/admin account email addresses. Do not expose an admin API merely because an API-key environment variable is empty.

### P0-2: AI output is rendered as trusted HTML

The frontend calls `marked.parse(...)` and places the result into `innerHTML`. Model output, uploaded content, or RAG content can therefore introduce active HTML.

**Impact:** stored or reflected cross-site scripting, session actions performed as the parent, malicious links, or misleading child-facing UI.

**Patch:** all Markdown rendering is routed through `renderSafeMarkdown()`, which uses DOMPurify and fails closed to escaped text if the sanitizer is missing.

**Follow-up:** vendor the sanitizer in your own static assets, pin the version, add a verified Subresource Integrity hash if using a CDN, and replace inline scripts so an enforcing Content Security Policy can be enabled.

### P0-3: Anonymous identity is based on IP and the endpoint returns the raw IP

The current `/api/client-id` trusts `X-Forwarded-For`, hashes the IP into a stable identifier, and returns the IP to the browser.

**Impact:** unnecessary collection of personal data, unreliable identity behind family/school networks, spoofing when proxy headers are not strictly controlled, and a poor privacy default for a service intended for children.

**Patch:** use an unguessable random `HttpOnly`, `SameSite=Lax`, secure-in-production cookie. The endpoint returns only the anonymous ID and never an IP.

### P0-4: Tutor sessions are a global Python dictionary

The process-local dictionary has no owner binding, expiry, persistence, capacity limit, or cross-worker consistency.

**Impact:** sessions disappear on restart, differ between workers, can grow without bound, and can be read or changed by a client who obtains another session ID.

**Patch:** `TutorSessionStore` uses SQLite WAL, owner hashes, expiry, payload limits, optimistic versions, and unique random IDs. For multiple app instances, migrate the same interface to Redis or PostgreSQL.

### P0-5: Wildcard CORS is combined with credentials

The server allows `*` origins while enabling credentials.

**Impact:** unsafe or non-functional browser credential behaviour and no explicit production trust boundary.

**Patch:** configure exact origins through `CORS_ORIGINS`. Production defaults to no cross-origin access rather than open access.

### P0-6: Public subscription creation is not tied securely to the authenticated account

The current endpoint accepts an arbitrary email/name and creates Stripe objects directly. Price IDs are hard-coded placeholders and there is no visible idempotency or webhook-led source of truth.

**Impact:** duplicate customers, abuse, subscription/account mismatch, and inconsistent access after delayed or failed payments.

**Required redesign:**

- require the authenticated parent account;
- create a Stripe Checkout Session server-side using server-owned price IDs;
- include the account ID in Stripe metadata;
- use an idempotency key;
- grant/revoke access only from verified Stripe webhook events;
- verify webhook signatures;
- store Stripe customer ID once per parent account;
- never accept an arbitrary customer email as the entitlement owner.

This package does not attempt a full billing migration because it requires your real Stripe products, webhook endpoint, and business rules.

## High-priority reliability and performance findings

### P1-1: Blocking work inside `async def`

Several async handlers directly call synchronous SQLite, Chroma, Stripe, OCR, and SDK functions. A regular utility function called inside an async route is not automatically placed in FastAPI's thread pool.

**Impact:** one slow database lock, OCR operation, embedding call, or LLM request can stall unrelated users sharing the event loop.

**Patch:** account routes use `asyncio.to_thread`; progress queries are patched similarly; `run_blocking()` provides a bounded worker bulkhead and timeout. Continue migrating every synchronous call in async routes.

### P1-2: No admission control for costly AI requests

Without a queue/bulkhead, traffic spikes can produce too many simultaneous LLM/OCR jobs and exhaust threads, memory, provider quotas, or local Ollama capacity.

**Patch:** expensive endpoints share a configurable semaphore and return a child-friendly `503` with `Retry-After` when full. Set separate limits per provider in a later iteration.

### P1-3: SQLite first-request races

The current account migration does `SELECT`, then `INSERT`. Concurrent first requests for the same user can hit a unique constraint. Default-student creation can create duplicates.

**Patch:** WAL, busy timeout, explicit write transactions, `INSERT OR IGNORE`, and a partial unique index for one default student per account.

**Scale boundary:** SQLite is suitable for one service node and modest write concurrency. Before multiple application instances or sustained paid traffic, move accounts, subscriptions, messages, and learning progress to managed PostgreSQL. Redis is a better fit for sessions, rate limits, and short-lived cache entries.

### P1-4: Chroma `PersistentClient` is used as production storage

Local persistent Chroma is tied to one filesystem and is not the correct shared state for independently scaled web instances.

**Patch:** the RAG module supports `CHROMA_HOST`/`CHROMA_PORT` for server-backed Chroma and warns when local persistent mode is used.

### P1-5: RAG document IDs can collide

Millisecond timestamps are used for IDs, including within batch loops. Concurrent writes or fast batches can generate duplicate IDs.

**Patch:** UUID-based IDs; duplicates in caller-supplied batches are rejected before the write.

### P1-6: Broken Chinese textbook methods

The constructor comments out `chinese_collection`, but ingestion/search methods still access it.

**Impact:** runtime `AttributeError` when those features are used.

**Patch:** lazy, thread-safe creation of the collection.

### P1-7: Uploads are read fully into memory and share filenames

`await file.read()` buffers the full upload, then writes it under a sanitised original filename. Two simultaneous files named `homework.pdf` can overwrite each other.

**Patch:** stream in chunks to a unique temporary filename, enforce the byte limit during streaming, verify basic file signatures, close the upload, and delete the temporary file after parsing.

**Follow-up:** place OCR/PDF processing in a restricted worker process, cap PDF pages and image dimensions, reject encrypted PDFs, and scan files if uploads are retained.

### P1-8: Production server starts with `reload=True`

Reload mode is a development feature and is unsuitable for production reliability.

**Patch:** reload only when `DEV_MODE=true`; otherwise use `WEB_CONCURRENCY` workers. Do not use more than one worker while state remains local-only.

## Token usage and latency

### What currently wastes tokens

- Full homework, full student answers, full profile, full review feedback, and full RAG answers can all be sent together.
- Correct answers already used to build a deterministic table are repeated in the LLM context.
- Cache keys use only the first 200 characters, which can create false cache hits and incorrect feedback.
- Natural-language profile parsing invokes an LLM when structured fields are already available.

### Changes included

- `budget_review_inputs()` removes unnecessary profile fields and caps each text section.
- RAG answer context is capped before prompt formatting.
- `stable_cache_key()` hashes complete compacted inputs rather than truncated prefixes.
- A helper prioritises incorrect/unanswered items so later prompt refactors can omit correct rows.

### Recommended request pipeline

1. Validate and normalise the question locally.
2. Retrieve the exact RAG document by `doc_id`, not semantic search, when the question came from your library.
3. Mark objective Maths and short-answer questions deterministically.
4. Build the result table without an LLM.
5. If every answer is correct, use a short template response and make **zero** LLM calls.
6. If feedback is needed, send only incorrect/unanswered items, the child's year group, and a strict output budget.
7. Route simple feedback to a small/fast model; reserve a stronger model for ambiguous English reasoning.
8. Cache by model version, prompt version, complete normalised inputs, and RAG document version.
9. Stream longer explanations to improve perceived latency.

## Child-friendly and safeguarding review

### Language and interaction

- Keep sentences short and explain one step at a time.
- Avoid shame, rankings, or messages such as “You failed”. Use “Let’s fix this step together”.
- Do not reveal the answer immediately in tutor mode; use one hint, then a worked step, then the answer.
- Do not create addictive streak pressure or dark patterns.
- Make the parent account the data controller-facing identity; students should use a first name or nickname, not an email.
- Do not ask a child to enter a full date of birth, home address, school, exact location, phone number, or personal story unless strictly necessary.

### Model safety

- Treat homework text, uploads, and RAG documents as untrusted data, never as system instructions.
- Separate system policy from retrieved text with clear delimiters.
- Never let model output choose admin actions, database filters, file paths, or payment operations.
- Add age-appropriate content filtering for sexual, violent, self-harm, bullying, illegal, and contact-seeking content.
- For safeguarding disclosures, provide a calm response and direct the child to a trusted adult; do not attempt counselling or investigation.
- Keep a reviewed set of refusal and escalation messages suitable for ages 5–11.

## UK GDPR / Children's Code work required

This is an engineering review, not legal advice. Before launch, complete a DPIA and document the lawful basis and retention period for every data category.

Minimum product changes:

- high-privacy defaults;
- data minimisation by feature;
- parent-facing privacy notice plus a child-friendly summary;
- no behavioural advertising or unnecessary profiling;
- no raw child homework in general application logs;
- configurable deletion/retention jobs for uploads, conversations, support messages, progress, traces, and backups;
- parent export and erasure workflows that cover every datastore and third-party processor;
- processor agreements and data-location review for LLM, email, analytics, Stripe, hosting, logging, and vector database providers;
- role-based staff access and an audit log for admin reads/changes;
- separate production, staging, and development data;
- secret rotation and incident response procedures.

## Observability and site reliability

Add service-level objectives and dashboards for:

- availability and error rate by endpoint;
- p50/p95/p99 latency;
- queue wait and active AI jobs;
- LLM provider timeout/error/rate-limit counts;
- tokens and cost by feature, model, and subscription tier;
- RAG exact-hit/fallback rate and answer-version mismatch;
- SQLite lock retries or PostgreSQL pool saturation;
- OCR/PDF failure and rejection counts;
- email/webhook delivery lag;
- cache hit ratio and stale-result reports.

Never store raw homework, answers, child names, emails, access tokens, or model prompts in high-volume telemetry by default. Use redacted samples only with strict access and short retention.

## Testing gaps found

The repository already has unit tests for question parsing, review services, account storage, messages, and tutor-mode API behaviour. Important missing suites are:

- every admin route returns `401/403` to non-admin users;
- one account cannot read another student's progress/session/message;
- concurrent account/default-student creation;
- concurrent tutor-session update and worker restart;
- upload same-name race, oversize, fake extension, decompression bomb, and cleanup;
- CORS/security headers/CSRF behaviour;
- Stripe webhook signature and idempotency;
- RAG concurrent IDs, old metadata compatibility, and answer/index alignment;
- prompt-injection and XSS payloads through model/RAG/upload content;
- child-safety response golden tests;
- load test with realistic slow LLM latency and provider failures.

The package adds 11 focused tests for session ownership/concurrency, account races, RAG IDs, prompt budgets, admin guarding, and sanitisation contracts.

## Suggested deployment sequence

1. Apply the patch in a new branch.
2. Set production environment variables and secrets.
3. Run compilation, unit tests, and frontend contract tests.
4. Manually verify parent login, student switching, tutor mode, exact RAG marking, subscription checks, admin access, uploads, and deletion.
5. Add Stripe webhook-led entitlements before accepting payments.
6. Load test one instance; then move sessions to Redis and relational data to PostgreSQL before horizontal scaling.
7. Run a security review and child-data DPIA before inviting real families.
