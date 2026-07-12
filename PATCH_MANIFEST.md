# Patch manifest

## Automatically replaced

- `src/webapp/account_store.py`
- `src/webapp/account_routes.py`
- `src/homework_rag.py`

## Automatically added

- `src/webapp/runtime.py`
- `src/webapp/session_store.py`
- `src/webapp/upload_utils.py`
- `src/webapp/prompt_budget.py`
- `static/js/safe_markdown.js`

## Automatically edited

- `web_app.py`
  - safe CORS and middleware
  - global legacy admin protection
  - cookie-backed anonymous identity
  - persistent owner-bound sessions
  - streamed uploads
  - non-blocking progress reads
  - production Uvicorn settings
- `src/webapp/review_service.py`
  - prompt budgets and capped RAG answer context
- `static/app.html`
  - sanitizer scripts
- `static/js/app.js`
  - safe Markdown renderer

## Intentionally not automated

- Stripe Checkout/webhook migration
- PostgreSQL/Redis migration
- deletion/export workflow across third-party processors
- strict enforcing CSP migration (requires removing inline scripts)
- provider-specific model routing and streaming
