#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Production-hardened homework RAG storage.

Compatibility goals:
* preserve the existing public convenience functions;
* preserve existing collection and metadata names;
* read old ``correct_answers`` values while writing a consistent JSON format.

Reliability improvements:
* collision-free UUID document IDs;
* thread-safe lazy initialisation and serialised writes;
* bounded query sizes and paginated statistics;
* PostgreSQL/pgvector storage for multi-worker production;
* correct lazy creation of the Chinese collection;
* clearer distance/similarity result fields.
"""
from __future__ import annotations

import json
import hashlib
import logging
import os
import random
import re
import threading
import time
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, Iterable, List, Optional

from .pgvector_store import PGVectorStore

logger = logging.getLogger(__name__)

# Vector storage configuration
RAG_MAX_RETRIES = max(1, min(int(os.getenv("RAG_MAX_RETRIES", "3")), 8))
RAG_RETRY_DELAY = max(0.05, float(os.getenv("RAG_RETRY_DELAY", "0.4")))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY")
DEFAULT_ENDPOINT = os.getenv("DEFAULT_ENDPOINT_OPENAI")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_QUERY_RESULTS = max(1, min(int(os.getenv("RAG_MAX_QUERY_RESULTS", "50")), 500))
MAX_DOCUMENT_CHARS = max(1_000, int(os.getenv("RAG_MAX_DOCUMENT_CHARS", "100000")))
STATS_PAGE_SIZE = max(100, min(int(os.getenv("RAG_STATS_PAGE_SIZE", "1000")), 10_000))

_embedding_function = None
_embedding_function_lock = threading.Lock()


def _create_embedding_function():
    """Return one process-wide embedding function, initialised only when needed."""
    global _embedding_function
    if _embedding_function is not None:
        return _embedding_function
    with _embedding_function_lock:
        if _embedding_function is not None:
            return _embedding_function
        if EMBEDDING_PROVIDER in {"local", "sentence_transformer"}:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)

            def local_embedding(texts: List[str]) -> List[List[float]]:
                return model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ).tolist()

            _embedding_function = local_embedding
        elif EMBEDDING_PROVIDER == "api":
            if not DEFAULT_API_KEY:
                raise ValueError("EMBEDDING_PROVIDER=api requires DEFAULT_API_KEY")
            import requests

            def api_embedding(texts: List[str]) -> List[List[float]]:
                endpoint = DEFAULT_ENDPOINT or "https://api.openai.com/v1/embeddings"
                model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
                response = requests.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {DEFAULT_API_KEY}"},
                    json={"input": texts, "model": model_name},
                    timeout=max(5, min(int(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30")), 120)),
                )
                response.raise_for_status()
                return [item["embedding"] for item in response.json()["data"]]

            _embedding_function = api_embedding
        else:
            raise ValueError(f"Unknown EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER}")
        return _embedding_function


def _new_doc_id(prefix: str = "hw") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _bounded_k(k: int) -> int:
    try:
        value = int(k)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, MAX_QUERY_RESULTS))


class HomeworkRAGStore:
    def __init__(self, persist_directory: Optional[str] = None):
        self._write_lock = threading.RLock()
        self._chinese_lock = threading.Lock()
        self._chinese_collection = None

        self._embedding_function = None
        self.store = PGVectorStore(collection_name="homework_collection")
        logger.info(
            "[RAG] Using PGVectorStore for homework_collection at %s",
            self.store.database_target,
        )

    def log_voice_event(
            self,
            event_type: str,  # 'tts_used' or 'stt_used'
            year_group: int,
            subject: str,
            student_id: str = None,
    ) -> str:
        """Increment an aggregate counter without retaining a learner ID.

        ``student_id`` remains in the signature for compatibility with older
        callers, but it is deliberately ignored and never persisted.
        """
        del student_id
        from src.webapp.privacy_metrics import record_voice_event

        record_voice_event(
            event_type,
            year_group=year_group,
            subject=subject,
        )
        return "aggregate_voice_counter"

    def get_voice_usage_stats(self) -> Dict[str, Any]:
        """Read privacy-minimised aggregate voice counts."""
        from src.webapp.privacy_metrics import voice_summary

        return voice_summary()

    @property
    def embedding_function(self):
        if self._embedding_function is None:
            self._embedding_function = _create_embedding_function()
        return self._embedding_function

    @property
    def chinese_collection(self):
        if self._chinese_collection is None:
            with self._chinese_lock:
                if self._chinese_collection is None:
                    self._chinese_collection = PGVectorStore(collection_name="chinese_collection")
                    logger.info("[RAG] Using PGVectorStore for chinese_collection")
        return self._chinese_collection

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(metadata, dict):
            return {}
        sanitized: Dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            safe_key = str(key)[:128]
            if isinstance(value, (str, int, float, bool)):
                sanitized[safe_key] = value
            elif isinstance(value, datetime):
                sanitized[safe_key] = value.astimezone(UTC).isoformat()
            elif isinstance(value, (list, dict, tuple)):
                sanitized[safe_key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            else:
                sanitized[safe_key] = str(value)
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
                delay = RAG_RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(0, RAG_RETRY_DELAY)
                logger.warning("[RAG] %s failed (attempt %s); retrying in %.2fs", description, attempt, delay)
                time.sleep(delay)
        raise AssertionError("unreachable")

    def add_homework(self, homework_content: str, metadata: Dict[str, Any]) -> str:
        content = self._validate_content(homework_content)
        now = datetime.now(UTC)
        doc_id = _new_doc_id()
        sanitized = self._sanitize_metadata(metadata)
        sanitized.setdefault("created_at", now.isoformat())

        def add():
            embeddings = self.embedding_function([content])
            self.store.add_documents(texts=[content], metadatas=[sanitized], ids=[doc_id], embeddings=embeddings)

        self._retry_write(add, f"add document {doc_id}")
        logger.info("[RAG] Added homework document: %s", doc_id)
        return doc_id

    def add_batch_homework(self, homework_list: List[Dict[str, Any]]) -> List[str]:
        if not homework_list:
            return []
        if len(homework_list) > 500:
            raise ValueError("A single RAG batch cannot exceed 500 documents")
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        doc_ids: List[str] = []
        now = datetime.now(UTC)
        for item in homework_list:
            texts.append(self._validate_content(item.get("content", "")))
            metadata = self._sanitize_metadata(item.get("metadata", {}))
            metadata.setdefault("created_at", now.isoformat())
            metadata.setdefault("study_year_month", now.strftime("%Y-%m"))
            metadatas.append(metadata)
            requested = str(item.get("doc_id") or "").strip()
            doc_ids.append(requested or _new_doc_id())
        if len(set(doc_ids)) != len(doc_ids):
            raise ValueError("Duplicate doc_id values in batch")

        self._retry_write(
            lambda: self.store.add_documents(
                texts=texts, 
                metadatas=metadatas, 
                ids=doc_ids, 
                embeddings=self.embedding_function(texts)
            ),
            f"add batch of {len(doc_ids)} documents",
        )
        return doc_ids

    def search(
        self,
        query: str,
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        clean_query = str(query or "").strip()
        if not clean_query:
            raise ValueError("query must not be empty")
        where = filters or {}
        query_embeddings = self.embedding_function([clean_query])
        raw = self.store.search(
            query_embedding=query_embeddings[0],
            k=_bounded_k(k),
            filters=where
        )
        if not raw:
            return []
        
        results: List[Dict[str, Any]] = []
        for item in raw:
            results.append(
                {
                    "doc_id": item["doc_id"],
                    "content": item["content"],
                    "metadata": item["metadata"],
                    # Keep score for backward compatibility, but identify it correctly.
                    "score": item["distance"],
                    "distance": item["distance"],
                    "similarity": item["similarity"],
                }
            )
        return results

    def search_by_metadata(
        self,
        filters: Dict[str, Any],
        k: int = 10,
        *,
        offset: int = 0,
        exclude_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not filters:
            raise ValueError("At least one metadata filter is required")
        return self.store.get_by_metadata(
            filters=filters,
            k=_bounded_k(k),
            offset=max(0, int(offset)),
            exclude_ids=exclude_ids,
        )

    def delete_homework(self, doc_id: str) -> bool:
        if not doc_id:
            return False
        try:
            self._retry_write(lambda: self.store.delete(ids=[doc_id]), f"delete {doc_id}")
            return True
        except Exception:
            return False

    def delete_student_homework(self, student_id: str) -> int:
        """Delete legacy RAG documents that directly reference one learner.

        New shared-library documents do not store ``student_id``. This method
        exists to erase records created by older application versions.
        """
        learner = str(student_id or "").strip()
        if not learner:
            return 0
        try:
            deleted_count = self._retry_write(
                lambda: self.store.delete_by_metadata(filters={"student_id": learner}),
                f"delete legacy learner homework {learner}",
            )
            return deleted_count
        except Exception:
            logger.exception("[RAG] Failed to erase legacy homework for learner %s", learner)
            return 0

    def get_stats(self) -> Dict[str, Any]:
        total = int(self.store.count())
        subject_counts: Dict[str, int] = {}
        year_counts: Dict[Any, int] = {}
        offset = 0
        while offset < total:
            metas = self.store.get_stats_metadata(
                limit=min(STATS_PAGE_SIZE, total - offset),
                offset=offset,
            )
            if not metas:
                break
            for meta in metas:
                subject = meta.get("subject", "Unknown")
                year = meta.get("year_group", "Unknown")
                subject_counts[subject] = subject_counts.get(subject, 0) + 1
                year_counts[year] = year_counts.get(year, 0) + 1
            offset += len(metas)
        return {"total_documents": total, "by_subject": subject_counts, "by_year_group": year_counts}

    @staticmethod
    def _build_where_clause(filters: Dict[str, Any]) -> Dict[str, Any]:
        conditions = [{str(key): value} for key, value in (filters or {}).items() if value is not None]
        if len(conditions) == 1:
            return conditions[0]
        if len(conditions) > 1:
            return {"$and": conditions}
        return {}

    def get_student_homework_history(
        self,
        student_id: str,
        subject: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {"student_id": student_id}
        if subject:
            filters["subject"] = subject
        
        return self.store.get_by_metadata(
            filters=filters,
            k=max(1, min(int(limit), 500)),
        )

    def get_student_previous_topics(self, student_id: str, subject: str) -> List[str]:
        return [item["content"][:200] for item in self.get_student_homework_history(student_id, subject)]

    def ingest_chinese_textbooks(self, chinese_dir: Optional[str] = None) -> int:
        root_dir = chinese_dir or os.path.join(PROJECT_DIR, "data", "chinese")
        if not os.path.exists(root_dir):
            logger.warning("[RAG] Chinese textbooks directory not found: %s", root_dir)
            return 0
        mapping = {
            "第一册": 1, "第二册": 2, "第三册": 3, "第四册": 4, "第五册": 5,
            "第六册": 6, "第七册": 7, "第八册": 8, "第九册": 9,
        }
        texts: List[str] = []
        metas: List[Dict[str, Any]] = []
        ids: List[str] = []
        for volume in os.listdir(root_dir):
            volume_path = os.path.join(root_dir, volume)
            if not os.path.isdir(volume_path):
                continue
            year = next((number for label, number in mapping.items() if label in volume), None)
            if year is None:
                continue
            for directory, _dirs, files in os.walk(volume_path):
                for filename in files:
                    if not filename.lower().endswith(".pdf"):
                        continue
                    filepath = os.path.join(directory, filename)
                    doc_id = f"chinese_y{year}_{uuid.uuid5(uuid.NAMESPACE_URL, filepath).hex}"
                    existing = self.chinese_collection.get_by_ids(ids=[doc_id])
                    if existing:
                        continue
                    content = f"Chinese Textbook - Year {year}\nVolume: {volume}\nFile: {filename}"
                    texts.append(content)
                    metas.append(
                        self._sanitize_metadata(
                            {
                                "subject": "Chinese",
                                "year_group": year,
                                "volume": volume,
                                "filename": filename,
                                "source": "chinese_textbook",
                                "ingested_at": datetime.now(UTC).isoformat(),
                            }
                        )
                    )
                    ids.append(doc_id)
        if ids:
            self._retry_write(
                lambda: self.chinese_collection.add_documents(
                    texts=texts, 
                    metadatas=metas, 
                    ids=ids, 
                    embeddings=self.embedding_function(texts)
                ),
                f"ingest {len(ids)} Chinese textbook records",
            )
        return len(ids)

    def search_chinese_textbooks(
        self,
        query: str,
        year_group: Optional[int] = None,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        
        filters = {}
        if year_group is not None:
            filters["year_group"] = int(year_group)
        
        query_embeddings = self.embedding_function([clean_query])
        return self.chinese_collection.search(
            query_embedding=query_embeddings[0],
            k=_bounded_k(k),
            filters=filters
        )

    def search_homework_answers(self, doc_id: str) -> Optional[list]:
        if not doc_id:
            return None
        try:
            result = self.store.get_by_ids(ids=[doc_id])
        except Exception:
            logger.exception("[RAG] Failed to read answers for %s", doc_id)
            return None
        if not result:
            return None
        metadata = result[0].get("metadata") or {}
        value = metadata.get("correct_answers")
        if value in (None, ""):
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [value]
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
            return [str(parsed)]
        return [str(value)]


_store: Optional[HomeworkRAGStore] = None
_store_lock = threading.Lock()
_solution_method_store: Optional[PGVectorStore] = None
_solution_method_store_lock = threading.Lock()
_detail_explanation_store: Optional[PGVectorStore] = None
_detail_explanation_store_lock = threading.Lock()


def get_homework_rag_store() -> HomeworkRAGStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = HomeworkRAGStore()
    return _store


def _get_solution_method_store() -> PGVectorStore:
    global _solution_method_store
    if _solution_method_store is None:
        with _solution_method_store_lock:
            if _solution_method_store is None:
                _solution_method_store = PGVectorStore(
                    collection_name="solution_method_collection"
                )
    return _solution_method_store


def _normalise_method_question(question: Any) -> str:
    value = re.sub(
        r"^\s*(?:question\s*)?\d+\s*[.):-]\s*",
        "",
        str(question or ""),
        flags=re.I,
    )
    return " ".join(value.casefold().split())


def solution_method_key(question: Any, subject: Any, year_group: Any) -> str:
    """Return a stable opaque key without storing the question itself."""
    try:
        year = int(year_group)
    except (TypeError, ValueError):
        year = 3
    raw = (
        f"{str(subject or '').strip().casefold()}|{year}|"
        f"{_normalise_method_question(question)}"
    )
    return "method_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_solution_methods(
    questions: Iterable[Any], subject: str, year_group: int
) -> Dict[str, str]:
    """Load the first saved method for each requested question."""
    method_ids = [
        solution_method_key(question, subject, year_group)
        for question in questions
        if str(question or "").strip()
    ]
    if not method_ids:
        return {}
    rows = _get_solution_method_store().get_by_ids(method_ids)
    return {
        str(row["doc_id"]): str(row.get("content") or "").strip()
        for row in rows
        if str(row.get("content") or "").strip()
    }


def save_solution_methods(
    records: Iterable[Dict[str, Any]], subject: str, year_group: int
) -> Dict[str, str]:
    """Persist methods once so later attempts reuse the original explanation."""
    materialised = list(records or [])
    clean_records = []
    for record in materialised:
        question = str(record.get("question") or "").strip()
        method = str(record.get("method") or "").strip()
        if not question or not method:
            continue
        clean_records.append(
            (solution_method_key(question, subject, year_group), method)
        )
    if not clean_records:
        return {}

    store = _get_solution_method_store()
    embedding_dimension = int(getattr(store, "embedding_dimension", 384))
    fixed_embedding = [1.0] + [0.0] * (embedding_dimension - 1)
    store.add_documents_if_absent(
        texts=[method for _, method in clean_records],
        metadatas=[
            {"kind": "solution_method", "schema_version": 1}
            for _ in clean_records
        ],
        ids=[method_id for method_id, _ in clean_records],
        embeddings=[list(fixed_embedding) for _ in clean_records],
    )
    return load_solution_methods(
        [record.get("question") for record in materialised],
        subject,
        year_group,
    )


def _get_detail_explanation_store() -> PGVectorStore:
    global _detail_explanation_store
    if _detail_explanation_store is None:
        with _detail_explanation_store_lock:
            if _detail_explanation_store is None:
                _detail_explanation_store = PGVectorStore(
                    collection_name="detail_explanation_collection"
                )
    return _detail_explanation_store


def detail_explanation_key(
    question: Any, subject: Any, year_group: Any, *, is_eleven_plus: bool = False
) -> str:
    """Return a stable opaque key for a reusable one-question explanation."""
    try:
        year = int(year_group)
    except (TypeError, ValueError):
        year = 3
    raw = (
        f"{'11plus' if is_eleven_plus else 'primary'}|"
        f"{str(subject or '').strip().casefold()}|{year}|"
        f"{_normalise_method_question(question)}"
    )
    return "explain_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_detail_explanation(
    question: Any, subject: str, year_group: int, *, is_eleven_plus: bool = False
) -> Optional[str]:
    """Load the saved detailed explanation for one question, if present."""
    key = detail_explanation_key(
        question, subject, year_group, is_eleven_plus=is_eleven_plus
    )
    for row in _get_detail_explanation_store().get_by_ids([key]):
        content = str(row.get("content") or "").strip()
        if content:
            return content
    return None


def save_detail_explanation(
    records: Iterable[Dict[str, Any]],
    subject: str,
    year_group: int,
    *,
    is_eleven_plus: bool = False,
) -> Dict[str, str]:
    """Persist reusable explanations once so later pupils reuse them."""
    materialised = list(records or [])
    clean_records = []
    for record in materialised:
        question = str(record.get("question") or "").strip()
        explanation = str(record.get("explanation") or "").strip()
        if not question or not explanation:
            continue
        clean_records.append(
            (
                detail_explanation_key(
                    question, subject, year_group, is_eleven_plus=is_eleven_plus
                ),
                question,
                explanation,
            )
        )
    if not clean_records:
        return {}

    store = _get_detail_explanation_store()
    embedding_dimension = int(getattr(store, "embedding_dimension", 384))
    fixed_embedding = [1.0] + [0.0] * (embedding_dimension - 1)
    store.add_documents_if_absent(
        texts=[explanation for _, _, explanation in clean_records],
        metadatas=[
            {"kind": "detail_explanation", "schema_version": 1}
            for _ in clean_records
        ],
        ids=[key for key, _, _ in clean_records],
        embeddings=[list(fixed_embedding) for _ in clean_records],
    )
    saved: Dict[str, str] = {}
    for key, question, explanation in clean_records:
        saved[key] = explanation
    return saved


def list_explanation_source_sets(*, is_eleven_plus: Optional[bool] = None, limit: int = 500) -> List[Dict[str, Any]]:
    """List shared homework/11+ RAG sets that can have saved explanations.

    The returned records intentionally contain only admin-facing metadata and a
    short title; the full question content is not exposed by the admin API.
    """
    stores = []
    if is_eleven_plus is None or not is_eleven_plus:
        stores.append((get_homework_rag_store(), False))
    if is_eleven_plus is None or is_eleven_plus:
        try:
            from src.elevenplus_rag import get_elevenplus_rag_store
            stores.append((get_elevenplus_rag_store(), True))
        except Exception:
            logger.exception("Could not initialise 11+ RAG store for admin explanation management")

    results: List[Dict[str, Any]] = []
    for store, eleven_plus in stores:
        try:
            total = min(int(store.store.count()), max(0, int(limit)))
            offset = 0
            while offset < total:
                rows = store.store.get_stats_metadata(limit=min(100, total - offset), offset=offset)
                # Stats metadata does not include ids, so fetch the corresponding
                # documents by page from the underlying vector store.
                docs = store.store.get_all(limit=min(100, total - offset), offset=offset) if hasattr(store.store, "get_all") else []
                if not docs:
                    break
                for row in docs:
                    metadata = row.get("metadata") or {}
                    doc_id = str(row.get("doc_id") or "").strip()
                    if not doc_id:
                        continue
                    content_type = str(metadata.get("content_type") or metadata.get("content_kind") or "").strip().casefold()
                    # The admin tool is for reusable explanations attached to
                    # homework / 11+ practice sets, not mock exams or Topic Mastery.
                    if eleven_plus and ("mock" in content_type or "mastery" in content_type):
                        continue
                    results.append({
                        "doc_id": doc_id,
                        "is_eleven_plus": eleven_plus,
                        "subject": str(metadata.get("subject") or "").strip(),
                        "year_group": metadata.get("year_group"),
                        "week_num": metadata.get("week_num"),
                        "content_type": str(metadata.get("content_type") or metadata.get("content_kind") or "").strip(),
                        "title": str(metadata.get("title") or metadata.get("name") or "").strip(),
                    })
                offset += len(docs)
        except Exception:
            logger.exception("Could not list explanation source sets")
    return results[:max(0, int(limit))]


def delete_saved_explanations_for_set(doc_id: str, *, is_eleven_plus: bool = False) -> int:
    """Delete all reusable per-question explanations belonging to one set.

    Explanations are keyed by question rather than by source document, so we
    first load the selected set, extract its questions, calculate the same
    stable explanation keys, and delete only those records.
    """
    clean_id = str(doc_id or "").strip()
    if not clean_id:
        return 0

    if is_eleven_plus:
        from src.elevenplus_rag import get_elevenplus_rag_store, get_homework_questions
        source_store = get_elevenplus_rag_store()
    else:
        source_store = get_homework_rag_store()
        try:
            from src.elevenplus_rag import get_homework_questions
        except Exception:
            get_homework_questions = None

    docs = source_store.store.get_by_ids(ids=[clean_id])
    if not docs:
        return 0
    doc = docs[0]
    content = str(doc.get("content") or "")
    metadata = doc.get("metadata") or {}
    subject = str(metadata.get("subject") or "general")
    try:
        year_group = int(metadata.get("year_group") or 3)
    except (TypeError, ValueError):
        year_group = 3

    questions = []
    if get_homework_questions:
        try:
            parsed = get_homework_questions(clean_id, content)
            for item in parsed or []:
                if isinstance(item, dict):
                    q = item.get("question") or item.get("text")
                else:
                    q = item
                if str(q or "").strip():
                    questions.append(str(q).strip())
        except Exception:
            logger.exception("Could not extract questions for explanation deletion: %s", clean_id)

    if not questions:
        return 0

    store = _get_solution_method_store()
    ids = [solution_method_key(q, subject, year_group) for q in questions]
    try:
        return int(store.delete(ids))
    except Exception:
        logger.exception("Could not delete saved explanations for set %s", clean_id)
        return 0


def store_homework(
    homework_content: str,
    year_group: int,
    subject: str,
    homework_minutes: str,
    key_stage: Optional[str] = None,
    english_level: Optional[str] = None,
    student_id: Optional[str] = None,
    correct_answers: Any = None,
    age: Optional[int] = None,
) -> str:
    metadata: Dict[str, Any] = {
        "year_group": int(year_group),
        "subject": str(subject),
        "homework_minutes": str(homework_minutes),
        "study_year_month": datetime.now(UTC).strftime("%Y-%m"),
    }
    if key_stage:
        metadata["key_stage"] = key_stage
    if english_level:
        metadata["english_level"] = english_level
    if student_id:
        metadata["student_id"] = student_id
    if correct_answers is not None:
        metadata["correct_answers"] = correct_answers
    if age is not None:
        metadata["age"] = int(age)
    return get_homework_rag_store().add_homework(homework_content, metadata)


def search_homework(
    query: str,
    year_group: Optional[int] = None,
    subject: Optional[str] = None,
    homework_minutes: Optional[str] = None,
    study_year_month: Optional[str] = None,
    k: int = 5,
) -> List[Dict[str, Any]]:
    filters: Dict[str, Any] = {}
    if year_group is not None:
        filters["year_group"] = int(year_group)
    if subject is not None:
        filters["subject"] = subject
    if homework_minutes is not None:
        filters["homework_minutes"] = homework_minutes
    if study_year_month is not None:
        filters["study_year_month"] = study_year_month
    return get_homework_rag_store().search(query, k=k, filters=filters or None)



def search_homework_by_metadata(
    year_group: int,
    subject: str,
    k: int = 50,
    *,
    offset: int = 0,
    exclude_ids: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Return exact year/subject candidates without creating a query embedding.

    ``exclude_ids`` is used by homework assignment to skip documents already
    shown to the learner. This prevents the old first-50 window from causing a
    false RAG miss when hundreds of unseen documents remain in PostgreSQL.
    """
    return get_homework_rag_store().search_by_metadata(
        {"year_group": int(year_group), "subject": str(subject)},
        k=k,
        offset=offset,
        exclude_ids=exclude_ids,
    )

