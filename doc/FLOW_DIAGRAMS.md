# Maths Generator: Deduplication Flow Diagrams

## 1. Original Flow (Problematic)

```
generate_year_homework(year=1, count=500)
│
└─→ for i in range(1, 501):
    │
    ├─→ topic = topics[(i-1) % len(topics)]   # Cycles: topic A, B, C, ... A, B, C, ...
    │
    ├─→ generate_math_homework(year=1, topic="Simple Addition", index=i)
    │   │
    │   └─→ _year1("Simple Addition", i)
    │       │
    │       ├─→ rng = stable_random("Maths", 1, "Simple Addition", i)
    │       │
    │       └─→ Generate 10 questions
    │           Q1: "5 + 3 = ?"
    │           Q2: "7 + 2 = ?"
    │           Q3: "5 + 3 = ?"  ← DUPLICATE! (RNG coincidence)
    │           ...
    │
    └─→ build_batch_item(content, answers)
        │
        └─→ ✅ Add to batch (NO VALIDATION!)
            ❌ Duplicates silently added to RAG store
```

**Problem:** No deduplication → corrupted homework in RAG.

---

## 2. Fixed Flow (With Deduplication)

```
generate_year_homework(year=1, count=500)
│
└─→ for i in range(1, 501):
    │
    ├─→ topic = topics[(i-1) % len(topics)]
    │
    ├─→ generate_math_homework(year=1, topic="Simple Addition", index=i)
    │   │
    │   └─→ Try to generate 10 unique questions
    │       │
    │       └─→ _build_year_questions(year=1, topic, index=i, target_count=10)
    │           │
    │           └─→ for attempt in range(MAX_DEDUP_ATTEMPTS=50):
    │               │
    │               ├─→ perturbed_index = i + (attempt * 1000)
    │               │
    │               ├─→ _year1(topic, perturbed_index)
    │               │   │
    │               │   └─→ Generate 10 questions
    │               │       (RNG state differs due to perturbed_index)
    │               │
    │               ├─→ Extract stems from questions
    │               │
    │               ├─→ Remove duplicates (keep unique stems)
    │               │
    │               ├─→ if len(unique_questions) >= 10:
    │               │   │
    │               │   └─→ ✅ RETURN unique_questions[:10]
    │               │       Done! Continue to next homework set.
    │               │
    │               └─→ if attempt < 49:
    │                   └─→ Retry with next perturbed_index
    │
    │           (After 50 attempts, if still < 10 unique)
    │           └─→ ❌ raise InsufficientUniqueQuestionsError(...)
    │               │
    │               └─→ Propagates up
    │
    ├─→ except InsufficientUniqueQuestionsError as e:
    │   │
    │   ├─→ print(f"ERROR at homework {i}: {e}")
    │   │
    │   ├─→ print(f"Batch has {len(batch)} items (target: 500)")
    │   │
    │   └─→ ❌ raise RuntimeError(...)
    │       │
    │       └─→ Stops batch generation
    │
    └─→ build_batch_item(content, answers)
        │
        └─→ ✅ Add to batch (ALL 10 QS UNIQUE)
            ✅ Ingests into RAG with guarantee: no duplicates
```

**Benefit:** Deduplication guaranteed → clean homework in RAG.

---

## 3. Deduplication Inner Loop (Detailed)

