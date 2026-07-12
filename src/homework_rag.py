#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Production-hardened homework RAG storage.

Compatibility goals:
* preserve the existing public convenience functions;
* keep existing Chroma collection and metadata names;
* read old ``correct_answers`` values while writing a consistent JSON format.

Reliability improvements:
* collision-free UUID document IDs;
* thread-safe lazy initialisation and serialised writes;
* bounded query sizes and paginated statistics;
* optional server-backed Chroma for multi-worker production;
* correct lazy creation of the Chinese collection;
* clearer distance/similarity result fields.
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

RAG_MAX_RETRIES = max(1, min(int(os.getenv("RAG_MAX_RETRIES", "3")), 8))
RAG_RETRY_DELAY = max(0.05, float(os.getenv("RAG_RETRY_DELAY", "0.4")))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_ENDPOINT = os.getenv("QWEN_ENDPOINT_OPENAI")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH") or os.path.join(PROJECT_DIR, "data", "chroma_homework_db")
CHROMA_HOST = os.getenv("CHROMA_HOST", "").strip()
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_SSL = os.getenv("CHROMA_SSL", "false").lower() in {"1", "true", "yes"}
MAX_QUERY_RESULTS = max(1, min(int(os.getenv("RAG_MAX_QUERY_RESULTS", "50")), 500))
MAX_DOCUMENT_CHARS = max(1_000, int(os.getenv("RAG_MAX_DOCUMENT_CHARS", "100000")))
STATS_PAGE_SIZE = max(100, min(int(os.getenv("RAG_STATS_PAGE_SIZE", "1000")), 10_000))

if not CHROMA_HOST and not os.path.exists(CHROMA_DB_PATH):
    archive_path = os.path.join(PROJECT_DIR, "data_archive", "chroma_homework_db")
    if os.path.exists(archive_path):
        CHROMA_DB_PATH = archive_path


def _import_chroma():
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required for homework RAG") from exc
    return chromadb


