# CORRECTED: Voice Tracking for PGVectorStore-based homework_rag.py
# This version uses PGVectorStore (PostgreSQL) instead of ChromaDB

# ===== FIX 1: Remove the __init__ voice collection setup =====
# DELETE these lines from __init__ (around line 113-117):
#
#     self.voice_events_collection = self.client.get_or_create_collection(
#         name="voice_usage_events",
#         embedding_function=self.embedding_function,
#         metadata={"hnsw:space": "cosine"},
#     )
#
# Replace with: (nothing — voice events go into the same PGVectorStore as homework)

# ===== FIX 2: Replace log_voice_event method (around line 119-182) =====
# Delete the old method and replace with this:

    def log_voice_event(
            self,
            event_type: str,  # 'tts_used' or 'stt_used'
            year_group: int,
            subject: str,
            student_id: str = None,
    ) -> str:
        """Log a single voice-feature usage event to PGVectorStore.

        Args:
            event_type: 'tts_used' (read aloud) or 'stt_used' (speech input)
            year_group: UK year group (1-6)
            subject: Subject name
            student_id: Optional student identifier

        Returns:
            Event ID
        """
        now = datetime.now(UTC)
        event_id = _new_doc_id("voice_event")
        
        # Minimal document content for voice events (not searched semantically)
        doc_content = f"Voice event: {event_type} in {subject} (Year {year_group})"
        
        metadata = {
            "event_type": event_type,
            "year_group": year_group,
            "age": year_group + 4,  # Convention: age = 5 + (year_group - 1)
            "subject": subject,
            "student_id": student_id or "",
            "created_at": now.isoformat(),
            "is_voice_event": True,  # Tag so we can filter voice events specifically
        }
        sanitized = self._sanitize_metadata(metadata)
        
        def add():
            # Use minimal embedding since these aren't searched
            embeddings = self.embedding_function([doc_content])
            self.store.add_documents(
                texts=[doc_content],
                metadatas=[sanitized],
                ids=[event_id],
                embeddings=embeddings
            )
        
        self._retry_write(add, f"log voice event {event_id}")
        logger.info(f"[RAG] Logged voice event: {event_type} (Y{year_group}, {subject})")
        return event_id


    def get_voice_usage_stats(self) -> Dict[str, Any]:
        """Aggregate voice usage by age and subject from PGVectorStore.

        Returns:
            Dictionary with:
            - total_events: int
            - by_age: {age: count}
            - by_subject: {subject: count}
            - by_event_type: {event_type: count}
        """
        # Query all voice events using metadata filter
        try:
            voice_events = self.store.get_by_metadata(
                filters={"is_voice_event": True},
                k=MAX_QUERY_RESULTS,  # Get up to MAX_QUERY_RESULTS (default 50, configurable)
                offset=0
            )
        except Exception as e:
            logger.error("[RAG] Failed to fetch voice events: %s", e)
            return {
                "total_events": 0,
                "by_age": {},
                "by_subject": {},
                "by_event_type": {},
                "error": str(e)
            }
        
        total = len(voice_events)
        by_age: Dict[Any, int] = {}
        by_subject: Dict[str, int] = {}
        by_event_type: Dict[str, int] = {}
        
        for event in voice_events:
            meta = event.get("metadata", {})
            age = meta.get("age", "Unknown")
            subject = meta.get("subject", "Unknown")
            event_type = meta.get("event_type", "Unknown")
            
            by_age[age] = by_age.get(age, 0) + 1
            by_subject[subject] = by_subject.get(subject, 0) + 1
            by_event_type[event_type] = by_event_type.get(event_type, 0) + 1
        
        return {
            "total_events": total,
            "by_age": by_age,
            "by_subject": by_subject,
            "by_event_type": by_event_type,
        }


# ===== FIX 3: Replace module-level convenience functions =====
# Find these functions at the end (around line 634+) and replace:

def log_voice_event(event_type: str, year_group: int, subject: str, student_id: str = None) -> str:
    """Convenience function: log a voice usage event.

    Args:
        event_type: 'tts_used' or 'stt_used'
        year_group: UK year group (1-6)
        subject: Subject name
        student_id: Optional student ID

    Returns:
        Event ID
    """
    store = get_homework_rag_store()
    return store.log_voice_event(event_type, year_group, subject, student_id)


def get_voice_usage_stats() -> Dict[str, Any]:
    """Convenience function: get aggregated voice usage statistics.

    Returns:
        Stats dictionary with total_events, by_age, by_subject, by_event_type
    """
    store = get_homework_rag_store()
    return store.get_voice_usage_stats()


# ===== KEY DIFFERENCES FROM OLD CODE =====
# 
# OLD (ChromaDB-based):
#   - Used separate voice_events_collection via ChromaDB client
#   - No retry logic needed
#   - Direct ChromaDB API calls
#
# NEW (PGVectorStore-based):
#   - Uses same PGVectorStore as homework documents
#   - Wrapped in _retry_write() for thread safety & resilience
#   - Uses self.store.add_documents() and self.store.get_by_metadata()
#   - Filters on is_voice_event=True to separate voice events from homework
#   - Handles pagination with MAX_QUERY_RESULTS
#
# ===== CAVEAT =====
#
# If you have >50 voice events (MAX_QUERY_RESULTS), get_voice_usage_stats()
# will only return stats for the first 50. This is fine for Tier 0 testing.
#
# If you later scale voice features and need pagination:
#   - Loop through offsets: 0, 50, 100, 150, ... until store.get_by_metadata() returns empty
#   - Aggregate results into the by_age/by_subject/by_event_type dicts
#
# For now, just increase MAX_QUERY_RESULTS in the env if needed:
#   RAG_MAX_QUERY_RESULTS=1000
