# AI Tutor RAG and Performance Fixes

## Behaviour now

1. Homework generation searches PGVector by exact metadata first:
   - primary: `year_group + subject`
   - 11+ year-round: `year_group + subject + week_num + content_type`
2. An unseen matching RAG document is returned without calling the LLM.
3. The LLM is called only when no unseen exact RAG item is available.
4. LLM-generated homework is stored back in PGVector with a private structured answer key.
5. RAG answer marking is deterministic and does not call the LLM.

## Main fixes

- Made sentence-transformer embeddings lazy and process-wide. Metadata-only retrieval and answer lookup no longer load the embedding model.
- Added PostgreSQL metadata and optional HNSW indexes.
- Replaced row-by-row vector upserts with batched conflict-safe upserts.
- Added a bounded SQLite vector fallback for tests and local diagnostics.
- Fixed PostgreSQL-only delete/filter SQL that failed under SQLite tests.
- Fixed `Explain Deep` and `Improve Practice` wrapper argument errors.
- Fixed timeout HTTP errors being changed into generic 500 responses.
- Fixed `homework_manager.py` unpacking the old two-value generator result.
- Removed duplicate cache definitions that silently disabled the optional Redis cache.
- Prevented private LLM answer sections from reaching the browser.
- Added local subject/year parsing before profile LLM parsing.
- Reduced generation, review, explanation and practice prompt/output budgets.
- Replaced stale Chroma test assumptions with PGVector-compatible tests.

## Useful environment settings

```env
# Existing default for all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Prompt size limits
REVIEW_HOMEWORK_MAX_CHARS=8000
REVIEW_ANSWERS_MAX_CHARS=4000
REVIEW_FEEDBACK_MAX_CHARS=2000

# PGVector/RAG bounds
RAG_MAX_QUERY_RESULTS=50
RAG_MAX_RETRIES=3
RAG_RETRY_DELAY=0.4
```

Keep `EMBEDDING_DIMENSION` equal to the dimension used by the existing database column and embedding model. Changing it requires rebuilding/re-embedding the vector table.

## Verification

```text
60 passed, 6 skipped
```

The six skipped tests are browser E2E tests that require a running web server and `RUN_E2E=1`.

## Year 2 Maths false RAG miss fix

The message `No unseen exact candidate` previously combined two different states:

1. no matching rows existed in the active database; or
2. matching rows existed, but the newest 50 had already been assigned to that learner.

The generator now loads the learner's assigned document IDs and excludes them in the PostgreSQL metadata query. This lets it retrieve row 51 and later rows without an embedding or LLM call. Logs now include the password-free database target, exact row count, and seen row count when an actual miss occurs.

Diagnostic command:

```bash
python scripts/diagnose_rag.py --year 2 --subject Maths --learner YOUR_STUDENT_ID
```

## PyCharm ingestion database fix (2026-07-15)

The web application loaded `.env` before importing the PGVector layer, but the
Maths ingestion script did not. When run from PyCharm without explicit Run
Configuration environment variables, ingestion could therefore use the
relative SQLite fallback (`test_vector.db`) while the website queried
PostgreSQL. This produced `exact_in_database=0` even after generation.

Fixes:

- `scripts/homework_math_generator.py` now resolves the project root correctly,
  loads the project `.env` before any RAG import, prints the password-free RAG
  database target, and refuses silent SQLite ingestion unless
  `--allow-sqlite` is explicitly supplied.
- `scripts/diagnose_rag.py` now loads the same project `.env` and reports whether
  `PGVECTOR_DATABASE_URL`, `DATABASE_URL`, or the SQLite fallback selected the
  database.
- `src/pgvector_store.py` now prefers `PGVECTOR_DATABASE_URL` and falls back to
  `DATABASE_URL`, allowing RAG and application data to have explicit URLs.
- `launch.py` loads `.env`, changes to the project root, and starts `web_app.py`
  by absolute path, so PyCharm's Working directory setting cannot redirect
  relative database or static-file paths.

Recommended Year 2 ingestion command:

```bash
python scripts/homework_math_generator.py --year 2
```

The command must print a PostgreSQL target before generation, for example:

```text
RAG target: postgresql://localhost:5432/aitutor
```
