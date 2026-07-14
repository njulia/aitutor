from __future__ import annotations

import json
import logging
import os
import random
import re
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Optional

# Standalone 11+ generator scripts import this module directly. Load the same
# project .env file used by launch.py before importing PGVectorStore, because
# pgvector's SQLAlchemy column type is selected when that module is imported.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(PROJECT_DIR, ".env"), override=False)
except ImportError:  # pragma: no cover - python-dotenv is an app dependency
    pass

from .pgvector_store import PGVectorStore

logger = logging.getLogger(__name__)

# Vector storage configuration
RAG_MAX_RETRIES = max(1, min(int(os.getenv("RAG_MAX_RETRIES", "3")), 8))
RAG_RETRY_DELAY = max(0.05, float(os.getenv("RAG_RETRY_DELAY", "0.4")))
MAX_QUERY_RESULTS = max(1, min(int(os.getenv("RAG_MAX_QUERY_RESULTS", "50")), 500))
MAX_DOCUMENT_CHARS = max(1_000, int(os.getenv("RAG_MAX_DOCUMENT_CHARS", "100000")))
STATS_PAGE_SIZE = max(100, min(int(os.getenv("RAG_STATS_PAGE_SIZE", "1000")), 10_000))


def _env_true(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _bounded_k(k: int) -> int:
    try:
        value = int(k)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, MAX_QUERY_RESULTS))

_YEAR_ROUND_BLOCK_RE = re.compile(
    r"Homework Question\s+(?P<number>\d+)\s*:\s*\n"
    r"(?P<question>.*?)\n"
    r"Options:\s*(?P<options>.*?)\n"
    r"Correct Answer:\s*(?:Option\s*)?(?P<letter>[A-H])\s*\((?P<answer>.*?)\)\s*\n"
    r"Explanation:\s*(?P<explanation>.*?)\n"
    r"(?:Coaching Strategy|Coach(?:ing)? Tip):\s*(?P<tip>.*?)"
    r"(?=\n\nHomework Question\s+\d+\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _split_legacy_options(value: str) -> List[str]:
    """Split the old comma-joined option format without breaking 1,000 or quotes."""
    text = str(value or "").strip()
    if not text:
        return []

    parts: List[str] = []
    buffer: List[str] = []
    quote: Optional[str] = None
    index = 0
    while index < len(text):
        char = text[index]
        if char in {'"', "'"}:
            previous = text[index - 1] if index else ""
            following = text[index + 1] if index + 1 < len(text) else ""
            is_apostrophe = char == "'" and previous.isalnum() and following.isalnum()
            if not is_apostrophe:
                if quote is None:
                    quote = char
                elif quote == char:
                    quote = None
            buffer.append(char)
            index += 1
            continue

        if char == "," and index + 1 < len(text) and text[index + 1] == " ":
            if quote is None:
                candidate = "".join(buffer).strip()
                if candidate:
                    parts.append(candidate)
                buffer = []
                index += 2
                continue

        buffer.append(char)
        index += 1

    candidate = "".join(buffer).strip()
    if candidate:
        parts.append(candidate)
    return parts


def _normalise_answer_records(raw_answers: Any) -> List[Dict[str, Any]]:
    if not raw_answers:
        return []
    if isinstance(raw_answers, str):
        try:
            raw_answers = json.loads(raw_answers)
        except (TypeError, json.JSONDecodeError):
            return []
    if not isinstance(raw_answers, list):
        return []

    records: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_answers, start=1):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or item.get("questionText") or "").strip()
        answer = str(
            item.get("answer")
            or item.get("correctValue")
            or item.get("correct_answer")
            or ""
        ).strip()
        options = item.get("options") if isinstance(item.get("options"), list) else []
        options = [str(option).strip() for option in options if str(option).strip()]
        if not question or not answer:
            continue
        if not re.match(r"^\s*\d+[.)]\s*", question):
            question = f"{index}. {question}"
        records.append(
            {
                "question": question,
                "answer": answer,
                "options": options,
                "correct_letter": str(
                    item.get("correct_letter")
                    or item.get("correctLetter")
                    or item.get("letter")
                    or ""
                ).strip().upper(),
                "explanation": str(item.get("explanation") or "").strip(),
                "tip": str(item.get("tip") or item.get("coaching_strategy") or "").strip(),
            }
        )
    return records