def _create_embedding_function():
    if EMBEDDING_PROVIDER == "local":
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        logger.info("[RAG] Using Chroma default local ONNX embedding function")
        return DefaultEmbeddingFunction()
    if EMBEDDING_PROVIDER == "sentence_transformer":
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        logger.info("[RAG] Using sentence-transformer model %s", LOCAL_EMBEDDING_MODEL)
        return SentenceTransformerEmbeddingFunction(model_name=LOCAL_EMBEDDING_MODEL)
    if EMBEDDING_PROVIDER == "api":
        if not QWEN_API_KEY:
            raise ValueError("EMBEDDING_PROVIDER=api requires QWEN_API_KEY")
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        kwargs: Dict[str, Any] = {
            "model_name": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            "api_key": QWEN_API_KEY,
        }
        if QWEN_ENDPOINT:
            kwargs["api_base"] = QWEN_ENDPOINT
        return OpenAIEmbeddingFunction(**kwargs)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER}")


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
        chromadb = _import_chroma()
        self.persist_dir = persist_directory or CHROMA_DB_PATH
        self._write_lock = threading.RLock()
        self._chinese_lock = threading.Lock()
        self._chinese_collection = None

        if CHROMA_HOST:
            self.client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT, ssl=CHROMA_SSL)
            logger.info("[RAG] Using server-backed Chroma at %s:%s", CHROMA_HOST, CHROMA_PORT)
        else:
            os.makedirs(self.persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            logger.warning(
                "[RAG] Using local PersistentClient. Set CHROMA_HOST for multi-instance production."
            )

        self.embedding_function = _create_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name="homework_collection",
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def chinese_collection(self):
        if self._chinese_collection is None:
            with self._chinese_lock:
                if self._chinese_collection is None:
                    self._chinese_collection = self.client.get_or_create_collection(
                        name="chinese_collection",
                        embedding_function=self.embedding_function,
                        metadata={"hnsw:space": "cosine"},
                    )
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
            self.collection.add(documents=[content], metadatas=[sanitized], ids=[doc_id])

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
            lambda: self.collection.add(documents=texts, metadatas=metadatas, ids=doc_ids),
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
        query_kwargs: Dict[str, Any] = {
            "query_texts": [clean_query[:10_000]],
            "n_results": _bounded_k(k),
            "include": ["documents", "metadatas", "distances"],
        }
        where = self._build_where_clause(filters or {})
        if where:
            query_kwargs["where"] = where
        raw = self.collection.query(**query_kwargs)
        if not raw or not raw.get("ids") or not raw["ids"][0]:
            return []
        results: List[Dict[str, Any]] = []
        ids = raw["ids"][0]
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        for index, doc_id in enumerate(ids):
            distance = distances[index] if index < len(distances) else None
            similarity = None if distance is None else max(-1.0, min(1.0, 1.0 - float(distance)))
            results.append(
                {
                    "doc_id": doc_id,
                    "content": docs[index] if index < len(docs) else "",
                    "metadata": metas[index] if index < len(metas) else {},
                    # Keep score for backward compatibility, but identify it correctly.
                    "score": distance,
                    "distance": distance,
                    "similarity": similarity,
                }
            )
        return results

    def search_by_metadata(self, filters: Dict[str, Any], k: int = 10) -> List[Dict[str, Any]]:
        where = self._build_where_clause(filters)
        if not where:
            raise ValueError("At least one metadata filter is required")
        raw = self.collection.get(
            where=where,
            limit=_bounded_k(k),
            include=["documents", "metadatas"],
        )
        if not raw or not raw.get("ids"):
            return []
        return [
            {
                "doc_id": raw["ids"][i],
                "content": raw.get("documents", [""] * len(raw["ids"]))[i],
                "metadata": raw.get("metadatas", [{}] * len(raw["ids"]))[i],
            }
            for i in range(len(raw["ids"]))
        ]

    def delete_homework(self, doc_id: str) -> bool:
        if not doc_id:
            return False
        try:
            self._retry_write(lambda: self.collection.delete(ids=[doc_id]), f"delete {doc_id}")
            return True
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        total = int(self.collection.count())
        subject_counts: Dict[str, int] = {}
        year_counts: Dict[Any, int] = {}
        offset = 0
        while offset < total:
            raw = self.collection.get(
                limit=min(STATS_PAGE_SIZE, total - offset),
                offset=offset,
                include=["metadatas"],
            )
            metas = raw.get("metadatas") or []
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
        raw = self.collection.get(
            where=self._build_where_clause(filters),
            limit=max(1, min(int(limit), 500)),
            include=["documents", "metadatas"],
        )
        ids = raw.get("ids") or []
        return [
            {
                "doc_id": ids[i],
                "content": raw.get("documents", [""] * len(ids))[i],
                "metadata": raw.get("metadatas", [{}] * len(ids))[i],
            }
            for i in range(len(ids))
        ]

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
                    existing = self.chinese_collection.get(ids=[doc_id], include=[])
                    if existing and existing.get("ids"):
                        continue
                    texts.append(f"Chinese Textbook - Year {year}\nVolume: {volume}\nFile: {filename}")
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
                lambda: self.chinese_collection.add(documents=texts, metadatas=metas, ids=ids),
                f"ingest {len(ids)} Chinese textbook records",
            )
        return len(ids)

    def search_chinese_textbooks(
        self,
        query: str,
        year_group: Optional[int] = None,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {
            "query_texts": [str(query or "").strip()[:10_000]],
            "n_results": _bounded_k(k),
            "include": ["documents", "metadatas", "distances"],
        }
        if year_group is not None:
            kwargs["where"] = {"year_group": int(year_group)}
        raw = self.chinese_collection.query(**kwargs)
        ids = raw.get("ids", [[]])[0] if raw else []
        return [
            {
                "doc_id": ids[i],
                "content": raw["documents"][0][i],
                "metadata": raw["metadatas"][0][i],
                "distance": raw["distances"][0][i],
            }
            for i in range(len(ids))
        ]

    def search_homework_answers(self, doc_id: str) -> Optional[list]:
        if not doc_id:
            return None
        try:
            result = self.collection.get(ids=[doc_id], include=["metadatas"])
        except Exception:
            logger.exception("[RAG] Failed to read answers for %s", doc_id)
            return None
        if not result or not result.get("ids"):
            return None
        metadata = (result.get("metadatas") or [{}])[0]
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


def get_homework_rag_store() -> HomeworkRAGStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = HomeworkRAGStore()
    return _store


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


def get_student_homework_history(student_id: str, subject: Optional[str] = None) -> List[Dict[str, Any]]:
    return get_homework_rag_store().get_student_homework_history(student_id, subject)


def get_student_previous_topics(student_id: str, subject: str) -> List[str]:
    return get_homework_rag_store().get_student_previous_topics(student_id, subject)


def ingest_chinese_textbooks(chinese_dir: Optional[str] = None) -> int:
    return get_homework_rag_store().ingest_chinese_textbooks(chinese_dir)


def search_chinese_textbooks(query: str, year_group: Optional[int] = None, k: int = 5) -> List[Dict[str, Any]]:
    return get_homework_rag_store().search_chinese_textbooks(query, year_group, k)


def search_homework_answers(doc_id: str) -> Optional[list]:
    return get_homework_rag_store().search_homework_answers(doc_id)