def get_student_homework_history(student_id: str, subject: Optional[str] = None) -> List[Dict[str, Any]]:
    return get_homework_rag_store().get_student_homework_history(student_id, subject)


def delete_student_homework(student_id: str) -> int:
    """Erase legacy learner-owned documents from the shared homework RAG."""
    return get_homework_rag_store().delete_student_homework(student_id)


def get_student_previous_topics(student_id: str, subject: str) -> List[str]:
    return get_homework_rag_store().get_student_previous_topics(student_id, subject)


def ingest_chinese_textbooks(chinese_dir: Optional[str] = None) -> int:
    return get_homework_rag_store().ingest_chinese_textbooks(chinese_dir)


def search_chinese_textbooks(query: str, year_group: Optional[int] = None, k: int = 5) -> List[Dict[str, Any]]:
    return get_homework_rag_store().search_chinese_textbooks(query, year_group, k)


def search_homework_answers(doc_id: str) -> Optional[list]:
    return get_homework_rag_store().search_homework_answers(doc_id)


def log_voice_event(
    event_type: str,
    year_group: int,
    subject: str,
    student_id: str = None,
) -> str:
    """Increment an aggregate voice counter without loading RAG or embeddings."""
    del student_id
    from src.webapp.privacy_metrics import record_voice_event

    record_voice_event(
        event_type,
        year_group=year_group,
        subject=subject,
    )
    return "aggregate_voice_counter"


def get_voice_usage_stats() -> Dict[str, Any]:
    """Return aggregate voice usage without loading the homework RAG store."""
    from src.webapp.privacy_metrics import voice_summary

    return voice_summary()