def extract_year_round_answer_records(content: str) -> List[Dict[str, Any]]:
    """Recover structured answers from legacy year-round documents.

    Older generators stored answers and explanations inside the document rather
    than metadata. This parser supports those records so existing RAG databases
    continue to work after the safer question-only format is introduced.
    """
    records: List[Dict[str, Any]] = []
    for match in _YEAR_ROUND_BLOCK_RE.finditer(str(content or "").strip()):
        number = int(match.group("number"))
        records.append(
            {
                "question": f"{number}. {match.group('question').strip()}",
                "answer": match.group("answer").strip(),
                "options": _split_legacy_options(match.group("options")),
                "correct_letter": match.group("letter").strip().upper(),
                "explanation": match.group("explanation").strip(),
                "tip": match.group("tip").strip(),
            }
        )
    return records


def extract_multiple_choice_questions(content: str) -> List[Dict[str, Any]]:
    """Extract question stems and options without returning answer material."""
    text = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
    legacy = extract_year_round_answer_records(text)
    if legacy:
        return questions_from_answer_records(legacy)

    # LLM fallback and new RAG records use one option per line. Ignore every
    # answer/explanation section before parsing so answer keys never reach UI.
    questions_only = re.split(
        r"(?im)^\s*#{0,6}\s*(?:answers?|answer key|explanations?|worked solutions?|bonus)\b.*$",
        text,
        maxsplit=1,
    )[0]
    question_re = re.compile(r"^\s*(?:Question\s*)?(\d+)[.)]\s+(.+?)\s*$", re.I)
    option_re = re.compile(r"^\s*(?:[-*]\s*)?\(?([A-H])\)?[.)]\s+(.+?)\s*$", re.I)
    questions: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for raw_line in questions_only.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        question_match = question_re.match(line)
        if question_match:
            if current and len(current["options"]) >= 2:
                questions.append(current)
            current = {
                "number": int(question_match.group(1)),
                "question": question_match.group(2).strip(),
                "options": [],
            }
            continue
        option_match = option_re.match(line)
        if option_match and current is not None:
            current["options"].append(
                {"label": option_match.group(1).upper(), "text": option_match.group(2).strip()}
            )
    if current and len(current["options"]) >= 2:
        questions.append(current)
    return questions


def questions_from_answer_records(records: Any) -> List[Dict[str, Any]]:
    """Return the public, answer-free shape consumed by the browser."""
    normalised = _normalise_answer_records(records)
    questions: List[Dict[str, Any]] = []
    for index, record in enumerate(normalised, start=1):
        match = re.match(r"^\s*(\d+)[.)]\s*(.*)$", record["question"], re.DOTALL)
        number = int(match.group(1)) if match else index
        question = match.group(2).strip() if match else record["question"]
        options = [
            {"label": chr(65 + option_index), "text": option}
            for option_index, option in enumerate(record.get("options") or [])
        ]
        if question and len(options) >= 2:
            questions.append({"number": number, "question": question, "options": options})
    return questions


def format_questions_only(questions: List[Dict[str, Any]]) -> str:
    """Create a readable question-only fallback string for API clients."""
    lines = ["QUESTIONS"]
    for index, item in enumerate(questions, start=1):
        number = int(item.get("number") or index)
        lines.append(f"{number}. {str(item.get('question') or '').strip()}")
        for option_index, option in enumerate(item.get("options") or []):
            if isinstance(option, dict):
                label = str(option.get("label") or chr(65 + option_index)).strip().upper()
                text = str(option.get("text") or "").strip()
            else:
                label = chr(65 + option_index)
                text = str(option).strip()
            if text:
                lines.append(f"{label}) {text}")
        lines.append("")
    return "\n".join(lines).strip()

