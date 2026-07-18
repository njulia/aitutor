# 11+ Year-Round Subject Key Update

The 52-week plan now uses separate internal RAG subject keys:

| Friendly label | RAG subject key |
|---|---|
| Maths | `Maths-1year` |
| English | `English-1year` |
| Verbal Reasoning | `VerbalReasoning-1year` |
| Non-Verbal Reasoning | `NonVerbalReasoning-1year` |

Ordinary 11+ practice still uses the existing friendly subject names. Only requests containing a valid `plan_week` from 1 to 52 are converted to the new keys.

## Files updated

- The four subject-specific year-round generators and the older Maths wrapper generator.
- `/api/subjects`, which now returns `eleven_plus_year_round` separately from `eleven_plus`.
- The 11+ year-round browser page, which sends the internal keys but displays friendly labels.
- Exact RAG lookup and legacy aliases.
- Homework generation, marking, prompt labels and progress display.
- API and unit tests.

## Rebuild the year-round RAG records

Run from the project root:

```bash
python scripts/elevenplus/elevenplus_math_year_round_plan_generator.py
python scripts/elevenplus/elevenplus_english_year_round_plan_generator.py
python scripts/elevenplus/elevenplus_vr_year_round_plan_generator.py
python scripts/elevenplus/elevenplus_nvr_year_round_plan_generator.py
```

With Docker Compose:

```bash
docker compose exec app python scripts/elevenplus/elevenplus_math_year_round_plan_generator.py
docker compose exec app python scripts/elevenplus/elevenplus_english_year_round_plan_generator.py
docker compose exec app python scripts/elevenplus/elevenplus_vr_year_round_plan_generator.py
docker compose exec app python scripts/elevenplus/elevenplus_nvr_year_round_plan_generator.py
```

The lookup checks each new key first. It falls back to older year-round keys only when no new-key record exists, so a rolling deployment remains compatible.

## Verification

- Python compilation: passed
- Inline JavaScript syntax checks: passed
- Automated tests: **55 passed, 9 skipped**
- Six browser tests require a running app with `RUN_E2E=1`.
- Three ChromaDB integration tests require ChromaDB in the test environment.
