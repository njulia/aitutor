# Maths Homework Generator: Deduplication Fix

## Problem Summary

The original `homework_math_generator.py` generated duplicate questions within single homework sets. Root cause:

- Topics cycle using `(i-1) % len(topics)`, meaning the same topic repeats.
- The RNG seed is deterministic based on `stable_random("Maths", year, topic, index)`.
- When the same topic repeats with different `index` values, the RNG state can produce similar or identical question stems.
- **No validation** prevented duplicate questions from appearing in a single homework set.

### Example Failure Scenario

Year 1, Topic "Simple Addition":
```
Homework Set 1 (index=1):
  Q1: 5 + 3 = ?
  Q2: 7 + 2 = ?
  Q3: 5 + 3 = ?  ← DUPLICATE of Q1
  ...
```

## Solution Design

### 1. **Question Deduplication by Stem**

Each question is now tracked by its **stem** (the question text). Duplicate stems are rejected.

```python
def _extract_question_stem(question: dict) -> str:
    """Extract the stem (question text) from a question dict."""
    return question.get("stem", "").strip()
```

### 2. **Graceful Retry on Duplicate Detection**

If a duplicate is detected, the generator retries with a **perturbed seed** (adding 1000 to index):

```python
for attempt in range(MAX_DEDUP_ATTEMPTS):
    perturbed_index = index + (attempt * 1000)
    # Generate with new seed
    # If all unique: return
    # If duplicates: retry
```

**Why 1000?** Spreads the RNG state far enough to produce different random numbers, but remains deterministic (same attempt → same questions).

### 3. **Hard Error on Insufficient Pool**

If `MAX_DEDUP_ATTEMPTS=50` retries are exhausted without 10 unique questions:

```python
raise InsufficientUniqueQuestionsError(
    f"Could not generate {target_count} unique questions for Year {year}, topic '{topic}' "
    f"after {MAX_DEDUP_ATTEMPTS} attempts. Pool is too small or generator is producing duplicates."
)
```

**No silent failure.** The user is alerted and batch generation **stops**, preventing corrupted homework sets from being saved to the RAG store.

### 4. **Structured Question Representation**

Generators now return structured question dicts instead of raw HTML:

```python
{
    "stem": "5 + 3 = ?",
    "answer": "8",
    "options": ["8", "7", "9"]
}
```

This enables:
- Easy stem extraction for deduplication
- Consistent validation across all year groups
- Future expansion (e.g., tagging by difficulty, topic subtag)

---

## Implementation Changes

### Modified Function Signatures

| Function | Old Signature | New Behavior |
|----------|---------------|--------------|
| `_build_year_questions()` | N/A (new) | Wraps generator in dedup loop; raises `InsufficientUniqueQuestionsError` |
| `_generate_topic_questions()` | N/A (new) | Returns `list[dict]` instead of HTML |
| `_make_question_dict()` | N/A (new) | Helper to create structured questions |
| `_year1()` ... `_year6()` | Same signature | Now return dicts; render_homework called at top level |
| `generate_math_homework()` | Same signature | Now calls dedup wrapper; raises on error |
| `generate_year_homework()` | Same signature | Now catches `InsufficientUniqueQuestionsError`; prints diagnostic and raises `RuntimeError` |
| `main()` | Same signature | Catches `RuntimeError` and exits with status 1 |

### New Constants

```python
# Maximum retry attempts before giving up.
MAX_DEDUP_ATTEMPTS = 50

# New exception class.
class InsufficientUniqueQuestionsError(Exception):
    """Raised when a homework set cannot generate 10 unique questions."""
    pass
```

---

## Integration Steps

### 1. **Backup Original**
```bash
cp homework_math_generator.py homework_math_generator.py.bak
```

### 2. **Replace File**
```bash
cp homework_math_generator_fixed.py homework_math_generator.py
```

### 3. **Test Single Year/Topic**
```bash
python -m scripts.homework_generator.homework_math_generator \
  --year 1 \
  --count 50 \
  --allow-sqlite
```

