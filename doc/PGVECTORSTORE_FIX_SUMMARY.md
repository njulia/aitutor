# PGVectorStore Fix Summary

## The Problem

You got this error when adding voice tracking to `homework_rag.py`:

```
AttributeError: 'HomeworkRAGStore' object has no attribute 'client'
```

**Why:** Your version of `homework_rag.py` uses **PGVectorStore** (PostgreSQL/pgvector), not ChromaDB. The original integration instructions were written for a ChromaDB-based version that has `self.client`.

---

## What Changed

Your actual `HomeworkRAGStore` structure:
```python
class HomeworkRAGStore:
    def __init__(self, persist_directory: Optional[str] = None):
        self._write_lock = threading.RLock()
        self._embedding_function = None
        self.store = PGVectorStore(collection_name="homework_collection")  # ← PostgreSQL, not ChromaDB
        logger.info("[RAG] Using PGVectorStore...")
```

The old instructions tried to do:
```python
self.voice_events_collection = self.client.get_or_create_collection(...)  # ❌ no self.client
```

---

## The Solution

Voice events now go into **the same PGVectorStore** as homework, tagged with `is_voice_event: True`.

### Three changes:

**1. Remove ChromaDB collection init** (was around line 113-117)
   - Delete: `self.voice_events_collection = self.client.get_or_create_collection(...)`
   - Replace with: nothing (voice uses the existing `self.store`)

**2. Rewrite `log_voice_event()` method** to use PGVectorStore:
   ```python
   def log_voice_event(self, event_type, year_group, subject, student_id=None):
       event_id = _new_doc_id("voice_event")
       doc_content = f"Voice event: {event_type} in {subject} (Year {year_group})"
       metadata = {
           "event_type": event_type,
           "year_group": year_group,
           "age": year_group + 4,
           "subject": subject,
           "student_id": student_id or "",
           "is_voice_event": True,  # ← Key: tag for filtering
           "created_at": now.isoformat(),
       }
       def add():
           embeddings = self.embedding_function([doc_content])
           self.store.add_documents(...)  # ← Uses PGVectorStore
       self._retry_write(add, ...)
   ```

**3. Rewrite `get_voice_usage_stats()` method** to query PGVectorStore:
   ```python
   def get_voice_usage_stats(self):
       voice_events = self.store.get_by_metadata(
           filters={"is_voice_event": True},  # ← Filter to just voice events
           k=MAX_QUERY_RESULTS
       )
       # Aggregate by age, subject, event_type...
   ```

---

## File Provided

**`homework_rag.py`** — This is your uploaded file with all three fixes applied. You can replace your version with this one, or apply the changes manually:

1. Find `__init__` and remove the `self.voice_events_collection = ...` lines
2. Find `log_voice_event()` method and replace it with the PGVectorStore version above
3. Find `get_voice_usage_stats()` method and replace it with the PGVectorStore version above

---

## How It Works Now

### Storage

Voice events are stored in PGVectorStore the same way homework is:
- `doc_id` → `voice_event_<uuid>` (e.g., `voice_event_abc123def456`)
- `doc_content` → Short text like `"Voice event: tts_used in Maths (Year 3)"`
- `metadata` → Contains `event_type`, `year_group`, `subject`, `is_voice_event: True`
- `embeddings` → Generated but not semantically searched (voice events aren't search-ranked)

### Query

To get voice stats:
```python
# Get first 50 voice events
voice_events = self.store.get_by_metadata(
    filters={"is_voice_event": True},
    k=50
)

# Aggregate and return stats
```

The `is_voice_event: True` filter ensures we only look at voice events, not homework documents.

---

## Caveats

### Pagination

If you accumulate >50 voice events, `get_voice_usage_stats()` will only see the first 50 (limited by `MAX_QUERY_RESULTS`, default 50).

For testing Tier 0, this is fine. If you later scale voice and need all events:

1. Increase `MAX_QUERY_RESULTS` env var:
   ```bash
   export RAG_MAX_QUERY_RESULTS=1000
   ```

2. Or implement pagination loop:
   ```python
   offset = 0
   while True:
       batch = self.store.get_by_metadata(..., offset=offset)
       if not batch:
           break
       # aggregate batch
       offset += 50
   ```

### Embeddings

Voice events get embeddings (so they're properly stored in PGVectorStore), but they're not meant to be searched semantically. The embedding is just there to satisfy the storage schema.

---

## Testing

After applying this fix:

1. Run your app
2. Open Tutor Mode, click 🎤 (voice) or 🔊 (read aloud)
3. Check logs for: `[RAG] Logged voice event: tts_used (Y3, Maths)`
4. Query stats endpoint:
   ```bash
   curl http://localhost:8000/api/admin/voice-usage-stats
   ```
   Should return:
   ```json
   {
     "success": true,
     "stats": {
       "total_events": 1,
       "by_age": { "7": 1 },
       "by_subject": { "Maths": 1 },
       "by_event_type": { "tts_used": 1 }
     }
   }
   ```

---

## What Didn't Change

- `app.js` — still correct ✅
- `app.html` — still correct ✅
- `web_app.py` endpoints — still correct ✅

Only `homework_rag.py` needed this fix because it's the only file that directly knows about the storage backend (PGVectorStore vs ChromaDB).
