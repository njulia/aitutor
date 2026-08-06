# 11+ Year-Round Plan Update

## What changed

- Multiple-choice weekly questions are shown as selectable options instead of a text box.
- Before marking, the page receives and displays only question stems and options.
- Weekly retrieval uses an exact `year_group + subject + week_num` RAG filter.
- Year-round RAG records now use separate internal subject keys: `Maths-11+`, `English-11+`, `VerbalReasoning-11+`, and `NonVerbalReasoning-11+`.
- The page keeps child-friendly labels while sending the new internal keys.
- Older `VerbalReasoning` and `NonVerbalReasoning` metadata names remain supported.
- RAG marking returns the correct option, a worked explanation, and a helpful 11+ tip for each question without calling the LLM.
- If the selected week is missing from RAG, the LLM fallback is told to create three questions for that exact week's goals.
- The default 11+ Chroma path now points to the project's `data/chroma_11plus_db` directory.
- Year-round ingestion uses `upsert`, so deterministic weekly document IDs can be regenerated safely.

## Rebuild the four weekly RAG sets

Run these commands from the project root:

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

The compatibility parser can read the older records, so deleting the old collection first is not required.

## Verification

- Python compilation: passed
- Inline JavaScript syntax check: passed
- Automated tests: **55 passed, 9 skipped**
- Skips: six browser tests require `RUN_E2E=1` and Playwright Chromium; three Chroma integration tests require ChromaDB in the test environment.