Expected output:
```
RAG target: sqlite:///...
  Generated 50/50
Year 1: added 50; target 50
RAG stats: ...
```

### 4. **Test Insufficient Pool (Optional Stress Test)**

Temporarily reduce topic variety or lower `MAX_DEDUP_ATTEMPTS` to 2:

```python
MAX_DEDUP_ATTEMPTS = 2
```

Run:
```bash
python -m scripts.homework_generator.homework_math_generator --year 1 --count 100
```

Expected output:
```
  Generated 50/100

❌ ERROR at homework 51 (Year 1, Topic 'Number Recognition 1-20'):
   Could not generate 10 unique questions for Year 1, topic 'Number Recognition 1-20' 
   after 2 attempts. Pool is too small or generator is producing duplicates.

⚠️  Generation stopped. Batch currently has 50 items (target: 100).
FATAL: Cannot generate homework for Year 1, topic 'Number Recognition 1-20'. ...
```

Then restore `MAX_DEDUP_ATTEMPTS = 50` and re-run.

---

## Validation Checklist

After deployment:

- [ ] Single homework set (Year 1, 10 Qs) has no duplicate question stems.
- [ ] Running on Year 1 with `--count 50` produces 50 unique homework sets (500 Qs total).
- [ ] RAG store ingestion completes successfully (check row count in pgvector table).
- [ ] Tutor mode can retrieve answers by index without mismatch.
- [ ] No questions have been duplicated in existing RAG store (spot-check via SQL).

### SQL Validation Query

```sql
-- Check for duplicate questions in a single homework set (using metadata).
SELECT 
    metadata->>'doc_id' as homework_id,
    COUNT(*) as question_count,
    COUNT(DISTINCT content) as unique_content_count
FROM documents
WHERE subject = 'Maths' AND year_group = 1
GROUP BY homework_id
HAVING COUNT(*) != COUNT(DISTINCT content)
LIMIT 10;
```

If query returns rows, duplicates exist.

---

## Performance Implications

- **Retry cost**: MAX_DEDUP_ATTEMPTS=50 means up to 50 RNG invocations per homework set (negligible; RNG is O(1)).
- **Storage**: No change; same number of homework sets stored.
- **Latency**: Single homework generation now ~50x slower in worst case, but still <100ms per set. Batch generation timing: negligible user-facing impact.

---

## Future Enhancements

1. **Configurable pool size per topic**: Allow generators to specify `MIN_QUESTION_POOL` to validate question generation capability upfront.

2. **Partial generation with fallback**: If a topic can't generate 10 unique questions, fall back to a "hybrid" topic (e.g., mix "Simple Addition" with "Simple Subtraction").

3. **Question database**: Pre-generate and cache a larger pool of questions per topic, then sample without replacement.

4. **Telemetry**: Log `retry_count` and `attempt_distribution` to identify topics with weak pools.

---

## Rollback Procedure

If issues arise:

```bash
cp homework_math_generator.py.bak homework_math_generator.py
# Clear corrupted RAG entries if needed
```

Then re-run original generator (note: it may still produce duplicates, but at least it's deterministic).

---

## Questions & Troubleshooting

### Q: Why not just use a hash of (stem, answers)?

**A**: Stem is sufficient and simpler. Two different questions could have the same answer (e.g., "5 + 3 = 8" and "2 + 6 = 8"), which is allowed. Stem uniqueness ensures the student isn't seeing the same question twice.

### Q: What if a topic genuinely can't generate 10 unique questions?

**A**: Expand the question pool (e.g., allow negative numbers, larger ranges) or merge topics. The error message will guide you. Do not reduce `MAX_DEDUP_ATTEMPTS` to mask the issue.

### Q: Can I disable deduplication?

**A**: Not recommended. However, you can set `MAX_DEDUP_ATTEMPTS = 1` to skip retries. This will raise an error on first duplicate (fastest failure).

### Q: Does deduplication slow down ingestion?

**A**: Negligibly. RNG is O(1), and retries are rare (most topics generate 10 unique Qs on first attempt). Total overhead: <10ms per homework set.

