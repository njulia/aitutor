# ===== ADD THESE METHODS TO HomeworkRAGStore CLASS IN homework_rag.py =====
# Insert after __init__ method and before the existing add_homework method

# In __init__, add this line after self.collection initialization:
#
#     self.voice_events_collection = self.client.get_or_create_collection(
#         name="voice_usage_events",
#         embedding_function=self.embedding_function,
#         metadata={"hnsw:space": "cosine"},
#     )


# Then add these methods to HomeworkRAGStore class:

    def log_voice_event(
        self,
        event_type: str,       # 'tts_used' or 'stt_used'
        year_group: int,
        subject: str,
        student_id: str = None,
    ) -> str:
        """Log a single voice-feature usage event.
        
        Args:
            event_type: 'tts_used' (read aloud) or 'stt_used' (speech input)
            year_group: UK year group (1-6)
            subject: Subject name
            student_id: Optional student identifier
            
        Returns:
            Event ID
        """
        now = datetime.now()
        event_id = f"voice_{int(now.timestamp() * 1000)}"
        metadata = {
            "event_type": event_type,
            "year_group": year_group,
            "age": year_group + 4,  # Convention: age = 5 + (year_group - 1)
            "subject": subject,
            "student_id": student_id,
            "created_at": now.isoformat(),
        }
        sanitized = self._sanitize_metadata(metadata)
        self.voice_events_collection.add(
            documents=[f"{event_type} | year {year_group} | {subject}"],
            metadatas=[sanitized],
            ids=[event_id],
        )
        logger.info(f"[RAG] Logged voice event: {event_type} (Y{year_group}, {subject})")
        return event_id


    def get_voice_usage_stats(self) -> Dict[str, Any]:
        """Aggregate voice usage by age and subject.
        
        Returns:
            Dictionary with:
            - total_events: int
            - by_age: {age: count}
            - by_subject: {subject: count}
            - by_event_type: {event_type: count}
        """
        all_events = self.voice_events_collection.get()
        total = len(all_events["ids"]) if all_events.get("ids") else 0

        by_age: Dict[Any, int] = {}
        by_subject: Dict[str, int] = {}
        by_event_type: Dict[str, int] = {}

        for meta in (all_events.get("metadatas") or []):
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


# ===== ADD THESE MODULE-LEVEL FUNCTIONS AT END OF homework_rag.py =====
# (After the existing search_homework_answers and other convenience functions)

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