```
┌─ Attempt 0 (index + 0*1000 = index) ─────────────────────────────┐
│                                                                    │
│  rng = stable_random("Maths", 1, "Simple Addition", i)            │
│                                                                    │
│  Generate:                                                         │
│    Q1: "5 + 3 = ?" → stem="5 + 3 = ?"                            │
│    Q2: "7 + 2 = ?" → stem="7 + 2 = ?"                            │
│    Q3: "5 + 3 = ?" → stem="5 + 3 = ?"  ← DUPLICATE              │
│    Q4: "9 + 1 = ?" → stem="9 + 1 = ?"                            │
│    Q5-Q10: ...                                                     │
│                                                                    │
│  Seen stems = {"5 + 3 = ?", "7 + 2 = ?", "9 + 1 = ?", ...}       │
│  Unique count = 9 (out of 10 generated)                           │
│  9 < 10? YES → Retry                                              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                            ↓
┌─ Attempt 1 (index + 1*1000) ──────────────────────────────────────┐
│                                                                    │
│  rng = stable_random("Maths", 1, "Simple Addition", i+1000)      │
│  (Different seed → different random sequence)                     │
│                                                                    │
│  Generate:                                                         │
│    Q1: "8 + 4 = ?" → stem="8 + 4 = ?"                            │
│    Q2: "6 + 1 = ?" → stem="6 + 1 = ?"                            │
│    Q3: "3 + 7 = ?" → stem="3 + 7 = ?"                            │
│    Q4: "2 + 9 = ?" → stem="2 + 9 = ?"                            │
│    Q5-Q10: ...                                                     │
│                                                                    │
│  Seen stems = {"8 + 4 = ?", "6 + 1 = ?", "3 + 7 = ?", ...}      │
│  Unique count = 10 (all unique!)                                  │
│  10 >= 10? YES → ✅ RETURN [Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9, Q10]
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Error Path: Insufficient Pool

```
MAX_DEDUP_ATTEMPTS = 50 exhausted
│
└─→ for attempt in range(50):
    │
    ├─→ attempt=0: unique=9 < 10 ✗
    ├─→ attempt=1: unique=8 < 10 ✗
    ├─→ attempt=2: unique=9 < 10 ✗
    ├─→ attempt=3: unique=9 < 10 ✗
    ├─→ ...
    ├─→ attempt=49: unique=8 < 10 ✗
    │
    └─→ Loop exits (no return)

❌ raise InsufficientUniqueQuestionsError(
       f"Could not generate 10 unique questions for Year 1, topic 'Money (Coins)' "
       f"after 50 attempts. Pool is too small or generator is producing duplicates."
   )
   │
   └─→ Caught in generate_year_homework()
       │
       ├─→ print(f"❌ ERROR at homework 42 (Year 1, Topic 'Money (Coins)'):")
       ├─→ print(f"   Could not generate 10 unique questions...")
       ├─→ print(f"⚠️  Generation stopped. Batch currently has 41 items (target: 500).")
       │
       └─→ ❌ raise RuntimeError(
              f"Cannot generate homework for Year 1, topic 'Money (Coins)'. "
              f"Question pool is too small."
          )
           │
           └─→ Caught in main()
               │
               ├─→ print(f"❌ FATAL: Cannot generate homework for Year 1, topic...")
               │
               └─→ sys.exit(1)  # Exit code 1 (failure)
```

---

## 5. Stem Extraction Logic

```
Question dict:
{
    "stem": "5 + 3 = ?",
    "answer": "8",
    "options": ["8", "7", "9"]
}
│
└─→ _extract_question_stem(question)
    │
    ├─→ stem = question.get("stem", "").strip()
    │          → "5 + 3 = ?"
    │
    └─→ return stem

Dedup tracking:
┌─────────────────────────────────────┐
│ seen_stems = set()                  │
│ unique_questions = []               │
│                                     │
│ for question in [Q1, Q2, Q3, ...]:  │
│   stem = "5 + 3 = ?"                │
│   if stem not in seen_stems:        │
│     seen_stems.add(stem)            │
│     unique_questions.append(Q)      │
│   else:                             │
│     (skip duplicate)                │
└─────────────────────────────────────┘

Result:
  seen_stems = {"5 + 3 = ?", "7 + 2 = ?", "9 + 1 = ?", ...}
  unique_questions = [Q1, Q2, Q4, Q5, Q6, Q7, Q8, Q9, Q10]
  (Q3 was a duplicate of Q1 and was rejected)
```

---

## 6. State Machine: Single Homework Generation

```
                    ┌──────────────────┐
                    │ START generation │
                    └────────┬─────────┘
                             │
                             v
                    ┌──────────────────┐
                    │ attempt = 0      │
                    └────────┬─────────┘
                             │
                    ┌────────v─────────┐
                    │ attempt < 50?    │
                    └────┬────────┬────┘
                         │        │
                      YES│        │NO
                         │        │
                    ┌────v────┐   │
                    │Generate │   │
                    │10 Q's   │   │
                    │(perturb)│   │
                    └────┬────┘   │
                         │        │
                    ┌────v─────────────────┐
                    │ Deduplicate by stem  │
                    │ count unique         │
                    └────┬────────────┬────┘
                         │            │
            ┌────────────┬┘            │
            │unique >= 10?              │
            │            NO             │
            │            │              │
         YES│            │              │
            v            v              v
        ┌────────┐  ┌─────────┐  ┌────────────────┐
        │RETURN  │  │attempt+ │  │RAISE ERROR     │
        │unique_q│  │attempt+1│  │InsufficientU..│
        │[0:10]  │  │loop back│  │return FAILURE  │
        └────────┘  └─────────┘  └────────────────┘
            │           │              │
            v           v              v
        ┌────────────────────────────────────┐
        │ END: generation result             │
        │ (success or InsufficientUniqueErr) │
        └────────────────────────────────────┘
