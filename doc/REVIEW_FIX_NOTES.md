# Review reliability, privacy and latency refactor

Updated: 16 July 2026

## Fixed

- 11+ year-round answer checking no longer switches to API-only model names such as `qwen-flash` when using Ollama.
- "Explain in Detail" for RAG/library questions no longer switches to `qwen-plus` or fails when that model is not installed locally.
- Detailed-review and targeted-practice request models now include `homework_doc_id`, `question_index`, and `is_eleven_plus` consistently.
- Multi-subject generated homework is reviewed against each block's own document ID and answer key instead of reusing the first block's key.

## Lower latency and cost

- RAG/library answers are marked and explained locally from the trusted stored answer records. No LLM call is made for quick or detailed RAG review.
- Separate homework blocks and optional year-round review subjects are checked in parallel in the browser.
- Common profile descriptions are parsed locally. Whole-word subject matching prevents `Art` being incorrectly detected inside words such as `particular`.
- Provider token limits are bounded integers, and Ollama keeps its configured local model unless an explicit local review model is set.

Optional Ollama overrides:

```dotenv
OLLAMA_QUICK_REVIEW_MODEL=qwen2.5:7b
OLLAMA_DETAIL_REVIEW_MODEL=qwen2.5:7b
```

If these are omitted, the application uses `OLLAMA_MODEL` for review calls.

## Child privacy and safety

- Review prompts receive only bounded age/year/learning context for ages 5-12; child identifiers and free-text descriptions are excluded.
- Common profile text has email addresses, phone numbers, UK postcodes, names at the start of the description, and unnecessary locations removed before an LLM fallback.
- Anonymous homework and answers are not stored in progress history.
- Langfuse remains privacy-first: content capture is still off by default and request tracing continues to use pseudonymous identifiers.

## Validation

```text
Python compile checks: passed
JavaScript syntax check: passed
Unit/API suite: 70 passed, 6 browser tests skipped by their RUN_E2E guard
```

The browser tests require the `pytest-playwright` plugin and installed Playwright browser binaries from `requirements-dev.txt`.