# Convenience functions for direct use
_elevenplus_rag_store = None
_elevenplus_rag_lock = threading.Lock()


class ElevenPlusRAGStore:
    def __init__(self, persist_directory: str = None):
        self._write_lock = threading.RLock()
        self._embedding_function = None
        self.store = PGVectorStore(collection_name="elevenplus_collection")
        allow_sqlite = _env_true("TESTING") or _env_true("ELEVENPLUS_RAG_ALLOW_SQLITE")
        if not self.store.is_postgres and not allow_sqlite:
            raise RuntimeError(
                "11+ RAG requires PostgreSQL/pgvector. Set PGVECTOR_DATABASE_URL "
                "or DATABASE_URL to a postgresql+psycopg:// URL. SQLite is allowed "
                "only for automated tests or when ELEVENPLUS_RAG_ALLOW_SQLITE=true."
            )
        logger.info(
            "[RAG] Using PGVectorStore for elevenplus_collection at %s",
            self.store.database_target,
        )

    @property
    def embedding_function(self):
        if self._embedding_function is None:
            from src.homework_rag import _create_embedding_function
            self._embedding_function = _create_embedding_function()
        return self._embedding_function

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(metadata, dict):
            return {}
        sanitized: Dict[str, Any] = {}
        for k, v in metadata.items():
            if v is None:
                continue
            safe_key = str(k)[:128]
            if isinstance(v, (str, int, float, bool)):
                sanitized[safe_key] = v
            elif isinstance(v, datetime):
                if v.tzinfo is None:
                    v = v.replace(tzinfo=UTC)
                sanitized[safe_key] = v.astimezone(UTC).isoformat()
            elif isinstance(v, (list, dict, tuple)):
                sanitized[safe_key] = json.dumps(
                    v, ensure_ascii=False, separators=(",", ":")
                )
            else:
                sanitized[safe_key] = str(v)
        return sanitized

    @staticmethod
    def _validate_content(content: str) -> str:
        text = str(content or "").strip()
        if not text:
            raise ValueError("homework_content must not be empty")
        if len(text) > MAX_DOCUMENT_CHARS:
            raise ValueError(f"homework_content exceeds {MAX_DOCUMENT_CHARS} characters")
        return text

    def _retry_write(self, operation, description: str):
        for attempt in range(1, RAG_MAX_RETRIES + 1):
            try:
                with self._write_lock:
                    return operation()
            except Exception:
                if attempt >= RAG_MAX_RETRIES:
                    logger.exception("[RAG] %s failed after %s attempts", description, attempt)
                    raise
                delay = RAG_RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(
                    0, RAG_RETRY_DELAY
                )
                logger.warning(
                    "[RAG] %s failed (attempt %s); retrying in %.2fs",
                    description,
                    attempt,
                    delay,
                )
                time.sleep(delay)
        raise AssertionError("unreachable")

    def add_homework(
            self,
            homework_content: str,
            metadata: Dict[str, Any]
    ) -> str:
        """Add a homework document to the RAG store

        Args:
            homework_content: The homework content text
            metadata: Dictionary with metadata fields:
                - year_group: int (1-6)
                - subject: str
                - homework_minutes: str (e.g., "10-15", "30")
                - study_year_month: str (e.g., "2026-09")
                - key_stage: str (e.g., "KS1", "KS2")
                - english_level: str
                - student_id: str
                - created_at: str (ISO datetime)
                - correct_answers: Optional correct answers for homework with unique answers
            doc_id: Optional document ID (auto-generated if not provided)

        Returns:
            The document ID
        """
        content = self._validate_content(homework_content)
        now = datetime.now(UTC)
        doc_id = f"ep_{uuid.uuid4().hex}"

        # Ensure metadata has required fields and complies with RAG rules
        metadata_copy = metadata.copy()
        metadata_copy.setdefault("created_at", now.isoformat())
        sanitized_metadata = self._sanitize_metadata(metadata_copy)

        def add():
            self.store.add_documents(
                texts=[content],
                metadatas=[sanitized_metadata],
                ids=[doc_id],
                embeddings=self.embedding_function([content]),
            )

        self._retry_write(add, f"add 11+ document {doc_id}")
        logger.info("[RAG] Added 11+ homework document: %s", doc_id)
        return doc_id

    def add_batch_homework(
            self,
            homework_list: List[Dict[str, Any]],
    ) -> List[str]:
        """Add multiple homework documents in batch

        Args:
            homework_list: List of dicts with keys:
                - content: str (homework content)
                - metadata: Dict[str, Any]
                - doc_id: Optional[str]

        Returns:
            List of document IDs
        """
        if not homework_list:
            return []
        if len(homework_list) > 500:
            raise ValueError("A single 11+ RAG batch cannot exceed 500 documents")

        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        doc_ids: List[str] = []

        for item in homework_list:
            content = self._validate_content(item.get("content", ""))
            metadata = dict(item.get("metadata") or {})
            doc_id = item.get("doc_id")

            now = datetime.now(UTC)
            if not doc_id:
                # 用毫秒时间戳生成唯一 ID
                doc_id = f"ep_{uuid.uuid4().hex}"

            metadata.setdefault("created_at", now.isoformat())
            metadata.setdefault("study_year_month", now.strftime("%Y-%m"))

            texts.append(content)
            metadatas.append(self._sanitize_metadata(metadata))
            doc_ids.append(doc_id)

        if len(set(doc_ids)) != len(doc_ids):
            raise ValueError("Duplicate doc_id values in batch")

        # Upsert keeps ingestion idempotent and avoids deleting the collection first.
        self._retry_write(
            lambda: self.store.add_documents(
                texts=texts,
                metadatas=metadatas,
                ids=doc_ids,
                embeddings=self.embedding_function(texts),
            ),
            f"upsert batch of {len(doc_ids)} 11+ documents",
        )
        logger.info("[RAG] Upserted %s 11+ homework documents in batch", len(doc_ids))
        return doc_ids

    def search(
            self,
            query: str,
            k: int = 5,
            filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """搜索作业文档

        Args:
            query: 语义搜索关键词
            k: 返回结果数量
            filters: 可选的 metadata 过滤条件, 如:
                {"year_group": 3, "subject": "Maths"}

        Returns:
            包含 'doc_id', 'content', 'metadata', 'score' 的字典列表
        """
        clean_query = str(query or "").strip()
        if not clean_query:
            raise ValueError("query must not be empty")
        query_embeddings = self.embedding_function([clean_query])
        raw = self.store.search(
            query_embedding=query_embeddings[0],
            k=_bounded_k(k),
            filters=filters
        )

        results = []
        for item in raw:
            results.append({
                "doc_id": item["doc_id"],
                "content": item["content"],
                "metadata": item["metadata"],
                "score": item["distance"],
                "distance": item.get("distance"),
                "similarity": item.get("similarity"),
            })

        return results

    def search_by_metadata(
            self,
            filters: Dict[str, Any],
            k: int = 10,
            *,
            offset: int = 0,
            exclude_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search homework documents by metadata only (no semantic search)

        Args:
            filters: Metadata filter dict, e.g.:
                {"year_group": 3, "subject": "Maths", "study_year_month": "2026-09"}
            k: Max number of results

        Returns:
            List of dicts with 'content' and 'metadata'
        """
        if not filters:
            raise ValueError("At least one metadata filter is required")
        results = self.store.get_by_metadata(
            filters=filters,
            k=_bounded_k(k),
            offset=max(0, int(offset)),
            exclude_ids=exclude_ids,
        )

        if not results:
            return []

        return [
            {
                "doc_id": r["doc_id"],
                "content": r["content"],
                "metadata": r["metadata"],
            }
            for r in results
        ]

    def delete_homework(self, doc_id: str) -> bool:
        """Delete a homework document by ID

        Args:
            doc_id: Document ID to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            self.store.delete(ids=[doc_id])
            logger.info(f"[RAG] Deleted homework document: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"[RAG] Failed to delete document {doc_id}: {e}")
            return False

    def delete_student_homework(self, student_id: str) -> int:
        """Delete legacy 11+ documents that directly reference one learner."""
        learner = str(student_id or "").strip()
        if not learner:
            return 0
        try:
            return self.store.delete_by_metadata(filters={"student_id": learner})
        except Exception:
            logger.exception("[RAG] Failed to erase legacy 11+ homework for learner %s", learner)
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG store

        Returns:
            Dictionary with collection stats
        """
        total_docs = self.store.count()
        
        # Count by subject and year_group
        subject_counts = {}
        year_counts = {}
        
        # To avoid loading everything, we can use a more efficient way if needed, 
        # but for now follow the pattern of homework_rag
        offset = 0
        while offset < total_docs:
            metas = self.store.get_stats_metadata(limit=STATS_PAGE_SIZE, offset=offset)
            if not metas:
                break
            for meta in metas:
                subject = meta.get("subject", "Unknown")
                year_group = meta.get("year_group", "Unknown")
                subject_counts[subject] = subject_counts.get(subject, 0) + 1
                year_counts[year_group] = year_counts.get(year_group, 0) + 1
            offset += len(metas)

        return {
            "total_documents": total_docs,
            "by_subject": subject_counts,
            "by_year_group": year_counts,
        }

    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        # Legacy for backward compatibility, not used by PGVectorStore directly
        return filters

    def get_student_homework_history(
            self,
            student_id: str,
            subject: str = None,
    ) -> List[Dict[str, Any]]:
        """Get all homework previously generated for a student

        Args:
            student_id: Student ID
            subject: Optional subject filter

        Returns:
            List of homework documents with metadata
        """
        filters = {"student_id": student_id}
        if subject:
            filters["subject"] = subject

        results = self.store.get_by_metadata(filters=filters, k=500)

        if not results:
            return []

        return [
            {
                "doc_id": r["doc_id"],
                "content": r["content"],
                "metadata": r["metadata"],
            }
            for r in results
        ]

    def get_student_previous_topics(
            self,
            student_id: str,
            subject: str,
    ) -> List[str]:
        """Extract list of topics/areas previously covered for a student in a subject

        Args:
            student_id: Student ID
            subject: Subject name

        Returns:
            List of topic keywords/descriptions from previous homework
        """
        history = self.get_student_homework_history(student_id, subject)
        if not history:
            return []

        # Extract content previews (first 200 chars) as topic indicators
        topics = []
        for hw in history:
            content = hw["content"][:200]
            topics.append(content)
        return topics


    def search_homework_answers(
            self,
            doc_id: str,
    ) -> Optional[list]:
        """通过 doc_id 直接获取正确答案

        Args:
            doc_id: 作业文档 ID

        Returns:
            正确答案列表，未找到则返回 None
        """
        if not doc_id:
            logger.warning("[RAG] doc_id 为空")
            return None

        try:
            result = self.store.get_by_ids(ids=[doc_id])
            if not result:
                logger.warning(f"[RAG] 未找到 doc_id={doc_id} 对应的文档")
                return None

            metadata = result[0]["metadata"]
            raw_correct_answers = metadata.get("correct_answers")
            decoded_answers: Any = raw_correct_answers
            if isinstance(raw_correct_answers, str):
                try:
                    decoded_answers = json.loads(raw_correct_answers)
                except (TypeError, json.JSONDecodeError):
                    decoded_answers = raw_correct_answers

            correct_answers = _normalise_answer_records(decoded_answers)
            if correct_answers:
                logger.info("[RAG] Found structured answers for doc_id=%s", doc_id)
                return correct_answers
            if isinstance(decoded_answers, list) and decoded_answers:
                # Preserve older answer-only lists for the generic 11+ review path.
                return decoded_answers

            content = result[0]["content"]
            legacy_records = extract_year_round_answer_records(content)
            if legacy_records:
                logger.info("[RAG] Recovered legacy year-round answers for doc_id=%s", doc_id)
                return legacy_records
            return None
        except Exception as e:
            logger.error(f"[RAG] 获取正确答案失败: {e}")
            return None


# Convenience functions for direct use
_elevenplus_rag_store = None


def get_elevenplus_rag_store() -> ElevenPlusRAGStore:
    """Get or create the singleton RAG store instance."""
    global _elevenplus_rag_store
    if _elevenplus_rag_store is None:
        with _elevenplus_rag_lock:
            if _elevenplus_rag_store is None:
                _elevenplus_rag_store = ElevenPlusRAGStore()
    return _elevenplus_rag_store


def store_homework(
        homework_content: str,
        year_group: int,
        subject: str,
        homework_minutes: str,
        key_stage: str = None,
        english_level: str = None,
        student_id: str = None,
        correct_answers: str = None,
        age: Optional[int] = None,
        week_num: Optional[int] = None,
        content_type: Optional[str] = None,
        topic: Optional[str] = None,
) -> str:
    """Store a homework document in the RAG store

    Args:
        homework_content: The homework content
        year_group: UK year group (1-6)
        subject: Subject name
        homework_minutes: Recommended homework time (e.g., "10-15", "30")
        key_stage: UK Key Stage (KS1/KS2)
        english_level: Student English level
        student_id: Student ID
        correct_answers: Optional correct answers for homework with unique answers
        age: Student age

    Returns:
        Document ID
    """
    store = get_elevenplus_rag_store()

    metadata = {
        "year_group": year_group,
        "subject": subject,
        "homework_minutes": homework_minutes,
        "study_year_month": datetime.now().strftime("%Y-%m"),
    }

    if key_stage:
        metadata["key_stage"] = key_stage
    if english_level:
        metadata["english_level"] = english_level
    if student_id:
        metadata["student_id"] = student_id
    if correct_answers:
        metadata["correct_answers"] = correct_answers
    if age is not None:
        metadata["age"] = int(age)
    if week_num is not None:
        metadata["week_num"] = int(week_num)
    if content_type:
        metadata["content_type"] = str(content_type)
    if topic:
        metadata["topic"] = str(topic)

    return store.add_homework(homework_content, metadata)


def search_homework(
        query: str,
        year_group: int = None,
        subject: str = None,
        homework_minutes: str = None,
        study_year_month: str = None,
        k: int = 5,
) -> List[Dict[str, Any]]:
    """Search for homework documents

    Args:
        query: Semantic search query
        year_group: Filter by year group (1-6)
        subject: Filter by subject
        homework_minutes: Filter by homework time
        study_year_month: Filter by study year-month (e.g., "2026-09")
        k: Number of results

    Returns:
        List of search results
    """
    store = get_elevenplus_rag_store()

    filters = {}
    if year_group is not None:
        filters["year_group"] = year_group
    if subject is not None:
        filters["subject"] = subject
    if homework_minutes is not None:
        filters["homework_minutes"] = homework_minutes
    if study_year_month is not None:
        filters["study_year_month"] = study_year_month

    return store.search(query, k=k, filters=filters if filters else None)



def _subject_aliases(subject: str) -> List[str]:
    """Return exact new keys first, followed by safe legacy aliases."""
    canonical = str(subject or "").strip()
    has_year_suffix = canonical.casefold().endswith("-1year")
    base = canonical[:-6] if has_year_suffix else canonical
    folded = re.sub(r"[\s_-]+", "", base).casefold()

    if folded in {"maths", "mathematics"}:
        aliases = ["Maths-1year", "Maths"] if has_year_suffix else ["Maths"]
    elif folded == "english":
        aliases = ["English-1year", "English"] if has_year_suffix else ["English"]
    elif folded == "verbalreasoning":
        aliases = (
            ["VerbalReasoning-1year", "Verbal Reasoning-1year", "Verbal Reasoning", "VerbalReasoning"]
            if has_year_suffix
            else ["Verbal Reasoning", "VerbalReasoning"]
        )
    elif folded == "nonverbalreasoning":
        aliases = (
            [
                "NonVerbalReasoning-1year",
                "Non-Verbal Reasoning-1year",
                "Non Verbal Reasoning-1year",
                "Non-Verbal Reasoning",
                "NonVerbalReasoning",
                "Non Verbal Reasoning",
            ]
            if has_year_suffix
            else ["Non-Verbal Reasoning", "NonVerbalReasoning", "Non Verbal Reasoning"]
        )
    else:
        aliases = [canonical]

    # Preserve order while avoiding duplicate metadata queries.
    return list(dict.fromkeys(alias for alias in aliases if alias))


def search_homework_by_metadata(
    year_group: int,
    subject: str,
    k: int = 50,
    week_num: Optional[int] = None,
    content_type: Optional[str] = None,
    *,
    offset: int = 0,
    exclude_ids: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Return exact metadata candidates without creating a query embedding.

    ``week_num`` is a hard filter for the 52-week plan. Subject aliases keep
    older RAG databases compatible with the canonical spaced subject names.
    """
    store = get_elevenplus_rag_store()
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    aliases = _subject_aliases(subject)
    prefer_exact_year_round = str(subject or "").strip().casefold().endswith("-1year")
    remaining_offset = max(0, int(offset))
    for alias_index, alias in enumerate(aliases):
        filters: Dict[str, Any] = {"year_group": int(year_group), "subject": alias}
        if week_num is not None:
            filters["week_num"] = int(week_num)
        if content_type:
            filters["content_type"] = str(content_type)
        if remaining_offset or exclude_ids:
            alias_results = store.search_by_metadata(
                filters,
                k=k,
                offset=remaining_offset,
                exclude_ids=exclude_ids,
            )
        else:
            # Preserve compatibility with small test doubles and older custom
            # store wrappers that implement only (filters, k).
            alias_results = store.search_by_metadata(filters, k=k)
        remaining_offset = 0
        for item in alias_results:
            doc_id = str(item.get("doc_id") or "")
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                merged.append(item)
            if len(merged) >= k:
                return merged
        # New 52-week records are authoritative. Query legacy aliases only
        # when the exact new key has no records, reducing database work.
        if prefer_exact_year_round and alias_index == 0 and alias_results:
            return merged
    return merged


def count_homework_by_metadata(
    year_group: int,
    subject: str,
    week_num: Optional[int] = None,
    content_type: Optional[str] = None,
) -> int:
    """Count exact 11+ metadata matches across canonical and legacy aliases."""
    store = get_elevenplus_rag_store().store
    total = 0
    for alias in _subject_aliases(subject):
        filters: Dict[str, Any] = {"year_group": int(year_group), "subject": alias}
        if week_num is not None:
            filters["week_num"] = int(week_num)
        if content_type:
            filters["content_type"] = str(content_type)
        total += store.count_by_metadata(filters)
    return total


def get_database_target() -> str:
    """Return the password-free PostgreSQL target used by the 11+ RAG."""
    return get_elevenplus_rag_store().store.database_target


def get_homework_questions(doc_id: Optional[str], content: str = "") -> List[Dict[str, Any]]:
    """Return answer-free structured questions for the year-round browser UI."""
    records = search_homework_answers(doc_id) if doc_id else None
    questions = questions_from_answer_records(records)
    if questions:
        return questions
    return extract_multiple_choice_questions(content)

def get_student_homework_history(student_id: str, subject: str = None) -> List[Dict[str, Any]]:
    """Get homework history for a student"""
    store = get_elevenplus_rag_store()
    return store.get_student_homework_history(student_id, subject)


def delete_student_homework(student_id: str) -> int:
    """Erase legacy learner-owned documents from the 11+ RAG."""
    return get_elevenplus_rag_store().delete_student_homework(student_id)


def get_student_previous_topics(student_id: str, subject: str) -> List[str]:
    """Get previous topics covered for a student in a subject"""
    store = get_elevenplus_rag_store()
    return store.get_student_previous_topics(student_id, subject)


def search_homework_answers(doc_id: str) -> Optional[list]:
    """通过 doc_id 获取正确答案

    Args:
        doc_id: 作业文档 ID

    Returns:
        正确答案字符串，未找到则返回 None
    """
    store = get_elevenplus_rag_store()
    return store.search_homework_answers(doc_id)