```

---

## 7. Full Pipeline: Year Group Ingestion

```
main()
│
├─→ Store setup
│
├─→ for year in [1, 2, 3, 4, 5, 6]:
│   │
│   ├─→ Check existing count
│   │   if complete: skip
│   │
│   ├─→ try:
│   │   │
│   │   ├─→ generate_year_homework(year, expected_count=960)
│   │   │   │
│   │   │   ├─→ for i in range(1, 961):
│   │   │   │   │
│   │   │   │   ├─→ topic = topics[(i-1) % len(topics)]
│   │   │   │   │
│   │   │   │   ├─→ generate_math_homework(year, topic, i)
│   │   │   │   │   │
│   │   │   │   │   └─→ _build_year_questions(...)  # ← Dedup happens here
│   │   │   │   │       │
│   │   │   │   │       ├─→ Attempt 0, 1, 2, ... until 10 unique
│   │   │   │   │       │
│   │   │   │   │       └─→ return unique_questions[0:10]
│   │   │   │   │           or raise InsufficientUniqueQuestionsError
│   │   │   │   │
│   │   │   │   ├─→ except InsufficientUniqueQuestionsError:
│   │   │   │   │   │
│   │   │   │   │   ├─→ print("ERROR at homework 42, topic X")
│   │   │   │   │   ├─→ print("Batch stopped at 41/960")
│   │   │   │   │   │
│   │   │   │   │   └─→ raise RuntimeError(...)
│   │   │   │   │       (breaks outer loop)
│   │   │   │   │
│   │   │   │   └─→ build_batch_item(...)
│   │   │   │       └─→ batch.append(...)
│   │   │   │
│   │   │   └─→ return batch (41 items if error, 960 if success)
│   │   │
│   │   ├─→ add_homework_in_batches(store, data)
│   │   │   └─→ Ingest into RAG
│   │   │
│   │   └─→ print(f"Year {year}: added 41; target 960")  # or "added 960; target 960"
│   │
│   └─→ except RuntimeError as e:
│       │
│       ├─→ print(f"❌ FATAL: {e}")
│       │
│       └─→ sys.exit(1)
│
└─→ get_rag_stats(store)
```

---

## 8. Questions Per Homework Set

```
Homework Set #42 (Year 1, Topic "Simple Addition")
├─ Question 1:  "5 + 3 = ?"         [Answer: 8]
├─ Question 2:  "7 + 2 = ?"         [Answer: 9]
├─ Question 3:  "9 + 1 = ?"         [Answer: 10]
├─ Question 4:  "4 + 6 = ?"         [Answer: 10]
├─ Question 5:  "2 + 8 = ?"         [Answer: 10]
├─ Question 6:  "1 + 7 = ?"         [Answer: 8]
├─ Question 7:  "6 + 4 = ?"         [Answer: 10]
├─ Question 8:  "3 + 5 = ?"         [Answer: 8]
├─ Question 9:  "8 + 2 = ?"         [Answer: 10]
└─ Question 10: "10 + 0 = ?"        [Answer: 10]

✅ All stems UNIQUE (checked by dedup loop)
✅ Safe to inggest into RAG
```

---

## Summary

1. **Original:** No dedup → duplicates silently added.
2. **Fixed:** Dedup per set → validation loop with retries → hard error on insufficient pool.
3. **Retry:** Perturb RNG seed (attempt * 1000) to generate different questions.
4. **Graceful failure:** After 50 retries, raise `InsufficientUniqueQuestionsError` (not a silent failure).
5. **User feedback:** Clear diagnostic message showing which homework/topic failed and why.
6. **Safety:** Batch generation stops on error; corrupted homework never ingested.

